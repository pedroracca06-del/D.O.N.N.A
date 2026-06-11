"""
engines/market_reality_shared.py — Shared utilities for Market Reality engines.

Imported by both market_reality.py (V1) and market_reality_v2.py (V2).
Single definition of weekly structure detection — both engines stay in sync.

In-memory cache (60s TTL) prevents a duplicate yfinance network call when
V1 and V2 both compute within the same Finnhub cycle (~1-2 seconds apart).
"""
from __future__ import annotations

import time
from typing import Optional

_weekly_cache: dict = {}
_weekly_cache_ts: float = 0.0
_WEEKLY_CACHE_TTL = 60  # seconds — covers one full V1+V2 compute cycle


def fetch_weekly_structure() -> dict:
    """
    Detect weekly high/low breaks by comparing today's range against the
    prior 4 days of NQ=F and ES=F 1d bars.  Tolerates yfinance outages.

    Returns:
        {
            'structure':    'RANGE' | 'WEEKLY_LOW_BREAK' | 'WEEKLY_HIGH_BREAK',
            'nq_week_high': float | None,
            'nq_week_low':  float | None,
            'es_week_high': float | None,
            'es_week_low':  float | None,
        }

    Cached for 60 seconds so that V1 and V2 computing in the same Finnhub
    cycle share one network call rather than two.
    """
    global _weekly_cache, _weekly_cache_ts

    if _weekly_cache and (time.time() - _weekly_cache_ts) < _WEEKLY_CACHE_TTL:
        return _weekly_cache

    result: dict = {
        'structure':    'RANGE',
        'nq_week_high': None,
        'nq_week_low':  None,
        'es_week_high': None,
        'es_week_low':  None,
    }
    try:
        import yfinance as yf
        structures: list[str] = []
        for yf_sym, label in (('NQ=F', 'nq'), ('ES=F', 'es')):
            hist = yf.Ticker(yf_sym).history(period='5d', interval='1d')
            if hist is None or hist.empty or len(hist) < 2:
                continue
            prior      = hist.iloc[:-1]
            today      = hist.iloc[-1]
            prior_high = float(prior['High'].max())
            prior_low  = float(prior['Low'].min())
            today_low  = float(today['Low'])
            today_high = float(today['High'])
            result[f'{label}_week_high'] = round(prior_high, 2)
            result[f'{label}_week_low']  = round(prior_low, 2)
            tol = prior_high * 0.0005  # 0.05% tolerance
            if today_low < prior_low - tol:
                structures.append('WEEKLY_LOW_BREAK')
            elif today_high > prior_high + tol:
                structures.append('WEEKLY_HIGH_BREAK')
        if 'WEEKLY_LOW_BREAK' in structures:
            result['structure'] = 'WEEKLY_LOW_BREAK'
        elif 'WEEKLY_HIGH_BREAK' in structures:
            result['structure'] = 'WEEKLY_HIGH_BREAK'
    except Exception as exc:
        print(f'[market_reality_shared] weekly structure fetch failed: {exc}')

    _weekly_cache    = result
    _weekly_cache_ts = time.time()
    return result
