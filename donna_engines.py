"""donna_engines.py — live data fetchers, build_ functions, scenario/morning-brief logic."""
from __future__ import annotations

import json
import re
from datetime import timedelta

from donna_config import (
    FINNHUB_API_KEY, FMP_API_KEY, ALPHA_VANTAGE_API_KEY,
    ANTHROPIC_ASSISTANT_MODEL, ANTHROPIC_MODEL,
    MORNING_BRIEF_FILE, FOREX_FACTORY_NOTES_URL,
    client, cache_get, cache_set, safe_float, utc_now_iso,
    now_ny, session_label, send_telegram_message, _requests_get_json,
)
from donna_state import (
    load_risk_state, load_alert_history, load_assistant_state, load_settings,
    load_macro_events, load_journal, write_json_file,
)

try:
    from donna_risk_engine import build_risk_engine_payload, load_re_state
except Exception:
    def build_risk_engine_payload(*a, **kw):
        return {'stop_trading': False, 'stop_reason': '', 'position_size': {}, 'rr': {}, 'drawdown': {}, 'session_losses': {}}
    def load_re_state():
        return {'account_size': 25000.0, 'risk_pct': 1.0}


# ── Quote fetchers ─────────────────────────────────────────────

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


def build_price_levels(fmp_symbol, session, market_open_mins):
    """Today's OHLC, PDH/PDL from daily history, and ORB from 1-min intraday."""
    cache_key = f'price_levels::{fmp_symbol}'
    cached = cache_get(cache_key)
    if cached:
        return cached

    result = {
        'today_open': None, 'today_high': None, 'today_low': None,
        'prev_high': None,  'prev_low': None,
        'orb_high': None,   'orb_low': None,
    }

    if not FMP_API_KEY:
        cache_set(cache_key, result, 30)
        return result

    try:
        d = _requests_get_json(f'https://financialmodelingprep.com/api/v3/quote/{fmp_symbol}', {'apikey': FMP_API_KEY})
        if d and isinstance(d, list):
            q = d[0]
            result['today_open'] = safe_float(q.get('open'))
            result['today_high'] = safe_float(q.get('dayHigh'))
            result['today_low']  = safe_float(q.get('dayLow'))
    except Exception:
        pass

    try:
        d = _requests_get_json(
            f'https://financialmodelingprep.com/api/v3/historical-price-full/{fmp_symbol}',
            {'timeseries': '2', 'apikey': FMP_API_KEY},
        )
        hist = (d or {}).get('historical', [])
        if len(hist) >= 2:
            prev = hist[1]
            result['prev_high'] = safe_float(prev.get('high'))
            result['prev_low']  = safe_float(prev.get('low'))
    except Exception:
        pass

    if session == 'NEW_YORK_CASH' and market_open_mins >= 5:
        try:
            today_str = now_ny().strftime('%Y-%m-%d')
            bars = _requests_get_json(
                f'https://financialmodelingprep.com/api/v3/historical-chart/1min/{fmp_symbol}',
                {'from': today_str, 'to': today_str, 'apikey': FMP_API_KEY},
            )
            if isinstance(bars, list):
                orb_times = {'09:30:00', '09:31:00', '09:32:00', '09:33:00', '09:34:00'}
                orb_bars = [b for b in bars if any(str(b.get('date', '')).endswith(t) for t in orb_times)]
                if orb_bars:
                    highs = [safe_float(b.get('high', 0)) for b in orb_bars]
                    lows  = [safe_float(b.get('low',  0)) for b in orb_bars]
                    result['orb_high'] = max((h for h in highs if h), default=None)
                    result['orb_low']  = min((l for l in lows  if l), default=None)
        except Exception:
            pass

    cache_set(cache_key, result, 60)
    return result


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


# ── Live aggregated data ───────────────────────────────────────

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
            'dir': 'up' if (pct_num is not None and pct_num >= 0) else 'down',
        })

    cache_set('major_indexes', rows, 20)
    return rows


def get_live_futures_macro_pulse():
    c = cache_get('futures_macro_pulse')
    if c:
        return c

    fallback = load_risk_state().get('market_snapshot', {})
    rows = []

    futures_assets = [('NQ', 'NQ'), ('ES', 'ES'), ('OIL', 'OIL'), ('GOLD', 'GOLD'), ('SILVER', 'SILVER')]
    macro_assets   = [('DXY', 'DX-Y.NYB', 'DXY'), ('US10Y', '^TNX', 'US10Y'), ('VIX', '^VIX', 'VIX')]

    for label, fallback_key in futures_assets:
        q = get_futures_quote(label)
        if not q:
            q = fallback.get(fallback_key, {})
        last = (q or {}).get('last', '-')
        chg  = (q or {}).get('chg', '-')
        pct_raw = (q or {}).get('pct', None)
        pct_num = safe_float(pct_raw, None) if pct_raw is not None else None
        rows.append({
            'symbol': label,
            'last': last if last not in (None, 0) else '-',
            'chg': chg if chg not in (None, 0) else '-',
            'pct': f'{pct_num:+.2f}%' if pct_num is not None and last not in (None, '-', 0) else '-',
            'dir': 'up' if (pct_num is not None and pct_num >= 0) else 'down',
        })

    for label, symbol, fallback_key in macro_assets:
        q = get_quote_with_fallback(symbol)
        if not q:
            q = fallback.get(fallback_key, {})
        last = (q or {}).get('last', '-')
        chg  = (q or {}).get('chg', '-')
        pct_raw = (q or {}).get('pct', None)
        pct_num = safe_float(pct_raw, None) if pct_raw is not None else None
        rows.append({
            'symbol': label,
            'last': last if last not in (None, 0) else '-',
            'chg': chg if chg not in (None, 0) else '-',
            'pct': f'{pct_num:+.2f}%' if pct_num is not None and last not in (None, '-', 0) else '-',
            'dir': 'up' if (pct_num is not None and pct_num >= 0) else 'down',
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
            out.append({
                'symbol': it.get('symbol', '-'),
                'last': it.get('price', '-'),
                'chg': f"{safe_float(it.get('change', 0)):+.2f}",
                'pct': f"{safe_float(it.get('changesPercentage', 0)):+.2f}%",
            })
        return out

    result = {
        'gainers': norm(fetch_fmp_market_movers('gainers')),
        'losers':  norm(fetch_fmp_market_movers('losers')),
        'actives': norm(fetch_fmp_market_movers('actives')),
    }
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
        watchlist.append({
            'symbol': it.get('symbol', '-'),
            'last': it.get('price', '-'),
            'chg': f"{safe_float(it.get('change', 0)):+.2f}",
            'pct': f"{pct:+.2f}%",
            'dir': 'up' if pct >= 0 else 'down',
        })
    result = {'major_indexes': get_live_major_indexes(), 'watchlist': watchlist}
    cache_set('market_data', result, 20)
    return result


def get_live_calendar():
    c = cache_get('calendar')
    if c:
        return c
    data   = load_macro_events()
    events = data.get('events', [])
    now    = now_ny()

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
        row  = dict(ev)
        row['minutes_to_event'] = mins
        rows.append(row)
        if mins is not None and mins >= 0 and (next_minutes is None or mins < next_minutes):
            next_minutes, next_event = mins, ev.get('title', 'Macro Event')

    result = {
        'source': data.get('source', 'ForexFactory/manual'),
        'events': rows,
        'next_event': next_event or 'No scheduled event',
        'minutes_to_event': next_minutes,
    }
    cache_set('calendar', result, 300)
    return result


def get_live_earnings():
    c = cache_get('earnings')
    if c:
        return c
    today = now_ny().date().isoformat()
    week  = (now_ny().date() + timedelta(days=7)).isoformat()
    data  = fetch_finnhub_earnings(today, week)
    before_open, after_close, this_week = [], [], []
    for item in data[:50]:
        row = {
            'symbol': item.get('symbol', '-'),
            'date': item.get('date', '-'),
            'hour': item.get('hour', '-'),
            'eps_estimate': item.get('epsEstimate'),
            'eps_actual': item.get('epsActual'),
        }
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
    data   = fetch_finnhub_market_news()
    result = [{'headline': x.get('headline', '-'), 'source': x.get('source', '-'), 'summary': x.get('summary', ''), 'url': x.get('url', '')} for x in data[:8]]
    cache_set('news', result, 120)
    return result


# ── Engine helpers ─────────────────────────────────────────────

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


# ── Core build_ functions ──────────────────────────────────────

def build_session_significance(risk=None):
    state    = risk or load_risk_state()
    snap     = state.get('market_snapshot', {})
    nq_points = safe_float(snap.get('NQ_SESSION_POINTS', 0))
    es_points = safe_float(snap.get('ES_SESSION_POINTS', 0))
    nas_pct   = safe_float(snap.get('NASDAQ', {}).get('pct', 0))
    spx_pct   = safe_float(snap.get('SPX', {}).get('pct', 0))
    nq_label  = classify_move(nq_points, nas_pct, 'NQ')
    es_label  = classify_move(es_points, spx_pct, 'ES')

    summary = 'This session was routine.'
    if nq_label == 'MAJOR':
        summary = f'NQ pushed roughly {int(nq_points)} points in the NY session. That is major, not routine.'
    elif nq_label == 'NOTABLE':
        summary = f'NQ posted a meaningful session expansion of about {int(nq_points)} points.'
    elif nq_label == 'ACTIVE':
        summary = 'The session is active, but not extraordinary.'
    if es_label in {'MAJOR', 'NOTABLE'}:
        summary += ' ES participation confirms broad index support.'
    if state.get('donna_session') == 'NEW_YORK_CASH':
        summary += ' Because this happened in New York cash hours, the move matters more.'

    return {
        'label': f'{nq_label} NY Session',
        'nq_points': round(nq_points, 2),
        'nq_pct': round(nas_pct, 2),
        'es_points': round(es_points, 2),
        'es_pct': round(spx_pct, 2),
        'summary': summary,
    }


def build_market_driver_engine(risk=None):
    state  = risk or load_risk_state()
    macro, headline, market = (
        str(state.get('macro_risk', 'low')).lower(),
        str(state.get('headline_risk', 'low')).lower(),
        str(state.get('market_news_risk', 'low')).lower(),
    )
    text = (str(state.get('last_headline', '')) + ' ' + str(state.get('last_market_headline', ''))).lower()

    dominant_driver   = 'Balanced Conditions'
    secondary_driver  = 'No clear secondary force'
    market_regime     = 'Neutral'
    market_threat     = state.get('next_event', 'None')
    market_confidence = 'Low'
    market_summary    = 'No strong market driver currently detected.'

    sig = build_session_significance(state)
    if sig['nq_points'] >= 220:
        dominant_driver, market_regime, market_confidence, market_summary = (
            'Mega-Cap / Nasdaq Leadership', 'Trend Expansion', 'High',
            'Leadership names are driving a meaningful Nasdaq session expansion.',
        )

    if 'fed' in text or 'rates' in text or 'yield' in text:
        secondary_driver = 'Rates / Fed Sensitivity'
    elif 'oil' in text or 'energy' in text:
        secondary_driver = 'Energy Pressure'
    elif 'war' in text or 'iran' in text or 'geopolitical' in text:
        secondary_driver = 'Geopolitical Risk'

    if macro == 'high':
        dominant_driver, market_regime, market_confidence, market_summary = (
            'Macro Event Risk', 'Macro-Sensitive', 'High',
            'Macro timing is dominating price behavior.',
        )
    elif headline == 'high':
        dominant_driver, market_regime, market_confidence, market_summary = (
            'Headline Shock', 'Reactive Conditions', 'Medium-High',
            'Breaking headlines are steering short-term market behavior.',
        )
    elif market == 'high' and dominant_driver == 'Balanced Conditions':
        dominant_driver, market_regime, market_confidence, market_summary = (
            'Company Catalyst Pressure', 'Catalyst Driven', 'Medium',
            'Company-specific catalysts are pushing market tone.',
        )

    return {
        'dominant_driver': dominant_driver,
        'secondary_driver': secondary_driver,
        'market_regime': market_regime,
        'market_threat': market_threat,
        'market_confidence': market_confidence,
        'market_summary': market_summary,
    }


def build_morning_edge(risk=None):
    state  = risk or load_risk_state()
    driver = build_market_driver_engine(state)
    sig    = build_session_significance(state)
    snap   = state.get('market_snapshot', {})
    nas_pct = safe_float(snap.get('NASDAQ', {}).get('pct', 0))
    spx_pct = safe_float(snap.get('SPX', {}).get('pct', 0))

    today_bias = 'Risk-On' if nas_pct > 0 and spx_pct >= 0 else 'Mixed'
    if str(state.get('macro_risk', 'medium')).lower() == 'high':
        today_bias = 'High Event Risk'
    open_quality = 'Strong' if sig['label'].startswith('MAJOR') or sig['label'].startswith('NOTABLE') else 'Balanced'
    focus       = 'Nasdaq Momentum' if nas_pct >= spx_pct else 'Broad Index Strength'
    main_threat = state.get('next_event', 'No major event')
    watch_first = ['NVDA', 'MSFT', 'AMZN', 'AMD'] if 'Nasdaq' in focus else ['SPY', 'QQQ', 'JPM', 'AAPL']
    first_read  = 'Treat leadership strength as real until the market proves otherwise.'
    if str(state.get('event_phase', '')).upper() in {'LIVE', 'IMMINENT', 'APPROACHING'}:
        first_read = 'Respect event timing. Do not confuse pre-event noise for true conviction.'

    return {
        'today_bias': today_bias,
        'main_threat': main_threat,
        'open_quality': open_quality,
        'focus': focus,
        'watch_first': watch_first,
        'first_read': first_read,
        'driver_note': driver['market_summary'],
    }


def build_what_matters_now(risk=None):
    state  = risk or load_risk_state()
    morning = build_morning_edge(state)
    driver  = build_market_driver_engine(state)
    sig     = build_session_significance(state)
    pulse   = get_live_futures_macro_pulse()

    pulse_map = {row['symbol']: row for row in pulse}

    def pct(symbol):
        row = pulse_map.get(symbol, {})
        raw = str(row.get('pct', '')).replace('%', '').replace('+', '').strip()
        try:
            return float(raw)
        except Exception:
            return None

    nq_pct    = pct('NQ')
    es_pct    = pct('ES')
    oil_pct   = pct('OIL')
    gold_pct  = pct('GOLD')
    silver_pct = pct('SILVER')
    dxy_pct   = pct('DXY')
    vix_pct   = pct('VIX')
    us10y_pct = pct('US10Y')

    headline           = 'Balanced conditions'
    summary            = 'Donna does not yet see one dominant cross-asset force.'
    watch              = ['NQ', 'ES', 'OIL', 'GOLD', 'SILVER']
    mode               = 'balanced'
    risk_to_conviction = 'Normal'
    focus_reason       = 'No single asset is overpowering the tape yet.'

    if str(state.get('macro_risk', '')).lower() == 'high' or (vix_pct is not None and vix_pct >= 4):
        headline           = 'Macro risk is in control right now'
        summary            = f"{state.get('next_event', 'Macro timing matters')} is the main threat. Respect reaction risk over conviction."
        watch              = ['NQ', 'ES', 'DXY', 'US10Y', 'VIX']
        mode               = 'macro_risk'
        risk_to_conviction = 'High'
        focus_reason       = 'Event timing and volatility expansion matter more than clean trend continuation.'
    elif oil_pct is not None and abs(oil_pct) >= 2.0:
        direction          = 'surging' if oil_pct > 0 else 'breaking lower'
        headline           = f'Oil is {direction} and changing the tone'
        summary            = 'Energy is making a real move. Watch for cross-asset pressure, inflation/risk sentiment shifts, and index reaction.'
        watch              = ['OIL', 'ES', 'NQ', 'DXY', 'US10Y']
        mode               = 'oil_shock'
        risk_to_conviction = 'Medium-High'
        focus_reason       = 'Crude is the dominant mover and can reshape equity tone fast.'
    elif (gold_pct is not None and abs(gold_pct) >= 1.0) or (silver_pct is not None and abs(silver_pct) >= 2.0):
        headline           = 'Metals are making a real move'
        summary            = 'Gold and silver are active enough to matter for macro interpretation and defensive tone.'
        watch              = ['GOLD', 'SILVER', 'DXY', 'US10Y', 'NQ']
        mode               = 'metals'
        risk_to_conviction = 'Medium'
        focus_reason       = 'Precious metals are signaling a macro/defensive shift worth respecting.'
    elif nq_pct is not None and nq_pct >= 0.75:
        headline           = 'Nasdaq momentum is still leading'
        summary            = sig['summary']
        watch              = ['NQ', 'ES', 'NVDA', 'MSFT', 'AMD']
        mode               = 'nq_momentum'
        risk_to_conviction = 'Medium'
        focus_reason       = 'Nasdaq leadership is strong enough to stay front and center.'
    elif (nq_pct is not None and nq_pct <= -0.75) or (es_pct is not None and es_pct <= -0.60):
        headline           = 'Risk-off pressure is leading this tape'
        summary            = 'Index pressure is strong enough to matter. Watch whether this is just rotation or true stress.'
        watch              = ['NQ', 'ES', 'VIX', 'DXY', 'US10Y']
        mode               = 'risk_off'
        risk_to_conviction = 'High'
        focus_reason       = 'Downside pressure plus defensive confirmation raises fragility.'
    elif (dxy_pct is not None and abs(dxy_pct) >= 0.40) or (us10y_pct is not None and abs(us10y_pct) >= 1.00):
        headline           = 'Macro pressure is coming from dollar / rates'
        summary            = 'DXY or yields are moving enough to affect equities and metals. Respect cross-asset pressure first.'
        watch              = ['DXY', 'US10Y', 'NQ', 'ES', 'GOLD']
        mode               = 'rates_fx'
        risk_to_conviction = 'Medium-High'
        focus_reason       = 'Rates and dollar movement are strong enough to distort clean equity reads.'
    else:
        headline           = f"{driver['dominant_driver']} is driving current conditions."
        summary            = driver['market_summary']
        watch              = ['NQ', 'ES', 'OIL', 'GOLD', 'SILVER']
        mode               = 'balanced'
        risk_to_conviction = 'Normal'
        focus_reason       = 'Donna sees a tradable environment, but not one overwhelming cross-asset driver.'

    return {
        'headline': headline,
        'summary': summary,
        'watch': watch,
        'mode': mode,
        'risk_to_conviction': risk_to_conviction,
        'focus_reason': focus_reason,
    }


def build_regime_engine(risk=None, sig=None, pulse=None, bias_score=50):
    state = risk or load_risk_state()
    sig   = sig or build_session_significance(state)
    if pulse is None:
        pulse = get_live_futures_macro_pulse()

    pulse_map = {r['symbol']: r for r in pulse}

    def pct_float(sym):
        raw = str(pulse_map.get(sym, {}).get('pct', '')).replace('%', '').replace('+', '').strip()
        try:
            return float(raw)
        except Exception:
            return None

    macro       = str(state.get('macro_risk', 'medium')).lower()
    headline    = str(state.get('headline_risk', 'medium')).lower()
    event_phase = str(state.get('event_phase', '')).upper()
    nq_pct      = pct_float('NQ')
    vix_pct     = pct_float('VIX')
    nq_pts      = safe_float(sig.get('nq_points', 0))
    sig_label   = str(sig.get('label', '')).upper()

    if event_phase in ('LIVE', 'IMMINENT', 'APPROACHING') or macro == 'high':
        regime = 'EVENT_DRIVEN'
    elif (vix_pct is not None and vix_pct >= 4.0) or (nq_pct is not None and nq_pct <= -0.75) or headline == 'high':
        regime = 'RISK_OFF'
    elif ('MAJOR' in sig_label or 'NOTABLE' in sig_label) and macro == 'low' and bias_score >= 65:
        regime = 'TRENDING'
    elif nq_pts < 80 and macro != 'high' and headline != 'high':
        regime = 'RANGING'
    else:
        regime = 'CONSOLIDATING'

    regime_props = {
        'TRENDING':      {'regime_color': 'green',  'regime_confidence': 82, 'harvey_mode': 'AGGRESSIVE', 'bias_threshold': 60},
        'RANGING':       {'regime_color': 'blue',   'regime_confidence': 68, 'harvey_mode': 'STANDARD',   'bias_threshold': 70},
        'EVENT_DRIVEN':  {'regime_color': 'yellow', 'regime_confidence': 85, 'harvey_mode': 'DEFENSIVE',  'bias_threshold': 80},
        'RISK_OFF':      {'regime_color': 'red',    'regime_confidence': 78, 'harvey_mode': 'DEFENSIVE',  'bias_threshold': 75},
        'CONSOLIDATING': {'regime_color': 'muted',  'regime_confidence': 55, 'harvey_mode': 'STANDARD',   'bias_threshold': 68},
    }
    props = regime_props[regime]

    if regime == 'TRENDING':
        sig_word = sig_label.split()[0].capitalize()
        regime_summary = f"NQ session is {sig_word} with macro risk low and bias confirmed — trend conditions are real."
    elif regime == 'RANGING':
        regime_summary = f"NQ has moved only {int(nq_pts)} points this session — balanced conditions with no clear directional edge."
    elif regime == 'EVENT_DRIVEN':
        next_ev = state.get('next_event', 'macro event')
        regime_summary = f"Event timing is the dominant force ({next_ev}) — price action is reactive, not structural."
    elif regime == 'RISK_OFF':
        if vix_pct is not None and vix_pct >= 4.0:
            regime_summary = f"VIX is expanding ({vix_pct:+.1f}%) — defensive conditions suppress conviction across the tape."
        elif nq_pct is not None and nq_pct <= -0.75:
            regime_summary = f"NQ is down {nq_pct:.1f}% — downside pressure marks this as a risk-off environment."
        else:
            regime_summary = "Headline risk is elevated — sentiment is fragile and reactive to news flow."
    else:
        regime_summary = "Conditions are mixed with no dominant regime — wait for one force to take control."

    return {
        'regime':            regime,
        'regime_color':      props['regime_color'],
        'regime_confidence': props['regime_confidence'],
        'regime_summary':    regime_summary,
        'harvey_mode':       props['harvey_mode'],
        'bias_threshold':    props['bias_threshold'],
    }


def build_harvey_payload(risk=None):
    state   = risk or load_risk_state()
    sig     = build_session_significance(state)
    driver  = build_market_driver_engine(state)
    morning = build_morning_edge(state)
    wm      = build_what_matters_now(state)
    pulse   = get_live_futures_macro_pulse()
    alerts  = load_alert_history()

    pulse_map = {r['symbol']: r for r in pulse}

    def pct_float(sym):
        raw = str(pulse_map.get(sym, {}).get('pct', '')).replace('%', '').replace('+', '').strip()
        try:
            return float(raw)
        except Exception:
            return None

    nq_pct  = pct_float('NQ')
    es_pct  = pct_float('ES')
    vix_pct = pct_float('VIX')
    nq_last = pulse_map.get('NQ', {}).get('last', '-')
    es_last = pulse_map.get('ES', {}).get('last', '-')

    # ── Bias score ───────────────────────────────────────────────
    bias_score     = 50
    bias_direction = 'NEUTRAL'
    sig_label      = str(sig.get('label', '')).upper()
    nq_pts         = safe_float(sig.get('nq_points', 0))

    if 'MAJOR' in sig_label:        bias_score += 20
    elif 'NOTABLE' in sig_label:    bias_score += 12
    elif 'ACTIVE' in sig_label:     bias_score += 6

    if nq_pct is not None:
        if nq_pct >= 1.5:    bias_score += 18
        elif nq_pct >= 0.75: bias_score += 10
        elif nq_pct >= 0.3:  bias_score += 5
        elif nq_pct <= -1.5: bias_score -= 18
        elif nq_pct <= -0.75:bias_score -= 10
        elif nq_pct <= -0.3: bias_score -= 5

    if es_pct is not None:
        if es_pct >= 0.5:    bias_score += 6
        elif es_pct <= -0.5: bias_score -= 6

    macro = str(state.get('macro_risk', 'medium')).lower()
    if macro == 'high':     bias_score -= 15
    elif macro == 'medium': bias_score -= 5

    if vix_pct is not None and vix_pct >= 4:
        bias_score -= 12

    bias_score = max(0, min(100, bias_score))

    if bias_score >= 72:   bias_direction = 'LONG'
    elif bias_score >= 58: bias_direction = 'LEAN LONG'
    elif bias_score >= 42: bias_direction = 'NEUTRAL'
    elif bias_score >= 28: bias_direction = 'LEAN SHORT'
    else:                  bias_direction = 'SHORT'

    # ── Regime ───────────────────────────────────────────────────
    regime_data    = build_regime_engine(state, sig, pulse, bias_score)
    regime         = regime_data['regime']
    harvey_mode    = regime_data['harvey_mode']
    bias_threshold = regime_data['bias_threshold']
    sell_threshold = 100 - bias_threshold

    # ── ORB status ───────────────────────────────────────────────
    session        = str(state.get('donna_session', '')).upper()
    now_ny_obj     = now_ny()
    market_open_mins = (now_ny_obj.hour * 60 + now_ny_obj.minute) - (9 * 60 + 30)

    if session != 'NEW_YORK_CASH':
        orb_status, orb_note, orb_quality = 'PRE-MARKET', 'Cash session not open. ORB forms at 9:30 ET open.', 'PENDING'
    elif market_open_mins < 0:
        orb_status, orb_note, orb_quality = 'PRE-MARKET', 'Waiting for 9:30 ET open.', 'PENDING'
    elif market_open_mins <= 5:
        orb_status  = 'FORMING'
        orb_note    = f'ORB forming — {5 - market_open_mins} min remaining in opening range.'
        orb_quality = 'WAIT'
    elif market_open_mins <= 15:
        orb_status, orb_note, orb_quality = 'SET', 'ORB is set. Watch for breakout or breakdown confirmation.', 'WATCH'
    else:
        if nq_pct is not None and abs(nq_pct) >= 0.5:
            direction  = 'BULLISH BREAK' if nq_pct > 0 else 'BEARISH BREAK'
            orb_status  = direction
            orb_note    = f'NQ has broken {"above" if nq_pct > 0 else "below"} the opening range. Look for continuation or failure.'
            orb_quality = 'ACTIVE'
        else:
            orb_status, orb_note, orb_quality = 'RANGING', 'NQ is ranging inside or near ORB bounds. Wait for a clean break.', 'WAIT'

    # ── Verdict ──────────────────────────────────────────────────
    event_phase = str(state.get('event_phase', '')).upper()
    if event_phase in ('LIVE', 'IMMINENT'):
        verdict       = 'WAIT'
        next_ev       = state.get('next_event', 'macro event')
        mins          = state.get('minutes_to_event')
        timing        = 'is live now' if (mins is not None and int(mins) <= 0) else f'in {mins} min' if mins is not None else 'is imminent'
        verdict_reason = f"{next_ev} {timing}. Do not trade into the release — wait for the initial reaction to resolve before reading direction."
        verdict_color  = 'yellow'
    elif regime == 'EVENT_DRIVEN' and bias_score < 85:
        verdict        = 'WAIT'
        verdict_reason = (f'Regime: EVENT_DRIVEN [{harvey_mode}]. Bias {bias_score}/100 — this regime requires 85+ for a signal. '
                          f'Respect event timing over conviction.')
        verdict_color  = 'yellow'
    elif bias_score >= bias_threshold and orb_quality in ('ACTIVE', 'WATCH'):
        verdict        = 'BUY'
        verdict_reason = (f'Bias {bias_score}/100 LONG [{harvey_mode} | {regime}]. '
                          f'{sig.get("summary", "Session supports momentum.")} Confirm with leadership.')
        verdict_color  = 'green'
    elif bias_score <= sell_threshold and orb_quality in ('ACTIVE', 'WATCH'):
        verdict        = 'SELL'
        verdict_reason = (f'Bias {bias_score}/100 SHORT [{harvey_mode} | {regime}]. '
                          f'Downside pressure confirmed. Respect breakdown until proven otherwise.')
        verdict_color  = 'red'
    elif orb_quality in ('FORMING', 'PENDING'):
        verdict        = 'WAIT'
        verdict_reason = 'ORB not yet set. No clean entries until the opening range is established.'
        verdict_color  = 'yellow'
    elif orb_quality == 'WAIT' and orb_status == 'RANGING':
        verdict = 'WAIT'
        try:
            nq_lvl     = float(str(nq_last).replace(',', ''))
            break_up   = f'{nq_lvl * 1.005:,.2f}'
            break_dn   = f'{nq_lvl * 0.995:,.2f}'
            verdict_reason = (f'NQ is ranging near {nq_last} with no directional break. '
                              f'A sustained move above {break_up} opens the long; below {break_dn} confirms the short. '
                              f'Stay out until price commits.')
        except Exception:
            verdict_reason = f'NQ is ranging near {nq_last} inside the opening range. Wait for a clean directional break before entering.'
        verdict_color  = 'yellow'
    else:
        verdict        = 'WAIT'
        needed         = bias_threshold - bias_score
        verdict_reason = (f'Bias is {bias_score}/100 — {needed} points short of a BUY signal '
                          f'(threshold: {bias_threshold} in {regime} regime [{harvey_mode}]). '
                          f'No dominant directional edge yet. Wait for momentum to build before committing size.')
        verdict_color  = 'yellow'

    # ── Key levels ───────────────────────────────────────────────
    snap     = state.get('market_snapshot', {})
    nq_price = safe_float(snap.get('NQ', {}).get('last', 0))
    es_price = safe_float(snap.get('ES', {}).get('last', 0))

    def fib_levels(price, pct_range=0.02):
        if not price:
            return {}
        swing = price * pct_range
        high  = price + swing
        low   = price - swing
        return {
            'high':    round(high, 2),
            'fib_786': round(high - swing * 0.214, 2),
            'fib_618': round(high - swing * 0.382, 2),
            'fib_500': round(high - swing * 0.500, 2),
            'fib_382': round(high - swing * 0.618, 2),
            'fib_236': round(high - swing * 0.764, 2),
            'low':     round(low, 2),
        }

    nq_fibs = fib_levels(nq_price) if nq_price else {}
    es_fibs  = fib_levels(es_price) if es_price else {}

    nq_levels = build_price_levels('NQ=F', session, market_open_mins)
    es_levels = build_price_levels('ES=F', session, market_open_mins)

    # ── Divergence ───────────────────────────────────────────────
    divergence = None
    if nq_pct is not None and es_pct is not None:
        diff = abs(nq_pct - es_pct)
        if diff >= 0.8:
            stronger  = 'NQ' if nq_pct > es_pct else 'ES'
            weaker    = 'ES' if stronger == 'NQ' else 'NQ'
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

    # ── Risk engine layer ────────────────────────────────────────
    trades      = load_journal()
    re_state    = load_re_state()
    risk_engine = build_risk_engine_payload(
        trades       = trades,
        account_size = float(re_state.get('account_size', 25000)),
        risk_pct     = float(re_state.get('risk_pct', 1.0)),
    )

    if risk_engine.get('stop_trading'):
        verdict        = 'STOP'
        verdict_reason = f"RISK ENGINE: {risk_engine.get('stop_reason', 'Session trading limit reached.')} — No new positions until flag is cleared."
        verdict_color  = 'red'

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
        'nq_levels':            nq_levels,
        'es_levels':            es_levels,
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
        'regime':               regime_data,
        'risk_engine':          risk_engine,
        'cross_asset_intelligence': build_cross_asset_intelligence(),
    }


def build_market_movers_engine():
    return {
        'leaders': [
            {'ticker': 'NVDA', 'company': 'NVIDIA',    'impact': 'Very High', 'index_exposure': 'NQ / QQQ / SPX', 'catalyst': 'AI leadership',       'why_it_matters': 'Can drag the entire Nasdaq complex.'},
            {'ticker': 'MSFT', 'company': 'Microsoft', 'impact': 'Very High', 'index_exposure': 'NQ / SPX',       'catalyst': 'Cloud + AI',            'why_it_matters': 'Massive index weight and broad influence.'},
            {'ticker': 'AMZN', 'company': 'Amazon',    'impact': 'High',      'index_exposure': 'NQ / SPX',       'catalyst': 'Consumer + cloud',      'why_it_matters': 'Broad market sentiment and cloud read-through.'},
        ],
        'threats': [
            {'ticker': 'TSLA', 'company': 'Tesla',     'impact': 'High',   'index_exposure': 'NQ / QQQ',   'catalyst': 'High-beta sentiment', 'why_it_matters': 'Can distort Nasdaq mood and momentum fast.'},
            {'ticker': 'JPM',  'company': 'JPMorgan',  'impact': 'Medium', 'index_exposure': 'SPX / DJIA', 'catalyst': 'Financial tone',      'why_it_matters': 'Can confirm or deny broad risk appetite.'},
        ],
        'next_to_watch': [
            {'ticker': 'AMD',  'company': 'AMD',   'impact': 'High',      'index_exposure': 'NQ',       'catalyst': 'Semi sympathy',   'why_it_matters': 'Important read on semiconductor breadth.'},
            {'ticker': 'AAPL', 'company': 'Apple', 'impact': 'Very High', 'index_exposure': 'NQ / SPX', 'catalyst': 'Mega-cap weight', 'why_it_matters': 'Huge index footprint and sentiment influence.'},
        ],
    }


def build_donna_observations(risk=None):
    state  = risk or load_risk_state()
    pulse  = get_live_futures_macro_pulse()
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
    nq_pct    = pct('NQ')
    es_pct    = pct('ES')
    oil_pct   = pct('OIL')
    gold_pct  = pct('GOLD')
    silver_pct = pct('SILVER')
    dxy_pct   = pct('DXY')
    us10y_pct = pct('US10Y')
    vix_pct   = pct('VIX')

    if oil_pct is not None and abs(oil_pct) >= 2.0:
        direction = 'surging' if oil_pct > 0 else 'breaking lower'
        observations.append({'type': 'observation', 'title': f'OIL {direction}', 'summary': 'Crude is moving enough to affect cross-asset tone. Watch index futures, dollar, and rates response.', 'priority': 'high', 'timestamp': utc_now_iso()})

    if nq_pct is not None and nq_pct >= 0.75:
        observations.append({'type': 'observation', 'title': 'Nasdaq strength remains meaningful', 'summary': 'NQ is still showing enough upside pressure to matter. Respect leadership until it fails.', 'priority': 'high', 'timestamp': utc_now_iso()})
    elif nq_pct is not None and nq_pct <= -0.75:
        observations.append({'type': 'observation', 'title': 'Nasdaq pressure is real', 'summary': 'NQ downside is strong enough to matter. Be careful forcing longs without confirmation.', 'priority': 'high', 'timestamp': utc_now_iso()})

    if es_pct is not None and abs(es_pct) >= 0.60:
        direction = 'confirming upside participation' if es_pct > 0 else 'confirming downside pressure'
        observations.append({'type': 'observation', 'title': f'ES is {direction}', 'summary': 'Broad index participation is strong enough to validate the current tape.', 'priority': 'medium', 'timestamp': utc_now_iso()})

    if gold_pct is not None and abs(gold_pct) >= 1.0:
        direction = 'strength' if gold_pct > 0 else 'weakness'
        observations.append({'type': 'observation', 'title': f'Gold {direction} is notable', 'summary': 'Metals are moving enough to matter for macro tone and cross-asset interpretation.', 'priority': 'medium', 'timestamp': utc_now_iso()})

    if silver_pct is not None and abs(silver_pct) >= 2.0:
        direction = 'strength' if silver_pct > 0 else 'weakness'
        observations.append({'type': 'observation', 'title': f'Silver {direction} is expanding', 'summary': 'Silver volatility is elevated. Respect the move as more than background noise.', 'priority': 'medium', 'timestamp': utc_now_iso()})

    if dxy_pct is not None and abs(dxy_pct) >= 0.40:
        direction = 'rising' if dxy_pct > 0 else 'falling'
        observations.append({'type': 'observation', 'title': f'DXY is {direction}', 'summary': 'Dollar movement is becoming important enough to influence equities and metals.', 'priority': 'medium', 'timestamp': utc_now_iso()})

    if us10y_pct is not None and abs(us10y_pct) >= 1.0:
        direction = 'rising' if us10y_pct > 0 else 'falling'
        observations.append({'type': 'observation', 'title': f'US10Y is {direction}', 'summary': 'Rates are moving enough to affect risk appetite and valuation-sensitive assets.', 'priority': 'medium', 'timestamp': utc_now_iso()})

    if vix_pct is not None and vix_pct >= 4.0:
        observations.append({'type': 'observation', 'title': 'Volatility is expanding', 'summary': 'VIX is pressing higher. Expect more fragile conviction and sharper reactions.', 'priority': 'high', 'timestamp': utc_now_iso()})

    if str(state.get('event_phase', '')).upper() in {'LIVE', 'IMMINENT', 'APPROACHING'}:
        observations.append({'type': 'observation', 'title': f"Macro timing matters: {state.get('next_event', 'Scheduled event')}", 'summary': 'Event risk is close enough that price action may not be clean. Respect timing over impulse.', 'priority': 'high', 'timestamp': utc_now_iso()})

    if not observations:
        observations.append({'type': 'observation', 'title': driver.get('dominant_driver', 'Balanced conditions'), 'summary': morning.get('first_read', 'Donna does not see a dominant threat beyond normal market rotation.'), 'priority': 'low', 'timestamp': utc_now_iso()})

    return observations[:6]


def build_session_playbook(risk=None):
    state    = risk or load_risk_state()
    session  = str(state.get('donna_session', 'OFF_HOURS'))
    macro    = str(state.get('macro_risk', 'medium')).lower()
    headline = str(state.get('headline_risk', 'medium')).lower()
    driver   = build_market_driver_engine(state)
    morning  = build_morning_edge(state)
    events_data = load_macro_events()

    session_map = {
        'NEW_YORK_CASH': 'NY Cash (9:30–4:00 ET)',
        'LONDON': 'London Open (3:00–9:30 ET)',
        'ASIA': 'Asia Session (7:00 PM–3:00 ET)',
        'OFF_HOURS': 'Off Hours',
    }
    session_type = session_map.get(session, session.replace('_', ' '))
    dominant     = driver.get('dominant_driver', 'Balanced')
    today_events = [f"{e.get('time_et', '?')} ET — {e.get('title', '')}" for e in (events_data.get('events') or [])[:3]]

    event_phase = str(state.get('event_phase', '')).upper()
    if macro == 'high' and event_phase in ('LIVE', 'IMMINENT', 'APPROACHING'):
        tactical = f"Event risk is active ({state.get('next_event', 'macro event')}). Reduce size and wait for clean post-event price action."
    elif macro == 'high':
        tactical = "Macro risk is elevated. Let the market show direction before committing to positions."
    elif headline == 'high':
        tactical = "Headline sensitivity is high. Avoid aggressive entries without confirmation from leadership."
    elif session == 'NEW_YORK_CASH':
        tactical = morning.get('first_read', 'Trade what the tape shows. Respect leadership and avoid forcing setups.')
    elif session == 'LONDON':
        tactical = "London open — respect early momentum, but wait for NY confirmation before adding size."
    elif session == 'ASIA':
        tactical = "Asia session — lower reliability for NQ signals. Use for context, not conviction trades."
    else:
        tactical = morning.get('first_read', 'No active session. Review plan, set alerts, and prepare for next open.')

    return {
        'session_type':   session_type,
        'dominant_driver': dominant,
        'key_events':     today_events,
        'tactical_note':  tactical,
    }


def build_scenario_engine(force: bool = False) -> dict:
    """Generate 3-5 if/then playbook scenarios via Claude. Cached 30 min."""
    cache_key = 'scenario_engine'
    if not force:
        cached = cache_get(cache_key)
        if cached:
            return cached

    risk         = load_risk_state()
    sig          = build_session_significance(risk)
    regime_data  = build_regime_engine(risk, sig)
    macro_events = load_macro_events()
    pulse        = get_live_futures_macro_pulse()
    snap         = risk.get('market_snapshot', {})

    pulse_map = {r['symbol']: r for r in pulse}

    def pulse_line(sym):
        r = pulse_map.get(sym, {})
        return f"{sym}: {r.get('last', '-')} ({r.get('pct', '-')})"

    events_text = '\n'.join(
        f"  {e.get('time_et', '?')} ET — {e.get('title', '')} [{e.get('importance', '').upper()}]"
        for e in macro_events.get('events', [])
    ) or '  None scheduled'

    nq_last = snap.get('NQ', {}).get('last', 0)
    es_last = snap.get('ES', {}).get('last', 0)

    context = (
        f"Date: {now_ny().strftime('%A, %B %-d, %Y')}\n"
        f"Session: {risk.get('donna_session', '—')}\n"
        f"Regime: {regime_data.get('regime', '—')} | HARVEY Mode: {regime_data.get('harvey_mode', '—')}\n"
        f"Macro Risk: {risk.get('macro_risk', 'medium').upper()} | Event Phase: {risk.get('event_phase', '—').upper()}\n"
        f"Next Event: {risk.get('next_event', 'none')}\n\n"
        f"Today's macro calendar:\n{events_text}\n\n"
        f"Live futures & macro pulse:\n"
        f"  {pulse_line('NQ')}\n  {pulse_line('ES')}\n  {pulse_line('OIL')}\n"
        f"  {pulse_line('GOLD')}\n  {pulse_line('DXY')}\n  {pulse_line('VIX')}\n  {pulse_line('US10Y')}\n\n"
        f"NQ price reference: {nq_last}\n"
        f"ES price reference: {es_last}\n"
        f"Session significance: {sig.get('label', '—')} — NQ ~{int(sig.get('nq_points', 0))} pts\n"
        f"Last headline: {risk.get('last_headline', '')}\n"
        f"Dominant driver: {risk.get('donna_session', '')}, macro={risk.get('macro_risk', '')}"
    )

    system = (
        "You are DONNA's scenario planning engine. Generate exactly 3 to 5 if/then playbook scenarios "
        "for today's trading session based on the context provided. "
        "Return ONLY valid JSON — an array of scenario objects, nothing else. "
        "Each object must have exactly these string keys: "
        "trigger, expected_reaction, key_levels, watch_for, confidence. "
        "confidence must be one of: HIGH, MEDIUM, LOW. "
        "Be specific with price levels (use the NQ/ES reference prices to anchor levels). "
        "Scenarios should cover: upside break, downside break, event-reaction, and range/consolidation cases. "
        "key_levels should be a short slash-separated string like '19,380 / 19,450 / 19,520'. "
        "Keep each field concise — one sentence max. No markdown, no extra keys."
    )

    nq_base = int(safe_float(nq_last, 19000))
    fallback_scenarios = [
        {'trigger': f'If NQ breaks and holds above {nq_base + 100:,}', 'expected_reaction': 'Continuation toward next resistance. Leadership names accelerate.', 'key_levels': f'{nq_base:,} / {nq_base + 100:,} / {nq_base + 200:,}', 'watch_for': 'NVDA and MSFT confirmation above their intraday highs.', 'confidence': 'MEDIUM'},
        {'trigger': f'If NQ loses {nq_base - 100:,} and fails to reclaim', 'expected_reaction': 'Pressure toward lower support. Risk-off tone accelerates.', 'key_levels': f'{nq_base - 100:,} / {nq_base - 200:,} / {nq_base - 300:,}', 'watch_for': 'VIX expansion above 20 and DXY strength confirming the move.', 'confidence': 'MEDIUM'},
        {'trigger': f'If macro event ({risk.get("next_event", "scheduled event")}) surprises to the upside', 'expected_reaction': 'Sharp initial spike. Wait for first 5-minute reaction to resolve before entering.', 'key_levels': f'{nq_base:,} / {nq_base + 150:,}', 'watch_for': 'Whether ES confirms the NQ move within 2 minutes of the print.', 'confidence': 'LOW'},
    ]

    if not client:
        result = {'scenarios': fallback_scenarios, 'generated_at': utc_now_iso(), 'source': 'fallback'}
        cache_set(cache_key, result, 1800)
        return result

    try:
        resp = client.messages.create(
            model=ANTHROPIC_ASSISTANT_MODEL,
            system=system,
            messages=[{'role': 'user', 'content': f'Generate scenarios for today:\n\n{context}'}],
            max_tokens=1200,
        )
        raw = resp.content[0].text.strip() if resp.content else '[]'
        raw = re.sub(r'^```(?:json)?\s*', '', raw, flags=re.MULTILINE)
        raw = re.sub(r'\s*```$', '', raw, flags=re.MULTILINE)
        scenarios = json.loads(raw)
        if not isinstance(scenarios, list):
            raise ValueError('Not a list')
        clean = []
        for s in scenarios[:5]:
            conf = str(s.get('confidence', 'MEDIUM')).upper()
            if conf not in ('HIGH', 'MEDIUM', 'LOW'):
                conf = 'MEDIUM'
            clean.append({
                'trigger':           str(s.get('trigger', '—')),
                'expected_reaction': str(s.get('expected_reaction', '—')),
                'key_levels':        str(s.get('key_levels', '—')),
                'watch_for':         str(s.get('watch_for', '—')),
                'confidence':        conf,
            })
        result = {'scenarios': clean or fallback_scenarios, 'generated_at': utc_now_iso(), 'source': 'claude'}
    except Exception as e:
        print(f'Scenario engine error: {e}')
        result = {'scenarios': fallback_scenarios, 'generated_at': utc_now_iso(), 'source': 'fallback'}

    cache_set(cache_key, result, 1800)
    return result


def build_performance_memory() -> dict:
    """Compute deep performance stats. Claude insight cached 1 hour by trade count."""
    trades = load_journal()
    total  = len(trades)

    empty = {
        'total': 0, 'wins': 0, 'losses': 0, 'breakevens': 0,
        'win_rate': 0.0, 'profit_factor': 0.0, 'avg_win': 0.0,
        'avg_loss': 0.0, 'avg_rr': 0.0,
        'by_regime': {}, 'by_session': {}, 'by_setup': {},
        'best_regime': '—', 'worst_regime': '—', 'best_session': '—', 'best_setup': '—',
        'streak': {'type': 'NONE', 'count': 0},
        'insight': '', 'insufficient_data': True,
    }
    if total == 0:
        return empty

    wins, losses, breakevens = 0, 0, 0
    win_pnl, loss_pnl = [], []
    regime_buckets: dict = {}
    session_buckets: dict = {}
    setup_buckets: dict = {}

    for t in trades:
        outcome   = str(t.get('outcome', '')).upper()
        direction = str(t.get('direction', 'LONG')).upper()
        try:
            entry = float(t.get('entry_price', 0))
            exit_ = float(t.get('exit_price', 0))
            size  = float(t.get('size', 1))
        except Exception:
            entry, exit_, size = 0.0, 0.0, 1.0

        pnl = (exit_ - entry) * size if direction == 'LONG' else (entry - exit_) * size

        if outcome == 'WIN':
            wins += 1
            win_pnl.append(abs(pnl))
        elif outcome == 'LOSS':
            losses += 1
            loss_pnl.append(abs(pnl))
        else:
            breakevens += 1

        regime  = str(t.get('active_regime', 'UNKNOWN'))
        session = str(t.get('session', 'UNKNOWN'))
        setup   = str(t.get('setup_type', '') or 'UNKNOWN').strip() or 'UNKNOWN'

        for bucket, key in [(regime_buckets, regime), (session_buckets, session), (setup_buckets, setup)]:
            if key not in bucket:
                bucket[key] = {'wins': 0, 'losses': 0, 'breakevens': 0}
            if outcome == 'WIN':     bucket[key]['wins'] += 1
            elif outcome == 'LOSS':  bucket[key]['losses'] += 1
            else:                    bucket[key]['breakevens'] += 1

    win_rate      = round(wins / total * 100, 1) if total else 0.0
    avg_win       = round(sum(win_pnl) / len(win_pnl), 2) if win_pnl else 0.0
    avg_loss      = round(sum(loss_pnl) / len(loss_pnl), 2) if loss_pnl else 0.0
    profit_factor = round(sum(win_pnl) / sum(loss_pnl), 2) if loss_pnl and sum(loss_pnl) > 0 else 0.0
    avg_rr        = round(avg_win / avg_loss, 2) if avg_loss else 0.0

    def enrich(buckets):
        result = {}
        for k, v in buckets.items():
            t_ = v['wins'] + v['losses'] + v['breakevens']
            result[k] = {**v, 'total': t_, 'win_rate': round(v['wins'] / t_ * 100, 1) if t_ else 0.0}
        return result

    by_regime  = enrich(regime_buckets)
    by_session = enrich(session_buckets)
    by_setup   = enrich(setup_buckets)

    best_regime  = max(by_regime,  key=lambda k: (by_regime[k]['win_rate'],  by_regime[k]['total']),  default='—') if by_regime  else '—'
    worst_regime = min(by_regime,  key=lambda k: by_regime[k]['win_rate'],   default='—') if by_regime  else '—'
    best_session = max(by_session, key=lambda k: (by_session[k]['win_rate'], by_session[k]['total']), default='—') if by_session else '—'
    best_setup   = max(by_setup,   key=lambda k: (by_setup[k]['win_rate'],   by_setup[k]['total']),   default='—') if by_setup   else '—'

    streak_type: str | None = None
    streak_count = 0
    for t in reversed(trades):
        o = str(t.get('outcome', '')).upper()
        if o == 'BREAKEVEN':
            continue
        if streak_type is None:
            streak_type = o; streak_count = 1
        elif o == streak_type:
            streak_count += 1
        else:
            break
    streak = {'type': streak_type or 'NONE', 'count': streak_count}

    insight = ''
    if total >= 5 and client:
        insight_key = f'perf_insight::{total}'
        insight = cache_get(insight_key) or ''
        if not insight:
            try:
                regime_lines  = ', '.join(f'{k} {v["win_rate"]}% ({v["total"]}t)' for k, v in sorted(by_regime.items(),  key=lambda x: -x[1]['win_rate']))
                session_lines = ', '.join(f'{k} {v["win_rate"]}%'                 for k, v in sorted(by_session.items(), key=lambda x: -x[1]['win_rate']))
                setup_lines   = ', '.join(f'{k} {v["win_rate"]}%'                 for k, v in sorted(by_setup.items(),   key=lambda x: -x[1]['win_rate'])[:5]) or '—'
                context = (f"{total} trades, {win_rate}% win rate, {profit_factor}x profit factor, "
                           f"{avg_rr} avg RR. Regime: {regime_lines}. Session: {session_lines}. "
                           f"Setup: {setup_lines}. Streak: {streak_count} {streak_type}.")
                resp = client.messages.create(
                    model=ANTHROPIC_MODEL,
                    system=("You are DONNA's edge analyst. Given a trader's performance stats, "
                            "write exactly ONE sentence (under 30 words) identifying their clearest "
                            "statistical edge. Be specific, direct, and data-driven. No markdown."),
                    messages=[{'role': 'user', 'content': context}],
                    max_tokens=80,
                )
                insight = resp.content[0].text.strip() if resp.content else ''
                if insight:
                    cache_set(insight_key, insight, 3600)
            except Exception as e:
                print(f'Performance insight error: {e}')

    return {
        'total': total, 'wins': wins, 'losses': losses, 'breakevens': breakevens,
        'win_rate': win_rate, 'profit_factor': profit_factor,
        'avg_win': avg_win, 'avg_loss': avg_loss, 'avg_rr': avg_rr,
        'by_regime': by_regime, 'by_session': by_session, 'by_setup': by_setup,
        'best_regime': best_regime, 'worst_regime': worst_regime,
        'best_session': best_session, 'best_setup': best_setup,
        'streak': streak, 'insight': insight,
        'insufficient_data': total < 3,
    }


def build_cross_asset_intelligence() -> dict:
    """Detect when major asset classes are sending conflicting signals."""
    pulse     = get_live_futures_macro_pulse()
    pulse_map = {r['symbol']: r for r in pulse}

    def pf(sym):
        raw = str(pulse_map.get(sym, {}).get('pct', '')).replace('%', '').replace('+', '').strip()
        try:
            return float(raw)
        except Exception:
            return None

    nq_pct    = pf('NQ')
    es_pct    = pf('ES')
    gold_pct  = pf('GOLD')
    oil_pct   = pf('OIL')
    dxy_pct   = pf('DXY')
    vix_pct   = pf('VIX')

    divergences = []

    # 1. Equity / Gold both bid — risk-on and safe haven simultaneously
    if nq_pct is not None and gold_pct is not None:
        if nq_pct >= 0.5 and gold_pct >= 0.8:
            sev = 'HIGH' if (nq_pct >= 1.0 and gold_pct >= 1.2) else 'MEDIUM'
            divergences.append({
                'name':          'Equity / Gold Both Bid',
                'severity':      sev,
                'what_it_means': 'Risk-on and safe haven are simultaneously in demand — the market is sending conflicting signals about risk appetite.',
                'watch_for':     'Which breaks first: Gold fading confirms pure risk-on; equity selling confirms the defensive bid wins.',
            })

    # 2. Equity up / VIX also rising — protection bought into strength
    if nq_pct is not None and vix_pct is not None:
        if nq_pct >= 0.5 and vix_pct >= 3.0:
            sev = 'HIGH' if vix_pct >= 5.0 else 'MEDIUM'
            divergences.append({
                'name':          'Equity Up / VIX Bid',
                'severity':      sev,
                'what_it_means': 'Someone is buying protection into equity strength — the options market does not trust this rally.',
                'watch_for':     'If VIX holds elevated while equities push higher, treat the move with skepticism. Snap-back risk is elevated.',
            })

    # 3. DXY surging while equities also rising — dollar headwind being ignored
    if dxy_pct is not None and nq_pct is not None:
        if dxy_pct >= 0.4 and nq_pct >= 0.5:
            sev = 'HIGH' if dxy_pct >= 0.7 else 'MEDIUM'
            divergences.append({
                'name':          'Dollar Strength / Equity Bid',
                'severity':      sev,
                'what_it_means': 'A rising dollar is typically a headwind for equities — both rising together is unusual and tends to resolve quickly.',
                'watch_for':     'Whether DXY holds after the catalyst resolves. Fading dollar would confirm the equity move is clean.',
            })

    # 4. Oil breaking down while equities rally — deflation / demand concern
    if oil_pct is not None and nq_pct is not None:
        if oil_pct <= -2.0 and nq_pct >= 0.5:
            sev = 'HIGH' if oil_pct <= -3.0 else 'MEDIUM'
            divergences.append({
                'name':          'Oil Breakdown / Equity Strength',
                'severity':      sev,
                'what_it_means': 'Crude crashing while equities rally can signal deflation or demand destruction — equity strength may be narrow.',
                'watch_for':     'Energy sector stocks (XLE). If they are also down hard, the equity strength is likely concentrated in tech only.',
            })

    # 5. NQ / ES spread above 1% — tech massively leading or lagging
    if nq_pct is not None and es_pct is not None:
        spread = abs(nq_pct - es_pct)
        if spread >= 1.0:
            leader = 'NQ' if nq_pct > es_pct else 'ES'
            lagger = 'ES' if leader == 'NQ' else 'NQ'
            sev    = 'HIGH' if spread >= 1.5 else 'MEDIUM'
            divergences.append({
                'name':          f'{leader} / {lagger} Spread ({spread:.1f}%)',
                'severity':      sev,
                'what_it_means': f'{leader} is significantly outperforming {lagger} — breadth is narrow and leadership is concentrated.',
                'watch_for':     f'Whether {lagger} catches up (confirming the move) or {leader} reverts (signaling exhaustion).',
            })

    # Overall mode
    if not divergences:
        mode = 'ALIGNED'
    else:
        high_count = sum(1 for d in divergences if d['severity'] == 'HIGH')
        if len(divergences) >= 3 or high_count >= 2:
            mode = 'WARNING'
        elif high_count == 1 or len(divergences) == 2:
            mode = 'DIVERGING'
        else:
            mode = 'MIXED'

    return {
        'cross_asset_mode': mode,
        'divergences':      divergences,
        'pulse_snapshot':   {s: pf(s) for s in ('NQ', 'ES', 'GOLD', 'OIL', 'DXY', 'US10Y', 'VIX')},
    }


def build_dashboard_payload():
    risk          = load_risk_state()
    driver        = build_market_driver_engine(risk)
    morning       = build_morning_edge(risk)
    significance  = build_session_significance(risk)
    what_matters  = build_what_matters_now(risk)
    observations  = build_donna_observations(risk)
    regime        = build_regime_engine(risk, significance)
    session_playbook = build_session_playbook(risk)
    movers        = build_market_movers_engine()
    alerts        = load_alert_history()[:10]
    assistant     = load_assistant_state()
    settings      = load_settings()
    live_market   = get_live_market_data()
    calendar      = get_live_calendar()
    earnings      = get_live_earnings()
    news          = get_live_news()
    live_movers   = get_live_movers()
    futures_macro_pulse = get_live_futures_macro_pulse()
    scenarios     = build_scenario_engine()
    cross_asset   = build_cross_asset_intelligence()
    effective_alerts = alerts if alerts else observations

    live_strip = [
        {'label': 'Macro',       'value': str(risk.get('macro_risk', '-')).upper()},
        {'label': 'Headline',    'value': str(risk.get('headline_risk', '-')).upper()},
        {'label': 'Market',      'value': str(risk.get('market_news_risk', '-')).upper()},
        {'label': 'Driver',      'value': driver['dominant_driver']},
        {'label': 'Threat',      'value': morning['main_threat']},
        {'label': 'Open Quality','value': morning['open_quality']},
        {'label': 'Session',     'value': risk.get('donna_session', session_label())},
        {'label': 'Headline',    'value': risk.get('last_headline', '')},
    ]

    return {
        'status':               'online',
        'risk':                 risk,
        'driver':               driver,
        'morning_edge':         morning,
        'session_significance': significance,
        'what_matters_now':     what_matters,
        'market_movers_engine': movers,
        'alerts':               effective_alerts,
        'raw_trade_alerts':     alerts,
        'observations':         observations,
        'assistant':            assistant,
        'settings':             settings,
        'major_indexes':        live_market['major_indexes'],
        'watchlist':            live_market['watchlist'],
        'live_movers':          live_movers,
        'futures_macro_pulse':  futures_macro_pulse,
        'calendar':             calendar,
        'earnings':             earnings,
        'news':                 news,
        'live_strip':           live_strip,
        'session_playbook':     session_playbook,
        'forex_factory_notes_url': FOREX_FACTORY_NOTES_URL,
        'regime':               regime,
        'scenarios':            scenarios,
        'cross_asset_intelligence': cross_asset,
    }


def generate_morning_brief() -> str:
    """Call Claude to produce a professional morning brief from live DONNA context."""
    if not client:
        return ''
    risk         = load_risk_state()
    sig          = build_session_significance(risk)
    driver       = build_market_driver_engine(risk)
    morning      = build_morning_edge(risk)
    macro_events = load_macro_events()
    pulse        = get_live_futures_macro_pulse()

    pulse_lines = []
    for row in pulse:
        sym  = row.get('symbol', '')
        last = row.get('last', '-')
        pct  = row.get('pct', '-')
        if sym in ('NQ', 'ES', 'OIL', 'GOLD', 'DXY', 'VIX', 'US10Y'):
            pulse_lines.append(f"  {sym}: {last}  ({pct}%)")
    pulse_text = '\n'.join(pulse_lines) or '  (no live data)'

    events      = macro_events.get('events', [])
    events_text = '\n'.join(f"  {e.get('time_et', '?')} ET — {e.get('title', '')} [{e.get('importance', '').upper()}]" for e in events) or '  None scheduled'

    today    = now_ny()
    date_str = today.strftime('%A, %B %-d, %Y')
    snap     = risk.get('market_snapshot', {})

    context = (
        f"Date: {date_str}\n"
        f"Overnight / pre-market snapshot:\n{pulse_text}\n\n"
        f"Today's macro events:\n{events_text}\n\n"
        f"Risk levels:\n"
        f"  Macro: {risk.get('macro_risk', 'medium').upper()}\n"
        f"  Headline: {risk.get('headline_risk', 'medium').upper()}\n"
        f"  Market news: {risk.get('market_news_risk', 'medium').upper()}\n"
        f"  Event phase: {risk.get('event_phase', 'unknown').upper()}\n"
        f"  Next event: {risk.get('next_event', 'none')}\n\n"
        f"Session significance: {sig.get('label', '')} — NQ ~{int(sig.get('nq_points', 0))} pts, ES ~{int(sig.get('es_points', 0))} pts\n"
        f"Dominant driver: {driver.get('dominant_driver', '')}\n"
        f"Market regime: {driver.get('market_regime', '')}\n"
        f"Market summary: {driver.get('market_summary', '')}\n"
        f"Today's bias: {morning.get('today_bias', '')}\n"
        f"First read: {morning.get('first_read', '')}\n"
        f"Watch first: {', '.join(morning.get('watch_first', []))}\n"
        f"Last headline: {risk.get('last_headline', '')}"
    )

    system = (
        "You are DONNA's morning desk analyst. Write a concise pre-market brief for a professional futures trader. "
        "Rules: greet with date and day, summarize overnight moves for NQ/ES and key assets, list today's macro events with times, "
        "state risk levels plainly, name the dominant market driver, list 3-4 instruments to watch first, "
        "end with one sentence of execution guidance. "
        "Tone: direct, factual, professional — like a trading desk morning note, not a chatbot. "
        "Use emojis sparingly (max 5 total). Under 400 words. No bullet-point walls — mix short paragraphs and focused lists."
    )

    resp = client.messages.create(
        model=ANTHROPIC_ASSISTANT_MODEL,
        system=system,
        messages=[{'role': 'user', 'content': f'Generate the morning brief using this context:\n\n{context}'}],
        max_tokens=600,
    )
    return resp.content[0].text.strip() if resp.content else ''


def send_morning_brief() -> dict:
    """Generate and send the morning brief via Telegram."""
    try:
        brief = generate_morning_brief()
        if not brief:
            return {'ok': False, 'error': 'Brief generation returned empty — check client/model config'}
        result = send_telegram_message(brief)
        state  = {'last_sent_date': now_ny().strftime('%Y-%m-%d'), 'last_sent_utc': utc_now_iso()}
        write_json_file(MORNING_BRIEF_FILE, state)
        return {'ok': True, 'telegram': result, 'brief_length': len(brief)}
    except Exception as e:
        return {'ok': False, 'error': str(e)}
