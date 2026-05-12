# ============================================================
# donna_headlines.py — DONNA v5.0 Headline & Calendar Engine
# Primary:   FMP economic calendar API (full week, USD only)
# Secondary: ForexFactory public JSON feed — no scraping
# process_headlines_cycle() → every 15 min (full fetch + persist)
# check_todays_events()     → every 5 min  (re-score timing only)
# ============================================================

from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
import json
import os
import requests

BASE_DIR = Path(__file__).parent
MACRO_EVENTS_FILE = BASE_DIR / 'donna_macro_events.json'
RISK_STATE_FILE   = BASE_DIR / 'donna_risk_state.json'
NY_TZ = ZoneInfo('America/New_York')

FMP_API_KEY = os.getenv('FMP_API_KEY', '').strip()

# Event names that automatically trigger red_folder_week
_RED_FOLDER_NAMES = {
    'cpi', 'nonfarm payroll', 'nfp', 'fomc', 'fed rate',
    'ppi', 'retail sales', 'federal reserve', 'interest rate decision',
    'unemployment rate', 'core cpi', 'core pce',
}


# ── utilities ─────────────────────────────────────────────────
def _now_ny() -> datetime:
    return datetime.now(NY_TZ)

def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def _read_json(path: Path, default):
    try:
        if path.exists():
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception:
        pass
    return default

def _write_json(path: Path, data: dict):
    data['_last_updated'] = _utc_iso()
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)

def _safe_get(url: str, params=None, timeout: int = 18):
    try:
        r = requests.get(url, params=params, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f'[donna_headlines] GET {url} failed: {e}')
        return None

def _week_bounds() -> tuple[str, str]:
    now    = _now_ny()
    monday = now - timedelta(days=now.weekday())
    friday = monday + timedelta(days=4)
    return monday.strftime('%Y-%m-%d'), friday.strftime('%Y-%m-%d')

def _phase_from_mins(mins: int | None) -> str:
    if mins is None:
        return 'NONE'
    if mins < 0:
        return 'PASSED'
    if mins <= 5:
        return 'LIVE'
    if mins <= 15:
        return 'IMMINENT'
    if mins <= 45:
        return 'APPROACHING'
    return 'SCHEDULED'


# ── classifiers ───────────────────────────────────────────────
_NON_FINANCIAL = {
    'holiday', 'christmas', 'thanksgiving', 'easter', 'new year', 'independence day',
    'memorial day', 'labor day', 'martin luther king', 'presidents day', 'columbus day',
    'veterans day', 'good friday', 'daylight saving', 'daylight savings', 'clocks change',
    'bank holiday', 'public holiday', 'market closed', 'exchange closed',
}

def _category(title: str) -> str:
    t = title.lower()
    if any(w in t for w in ['fed', 'fomc', 'powell', 'rate decision', 'rate hike', 'rate cut']):
        return 'fed'
    if any(w in t for w in ['cpi', 'pce', 'inflation', 'ppi']):
        return 'inflation'
    if any(w in t for w in ['jobs', 'payroll', 'unemployment', 'jobless', 'nfp']):
        return 'employment'
    if any(w in t for w in ['gdp', 'growth', 'recession']):
        return 'growth'
    if any(w in t for w in ['retail sales', 'consumer confidence', 'consumer sentiment']):
        return 'consumer'
    return 'macro'

def _normalize_impact(raw: str) -> str:
    r = raw.strip().lower()
    if r in ('high', '3', 'red'):
        return 'high'
    if r in ('medium', 'moderate', '2', 'orange'):
        return 'medium'
    return 'low'

def _is_financial(event: dict) -> bool:
    t = event.get('title', '').lower()
    if any(w in t for w in _NON_FINANCIAL):
        return False
    return event.get('importance') in ('high', 'medium')

def _is_red_folder_event(title: str) -> bool:
    t = title.lower()
    return any(k in t for k in _RED_FOLDER_NAMES)


# ── FMP economic calendar — primary ──────────────────────────
def _fetch_fmp_calendar(mon_str: str, fri_str: str) -> list[dict]:
    if not FMP_API_KEY:
        return []
    data = _safe_get(
        'https://financialmodelingprep.com/api/v3/economic_calendar',
        {'from': mon_str, 'to': fri_str, 'apikey': FMP_API_KEY},
    )
    if not isinstance(data, list):
        return []

    events: list[dict] = []
    for item in data:
        title = str(item.get('event', '')).strip()
        if not title:
            continue

        # FMP uses 'country' for USD events
        currency = str(item.get('currency', '') or item.get('country', '')).upper()
        if currency not in ('USD', 'US'):
            continue

        imp_raw    = str(item.get('impact', '') or item.get('importance', '')).strip()
        importance = _normalize_impact(imp_raw)
        if importance == 'low':
            continue

        # Date/time — FMP delivers "YYYY-MM-DD HH:MM:SS" in ET
        raw_date = str(item.get('date', '')).strip()
        date_str = raw_date[:10] if len(raw_date) >= 10 else mon_str
        time_et  = '08:30'
        if len(raw_date) > 10:
            try:
                dt_str   = raw_date.replace('T', ' ')[:16]
                dt       = datetime.strptime(dt_str, '%Y-%m-%d %H:%M')
                date_str = dt.strftime('%Y-%m-%d')
                time_et  = dt.strftime('%H:%M')
            except Exception:
                pass

        forecast = str(item.get('estimate', '') or '').strip() or '—'
        previous = str(item.get('previous', '') or '').strip() or '—'

        events.append({
            'title':      title,
            'time_et':    time_et,
            'importance': importance,
            'category':   _category(title),
            'note':       f'Forecast: {forecast} | Prev: {previous}',
            'date':       date_str,
            'currency':   'USD',
            'source':     'FMP',
        })
    return events


# ── ForexFactory public JSON feed — secondary ─────────────────
def _fetch_ff_json_calendar() -> list[dict]:
    """Uses ForexFactory's public JSON endpoint — no HTML scraping."""
    data = _safe_get('https://nfs.faireconomy.media/ff_calendar_thisweek.json', timeout=15)
    if not isinstance(data, list):
        return []

    current_year = _now_ny().year
    events: list[dict] = []

    for item in data:
        country = str(item.get('country', '') or item.get('currency', '')).upper()
        if country != 'USD':
            continue

        imp_raw    = str(item.get('impact', '')).strip()
        importance = _normalize_impact(imp_raw)
        if importance == 'low':
            continue

        title = str(item.get('title', '') or item.get('name', '')).strip()
        if not title:
            continue

        # Date: try ISO first, then "Jan 15, 2024" / "Jan 15"
        raw_date = str(item.get('date', '')).strip()
        date_str = ''
        time_et  = '08:30'

        if 'T' in raw_date or (len(raw_date) > 10 and ' ' in raw_date):
            try:
                dt       = datetime.fromisoformat(raw_date)
                dt_ny    = dt.astimezone(NY_TZ)
                date_str = dt_ny.strftime('%Y-%m-%d')
                time_et  = dt_ny.strftime('%H:%M')
            except Exception:
                pass

        if not date_str:
            for fmt in ('%b %d, %Y', '%b %d'):
                try:
                    suffix = f' {current_year}' if '%Y' not in fmt else ''
                    dt = datetime.strptime(raw_date + suffix, fmt + (' %Y' if suffix else ''))
                    date_str = dt.strftime('%Y-%m-%d')
                    break
                except ValueError:
                    pass

        if not date_str:
            continue

        # Separate time field
        raw_time = str(item.get('time', '')).strip().lower()
        if raw_time and raw_time not in ('all day', 'tentative', ''):
            for fmt in ('%I:%M%p', '%I%p', '%H:%M'):
                try:
                    time_et = datetime.strptime(raw_time, fmt).strftime('%H:%M')
                    break
                except ValueError:
                    pass

        forecast = str(item.get('forecast', '') or '').strip() or '—'
        previous = str(item.get('previous', '') or '').strip() or '—'

        events.append({
            'title':      title,
            'time_et':    time_et,
            'importance': importance,
            'category':   _category(title),
            'note':       f'Forecast: {forecast} | Prev: {previous}',
            'date':       date_str,
            'currency':   'USD',
            'source':     'ForexFactory',
        })
    return events


# ── merge & deduplicate ───────────────────────────────────────
def _merge_events(primary: list[dict], secondary: list[dict]) -> list[dict]:
    """Primary (FMP) wins on duplicates; secondary fills gaps."""
    seen: set[tuple] = set()
    merged: list[dict] = []
    for ev in primary + secondary:
        key = (ev['date'], ev['title'].lower()[:32])
        if key not in seen:
            seen.add(key)
            merged.append(ev)
    return sorted(merged, key=lambda e: (e['date'], e['time_et']))


# ── next-event finder ────────────────────────────────────────
def _compute_next_event(events: list[dict]) -> tuple[str, int | None]:
    now = _now_ny()
    best_title: str | None = None
    best_mins:  int | None = None
    for ev in events:
        try:
            h, m = [int(x) for x in ev['time_et'].split(':')]
            target = now.replace(hour=h, minute=m, second=0, microsecond=0)
            mins   = int((target - now).total_seconds() // 60)
            if mins >= -10 and (best_mins is None or mins < best_mins):
                best_mins  = mins
                best_title = ev['title']
        except Exception:
            continue
    return (best_title or 'No scheduled event', best_mins)


# ── weekly summary + morning brief ───────────────────────────
def _build_weekly_summary(week_events: list[dict]) -> list[dict]:
    return [
        {'title': e['title'], 'date': e['date'], 'time_et': e['time_et'], 'category': e['category']}
        for e in week_events
        if e.get('importance') == 'high'
    ]

def _build_morning_brief_lead(week_events: list[dict]) -> str:
    highs = _build_weekly_summary(week_events)
    if not highs:
        return 'No HIGH-impact macro events scheduled this week.'
    parts = [f"{e['title']} ({e['date'][5:]} {e['time_et']}ET)" for e in highs]
    return 'THIS WEEK HIGH IMPACT: ' + ' | '.join(parts)


# ── public: is_red_folder_week ────────────────────────────────
def is_red_folder_week() -> bool:
    """
    Returns True when CPI / NFP / FOMC / PPI / Retail Sales are present
    this week, OR when 3+ HIGH-impact USD events are scheduled.
    Auto-writes red_folder_week=True and macro_risk=high to risk state.
    """
    macro       = _read_json(MACRO_EVENTS_FILE, {})
    week_events = macro.get('events', [])
    mon_str, fri_str = _week_bounds()

    week_events = [e for e in week_events if mon_str <= e.get('date', '') <= fri_str]

    name_hit   = any(_is_red_folder_event(e.get('title', '')) for e in week_events)
    high_count = sum(1 for e in week_events if e.get('importance') == 'high')
    is_red     = name_hit or high_count >= 3

    if is_red:
        risk = _read_json(RISK_STATE_FILE, {})
        risk['red_folder_week'] = True
        risk['macro_risk']      = 'high'
        risk['last_updated']    = _utc_iso()
        with open(RISK_STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(risk, f, indent=2)
        reason = 'key event name' if name_hit else f'{high_count} HIGH events'
        print(f'[donna_headlines] Red-folder week confirmed ({reason})')

    return is_red


# ── public: check_todays_breaking_events (on-demand / startup) ──
_BREAKING_KEYWORDS = {
    'cpi', 'core cpi', 'inflation', 'nonfarm payroll', 'nfp',
    'fomc', 'fed rate', 'federal reserve', 'interest rate decision',
    'ppi', 'retail sales', 'unemployment rate', 'core pce',
}

def check_todays_breaking_events() -> dict:
    """
    Reads donna_macro_events.json and immediately escalates risk state when
    any HIGH-impact USD event falls today.
    - Sets macro_risk=high and headline_risk=high in risk state.
    - Scans all week events for CPI/NFP/FOMC/PPI/Retail Sales keywords
      and sets red_folder_week=True if found.
    Returns a summary dict describing every action taken.
    Safe to call from startup and the /breaking-check endpoint.
    """
    macro       = _read_json(MACRO_EVENTS_FILE, {})
    all_events  = macro.get('events', [])
    today       = _now_ny().strftime('%Y-%m-%d')
    mon_str, fri_str = _week_bounds()

    # Today's HIGH events
    todays_high = [
        e for e in all_events
        if e.get('date') == today and e.get('importance') == 'high'
    ]

    # Week-wide red-folder keyword scan
    week_events = [e for e in all_events if mon_str <= e.get('date', '') <= fri_str]
    red_keywords_hit = [
        e['title'] for e in week_events
        if any(k in e.get('title', '').lower() for k in _BREAKING_KEYWORDS)
    ]
    is_red = bool(red_keywords_hit) or sum(
        1 for e in week_events if e.get('importance') == 'high'
    ) >= 3

    risk_escalated = bool(todays_high)

    if risk_escalated or is_red:
        risk = _read_json(RISK_STATE_FILE, {})
        if risk_escalated:
            risk['macro_risk']    = 'high'
            risk['headline_risk'] = 'high'
        if is_red:
            risk['red_folder_week'] = True
            risk['macro_risk']      = 'high'
        risk['last_updated'] = _utc_iso()
        with open(RISK_STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(risk, f, indent=2)

    next_event, mins = _compute_next_event(todays_high) if todays_high else ('None today', None)

    result = {
        'checked_at':       _utc_iso(),
        'today':            today,
        'events_found':     len(todays_high),
        'high_events':      [{'title': e['title'], 'time_et': e['time_et']} for e in todays_high],
        'risk_escalated':   risk_escalated,
        'red_folder':       is_red,
        'red_keywords_hit': red_keywords_hit,
        'next_high_event':  next_event,
        'minutes_away':     mins,
        'macro_risk':       'high' if (risk_escalated or is_red) else 'unchanged',
        'headline_risk':    'high' if risk_escalated else 'unchanged',
    }

    print(f'[donna_headlines] breaking-check — {len(todays_high)} HIGH events today, '
          f'red_folder={is_red}, escalated={risk_escalated}')
    return result


# ── public: check_todays_events (every 5 min) ─────────────────
def check_todays_events():
    """
    Called every 5 minutes. Reads cached week events, recomputes event_phase
    and timing fields for today. Escalates macro_risk to HIGH if any HIGH-impact
    event is within 60 minutes or currently live.
    """
    macro       = _read_json(MACRO_EVENTS_FILE, {})
    week_events = macro.get('events', [])

    today = _now_ny().strftime('%Y-%m-%d')
    today_all  = sorted(
        [e for e in week_events if e.get('date') == today and _is_financial(e)],
        key=lambda e: e.get('time_et', '')
    )
    today_high = [e for e in today_all if e.get('importance') == 'high']

    next_event, mins = _compute_next_event(today_all)
    phase = _phase_from_mins(mins)

    # If a HIGH event is sooner, use its phase
    if today_high:
        _, high_mins = _compute_next_event(today_high)
        if high_mins is not None and (mins is None or high_mins <= mins):
            phase = _phase_from_mins(high_mins)

    risk = _read_json(RISK_STATE_FILE, {})
    risk['next_event']       = next_event
    risk['minutes_to_event'] = mins
    risk['event_phase']      = phase

    if today_high:
        risk['macro_risk'] = 'high'

    risk['last_updated'] = _utc_iso()
    with open(RISK_STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(risk, f, indent=2)

    print(f'[donna_headlines] check_todays_events — {len(today_all)} events today '
          f'({len(today_high)} HIGH). Next: "{next_event}" in {mins}min, phase: {phase}')


# ── main cycle (every 15 min) ─────────────────────────────────
def process_headlines_cycle():
    """
    Full fetch + persist cycle called by headline_loop() every 15 minutes.
    1. Fetches Mon–Fri from FMP (primary) and ForexFactory JSON (secondary).
    2. Merges, deduplicates, filters to USD HIGH/MEDIUM only.
    3. Persists to donna_macro_events.json.
    4. Detects red-folder week (name-based and count-based).
    5. Writes weekly_summary, morning_brief_lead, and timing to risk state.
    """
    print(f'[donna_headlines] Running cycle at {_now_ny().strftime("%H:%M:%S")} ET')

    mon_str, fri_str = _week_bounds()

    # 1. Fetch both sources
    fmp_events = _fetch_fmp_calendar(mon_str, fri_str)
    ff_events  = [
        e for e in _fetch_ff_json_calendar()
        if mon_str <= e.get('date', '') <= fri_str
    ]
    week_events = _merge_events(fmp_events, ff_events)

    source = 'FMP+ForexFactory' if (fmp_events and ff_events) \
        else ('FMP' if fmp_events else ('ForexFactory' if ff_events else 'none'))

    print(f'[donna_headlines] {len(week_events)} USD HIGH/MEDIUM events '
          f'({mon_str}→{fri_str}) — source: {source}')

    # 2. Persist full week
    _write_json(MACRO_EVENTS_FILE, {
        'source':     source,
        'fetched_at': _utc_iso(),
        'week_start': mon_str,
        'week_end':   fri_str,
        'events':     week_events,
    })

    # 3. Red-folder detection
    is_red = is_red_folder_week()

    # 4. Weekly summary + morning brief lead (shown every day at top of brief)
    weekly_summary     = _build_weekly_summary(week_events)
    morning_brief_lead = _build_morning_brief_lead(week_events)

    # 5. Today's event timing
    today = _now_ny().strftime('%Y-%m-%d')
    today_all  = sorted(
        [e for e in week_events if e.get('date') == today and _is_financial(e)],
        key=lambda e: e.get('time_et', '')
    )
    today_high = [e for e in today_all if e.get('importance') == 'high']

    next_event, mins = _compute_next_event(today_all)
    phase = _phase_from_mins(mins)

    if today_high:
        _, high_mins = _compute_next_event(today_high)
        if high_mins is not None and (mins is None or high_mins <= mins):
            phase = _phase_from_mins(high_mins)

    # 6. Patch risk state
    risk = _read_json(RISK_STATE_FILE, {})
    risk['next_event']          = next_event
    risk['minutes_to_event']    = mins
    risk['event_phase']         = phase
    risk['weekly_summary']      = weekly_summary
    risk['morning_brief_lead']  = morning_brief_lead
    risk['red_folder_week']     = is_red

    if today_high:
        risk['macro_risk'] = 'high'

    try:
        if today_all:
            first = today_all[0]
            h, m_part = [int(x) for x in first['time_et'].split(':')]
            now = _now_ny()
            risk['event_time_ny'] = now.replace(
                hour=h, minute=m_part, second=0, microsecond=0
            ).isoformat()
    except Exception:
        pass

    risk['last_updated'] = _utc_iso()
    with open(RISK_STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(risk, f, indent=2)

    print(f'[donna_headlines] Done — {len(week_events)} week, '
          f'{len(today_all)} today ({len(today_high)} HIGH). '
          f'Phase: {phase} | Red-folder: {is_red}')
