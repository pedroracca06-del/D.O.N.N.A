"""
engines/momentum.py — MACD Momentum Confirmation Engine.

Evaluates buyer/seller control returning during OTE retracements.
Uses MACD slope, acceleration, and curl as quality evidence — NOT as triggers.

Data source: yfinance 5m intraday bars (same instrument as Market Reality).
Cache: 60s TTL per symbol to avoid duplicate network calls per reasoning cycle.

Output: momentum_confirmation ∈ {STRONG_BULLISH, BULLISH, NEUTRAL, BEARISH, STRONG_BEARISH}

This evidence feeds:
  1. directional_pressure._score_momentum() → bull/bear pts in the dominance engine
  2. _build_evaluation_prompt() → explicit MOMENTUM block for Claude grading
  3. System prompt grade criteria → LONG+BEARISH = one-tier downgrade, etc.

Architecture rule: NEVER call this from a request handler.
Called from the evaluation cycle only, after price_ote_eval is computed.
"""
from __future__ import annotations

import time
from typing import Optional

# ── Symbol routing: NOVA chart symbol → yfinance ticker ──────────────────────
_YF_MAP: dict[str, str] = {
    'MES': 'ES=F',
    'ES':  'ES=F',
    'MNQ': 'NQ=F',
    'NQ':  'NQ=F',
}

# ── Per-symbol cache (60s TTL) ────────────────────────────────────────────────
_cache:    dict[str, dict]  = {}
_cache_ts: dict[str, float] = {}
_CACHE_TTL = 60


# ── EMA (pure Python — no pandas) ────────────────────────────────────────────

def _ema(values: list[float], period: int) -> list[float]:
    """Standard EMA seeded with SMA of the first `period` bars."""
    if len(values) < period:
        return []
    k = 2.0 / (period + 1)
    seed = sum(values[:period]) / period
    result = [seed]
    for v in values[period:]:
        result.append(v * k + result[-1] * (1.0 - k))
    return result


# ── MACD computation ──────────────────────────────────────────────────────────

def _compute_macd(
    closes: list[float],
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> Optional[dict]:
    """
    Returns the last few bars of MACD line, signal line, and histogram.
    Requires at least slow + signal + 3 bars for stable values.
    """
    if len(closes) < slow + signal + 3:
        return None

    ema_fast  = _ema(closes, fast)
    ema_slow  = _ema(closes, slow)

    # Align: ema_slow starts (slow - fast) bars later than ema_fast
    offset   = len(ema_fast) - len(ema_slow)
    macd_raw = [f - s for f, s in zip(ema_fast[offset:], ema_slow)]

    sig_raw   = _ema(macd_raw, signal)
    sig_off   = len(macd_raw) - len(sig_raw)
    hist_raw  = [m - s for m, s in zip(macd_raw[sig_off:], sig_raw)]

    # Keep only the last few values needed for slope / accel / curl
    keep = 4
    return {
        'macd':    macd_raw[-keep:],
        'signal':  sig_raw[-keep:],
        'hist':    hist_raw[-keep:],
    }


# ── Momentum classification ───────────────────────────────────────────────────

def _classify(macd_vals: list[float], hist_vals: list[float]) -> dict:
    """
    Compute slope, acceleration, curl, histogram delta.
    Returns the full metrics dict including momentum_confirmation.

    All values are ABSOLUTE (STRONG_BULLISH = upward momentum, regardless of setup
    direction). The directional pressure scorer maps this to bull/bear points
    based on whether it confirms or conflicts with the OTE direction.
    """
    if len(macd_vals) < 3 or len(hist_vals) < 3:
        return {'momentum_confirmation': 'NEUTRAL', 'reason': 'insufficient bars'}

    m0, m1, m2 = macd_vals[-1], macd_vals[-2], macd_vals[-3]
    h0, h1     = hist_vals[-1], hist_vals[-2]

    slope_now  = m0 - m1   # current 1-bar rate of change
    slope_prev = m1 - m2   # prior 1-bar rate of change
    accel      = slope_now - slope_prev   # positive = slope speeding up
    hist_delta = h0 - h1                 # positive = histogram growing (bullish)

    curl_up   = slope_now > 0 and slope_prev <= 0   # was falling, now rising
    curl_down = slope_now < 0 and slope_prev >= 0   # was rising, now falling

    # Scoring — three signals: slope direction, acceleration, histogram delta
    bull_signals = (
        int(slope_now  > 0) +
        int(accel      > 0) +
        int(hist_delta > 0)
    )
    bear_signals = (
        int(slope_now  < 0) +
        int(accel      < 0) +
        int(hist_delta < 0)
    )

    # Curl is the strongest single signal — it marks the inflection point
    if curl_up:
        if hist_delta > 0:
            confirmation = 'STRONG_BULLISH'
        else:
            confirmation = 'BULLISH'
    elif curl_down:
        if hist_delta < 0:
            confirmation = 'STRONG_BEARISH'
        else:
            confirmation = 'BEARISH'
    elif bull_signals >= 3:
        confirmation = 'STRONG_BULLISH'
    elif bull_signals >= 2:
        confirmation = 'BULLISH'
    elif bear_signals >= 3:
        confirmation = 'STRONG_BEARISH'
    elif bear_signals >= 2:
        confirmation = 'BEARISH'
    else:
        confirmation = 'NEUTRAL'

    return {
        'momentum_confirmation': confirmation,
        'macd_line':  round(m0, 4),
        'macd_slope': round(slope_now, 4),
        'macd_accel': round(accel, 4),
        'histogram':  round(h0, 4),
        'hist_delta': round(hist_delta, 4),
        'curl_up':    curl_up,
        'curl_down':  curl_down,
    }


# ── Data fetch ────────────────────────────────────────────────────────────────

def _fetch_closes(yf_symbol: str) -> list[float]:
    """Fetch intraday 5m closes via yfinance. Returns empty list on failure."""
    try:
        import yfinance as yf
        hist = yf.Ticker(yf_symbol).history(period='1d', interval='5m')
        if hist is None or hist.empty:
            # Fallback: last 2 days (handles extended-hours gaps)
            hist = yf.Ticker(yf_symbol).history(period='2d', interval='5m')
        if hist is None or hist.empty or len(hist) < 40:
            return []
        return [float(c) for c in hist['Close'].tolist()]
    except Exception as exc:
        print(f'[momentum] fetch failed for {yf_symbol}: {exc}')
        return []


# ── Public interface ──────────────────────────────────────────────────────────

def compute_momentum(symbol: str, ote_eval: Optional[dict] = None) -> dict:
    """
    Compute MACD-based momentum confirmation for the given symbol.

    Args:
        symbol:   NOVA chart symbol (MES / MNQ / ES / NQ — without exchange prefix)
        ote_eval: price_ote_eval dict from _evaluate_price_structure(); used only
                  for context logging — classification is always absolute.

    Returns dict with keys:
        momentum_confirmation  — STRONG_BULLISH / BULLISH / NEUTRAL / BEARISH / STRONG_BEARISH
        macd_line, macd_slope, macd_accel, histogram, hist_delta
        curl_up, curl_down
        ote_context            — OTE direction from ote_eval or 'N/A'
        bars_used              — number of closes the MACD was computed from
        yf_symbol              — yfinance ticker used
        source                 — 'live' | 'cache' | 'unavailable'
    """
    clean_sym = symbol.upper().replace('CME_MINI:', '').replace('1!', '')
    yf_sym    = _YF_MAP.get(clean_sym)

    ote_direction = 'N/A'
    if ote_eval and ote_eval.get('has_ote'):
        ote_direction = ote_eval.get('direction', 'N/A')

    base = {
        'momentum_confirmation': 'NEUTRAL',
        'macd_line':  0.0,
        'macd_slope': 0.0,
        'macd_accel': 0.0,
        'histogram':  0.0,
        'hist_delta': 0.0,
        'curl_up':    False,
        'curl_down':  False,
        'ote_context': ote_direction,
        'bars_used':   0,
        'yf_symbol':   yf_sym or clean_sym,
        'source':      'unavailable',
    }

    if not yf_sym:
        base['reason'] = f'no yfinance mapping for {clean_sym}'
        return base

    # Cache hit
    now = time.time()
    if clean_sym in _cache and (now - _cache_ts.get(clean_sym, 0)) < _CACHE_TTL:
        result = dict(_cache[clean_sym])
        result['source'] = 'cache'
        result['ote_context'] = ote_direction
        return result

    closes = _fetch_closes(yf_sym)
    if len(closes) < 40:
        base['reason']  = f'insufficient bars ({len(closes)}) for {yf_sym}'
        base['source']  = 'unavailable'
        return base

    macd_data = _compute_macd(closes)
    if not macd_data:
        base['reason'] = 'MACD computation failed'
        return base

    metrics = _classify(macd_data['macd'], macd_data['hist'])
    result  = {
        **base,
        **metrics,
        'bars_used':   len(closes),
        'yf_symbol':   yf_sym,
        'source':      'live',
        'ote_context': ote_direction,
    }
    result.pop('reason', None)

    _cache[clean_sym]    = {k: v for k, v in result.items() if k != 'ote_context'}
    _cache_ts[clean_sym] = now

    print(
        f'[momentum] {clean_sym} = {result["momentum_confirmation"]} | '
        f'MACD={result["macd_line"]:+.3f} slope={result["macd_slope"]:+.4f} '
        f'accel={result["macd_accel"]:+.4f} hist_delta={result["hist_delta"]:+.4f}'
        + (' CURL_UP' if result['curl_up'] else ' CURL_DOWN' if result['curl_down'] else '')
        + f' | OTE={ote_direction} bars={len(closes)}'
    )
    return result


def format_for_prompt(m: dict) -> str:
    """Single-line momentum block for Claude prompt injection."""
    if not m or m.get('source') == 'unavailable':
        return 'MOMENTUM: unavailable'

    state   = m.get('momentum_confirmation', 'NEUTRAL')
    slope   = m.get('macd_slope', 0)
    accel   = m.get('macd_accel', 0)
    hist_d  = m.get('hist_delta', 0)
    curl    = 'CURL_UP' if m.get('curl_up') else ('CURL_DOWN' if m.get('curl_down') else 'no-curl')
    ote_ctx = m.get('ote_context', 'N/A')

    return (
        f'MOMENTUM: {state} | '
        f'slope={slope:+.4f} accel={accel:+.4f} hist_delta={hist_d:+.4f} | '
        f'{curl} | OTE_context={ote_ctx}'
    )
