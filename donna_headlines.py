# ============================================================
# donna_headlines.py — DONNA v5.0 Headline & Calendar Engine
# Replaces the stub process_headlines_cycle() in main.py
#
# DROP THIS FILE into your project root alongside main.py
# Called by headline_loop() every 15 minutes
# ============================================================

from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
import json
import requests

BASE_DIR = Path(__file__).parent
MACRO_EVENTS_FILE = BASE_DIR / 'donna_macro_events.json'
RISK_STATE_FILE   = BASE_DIR / 'donna_risk_state.json'
NY_TZ = ZoneInfo('America/New_York')

_FF_HEADERS = {
    'User-Agent':      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept':          'text/html,application/xhtml+xml,application/xhtml+xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection':      'keep-alive',
    'Cache-Control':   'max-age=0',
    'Upgrade-Insecure-Requests': '1',
}


def _now_ny():
    return datetime.now(NY_TZ)

def _utc_iso():
    return datetime.now(timezone.utc).isoformat()

def _read_json(path, default):
    try:
        if path.exists():
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception:
        pass
    return default

def _write_json(path, data):
    data['_last_updated'] = _utc_iso()
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)


# ── category classifier ───────────────────────────────────────
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
    if any(w in t for w in ['jobs', 'payroll', 'unemployment', 'jobless']):
        return 'employment'
    if any(w in t for w in ['gdp', 'growth', 'recession']):
        return 'growth'
    return 'macro'


# ── ForexFactory scraper ──────────────────────────────────────
def _fetch_forexfactory_calendar() -> list[dict]:
    from bs4 import BeautifulSoup

    try:
        resp = requests.get(
            'https://www.forexfactory.com/calendar',
            headers=_FF_HEADERS,
            timeout=20,
        )
        resp.raise_for_status()
    except Exception as e:
        print(f'[donna_headlines] ForexFactory fetch failed: {e}')
        return []

    soup = BeautifulSoup(resp.text, 'html.parser')
    events = []
    current_date = None
    current_year = _now_ny().year

    for row in soup.select('tr.calendar__row'):
        # ── date (carried forward across rows) ───────────────────
        date_cell = row.select_one('td.calendar__date')
        if date_cell:
            date_text = date_cell.get_text(strip=True)
            if date_text:
                for fmt in ('%a%b %d', '%a %b %d'):
                    try:
                        dt = datetime.strptime(f'{date_text} {current_year}', f'{fmt} %Y')
                        current_date = dt.strftime('%Y-%m-%d')
                        break
                    except ValueError:
                        pass

        if not current_date:
            continue

        # ── currency filter ───────────────────────────────────────
        cur_cell = row.select_one('td.calendar__currency')
        if not cur_cell or cur_cell.get_text(strip=True).upper() != 'USD':
            continue

        # ── impact: red=HIGH, orange=MEDIUM, yellow=LOW ───────────
        impact = 'low'
        impact_cell = row.select_one('td.calendar__impact')
        if impact_cell:
            span = impact_cell.find('span')
            if span:
                span_classes = ' '.join(span.get('class', []))
                span_title   = span.get('title', '').lower()
                if 'high' in span_classes or 'red' in span_classes or 'high' in span_title:
                    impact = 'high'
                elif 'medium' in span_classes or 'orange' in span_classes or 'medium' in span_title:
                    impact = 'medium'

        # ── title ─────────────────────────────────────────────────
        event_cell = row.select_one('td.calendar__event')
        if not event_cell:
            continue
        title_el = event_cell.select_one('.calendar__event-title') or event_cell
        title = title_el.get_text(strip=True)
        if not title:
            continue

        # ── time (ForexFactory displays ET) ──────────────────────
        time_et = '08:30'
        time_cell = row.select_one('td.calendar__time')
        if time_cell:
            time_text = time_cell.get_text(strip=True).lower()
            if time_text:
                for fmt in ('%I:%M%p', '%I%p'):
                    try:
                        time_et = datetime.strptime(time_text, fmt).strftime('%H:%M')
                        break
                    except ValueError:
                        pass

        # ── forecast / previous ───────────────────────────────────
        fc_cell   = row.select_one('td.calendar__forecast')
        prev_cell = row.select_one('td.calendar__previous')
        forecast  = (fc_cell.get_text(strip=True)   if fc_cell   else '') or '—'
        previous  = (prev_cell.get_text(strip=True) if prev_cell else '') or '—'

        events.append({
            'title':      title,
            'time_et':    time_et,
            'importance': impact,
            'category':   _category(title),
            'note':       f'Forecast: {forecast} | Prev: {previous}',
            'date':       current_date,
            'currency':   'USD',
        })

    return events


# ── red-folder week detector ──────────────────────────────────
def is_red_folder_week() -> bool:
    """
    Returns True when 3+ HIGH-impact USD events fall within Mon–Fri of the
    current week.  Automatically sets red_folder_week=True and
    macro_risk='high' in donna_risk_state.json when the threshold is met.
    """
    now    = _now_ny()
    monday = now - timedelta(days=now.weekday())
    friday = monday + timedelta(days=4)
    mon_str = monday.strftime('%Y-%m-%d')
    fri_str = friday.strftime('%Y-%m-%d')

    macro  = _read_json(MACRO_EVENTS_FILE, {})
    events = macro.get('events', [])

    high_count = sum(
        1 for e in events
        if e.get('importance') == 'high'
        and mon_str <= e.get('date', '') <= fri_str
    )

    is_red = high_count >= 3
    if is_red:
        risk = _read_json(RISK_STATE_FILE, {})
        risk['red_folder_week'] = True
        risk['macro_risk']      = 'high'
        risk['last_updated']    = _utc_iso()
        with open(RISK_STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(risk, f, indent=2)
        print(f'[donna_headlines] Red-folder week detected ({high_count} HIGH USD events)')

    return is_red


# ── filter helpers ────────────────────────────────────────────
def _is_financial(event: dict) -> bool:
    t = event.get('title', '').lower()
    if any(w in t for w in _NON_FINANCIAL):
        return False
    return event.get('importance') in ('high', 'medium')

def _filter_today(events: list[dict]) -> list[dict]:
    today = _now_ny().strftime('%Y-%m-%d')
    today_events = [e for e in events if e.get('date', '') == today and _is_financial(e)]
    if today_events:
        return sorted(today_events, key=lambda e: e.get('time_et', ''))
    upcoming = [e for e in events if _is_financial(e)]
    return sorted(upcoming, key=lambda e: (e.get('date', ''), e.get('time_et', '')))[:8]


# ── compute next event from today's list ─────────────────────
def _compute_next_event(events: list[dict]) -> tuple[str, int | None]:
    now = _now_ny()
    best_title, best_mins = None, None
    for ev in events:
        try:
            h, m = [int(x) for x in ev['time_et'].split(':')]
            target = now.replace(hour=h, minute=m, second=0, microsecond=0)
            mins = int((target - now).total_seconds() // 60)
            if mins >= -10 and (best_mins is None or mins < best_mins):
                best_mins = mins
                best_title = ev['title']
        except Exception:
            continue
    return (best_title or 'No scheduled event', best_mins)


# ── main cycle ────────────────────────────────────────────────
def process_headlines_cycle():
    """
    Main entry point — called by headline_loop() in main.py every 15 minutes.
    Scrapes ForexFactory for USD events, stores the full Mon–Fri week in
    donna_macro_events.json, checks for a red-folder week, then patches
    next_event / minutes_to_event / event_phase in donna_risk_state.json.
    """
    print(f'[donna_headlines] Running cycle at {_now_ny().strftime("%H:%M:%S")} ET')

    # 1. Scrape ForexFactory
    all_events = _fetch_forexfactory_calendar()

    # 2. Narrow to current Mon–Fri
    now    = _now_ny()
    monday = now - timedelta(days=now.weekday())
    friday = monday + timedelta(days=4)
    mon_str = monday.strftime('%Y-%m-%d')
    fri_str = friday.strftime('%Y-%m-%d')

    week_events = [
        e for e in all_events
        if mon_str <= e.get('date', '') <= fri_str
    ]

    # 3. Persist full week to macro events file
    _write_json(MACRO_EVENTS_FILE, {
        'source':     'ForexFactory',
        'fetched_at': _utc_iso(),
        'week_start': mon_str,
        'week_end':   fri_str,
        'events':     week_events,
    })

    # 4. Auto-flag red-folder week
    is_red_folder_week()

    # 5. Today's events for risk-state timing
    today_events = _filter_today(week_events)

    # 6. Compute next event
    next_event, mins_to_event = _compute_next_event(today_events)

    if mins_to_event is None:
        event_phase = 'NONE'
    else:
        m = int(mins_to_event)
        if m < 0:
            event_phase = 'PASSED'
        elif m <= 5:
            event_phase = 'LIVE'
        elif m <= 15:
            event_phase = 'IMMINENT'
        elif m <= 45:
            event_phase = 'APPROACHING'
        else:
            event_phase = 'SCHEDULED'

    # 7. Patch risk state — calendar fields only
    risk = _read_json(RISK_STATE_FILE, {})
    risk['next_event']       = next_event
    risk['minutes_to_event'] = mins_to_event
    risk['event_phase']      = event_phase

    try:
        if today_events:
            first = today_events[0]
            h, m_part = [int(x) for x in first['time_et'].split(':')]
            risk['event_time_ny'] = now.replace(
                hour=h, minute=m_part, second=0, microsecond=0
            ).isoformat()
    except Exception:
        pass

    risk['last_updated'] = _utc_iso()
    with open(RISK_STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(risk, f, indent=2)

    print(f'[donna_headlines] Done — {len(week_events)} USD events this week, '
          f'{len(today_events)} today. '
          f'Next: "{next_event}" in {mins_to_event}min, phase: {event_phase}')
