from __future__ import annotations

from fastapi import FastAPI, Request, HTTPException, Response
from fastapi.responses import HTMLResponse
from dotenv import load_dotenv
from pathlib import Path
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
import asyncio
import json
import os
import re
import requests

try:
    from anthropic import Anthropic
except Exception:
    Anthropic = None

try:
    from donna_news import process_news_guard_cycle
except Exception:
    def process_news_guard_cycle():
        return None

try:
    from donna_headlines import process_headlines_cycle
except Exception:
    def process_headlines_cycle():
        return None

try:
    from donna_finnhub import process_finnhub_cycle
except Exception:
    def process_finnhub_cycle():
        return None

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / '.env')

ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY', '').strip()
ANTHROPIC_MODEL = os.getenv('ANTHROPIC_MODEL', 'claude-haiku-4-5-20251001').strip()
ANTHROPIC_ASSISTANT_MODEL = os.getenv('ANTHROPIC_ASSISTANT_MODEL', 'claude-sonnet-4-6').strip()
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '').strip()
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '').strip()
TELEGRAM_ALERT_MODE = os.getenv('TELEGRAM_ALERT_MODE', 'critical').strip().lower()
FINNHUB_API_KEY = os.getenv('FINNHUB_API_KEY', '').strip()
FMP_API_KEY = os.getenv('FMP_API_KEY', '').strip()
ALPHA_VANTAGE_API_KEY = os.getenv('ALPHA_VANTAGE_API_KEY', '').strip()
FOREX_FACTORY_NOTES_URL = os.getenv('FOREX_FACTORY_NOTES_URL', '').strip()

client = Anthropic(api_key=ANTHROPIC_API_KEY) if (Anthropic and ANTHROPIC_API_KEY) else None
app = FastAPI(title='DONNA v5.0 Live Market Core', version='5.0')

NY_TZ = ZoneInfo('America/New_York')
UTC_TZ = ZoneInfo('UTC')
RISK_STATE_FILE = BASE_DIR / 'donna_risk_state.json'
ALERTS_FILE = BASE_DIR / 'donna_alert_history.json'
ASSISTANT_FILE = BASE_DIR / 'donna_assistant_state.json'
SETTINGS_FILE = BASE_DIR / 'donna_settings.json'
MACRO_EVENTS_FILE = BASE_DIR / 'donna_macro_events.json'
CACHE = {}

DEFAULT_RISK_STATE = {
    'macro_risk': 'medium',
    'headline_risk': 'medium',
    'market_news_risk': 'medium',
    'active_warnings': ['Macro timing matters today', 'Leadership concentration is elevated'],
    'next_event': '10:00 ET Data / Fed Window',
    'minutes_to_event': 45,
    'last_headline': 'Mega-cap leadership remains the main driver of Nasdaq strength.',
    'last_market_headline': 'Semis and mega-cap tech continue to control index direction.',
    'headline_guidance': 'Respect event timing and avoid treating a major NY session expansion like noise.',
    'headline_severity': 'MEDIUM',
    'last_market_guidance': 'Leadership names are doing most of the lifting. Watch NVDA, MSFT, AMZN, AMD.',
    'last_market_severity': 'HIGH',
    'event_phase': 'APPROACHING',
    'market_snapshot': {
    'SPX': {'last': 7022.95, 'chg': 55.57, 'pct': 0.80},
    'NASDAQ': {'last': 24016.01, 'chg': 376.93, 'pct': 1.60},
    'DJIA': {'last': 48463.72, 'chg': -72.27, 'pct': -0.15},
    'VIX': {'last': 18.17, 'chg': -0.19, 'pct': -1.03},
    'US10Y': {'last': 4.281, 'chg': 0.025, 'pct': 0.59},
    'DXY': {'last': 103.84, 'chg': -0.14, 'pct': -0.13},
    'NQ': {'last': 0, 'chg': 0, 'pct': 0},
    'ES': {'last': 0, 'chg': 0, 'pct': 0},
    'OIL': {'last': 0, 'chg': 0, 'pct': 0},
    'GOLD': {'last': 0, 'chg': 0, 'pct': 0},
    'SILVER': {'last': 0, 'chg': 0, 'pct': 0},
    'NQ_SESSION_POINTS': 393.0,
    'ES_SESSION_POINTS': 49.5,
},
}
DEFAULT_ASSISTANT_STATE = {
    'daily_focus': 'Trade what matters. Ignore noise.',
    'tasks': ['Review morning edge', 'Check likely market movers', 'Respect macro timing'],
    'reminders': ['Do not force trades into event windows', 'Leadership names deserve first attention'],
}

DEFAULT_SETTINGS = {
    'theme_mode': 'premium_dark',
    'layout_density': 'balanced',
    'telegram_alert_mode': TELEGRAM_ALERT_MODE or 'critical'
}

DEFAULT_MACRO_EVENTS = {
    'source': 'ForexFactory/manual',
    'events': [
        {'title': '10:00 ET Data / Fed Window', 'time_et': '10:00', 'importance': 'high', 'category': 'macro', 'note': 'High-impact macro window.'},
        {'title': '14:00 ET Fed / Rates Check', 'time_et': '14:00', 'importance': 'medium', 'category': 'fed', 'note': 'Rates-sensitive period.'},
    ],
}
def now_ny():
    return datetime.now(NY_TZ)


def now_utc():
    return datetime.now(UTC_TZ)


def utc_now_iso():
    return datetime.now(timezone.utc).isoformat()


def day_name():
    return now_ny().strftime('%A')


def session_label(dt=None):
    dt = dt or now_ny()
    m = dt.hour * 60 + dt.minute
    if m >= 19 * 60 or m < 3 * 60:
        return 'ASIA'
    if 3 * 60 <= m < 9 * 60 + 30:
        return 'LONDON'
    if 9 * 60 + 30 <= m < 16 * 60:
        return 'NEW_YORK_CASH'
    return 'OFF_HOURS'


def cache_get(key):
    v = CACHE.get(key)
    if not v:
        return None
    if datetime.now(timezone.utc).timestamp() > v['expires_at']:
        return None
    return v['value']


def cache_set(key, value, ttl):
    CACHE[key] = {'value': value, 'expires_at': datetime.now(timezone.utc).timestamp() + ttl}


def read_json_file(path, default):
    try:
        if not path.exists():
            return default
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return default


def write_json_file(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)


def ensure_files():
    if not RISK_STATE_FILE.exists():
        write_json_file(RISK_STATE_FILE, DEFAULT_RISK_STATE)
    if not ALERTS_FILE.exists():
        write_json_file(ALERTS_FILE, [])
    if not ASSISTANT_FILE.exists():
        write_json_file(ASSISTANT_FILE, DEFAULT_ASSISTANT_STATE)
    if not SETTINGS_FILE.exists():
        write_json_file(SETTINGS_FILE, DEFAULT_SETTINGS)
    if not MACRO_EVENTS_FILE.exists():
        write_json_file(MACRO_EVENTS_FILE, DEFAULT_MACRO_EVENTS)


def load_risk_state():
    data = read_json_file(RISK_STATE_FILE, DEFAULT_RISK_STATE)
    if not isinstance(data, dict):
        data = dict(DEFAULT_RISK_STATE)
    merged = dict(DEFAULT_RISK_STATE)
    merged.update(data)
    merged['donna_time_utc'] = now_utc().isoformat()
    merged['donna_time_ny'] = now_ny().isoformat()
    merged['donna_day'] = day_name()
    merged['donna_session'] = session_label()
    merged['last_updated'] = utc_now_iso()
    merged.setdefault('event_time_ny', now_ny().replace(minute=0, second=0, microsecond=0).isoformat())
    return merged


def save_risk_state(state):
    s = dict(state)
    s['last_updated'] = utc_now_iso()
    write_json_file(RISK_STATE_FILE, s)


def load_alert_history():
    data = read_json_file(ALERTS_FILE, [])
    return data if isinstance(data, list) else []


def save_alert_history(alerts):
    write_json_file(ALERTS_FILE, alerts[:50])


def load_assistant_state():
    data = read_json_file(ASSISTANT_FILE, DEFAULT_ASSISTANT_STATE)
    if not isinstance(data, dict):
        data = dict(DEFAULT_ASSISTANT_STATE)
    merged = dict(DEFAULT_ASSISTANT_STATE)
    merged.update(data)
    if not isinstance(merged.get('tasks'), list):
        merged['tasks'] = list(DEFAULT_ASSISTANT_STATE['tasks'])
    if not isinstance(merged.get('reminders'), list):
        merged['reminders'] = list(DEFAULT_ASSISTANT_STATE['reminders'])
    merged['last_updated'] = utc_now_iso()
    return merged


def save_assistant_state(state):
    s = dict(state)
    s['last_updated'] = utc_now_iso()
    write_json_file(ASSISTANT_FILE, s)


def load_settings():
    data = read_json_file(SETTINGS_FILE, DEFAULT_SETTINGS)
    if not isinstance(data, dict):
        data = dict(DEFAULT_SETTINGS)
    merged = dict(DEFAULT_SETTINGS)
    merged.update(data)
    merged['last_updated'] = utc_now_iso()
    return merged


def load_macro_events():
    data = read_json_file(MACRO_EVENTS_FILE, DEFAULT_MACRO_EVENTS)
    if not isinstance(data, dict):
        data = dict(DEFAULT_MACRO_EVENTS)
    if not isinstance(data.get('events'), list):
        data['events'] = list(DEFAULT_MACRO_EVENTS['events'])
    return data


def safe_float(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return default


def send_telegram_message(text):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return {'ok': False, 'error': 'Telegram not configured'}
    try:
        r = requests.post(f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage', json={'chat_id': TELEGRAM_CHAT_ID, 'text': text}, timeout=20)
        return r.json()
    except Exception as e:
        return {'ok': False, 'error': str(e)}


def _requests_get_json(url, params=None):
    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()
    return r.json()


def fetch_finnhub_quote(symbol):
    if not FINNHUB_API_KEY:
        return None
    try:
        d = _requests_get_json('https://finnhub.io/api/v1/quote', {'symbol': symbol, 'token': FINNHUB_API_KEY})
        c, pc = d.get('c'), d.get('pc')
        if c in (None, 0) or pc in (None, 0):
            return None
        chg = float(c) - float(pc)
        pct = chg / float(pc) * 100
        return {'last': round(float(c), 4), 'chg': round(chg, 4), 'pct': round(pct, 4)}
    except Exception:
        return None


def fetch_fmp_quote(symbol):
    if not FMP_API_KEY:
        return None
    try:
        d = _requests_get_json(f'https://financialmodelingprep.com/api/v3/quote/{symbol}', {'apikey': FMP_API_KEY})
        if not d or not isinstance(d, list):
            return None
        item = d[0]
        return {'last': round(float(item.get('price', 0)), 4), 'chg': round(float(item.get('change', 0)), 4), 'pct': round(float(item.get('changesPercentage', 0)), 4)}
    except Exception:
        return None


def fetch_alpha_quote(symbol):
    if not ALPHA_VANTAGE_API_KEY:
        return None
    try:
        d = _requests_get_json('https://www.alphavantage.co/query', {'function': 'GLOBAL_QUOTE', 'symbol': symbol, 'apikey': ALPHA_VANTAGE_API_KEY})
        q = d.get('Global Quote', {})
        if not q:
            return None
        last = float(q.get('05. price', 0))
        chg = float(q.get('09. change', 0))
        pct = float(str(q.get('10. change percent', '0')).replace('%', ''))
        return {'last': round(last, 4), 'chg': round(chg, 4), 'pct': round(pct, 4)}
    except Exception:
        return None


def get_quote_with_fallback(symbol, alt_symbol=None):
    key = f'quote::{symbol}'
    c = cache_get(key)
    if c:
        return c
    q = fetch_finnhub_quote(symbol)
    if not q and alt_symbol:
        q = fetch_finnhub_quote(alt_symbol)
    if not q:
        q = fetch_fmp_quote(symbol if not alt_symbol else alt_symbol)
    if not q:
        q = fetch_alpha_quote(symbol)
    if q:
        cache_set(key, q, 20)
    return q
    
def get_futures_quote(symbol_alias):
    futures_map = {
        'NQ': ['NQ=F', '^NDX', '^IXIC', 'QQQ'],
        'ES': ['ES=F', '^GSPC', 'SPY'],
        'OIL': ['CL=F', 'USO'],
        'GOLD': ['GC=F', 'GLD'],
        'SILVER': ['SI=F', 'SLV'],
    }

    candidates = futures_map.get(str(symbol_alias).upper(), [])
    for sym in candidates:
        q = get_quote_with_fallback(sym)
        if q and q.get('last') not in (None, '-', 0):
            return q

    return None
def fetch_fmp_market_movers(kind):
    if not FMP_API_KEY:
        return []
    endpoint_map = {'gainers': 'stock_market/gainers', 'losers': 'stock_market/losers', 'actives': 'stock_market/actives'}
    ep = endpoint_map.get(kind)
    if not ep:
        return []
    try:
        d = _requests_get_json(f'https://financialmodelingprep.com/api/v3/{ep}', {'apikey': FMP_API_KEY})
        return d if isinstance(d, list) else []
    except Exception:
        return []


def fetch_fmp_batch_quotes(symbols):
    if not FMP_API_KEY or not symbols:
        return []
    try:
        d = _requests_get_json(f"https://financialmodelingprep.com/api/v3/quote/{','.join(symbols)}", {'apikey': FMP_API_KEY})
        return d if isinstance(d, list) else []
    except Exception:
        return []


def fetch_finnhub_earnings(from_date, to_date):
    if not FINNHUB_API_KEY:
        return []
    try:
        d = _requests_get_json('https://finnhub.io/api/v1/calendar/earnings', {'from': from_date, 'to': to_date, 'token': FINNHUB_API_KEY})
        return d.get('earningsCalendar', []) or []
    except Exception:
        return []


def fetch_finnhub_market_news():
    if not FINNHUB_API_KEY:
        return []
    try:
        d = _requests_get_json('https://finnhub.io/api/v1/news', {'category': 'general', 'token': FINNHUB_API_KEY})
        return d[:8] if isinstance(d, list) else []
    except Exception:
        return []


def get_live_major_indexes():
    c = cache_get('major_indexes')
    if c:
        return c

    mapping = [
        ('NASDAQ', ['^IXIC', '^NDX', 'QQQ'], 'NASDAQ'),
        ('S&P 500', ['^GSPC', '^SPX', 'SPY'], 'SPX'),
        ('DJIA', ['^DJI', 'DIA'], 'DJIA'),
        ('VIX', ['^VIX'], 'VIX'),
        ('US 10Y', ['^TNX'], 'US10Y'),
        ('DXY', ['DX-Y.NYB'], 'DXY'),
    ]

    fallback = load_risk_state().get('market_snapshot', {})
    rows = []

    for label, candidates, fallback_key in mapping:
        q = None
        for sym in candidates:
            q = get_quote_with_fallback(sym)
            if q and q.get('last') not in (None, '-', 0):
                break

        if not q:
            q = fallback.get(fallback_key, {})

        last = (q or {}).get('last', '-')
        chg = (q or {}).get('chg', '-')
        pct_raw = (q or {}).get('pct', None)
        pct_num = safe_float(pct_raw, None) if pct_raw is not None else None

        rows.append({
            'symbol': label,
            'last': last if last not in (None, 0) else '-',
            'chg': chg if chg not in (None, 0) else '-',
            'pct': f'{pct_num:+.2f}%' if pct_num is not None and last not in (None, '-', 0) else '-',
            'dir': 'up' if (pct_num is not None and pct_num >= 0) else 'down'
        })

    cache_set('major_indexes', rows, 20)
    return rows

def get_live_futures_macro_pulse():
    c = cache_get('futures_macro_pulse')
    if c:
        return c

    fallback = load_risk_state().get('market_snapshot', {})

    rows = []

    futures_assets = [
        ('NQ', 'NQ'),
        ('ES', 'ES'),
        ('OIL', 'OIL'),
        ('GOLD', 'GOLD'),
        ('SILVER', 'SILVER'),
    ]

    macro_assets = [
        ('DXY', 'DX-Y.NYB', 'DXY'),
        ('US10Y', '^TNX', 'US10Y'),
        ('VIX', '^VIX', 'VIX'),
    ]

    for label, fallback_key in futures_assets:
        q = get_futures_quote(label)
        if not q:
            q = fallback.get(fallback_key, {})

        last = (q or {}).get('last', '-')
        chg = (q or {}).get('chg', '-')
        pct_raw = (q or {}).get('pct', None)

        pct_num = safe_float(pct_raw, None) if pct_raw is not None else None

        rows.append({
            'symbol': label,
            'last': last if last not in (None, 0) else '-',
            'chg': chg if chg not in (None, 0) else '-',
            'pct': f'{pct_num:+.2f}%' if pct_num is not None and last not in (None, '-', 0) else '-',
            'dir': 'up' if (pct_num is not None and pct_num >= 0) else 'down'
        })

    for label, symbol, fallback_key in macro_assets:
        q = get_quote_with_fallback(symbol)
        if not q:
            q = fallback.get(fallback_key, {})

        last = (q or {}).get('last', '-')
        chg = (q or {}).get('chg', '-')
        pct_raw = (q or {}).get('pct', None)

        pct_num = safe_float(pct_raw, None) if pct_raw is not None else None

        rows.append({
            'symbol': label,
            'last': last if last not in (None, 0) else '-',
            'chg': chg if chg not in (None, 0) else '-',
            'pct': f'{pct_num:+.2f}%' if pct_num is not None and last not in (None, '-', 0) else '-',
            'dir': 'up' if (pct_num is not None and pct_num >= 0) else 'down'
        })

    cache_set('futures_macro_pulse', rows, 20)
    return rows

def get_live_movers():
    c = cache_get('movers')
    if c:
        return c
    def norm(items, limit=6):
        out = []
        for it in items[:limit]:
            out.append({'symbol': it.get('symbol', '-'), 'last': it.get('price', '-'), 'chg': f"{safe_float(it.get('change', 0)):+.2f}", 'pct': f"{safe_float(it.get('changesPercentage', 0)):+.2f}%"})
        return out
    result = {'gainers': norm(fetch_fmp_market_movers('gainers')), 'losers': norm(fetch_fmp_market_movers('losers')), 'actives': norm(fetch_fmp_market_movers('actives'))}
    cache_set('movers', result, 60)
    return result


def get_live_market_data():
    c = cache_get('market_data')
    if c:
        return c
    watch = fetch_fmp_batch_quotes(['NVDA', 'MSFT', 'TSLA', 'AMD', 'AMZN', 'AAPL', 'META', 'JPM'])
    watchlist = []
    for it in watch[:10]:
        pct = safe_float(it.get('changesPercentage', 0))
        watchlist.append({'symbol': it.get('symbol', '-'), 'last': it.get('price', '-'), 'chg': f"{safe_float(it.get('change', 0)):+.2f}", 'pct': f"{pct:+.2f}%", 'dir': 'up' if pct >= 0 else 'down'})
    result = {'major_indexes': get_live_major_indexes(), 'watchlist': watchlist}
    cache_set('market_data', result, 20)
    return result


def get_live_calendar():
    c = cache_get('calendar')
    if c:
        return c
    data = load_macro_events()
    events = data.get('events', [])
    now = now_ny()
    def mins_until(t):
        try:
            h, m = [int(x) for x in t.split(':')]
            target = now.replace(hour=h, minute=m, second=0, microsecond=0)
            return int((target - now).total_seconds() // 60)
        except Exception:
            return None
    rows, next_event, next_minutes = [], None, None
    for ev in events:
        mins = mins_until(str(ev.get('time_et', '')))
        row = dict(ev)
        row['minutes_to_event'] = mins
        rows.append(row)
        if mins is not None and mins >= 0 and (next_minutes is None or mins < next_minutes):
            next_minutes, next_event = mins, ev.get('title', 'Macro Event')
    result = {'source': data.get('source', 'ForexFactory/manual'), 'events': rows, 'next_event': next_event or 'No scheduled event', 'minutes_to_event': next_minutes}
    cache_set('calendar', result, 300)
    return result


def get_live_earnings():
    c = cache_get('earnings')
    if c:
        return c
    today = now_ny().date().isoformat()
    week = (now_ny().date() + timedelta(days=7)).isoformat()
    data = fetch_finnhub_earnings(today, week)
    before_open, after_close, this_week = [], [], []
    for item in data[:50]:
        row = {'symbol': item.get('symbol', '-'), 'date': item.get('date', '-'), 'hour': item.get('hour', '-'), 'eps_estimate': item.get('epsEstimate'), 'eps_actual': item.get('epsActual')}
        this_week.append(row)
        hour = str(item.get('hour', '')).lower()
        if hour in {'bmo', 'before market open'}:
            before_open.append(row)
        elif hour in {'amc', 'after market close'}:
            after_close.append(row)
    result = {'before_open': before_open[:10], 'after_close': after_close[:10], 'this_week': this_week[:20]}
    cache_set('earnings', result, 600)
    return result


def get_live_news():
    c = cache_get('news')
    if c:
        return c
    data = fetch_finnhub_market_news()
    result = [{'headline': x.get('headline', '-'), 'source': x.get('source', '-'), 'summary': x.get('summary', ''), 'url': x.get('url', '')} for x in data[:8]]
    cache_set('news', result, 120)
    return result


def classify_move(points, pct, instrument):
    instrument = instrument.upper()
    if instrument == 'NQ':
        if points >= 350 or pct >= 1.50: return 'MAJOR'
        if points >= 220 or pct >= 1.00: return 'NOTABLE'
        if points >= 120 or pct >= 0.60: return 'ACTIVE'
        return 'ROUTINE'
    if instrument == 'ES':
        if points >= 55 or pct >= 1.00: return 'MAJOR'
        if points >= 35 or pct >= 0.65: return 'NOTABLE'
        if points >= 18 or pct >= 0.35: return 'ACTIVE'
        return 'ROUTINE'
    return 'ROUTINE'


def build_session_significance(risk=None):
    state = risk or load_risk_state()
    snap = state.get('market_snapshot', {})
    nq_points, es_points = safe_float(snap.get('NQ_SESSION_POINTS', 0)), safe_float(snap.get('ES_SESSION_POINTS', 0))
    nas_pct, spx_pct = safe_float(snap.get('NASDAQ', {}).get('pct', 0)), safe_float(snap.get('SPX', {}).get('pct', 0))
    nq_label, es_label = classify_move(nq_points, nas_pct, 'NQ'), classify_move(es_points, spx_pct, 'ES')
    summary = 'This session was routine.'
    if nq_label == 'MAJOR': summary = f'NQ pushed roughly {int(nq_points)} points in the NY session. That is major, not routine.'
    elif nq_label == 'NOTABLE': summary = f'NQ posted a meaningful session expansion of about {int(nq_points)} points.'
    elif nq_label == 'ACTIVE': summary = 'The session is active, but not extraordinary.'
    if es_label in {'MAJOR', 'NOTABLE'}: summary += ' ES participation confirms broad index support.'
    if state.get('donna_session') == 'NEW_YORK_CASH': summary += ' Because this happened in New York cash hours, the move matters more.'
    return {'label': f'{nq_label} NY Session', 'nq_points': round(nq_points,2), 'nq_pct': round(nas_pct,2), 'es_points': round(es_points,2), 'es_pct': round(spx_pct,2), 'summary': summary}


def build_market_driver_engine(risk=None):
    state = risk or load_risk_state()
    macro, headline, market = str(state.get('macro_risk','low')).lower(), str(state.get('headline_risk','low')).lower(), str(state.get('market_news_risk','low')).lower()
    text = (str(state.get('last_headline','')) + ' ' + str(state.get('last_market_headline',''))).lower()
    dominant_driver, secondary_driver, market_regime, market_threat, market_confidence, market_summary = 'Balanced Conditions', 'No clear secondary force', 'Neutral', state.get('next_event','None'), 'Low', 'No strong market driver currently detected.'
    sig = build_session_significance(state)
    if sig['nq_points'] >= 220:
        dominant_driver, market_regime, market_confidence, market_summary = 'Mega-Cap / Nasdaq Leadership', 'Trend Expansion', 'High', 'Leadership names are driving a meaningful Nasdaq session expansion.'
    if 'fed' in text or 'rates' in text or 'yield' in text:
        secondary_driver = 'Rates / Fed Sensitivity'
    elif 'oil' in text or 'energy' in text:
        secondary_driver = 'Energy Pressure'
    elif 'war' in text or 'iran' in text or 'geopolitical' in text:
        secondary_driver = 'Geopolitical Risk'
    if macro == 'high':
        dominant_driver, market_regime, market_confidence, market_summary = 'Macro Event Risk', 'Macro-Sensitive', 'High', 'Macro timing is dominating price behavior.'
    elif headline == 'high':
        dominant_driver, market_regime, market_confidence, market_summary = 'Headline Shock', 'Reactive Conditions', 'Medium-High', 'Breaking headlines are steering short-term market behavior.'
    elif market == 'high' and dominant_driver == 'Balanced Conditions':
        dominant_driver, market_regime, market_confidence, market_summary = 'Company Catalyst Pressure', 'Catalyst Driven', 'Medium', 'Company-specific catalysts are pushing market tone.'
    return {'dominant_driver': dominant_driver, 'secondary_driver': secondary_driver, 'market_regime': market_regime, 'market_threat': market_threat, 'market_confidence': market_confidence, 'market_summary': market_summary}


def build_morning_edge(risk=None):
    state = risk or load_risk_state()
    driver, sig = build_market_driver_engine(state), build_session_significance(state)
    nas_pct, spx_pct = safe_float(state.get('market_snapshot', {}).get('NASDAQ', {}).get('pct', 0)), safe_float(state.get('market_snapshot', {}).get('SPX', {}).get('pct', 0))
    today_bias = 'Risk-On' if nas_pct > 0 and spx_pct >= 0 else 'Mixed'
    if str(state.get('macro_risk','medium')).lower() == 'high': today_bias = 'High Event Risk'
    open_quality = 'Strong' if sig['label'].startswith('MAJOR') or sig['label'].startswith('NOTABLE') else 'Balanced'
    focus = 'Nasdaq Momentum' if nas_pct >= spx_pct else 'Broad Index Strength'
    main_threat = state.get('next_event', 'No major event')
    watch_first = ['NVDA', 'MSFT', 'AMZN', 'AMD'] if 'Nasdaq' in focus else ['SPY', 'QQQ', 'JPM', 'AAPL']
    first_read = 'Treat leadership strength as real until the market proves otherwise.'
    if str(state.get('event_phase','')).upper() in {'LIVE','IMMINENT','APPROACHING'}:
        first_read = 'Respect event timing. Do not confuse pre-event noise for true conviction.'
    return {'today_bias': today_bias, 'main_threat': main_threat, 'open_quality': open_quality, 'focus': focus, 'watch_first': watch_first, 'first_read': first_read, 'driver_note': driver['market_summary']}

def build_what_matters_now(risk=None):
    state = risk or load_risk_state()
    morning = build_morning_edge(state)
    driver = build_market_driver_engine(state)
    sig = build_session_significance(state)
    pulse = get_live_futures_macro_pulse()

    pulse_map = {row['symbol']: row for row in pulse}

    def pct(symbol):
        row = pulse_map.get(symbol, {})
        raw = str(row.get('pct', '')).replace('%', '').replace('+', '').strip()
        try:
            return float(raw)
        except Exception:
            return None

    nq_pct = pct('NQ')
    es_pct = pct('ES')
    oil_pct = pct('OIL')
    gold_pct = pct('GOLD')
    silver_pct = pct('SILVER')
    dxy_pct = pct('DXY')
    vix_pct = pct('VIX')
    us10y_pct = pct('US10Y')

    headline = 'Balanced conditions'
    summary = 'Donna does not yet see one dominant cross-asset force.'
    watch = ['NQ', 'ES', 'OIL', 'GOLD', 'SILVER']
    mode = 'balanced'
    risk_to_conviction = 'Normal'
    focus_reason = 'No single asset is overpowering the tape yet.'

    if str(state.get('macro_risk', '')).lower() == 'high' or (vix_pct is not None and vix_pct >= 4):
        headline = 'Macro risk is in control right now'
        summary = f"{state.get('next_event', 'Macro timing matters')} is the main threat. Respect reaction risk over conviction."
        watch = ['NQ', 'ES', 'DXY', 'US10Y', 'VIX']
        mode = 'macro_risk'
        risk_to_conviction = 'High'
        focus_reason = 'Event timing and volatility expansion matter more than clean trend continuation.'

    elif oil_pct is not None and abs(oil_pct) >= 2.0:
        direction = 'surging' if oil_pct > 0 else 'breaking lower'
        headline = f'Oil is {direction} and changing the tone'
        summary = 'Energy is making a real move. Watch for cross-asset pressure, inflation/risk sentiment shifts, and index reaction.'
        watch = ['OIL', 'ES', 'NQ', 'DXY', 'US10Y']
        mode = 'oil_shock'
        risk_to_conviction = 'Medium-High'
        focus_reason = 'Crude is the dominant mover and can reshape equity tone fast.'

    elif ((gold_pct is not None and abs(gold_pct) >= 1.0) or
          (silver_pct is not None and abs(silver_pct) >= 2.0)):
        headline = 'Metals are making a real move'
        summary = 'Gold and silver are active enough to matter for macro interpretation and defensive tone.'
        watch = ['GOLD', 'SILVER', 'DXY', 'US10Y', 'NQ']
        mode = 'metals'
        risk_to_conviction = 'Medium'
        focus_reason = 'Precious metals are signaling a macro/defensive shift worth respecting.'

    elif nq_pct is not None and nq_pct >= 0.75:
        headline = 'Nasdaq momentum is still leading'
        summary = sig['summary']
        watch = ['NQ', 'ES', 'NVDA', 'MSFT', 'AMD']
        mode = 'nq_momentum'
        risk_to_conviction = 'Medium'
        focus_reason = 'Nasdaq leadership is strong enough to stay front and center.'

    elif ((nq_pct is not None and nq_pct <= -0.75) or
          (es_pct is not None and es_pct <= -0.60)):
        headline = 'Risk-off pressure is leading this tape'
        summary = 'Index pressure is strong enough to matter. Watch whether this is just rotation or true stress.'
        watch = ['NQ', 'ES', 'VIX', 'DXY', 'US10Y']
        mode = 'risk_off'
        risk_to_conviction = 'High'
        focus_reason = 'Downside pressure plus defensive confirmation raises fragility.'

    elif ((dxy_pct is not None and abs(dxy_pct) >= 0.40) or
          (us10y_pct is not None and abs(us10y_pct) >= 1.00)):
        headline = 'Macro pressure is coming from dollar / rates'
        summary = 'DXY or yields are moving enough to affect equities and metals. Respect cross-asset pressure first.'
        watch = ['DXY', 'US10Y', 'NQ', 'ES', 'GOLD']
        mode = 'rates_fx'
        risk_to_conviction = 'Medium-High'
        focus_reason = 'Rates and dollar movement are strong enough to distort clean equity reads.'

    else:
        headline = f"{driver['dominant_driver']} is driving current conditions."
        summary = driver['market_summary']
        watch = ['NQ', 'ES', 'OIL', 'GOLD', 'SILVER']
        mode = 'balanced'
        risk_to_conviction = 'Normal'
        focus_reason = 'Donna sees a tradable environment, but not one overwhelming cross-asset driver.'

    return {
        'headline': headline,
        'summary': summary,
        'watch': watch,
        'mode': mode,
        'risk_to_conviction': risk_to_conviction,
        'focus_reason': focus_reason,
    }

def build_harvey_payload(risk=None):
    """
    HARVEY execution engine — builds the full payload for the HARVEY tab.
    Reads live state, pulse, session significance, and alert history.
    Returns everything the frontend needs to render the execution view.
    """
    state    = risk or load_risk_state()
    sig      = build_session_significance(state)
    driver   = build_market_driver_engine(state)
    morning  = build_morning_edge(state)
    wm       = build_what_matters_now(state)
    pulse    = get_live_futures_macro_pulse()
    alerts   = load_alert_history()

    pulse_map = {r['symbol']: r for r in pulse}

    def pct_float(sym):
        raw = str(pulse_map.get(sym, {}).get('pct', '')).replace('%','').replace('+','').strip()
        try: return float(raw)
        except: return None

    nq_pct  = pct_float('NQ')
    es_pct  = pct_float('ES')
    vix_pct = pct_float('VIX')
    nq_last = pulse_map.get('NQ', {}).get('last', '-')
    es_last = pulse_map.get('ES', {}).get('last', '-')

    # ── BIAS SCORE ──────────────────────────────────────────
    bias_score = 50
    bias_direction = 'NEUTRAL'

    sig_label = str(sig.get('label', '')).upper()
    nq_pts = safe_float(sig.get('nq_points', 0))
    if 'MAJOR' in sig_label:     bias_score += 20
    elif 'NOTABLE' in sig_label: bias_score += 12
    elif 'ACTIVE' in sig_label:  bias_score += 6

    if nq_pct is not None:
        if nq_pct >= 1.5:    bias_score += 18
        elif nq_pct >= 0.75: bias_score += 10
        elif nq_pct >= 0.3:  bias_score += 5
        elif nq_pct <= -1.5: bias_score -= 18
        elif nq_pct <= -0.75:bias_score -= 10
        elif nq_pct <= -0.3: bias_score -= 5

    if es_pct is not None:
        if es_pct >= 0.5:   bias_score += 6
        elif es_pct <= -0.5: bias_score -= 6

    macro = str(state.get('macro_risk', 'medium')).lower()
    if macro == 'high':     bias_score -= 15
    elif macro == 'medium': bias_score -= 5

    if vix_pct is not None and vix_pct >= 4: bias_score -= 12

    bias_score = max(0, min(100, bias_score))

    if bias_score >= 72:   bias_direction = 'LONG'
    elif bias_score >= 58: bias_direction = 'LEAN LONG'
    elif bias_score >= 42: bias_direction = 'NEUTRAL'
    elif bias_score >= 28: bias_direction = 'LEAN SHORT'
    else:                  bias_direction = 'SHORT'

    # ── ORB STATUS ──────────────────────────────────────────
    session = str(state.get('donna_session', '')).upper()
    now_ny_obj = now_ny()
    market_open_mins = (now_ny_obj.hour * 60 + now_ny_obj.minute) - (9 * 60 + 30)

    if session != 'NEW_YORK_CASH':
        orb_status  = 'PRE-MARKET'
        orb_note    = 'Cash session not open. ORB forms at 9:30 ET open.'
        orb_quality = 'PENDING'
    elif market_open_mins < 0:
        orb_status  = 'PRE-MARKET'
        orb_note    = 'Waiting for 9:30 ET open.'
        orb_quality = 'PENDING'
    elif market_open_mins <= 5:
        orb_status  = 'FORMING'
        orb_note    = f'ORB forming — {5 - market_open_mins} min remaining in opening range.'
        orb_quality = 'WAIT'
    elif market_open_mins <= 15:
        orb_status  = 'SET'
        orb_note    = 'ORB is set. Watch for breakout or breakdown confirmation.'
        orb_quality = 'WATCH'
    else:
        if nq_pct is not None and abs(nq_pct) >= 0.5:
            direction = 'BULLISH BREAK' if nq_pct > 0 else 'BEARISH BREAK'
            orb_status  = direction
            orb_note    = f'NQ has broken {"above" if nq_pct > 0 else "below"} the opening range. Look for continuation or failure.'
            orb_quality = 'ACTIVE'
        else:
            orb_status  = 'RANGING'
            orb_note    = 'NQ is ranging inside or near ORB bounds. Wait for a clean break.'
            orb_quality = 'WAIT'

    # ── VERDICT ─────────────────────────────────────────────
    event_phase = str(state.get('event_phase', '')).upper()
    if event_phase in ('LIVE', 'IMMINENT'):
        verdict = 'WAIT'
        next_ev = state.get('next_event', 'macro event')
        mins    = state.get('minutes_to_event')
        timing  = 'is live now' if (mins is not None and int(mins) <= 0) else f'in {mins} min' if mins is not None else 'is imminent'
        verdict_reason = f"{next_ev} {timing}. Do not trade into the release — wait for the initial reaction to resolve before reading direction."
        verdict_color  = 'yellow'
    elif macro == 'high' and bias_score < 60:
        verdict = 'WAIT'
        verdict_reason = 'Macro risk HIGH. Conviction is compressed. Let the market show its hand first.'
        verdict_color  = 'yellow'
    elif bias_score >= 68 and orb_quality in ('ACTIVE', 'WATCH') and macro != 'high':
        verdict = 'BUY'
        verdict_reason = f'Bias {bias_score}/100 LONG. {sig.get("summary","Session supports momentum.")} Confirm with leadership.'
        verdict_color  = 'green'
    elif bias_score <= 32 and orb_quality in ('ACTIVE', 'WATCH') and macro != 'high':
        verdict = 'SELL'
        verdict_reason = f'Bias {bias_score}/100 SHORT. Downside pressure confirmed. Respect breakdown until proven otherwise.'
        verdict_color  = 'red'
    elif orb_quality in ('FORMING', 'PENDING'):
        verdict = 'WAIT'
        verdict_reason = 'ORB not yet set. No clean entries until the opening range is established.'
        verdict_color  = 'yellow'
    elif orb_quality == 'WAIT' and orb_status == 'RANGING':
        verdict = 'WAIT'
        try:
            nq_lvl   = float(str(nq_last).replace(',', ''))
            break_up = f'{nq_lvl * 1.005:,.2f}'
            break_dn = f'{nq_lvl * 0.995:,.2f}'
            verdict_reason = (f'NQ is ranging near {nq_last} with no directional break. '
                              f'A sustained move above {break_up} opens the long; below {break_dn} confirms the short. '
                              f'Stay out until price commits.')
        except Exception:
            verdict_reason = f'NQ is ranging near {nq_last} inside the opening range. Wait for a clean directional break before entering.'
        verdict_color  = 'yellow'
    else:
        verdict = 'WAIT'
        needed  = 68 - bias_score
        verdict_reason = (f'Bias is {bias_score}/100 — {needed} points short of a BUY signal (threshold: 68). '
                          f'No dominant directional edge yet. Wait for momentum to build before committing size.')
        verdict_color  = 'yellow'

    # ── KEY LEVELS ──────────────────────────────────────────
    snap = state.get('market_snapshot', {})
    nq_data = snap.get('NQ', {})
    es_data = snap.get('ES', {})
    nq_price = safe_float(nq_data.get('last', 0))
    es_price = safe_float(es_data.get('last', 0))

    def fib_levels(price, pct_range=0.02):
        if not price: return {}
        swing = price * pct_range
        high  = price + swing
        low   = price - swing
        return {
            'high':     round(high, 2),
            'fib_786':  round(high - swing * 0.214, 2),
            'fib_618':  round(high - swing * 0.382, 2),
            'fib_500':  round(high - swing * 0.500, 2),
            'fib_382':  round(high - swing * 0.618, 2),
            'fib_236':  round(high - swing * 0.764, 2),
            'low':      round(low, 2),
        }

    nq_fibs = fib_levels(nq_price) if nq_price else {}
    es_fibs  = fib_levels(es_price) if es_price else {}

    # ── DIVERGENCE ──────────────────────────────────────────
    divergence = None
    if nq_pct is not None and es_pct is not None:
        diff = abs(nq_pct - es_pct)
        if diff >= 0.8:
            stronger = 'NQ' if nq_pct > es_pct else 'ES'
            weaker   = 'ES' if stronger == 'NQ' else 'NQ'
            divergence = {
                'active': True,
                'note': f'{stronger} significantly outperforming {weaker} ({diff:.2f}% spread). Watch for convergence or acceleration.',
                'spread': round(diff, 2),
            }

    session_context = {
        'session':       session,
        'time_ny':       state.get('donna_time_ny', ''),
        'day':           state.get('donna_day', ''),
        'next_event':    state.get('next_event', ''),
        'event_phase':   event_phase,
        'mins_to_event': state.get('minutes_to_event'),
    }

    return {
        'status':               'ok',
        'bias_score':           bias_score,
        'bias_direction':       bias_direction,
        'verdict':              verdict,
        'verdict_reason':       verdict_reason,
        'verdict_color':        verdict_color,
        'orb_status':           orb_status,
        'orb_note':             orb_note,
        'orb_quality':          orb_quality,
        'nq_fibs':              nq_fibs,
        'es_fibs':              es_fibs,
        'nq_last':              nq_last,
        'es_last':              es_last,
        'nq_pct':               nq_pct,
        'es_pct':               es_pct,
        'divergence':           divergence,
        'session_significance': sig,
        'morning_edge':         morning,
        'what_matters':         wm,
        'last_signals':         alerts[:10],
        'session_context':      session_context,
        'macro_risk':           state.get('macro_risk', 'medium'),
        'headline':             state.get('last_headline', ''),
    }


@app.get('/harvey-data')
async def harvey_data():
    return build_harvey_payload()


def build_market_movers_engine():
    return {
        'leaders': [
            {'ticker': 'NVDA', 'company': 'NVIDIA', 'impact': 'Very High', 'index_exposure': 'NQ / QQQ / SPX', 'catalyst': 'AI leadership', 'why_it_matters': 'Can drag the entire Nasdaq complex.'},
            {'ticker': 'MSFT', 'company': 'Microsoft', 'impact': 'Very High', 'index_exposure': 'NQ / SPX', 'catalyst': 'Cloud + AI', 'why_it_matters': 'Massive index weight and broad influence.'},
            {'ticker': 'AMZN', 'company': 'Amazon', 'impact': 'High', 'index_exposure': 'NQ / SPX', 'catalyst': 'Consumer + cloud', 'why_it_matters': 'Broad market sentiment and cloud read-through.'},
        ],
        'threats': [
            {'ticker': 'TSLA', 'company': 'Tesla', 'impact': 'High', 'index_exposure': 'NQ / QQQ', 'catalyst': 'High-beta sentiment', 'why_it_matters': 'Can distort Nasdaq mood and momentum fast.'},
            {'ticker': 'JPM', 'company': 'JPMorgan', 'impact': 'Medium', 'index_exposure': 'SPX / DJIA', 'catalyst': 'Financial tone', 'why_it_matters': 'Can confirm or deny broad risk appetite.'},
        ],
        'next_to_watch': [
            {'ticker': 'AMD', 'company': 'AMD', 'impact': 'High', 'index_exposure': 'NQ', 'catalyst': 'Semi sympathy', 'why_it_matters': 'Important read on semiconductor breadth.'},
            {'ticker': 'AAPL', 'company': 'Apple', 'impact': 'Very High', 'index_exposure': 'NQ / SPX', 'catalyst': 'Mega-cap weight', 'why_it_matters': 'Huge index footprint and sentiment influence.'},
        ],
    }


def normalize_payload(payload):
    return {'ticker': str(payload.get('ticker','UNKNOWN')), 'price': str(payload.get('price','0')), 'signal': str(payload.get('signal','NONE')).upper(), 'timeframe': str(payload.get('timeframe','unknown')), 'session': str(payload.get('session', session_label())), 'setup_type': str(payload.get('setup_type','unknown')), 'signal_priority': str(payload.get('signal_priority','unknown')), 'context_strength': str(payload.get('context_strength','moderate')), 'market_state': str(payload.get('market_state','neutral')), 'scenario': str(payload.get('scenario','none')), 'fib_zone': str(payload.get('fib_zone','none')), 'liquidity': str(payload.get('liquidity','unknown')), 'bias': str(payload.get('bias','neutral')), 'score': str(payload.get('score','0')), 'quality': str(payload.get('quality','B')).upper()}


def pre_verdict_engine(data):
    score, quality, context = safe_float(data['score']), data['quality'], data['context_strength'].lower()
    points = 0
    if score >= 80: points += 4
    elif score >= 70: points += 3
    elif score >= 60: points += 2
    elif score >= 50: points += 1
    else: points -= 2
    if quality == 'A': points += 3
    elif quality == 'B': points += 2
    elif quality == 'D': points -= 1
    if context == 'strong': points += 3
    elif context == 'moderate': points += 1
    else: points -= 1
    return 'TAKE' if points >= 8 else 'CAUTION' if points >= 4 else 'SKIP'


def should_send_trade_to_telegram(parsed):
    mode = (TELEGRAM_ALERT_MODE or 'critical').lower()
    if mode == 'off': return False
    if mode == 'all': return True
    verdict = str(parsed.get('verdict','')).upper()
    try: confidence = float(str(parsed.get('confidence','0')).replace('%','').strip())
    except Exception: confidence = 0.0
    return verdict == 'TAKE' or confidence >= 80


def add_alert_to_history(data, parsed):
    alerts = load_alert_history()
    alerts.insert(0, {'ticker': data['ticker'], 'signal': data['signal'], 'session': data['session'], 'timeframe': data['timeframe'], 'price': data['price'], 'verdict': parsed['verdict'], 'confidence': parsed['confidence'], 'summary': parsed['summary'], 'timestamp': utc_now_iso()})
    save_alert_history(alerts)


def process_signal(payload):
    data = normalize_payload(payload)
    if data['signal'] == 'NONE':
        return {'status': 'ignored', 'reason': 'signal NONE'}
    risk, sig = load_risk_state(), build_session_significance(load_risk_state())
    verdict = pre_verdict_engine(data)
    confidence, why, risk_text, execution, summary = '72%', 'Context and score are acceptable.', 'Standard caution.', 'Use leadership and event timing as the final filter.', 'Donna processed the alert.'
    if sig['label'].startswith('MAJOR'):
        summary = 'Major NY session expansion in play. Do not dismiss momentum conditions.'
        why = 'The broader session is significant, not routine.'
        confidence = '82%' if verdict == 'TAKE' else '74%'
        execution = 'Respect leadership. Do not fade strength blindly into a major expansion.'
    parsed = {'verdict': verdict, 'confidence': confidence, 'why': why, 'risk': risk_text, 'execution': execution, 'summary': summary}
    add_alert_to_history(data, parsed)
    if should_send_trade_to_telegram(parsed):
        send_telegram_message(f"DONNA // {data['ticker']} // {data['signal']}\n{data['session']} | TF {data['timeframe']} | Price {data['price']}\n\nVerdict: {parsed['verdict']}\nConfidence: {parsed['confidence']}\nWhy: {parsed['why']}\nExecution: {parsed['execution']}\nSummary: {parsed['summary']}")
    return {'status': 'ok', 'data': data, 'parsed': parsed}

ASSISTANT_SYSTEM_PROMPT = 'You are Donna, an elite market intelligence assistant. Return JSON only: {"action":"none|set_focus|add_task|add_reminder|clear_tasks|clear_reminders","value":"","reply":"short reply"}'


def summarize_system_context():
    risk, driver, morning, sig, movers, assistant = load_risk_state(), build_market_driver_engine(load_risk_state()), build_morning_edge(load_risk_state()), build_session_significance(load_risk_state()), build_market_movers_engine(), load_assistant_state()
    return f"Session: {risk.get('donna_session')}\nMacro Risk: {risk.get('macro_risk')}\nHeadline Risk: {risk.get('headline_risk')}\nMarket Risk: {risk.get('market_news_risk')}\nNext Event: {risk.get('next_event')}\nEvent Phase: {risk.get('event_phase')}\nDominant Driver: {driver.get('dominant_driver')}\nThreat: {driver.get('market_threat')}\nSession Significance: {sig.get('label')}\nSession Summary: {sig.get('summary')}\nMorning Bias: {morning.get('today_bias')}\nFocus: {morning.get('focus')}\nLikely Leaders: {[x['ticker'] for x in movers['leaders']]}\nLikely Threats: {[x['ticker'] for x in movers['threats']]}\nDaily Focus: {assistant.get('daily_focus')}"


def parse_json_loose(text, fallback):
    try: return json.loads(text)
    except Exception: pass
    try:
        m = re.search(r'\{.*\}', text, re.S)
        return json.loads(m.group(0)) if m else fallback
    except Exception:
        return fallback


def apply_assistant_action(action, value):
    state = load_assistant_state()
    action, value = str(action or 'none').strip().lower(), str(value or '').strip()
    if action == 'set_focus' and value: state['daily_focus'] = value
    elif action == 'add_task' and value:
        state['tasks'].append(value); state['tasks'] = state['tasks'][:20]
    elif action == 'add_reminder' and value:
        state['reminders'].append(value); state['reminders'] = state['reminders'][:20]
    elif action == 'clear_tasks': state['tasks'] = []
    elif action == 'clear_reminders': state['reminders'] = []
    save_assistant_state(state)
    return state
    
def build_donna_observations(risk=None):
    state = risk or load_risk_state()
    pulse = get_live_futures_macro_pulse()
    driver = build_market_driver_engine(state)
    morning = build_morning_edge(state)

    pulse_map = {row.get('symbol'): row for row in pulse}

    def pct(symbol):
        row = pulse_map.get(symbol, {})
        raw = str(row.get('pct', '')).replace('%', '').replace('+', '').strip()
        try:
            return float(raw)
        except Exception:
            return None

    observations = []

    nq_pct = pct('NQ')
    es_pct = pct('ES')
    oil_pct = pct('OIL')
    gold_pct = pct('GOLD')
    silver_pct = pct('SILVER')
    dxy_pct = pct('DXY')
    us10y_pct = pct('US10Y')
    vix_pct = pct('VIX')

    if oil_pct is not None and abs(oil_pct) >= 2.0:
        direction = 'surging' if oil_pct > 0 else 'breaking lower'
        observations.append({
            'type': 'observation',
            'title': f'OIL {direction}',
            'summary': 'Crude is moving enough to affect cross-asset tone. Watch index futures, dollar, and rates response.',
            'priority': 'high',
            'timestamp': utc_now_iso(),
        })

    if nq_pct is not None and nq_pct >= 0.75:
        observations.append({
            'type': 'observation',
            'title': 'Nasdaq strength remains meaningful',
            'summary': 'NQ is still showing enough upside pressure to matter. Respect leadership until it fails.',
            'priority': 'high',
            'timestamp': utc_now_iso(),
        })
    elif nq_pct is not None and nq_pct <= -0.75:
        observations.append({
            'type': 'observation',
            'title': 'Nasdaq pressure is real',
            'summary': 'NQ downside is strong enough to matter. Be careful forcing longs without confirmation.',
            'priority': 'high',
            'timestamp': utc_now_iso(),
        })

    if es_pct is not None and abs(es_pct) >= 0.60:
        direction = 'confirming upside participation' if es_pct > 0 else 'confirming downside pressure'
        observations.append({
            'type': 'observation',
            'title': f'ES is {direction}',
            'summary': 'Broad index participation is strong enough to validate the current tape.',
            'priority': 'medium',
            'timestamp': utc_now_iso(),
        })

    if gold_pct is not None and abs(gold_pct) >= 1.0:
        direction = 'strength' if gold_pct > 0 else 'weakness'
        observations.append({
            'type': 'observation',
            'title': f'Gold {direction} is notable',
            'summary': 'Metals are moving enough to matter for macro tone and cross-asset interpretation.',
            'priority': 'medium',
            'timestamp': utc_now_iso(),
        })

    if silver_pct is not None and abs(silver_pct) >= 2.0:
        direction = 'strength' if silver_pct > 0 else 'weakness'
        observations.append({
            'type': 'observation',
            'title': f'Silver {direction} is expanding',
            'summary': 'Silver volatility is elevated. Respect the move as more than background noise.',
            'priority': 'medium',
            'timestamp': utc_now_iso(),
        })

    if dxy_pct is not None and abs(dxy_pct) >= 0.40:
        direction = 'rising' if dxy_pct > 0 else 'falling'
        observations.append({
            'type': 'observation',
            'title': f'DXY is {direction}',
            'summary': 'Dollar movement is becoming important enough to influence equities and metals.',
            'priority': 'medium',
            'timestamp': utc_now_iso(),
        })

    if us10y_pct is not None and abs(us10y_pct) >= 1.0:
        direction = 'rising' if us10y_pct > 0 else 'falling'
        observations.append({
            'type': 'observation',
            'title': f'US10Y is {direction}',
            'summary': 'Rates are moving enough to affect risk appetite and valuation-sensitive assets.',
            'priority': 'medium',
            'timestamp': utc_now_iso(),
        })

    if vix_pct is not None and vix_pct >= 4.0:
        observations.append({
            'type': 'observation',
            'title': 'Volatility is expanding',
            'summary': 'VIX is pressing higher. Expect more fragile conviction and sharper reactions.',
            'priority': 'high',
            'timestamp': utc_now_iso(),
        })

    if str(state.get('event_phase', '')).upper() in {'LIVE', 'IMMINENT', 'APPROACHING'}:
        observations.append({
            'type': 'observation',
            'title': f"Macro timing matters: {state.get('next_event', 'Scheduled event')}",
            'summary': 'Event risk is close enough that price action may not be clean. Respect timing over impulse.',
            'priority': 'high',
            'timestamp': utc_now_iso(),
        })

    if not observations:
        observations.append({
            'type': 'observation',
            'title': driver.get('dominant_driver', 'Balanced conditions'),
            'summary': morning.get('first_read', 'Donna does not see a dominant threat beyond normal market rotation.'),
            'priority': 'low',
            'timestamp': utc_now_iso(),
        })

    return observations[:6]

def build_dashboard_payload():
    risk = load_risk_state()
    driver = build_market_driver_engine(risk)
    morning = build_morning_edge(risk)
    significance = build_session_significance(risk)
    what_matters = build_what_matters_now(risk)
    observations = build_donna_observations(risk)

    movers = build_market_movers_engine()
    alerts = load_alert_history()[:10]
    assistant = load_assistant_state()
    settings = load_settings()

    live_market = get_live_market_data()
    calendar = get_live_calendar()
    earnings = get_live_earnings()
    news = get_live_news()
    live_movers = get_live_movers()
    futures_macro_pulse = get_live_futures_macro_pulse()

    effective_alerts = alerts if alerts else observations

    live_strip = [
        {'label': 'Macro', 'value': str(risk.get('macro_risk', '-')).upper()},
        {'label': 'Headline', 'value': str(risk.get('headline_risk', '-')).upper()},
        {'label': 'Market', 'value': str(risk.get('market_news_risk', '-')).upper()},
        {'label': 'Driver', 'value': driver['dominant_driver']},
        {'label': 'Threat', 'value': morning['main_threat']},
        {'label': 'Open Quality', 'value': morning['open_quality']},
        {'label': 'Session', 'value': risk.get('donna_session', session_label())},
        {'label': 'Headline', 'value': risk.get('last_headline', '')},
    ]

    return {
        'status': 'online',
        'risk': risk,
        'driver': driver,
        'morning_edge': morning,
        'session_significance': significance,
        'what_matters_now': what_matters,
        'market_movers_engine': movers,
        'alerts': effective_alerts,
        'raw_trade_alerts': alerts,
        'observations': observations,
        'assistant': assistant,
        'settings': settings,
        'major_indexes': live_market['major_indexes'],
        'watchlist': live_market['watchlist'],
        'live_movers': live_movers,
        'futures_macro_pulse': futures_macro_pulse,
        'calendar': calendar,
        'earnings': earnings,
        'news': news,
        'live_strip': live_strip,
        'forex_factory_notes_url': FOREX_FACTORY_NOTES_URL,
    }
async def news_loop():
    while True:
        try: await asyncio.to_thread(process_news_guard_cycle)
        except Exception as e: print('Donna News loop error:', str(e))
        await asyncio.sleep(300)


async def headline_loop():
    while True:
        try: await asyncio.to_thread(process_headlines_cycle)
        except Exception as e: print('Headline loop error:', str(e))
        await asyncio.sleep(900)


async def finnhub_loop():
    while True:
        try: await asyncio.to_thread(process_finnhub_cycle)
        except Exception as e: print('Finnhub loop error:', str(e))
        await asyncio.sleep(300)


@app.on_event('startup')
async def startup():
    ensure_files()
    asyncio.create_task(news_loop())
    asyncio.create_task(headline_loop())
    asyncio.create_task(finnhub_loop())


@app.get('/')
async def root():
    return {'status': 'Donna is online', 'version': app.version}


@app.head('/')
async def root_head():
    return Response(status_code=200)


@app.get('/check-env')
async def check_env():
    return {'anthropic_key_found': bool(ANTHROPIC_API_KEY), 'telegram_found': bool(TELEGRAM_BOT_TOKEN), 'finnhub_found': bool(FINNHUB_API_KEY), 'fmp_found': bool(FMP_API_KEY), 'alpha_vantage_found': bool(ALPHA_VANTAGE_API_KEY), 'forex_factory_notes_url_set': bool(FOREX_FACTORY_NOTES_URL), 'risk_file_exists': RISK_STATE_FILE.exists(), 'alerts_file_exists': ALERTS_FILE.exists(), 'assistant_file_exists': ASSISTANT_FILE.exists(), 'settings_file_exists': SETTINGS_FILE.exists(), 'macro_events_file_exists': MACRO_EVENTS_FILE.exists(), 'telegram_alert_mode': TELEGRAM_ALERT_MODE, 'chat_model': ANTHROPIC_ASSISTANT_MODEL, 'fast_model': ANTHROPIC_MODEL}


@app.get('/dashboard-data')
async def dashboard_data():
    return build_dashboard_payload()

@app.get('/dashboard', response_class=HTMLResponse)
async def dashboard():
    return HTMLResponse(content=DASHBOARD_HTML)


@app.get('/market-data')
async def market_data():
    return get_live_market_data()


@app.get('/major-indexes')
async def major_indexes():
    return {'rows': get_live_major_indexes()}


@app.get('/movers')
async def movers():
    return get_live_movers()


@app.get('/calendar')
async def calendar():
    return get_live_calendar()


@app.get('/earnings')
async def earnings():
    return get_live_earnings()


@app.get('/system-health')
async def system_health():
    return {'status': 'ok', 'cache_keys': list(CACHE.keys()), 'finnhub_configured': bool(FINNHUB_API_KEY), 'fmp_configured': bool(FMP_API_KEY), 'alpha_vantage_configured': bool(ALPHA_VANTAGE_API_KEY), 'forex_factory_macro_layer': load_macro_events().get('source', 'unknown'), 'last_time_ny': now_ny().isoformat()}


@app.get('/alerts-data')
async def alerts_data():
    return {'alerts': load_alert_history()}


@app.get('/assistant-data')
async def assistant_data():
    return load_assistant_state()


@app.get('/test-telegram')
async def test_telegram():
    return send_telegram_message('DONNA TEST MESSAGE')


@app.post('/webhook')
async def webhook(request: Request):
    body = await request.body()
    text = body.decode('utf-8', errors='ignore').strip()
    if not text:
        raise HTTPException(status_code=400, detail='Empty body')
    try:
        payload = json.loads(text)
    except Exception:
        raise HTTPException(status_code=400, detail=f'Webhook body is not valid JSON. Received: {text[:200]}')
    result = process_signal(payload)
    if result.get('status') != 'ok':
        raise HTTPException(status_code=500, detail=result.get('error', 'Signal processing failed'))
    return result


@app.post('/assistant/set-focus')
async def assistant_set_focus(request: Request):
    body = await request.json()
    value = str(body.get('daily_focus', '')).strip()
    if not value:
        raise HTTPException(status_code=400, detail='daily_focus is required')
    state = load_assistant_state(); state['daily_focus'] = value; save_assistant_state(state)
    return {'status': 'ok', 'assistant': state}


@app.post('/assistant/add-task')
async def assistant_add_task(request: Request):
    body = await request.json()
    value = str(body.get('task', '')).strip()
    if not value:
        raise HTTPException(status_code=400, detail='task is required')
    state = load_assistant_state(); state['tasks'].append(value); state['tasks'] = state['tasks'][:20]; save_assistant_state(state)
    return {'status': 'ok', 'assistant': state}


@app.post('/assistant/delete-task')
async def assistant_delete_task(request: Request):
    body = await request.json()
    try: index = int(body.get('index'))
    except Exception: raise HTTPException(status_code=400, detail='index must be integer')
    state = load_assistant_state()
    if index < 0 or index >= len(state['tasks']): raise HTTPException(status_code=400, detail='invalid task index')
    state['tasks'].pop(index); save_assistant_state(state)
    return {'status': 'ok', 'assistant': state}


@app.post('/assistant/add-reminder')
async def assistant_add_reminder(request: Request):
    body = await request.json()
    value = str(body.get('reminder', '')).strip()
    if not value:
        raise HTTPException(status_code=400, detail='reminder is required')
    state = load_assistant_state(); state['reminders'].append(value); state['reminders'] = state['reminders'][:20]; save_assistant_state(state)
    return {'status': 'ok', 'assistant': state}


@app.post('/assistant/delete-reminder')
async def assistant_delete_reminder(request: Request):
    body = await request.json()
    try: index = int(body.get('index'))
    except Exception: raise HTTPException(status_code=400, detail='index must be integer')
    state = load_assistant_state()
    if index < 0 or index >= len(state['reminders']): raise HTTPException(status_code=400, detail='invalid reminder index')
    state['reminders'].pop(index); save_assistant_state(state)
    return {'status': 'ok', 'assistant': state}


@app.post('/assistant/clear-tasks')
async def assistant_clear_tasks():
    state = load_assistant_state(); state['tasks'] = []; save_assistant_state(state); return {'status': 'ok', 'assistant': state}


@app.post('/assistant/clear-reminders')
async def assistant_clear_reminders():
    state = load_assistant_state(); state['reminders'] = []; save_assistant_state(state); return {'status': 'ok', 'assistant': state}


@app.post('/assistant/chat')
async def assistant_chat(request: Request):
    body = await request.json()
    message = str(body.get('message', '')).strip()
    if not message:
        raise HTTPException(status_code=400, detail='message is required')
    fallback = {'action': 'none', 'value': '', 'reply': ''}
    if not client:
        risk, driver, morning, sig = load_risk_state(), build_market_driver_engine(load_risk_state()), build_morning_edge(load_risk_state()), build_session_significance(load_risk_state())
        msg_lower = message.lower()
        if 'what matters' in msg_lower or 'summary' in msg_lower: reply = f"{driver['dominant_driver']} is in control. {sig['summary']}"
        elif 'danger' in msg_lower or 'safe' in msg_lower: reply = f"Main threat: {morning['main_threat']}. Open quality: {morning['open_quality']}."
        elif 'mover' in msg_lower or 'company' in msg_lower: reply = 'Watch NVDA, MSFT, AMZN, AMD, and TSLA first. They have the most index influence right now.'
        elif 'significant' in msg_lower or 'real' in msg_lower: reply = sig['summary']
        else: reply = f"Donna fallback: Bias is {morning['today_bias']}. Focus is {morning['focus']}."
        return {'status': 'ok', 'action': 'none', 'value': '', 'reply': reply, 'assistant': load_assistant_state(), 'risk': load_risk_state(), 'alerts': load_alert_history()[:10]}
    try:
        response = client.messages.create(model=ANTHROPIC_ASSISTANT_MODEL, system=ASSISTANT_SYSTEM_PROMPT, messages=[{"role": "user", "content": f"User message:\n{message}\n\nSystem context:\n{summarize_system_context()}"}], max_tokens=220)
        parsed = parse_json_loose(response.content[0].text, fallback)
        action, value = str(parsed.get('action', 'none')).strip().lower(), str(parsed.get('value', '')).strip()
        reply = str(parsed.get('reply', '')).strip() or 'Donna processed the request.'
        updated_state = apply_assistant_action(action, value)
        return {'status': 'ok', 'action': action, 'value': value, 'reply': reply, 'assistant': updated_state, 'risk': load_risk_state(), 'alerts': load_alert_history()[:10]}
    except Exception as e:
        return {'status': 'error', 'action': 'none', 'value': '', 'reply': f'Assistant error: {str(e)}', 'assistant': load_assistant_state(), 'risk': load_risk_state(), 'alerts': load_alert_history()[:10]}


DASHBOARD_HTML = '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>D.O.N.N.A v5.0</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Rajdhani:wght@500;600;700&family=Inter:wght@400;500;600;700;900&display=swap" rel="stylesheet">
<style>
*{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:#060d1a;
  --bg2:#091220;
  --panel:#0e1c35;
  --panel2:#122040;
  --line:rgba(100,160,255,.10);
  --line2:rgba(100,160,255,.06);
  --text:#e8f2ff;
  --muted:#7a99c8;
  --muted2:#4d6a9a;
  --blue:#4d8fff;
  --blue2:#2563eb;
  --blue3:#1a3f80;
  --green:#00e5a0;
  --green2:rgba(0,229,160,.12);
  --yellow:#ffc93c;
  --red:#ff4d6d;
  --red2:rgba(255,77,109,.12);
  --gold:#f0b429;
  --shadow:0 24px 64px rgba(0,0,0,.45);
  --shadow2:0 8px 24px rgba(0,0,0,.3);
  --radius:18px;
  --radius2:12px;
}

html,body{min-height:100%;background:var(--bg)}
body{
  font-family:'Inter',sans-serif;
  color:var(--text);
  background:
    radial-gradient(ellipse at 0% 100%, rgba(0,229,160,.07) 0%, transparent 40%),
    radial-gradient(ellipse at 100% 0%, rgba(37,99,235,.12) 0%, transparent 35%),
    radial-gradient(ellipse at 50% 50%, rgba(14,28,53,.8) 0%, transparent 100%),
    var(--bg);
  padding:20px 24px 40px;
}
.wrap{max-width:1560px;margin:0 auto}

/* ── TOPBAR ── */
.topbar{
  display:flex;justify-content:space-between;align-items:center;
  gap:16px;flex-wrap:wrap;margin-bottom:16px;
}
.brand{display:flex;align-items:baseline;gap:16px}
.brand h1{
  font-family:'Rajdhani',sans-serif;
  font-size:42px;font-weight:700;letter-spacing:6px;
  background:linear-gradient(135deg,#fff 30%,var(--blue) 100%);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;
  line-height:1;
}
.brand-tag{
  font-family:'Space Mono',monospace;
  font-size:10px;color:var(--muted2);letter-spacing:1px;
  border:1px solid var(--line);padding:4px 8px;border-radius:6px;
}
.top-right{display:flex;gap:12px;align-items:center;flex-wrap:wrap}
.status-badge{
  display:flex;align-items:center;gap:8px;
  padding:8px 14px;border-radius:999px;
  background:rgba(0,229,160,.07);border:1px solid rgba(0,229,160,.2);
  font-family:'Space Mono',monospace;font-size:11px;color:#00e5a0;font-weight:700;
  letter-spacing:1px;
}
.dot{
  width:8px;height:8px;border-radius:50%;background:var(--green);
  box-shadow:0 0 10px rgba(0,229,160,.9);
  animation:pulse 2s ease-in-out infinite;
}
@keyframes pulse{0%,100%{opacity:1;transform:scale(1)}50%{opacity:.6;transform:scale(.85)}}
.nav{display:flex;gap:8px}
.tab-btn{
  font-family:'Rajdhani',sans-serif;font-size:15px;font-weight:700;letter-spacing:1px;
  border:1px solid var(--line);padding:9px 18px;border-radius:10px;
  background:rgba(255,255,255,.03);color:var(--muted);
  cursor:pointer;transition:all .2s ease;text-transform:uppercase;
}
.tab-btn:hover{color:var(--text);border-color:rgba(77,143,255,.3);background:rgba(77,143,255,.07)}
.tab-btn.active{
  background:linear-gradient(135deg,var(--blue),var(--blue2));
  border-color:transparent;color:#fff;
  box-shadow:0 4px 20px rgba(37,99,235,.4);
}

/* ── LIVE STRIP ── */
.live-strip-row{
  display:grid;grid-template-columns:160px 1fr 200px;gap:10px;
  align-items:center;margin-bottom:16px;
}
.live-label{
  font-family:'Space Mono',monospace;font-size:10px;letter-spacing:2px;
  color:var(--red);text-transform:uppercase;
  padding:12px 14px;border-radius:var(--radius2);
  background:rgba(255,77,109,.07);border:1px solid rgba(255,77,109,.18);
}
.ticker-wrap{
  overflow:hidden;border-radius:var(--radius2);
  background:var(--panel);border:1px solid var(--line2);
  height:42px;display:flex;align-items:center;position:relative;
}
.ticker-wrap::before,.ticker-wrap::after{
  content:'';position:absolute;top:0;bottom:0;width:40px;z-index:2;
}
.ticker-wrap::before{left:0;background:linear-gradient(to right,var(--panel),transparent)}
.ticker-wrap::after{right:0;background:linear-gradient(to left,var(--panel),transparent)}
.ticker-track{
  display:inline-flex;white-space:nowrap;padding-left:100%;
  animation:tickerMove 35s linear infinite;
}
@keyframes tickerMove{0%{transform:translateX(0)}100%{transform:translateX(-100%)}}
.ticker-item{
  padding-right:36px;font-family:'Space Mono',monospace;font-size:11px;
  color:var(--muted);
}
.ticker-item b{color:var(--text);font-weight:700}
.ticker-item .up{color:var(--green)}
.ticker-item .dn{color:var(--red)}
.session-chip{
  font-family:'Rajdhani',sans-serif;
  text-align:center;padding:10px 14px;border-radius:var(--radius2);
  background:var(--panel);border:1px solid var(--line);
}
.session-chip .lab{font-size:10px;letter-spacing:1.5px;color:var(--muted2);text-transform:uppercase}
.session-chip .val{font-size:20px;font-weight:700;margin-top:2px;letter-spacing:1px}

/* ── SHARED PANEL ── */
.panel,.card{
  background:linear-gradient(180deg,rgba(16,32,64,.98),rgba(10,22,48,.99));
  border:1px solid var(--line);border-radius:var(--radius);
  box-shadow:var(--shadow);padding:22px;
}
.panel-sm{padding:16px 18px}
.kicker{
  font-family:'Space Mono',monospace;font-size:10px;letter-spacing:2px;
  color:var(--muted2);text-transform:uppercase;margin-bottom:10px;
}
.section-title{
  font-family:'Rajdhani',sans-serif;font-size:22px;font-weight:700;
  letter-spacing:.5px;line-height:1.1;
}
.page{display:none}.page.active{display:block}
.vstack{display:grid;gap:16px}

/* ── TABLES ── */
table{width:100%;border-collapse:collapse}
th{
  font-family:'Space Mono',monospace;font-size:10px;letter-spacing:1.5px;
  color:var(--muted2);text-transform:uppercase;text-align:left;
  padding:0 0 10px;border-bottom:1px solid var(--line2);
}
td{
  padding:11px 0;border-bottom:1px solid var(--line2);
  font-size:14px;font-weight:600;
}
tr:last-child td{border-bottom:none}
.up{color:var(--green)}.dn{color:var(--red)}
.neutral{color:var(--muted)}

/* ── RISK BADGES ── */
.risk-badge{
  display:inline-block;padding:4px 10px;border-radius:6px;
  font-family:'Space Mono',monospace;font-size:11px;font-weight:700;
  letter-spacing:1px;text-transform:uppercase;
}
.risk-low{background:rgba(0,229,160,.12);color:var(--green);border:1px solid rgba(0,229,160,.25)}
.risk-medium{background:rgba(255,201,60,.10);color:var(--yellow);border:1px solid rgba(255,201,60,.25)}
.risk-high{background:rgba(255,77,109,.12);color:var(--red);border:1px solid rgba(255,77,109,.25)}

/* ── KV ROWS ── */
.kv-row{
  display:flex;justify-content:space-between;align-items:center;gap:12px;
  padding:11px 0;border-bottom:1px solid var(--line2);
}
.kv-row:last-child{border-bottom:none}
.kv-k{color:var(--muted);font-size:13px}
.kv-v{color:var(--text);font-size:13px;font-weight:600;text-align:right;max-width:60%}

/* ── OBSERVATION CARDS ── */
.obs-item{
  padding:13px 16px;border-radius:12px;margin-bottom:10px;
  border-left:3px solid var(--blue);
  background:rgba(77,143,255,.06);
}
.obs-item:last-child{margin-bottom:0}
.obs-item.high{border-left-color:var(--red);background:rgba(255,77,109,.06)}
.obs-item.medium{border-left-color:var(--yellow);background:rgba(255,201,60,.06)}
.obs-item.low{border-left-color:var(--muted2);background:rgba(255,255,255,.03)}
.obs-title{font-size:13px;font-weight:700;margin-bottom:4px}
.obs-body{font-size:12px;color:var(--muted);line-height:1.5}

/* ── HERO BANNER ── */
.hero-banner{
  padding:28px 30px;border-radius:20px;
  border:1px solid rgba(77,143,255,.2);
  background:
    radial-gradient(circle at top right, rgba(37,99,235,.15) 0%, transparent 50%),
    linear-gradient(180deg,rgba(16,32,64,.98),rgba(10,22,48,.99));
  box-shadow:var(--shadow);
}
.hero-eyebrow{
  font-family:'Space Mono',monospace;font-size:10px;letter-spacing:2.5px;
  color:var(--blue);text-transform:uppercase;margin-bottom:12px;
}
.hero-title{
  font-family:'Rajdhani',sans-serif;font-size:38px;font-weight:700;
  line-height:1.05;letter-spacing:.5px;
}
.hero-sub{
  margin-top:12px;font-size:14px;line-height:1.7;color:var(--muted);max-width:80ch;
}
.hero-grid{display:grid;grid-template-columns:1.3fr .7fr;gap:20px;align-items:start}
.chip-stack{display:grid;gap:10px}
.chip{
  border-radius:12px;padding:13px 15px;
  border:1px solid var(--line);background:rgba(255,255,255,.03);
}
.chip-label{
  display:block;font-family:'Space Mono',monospace;font-size:9px;
  letter-spacing:1.5px;color:var(--muted2);text-transform:uppercase;margin-bottom:6px;
}
.chip-value{
  display:block;font-family:'Rajdhani',sans-serif;font-size:19px;font-weight:700;letter-spacing:.3px;
}

/* ── STAT GRID ── */
.stat-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}
.stat-card{text-align:center;padding:18px 14px}
.stat-card .s-lab{
  font-family:'Space Mono',monospace;font-size:9px;letter-spacing:1.5px;
  color:var(--muted2);text-transform:uppercase;margin-bottom:10px;
}
.stat-card .s-val{
  font-family:'Rajdhani',sans-serif;font-size:26px;font-weight:700;letter-spacing:1px;
  line-height:1;
}
.stat-card .s-sub{margin-top:6px;font-size:11px;color:var(--muted2);line-height:1.4}

/* ── MAIN GRID ── */
.main-grid{display:grid;grid-template-columns:1.2fr .8fr;gap:16px;align-items:start}
.left-stack,.right-stack{display:grid;gap:16px}

/* ── NEWS ── */
.news-item{
  padding:14px 0;border-bottom:1px solid var(--line2);
}
.news-item:last-child{border-bottom:none}
.news-headline{font-size:14px;font-weight:600;line-height:1.45;color:var(--text)}
.news-meta{margin-top:5px;font-size:11px;color:var(--muted2)}
.news-summary{margin-top:6px;font-size:12px;color:var(--muted);line-height:1.5}
.news-link{color:var(--blue);font-size:11px;text-decoration:none}
.news-link:hover{text-decoration:underline}

/* ── ASSISTANT ── */
.chat-wrap{
  min-height:280px;max-height:480px;overflow-y:auto;
  border-radius:14px;background:rgba(0,0,0,.2);
  border:1px solid var(--line);padding:14px;margin-bottom:12px;
}
.msg{margin-bottom:10px;padding:12px 14px;border-radius:12px;line-height:1.55;font-size:13px}
.msg.user{background:rgba(77,143,255,.12);border:1px solid rgba(77,143,255,.2)}
.msg.assistant{background:rgba(255,255,255,.04);border:1px solid var(--line2)}
.msg .role{
  display:block;font-family:'Space Mono',monospace;font-size:9px;
  letter-spacing:1.5px;color:var(--muted2);text-transform:uppercase;margin-bottom:6px;
}
.chat-input-row{display:flex;gap:10px}
.chat-input{
  flex:1;padding:12px 14px;border-radius:12px;
  border:1px solid var(--line);background:rgba(255,255,255,.04);
  color:var(--text);font-family:'Inter',sans-serif;font-size:13px;
  outline:none;transition:border-color .2s;
}
.chat-input:focus{border-color:rgba(77,143,255,.4)}
.send-btn{
  padding:12px 20px;border-radius:12px;border:none;cursor:pointer;
  background:linear-gradient(135deg,var(--blue),var(--blue2));
  color:#fff;font-family:'Rajdhani',sans-serif;font-size:15px;font-weight:700;
  letter-spacing:1px;transition:all .2s;white-space:nowrap;
}
.send-btn:hover{transform:translateY(-1px);box-shadow:0 6px 20px rgba(37,99,235,.4)}
.send-btn:disabled{opacity:.5;cursor:not-allowed;transform:none}
.asst-state-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}
.state-list-item{
  display:flex;justify-content:space-between;align-items:center;
  padding:9px 0;border-bottom:1px solid var(--line2);font-size:13px;
}
.state-list-item:last-child{border-bottom:none}
.del-btn{
  background:none;border:none;color:var(--muted2);cursor:pointer;
  font-size:15px;padding:2px 6px;border-radius:6px;transition:all .15s;
}
.del-btn:hover{background:var(--red2);color:var(--red)}
.add-row{display:flex;gap:8px;margin-top:10px}
.add-input{
  flex:1;padding:9px 12px;border-radius:10px;
  border:1px solid var(--line);background:rgba(255,255,255,.04);
  color:var(--text);font-size:13px;outline:none;
}
.add-input:focus{border-color:rgba(77,143,255,.35)}
.add-btn{
  padding:9px 14px;border-radius:10px;border:1px solid rgba(77,143,255,.3);
  background:rgba(77,143,255,.1);color:var(--blue);
  cursor:pointer;font-size:13px;font-weight:600;transition:all .2s;
}
.add-btn:hover{background:rgba(77,143,255,.18)}

/* ── ALERT ITEMS ── */
.alert-item{
  padding:12px 14px;border-radius:12px;margin-bottom:10px;
  border:1px solid var(--line);background:rgba(255,255,255,.03);
}
.alert-item:last-child{margin-bottom:0}
.alert-header{display:flex;justify-content:space-between;align-items:center;gap:8px;margin-bottom:6px}
.alert-ticker{font-family:'Rajdhani',sans-serif;font-size:18px;font-weight:700;letter-spacing:1px}
.alert-signal{
  font-family:'Space Mono',monospace;font-size:10px;padding:3px 8px;border-radius:6px;
  background:rgba(77,143,255,.12);border:1px solid rgba(77,143,255,.22);color:var(--blue);
}
.alert-meta{font-size:11px;color:var(--muted2);margin-bottom:6px}
.alert-body{font-size:12px;color:var(--muted);line-height:1.5}
.verdict-TAKE{color:var(--green)}
.verdict-CAUTION{color:var(--yellow)}
.verdict-SKIP{color:var(--red)}

/* ── FOOTER ── */
.footer{
  margin-top:24px;display:flex;justify-content:space-between;
  gap:12px;flex-wrap:wrap;
  font-family:'Space Mono',monospace;font-size:10px;color:var(--muted2);
  letter-spacing:.5px;
}

/* ── SCROLLBAR ── */
::-webkit-scrollbar{width:6px;height:6px}
::-webkit-scrollbar-track{background:transparent}
::-webkit-scrollbar-thumb{background:rgba(77,143,255,.2);border-radius:4px}
::-webkit-scrollbar-thumb:hover{background:rgba(77,143,255,.35)}

/* ── RESPONSIVE ── */
@media(max-width:1200px){
  .hero-grid,.main-grid,.stat-grid{grid-template-columns:1fr 1fr}
  .stat-grid{grid-template-columns:repeat(2,1fr)}
}
@media(max-width:760px){
  body{padding:12px}
  .brand h1{font-size:32px}
  .hero-title{font-size:26px}
  .hero-grid,.main-grid,.stat-grid,.asst-state-grid,.live-strip-row{grid-template-columns:1fr}
}

/* ═══════════════════════════════════════
   H.A.R.V.E.Y EXECUTION TAB
   ═══════════════════════════════════════ */

.harvey-btn {
  background: linear-gradient(135deg, rgba(0,229,160,.15), rgba(0,229,160,.05)) !important;
  border-color: rgba(0,229,160,.3) !important;
  color: var(--green) !important;
}
.harvey-btn.active {
  background: linear-gradient(135deg, #047857, #065f46) !important;
  border-color: transparent !important;
  color: #fff !important;
  box-shadow: 0 4px 20px rgba(0,229,160,.35) !important;
}

.verdict-banner {
  border-radius: 18px;
  padding: 28px 30px;
  border: 1px solid var(--line);
  position: relative;
  overflow: hidden;
}
.verdict-banner::before {
  content: '';
  position: absolute;
  top: 0; left: 0; right: 0; bottom: 0;
  opacity: .06;
  border-radius: 18px;
}
.verdict-banner.green { border-color: rgba(0,229,160,.35); background: linear-gradient(135deg, rgba(4,120,87,.15), rgba(10,22,48,.99)); }
.verdict-banner.green::before { background: var(--green) }
.verdict-banner.red { border-color: rgba(255,77,109,.35); background: linear-gradient(135deg, rgba(153,27,27,.15), rgba(10,22,48,.99)); }
.verdict-banner.red::before { background: var(--red) }
.verdict-banner.yellow { border-color: rgba(255,201,60,.3); background: linear-gradient(135deg, rgba(180,83,9,.12), rgba(10,22,48,.99)); }
.verdict-banner.yellow::before { background: var(--yellow) }

.verdict-label { font-family: 'Space Mono', monospace; font-size: 11px; letter-spacing: 3px; text-transform: uppercase; margin-bottom: 12px; color: var(--muted2); }
.verdict-word { font-family: 'Rajdhani', sans-serif; font-size: 72px; font-weight: 700; line-height: 1; letter-spacing: 2px; }
.verdict-banner.green .verdict-word { color: var(--green) }
.verdict-banner.red   .verdict-word { color: var(--red) }
.verdict-banner.yellow .verdict-word { color: var(--yellow) }
.verdict-reason { margin-top: 14px; font-size: 14px; line-height: 1.65; color: var(--muted); max-width: 80ch; }
.verdict-grid { display: grid; grid-template-columns: 1.3fr .7fr; gap: 18px; align-items: start; }

.bias-wrap { display: flex; flex-direction: column; align-items: center; gap: 12px; }
.bias-gauge { width: 100%; height: 14px; background: rgba(255,255,255,.06); border-radius: 999px; overflow: hidden; border: 1px solid var(--line); }
.bias-fill { height: 100%; border-radius: 999px; transition: width .6s ease; }
.bias-score-big { font-family: 'Rajdhani', sans-serif; font-size: 52px; font-weight: 700; line-height: 1; }
.bias-direction { font-family: 'Space Mono', monospace; font-size: 13px; font-weight: 700; letter-spacing: 2px; }

.orb-card { border-radius: var(--radius); padding: 20px 22px; border: 1px solid var(--line); background: linear-gradient(180deg, rgba(16,32,64,.98), rgba(10,22,48,.99)); }
.orb-status-pill { display: inline-block; padding: 5px 14px; border-radius: 999px; font-family: 'Space Mono', monospace; font-size: 11px; font-weight: 700; letter-spacing: 1.5px; text-transform: uppercase; margin-bottom: 12px; }
.orb-FORMING    { background: rgba(255,201,60,.12); border: 1px solid rgba(255,201,60,.3); color: var(--yellow) }
.orb-SET        { background: rgba(77,143,255,.12);  border: 1px solid rgba(77,143,255,.3);  color: var(--blue) }
.orb-ACTIVE     { background: rgba(0,229,160,.12);   border: 1px solid rgba(0,229,160,.3);   color: var(--green) }
.orb-WATCH      { background: rgba(77,143,255,.12);  border: 1px solid rgba(77,143,255,.3);  color: var(--blue) }
.orb-WAIT       { background: rgba(255,255,255,.06); border: 1px solid var(--line);          color: var(--muted) }
.orb-PENDING    { background: rgba(255,255,255,.04); border: 1px solid var(--line2);         color: var(--muted2) }
.orb-PRE-MARKET { background: rgba(255,255,255,.04); border: 1px solid var(--line2);         color: var(--muted2) }
.orb-RANGING    { background: rgba(255,201,60,.08);  border: 1px solid rgba(255,201,60,.2);  color: var(--yellow) }

.orb-status-label { font-family: 'Rajdhani', sans-serif; font-size: 26px; font-weight: 700; margin-bottom: 8px; }
.orb-note { font-size: 13px; color: var(--muted); line-height: 1.6; }

.fib-table { width: 100%; border-collapse: collapse }
.fib-table td { padding: 8px 0; border-bottom: 1px solid var(--line2); font-size: 13px; font-weight: 600; }
.fib-table tr:last-child td { border-bottom: none }
.fib-label { font-family: 'Space Mono', monospace; font-size: 10px; color: var(--muted2); letter-spacing: 1px; }
.fib-price { text-align: right; color: var(--text) }
.fib-high  { color: var(--green) }
.fib-low   { color: var(--red) }

.signal-card { padding: 13px 16px; border-radius: 12px; border: 1px solid var(--line2); background: rgba(255,255,255,.03); margin-bottom: 8px; transition: background .15s; }
.signal-card:last-child { margin-bottom: 0 }
.signal-card:hover { background: rgba(255,255,255,.05) }
.signal-top { display: flex; justify-content: space-between; align-items: center; gap: 8px; margin-bottom: 6px; }
.signal-ticker { font-family: 'Rajdhani', sans-serif; font-size: 20px; font-weight: 700; letter-spacing: 1px; }
.signal-verdict { font-family: 'Space Mono', monospace; font-size: 10px; font-weight: 700; padding: 3px 8px; border-radius: 6px; letter-spacing: 1px; }
.sv-TAKE    { background: rgba(0,229,160,.15); color: var(--green); border: 1px solid rgba(0,229,160,.3) }
.sv-CAUTION { background: rgba(255,201,60,.12); color: var(--yellow); border: 1px solid rgba(255,201,60,.25) }
.sv-SKIP    { background: rgba(255,77,109,.12); color: var(--red); border: 1px solid rgba(255,77,109,.25) }
.signal-meta { font-size: 11px; color: var(--muted2); margin-bottom: 4px }
.signal-summary { font-size: 12px; color: var(--muted); line-height: 1.5 }

.divergence-alert { padding: 12px 16px; border-radius: 12px; background: rgba(255,201,60,.07); border: 1px solid rgba(255,201,60,.2); display: flex; align-items: flex-start; gap: 12px; }
.divergence-icon { font-size: 18px; flex-shrink: 0; margin-top: 2px; }
.divergence-text { font-size: 13px; color: var(--yellow); line-height: 1.5; }

.harvey-top-grid { display: grid; grid-template-columns: 1.3fr .7fr; gap: 16px; align-items: start; }
.harvey-mid-grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 16px; align-items: start; }
.harvey-bot-grid { display: grid; grid-template-columns: 1.6fr 1fr; gap: 16px; align-items: start; }

@media(max-width:1100px) {
  .harvey-top-grid, .harvey-mid-grid, .harvey-bot-grid, .verdict-grid { grid-template-columns: 1fr }
}
</style>
</head>
<body>
<div class="wrap">

  <!-- TOPBAR -->
  <div class="topbar">
    <div class="brand">
      <h1>D.O.N.N.A</h1>
      <span class="brand-tag">v5.0 // LIVE MARKET CORE</span>
    </div>
    <div class="top-right">
      <div class="nav">
        <button class="tab-btn active" data-page="dashboard">Dashboard</button>
        <button class="tab-btn" data-page="trading">Trading</button>
        <button class="tab-btn" data-page="news">News</button>
        <button class="tab-btn" data-page="assistant">Assistant</button>
        <button class="tab-btn harvey-btn" data-page="harvey">H.A.R.V.E.Y</button>
      </div>
      <div class="status-badge"><span class="dot"></span>ONLINE</div>
    </div>
  </div>

  <!-- LIVE STRIP -->
  <div class="live-strip-row">
    <div class="live-label">⬤ LIVE INTELLIGENCE</div>
    <div class="ticker-wrap">
      <div class="ticker-track" id="liveStrip">Loading...</div>
    </div>
    <div class="session-chip">
      <div class="lab">Current Session</div>
      <div class="val" id="sessionVal">—</div>
    </div>
  </div>

  <!-- ════════════════════ DASHBOARD ════════════════════ -->
  <div class="page active" id="page-dashboard">
    <div class="vstack">

      <!-- HERO -->
      <div class="hero-banner">
        <div class="hero-eyebrow">Command Overview</div>
        <div class="hero-grid">
          <div>
            <div class="hero-title" id="heroTitle">Loading market intelligence...</div>
            <div class="hero-sub" id="heroSub">Connecting to live data feeds.</div>
          </div>
          <div class="chip-stack">
            <div class="chip">
              <span class="chip-label">Dominant Driver</span>
              <span class="chip-value" id="driverDominant">—</span>
            </div>
            <div class="chip">
              <span class="chip-label">Main Threat</span>
              <span class="chip-value" id="mainThreat">—</span>
            </div>
            <div class="chip">
              <span class="chip-label">Open Quality</span>
              <span class="chip-value" id="openQuality">—</span>
            </div>
            <div class="chip">
              <span class="chip-label">Morning Bias</span>
              <span class="chip-value" id="morningBias">—</span>
            </div>
          </div>
        </div>
      </div>

      <!-- STAT GRID -->
      <div class="stat-grid">
        <div class="card stat-card">
          <div class="s-lab">Macro Risk</div>
          <div class="s-val" id="macroRisk">—</div>
          <div class="s-sub">Event timing &amp; macro pressure</div>
        </div>
        <div class="card stat-card">
          <div class="s-lab">Headline Risk</div>
          <div class="s-val" id="headlineRisk">—</div>
          <div class="s-sub">Breaking-news sensitivity</div>
        </div>
        <div class="card stat-card">
          <div class="s-lab">Market Risk</div>
          <div class="s-val" id="marketRisk">—</div>
          <div class="s-sub">Company &amp; sector catalyst pressure</div>
        </div>
        <div class="card stat-card">
          <div class="s-lab">Session Significance</div>
          <div class="s-val" id="sessionSig" style="font-size:18px;line-height:1.2">—</div>
          <div class="s-sub" id="sessionSigSub">—</div>
        </div>
      </div>

      <!-- MAIN GRID -->
      <div class="main-grid">

        <!-- LEFT -->
        <div class="left-stack">

          <!-- MARKET DRIVER ENGINE -->
          <div class="panel">
            <div class="kicker">Market Driver Engine</div>
            <div class="section-title" style="margin-bottom:14px">Regime + Context</div>
            <div class="kv-row"><span class="kv-k">Dominant Driver</span><span class="kv-v" id="driverDominant2">—</span></div>
            <div class="kv-row"><span class="kv-k">Secondary Driver</span><span class="kv-v" id="driverSecondary">—</span></div>
            <div class="kv-row"><span class="kv-k">Regime</span><span class="kv-v" id="driverRegime">—</span></div>
            <div class="kv-row"><span class="kv-k">Threat</span><span class="kv-v" id="driverThreat">—</span></div>
            <div class="kv-row"><span class="kv-k">Confidence</span><span class="kv-v" id="driverConfidence">—</span></div>
            <div style="margin-top:14px;font-size:13px;color:var(--muted);line-height:1.6" id="driverSummary">—</div>
          </div>

          <!-- MAJOR INDEXES -->
          <div class="panel">
            <div class="kicker">Market Board</div>
            <div class="section-title" style="margin-bottom:14px">Major Indexes</div>
            <table>
              <thead><tr><th>Index</th><th>Last</th><th>Chg</th><th>% Chg</th></tr></thead>
              <tbody id="majorIndexesTable"></tbody>
            </table>
          </div>

          <!-- MARKET MOVERS (Live) -->
          <div class="panel">
            <div class="kicker">Live Movers</div>
            <div class="section-title" style="margin-bottom:14px">Top Gainers &amp; Losers</div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px">
              <div>
                <div class="kicker" style="margin-bottom:8px;color:var(--green)">Gainers</div>
                <table>
                  <thead><tr><th>Sym</th><th>Last</th><th>%Chg</th></tr></thead>
                  <tbody id="gainersTable"></tbody>
                </table>
              </div>
              <div>
                <div class="kicker" style="margin-bottom:8px;color:var(--red)">Losers</div>
                <table>
                  <thead><tr><th>Sym</th><th>Last</th><th>%Chg</th></tr></thead>
                  <tbody id="losersTable"></tbody>
                </table>
              </div>
            </div>
          </div>

        </div>

        <!-- RIGHT -->
        <div class="right-stack">

          <!-- ACTIVE WARNINGS -->
          <div class="panel">
            <div class="kicker">Risk Board</div>
            <div class="section-title" style="margin-bottom:14px">Active Warnings</div>
            <div id="warningsList"></div>
            <div style="margin-top:14px;font-size:13px;color:var(--muted);line-height:1.6" id="morningRead">—</div>
            <div style="margin-top:10px;font-size:12px;color:var(--muted2);line-height:1.6" id="donnaTime">—</div>
          </div>

          <!-- DONNA OBSERVATIONS -->
          <div class="panel">
            <div class="kicker">Donna Feed</div>
            <div class="section-title" style="margin-bottom:14px">Live Observations</div>
            <div id="observationsList"></div>
          </div>

          <!-- TOP STORY -->
          <div class="panel">
            <div class="kicker">Primary Catalyst</div>
            <div style="font-size:24px;font-weight:700;font-family:Rajdhani,sans-serif;line-height:1.1;margin-bottom:10px" id="topStory">—</div>
            <div style="font-size:13px;color:var(--muted);line-height:1.6" id="topStoryNote">—</div>
          </div>

        </div>

      </div>
    </div>
  </div>

  <!-- ════════════════════ TRADING ════════════════════ -->
  <div class="page" id="page-trading">
    <div class="vstack">

      <!-- HERO -->
      <div class="hero-banner">
        <div class="hero-eyebrow">What Matters Right Now</div>
        <div class="hero-grid">
          <div>
            <div class="hero-title" id="tradingHeadline">—</div>
            <div class="hero-sub" id="tradingSummary">—</div>
            <div style="margin-top:14px;padding:12px 14px;border-radius:12px;font-size:13px;color:var(--muted);line-height:1.6;background:rgba(255,255,255,.03);border:1px solid var(--line2)" id="tradingFocusReason">—</div>
          </div>
          <div class="chip-stack">
            <div class="chip">
              <span class="chip-label">Donna Mode</span>
              <span class="chip-value" id="tradingMode">—</span>
            </div>
            <div class="chip">
              <span class="chip-label">Risk To Conviction</span>
              <span class="chip-value" id="tradingRtC">—</span>
            </div>
          </div>
        </div>
        <div style="margin-top:16px">
          <div class="kicker" style="margin-bottom:10px">Quick Focus</div>
          <div style="display:flex;gap:8px;flex-wrap:wrap" id="watchFirstRow"></div>
        </div>
      </div>

      <!-- MID GRID -->
      <div style="display:grid;grid-template-columns:1.1fr .9fr;gap:16px;align-items:start">

        <!-- FUTURES/MACRO PULSE -->
        <div class="panel">
          <div class="kicker">Live Pulse</div>
          <div class="section-title" style="margin-bottom:14px">Futures + Macro Pulse</div>
          <table>
            <thead><tr><th>Asset</th><th>Last</th><th>Chg</th><th>% Chg</th></tr></thead>
            <tbody id="tradingPulseTable"></tbody>
          </table>
        </div>

        <!-- TRADE INTELLIGENCE -->
        <div class="panel">
          <div class="kicker">Execution View</div>
          <div class="section-title" style="margin-bottom:14px">Trade Intelligence</div>
          <div class="kv-row"><span class="kv-k">Bias</span><span class="kv-v" id="tradeBias">—</span></div>
          <div class="kv-row"><span class="kv-k">Open Quality</span><span class="kv-v" id="tradeOpenQuality">—</span></div>
          <div class="kv-row"><span class="kv-k">Main Threat</span><span class="kv-v" id="tradeThreat">—</span></div>
          <div class="kv-row"><span class="kv-k">Focus</span><span class="kv-v" id="tradeFocus">—</span></div>
          <div style="margin-top:14px;font-size:13px;color:var(--muted);line-height:1.6" id="tradeNote">—</div>
        </div>

      </div>

      <!-- RECENT ALERTS -->
      <div class="panel">
        <div class="kicker">Alert History</div>
        <div class="section-title" style="margin-bottom:14px">Recent Alerts &amp; Observations</div>
        <div id="recentAlerts"></div>
      </div>

    </div>
  </div>

  <!-- ════════════════════ NEWS ════════════════════ -->
  <div class="page" id="page-news">
    <div class="vstack">

      <div class="hero-banner">
        <div class="hero-eyebrow">Macro Story</div>
        <div class="hero-title" id="newsMacroTitle">—</div>
        <div class="hero-sub" id="newsMacroNote">—</div>
      </div>

      <div class="panel">
        <div class="kicker">Market Catalyst</div>
        <div class="section-title" style="margin-bottom:6px" id="newsMarketTitle">—</div>
        <div style="font-size:13px;color:var(--muted);line-height:1.6" id="newsMarketNote">—</div>
      </div>

      <div class="panel">
        <div class="kicker">Latest Headlines</div>
        <div class="section-title" style="margin-bottom:14px">Live Market News</div>
        <div id="newsList"></div>
      </div>

      <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:14px">
        <div class="panel">
          <div class="kicker" style="color:var(--green)">Leaders</div>
          <table>
            <thead><tr><th>Ticker</th><th>Impact</th><th>Index</th></tr></thead>
            <tbody id="leadersTable"></tbody>
          </table>
        </div>
        <div class="panel">
          <div class="kicker" style="color:var(--red)">Threat Names</div>
          <table>
            <thead><tr><th>Ticker</th><th>Impact</th><th>Index</th></tr></thead>
            <tbody id="threatsTable"></tbody>
          </table>
        </div>
        <div class="panel">
          <div class="kicker" style="color:var(--yellow)">Next To Watch</div>
          <table>
            <thead><tr><th>Ticker</th><th>Impact</th><th>Index</th></tr></thead>
            <tbody id="nextWatchTable"></tbody>
          </table>
        </div>
      </div>

    </div>
  </div>

  <!-- ════════════════════ ASSISTANT ════════════════════ -->
  <div class="page" id="page-assistant">
    <div class="vstack">

      <!-- CHAT -->
      <div class="panel">
        <div class="kicker">Donna AI</div>
        <div class="section-title" style="margin-bottom:14px">Command Interface</div>
        <div class="chat-wrap" id="assistantOutput"></div>
        <div class="chat-input-row">
          <input class="chat-input" id="assistantInput" type="text" placeholder="Ask Donna anything about the market..." />
          <button class="send-btn" id="assistantSend">SEND</button>
        </div>
      </div>

      <!-- ASSISTANT STATE -->
      <div class="asst-state-grid">

        <!-- FOCUS + TASKS -->
        <div class="panel">
          <div class="kicker">Daily Agenda</div>
          <div class="section-title" style="margin-bottom:8px">Focus &amp; Tasks</div>
          <div style="padding:10px 12px;border-radius:10px;background:rgba(77,143,255,.07);border:1px solid rgba(77,143,255,.15);font-size:13px;color:var(--text);margin-bottom:14px" id="dailyFocus">—</div>
          <div id="tasksList"></div>
          <div class="add-row">
            <input class="add-input" id="taskInput" type="text" placeholder="Add a task..." />
            <button class="add-btn" id="addTaskBtn">+ Add</button>
          </div>
        </div>

        <!-- REMINDERS -->
        <div class="panel">
          <div class="kicker">Reminders</div>
          <div class="section-title" style="margin-bottom:14px">Active Reminders</div>
          <div id="remindersList"></div>
          <div class="add-row">
            <input class="add-input" id="reminderInput" type="text" placeholder="Add a reminder..." />
            <button class="add-btn" id="addReminderBtn">+ Add</button>
          </div>
        </div>

      </div>

    </div>
  </div>

  <!-- ════════════════════ H.A.R.V.E.Y ════════════════════ -->
  <div class="page" id="page-harvey">
    <div class="vstack">

      <!-- VERDICT BANNER -->
      <div class="verdict-banner yellow" id="harveyVerdict">
        <div class="verdict-grid">
          <div>
            <div class="verdict-label">H.A.R.V.E.Y // Execution Verdict</div>
            <div class="verdict-word" id="harveyVerdictWord">—</div>
            <div class="verdict-reason" id="harveyVerdictReason">Loading execution intelligence...</div>
          </div>
          <div class="bias-wrap" style="padding:10px 0">
            <div class="bias-score-big" id="harveyBiasScore">—</div>
            <div class="bias-direction" id="harveyBiasDir">—</div>
            <div style="width:100%;margin-top:8px">
              <div style="font-family:Space Mono,monospace;font-size:9px;letter-spacing:1.5px;color:var(--muted2);text-transform:uppercase;margin-bottom:6px;text-align:center">Bias Score / 100</div>
              <div class="bias-gauge"><div class="bias-fill" id="harveyBiasFill" style="width:50%"></div></div>
              <div style="display:flex;justify-content:space-between;margin-top:4px">
                <span style="font-family:Space Mono,monospace;font-size:9px;color:var(--red)">SHORT</span>
                <span style="font-family:Space Mono,monospace;font-size:9px;color:var(--muted2)">NEUTRAL</span>
                <span style="font-family:Space Mono,monospace;font-size:9px;color:var(--green)">LONG</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- ORB + SESSION ROW -->
      <div class="harvey-top-grid">
        <div class="orb-card">
          <div class="kicker">Opening Range</div>
          <div class="section-title" style="margin-bottom:14px">ORB Manager</div>
          <div class="orb-status-pill orb-PENDING" id="harveyOrbPill">PENDING</div>
          <div class="orb-status-label" id="harveyOrbStatus">—</div>
          <div class="orb-note" id="harveyOrbNote">—</div>
          <div style="margin-top:16px" id="harveyDivergence"></div>
        </div>
        <div class="panel">
          <div class="kicker">Session</div>
          <div class="section-title" style="margin-bottom:14px">Context</div>
          <div class="kv-row"><span class="kv-k">Session</span><span class="kv-v" id="harveySession">—</span></div>
          <div class="kv-row"><span class="kv-k">Day</span><span class="kv-v" id="harveyDay">—</span></div>
          <div class="kv-row"><span class="kv-k">Next Event</span><span class="kv-v" id="harveyNextEvent">—</span></div>
          <div class="kv-row"><span class="kv-k">Event Phase</span><span class="kv-v" id="harveyEventPhase">—</span></div>
          <div class="kv-row"><span class="kv-k">Macro Risk</span><span class="kv-v" id="harveyMacroRisk">—</span></div>
          <div class="kv-row"><span class="kv-k">Session Label</span><span class="kv-v" id="harveySessionLabel">—</span></div>
          <div class="kv-row"><span class="kv-k">NQ Points</span><span class="kv-v up" id="harveyNqPts">—</span></div>
          <div class="kv-row"><span class="kv-k">ES Points</span><span class="kv-v up" id="harveyEsPts">—</span></div>
        </div>
      </div>

      <!-- FIB LEVELS + PULSE -->
      <div class="harvey-mid-grid">
        <div class="panel">
          <div class="kicker" style="color:var(--green)">NQ Futures</div>
          <div class="section-title" style="margin-bottom:4px">Key Levels</div>
          <div style="font-family:Rajdhani,sans-serif;font-size:28px;font-weight:700;margin-bottom:14px" id="harveyNqLast">—</div>
          <table class="fib-table" id="harveyNqFibs"><tr><td colspan="2" class="neutral" style="font-size:12px">Loading...</td></tr></table>
        </div>
        <div class="panel">
          <div class="kicker" style="color:var(--blue)">ES Futures</div>
          <div class="section-title" style="margin-bottom:4px">Key Levels</div>
          <div style="font-family:Rajdhani,sans-serif;font-size:28px;font-weight:700;margin-bottom:14px" id="harveyEsLast">—</div>
          <table class="fib-table" id="harveyEsFibs"><tr><td colspan="2" class="neutral" style="font-size:12px">Loading...</td></tr></table>
        </div>
        <div class="panel">
          <div class="kicker">Execution View</div>
          <div class="section-title" style="margin-bottom:14px">Trade Intel</div>
          <div class="kv-row"><span class="kv-k">Bias</span><span class="kv-v" id="harveyMorningBias">—</span></div>
          <div class="kv-row"><span class="kv-k">Open Quality</span><span class="kv-v" id="harveyOpenQuality">—</span></div>
          <div class="kv-row"><span class="kv-k">Focus</span><span class="kv-v" id="harveyFocus">—</span></div>
          <div class="kv-row"><span class="kv-k">Watch First</span><span class="kv-v" id="harveyWatchFirst">—</span></div>
          <div style="margin-top:14px;padding:12px 14px;border-radius:10px;background:rgba(255,255,255,.03);border:1px solid var(--line2);font-size:13px;color:var(--muted);line-height:1.6" id="harveyFirstRead">—</div>
        </div>
      </div>

      <!-- SIGNAL HISTORY + WHAT MATTERS -->
      <div class="harvey-bot-grid">
        <div class="panel">
          <div class="kicker">TradingView Feed</div>
          <div class="section-title" style="margin-bottom:14px">Last 10 Signals</div>
          <div id="harveySignals">
            <div class="obs-item low"><div class="obs-body">No signals received yet. Connect your TradingView indicator to the webhook.</div></div>
          </div>
        </div>
        <div class="panel">
          <div class="kicker">Donna Intelligence</div>
          <div class="section-title" style="margin-bottom:14px">What Matters Now</div>
          <div style="font-size:15px;font-weight:600;line-height:1.5;margin-bottom:12px;color:var(--text)" id="harveyWmHeadline">—</div>
          <div style="font-size:13px;color:var(--muted);line-height:1.65;margin-bottom:14px" id="harveyWmSummary">—</div>
          <div class="kv-row"><span class="kv-k">Mode</span><span class="kv-v" id="harveyWmMode">—</span></div>
          <div class="kv-row"><span class="kv-k">Risk to Conviction</span><span class="kv-v" id="harveyWmRtc">—</span></div>
          <div style="margin-top:14px;padding:12px 14px;border-radius:10px;background:rgba(0,229,160,.05);border:1px solid rgba(0,229,160,.12);font-size:13px;color:var(--muted);line-height:1.6" id="harveyWmFocus">—</div>
        </div>
      </div>

    </div>
  </div>

  <!-- FOOTER -->
  <div class="footer">
    <span>D.O.N.N.A v5.0 // LIVE MARKET CORE</span>
    <span id="lastUpdated">Connecting...</span>
  </div>

</div>

<script>
// ════════ TAB NAVIGATION ════════
document.querySelectorAll('.tab-btn[data-page]').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab-btn[data-page]').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById('page-' + btn.dataset.page).classList.add('active');
  });
});

// ════════ HELPERS ════════
function setText(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val || '—';
}
function setHtml(id, val) {
  const el = document.getElementById(id);
  if (el) el.innerHTML = val || '';
}
function riskClass(level) {
  const l = (level || '').toLowerCase();
  if (l === 'high') return 'risk-high';
  if (l === 'medium') return 'risk-medium';
  return 'risk-low';
}
function riskBadge(level) {
  return `<span class="risk-badge ${riskClass(level)}">${(level||'—').toUpperCase()}</span>`;
}
function dirClass(pct) {
  const n = parseFloat(String(pct).replace('%',''));
  if (isNaN(n)) return '';
  return n >= 0 ? 'up' : 'dn';
}

// ════════ LIVE STRIP ════════
function buildStrip(items) {
  if (!items || !items.length) return '';
  return items.map(item => {
    const val = item.value || '—';
    return `<span class="ticker-item"><b>${item.label}:</b> ${val}</span>`;
  }).join('');
}

// ════════ RENDER DASHBOARD ════════
function renderDashboard(d) {
  const risk = d.risk || {};
  const driver = d.driver || {};
  const morning = d.morning_edge || {};
  const sig = d.session_significance || {};
  const wm = d.what_matters_now || {};
  const obs = d.observations || [];
  const alerts = d.raw_trade_alerts || [];
  const movers = d.market_movers_engine || {};
  const liveMovers = d.live_movers || {};
  const news = d.news || [];

  // Session / strip
  setText('sessionVal', risk.donna_session || '—');
  setHtml('liveStrip', buildStrip(d.live_strip || []));

  // Hero
  setText('heroTitle', wm.headline || driver.dominant_driver || '—');
  setText('heroSub', wm.summary || driver.market_summary || '—');
  setText('driverDominant', driver.dominant_driver || '—');
  setText('mainThreat', morning.main_threat || '—');
  setText('openQuality', morning.open_quality || '—');
  setText('morningBias', morning.today_bias || '—');

  // Stat cards
  setHtml('macroRisk', riskBadge(risk.macro_risk));
  setHtml('headlineRisk', riskBadge(risk.headline_risk));
  setHtml('marketRisk', riskBadge(risk.market_news_risk));
  setText('sessionSig', sig.label || '—');
  setText('sessionSigSub', sig.nq_points ? `NQ ${sig.nq_points}pts  ES ${sig.es_points}pts` : '—');

  // Driver engine
  setText('driverDominant2', driver.dominant_driver || '—');
  setText('driverSecondary', driver.secondary_driver || '—');
  setText('driverRegime', driver.market_regime || '—');
  setText('driverThreat', driver.market_threat || '—');
  setText('driverConfidence', driver.market_confidence || '—');
  setText('driverSummary', driver.market_summary || '—');

  // Major indexes
  const idx = d.major_indexes || [];
  setHtml('majorIndexesTable', idx.map(r => `
    <tr>
      <td>${r.symbol}</td>
      <td class="${dirClass(r.pct)}">${r.last}</td>
      <td class="${dirClass(r.pct)}">${r.chg}</td>
      <td class="${dirClass(r.pct)}">${r.pct}</td>
    </tr>`).join('') || '<tr><td colspan="4" class="neutral">No data</td></tr>');

  // Gainers / Losers
  const gainers = (liveMovers.gainers || []).slice(0, 5);
  const losers = (liveMovers.losers || []).slice(0, 5);
  setHtml('gainersTable', gainers.map(r => `
    <tr>
      <td class="up">${r.symbol}</td>
      <td>${r.last}</td>
      <td class="up">${r.pct}</td>
    </tr>`).join('') || '<tr><td colspan="3" class="neutral">—</td></tr>');
  setHtml('losersTable', losers.map(r => `
    <tr>
      <td class="dn">${r.symbol}</td>
      <td>${r.last}</td>
      <td class="dn">${r.pct}</td>
    </tr>`).join('') || '<tr><td colspan="3" class="neutral">—</td></tr>');

  // Warnings
  const warnings = risk.active_warnings || [];
  setHtml('warningsList', warnings.map(w => `
    <div class="obs-item medium">
      <div class="obs-title">${w}</div>
    </div>`).join('') || '<div class="obs-item low"><div class="obs-body">No active warnings.</div></div>');
  setText('morningRead', morning.first_read || '—');
  setText('donnaTime', `Updated: ${risk.donna_time_ny ? risk.donna_time_ny.substring(0,19).replace('T',' ') + ' ET' : '—'}`);

  // Observations
  setHtml('observationsList', obs.map(o => `
    <div class="obs-item ${o.priority || 'low'}">
      <div class="obs-title">${o.title || '—'}</div>
      <div class="obs-body">${o.summary || ''}</div>
    </div>`).join('') || '<div class="obs-item low"><div class="obs-body">No observations yet.</div></div>');

  // Top story
  setText('topStory', risk.last_headline || wm.headline || '—');
  setText('topStoryNote', risk.headline_guidance || wm.summary || '—');

  // Footer
  setText('lastUpdated', `Last sync: ${new Date().toLocaleTimeString('en-US', {hour12:true, hour:'2-digit', minute:'2-digit', second:'2-digit'})} ET`);
}

// ════════ RENDER TRADING ════════
function renderTrading(d) {
  const wm = d.what_matters_now || {};
  const morning = d.morning_edge || {};
  const pulse = d.futures_macro_pulse || [];
  const alerts = d.raw_trade_alerts || [];
  const obs = d.observations || [];

  setText('tradingHeadline', wm.headline || '—');
  setText('tradingSummary', wm.summary || '—');
  setText('tradingFocusReason', wm.focus_reason || '—');
  setText('tradingMode', (wm.mode || '—').replace(/_/g,' ').toUpperCase());
  setText('tradingRtC', wm.risk_to_conviction || '—');

  // Watch-first buttons
  const watchFirst = morning.watch_first || wm.watch || [];
  setHtml('watchFirstRow', watchFirst.map(sym => `
    <button class="tab-btn" style="font-size:13px;padding:8px 14px;letter-spacing:1px"
      onclick="this.classList.toggle('active')">${sym}</button>
  `).join(''));

  // Pulse table
  setHtml('tradingPulseTable', pulse.map(r => `
    <tr>
      <td style="font-family:Rajdhani,sans-serif;font-size:16px;font-weight:700">${r.symbol}</td>
      <td class="${dirClass(r.pct)}">${r.last}</td>
      <td class="${dirClass(r.pct)}">${r.chg}</td>
      <td class="${dirClass(r.pct)}">${r.pct}</td>
    </tr>`).join('') || '<tr><td colspan="4" class="neutral">No pulse data</td></tr>');

  // Trade intel
  setText('tradeBias', morning.today_bias || '—');
  setText('tradeOpenQuality', morning.open_quality || '—');
  setText('tradeThreat', morning.main_threat || '—');
  setText('tradeFocus', morning.focus || '—');
  setText('tradeNote', morning.first_read || '—');

  // Alerts + observations merged
  const combined = alerts.length ? alerts : obs;
  setHtml('recentAlerts', combined.slice(0, 8).map(item => {
    if (item.ticker) {
      // Trade alert
      const v = item.verdict || '';
      return `
        <div class="alert-item">
          <div class="alert-header">
            <span class="alert-ticker">${item.ticker}</span>
            <span class="alert-signal">${item.signal || ''}</span>
          </div>
          <div class="alert-meta">${item.session || ''} | ${item.timeframe || ''} | $${item.price || ''}</div>
          <div class="alert-body">
            Verdict: <span class="verdict-${v}">${v}</span> &nbsp;·&nbsp;
            Confidence: ${item.confidence || '—'} &nbsp;·&nbsp;
            ${item.summary || ''}
          </div>
        </div>`;
    } else {
      // Observation
      return `
        <div class="obs-item ${item.priority || 'low'}">
          <div class="obs-title">${item.title || '—'}</div>
          <div class="obs-body">${item.summary || ''}</div>
        </div>`;
    }
  }).join('') || '<div class="obs-item low"><div class="obs-body">No recent alerts.</div></div>');
}

// ═══════════════════════════════════════
// H.A.R.V.E.Y RENDERER
// ═══════════════════════════════════════

function renderHarvey(d) {
  const bias      = d.bias_score      || 50;
  const biasDir   = d.bias_direction  || 'NEUTRAL';
  const verdict   = d.verdict         || 'WAIT';
  const reason    = d.verdict_reason  || '—';
  const vcolor    = d.verdict_color   || 'yellow';
  const orb       = d.orb_status      || '—';
  const orbNote   = d.orb_note        || '—';
  const orbQ      = d.orb_quality     || 'PENDING';
  const sig       = d.session_significance || {};
  const morning   = d.morning_edge    || {};
  const wm        = d.what_matters    || {};
  const ctx       = d.session_context || {};
  const signals   = d.last_signals    || d.raw_trade_alerts || [];
  const div       = d.divergence      || null;
  const nqFibs    = d.nq_fibs         || {};
  const esFibs    = d.es_fibs         || {};

  const vb = document.getElementById('harveyVerdict');
  if (vb) vb.className = `verdict-banner ${vcolor}`;
  setText('harveyVerdictWord',   verdict);
  setText('harveyVerdictReason', reason);

  const biasColor = bias >= 60 ? 'var(--green)' : bias <= 40 ? 'var(--red)' : 'var(--yellow)';
  const bsEl = document.getElementById('harveyBiasScore');
  if (bsEl) { bsEl.textContent = bias; bsEl.style.color = biasColor; }
  const bdEl = document.getElementById('harveyBiasDir');
  if (bdEl) { bdEl.textContent = biasDir; bdEl.style.color = biasColor; }
  const bfEl = document.getElementById('harveyBiasFill');
  if (bfEl) {
    bfEl.style.width = bias + '%';
    bfEl.style.background = `linear-gradient(90deg, ${bias >= 60 ? 'var(--green)' : bias <= 40 ? 'var(--red)' : 'var(--yellow)'}, ${bias >= 60 ? '#00b37a' : bias <= 40 ? '#cc2244' : '#d97706'})`;
  }

  const pillEl = document.getElementById('harveyOrbPill');
  if (pillEl) { pillEl.className = `orb-status-pill orb-${orbQ}`; pillEl.textContent = orbQ; }
  setText('harveyOrbStatus', orb);
  setText('harveyOrbNote',   orbNote);

  const divEl = document.getElementById('harveyDivergence');
  if (divEl) {
    divEl.innerHTML = (div && div.active) ? `
      <div class="divergence-alert">
        <div class="divergence-icon">⚠</div>
        <div class="divergence-text"><strong>NQ/ES Divergence Detected</strong><br>${div.note}</div>
      </div>` : '';
  }

  setText('harveySession',    ctx.session    || d.donna_session || '—');
  setText('harveyDay',        ctx.day        || '—');
  setText('harveyNextEvent',  ctx.next_event || '—');
  setText('harveyEventPhase', ctx.event_phase|| '—');
  setHtml('harveyMacroRisk',  riskBadge(d.macro_risk));
  setText('harveySessionLabel', sig.label    || '—');
  setText('harveyNqPts', sig.nq_points ? sig.nq_points + ' pts (' + (sig.nq_pct||0) + '%)' : '—');
  setText('harveyEsPts', sig.es_points ? sig.es_points + ' pts (' + (sig.es_pct||0) + '%)' : '—');

  function fibRows(fibs, highClass, lowClass) {
    if (!fibs || !fibs.high) return '<tr><td colspan="2" class="neutral" style="font-size:12px">No price data</td></tr>';
    return [
      ['HIGH',  fibs.high,    highClass],
      ['78.6%', fibs.fib_786, ''],
      ['61.8%', fibs.fib_618, ''],
      ['50.0%', fibs.fib_500, ''],
      ['38.2%', fibs.fib_382, ''],
      ['23.6%', fibs.fib_236, ''],
      ['LOW',   fibs.low,     lowClass],
    ].map(([label, price, cls]) => `
      <tr>
        <td class="fib-label">${label}</td>
        <td class="fib-price ${cls}">${price ? price.toLocaleString('en-US',{minimumFractionDigits:2}) : '—'}</td>
      </tr>`).join('');
  }

  const nqDir = (d.nq_pct || 0) >= 0 ? 'up' : 'dn';
  const esDir = (d.es_pct || 0) >= 0 ? 'up' : 'dn';
  const nqEl = document.getElementById('harveyNqLast');
  if (nqEl) { nqEl.textContent = d.nq_last || '—'; nqEl.className = nqDir; }
  const esEl = document.getElementById('harveyEsLast');
  if (esEl) { esEl.textContent = d.es_last || '—'; esEl.className = esDir; }
  setHtml('harveyNqFibs', fibRows(nqFibs, 'fib-high', 'fib-low'));
  setHtml('harveyEsFibs', fibRows(esFibs, 'fib-high', 'fib-low'));

  setText('harveyMorningBias',  morning.today_bias   || '—');
  setText('harveyOpenQuality',  morning.open_quality || '—');
  setText('harveyFocus',        morning.focus        || '—');
  setText('harveyWatchFirst',   (morning.watch_first || []).slice(0,4).join('  ·  ') || '—');
  setText('harveyFirstRead',    morning.first_read   || '—');

  setText('harveyWmHeadline', wm.headline    || '—');
  setText('harveyWmSummary',  wm.summary     || '—');
  setText('harveyWmMode',     (wm.mode||'—').replace(/_/g,' ').toUpperCase());
  setText('harveyWmRtc',      wm.risk_to_conviction || '—');
  setText('harveyWmFocus',    wm.focus_reason || '—');

  const sigEl = document.getElementById('harveySignals');
  if (sigEl) {
    if (signals && signals.length) {
      sigEl.innerHTML = signals.slice(0,10).map(s => `
        <div class="signal-card">
          <div class="signal-top">
            <span class="signal-ticker">${s.ticker || '—'}</span>
            <div style="display:flex;gap:8px;align-items:center">
              <span style="font-family:Space Mono,monospace;font-size:10px;color:var(--muted2)">${s.timeframe||''}</span>
              <span class="signal-verdict sv-${s.verdict||'SKIP'}">${s.verdict||'—'}</span>
            </div>
          </div>
          <div class="signal-meta">${s.signal||''} · ${s.session||''} · $${s.price||'—'} · Confidence: ${s.confidence||'—'}</div>
          <div class="signal-summary">${s.summary||''}</div>
        </div>`).join('');
    } else {
      sigEl.innerHTML = '<div class="obs-item low"><div class="obs-body">No signals yet. Waiting for TradingView webhook.</div></div>';
    }
  }
}

async function refreshHarvey() {
  try {
    const res = await fetch('/harvey-data');
    if (!res.ok) return;
    const d = await res.json();
    renderHarvey(d);
  } catch(e) {
    console.error('HARVEY refresh error:', e);
  }
}

// ════════ RENDER NEWS ════════
function renderNews(d) {
  const risk = d.risk || {};
  const movers = d.market_movers_engine || {};
  const news = d.news || [];

  setText('newsMacroTitle', risk.last_headline || '—');
  setText('newsMacroNote', risk.headline_guidance || '—');
  setText('newsMarketTitle', risk.last_market_headline || '—');
  setText('newsMarketNote', risk.last_market_guidance || '—');

  setHtml('newsList', news.map(n => `
    <div class="news-item">
      <div class="news-headline">${n.headline || '—'}</div>
      <div class="news-meta">${n.source || '—'}</div>
      ${n.summary ? `<div class="news-summary">${n.summary}</div>` : ''}
      ${n.url ? `<a class="news-link" href="${n.url}" target="_blank" rel="noopener">Read more →</a>` : ''}
    </div>`).join('') || '<div class="obs-item low"><div class="obs-body">No live news loaded yet.</div></div>');

  const leaders = movers.leaders || [];
  const threats = movers.threats || [];
  const nextWatch = movers.next_to_watch || [];

  const moverRow = (m) => `
    <tr>
      <td style="font-family:Rajdhani,sans-serif;font-size:16px;font-weight:700">${m.ticker}</td>
      <td><span class="risk-badge" style="background:rgba(77,143,255,.1);border-color:rgba(77,143,255,.2);color:var(--blue)">${m.impact}</span></td>
      <td style="font-size:11px;color:var(--muted2)">${m.index_exposure || '—'}</td>
    </tr>`;

  setHtml('leadersTable', leaders.map(moverRow).join('') || '<tr><td colspan="3" class="neutral">—</td></tr>');
  setHtml('threatsTable', threats.map(moverRow).join('') || '<tr><td colspan="3" class="neutral">—</td></tr>');
  setHtml('nextWatchTable', nextWatch.map(moverRow).join('') || '<tr><td colspan="3" class="neutral">—</td></tr>');
}

// ════════ RENDER ASSISTANT STATE ════════
function renderAssistantState(asst) {
  if (!asst) return;
  setText('dailyFocus', asst.daily_focus || '—');

  const tasks = asst.tasks || [];
  setHtml('tasksList', tasks.map((t, i) => `
    <div class="state-list-item">
      <span style="font-size:13px">${t}</span>
      <button class="del-btn" onclick="deleteTask(${i})" title="Remove">✕</button>
    </div>`).join('') || '<div style="color:var(--muted2);font-size:13px;padding:8px 0">No tasks.</div>');

  const reminders = asst.reminders || [];
  setHtml('remindersList', reminders.map((r, i) => `
    <div class="state-list-item">
      <span style="font-size:13px">${r}</span>
      <button class="del-btn" onclick="deleteReminder(${i})" title="Remove">✕</button>
    </div>`).join('') || '<div style="color:var(--muted2);font-size:13px;padding:8px 0">No reminders.</div>');
}

// ════════ MAIN REFRESH ════════
async function refresh() {
  try {
    const res = await fetch('/dashboard-data');
    if (!res.ok) throw new Error('HTTP ' + res.status);
    const d = await res.json();

    renderDashboard(d);
    renderTrading(d);
    renderNews(d);
    renderAssistantState(d.assistant);
    renderHarvey(d);
    refreshHarvey();

  } catch (err) {
    console.error('Donna refresh error:', err);
    setText('lastUpdated', 'Sync error — retrying...');
  }
}

// ════════ ASSISTANT CHAT ════════
const chatOutput = document.getElementById('assistantOutput');
const chatInput = document.getElementById('assistantInput');
const sendBtn = document.getElementById('assistantSend');

function appendMsg(role, text) {
  const el = document.createElement('div');
  el.className = 'msg ' + role;
  el.innerHTML = `<span class="role">${role === 'user' ? 'You' : 'Donna'}</span>${text}`;
  chatOutput.appendChild(el);
  chatOutput.scrollTop = chatOutput.scrollHeight;
}

async function sendChat() {
  const msg = chatInput.value.trim();
  if (!msg) return;
  chatInput.value = '';
  sendBtn.disabled = true;
  appendMsg('user', msg);
  try {
    const res = await fetch('/assistant/chat', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({message: msg})
    });
    const data = await res.json();
    appendMsg('assistant', data.reply || 'No response.');
    if (data.assistant) renderAssistantState(data.assistant);
  } catch (err) {
    appendMsg('assistant', 'Connection error. Please try again.');
  }
  sendBtn.disabled = false;
  chatInput.focus();
}

sendBtn.addEventListener('click', sendChat);
chatInput.addEventListener('keydown', e => { if (e.key === 'Enter') sendChat(); });

// ════════ TASK / REMINDER ACTIONS ════════
async function deleteTask(index) {
  try {
    const res = await fetch('/assistant/delete-task', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({index})
    });
    const data = await res.json();
    if (data.assistant) renderAssistantState(data.assistant);
  } catch(e) { console.error(e); }
}

async function deleteReminder(index) {
  try {
    const res = await fetch('/assistant/delete-reminder', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({index})
    });
    const data = await res.json();
    if (data.assistant) renderAssistantState(data.assistant);
  } catch(e) { console.error(e); }
}

document.getElementById('addTaskBtn').addEventListener('click', async () => {
  const val = document.getElementById('taskInput').value.trim();
  if (!val) return;
  document.getElementById('taskInput').value = '';
  try {
    const res = await fetch('/assistant/add-task', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({task: val})
    });
    const data = await res.json();
    if (data.assistant) renderAssistantState(data.assistant);
  } catch(e) { console.error(e); }
});

document.getElementById('addReminderBtn').addEventListener('click', async () => {
  const val = document.getElementById('reminderInput').value.trim();
  if (!val) return;
  document.getElementById('reminderInput').value = '';
  try {
    const res = await fetch('/assistant/add-reminder', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({reminder: val})
    });
    const data = await res.json();
    if (data.assistant) renderAssistantState(data.assistant);
  } catch(e) { console.error(e); }
});

document.getElementById('taskInput').addEventListener('keydown', e => {
  if (e.key === 'Enter') document.getElementById('addTaskBtn').click();
});
document.getElementById('reminderInput').addEventListener('keydown', e => {
  if (e.key === 'Enter') document.getElementById('addReminderBtn').click();
});

// ════════ BOOT ════════
refresh();
setInterval(refresh, 15000);
</script>
</body>
</html>'''
