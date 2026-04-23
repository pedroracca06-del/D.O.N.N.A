# ============================================================
# donna_finnhub.py — DONNA v5.0 Live Market Snapshot Engine
# Replaces the stub process_finnhub_cycle() in main.py
#
# DROP THIS FILE into your project root alongside main.py
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

BASE_DIR          = Path(__file__).parent
RISK_STATE_FILE   = BASE_DIR / 'donna_risk_state.json'
NY_TZ             = ZoneInfo('America/New_York')

FINNHUB_API_KEY       = os.getenv('FINNHUB_API_KEY', '').strip()
FMP_API_KEY           = os.getenv('FMP_API_KEY', '').strip()
ALPHA_VANTAGE_API_KEY = os.getenv('ALPHA_VANTAGE_API_KEY', '').strip()


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


# ── quote fetchers ────────────────────────────────────────────
def _finnhub_quote(symbol: str) -> dict | None:
    if not FINNHUB_API_KEY:
        return None
    data = _safe_get(
        'https://finnhub.io/api/v1/quote',
        {'symbol': symbol, 'token': FINNHUB_API_KEY}
    )
    if not data:
        return None
    c  = _safe_float(data.get('c'), None)
    pc = _safe_float(data.get('pc'), None)
    if not c or not pc or c == 0 or pc == 0:
        return None
    chg = c - pc
    pct = (chg / pc) * 100
    return {'last': round(c, 4), 'chg': round(chg, 4), 'pct': round(pct, 4)}


def _fmp_quote(symbol: str) -> dict | None:
    if not FMP_API_KEY:
        return None
    data = _safe_get(
        f'https://financialmodelingprep.com/api/v3/quote/{symbol}',
        {'apikey': FMP_API_KEY}
    )
    if not isinstance(data, list) or not data:
        return None
    item = data[0]
    last = _safe_float(item.get('price'))
    chg  = _safe_float(item.get('change'))
    pct  = _safe_float(item.get('changesPercentage'))
    if last == 0:
        return None
    return {'last': round(last, 4), 'chg': round(chg, 4), 'pct': round(pct, 4)}


def _alpha_quote(symbol: str) -> dict | None:
    if not ALPHA_VANTAGE_API_KEY:
        return None
    data = _safe_get(
        'https://www.alphavantage.co/query',
        {'function': 'GLOBAL_QUOTE', 'symbol': symbol, 'apikey': ALPHA_VANTAGE_API_KEY}
    )
    if not data:
        return None
    q = data.get('Global Quote', {})
    last = _safe_float(q.get('05. price'))
    chg  = _safe_float(q.get('09. change'))
    pct  = _safe_float(str(q.get('10. change percent', '0')).replace('%', ''))
    if last == 0:
        return None
    return {'last': round(last, 4), 'chg': round(chg, 4), 'pct': round(pct, 4)}


def _quote(symbol: str, fallbacks: list[str] | None = None) -> dict | None:
    """Try Finnhub → FMP → Alpha Vantage → fallback symbols."""
    q = _finnhub_quote(symbol)
    if q:
        return q
    for sym in (fallbacks or []):
        q = _finnhub_quote(sym)
        if q:
            return q
    q = _fmp_quote(symbol)
    if q:
        return q
    q = _alpha_quote(symbol)
    return q


# ── symbol map ────────────────────────────────────────────────
# Each entry: key → (primary_symbol, [fallbacks], snapshot_key)
SNAPSHOT_MAP = [
    ('SPX',    '^GSPC',   ['^SPX', 'SPY'],         'SPX'),
    ('NASDAQ', '^IXIC',   ['^NDX', 'QQQ'],         'NASDAQ'),
    ('DJIA',   '^DJI',    ['DIA'],                  'DJIA'),
    ('VIX',    '^VIX',    [],                       'VIX'),
    ('US10Y',  '^TNX',    [],                       'US10Y'),
    ('DXY',    'DX-Y.NYB',['UUP'],                  'DXY'),
    ('NQ',     'NQ=F',    ['^NDX', 'QQQ'],         'NQ'),
    ('ES',     'ES=F',    ['^GSPC', 'SPY'],         'ES'),
    ('OIL',    'CL=F',    ['USO'],                  'OIL'),
    ('GOLD',   'GC=F',    ['GLD'],                  'GOLD'),
    ('SILVER', 'SI=F',    ['SLV'],                  'SILVER'),
]

# Session point tracking — NQ and ES
def _compute_session_points(current_snapshot: dict, label: str, pct: float) -> float:
    """Estimate session points from percentage move."""
    last = _safe_float((current_snapshot.get(label) or {}).get('last'))
    if last and last > 0 and pct != 0:
        return round(abs(last * pct / 100), 2)
    return 0.0


# ── main cycle ────────────────────────────────────────────────
def process_finnhub_cycle():
    """
    Main entry point — called by finnhub_loop() in main.py every 5 minutes.
    Fetches live quotes and updates market_snapshot in donna_risk_state.json.
    """
    print(f'[donna_finnhub] Running cycle at {_now_ny().strftime("%H:%M:%S")} ET')

    state = _read_risk()
    snapshot = state.get('market_snapshot', {})
    updated = 0
    failed  = []

    for label, primary, fallbacks, snap_key in SNAPSHOT_MAP:
        q = _quote(primary, fallbacks)
        time.sleep(0.5)
        if q and q.get('last') not in (None, 0):
            snapshot[snap_key] = {
                'last': q['last'],
                'chg':  q['chg'],
                'pct':  q['pct'],
            }
            updated += 1
        else:
            failed.append(label)

    # Update session points
    nq_data = snapshot.get('NQ', {})
    es_data = snapshot.get('ES', {})
    nq_pct  = _safe_float(nq_data.get('pct'))
    es_pct  = _safe_float(es_data.get('pct'))

    if nq_data.get('last') and nq_pct != 0:
        snapshot['NQ_SESSION_POINTS'] = _compute_session_points(snapshot, 'NQ', nq_pct)
    if es_data.get('last') and es_pct != 0:
        snapshot['ES_SESSION_POINTS'] = _compute_session_points(snapshot, 'ES', es_pct)

    snapshot['_updated_at'] = _utc_iso()
    state['market_snapshot'] = snapshot

    # Patch donna session/time fields while we're here
    now_ny  = _now_ny()
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

    status = f'updated={updated}'
    if failed:
        status += f' failed={failed}'
    print(f'[donna_finnhub] Done — {status}')
