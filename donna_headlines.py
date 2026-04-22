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
import os
import requests

BASE_DIR = Path(__file__).parent
MACRO_EVENTS_FILE = BASE_DIR / 'donna_macro_events.json'
RISK_STATE_FILE   = BASE_DIR / 'donna_risk_state.json'
NY_TZ = ZoneInfo('America/New_York')

FINNHUB_API_KEY = os.getenv('FINNHUB_API_KEY', '').strip()
FMP_API_KEY     = os.getenv('FMP_API_KEY', '').strip()


def _now_ny():
    return datetime.now(NY_TZ)

def _utc_iso():
    return datetime.now(timezone.utc).isoformat()

def _safe_get(url, params=None, timeout=18):
    try:
        r = requests.get(url, params=params, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f'[donna_headlines] GET {url} failed: {e}')
        return None

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


# ── importance scoring ────────────────────────────────────────
_HIGH_WORDS = {
    'fomc', 'fed rate', 'federal reserve', 'interest rate decision',
    'cpi', 'nonfarm payroll', 'nfp', 'gdp', 'pce', 'core inflation',
    'unemployment rate', 'jobs report', 'powell speech',
    'debt ceiling', 'treasury auction',
}
_MEDIUM_WORDS = {
    'retail sales', 'consumer confidence', 'consumer sentiment',
    'housing starts', 'building permits', 'jobless claims',
    'manufacturing pmi', 'services pmi', 'ism', 'ppi',
    'durable goods', 'trade balance', 'factory orders',
}

def _importance(title: str) -> str:
    t = title.lower()
    if any(w in t for w in _HIGH_WORDS):
        return 'high'
    if any(w in t for w in _MEDIUM_WORDS):
        return 'medium'
    return 'low'

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


# ── Finnhub economic calendar ─────────────────────────────────
def _fetch_finnhub_calendar() -> list[dict]:
    if not FINNHUB_API_KEY:
        return []
    now = _now_ny()
    from_date = now.strftime('%Y-%m-%d')
    to_date   = (now + timedelta(days=7)).strftime('%Y-%m-%d')
    data = _safe_get(
        'https://finnhub.io/api/v1/calendar/economic',
        {'from': from_date, 'to': to_date, 'token': FINNHUB_API_KEY}
    )
    if not data:
        return []
    raw = data.get('economicCalendar') or data.get('economic') or []
    if not isinstance(raw, list):
        return []

    events = []
    for item in raw[:40]:
        title = str(item.get('event', '') or item.get('name', '')).strip()
        if not title:
            continue
        # Parse time
        time_str = str(item.get('time', '') or '').strip()
        if not time_str:
            date_str = str(item.get('date', '')).strip()
            time_et = '08:30'  # default pre-market
        else:
            try:
                # Finnhub returns UTC time — convert to ET
                dt_utc = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
                dt_ny  = dt_utc.astimezone(NY_TZ)
                time_et = dt_ny.strftime('%H:%M')
            except Exception:
                time_et = time_str[:5]

        events.append({
            'title':      title,
            'time_et':    time_et,
            'importance': _importance(title),
            'category':   _category(title),
            'note':       f"Est: {item.get('estimate', '—')} | Prev: {item.get('prev', '—')}",
            'date':       str(item.get('date', now.strftime('%Y-%m-%d'))),
        })
    return events


# ── FMP economic calendar fallback ───────────────────────────
def _fetch_fmp_calendar() -> list[dict]:
    if not FMP_API_KEY:
        return []
    now = _now_ny()
    from_date = now.strftime('%Y-%m-%d')
    to_date   = (now + timedelta(days=7)).strftime('%Y-%m-%d')
    data = _safe_get(
        'https://financialmodelingprep.com/api/v3/economic_calendar',
        {'from': from_date, 'to': to_date, 'apikey': FMP_API_KEY}
    )
    if not isinstance(data, list):
        return []

    events = []
    for item in data[:40]:
        title = str(item.get('event', '')).strip()
        if not title:
            continue
        date_str = str(item.get('date', '')).strip()
        time_et  = '08:30'
        if date_str and 'T' in date_str:
            try:
                dt_utc = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                dt_ny  = dt_utc.astimezone(NY_TZ)
                time_et = dt_ny.strftime('%H:%M')
                date_str = dt_ny.strftime('%Y-%m-%d')
            except Exception:
                pass

        imp_raw = str(item.get('impact', '') or item.get('importance', '')).lower()
        if 'high' in imp_raw:
            importance = 'high'
        elif 'medium' in imp_raw or 'moderate' in imp_raw:
            importance = 'medium'
        else:
            importance = _importance(title)

        events.append({
            'title':      title,
            'time_et':    time_et,
            'importance': importance,
            'category':   _category(title),
            'note':       f"Est: {item.get('estimate', '—')} | Prev: {item.get('previous', '—')}",
            'date':       date_str,
        })
    return events


# ── filter to today's events ──────────────────────────────────
def _filter_today(events: list[dict]) -> list[dict]:
    today = _now_ny().strftime('%Y-%m-%d')
    today_events = [e for e in events if e.get('date', '') == today]
    if today_events:
        return sorted(today_events, key=lambda e: e.get('time_et', ''))
    # If no today events, return next 2 days of high/medium importance
    upcoming = [e for e in events if e.get('importance') in ('high', 'medium')]
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
    Fetches macro calendar, updates donna_macro_events.json,
    and patches next_event / minutes_to_event / event_phase in risk state.
    """
    print(f'[donna_headlines] Running cycle at {_now_ny().strftime("%H:%M:%S")} ET')

    # 1. Fetch calendar
    events = _fetch_finnhub_calendar()
    if not events:
        events = _fetch_fmp_calendar()

    today_events = _filter_today(events) if events else []

    # 2. Write macro events file
    macro_data = {
        'source': 'Finnhub/FMP live calendar',
        'fetched_at': _utc_iso(),
        'events': today_events,
    }
    _write_json(MACRO_EVENTS_FILE, macro_data)

    # 3. Compute next event
    next_event, mins_to_event = _compute_next_event(today_events)

    # Phase
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

    # 4. Patch risk state — only update calendar-related fields
    risk = _read_json(RISK_STATE_FILE, {})
    risk['next_event']       = next_event
    risk['minutes_to_event'] = mins_to_event
    risk['event_phase']      = event_phase

    # Recompute event_time_ny
    try:
        now = _now_ny()
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

    print(f'[donna_headlines] Done — {len(today_events)} events loaded. '
          f'Next: "{next_event}" in {mins_to_event}min, phase: {event_phase}')
