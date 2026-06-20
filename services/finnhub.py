# ============================================================
# donna_finnhub.py — DONNA v5.0 Live Market Snapshot Engine
# Primary data source: yfinance (free, no API key required)
# Finnhub retained only for news endpoint (/api/v1/news)
# Called by finnhub_loop() in main.py every 3 minutes
# ============================================================

from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import json
import os
import time
import requests
import yfinance as yf

from core.state_engine import state as _state

BASE_DIR        = Path(__file__).parent.parent
RISK_STATE_FILE = BASE_DIR / 'data' / 'donna_risk_state.json'
NY_TZ           = ZoneInfo('America/New_York')

# Finnhub key kept solely for the news endpoint
FINNHUB_API_KEY = os.getenv('FINNHUB_API_KEY', '').strip()


def _utc_iso():
    return datetime.now(timezone.utc).isoformat()

def _now_ny():
    return datetime.now(NY_TZ)

def _safe_float(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return default

def _safe_get(url, params=None, timeout=15):
    try:
        r = requests.get(url, params=params, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f'[donna_finnhub] GET {url} failed: {e}')
        return None

def _read_risk():
    try:
        if RISK_STATE_FILE.exists():
            with open(RISK_STATE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def _write_risk(state: dict):
    state['last_updated'] = _utc_iso()
    with open(RISK_STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, indent=2)


# ── yfinance quote fetcher ─────────────────────────────────────
def _fetch_quote_yf(symbol: str) -> dict:
    try:
        ticker = yf.Ticker(symbol)
        info   = ticker.fast_info
        last   = round(float(info.last_price), 2)
        prev   = round(float(info.previous_close), 2)
        chg    = round(last - prev, 2)
        pct    = round((chg / prev) * 100, 2) if prev else 0.0
        return {'last': last, 'chg': chg, 'pct': pct, 'prev_close': prev}
    except Exception as e:
        print(f'[yfinance] {symbol} failed: {e}')
        return {'last': 0, 'chg': 0, 'pct': 0, 'prev_close': 0}


# ── symbol map ────────────────────────────────────────────────
# (label, yfinance_symbol, snapshot_key)
SNAPSHOT_MAP = [
    ('NQ',     'NQ=F',      'NQ'),
    ('ES',     'ES=F',      'ES'),
    ('MNQ',    'NQ=F',      'MNQ'),
    ('MES',    'ES=F',      'MES'),
    ('SPX',    '^GSPC',     'SPX'),
    ('NASDAQ', '^IXIC',     'NASDAQ'),
    ('DJIA',   '^DJI',      'DJIA'),
    ('VIX',    '^VIX',      'VIX'),
    ('DXY',    'DX-Y.NYB',  'DXY'),
    ('US10Y',  '^TNX',      'US10Y'),
    ('GOLD',   'GC=F',      'GOLD'),
    ('SILVER', 'SI=F',      'SILVER'),
    ('OIL',    'CL=F',      'OIL'),
    ('BTC',    'BTC-USD',   'BTC'),
    ('ETH',    'ETH-USD',   'ETH'),
]


# ── session point helper ───────────────────────────────────────
def _compute_session_points(snapshot: dict, label: str, pct: float) -> float:
    last = _safe_float((snapshot.get(label) or {}).get('last'))
    if last and last > 0 and pct != 0:
        return round(abs(last * pct / 100), 2)
    return 0.0


# ── regime deriver ────────────────────────────────────────────
def _derive_regime(nq_pct: float, es_pct: float, vix_last: float) -> str:
    if vix_last and vix_last > 25:
        return 'VOLATILE'
    if nq_pct != 0 and es_pct != 0:
        avg = (nq_pct + es_pct) / 2
    else:
        avg = nq_pct or es_pct
    if avg >= 0.5:
        return 'TRENDING_UP'
    if avg <= -0.5:
        return 'TRENDING_DOWN'
    if abs(avg) < 0.2:
        return 'RANGING'
    return 'MIXED'


# ── main cycle ────────────────────────────────────────────────
def process_finnhub_cycle():
    """
    Main entry point — called by finnhub_loop() in main.py every 5 minutes.
    Fetches live quotes via yfinance and updates market_snapshot in donna_risk_state.json.
    """
    print(f'[donna_finnhub] Running cycle at {_now_ny().strftime("%H:%M:%S")} ET')

    state    = _read_risk()
    snapshot = state.get('market_snapshot', {})
    updated  = 0
    failed   = []

    for label, yf_symbol, snap_key in SNAPSHOT_MAP:
        q = _fetch_quote_yf(yf_symbol)
        time.sleep(0.3)
        if q and q.get('last') not in (None, 0):
            snapshot[snap_key] = {
                'last': q['last'],
                'chg':  q['chg'],
                'pct':  q['pct'],
            }
            updated += 1
        else:
            failed.append(label)

    # Session points for NQ and ES
    nq_data = snapshot.get('NQ', {})
    es_data = snapshot.get('ES', {})
    nq_pct  = _safe_float(nq_data.get('pct'))
    es_pct  = _safe_float(es_data.get('pct'))

    if nq_data.get('last') and nq_pct != 0:
        snapshot['NQ_SESSION_POINTS'] = _compute_session_points(snapshot, 'NQ', nq_pct)
    if es_data.get('last') and es_pct != 0:
        snapshot['ES_SESSION_POINTS'] = _compute_session_points(snapshot, 'ES', es_pct)

    # Diagnostic print for NQ and ES
    nq_last = (snapshot.get('NQ') or {}).get('last', 0)
    es_last = (snapshot.get('ES') or {}).get('last', 0)
    print(f'[donna_finnhub] NQ={nq_last} ES={es_last}')

    snapshot['_updated_at'] = _utc_iso()
    state['market_snapshot'] = snapshot

    # Market regime
    vix_last = _safe_float((snapshot.get('VIX') or {}).get('last'))
    regime   = _derive_regime(nq_pct, es_pct, vix_last)
    state['market_regime'] = regime

    # Session / time fields
    now_ny = _now_ny()
    m = now_ny.hour * 60 + now_ny.minute
    if m >= 19 * 60 or m < 3 * 60:
        session = 'ASIA'
    elif 3 * 60 <= m < 9 * 60 + 30:
        session = 'LONDON'
    elif 9 * 60 + 30 <= m < 16 * 60:
        session = 'NEW_YORK_CASH'
    else:
        session = 'OFF_HOURS'

    state['donna_session']  = session
    state['donna_time_ny']  = now_ny.isoformat()
    state['donna_time_utc'] = datetime.now(timezone.utc).isoformat()
    state['donna_day']      = now_ny.strftime('%A')

    _write_risk(state)

    try:
        _state.set_many({
            'market_regime': regime,
            'session_state': session,
        })
        print(f'[state_engine] Updated — regime: {regime} | session: {session}')
    except Exception as e:
        print(f'[state_engine] regime write failed: {e}')

    status = f'updated={updated}'
    if failed:
        status += f' failed={failed}'
    print(f'[donna_finnhub] Done — {status}')

    # Refresh market reality state after every price cycle
    try:
        from engines.market_reality import compute_market_reality
        compute_market_reality()
    except Exception as e:
        print(f'[market_reality] compute error: {e}')

    # Market Reality 2.0 — objective ground-truth layer (independent of v1)
    try:
        from engines.market_reality_v2 import compute_market_reality_v2
        compute_market_reality_v2()
    except Exception as e:
        print(f'[market_reality_v2] compute error: {e}')

    # Cross-Market Intelligence — relationships between instruments already in snapshot
    try:
        from engines.cross_market import compute_cross_market
        compute_cross_market()
    except Exception as e:
        print(f'[cross_market] compute error: {e}')

    # Market Structure Memory — ONH/ONL, PWH/PWL, monthly open, gap detection
    try:
        from engines.market_structure import compute_market_structure
        compute_market_structure()
    except Exception as e:
        print(f'[market_structure] compute error: {e}')

    # Liquidity & Participation Intelligence — RVOL, session type, breadth, volume confirmation
    try:
        from engines.participation import compute_participation
        compute_participation()
    except Exception as e:
        print(f'[participation] compute error: {e}')
