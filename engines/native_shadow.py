"""
native_shadow.py — NOVA-native Python shadow of Pine/TradingView ORB, IB, and PROS logic.

Shadow mode only — no execution impact, no gates, no signal changes.
TradingView/Pine remains the sole authoritative source for all execution decisions.

Produces a comparison dict injected into decision snapshots as `native_shadow`:
    "TradingView says X. Python shadow says Y. They match / partially match / mismatch."

See: nova_knowledge_core/NOVA_NATIVE_SHADOW_ENGINE_DESIGN.md
"""
from __future__ import annotations
from datetime import datetime, date
from typing import Optional


# ── Tolerance thresholds (NQ / ES points) ────────────────────────────────────
_IB_MATCH_TIGHT  = 5.0     # ≤5 pts → MATCH
_IB_MATCH_LOOSE  = 75.0    # ≤75 pts → PARTIAL_MATCH (same as existing IB guard)
_ORB_MATCH_TIGHT = 3.0     # ≤3 pts → MATCH
_ORB_MATCH_LOOSE = 20.0    # ≤20 pts → PARTIAL_MATCH

# ── PROS displacement thresholds (mirrors Pine constants) ────────────────────
_PROS_BODY_MULT  = 1.20    # body > avgBody × 1.20
_PROS_RANGE_MULT = 1.10    # range > avgRange × 1.10
_PROS_LEG_MAX_BARS = 50    # leg expires after 50 bars
_PROS_CON_MAX_BARS = 20    # continuation reference expires after 20 bars
_PROS_SMA_WINDOW   = 20    # SMA window for avgBody / avgRange

# ── Candle cache (today's session; refreshed when date changes) ───────────────
_nq_cache: dict = {}
_es_cache: dict = {}


def _load_yfinance_bars(ticker: str, cache: dict) -> list[dict]:
    """Return list of 1-minute bar dicts for today's date from yfinance, cached."""
    try:
        from zoneinfo import ZoneInfo
        import yfinance as _yf

        tz  = ZoneInfo('America/New_York')
        now = datetime.now(tz)
        key = now.date().isoformat()

        if cache.get('_date') == key and cache.get('_bars'):
            return cache['_bars']

        hist = _yf.Ticker(ticker).history(period='1d', interval='1m', prepost=True)
        if hist.empty:
            return []
        hist.index = hist.index.tz_convert(tz)
        today = hist[hist.index.date == now.date()]

        bars = [
            {
                'ts':    row.Index,
                'open':  float(row.Open),
                'high':  float(row.High),
                'low':   float(row.Low),
                'close': float(row.Close),
                'vol':   float(row.Volume),
            }
            for row in today.itertuples()
        ]
        cache['_date'] = key
        cache['_bars'] = bars
        return bars
    except Exception:
        return []


# ── IB shadow ────────────────────────────────────────────────────────────────

def compute_native_ib(bars: list[dict] | None = None) -> dict:
    """
    Compute IB High/Low from 1-minute NQ=F bars.
    Window: 9:30:00 – 10:29:59 ET (matches Pine's _f_ib_high/_f_ib_low functions).
    Returns {'ib_high', 'ib_low', 'ib_range', 'forming', 'bar_count'} or {'error'}.
    When bars are passed explicitly, uses the date of the bars (not today's date) —
    allows deterministic testing with synthetic bars from any date.
    """
    try:
        from zoneinfo import ZoneInfo
        tz  = ZoneInfo('America/New_York')
        now = datetime.now(tz)
        mins = now.hour * 60 + now.minute

        explicit = bars is not None
        if bars is None:
            bars = _load_yfinance_bars('NQ=F', _nq_cache)
        if not bars:
            return {'error': 'no_bars', 'ib_high': None, 'ib_low': None}

        # When bars are explicitly provided, infer target date from the bars themselves
        # so synthetic test bars work regardless of today's actual date.
        if explicit:
            target_date = bars[0]['ts'].date()
        else:
            target_date = now.date()
            if mins < 9 * 60 + 30:
                return {'error': 'IB window not started', 'ib_high': None, 'ib_low': None}

        ib_bars = [
            b for b in bars
            if b['ts'].date() == target_date
            and (
                (b['ts'].hour == 9  and b['ts'].minute >= 30) or
                (b['ts'].hour == 10 and b['ts'].minute <= 29)
            )
        ]

        if not ib_bars:
            return {'error': 'no_ib_bars', 'ib_high': None, 'ib_low': None}

        ib_high  = max(b['high'] for b in ib_bars)
        ib_low   = min(b['low']  for b in ib_bars)
        ib_range = round(ib_high - ib_low, 2)
        forming  = mins < 10 * 60 + 30

        return {
            'ib_high':   round(ib_high,  2),
            'ib_low':    round(ib_low,   2),
            'ib_range':  ib_range,
            'forming':   forming,
            'bar_count': len(ib_bars),
        }
    except Exception as e:
        return {'error': str(e), 'ib_high': None, 'ib_low': None}


# ── ORB shadow ────────────────────────────────────────────────────────────────

def compute_native_orb(bars: list[dict] | None = None) -> dict:
    """
    Compute ORB High/Low/Mid from 1-minute ES=F bars.
    ORB window: 8:00–8:14 ET (Pine default: orbStartHour=8, orbEndHour=8, orbEndMinute=15).
    ORB live after 9:30 ET (orbNYOpenGate). Expired after 11:00 ET (orbKillHour).
    Returns dict with levels and time-based state approximation.
    Gate type (MID_REJECT/LIQ_REJECT/EDGE_REJECT) is NOT computed — BRIDGE_ONLY.
    When bars are passed explicitly, infers target date from bars (test-safe).
    """
    try:
        from zoneinfo import ZoneInfo
        tz  = ZoneInfo('America/New_York')
        now = datetime.now(tz)
        mins = now.hour * 60 + now.minute

        explicit = bars is not None
        if bars is None:
            bars = _load_yfinance_bars('ES=F', _es_cache)

        target_date = bars[0]['ts'].date() if bars and explicit else now.date()

        orb_bars = [
            b for b in bars
            if b['ts'].date() == target_date
            and b['ts'].hour == 8 and b['ts'].minute < 15
        ]

        if not orb_bars:
            state = 'INACTIVE' if mins < 8 * 60 else 'FORMING' if mins < 8 * 60 + 15 else 'NO_DATA'
            return {'orb_high': None, 'orb_low': None, 'orb_mid': None,
                    'orb_state': state, 'bar_count': 0}

        orb_high = max(b['high'] for b in orb_bars)
        orb_low  = min(b['low']  for b in orb_bars)
        orb_mid  = round((orb_high + orb_low) / 2, 2)

        # Time-based state (approximate — no thesis-death or sequence tracking)
        if mins < 8 * 60:
            state = 'INACTIVE'
        elif mins < 8 * 60 + 15:
            state = 'FORMING'
        elif mins >= 11 * 60:
            state = 'EXPIRED'
        elif mins >= 9 * 60 + 30:
            state = 'ACTIVE'
        else:
            state = 'READY'   # ORB formed, NY gate not yet open

        return {
            'orb_high':  round(orb_high, 2),
            'orb_low':   round(orb_low,  2),
            'orb_mid':   orb_mid,
            'orb_state': state,
            'bar_count': len(orb_bars),
        }
    except Exception as e:
        return {'error': str(e), 'orb_high': None, 'orb_low': None,
                'orb_mid': None, 'orb_state': 'NO_DATA', 'bar_count': 0}


# ── PROS shadow ───────────────────────────────────────────────────────────────

def _sma(values: list[float], window: int) -> Optional[float]:
    if len(values) < window:
        return None
    return sum(values[-window:]) / window


def compute_native_pros(bars: list[dict] | None = None) -> dict:
    """
    Python-native PROS phase detection from 1-minute NQ=F bar sequence.

    Replicates Pine Phases A1–A4:
      A1: displacement detection (body/range thresholds vs SMA-20)
      A2: fib zone calculation from leg endpoints
      A3: rejection detection (zone touch + close reclaim)
      A4: continuation detection (reference anchor + break within 20 bars)

    Returns phase classification comparable to _evaluate_pros_phase() output.
    Requires >= 25 bars for SMA-20 window to be meaningful.
    """
    try:
        explicit = bars is not None
        if bars is None:
            bars = _load_yfinance_bars('NQ=F', _nq_cache)
        if not bars or len(bars) < 5:
            return {'phase': 'NO_DATA', 'direction': 'N/A', 'error': 'insufficient_bars',
                    'bar_count': len(bars) if bars else 0}

        from zoneinfo import ZoneInfo
        tz   = ZoneInfo('America/New_York')
        now  = datetime.now(tz)
        # When bars are passed explicitly, infer date from bars (test-safe)
        target_date = bars[0]['ts'].date() if explicit else now.date()
        today_bars = [b for b in bars if b['ts'].date() == target_date]
        if not today_bars:
            return {'phase': 'NO_DATA', 'direction': 'N/A', 'error': 'no_today_bars',
                    'bar_count': 0}

        # ── State variables (mirrors Pine var declarations) ───────────────────
        leg_low_bull  = None
        leg_high_bull = None
        leg_bar_bull  = None
        leg_low_bear  = None
        leg_high_bear = None
        leg_bar_bear  = None

        zone_touched_bull = False
        zone_touched_bear = False

        con_ref_high = None
        con_bar_bull = None
        con_ref_low  = None
        con_bar_bear = None

        cont_sticky_bull = 0
        cont_sticky_bear = 0

        # Final state tracking
        last_phase     = 'NONE'
        last_direction = 'N/A'
        last_ote_depth = 0
        last_leg_h     = None
        last_leg_l     = None
        last_fib618    = None
        last_fib786    = None

        bodies = []
        ranges = []

        for i, bar in enumerate(today_bars):
            body  = abs(bar['close'] - bar['open'])
            rng   = bar['high'] - bar['low']
            bodies.append(body)
            ranges.append(rng)

            avg_body  = _sma(bodies,  _PROS_SMA_WINDOW)
            avg_range = _sma(ranges,  _PROS_SMA_WINDOW)

            close = bar['close']
            open_ = bar['open']
            high  = bar['high']
            low   = bar['low']

            # ── Displacement detection (Phase A1) ────────────────────────────
            if avg_body and avg_range:
                highest3_high = max(b['high'] for b in today_bars[max(0, i-3):i]) if i >= 3 else None
                lowest3_low   = min(b['low']  for b in today_bars[max(0, i-3):i]) if i >= 3 else None

                bull_disp = (
                    close > open_ and
                    body > avg_body * _PROS_BODY_MULT and
                    rng  > avg_range * _PROS_RANGE_MULT and
                    (highest3_high is None or close > highest3_high)
                )
                bear_disp = (
                    close < open_ and
                    body > avg_body * _PROS_BODY_MULT and
                    rng  > avg_range * _PROS_RANGE_MULT and
                    (lowest3_low is None or close < lowest3_low)
                )

                if bull_disp:
                    lowest10 = min(b['low'] for b in today_bars[max(0, i-10):i]) if i >= 1 else low
                    leg_low_bull  = lowest10
                    leg_high_bull = high
                    leg_bar_bull  = i
                    zone_touched_bull = False
                    con_ref_high = None
                    con_bar_bull = None

                if bear_disp:
                    highest10 = max(b['high'] for b in today_bars[max(0, i-10):i]) if i >= 1 else high
                    leg_high_bear = highest10
                    leg_low_bear  = low
                    leg_bar_bear  = i
                    zone_touched_bear = False
                    con_ref_low  = None
                    con_bar_bear = None

            # ── Leg validity checks ───────────────────────────────────────────
            leg_valid_bull = (
                leg_bar_bull is not None and
                (i - leg_bar_bull) <= _PROS_LEG_MAX_BARS and
                leg_low_bull is not None and
                leg_high_bull is not None and
                leg_high_bull > leg_low_bull
            )
            leg_valid_bear = (
                leg_bar_bear is not None and
                (i - leg_bar_bear) <= _PROS_LEG_MAX_BARS and
                leg_high_bear is not None and
                leg_low_bear is not None and
                leg_high_bear > leg_low_bear
            )

            # Invalidate if price closes through leg origin
            if leg_valid_bull and close < leg_low_bull:
                leg_low_bull = leg_high_bull = leg_bar_bull = None
                zone_touched_bull = False
                con_ref_high = con_bar_bull = None
                leg_valid_bull = False

            if leg_valid_bear and close > leg_high_bear:
                leg_high_bear = leg_low_bear = leg_bar_bear = None
                zone_touched_bear = False
                con_ref_low = con_bar_bear = None
                leg_valid_bear = False

            if not leg_valid_bull:
                zone_touched_bull = False
                cont_sticky_bull  = 0
            if not leg_valid_bear:
                zone_touched_bear = False
                cont_sticky_bear  = 0

            # ── Fib zone calculation (Phase A2) ──────────────────────────────
            fib50_bull  = fib618_bull = fib705_bull = fib786_bull = None
            fib50_bear  = fib618_bear = fib705_bear = fib786_bear = None

            if leg_valid_bull:
                span = leg_high_bull - leg_low_bull
                fib50_bull  = leg_high_bull - span * 0.500
                fib618_bull = leg_high_bull - span * 0.618
                fib705_bull = leg_high_bull - span * 0.705
                fib786_bull = leg_high_bull - span * 0.786
                last_leg_h  = leg_high_bull
                last_leg_l  = leg_low_bull
                last_fib618 = fib618_bull
                last_fib786 = fib786_bull

            if leg_valid_bear:
                span = leg_high_bear - leg_low_bear
                fib50_bear  = leg_low_bear + span * 0.500
                fib618_bear = leg_low_bear + span * 0.618
                fib705_bear = leg_low_bear + span * 0.705
                fib786_bear = leg_low_bear + span * 0.786

            # ── Retrace depth ─────────────────────────────────────────────────
            retrace_depth_bull = 0
            if leg_valid_bull and fib50_bull and fib786_bull:
                if close > fib50_bull:
                    retrace_depth_bull = 1   # above 50%
                elif close > fib618_bull:
                    retrace_depth_bull = 2   # between 50–61.8%
                elif close >= fib705_bull:
                    retrace_depth_bull = 3   # OTE zone 61.8–70.5%
                elif close >= fib786_bull:
                    retrace_depth_bull = 4   # deep 70.5–78.6%
                else:
                    retrace_depth_bull = 5   # too deep (below 78.6%)

            retrace_depth_bear = 0
            if leg_valid_bear and fib50_bear and fib786_bear:
                if close < fib50_bear:
                    retrace_depth_bear = 1
                elif close < fib618_bear:
                    retrace_depth_bear = 2
                elif close <= fib705_bear:
                    retrace_depth_bear = 3
                elif close <= fib786_bear:
                    retrace_depth_bear = 4
                else:
                    retrace_depth_bear = 5

            # ── Zone touch detection (Phase A3) ──────────────────────────────
            if leg_valid_bull and fib618_bull and fib786_bull and fib50_bull:
                in_zone_bull   = (fib786_bull <= close <= fib50_bull)
                wick_bull      = (low <= fib618_bull)
                if in_zone_bull or wick_bull:
                    zone_touched_bull = True

            if leg_valid_bear and fib618_bear and fib786_bear and fib50_bear:
                in_zone_bear   = (fib50_bear <= close <= fib786_bear)
                wick_bear      = (high >= fib618_bear)
                if in_zone_bear or wick_bear:
                    zone_touched_bear = True

            # ── Rejection detection (Phase A3) ────────────────────────────────
            rejection_bull = (
                leg_valid_bull and
                zone_touched_bull and
                fib50_bull is not None and
                close > fib50_bull
            )
            rejection_bear = (
                leg_valid_bear and
                zone_touched_bear and
                fib50_bear is not None and
                close < fib50_bear
            )

            if rejection_bull:
                con_ref_high = high
                con_bar_bull = i
                zone_touched_bull = False

            if rejection_bear:
                con_ref_low  = low
                con_bar_bear = i
                zone_touched_bear = False

            # ── Continuation freshness (Phase A4) ────────────────────────────
            con_fresh_bull = (
                con_bar_bull is not None and
                (i - con_bar_bull) <= _PROS_CON_MAX_BARS
            )
            con_fresh_bear = (
                con_bar_bear is not None and
                (i - con_bar_bear) <= _PROS_CON_MAX_BARS
            )

            # ── Continuation detection (Phase A4) ────────────────────────────
            continuation_bull = (
                leg_valid_bull and
                con_fresh_bull and
                con_ref_high is not None and
                close > con_ref_high
            )
            continuation_bear = (
                leg_valid_bear and
                con_fresh_bear and
                con_ref_low is not None and
                close < con_ref_low
            )

            if continuation_bull:
                con_ref_high = None
                con_bar_bull = None
                cont_sticky_bull = 5

            if continuation_bear:
                con_ref_low  = None
                con_bar_bear = None
                cont_sticky_bear = 5

            if not leg_valid_bull:
                cont_sticky_bull = 0
            elif not continuation_bull and cont_sticky_bull > 0:
                cont_sticky_bull -= 1

            if not leg_valid_bear:
                cont_sticky_bear = 0
            elif not continuation_bear and cont_sticky_bear > 0:
                cont_sticky_bear -= 1

            # ── Phase determination (matches _evaluate_pros_phase mapping) ────
            if continuation_bull or cont_sticky_bull > 0:
                last_phase     = 'SETUP_READY'
                last_direction = 'LONG'
                last_ote_depth = retrace_depth_bull
            elif continuation_bear or cont_sticky_bear > 0:
                last_phase     = 'SETUP_READY'
                last_direction = 'SHORT'
                last_ote_depth = retrace_depth_bear
            elif leg_valid_bull and con_bar_bull is not None and con_fresh_bull:
                if retrace_depth_bull == 3:
                    last_phase = 'OTE_TAGGED'
                elif retrace_depth_bull == 4:
                    last_phase = 'OTE_APPROACHING'
                else:
                    last_phase = 'BUILDING'
                last_direction = 'LONG'
                last_ote_depth = retrace_depth_bull
            elif leg_valid_bear and con_bar_bear is not None and con_fresh_bear:
                if retrace_depth_bear == 3:
                    last_phase = 'OTE_TAGGED'
                elif retrace_depth_bear == 4:
                    last_phase = 'OTE_APPROACHING'
                else:
                    last_phase = 'BUILDING'
                last_direction = 'SHORT'
                last_ote_depth = retrace_depth_bear
            elif leg_valid_bull:
                last_phase     = 'BUILDING'
                last_direction = 'LONG'
                last_ote_depth = retrace_depth_bull
            elif leg_valid_bear:
                last_phase     = 'BUILDING'
                last_direction = 'SHORT'
                last_ote_depth = retrace_depth_bear
            else:
                last_phase     = 'NONE'
                last_direction = 'N/A'
                last_ote_depth = 0

        return {
            'phase':      last_phase,
            'direction':  last_direction,
            'ote_depth':  last_ote_depth,
            'leg_high':   round(last_leg_h,  2) if last_leg_h  else None,
            'leg_low':    round(last_leg_l,  2) if last_leg_l  else None,
            'fib_618':    round(last_fib618, 2) if last_fib618 else None,
            'fib_786':    round(last_fib786, 2) if last_fib786 else None,
            'bar_count':  len(today_bars),
        }
    except Exception as e:
        return {'phase': 'NO_DATA', 'direction': 'N/A', 'error': str(e), 'bar_count': 0}


# ── Match helpers ─────────────────────────────────────────────────────────────

def _level_match(shadow: Optional[float], bridge: Optional[float],
                 tight: float, loose: float) -> str:
    if shadow is None or bridge is None:
        return 'NO_DATA'
    delta = abs(shadow - bridge)
    if delta <= tight:
        return 'MATCH'
    if delta <= loose:
        return 'PARTIAL_MATCH'
    return 'MISMATCH'


def _phase_match(shadow_phase: str, bridge_phase: str) -> str:
    """Compare PROS phase strings — order-aware (SETUP_READY > OTE_TAGGED > BUILDING > NONE)."""
    _rank = {'SETUP_READY': 4, 'ACCEPTED_CONTINUATION': 4, 'OTE_TAGGED': 3,
             'OTE_APPROACHING': 2, 'BUILDING': 1, 'NONE': 0, 'NO_DATA': -1}
    if shadow_phase == 'NO_DATA' or not bridge_phase:
        return 'NO_DATA'
    s_rank = _rank.get(shadow_phase, 0)
    b_rank = _rank.get(bridge_phase, 0)
    if shadow_phase == bridge_phase:
        return 'MATCH'
    if abs(s_rank - b_rank) <= 1:
        return 'PARTIAL_MATCH'
    return 'MISMATCH'


def _dir_match(shadow_dir: str, bridge_dir: str) -> str:
    if shadow_dir in ('N/A', 'NO_DATA') or not bridge_dir or bridge_dir == 'N/A':
        return 'NO_DATA'
    if shadow_dir.upper() == bridge_dir.upper():
        return 'MATCH'
    return 'MISMATCH'


# ── Main comparison ───────────────────────────────────────────────────────────

def compare_shadow_to_bridge(
    native_ib:   dict,
    native_orb:  dict,
    native_pros: dict,
    bridge_ib_high:   Optional[float],
    bridge_ib_low:    Optional[float],
    bridge_orb_high:  Optional[float],
    bridge_orb_low:   Optional[float],
    bridge_orb_state: Optional[str],
    bridge_pros_phase: Optional[str],
    bridge_pros_dir:   Optional[str],
) -> dict:
    """Build the comparison record between shadow and bridge values."""
    from datetime import timezone
    ts = datetime.now(timezone.utc).isoformat()

    notes: list[str] = []

    # ── IB ──────────────────────────────────────────────────────────────────
    sh_ib_h = native_ib.get('ib_high')
    sh_ib_l = native_ib.get('ib_low')

    ib_h_match = _level_match(sh_ib_h, bridge_ib_high, _IB_MATCH_TIGHT, _IB_MATCH_LOOSE)
    ib_l_match = _level_match(sh_ib_l, bridge_ib_low,  _IB_MATCH_TIGHT, _IB_MATCH_LOOSE)

    if ib_h_match == 'MISMATCH':
        notes.append(f'IB_H mismatch: shadow={sh_ib_h}, bridge={bridge_ib_high}')
    if ib_l_match == 'MISMATCH':
        notes.append(f'IB_L mismatch: shadow={sh_ib_l}, bridge={bridge_ib_low}')

    # Overall IB match = worse of H and L
    _m_order = ['MISMATCH', 'PARTIAL_MATCH', 'MATCH', 'NO_DATA']
    def _worst(a: str, b: str) -> str:
        if a == 'MISMATCH' or b == 'MISMATCH':
            return 'MISMATCH'
        if a == 'PARTIAL_MATCH' or b == 'PARTIAL_MATCH':
            return 'PARTIAL_MATCH'
        if a == 'MATCH' and b == 'MATCH':
            return 'MATCH'
        return 'NO_DATA'

    ib_match = _worst(ib_h_match, ib_l_match)

    # ── ORB ─────────────────────────────────────────────────────────────────
    sh_orb_h = native_orb.get('orb_high')
    sh_orb_l = native_orb.get('orb_low')
    sh_orb_st = native_orb.get('orb_state')

    orb_h_match  = _level_match(sh_orb_h, bridge_orb_high, _ORB_MATCH_TIGHT, _ORB_MATCH_LOOSE)
    orb_l_match  = _level_match(sh_orb_l, bridge_orb_low,  _ORB_MATCH_TIGHT, _ORB_MATCH_LOOSE)
    orb_lv_match = _worst(orb_h_match, orb_l_match)

    # State comparison — approximate (shadow uses time only, bridge uses full state machine)
    if sh_orb_st and bridge_orb_state:
        bridge_expired = 'EXPIRED' in (bridge_orb_state or '').upper()
        shadow_expired = sh_orb_st == 'EXPIRED'
        if bridge_expired == shadow_expired:
            orb_st_match = 'MATCH'
        else:
            orb_st_match = 'PARTIAL_MATCH'
            notes.append(f'ORB state partial: shadow={sh_orb_st}, bridge={bridge_orb_state}')
    else:
        orb_st_match = 'NO_DATA'

    if orb_lv_match == 'MISMATCH':
        notes.append(f'ORB levels mismatch: shadow=H{sh_orb_h}/L{sh_orb_l}, bridge=H{bridge_orb_high}/L{bridge_orb_low}')

    # ORB gate type — cannot compute; mark as BRIDGE_ONLY
    orb_gate_note = 'BRIDGE_ONLY: MID/LIQ/EDGE gate type replication deferred (requires sweep-tier db)'
    notes.append(orb_gate_note)

    # ── PROS ────────────────────────────────────────────────────────────────
    sh_pros_phase = native_pros.get('phase')
    sh_pros_dir   = native_pros.get('direction')

    pros_ph_match = _phase_match(sh_pros_phase or 'NO_DATA', bridge_pros_phase or '')
    pros_dir_match = _dir_match(sh_pros_dir or 'N/A', bridge_pros_dir or '')

    if pros_ph_match == 'MISMATCH':
        notes.append(f'PROS phase mismatch: shadow={sh_pros_phase}, bridge={bridge_pros_phase}')
    if pros_dir_match == 'MISMATCH':
        notes.append(f'PROS direction mismatch: shadow={sh_pros_dir}, bridge={bridge_pros_dir}')

    # ── Overall ──────────────────────────────────────────────────────────────
    all_matches = [ib_match, orb_lv_match, pros_ph_match]
    data_matches = [m for m in all_matches if m != 'NO_DATA']

    if not data_matches:
        overall = 'INSUFFICIENT'
    elif all(m == 'MATCH' for m in data_matches):
        overall = 'ALL_MATCH'
    elif any(m == 'MISMATCH' for m in data_matches):
        overall = 'DIVERGED'
    else:
        overall = 'PARTIAL'

    return {
        # IB
        'shadow_ib_high':   sh_ib_h,
        'shadow_ib_low':    sh_ib_l,
        'bridge_ib_high':   bridge_ib_high,
        'bridge_ib_low':    bridge_ib_low,
        'ib_high_delta':    round(abs(sh_ib_h - bridge_ib_high), 2) if sh_ib_h and bridge_ib_high else None,
        'ib_low_delta':     round(abs(sh_ib_l - bridge_ib_low),  2) if sh_ib_l and bridge_ib_low  else None,
        'ib_match':         ib_match,

        # ORB
        'shadow_orb_high':  sh_orb_h,
        'shadow_orb_low':   sh_orb_l,
        'shadow_orb_mid':   native_orb.get('orb_mid'),
        'shadow_orb_state': sh_orb_st,
        'bridge_orb_high':  bridge_orb_high,
        'bridge_orb_low':   bridge_orb_low,
        'bridge_orb_state': bridge_orb_state,
        'orb_level_match':  orb_lv_match,
        'orb_state_match':  orb_st_match,
        'orb_gate_type':    'BRIDGE_ONLY',

        # PROS
        'shadow_pros_phase': sh_pros_phase,
        'shadow_pros_dir':   sh_pros_dir,
        'bridge_pros_phase': bridge_pros_phase,
        'bridge_pros_dir':   bridge_pros_dir,
        'pros_phase_match':  pros_ph_match,
        'pros_dir_match':    pros_dir_match,

        # Summary
        'overall_match':  overall,
        'shadow_source':  'yfinance_1m',
        'shadow_ts':      ts,
        'notes':          notes,
    }


def compute_shadow_report(
    bridge_ib_high:    Optional[float] = None,
    bridge_ib_low:     Optional[float] = None,
    bridge_ib_source:  str = 'pros_table',
    bridge_orb_high:   Optional[float] = None,
    bridge_orb_low:    Optional[float] = None,
    bridge_orb_state:  Optional[str]   = None,
    bridge_pros_phase: Optional[str]   = None,
    bridge_pros_dir:   Optional[str]   = None,
) -> dict:
    """
    Entry point for shadow engine. Fetches yfinance data, runs all three
    shadow computations, and returns the comparison dict.

    Called from _fire_decision_snapshot() in a daemon thread — never blocks
    the monitor cycle.
    """
    try:
        nq_bars = _load_yfinance_bars('NQ=F', _nq_cache)
        es_bars = _load_yfinance_bars('ES=F', _es_cache)

        native_ib   = compute_native_ib(bars=nq_bars)
        native_orb  = compute_native_orb(bars=es_bars)
        native_pros = compute_native_pros(bars=nq_bars)

        return compare_shadow_to_bridge(
            native_ib          = native_ib,
            native_orb         = native_orb,
            native_pros        = native_pros,
            bridge_ib_high     = bridge_ib_high,
            bridge_ib_low      = bridge_ib_low,
            bridge_orb_high    = bridge_orb_high,
            bridge_orb_low     = bridge_orb_low,
            bridge_orb_state   = bridge_orb_state,
            bridge_pros_phase  = bridge_pros_phase,
            bridge_pros_dir    = bridge_pros_dir,
        )
    except Exception as e:
        return {
            'overall_match': 'NO_DATA',
            'shadow_source': 'error',
            'shadow_ts':     datetime.utcnow().isoformat(),
            'notes':         [f'Shadow engine error: {str(e)}'],
            'error':         str(e),
        }
