"""
engines/participation.py — Liquidity & Participation Intelligence.

Teaches NOVA to evaluate conviction, participation, and move quality.
Every setup exists inside a participation context. A Grade A PROS setup
in low-participation conditions is a different risk profile than the same
setup on a trend day with confirming volume. NOVA needs to know the difference.

Questions answered:
  Is participation strong or weak?
  Is volume confirming price?
  Is this a trend day or low-conviction drift?
  Is liquidity expanding or contracting?
  Is breadth supporting the move?

Architecture:
  Heavy yfinance fetches (10-day history for RVOL baselines) cached 30 min.
  Current session stats recomputed every cycle from cached data.
  Breadth (SPY vs IWM) fetched once per cache window.

Observation only. No execution gates. No grading changes. No strategy changes.
Called from process_finnhub_cycle() after market_structure.
Output: donna_participation.json

Signals per instrument (NQ, ES):
  rvol              Relative volume ratio (today cumulative vs historical avg at this time)
  rvol_label        HIGH / ABOVE_AVERAGE / AVERAGE / BELOW_AVERAGE / LOW
  volume_trend      EXPANDING / STEADY / CONTRACTING (recent bars vs earlier bars)
  price_vol_confirm UP_CONFIRMED / DOWN_CONFIRMED / DIVERGING / MIXED

Session-level:
  session_type      TREND_DAY / HIGH_PARTICIPATION / RANGE_DAY / LOW_CONVICTION / UNCERTAIN
  breadth_signal    BROAD_STRENGTH / LARGE_CAP_LED / BROAD_SELLING / DIVERGING / NEUTRAL
  spy_pct           SPY % change open-to-now this session
  iwm_pct           IWM % change open-to-now this session
  participation_bias STRONG / MODERATE / WEAK
  narrative         plain English summary
"""
from __future__ import annotations

import json
import math
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, Tuple
from zoneinfo import ZoneInfo

from core.config import (
    PARTICIPATION_FILE as _P_FILE,
    RISK_STATE_FILE    as _RISK_FILE,
)

_NY_TZ     = ZoneInfo('America/New_York')
_CACHE_TTL = 1800   # 30 minutes

# In-memory DataFrame cache — avoid 4× yfinance network calls every cycle
_cache: dict = {}
_cache_ts: float = 0.0

_T = {
    'rvol_high':         1.5,   # RVOL >= 1.5  → HIGH
    'rvol_above':        1.2,   # RVOL >= 1.2  → ABOVE_AVERAGE
    'rvol_average':      0.8,   # RVOL >= 0.8  → AVERAGE
    'rvol_below':        0.5,   # RVOL >= 0.5  → BELOW_AVERAGE  else LOW
    'vol_expand':        1.15,  # recent/prior >= 1.15 → EXPANDING
    'vol_contract':      0.85,  # recent/prior <= 0.85 → CONTRACTING
    'pvc_ratio':         1.2,   # up_vol/down_vol ratio for directional confirmation
    'breadth_pct':       0.15,  # min % move for directional breadth signal
    'breadth_iwm_frac':  0.70,  # IWM must be >= 70% of SPY move → BROAD_STRENGTH
    'trend_consistency': 0.65,  # fraction of bars in one direction → trend-day pattern
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe(v, default: float = 0.0) -> float:
    try:
        f = float(v)
        return f if math.isfinite(f) else default
    except Exception:
        return default


def _read_json(path: Path) -> dict:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        pass
    return {}


def _session_filter(df) -> object:  # returns a pandas DataFrame subset
    """Keep only regular session bars: 9:30 AM <= bar < 4:00 PM ET."""
    mask = (
        (
            (df.index.hour > 9) |
            ((df.index.hour == 9) & (df.index.minute >= 30))
        ) & (
            df.index.hour < 16
        )
    )
    return df[mask]


# ── Signal classifiers ────────────────────────────────────────────────────────

def _rvol_label(rvol: float) -> str:
    if rvol >= _T['rvol_high']:   return 'HIGH'
    if rvol >= _T['rvol_above']:  return 'ABOVE_AVERAGE'
    if rvol >= _T['rvol_average']: return 'AVERAGE'
    if rvol >= _T['rvol_below']:  return 'BELOW_AVERAGE'
    return 'LOW'


def _compute_rvol(df, today) -> float:
    """
    Relative Volume = today's cumulative session volume (9:30 AM to now)
    divided by the historical average cumulative session volume at this time
    of day (average across prior sessions in the fetched window).

    Time-of-day aware: a low RVOL at 9:45 AM means something different than
    a low RVOL at 3:30 PM. We compare apples to apples.
    """
    try:
        now_ny = datetime.now(_NY_TZ)
        cur_mins = now_ny.hour * 60 + now_ny.minute

        df_s = _session_filter(df)
        bar_mins = df_s.index.hour * 60 + df_s.index.minute

        # Today's cumulative volume from 9:30 to now
        today_mask = (df_s.index.date == today) & (bar_mins <= cur_mins)
        today_vol = _safe(df_s[today_mask]['Volume'].sum())

        if today_vol <= 0:
            return 0.0

        # Historical: for each prior session day, cumulative volume from 9:30 to same time
        prior_days = sorted(set(d for d in df_s.index.date if d < today))[-10:]
        hist_vols: list[float] = []
        for d in prior_days:
            day_mask = (df_s.index.date == d) & (bar_mins <= cur_mins)
            vol = _safe(df_s[day_mask]['Volume'].sum())
            if vol > 0:
                hist_vols.append(vol)

        if not hist_vols:
            return 0.0

        avg_hist = sum(hist_vols) / len(hist_vols)
        return round(today_vol / avg_hist, 2) if avg_hist > 0 else 0.0

    except Exception:
        return 0.0


def _compute_volume_trend(today_bars) -> str:
    """
    Compare volume of the last 3 bars to the 3 bars before that.
    Measures whether current session momentum is building or fading.
    """
    try:
        n = 6
        if len(today_bars) < n:
            return 'UNCERTAIN'
        recent = today_bars.tail(n)
        half = n // 2
        recent_vol = _safe(recent.tail(half)['Volume'].mean())
        prior_vol  = _safe(recent.head(half)['Volume'].mean())
        if prior_vol <= 0:
            return 'UNCERTAIN'
        ratio = recent_vol / prior_vol
        if ratio >= _T['vol_expand']:   return 'EXPANDING'
        if ratio <= _T['vol_contract']: return 'CONTRACTING'
        return 'STEADY'
    except Exception:
        return 'UNCERTAIN'


def _compute_price_vol_confirm(today_bars) -> str:
    """
    Price-volume relationship: are up moves volume-heavier than down moves?

    UP_CONFIRMED   — up bars average higher volume than down bars, and price net positive
    DOWN_CONFIRMED — down bars average higher volume, and price net negative
    DIVERGING      — volume direction contradicts price direction (potential reversal signal)
    MIXED          — no statistically significant pattern
    UNCERTAIN      — insufficient data
    """
    try:
        n = 10
        if len(today_bars) < n:
            return 'UNCERTAIN'

        bars = today_bars.tail(n).copy()
        direction = bars['Close'] - bars['Open']
        up_bars   = bars[direction > 0]
        down_bars = bars[direction < 0]

        if up_bars.empty or down_bars.empty:
            return 'UNCERTAIN'

        up_vol   = _safe(up_bars['Volume'].mean())
        down_vol = _safe(down_bars['Volume'].mean())
        if up_vol <= 0 or down_vol <= 0:
            return 'UNCERTAIN'

        price_net = _safe(bars['Close'].iloc[-1]) - _safe(bars['Close'].iloc[0])
        ratio = up_vol / down_vol

        if ratio >= _T['pvc_ratio'] and price_net > 0:
            return 'UP_CONFIRMED'      # price rising, volume confirms
        if 1 / ratio >= _T['pvc_ratio'] and price_net < 0:
            return 'DOWN_CONFIRMED'    # price falling, volume confirms
        if ratio >= _T['pvc_ratio'] and price_net < 0:
            return 'DIVERGING'         # volume bullish, price bearish = absorption
        if 1 / ratio >= _T['pvc_ratio'] and price_net > 0:
            return 'DIVERGING'         # volume bearish, price bullish = distribution
        return 'MIXED'

    except Exception:
        return 'UNCERTAIN'


def _compute_breadth(spy_df, iwm_df, today) -> Tuple[str, Optional[float], Optional[float]]:
    """
    Breadth proxy: compare SPY vs IWM % change from today's session open.

    BROAD_STRENGTH  — both up, IWM keeping pace with SPY (small caps participating)
    LARGE_CAP_LED   — SPY up meaningfully, IWM lagging (narrow large-cap breadth)
    BROAD_SELLING   — both down meaningfully
    DIVERGING       — one up, one down (mixed breadth)
    NEUTRAL         — both within ±0.15% (no directional signal)
    """
    try:
        def _session_pct(df) -> Optional[float]:
            today_bars = _session_filter(df)
            today_bars = today_bars[today_bars.index.date == today]
            if today_bars.empty:
                return None
            first = _safe(today_bars['Open'].iloc[0])
            last  = _safe(today_bars['Close'].iloc[-1])
            if first <= 0:
                return None
            return round((last - first) / first * 100, 3)

        spy_pct = _session_pct(spy_df)
        iwm_pct = _session_pct(iwm_df)

        if spy_pct is None or iwm_pct is None:
            return 'UNKNOWN', spy_pct, iwm_pct

        thr = _T['breadth_pct']
        if spy_pct > thr and iwm_pct > thr:
            if iwm_pct >= spy_pct * _T['breadth_iwm_frac']:
                return 'BROAD_STRENGTH', spy_pct, iwm_pct
            return 'LARGE_CAP_LED', spy_pct, iwm_pct
        if spy_pct < -thr and iwm_pct < -thr:
            return 'BROAD_SELLING', spy_pct, iwm_pct
        if abs(spy_pct) < thr and abs(iwm_pct) < thr:
            return 'NEUTRAL', spy_pct, iwm_pct
        return 'DIVERGING', spy_pct, iwm_pct

    except Exception:
        return 'UNKNOWN', None, None


def _classify_session_type(
    rvol_label: str,
    vol_trend: str,
    pvc: str,
    today_bars,
    hist_avg_range: float,
) -> str:
    """
    Classify the session type based on participation and price action.

    TREND_DAY         High RVOL + confirming volume + directionally consistent price
    HIGH_PARTICIPATION High RVOL + range or mixed behavior
    RANGE_DAY          Average RVOL + contained price range
    LOW_CONVICTION     Below-average RVOL + narrow range or no follow-through
    UNCERTAIN          Insufficient session data
    """
    try:
        if len(today_bars) < 4:
            return 'UNCERTAIN'

        # Directional consistency: what fraction of bars move in the dominant direction?
        direction = today_bars['Close'] - today_bars['Open']
        n_up   = (direction > 0).sum()
        n_down = (direction < 0).sum()
        n_total = len(direction)
        consistency = max(n_up, n_down) / n_total if n_total > 0 else 0.5

        # Price range expansion vs historical
        t_high = _safe(today_bars['High'].max())
        t_low  = _safe(today_bars['Low'].min())
        t_range = t_high - t_low
        range_ratio = (t_range / hist_avg_range) if hist_avg_range > 0 else 1.0

        if rvol_label in ('HIGH', 'ABOVE_AVERAGE'):
            if (
                pvc in ('UP_CONFIRMED', 'DOWN_CONFIRMED') and
                consistency >= _T['trend_consistency'] and
                range_ratio >= 0.8
            ):
                return 'TREND_DAY'
            return 'HIGH_PARTICIPATION'

        if rvol_label == 'AVERAGE':
            if range_ratio < 0.6 or pvc == 'MIXED':
                return 'LOW_CONVICTION'
            return 'RANGE_DAY'

        return 'LOW_CONVICTION'

    except Exception:
        return 'UNCERTAIN'


def _classify_participation_bias(rvol_label: str, session_type: str, vol_trend: str) -> str:
    if rvol_label in ('HIGH', 'ABOVE_AVERAGE') and session_type in ('TREND_DAY', 'HIGH_PARTICIPATION'):
        return 'STRONG'
    if rvol_label == 'AVERAGE' and session_type in ('RANGE_DAY', 'HIGH_PARTICIPATION'):
        return 'MODERATE'
    if rvol_label in ('BELOW_AVERAGE', 'LOW') or session_type == 'LOW_CONVICTION':
        return 'WEAK'
    return 'MODERATE'


def _build_narrative(
    nq: dict,
    es: dict,
    session_type: str,
    breadth_signal: str,
    spy_pct: Optional[float],
    iwm_pct: Optional[float],
    participation_bias: str,
) -> str:
    parts: list[str] = []

    # Session type lead
    if session_type == 'TREND_DAY':
        parts.append('Trend day in progress — volume confirming directional price action')
    elif session_type == 'HIGH_PARTICIPATION':
        parts.append('High participation — strong volume but non-directional or rotating')
    elif session_type == 'RANGE_DAY':
        parts.append('Range day — average volume, price contained within session range')
    elif session_type == 'LOW_CONVICTION':
        parts.append('Low conviction — below-average volume, low-quality follow-through')

    # RVOL
    nq_rvol = nq.get('rvol', 0.0)
    nq_rl   = nq.get('rvol_label', 'UNKNOWN')
    if nq_rl in ('HIGH', 'ABOVE_AVERAGE'):
        parts.append(f'NQ volume elevated (RVOL {nq_rvol}x) — strong participation')
    elif nq_rl in ('BELOW_AVERAGE', 'LOW'):
        parts.append(f'NQ volume thin (RVOL {nq_rvol}x) — low conviction environment')

    # Price-volume confirmation
    nq_pvc = nq.get('price_vol_confirm', 'MIXED')
    if nq_pvc == 'UP_CONFIRMED':
        parts.append('Volume confirming upside (buyers active on up-bars)')
    elif nq_pvc == 'DOWN_CONFIRMED':
        parts.append('Volume confirming downside (sellers active on down-bars)')
    elif nq_pvc == 'DIVERGING':
        parts.append('Volume diverging from price — potential reversal or absorption')

    # Breadth
    if breadth_signal == 'BROAD_STRENGTH' and spy_pct and iwm_pct:
        parts.append(f'Broad participation: SPY {spy_pct:+.2f}% IWM {iwm_pct:+.2f}% — small caps confirming')
    elif breadth_signal == 'LARGE_CAP_LED' and spy_pct and iwm_pct:
        parts.append(f'Narrow breadth: SPY {spy_pct:+.2f}% but IWM {iwm_pct:+.2f}% — large-cap-only move')
    elif breadth_signal == 'BROAD_SELLING' and spy_pct and iwm_pct:
        parts.append(f'Broad selling: SPY {spy_pct:+.2f}% IWM {iwm_pct:+.2f}% — market-wide risk-off')
    elif breadth_signal == 'DIVERGING':
        parts.append(f'Mixed breadth: SPY {spy_pct:+.2f}% vs IWM {iwm_pct:+.2f}% — sector divergence')

    if not parts:
        return 'Participation data insufficient -- session in early stages or market closed.'

    return ' | '.join(parts)


# ── Cache and fetch ───────────────────────────────────────────────────────────

def _fetch_all() -> dict:
    """
    Fetch 10 days of 5m bars for NQ, ES and 2 days for SPY, IWM.
    Returns dict with DataFrames, or empty dict on failure.
    This is the expensive call — cached for 30 minutes.
    """
    try:
        import yfinance as yf

        result = {}
        for sym, key, period in [
            ('NQ=F', 'nq_df', '10d'),
            ('ES=F', 'es_df', '10d'),
            ('SPY',  'spy_df', '2d'),
            ('IWM',  'iwm_df', '2d'),
        ]:
            try:
                ticker = yf.Ticker(sym)
                df = ticker.history(period=period, interval='5m')
                if df is not None and not df.empty:
                    if df.index.tz is None:
                        df.index = df.index.tz_localize('UTC')
                    df.index = df.index.tz_convert(_NY_TZ)
                    result[key] = df
            except Exception as exc:
                print(f'[participation] fetch failed {sym}: {exc}')

        return result

    except Exception as exc:
        print(f'[participation] _fetch_all failed: {exc}')
        return {}


def _historical_avg_range(df, today) -> float:
    """Average session daily range (high-low) across prior sessions."""
    try:
        df_s = _session_filter(df)
        prior_days = [d for d in set(df_s.index.date) if d < today][-10:]
        ranges = []
        for d in prior_days:
            day_bars = df_s[df_s.index.date == d]
            if not day_bars.empty:
                h = _safe(day_bars['High'].max())
                l = _safe(day_bars['Low'].min())
                if h > l:
                    ranges.append(h - l)
        return sum(ranges) / len(ranges) if ranges else 0.0
    except Exception:
        return 0.0


# ── Main compute ──────────────────────────────────────────────────────────────

def compute_participation() -> dict:
    """
    Compute participation intelligence. Called from process_finnhub_cycle().
    Never raises — returns neutral state on any failure.
    """
    global _cache, _cache_ts

    try:
        now_ts     = time.time()
        cache_miss = (now_ts - _cache_ts) > _CACHE_TTL

        if cache_miss:
            fetched = _fetch_all()
            if fetched:
                _cache    = fetched
                _cache_ts = now_ts
        else:
            fetched = _cache

        if not fetched:
            return _neutral_state()

        now_ny = datetime.now(_NY_TZ)
        today  = now_ny.date()

        # Determine if regular session has data yet
        session_started = (
            now_ny.hour > 9 or
            (now_ny.hour == 9 and now_ny.minute >= 30)
        )

        # Per-instrument signals
        nq_data: dict = {}
        es_data: dict = {}

        for key, result in (('nq_df', nq_data), ('es_df', es_data)):
            df = fetched.get(key)
            if df is None:
                continue

            df_s       = _session_filter(df)
            today_bars = df_s[df_s.index.date == today]
            hist_range = _historical_avg_range(df, today)

            if session_started and not today_bars.empty:
                rvol      = _compute_rvol(df, today)
                vol_trend = _compute_volume_trend(today_bars)
                pvc       = _compute_price_vol_confirm(today_bars)
            else:
                rvol      = 0.0
                vol_trend = 'UNCERTAIN'
                pvc       = 'UNCERTAIN'

            result['rvol']              = rvol
            result['rvol_label']        = _rvol_label(rvol) if rvol > 0 else 'UNCERTAIN'
            result['volume_trend']      = vol_trend
            result['price_vol_confirm'] = pvc
            result['hist_avg_range']    = round(hist_range, 2)

        # Session type from NQ (primary instrument)
        nq_df = fetched.get('nq_df')
        session_type = 'UNCERTAIN'
        if nq_df is not None:
            df_s       = _session_filter(nq_df)
            today_bars = df_s[df_s.index.date == today]
            hist_range = _historical_avg_range(nq_df, today)
            if session_started and not today_bars.empty:
                session_type = _classify_session_type(
                    rvol_label  = nq_data.get('rvol_label', 'UNCERTAIN'),
                    vol_trend   = nq_data.get('volume_trend', 'UNCERTAIN'),
                    pvc         = nq_data.get('price_vol_confirm', 'UNCERTAIN'),
                    today_bars  = today_bars,
                    hist_avg_range = hist_range,
                )

        # Breadth
        spy_df = fetched.get('spy_df')
        iwm_df = fetched.get('iwm_df')
        breadth_signal, spy_pct, iwm_pct = 'UNKNOWN', None, None
        if spy_df is not None and iwm_df is not None and session_started:
            breadth_signal, spy_pct, iwm_pct = _compute_breadth(spy_df, iwm_df, today)

        # Participation bias (session-level summary)
        nq_rl  = nq_data.get('rvol_label', 'UNCERTAIN')
        nq_vt  = nq_data.get('volume_trend', 'UNCERTAIN')
        participation_bias = _classify_participation_bias(nq_rl, session_type, nq_vt)

        narrative = _build_narrative(
            nq=nq_data,
            es=es_data,
            session_type=session_type,
            breadth_signal=breadth_signal,
            spy_pct=spy_pct,
            iwm_pct=iwm_pct,
            participation_bias=participation_bias,
        )

        state = {
            'nq':                nq_data,
            'es':                es_data,
            'session_type':      session_type,
            'breadth_signal':    breadth_signal,
            'spy_pct':           spy_pct,
            'iwm_pct':           iwm_pct,
            'participation_bias': participation_bias,
            'narrative':         narrative,
            'levels_cached':     not cache_miss,
            'last_updated':      _utc_iso(),
        }

        _P_FILE.write_text(json.dumps(state, indent=2, default=str), encoding='utf-8')

        nq_rvol = nq_data.get('rvol', 0.0)
        print(
            f'[participation] {session_type} | bias={participation_bias} | '
            f'NQ_RVOL={nq_rvol}x({nq_rl}) | '
            f'vol_trend={nq_vt} | pvc={nq_data.get("price_vol_confirm")} | '
            f'breadth={breadth_signal} | cached={not cache_miss}'
        )
        return state

    except Exception as exc:
        print(f'[participation] compute error: {exc}')
        return _neutral_state()


def _neutral_state() -> dict:
    empty = {
        'rvol': 0.0, 'rvol_label': 'UNCERTAIN',
        'volume_trend': 'UNCERTAIN', 'price_vol_confirm': 'UNCERTAIN',
        'hist_avg_range': 0.0,
    }
    return {
        'nq': empty.copy(), 'es': empty.copy(),
        'session_type': 'UNCERTAIN',
        'breadth_signal': 'UNKNOWN',
        'spy_pct': None, 'iwm_pct': None,
        'participation_bias': 'UNKNOWN',
        'narrative': 'Participation data unavailable.',
        'levels_cached': False,
        'last_updated': _utc_iso(),
    }


# ── Load / format ─────────────────────────────────────────────────────────────

def load_participation() -> dict:
    """Load cached participation state from file. No network calls."""
    data = _read_json(_P_FILE)
    return data if data else _neutral_state()


def format_for_prompt(p: dict) -> str:
    """
    Multi-line participation block for Claude evaluation prompt.
    Placed after Market Structure Memory so Claude has full context
    before evaluating any setup.
    """
    nq = p.get('nq', {})
    es = p.get('es', {})

    if not nq and not es:
        return ''

    session_type = p.get('session_type', 'UNCERTAIN')
    breadth      = p.get('breadth_signal', 'UNKNOWN')
    spy_pct      = p.get('spy_pct')
    iwm_pct      = p.get('iwm_pct')
    bias         = p.get('participation_bias', 'UNKNOWN')
    narrative    = p.get('narrative', '')

    spy_str = f'SPY {spy_pct:+.2f}%' if spy_pct is not None else 'SPY ?'
    iwm_str = f'IWM {iwm_pct:+.2f}%' if iwm_pct is not None else 'IWM ?'

    lines = [
        '=== LIQUIDITY & PARTICIPATION INTELLIGENCE (observation only) ===',
        f'Session type:       {session_type}',
        f'Participation bias: {bias}',
        f'Breadth:            {breadth} ({spy_str} | {iwm_str})',
    ]

    for label, struct in (('NQ', nq), ('ES', es)):
        rvol  = struct.get('rvol', 0.0)
        rl    = struct.get('rvol_label', '?')
        vt    = struct.get('volume_trend', '?')
        pvc   = struct.get('price_vol_confirm', '?')
        lines.append(
            f'{label}: RVOL={rvol}x ({rl}) | vol_trend={vt} | price_vs_vol={pvc}'
        )

    lines.append(f'Summary: {narrative}')
    lines.append('=== END PARTICIPATION INTELLIGENCE ===')
    return '\n'.join(lines)


def format_for_assistant(p: dict) -> str:
    """Compact single-line format for assistant session context."""
    nq      = p.get('nq', {})
    rvol    = nq.get('rvol', 0.0)
    rl      = nq.get('rvol_label', '?')
    vt      = nq.get('volume_trend', '?')
    pvc     = nq.get('price_vol_confirm', '?')
    stype   = p.get('session_type', '?')
    breadth = p.get('breadth_signal', '?')
    bias    = p.get('participation_bias', '?')
    spy_pct = p.get('spy_pct')
    iwm_pct = p.get('iwm_pct')

    spy_str = f'{spy_pct:+.2f}%' if spy_pct is not None else '?'
    iwm_str = f'{iwm_pct:+.2f}%' if iwm_pct is not None else '?'

    return (
        f'PARTICIPATION: {stype}({bias}) | '
        f'NQ_RVOL={rvol}x({rl}) vol={vt} pvc={pvc} | '
        f'breadth={breadth}(SPY={spy_str}/IWM={iwm_str})'
    )
