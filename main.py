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
    from openai import OpenAI
except Exception:
    OpenAI = None

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

OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '').strip()
OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'gpt-4.1-mini').strip()
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '').strip()
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '').strip()
TELEGRAM_ALERT_MODE = os.getenv('TELEGRAM_ALERT_MODE', 'critical').strip().lower()
FINNHUB_API_KEY = os.getenv('FINNHUB_API_KEY', '').strip()
FMP_API_KEY = os.getenv('FMP_API_KEY', '').strip()
ALPHA_VANTAGE_API_KEY = os.getenv('ALPHA_VANTAGE_API_KEY', '').strip()
FOREX_FACTORY_NOTES_URL = os.getenv('FOREX_FACTORY_NOTES_URL', '').strip()

client = OpenAI(api_key=OPENAI_API_KEY) if (OpenAI and OPENAI_API_KEY) else None
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
        'NQ_SESSION_POINTS': 393.0,
        'ES_SESSION_POINTS': 49.5,
    },
}
DEFAULT_ASSISTANT_STATE = {
    'daily_focus': 'Trade what matters. Ignore noise.',
    'tasks': ['Review morning edge', 'Check likely market movers', 'Respect macro timing'],
    'reminders': ['Do not force trades into event windows', 'Leadership names deserve first attention'],
}
DEFAULT_SETTINGS = {'theme_mode': 'premium_dark', 'layout_density': 'balanced', 'telegram_alert_mode': TELEGRAM_ALERT_MODE or 'critical'}
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
    mapping = [('NASDAQ', 'QQQ', 'QQQ'), ('S&P 500', 'SPY', 'SPY'), ('DJIA', 'DIA', 'DIA'), ('VIX', '^VIX', None), ('US 10Y', '^TNX', None), ('DXY', 'DX-Y.NYB', None)]
    fallback = load_risk_state().get('market_snapshot', {})
    fallback_map = {'NASDAQ': fallback.get('NASDAQ', {}), 'S&P 500': fallback.get('SPX', {}), 'DJIA': fallback.get('DJIA', {}), 'VIX': fallback.get('VIX', {}), 'US 10Y': fallback.get('US10Y', {}), 'DXY': fallback.get('DXY', {})}
    rows = []
    for label, primary, alt in mapping:
        q = get_quote_with_fallback(primary, alt) or fallback_map.get(label, {})
        pct = safe_float(q.get('pct', 0))
        rows.append({'symbol': label, 'last': q.get('last', '-'), 'chg': q.get('chg', '-'), 'pct': f'{pct:+.2f}%', 'dir': 'up' if pct >= 0 else 'down'})
    cache_set('major_indexes', rows, 20)
    return rows

def get_live_futures_macro_pulse():
    c = cache_get('futures_macro_pulse')
    if c:
        return c

    # label, primary_symbol, alt_symbol, fallback_key
    mapping = [
        ('NQ', 'NQ=F', None, None),
        ('ES', 'ES=F', None, None),
        ('OIL', 'CL=F', None, None),
        ('GOLD', 'GC=F', None, None),
        ('SILVER', 'SI=F', None, None),
        ('DXY', 'DX-Y.NYB', None, 'DXY'),
        ('US10Y', '^TNX', None, 'US10Y'),
        ('VIX', '^VIX', None, 'VIX'),
    ]

    fallback = load_risk_state().get('market_snapshot', {})
    rows = []

    for label, primary, alt, fallback_key in mapping:
        q = get_quote_with_fallback(primary, alt)

        if not q and fallback_key:
            q = fallback.get(fallback_key, {})

        pct = safe_float((q or {}).get('pct', 0))
        rows.append({
            'symbol': label,
            'last': (q or {}).get('last', '-'),
            'chg': (q or {}).get('chg', '-'),
            'pct': f'{pct:+.2f}%',
            'dir': 'up' if pct >= 0 else 'down'
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


def build_dashboard_payload():
    risk = load_risk_state()
    driver = build_market_driver_engine(risk)
    morning = build_morning_edge(risk)
    significance = build_session_significance(risk)

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
        'market_movers_engine': movers,
        'alerts': alerts,
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
        'forex_factory_notes_url': FOREX_FACTORY_NOTES_URL
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
        await asyncio.sleep(300)


async def finnhub_loop():
    while True:
        try: await asyncio.to_thread(process_finnhub_cycle)
        except Exception as e: print('Finnhub loop error:', str(e))
        await asyncio.sleep(180)


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
    return {'openai_key_found': bool(OPENAI_API_KEY), 'telegram_found': bool(TELEGRAM_BOT_TOKEN), 'finnhub_found': bool(FINNHUB_API_KEY), 'fmp_found': bool(FMP_API_KEY), 'alpha_vantage_found': bool(ALPHA_VANTAGE_API_KEY), 'forex_factory_notes_url_set': bool(FOREX_FACTORY_NOTES_URL), 'risk_file_exists': RISK_STATE_FILE.exists(), 'alerts_file_exists': ALERTS_FILE.exists(), 'assistant_file_exists': ASSISTANT_FILE.exists(), 'settings_file_exists': SETTINGS_FILE.exists(), 'macro_events_file_exists': MACRO_EVENTS_FILE.exists(), 'telegram_alert_mode': TELEGRAM_ALERT_MODE, 'model': OPENAI_MODEL}


@app.get('/dashboard-data')
async def dashboard_data():
    return build_dashboard_payload()


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
        response = client.responses.create(model=OPENAI_MODEL, instructions=ASSISTANT_SYSTEM_PROMPT, input=f"User message:\n{message}\n\nSystem context:\n{summarize_system_context()}", max_output_tokens=220)
        parsed = parse_json_loose(response.output_text, fallback)
        action, value = str(parsed.get('action', 'none')).strip().lower(), str(parsed.get('value', '')).strip()
        reply = str(parsed.get('reply', '')).strip() or 'Donna processed the request.'
        updated_state = apply_assistant_action(action, value)
        return {'status': 'ok', 'action': action, 'value': value, 'reply': reply, 'assistant': updated_state, 'risk': load_risk_state(), 'alerts': load_alert_history()[:10]}
    except Exception as e:
        return {'status': 'error', 'action': 'none', 'value': '', 'reply': f'Assistant error: {str(e)}', 'assistant': load_assistant_state(), 'risk': load_risk_state(), 'alerts': load_alert_history()[:10]}


DASHBOARD_HTML = '''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8" /><meta name="viewport" content="width=device-width, initial-scale=1.0" /><title>D.O.N.N.A v5.0</title><style>
*{box-sizing:border-box;margin:0;padding:0}:root{--bg:#08111f;--bg2:#0d1830;--panel:#162441;--line:rgba(255,255,255,.10);--text:#edf4ff;--muted:#a3b5d4;--blue:#5f95ff;--blue2:#3972f6;--green:#43f7ad;--yellow:#ffd557;--red:#ff6b86;--shadow:0 18px 48px rgba(0,0,0,.28);--radius:22px}html,body{min-height:100%}body{font-family:Inter,Arial,sans-serif;color:var(--text);background:radial-gradient(circle at 5% 95%, rgba(67,247,173,.10), transparent 20%),radial-gradient(circle at 100% 0%, rgba(95,149,255,.18), transparent 25%),linear-gradient(180deg,var(--bg2),var(--bg));padding:24px}body,.panel,.card,table,th,td,.live-strip,.hero,.row,.badge,.tab-btn,.ghost-btn{caret-color:transparent}.wrap{max-width:1560px;margin:0 auto}button{font:inherit}input,textarea,select{caret-color:auto}input,textarea{user-select:text}button,.tab-btn,.ghost-btn{cursor:pointer}.topbar{display:flex;justify-content:space-between;align-items:flex-start;gap:18px;flex-wrap:wrap;margin-bottom:14px}.brand h1{font-size:52px;line-height:1;font-weight:900;letter-spacing:4px}.brand p{margin-top:8px;color:var(--muted);font-size:13px}.top-right{display:flex;gap:14px;align-items:flex-start;flex-wrap:wrap}.online{display:flex;align-items:center;gap:10px;padding:10px 16px;border-radius:999px;background:rgba(67,247,173,.08);border:1px solid rgba(67,247,173,.24);font-weight:900;color:#b7ffd9;font-size:13px;user-select:none}.dot{width:9px;height:9px;border-radius:50%;background:var(--green);box-shadow:0 0 14px rgba(67,247,173,.8)}.nav{display:flex;gap:10px;flex-wrap:wrap;user-select:none}.tab-btn{border:none;padding:12px 16px;border-radius:14px;background:rgba(255,255,255,.04);color:#edf4ff;font-weight:800;border:1px solid rgba(255,255,255,.08);transition:.18s ease}.tab-btn.active{background:linear-gradient(135deg,var(--blue),var(--blue2));box-shadow:var(--shadow)}.tab-btn:hover{transform:translateY(-1px)}.live-row{display:grid;grid-template-columns:190px 1fr 220px;gap:12px;align-items:center;margin-bottom:16px}.live-pill,.session-pill,.ticker-wrap{background:rgba(255,255,255,.04);border:1px solid var(--line);border-radius:16px;box-shadow:var(--shadow)}.live-pill{padding:14px 16px;color:#ffc7d2;border-color:rgba(255,107,134,.24);background:rgba(255,107,134,.08);font-size:12px;font-weight:900;letter-spacing:1.4px;text-transform:uppercase}.session-pill{padding:14px 16px;text-align:center}.session-pill .lab{font-size:11px;letter-spacing:1.2px;text-transform:uppercase;color:var(--muted)}.session-pill .val{margin-top:6px;font-size:18px;font-weight:900}.ticker-wrap{overflow:hidden;position:relative;min-height:52px;display:flex;align-items:center}.ticker-track{display:inline-flex;white-space:nowrap;padding-left:100%;animation:tickerMove 26s linear infinite;will-change:transform}@keyframes tickerMove{0%{transform:translateX(0)}100%{transform:translateX(-100%)}}.ticker-item{padding-right:40px;color:#e7efff;font-size:13px;font-weight:700}.ticker-item b{color:#fff}.panel,.card{background:linear-gradient(180deg, rgba(27,44,75,.95), rgba(21,36,65,.98));border:1px solid var(--line);border-radius:var(--radius);box-shadow:var(--shadow);padding:22px;user-select:none}.kicker{font-size:11px;text-transform:uppercase;letter-spacing:2px;color:var(--muted);margin-bottom:12px}.hero{display:grid;grid-template-columns:1.45fr 1fr;gap:16px;margin-bottom:16px}.hero-title{font-size:32px;font-weight:900;line-height:1.07}.hero-sub{margin-top:12px;color:var(--muted);font-size:15px;line-height:1.55}.side-stack{display:grid;gap:14px}.mini-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}.mini{background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.07);border-radius:16px;padding:14px}.mini .lab{font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:1.2px}.mini .val{font-size:16px;font-weight:900;margin-top:8px;line-height:1.25}.stat-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:16px}.stat-card .lab{font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:1.7px;margin-bottom:14px}.stat-card .val{font-size:46px;font-weight:900;line-height:1;text-transform:uppercase}.stat-card .sub{margin-top:10px;color:var(--muted);font-size:14px}.low{color:var(--green)} .medium{color:var(--yellow)} .high{color:var(--red)}.page{display:none}.page.active{display:block}.grid-2{display:grid;grid-template-columns:1.15fr .85fr;gap:16px}.stack{display:grid;gap:16px}.row{display:flex;justify-content:space-between;gap:14px;padding:14px 0;border-bottom:1px solid rgba(255,255,255,.08)}.row:last-child{border-bottom:none}.row .k{color:#dce8ff}.row .v{color:var(--muted);text-align:right}.feed-item{padding:13px 0;border-bottom:1px solid rgba(255,255,255,.08);line-height:1.5;color:#e9f1ff}.feed-item:last-child{border-bottom:none}.badges{display:flex;gap:10px;flex-wrap:wrap}.badge{padding:9px 12px;border-radius:999px;font-size:12px;font-weight:800;background:rgba(255,107,134,.08);border:1px solid rgba(255,107,134,.24);color:#ffc7d2}.table-card table{width:100%;border-collapse:collapse}.table-card th{color:var(--muted);text-align:left;padding:0 0 12px 0;border-bottom:1px solid rgba(255,255,255,.10);font-size:12px;text-transform:uppercase;letter-spacing:1.4px}.table-card td{padding:12px 0;border-bottom:1px solid rgba(255,255,255,.07);font-size:14px;font-weight:700}.table-card tr:last-child td{border-bottom:none}.up{color:var(--green)} .down{color:var(--red)}.strip-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}.soft-note{margin-top:12px;color:var(--muted);font-size:14px;line-height:1.55}.action-row{display:flex;gap:10px;flex-wrap:wrap;margin-top:12px}.ghost-btn{border:none;padding:10px 12px;border-radius:12px;background:rgba(255,255,255,.05);color:#edf4ff;border:1px solid rgba(255,255,255,.08)}.assistant-output{min-height:220px;max-height:460px;overflow:auto;border-radius:18px;background:rgba(0,0,0,.16);border:1px solid rgba(255,255,255,.08);padding:14px;user-select:text;caret-color:auto}.msg{margin-bottom:12px;padding:12px 13px;border-radius:14px;line-height:1.5;font-size:14px}.msg.user{background:rgba(95,149,255,.14);border:1px solid rgba(95,149,255,.24)}.msg.assistant{background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.08)}.msg .role{display:block;font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:1.1px;margin-bottom:6px}.text-input{width:100%;padding:13px 14px;margin-top:12px;border-radius:14px;border:1px solid rgba(255,255,255,.09);background:rgba(255,255,255,.04);color:#fff;outline:none;user-select:text}.footer{margin-top:18px;display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;color:var(--muted);font-size:12px}@media(max-width:1200px){.hero,.grid-2,.strip-grid{grid-template-columns:1fr}.stat-grid{grid-template-columns:repeat(2,1fr)}.live-row{grid-template-columns:1fr}}@media(max-width:760px){body{padding:16px}.brand h1{font-size:38px}.stat-grid{grid-template-columns:1fr}}</style></head><body><div class="wrap"><div class="topbar"><div class="brand"><h1>D.O.N.N.A</h1><p>Dynamic Operational Neural Network Assistant // Live Market Core</p></div><div class="top-right"><div class="nav"><button class="tab-btn active" data-page="dashboard">Dashboard</button><button class="tab-btn" data-page="trading">Trading</button><button class="tab-btn" data-page="news">News</button><button class="tab-btn" data-page="assistant">Assistant</button></div><div class="online"><span class="dot"></span>ONLINE</div></div></div><div class="live-row"><div class="live-pill">Live Intelligence</div><div class="ticker-wrap"><div class="ticker-track" id="liveStrip"></div></div><div class="session-pill"><div class="lab">Current Session</div><div class="val" id="sessionVal">-</div></div></div><div class="hero"><div class="panel"><div class="kicker">Donna Overview</div><div class="hero-title" id="heroTitle">Loading...</div><div class="hero-sub" id="heroSub">Loading...</div></div><div class="panel side-stack"><div><div class="kicker">Morning Edge</div><div style="font-size:20px;font-weight:900" id="morningBias">-</div><div class="soft-note" id="morningRead">-</div></div><div class="mini-grid"><div class="mini"><div class="lab">Donna Time</div><div class="val" id="donnaTime">-</div></div><div class="mini"><div class="lab">Open Quality</div><div class="val" id="openQuality">-</div></div></div><div><div class="kicker">Main Threat</div><div style="font-size:18px;font-weight:900" id="mainThreat">-</div><div class="soft-note" id="focusRead">-</div></div></div></div><div class="stat-grid"><div class="card stat-card"><div class="lab">Macro Risk</div><div class="val medium" id="macroRisk">-</div><div class="sub">Event timing and macro pressure</div></div><div class="card stat-card"><div class="lab">Headline Risk</div><div class="val medium" id="headlineRisk">-</div><div class="sub">Breaking-news sensitivity</div></div><div class="card stat-card"><div class="lab">Market Risk</div><div class="val medium" id="marketRisk">-</div><div class="sub">Company and sector catalyst pressure</div></div><div class="card stat-card"><div class="lab">Session Significance</div><div class="val" style="font-size:20px;line-height:1.15" id="sessionSignificance">-</div><div class="sub" id="sessionSub">-</div></div></div><div class="page active" id="page-dashboard"><div class="grid-2"><div class="stack"><div class="panel"><div class="kicker">Market Driver Engine</div><div class="row"><div class="k">Dominant Driver</div><div class="v" id="driverDominant">-</div></div><div class="row"><div class="k">Secondary Driver</div><div class="v" id="driverSecondary">-</div></div><div class="row"><div class="k">Regime</div><div class="v" id="driverRegime">-</div></div><div class="row"><div class="k">Threat</div><div class="v" id="driverThreat">-</div></div><div class="row"><div class="k">Confidence</div><div class="v" id="driverConfidence">-</div></div><div class="soft-note" id="driverSummary">-</div></div><div class="panel table-card"><div class="kicker">Major Indexes</div><table><thead><tr><th>Index</th><th>Last</th><th>Chg</th><th>%Chg</th></tr></thead><tbody id="majorIndexesTable"></tbody></table></div><div class="panel"><div class="kicker">Active Warnings</div><div class="badges" id="warnings"></div></div></div><div class="stack"><div class="panel table-card"><div class="kicker">Likely Market Movers</div><table><thead><tr><th>Ticker</th><th>Impact</th><th>Why</th></tr></thead><tbody id="likelyMoversTable"></tbody></table></div><div class="strip-grid"><div class="panel table-card"><div class="kicker">Top Movers</div><table><thead><tr><th>Symbol</th><th>Last</th><th>Chg</th><th>%Chg</th></tr></thead><tbody id="topMoversTable"></tbody></table></div><div class="panel table-card"><div class="kicker">Bottom Movers</div><table><thead><tr><th>Symbol</th><th>Last</th><th>Chg</th><th>%Chg</th></tr></thead><tbody id="bottomMoversTable"></tbody></table></div></div><div class="panel"><div class="kicker">Top Story</div><div style="font-size:24px;font-weight:900;line-height:1.18" id="topStory">-</div><div class="soft-note" id="topStoryNote">-</div></div></div></div></div><div class="page" id="page-trading"><div class="grid-2"><div class="stack"><div class="panel"><div class="kicker">What Matters Right Now</div><div style="font-size:28px;font-weight:900;line-height:1.12" id="tradingHeadline">-</div><div class="soft-note" id="tradingSummary">-</div><div class="action-row" id="watchFirstRow"></div></div><div class="panel"><div class="kicker">Recent Alerts</div><div id="recentAlerts"></div></div></div><div class="stack"><div class="panel table-card"><div class="kicker">Futures + Macro Pulse</div><table><thead><tr><th>Asset</th><th>Last</th><th>Chg</th><th>%Chg</th></tr></thead><tbody id="tradingPulseTable"></tbody></table></div><div class="panel"><div class="kicker">Trade Intelligence</div><div class="row"><div class="k">Bias</div><div class="v" id="tradeBias">-</div></div><div class="row"><div class="k">Open Quality</div><div class="v" id="tradeOpenQuality">-</div></div><div class="row"><div class="k">Main Threat</div><div class="v" id="tradeThreat">-</div></div><div class="row"><div class="k">Focus</div><div class="v" id="tradeFocus">-</div></div><div class="soft-note" id="tradeNote">-</div></div></div></div></div><div class="page" id="page-news"><div class="grid-2"><div class="stack"><div class="panel"><div class="kicker">Macro Story</div><div style="font-size:28px;font-weight:900;line-height:1.12" id="newsMacroTitle">-</div><div class="soft-note" id="newsMacroNote">-</div></div><div class="panel"><div class="kicker">Market Catalyst</div><div style="font-size:24px;font-weight:900;line-height:1.18" id="newsMarketTitle">-</div><div class="soft-note" id="newsMarketNote">-</div></div><div class="panel"><div class="kicker">Latest News</div><div id="newsList"></div></div></div><div class="stack"><div class="panel table-card"><div class="kicker">Leaders</div><table><thead><tr><th>Ticker</th><th>Impact</th><th>Index</th></tr></thead><tbody id="leadersTable"></tbody></table></div><div class="panel table-card"><div class="kicker">Threat Names</div><table><thead><tr><th>Ticker</th><th>Impact</th><th>Index</th></tr></thead><tbody id="threatsTable"></tbody></table></div><div class="panel table-card"><div class="kicker">Next To Watch</div><table><thead><tr><th>Ticker</th><th>Impact</th><th>Index</th></tr></thead><tbody id="nextWatchTable"></tbody></table></div></div></div></div><div class="page" id="page-assistant"><div class="grid-2"><div class="panel"><div class="kicker">Donna AI Assistant</div><div class="assistant-output" id="assistantOutput"><div class="msg assistant"><span class="role">Donna</span>Donna online. Ask what matters now, whether the session was significant, or which names can move the market.</div></div><textarea class="text-input" id="assistantInput" placeholder="Ask Donna something..."></textarea><div class="action-row"><button class="tab-btn" id="assistantSend">Send</button><button class="ghost-btn" data-prompt="What matters right now?">What matters now?</button><button class="ghost-btn" data-prompt="Was this a significant NY session move?">Session significance</button><button class="ghost-btn" data-prompt="What companies are most likely to move the market?">Likely movers</button></div></div><div class="stack"><div class="panel"><div class="kicker">Daily Focus</div><div style="font-size:20px;font-weight:900" id="dailyFocus">-</div><input class="text-input" id="focusInput" placeholder="Set daily focus" /><div class="action-row"><button class="tab-btn" id="setFocusBtn">Set Focus</button></div></div><div class="panel"><div class="kicker">Tasks</div><div id="taskList"></div><input class="text-input" id="taskInput" placeholder="Add task" /><div class="action-row"><button class="tab-btn" id="addTaskBtn">Add Task</button><button class="ghost-btn" id="clearTasksBtn">Clear Tasks</button></div></div><div class="panel"><div class="kicker">Reminders</div><div id="reminderList"></div><input class="text-input" id="reminderInput" placeholder="Add reminder" /><div class="action-row"><button class="tab-btn" id="addReminderBtn">Add Reminder</button><button class="ghost-btn" id="clearRemindersBtn">Clear Reminders</button></div></div></div></div></div><div class="footer"><div>Donna v5.0 Live Market Core</div><div id="footerUpdated">last update: -</div></div></div><script>let state=null;const byId=id=>document.getElementById(id);function toRiskClass(v){v=String(v||'').toLowerCase();if(v==='high')return'high';if(v==='medium')return'medium';return'low'}function showPage(name){document.querySelectorAll('.page').forEach(p=>p.classList.remove('active'));document.querySelectorAll('.tab-btn[data-page]').forEach(b=>b.classList.remove('active'));byId('page-'+name).classList.add('active');document.querySelector('.tab-btn[data-page="'+name+'"]').classList.add('active')}document.querySelectorAll('.tab-btn[data-page]').forEach(btn=>btn.addEventListener('click',()=>showPage(btn.dataset.page)));function renderSimpleRows(rows,targetId){byId(targetId).innerHTML=rows.map(r=>`<tr><td>${r.symbol}</td><td>${r.last}</td><td class="${r.dir||(String(r.chg).startsWith('-')?'down':'up')}">${r.chg}</td><td class="${r.dir||(String(r.pct).startsWith('-')?'down':'up')}">${r.pct}</td></tr>`).join('')}function renderLikelyMovers(rows,targetId){byId(targetId).innerHTML=rows.map(r=>`<tr><td>${r.ticker}</td><td>${r.impact}</td><td>${r.why_it_matters}</td></tr>`).join('')}function renderTriple(rows,targetId){byId(targetId).innerHTML=rows.map(r=>`<tr><td>${r.ticker}</td><td>${r.impact}</td><td>${r.index_exposure}</td></tr>`).join('')}function renderAlerts(alerts){if(!alerts||!alerts.length){byId('recentAlerts').innerHTML='<div class="feed-item">No alerts yet</div>';return}byId('recentAlerts').innerHTML=alerts.map(a=>`<div class="feed-item"><b>${a.ticker}</b> // ${a.signal} // ${a.verdict} // ${a.confidence}<br/><span style="color:var(--muted)">${a.session} | TF ${a.timeframe} | Price ${a.price}</span><br/>${a.summary}</div>`).join('')}function renderNews(news){if(!news||!news.length){byId('newsList').innerHTML='<div class="feed-item">No live news available</div>';return}byId('newsList').innerHTML=news.map(n=>`<div class="feed-item"><b>${n.headline}</b><br/><span style="color:var(--muted)">${n.source}</span><br/>${n.summary||''}</div>`).join('')}function renderTasks(list,targetId,route){if(!list||!list.length){byId(targetId).innerHTML='<div class="feed-item">None</div>';return}byId(targetId).innerHTML=list.map((item,idx)=>`<div class="feed-item">${item}<div class="action-row"><button class="ghost-btn" onclick="deleteIndexed('${route}', ${idx})">Delete</button></div></div>`).join('')}function buildTicker(items){byId('liveStrip').innerHTML=items.map(item=>`<div class="ticker-item"><b>${item.label}:</b> ${item.value}</div>`).join('')}async function api(url,options={}){const res=await fetch(url,{headers:{'Content-Type':'application/json'},...options});const data=await res.json().catch(()=>({}));if(!res.ok) throw new Error(data.detail||data.reply||'Request failed');return data}function addAssistantMessage(role,text){const wrap=byId('assistantOutput');const div=document.createElement('div');div.className='msg '+role;div.innerHTML=`<span class="role">${role==='user'?'You':'Donna'}</span>${text}`;wrap.appendChild(div);wrap.scrollTop=wrap.scrollHeight}async function sendAssistant(message=null){const input=byId('assistantInput');const text=message||input.value.trim();if(!text)return;addAssistantMessage('user',text);if(!message)input.value='';try{const data=await api('/assistant/chat',{method:'POST',body:JSON.stringify({message:text})});addAssistantMessage('assistant',data.reply||'No reply.');await refresh()}catch(err){addAssistantMessage('assistant','Assistant error: '+err.message)}}async function deleteIndexed(route,index){try{await api(route,{method:'POST',body:JSON.stringify({index})});await refresh()}catch(err){alert(err.message)}}async function setFocus(){const value=byId('focusInput').value.trim();if(!value)return;await api('/assistant/set-focus',{method:'POST',body:JSON.stringify({daily_focus:value})});byId('focusInput').value='';await refresh()}async function addTask(){const value=byId('taskInput').value.trim();if(!value)return;await api('/assistant/add-task',{method:'POST',body:JSON.stringify({task:value})});byId('taskInput').value='';await refresh()}async function addReminder(){const value=byId('reminderInput').value.trim();if(!value)return;await api('/assistant/add-reminder',{method:'POST',body:JSON.stringify({reminder:value})});byId('reminderInput').value='';await refresh()}async function refresh(){state=await api('/dashboard-data');const risk=state.risk,driver=state.driver,morning=state.morning_edge,sig=state.session_significance,movers=state.market_movers_engine;buildTicker(state.live_strip);byId('sessionVal').textContent=risk.donna_session;byId('heroTitle').textContent=`${driver.dominant_driver} is driving current conditions.`;byId('heroSub').textContent=driver.market_summary;byId('morningBias').textContent=morning.today_bias;byId('morningRead').textContent=morning.first_read;byId('donnaTime').textContent=risk.donna_time_ny;byId('openQuality').textContent=morning.open_quality;byId('mainThreat').textContent=morning.main_threat;byId('focusRead').textContent=`Focus: ${morning.focus}`;let macro=byId('macroRisk');macro.textContent=String(risk.macro_risk).toUpperCase();macro.className='val '+toRiskClass(risk.macro_risk);let headline=byId('headlineRisk');headline.textContent=String(risk.headline_risk).toUpperCase();headline.className='val '+toRiskClass(risk.headline_risk);let market=byId('marketRisk');market.textContent=String(risk.market_news_risk).toUpperCase();market.className='val '+toRiskClass(risk.market_news_risk);byId('sessionSignificance').textContent=sig.label;byId('sessionSub').textContent=sig.summary;byId('driverDominant').textContent=driver.dominant_driver;byId('driverSecondary').textContent=driver.secondary_driver;byId('driverRegime').textContent=driver.market_regime;byId('driverThreat').textContent=driver.market_threat||morning.main_threat;byId('driverConfidence').textContent=driver.market_confidence;byId('driverSummary').textContent=driver.market_summary;byId('warnings').innerHTML=(risk.active_warnings||[]).map(x=>`<span class="badge">${x}</span>`).join('');renderSimpleRows(state.major_indexes,'majorIndexesTable');renderLikelyMovers(movers.leaders.concat(movers.next_to_watch),'likelyMoversTable');renderSimpleRows(state.live_movers.gainers||[],'topMoversTable');renderSimpleRows(state.live_movers.losers||[],'bottomMoversTable');byId('topStory').textContent=risk.last_headline;byId('topStoryNote').textContent=risk.headline_guidance;byId('tradingHeadline').textContent=`${sig.label} // ${morning.focus}`;byId('tradingSummary').textContent=sig.summary;const coreFocus = ['NQ', 'ES', 'OIL', 'GOLD', 'SILVER'];
byId('watchFirstRow').innerHTML = coreFocus.map(x => `<button class="ghost-btn">${x}</button>`).join('');byId('tradeBias').textContent=morning.today_bias;byId('tradeOpenQuality').textContent=morning.open_quality;byId('tradeThreat').textContent=morning.main_threat;byId('tradeFocus').textContent=morning.focus;byId('tradeNote').textContent=morning.first_read;renderSimpleRows(state.futures_macro_pulse || [], 'tradingPulseTable');renderAlerts(state.alerts);byId('newsMacroTitle').textContent=state.calendar.next_event||risk.next_event;byId('newsMacroNote').textContent=`Source: ${state.calendar.source}. Minutes to event: ${state.calendar.minutes_to_event??'n/a'}`;byId('newsMarketTitle').textContent=risk.last_market_headline;byId('newsMarketNote').textContent=risk.last_market_guidance;renderNews(state.news);renderTriple(movers.leaders,'leadersTable');renderTriple(movers.threats,'threatsTable');renderTriple(movers.next_to_watch,'nextWatchTable');byId('dailyFocus').textContent=state.assistant.daily_focus;renderTasks(state.assistant.tasks,'taskList','/assistant/delete-task');renderTasks(state.assistant.reminders,'reminderList','/assistant/delete-reminder');byId('footerUpdated').textContent='last update: '+risk.donna_time_ny}document.querySelectorAll('.ghost-btn[data-prompt]').forEach(btn=>btn.addEventListener('click',()=>sendAssistant(btn.dataset.prompt)));byId('assistantSend').addEventListener('click',()=>sendAssistant());byId('assistantInput').addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();sendAssistant()}});byId('setFocusBtn').addEventListener('click',setFocus);byId('addTaskBtn').addEventListener('click',addTask);byId('addReminderBtn').addEventListener('click',addReminder);byId('clearTasksBtn').addEventListener('click',async()=>{await api('/assistant/clear-tasks',{method:'POST'});await refresh()});byId('clearRemindersBtn').addEventListener('click',async()=>{await api('/assistant/clear-reminders',{method:'POST'});await refresh()});refresh();setInterval(refresh,15000);</script></body></html>'''


@app.get('/dashboard', response_class=HTMLResponse)
async def dashboard():
    return HTMLResponse(content=DASHBOARD_HTML)
