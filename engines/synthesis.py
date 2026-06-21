"""
engines/synthesis.py -- Market Synthesis Layer V2.

V1 flaw (corrected here):
    Thesis was selected from structural conditions first.
    Evidence was collected afterward to support it.
    Result: the headline and its own evidence could directly contradict each other.
    The system couldn't detect its own contradictions.

V2 architecture -- evidence before thesis:
    1. Collect all signals from all five intelligence engines
    2. Weight each signal by importance (major=3, medium=2, minor=1)
    3. Score directional balance (bull_score vs bear_score)
    4. Detect major conflicts (weight-2+ signals from different sources disagreeing)
    5. Derive thesis STATE from the weighted evidence
    6. Generate thesis SENTENCE from state + key context
    7. Generate conditional branch (what would change the read)
    8. Score confidence and risk

Thesis states:
    BULLISH               -- aligned bull signals, no major conflict
    BEARISH               -- aligned bear signals, no major conflict
    NEUTRAL               -- balanced signals or insufficient data
    CONTESTED             -- major intelligence layers directly disagree
    TRANSITIONING         -- mild directional lean, conviction building
    ACCEPTANCE_DEVELOPING -- structural breakout confirmed by participation
    REJECTION_DEVELOPING  -- probe at level failing to attract follow-through
    LIQUIDITY_SEEKING     -- structural direction resolved, price targeting draw

Critical architecture rule:
    Never reads PROS, ORB, or any strategy signal.
    Strategies consume synthesis. Synthesis does not consume strategies.
    If PROS and ORB were deleted tomorrow, this engine must still work correctly.

No new APIs. No new data sources. No execution changes.
Called from services/finnhub.py after all other intelligence engines.
Output: donna_synthesis.json
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import NamedTuple
from zoneinfo import ZoneInfo

from core.config import (
    SYNTHESIS_FILE         as _SYN_FILE,
    INTELLIGENCE_LOG_FILE  as _INTEL_FILE,
    MARKET_REALITY_V2_FILE as _MR2_FILE,
    CROSS_MARKET_FILE      as _CM_FILE,
    MARKET_STRUCTURE_FILE  as _MS_FILE,
    PARTICIPATION_FILE     as _P_FILE,
    LIQUIDITY_FILE         as _LIQ_FILE,
    RISK_STATE_FILE        as _RISK_FILE,
)

_NY_TZ       = ZoneInfo('America/New_York')
_INTEL_MAX   = 500
_INTEL_LOCK  = __import__('threading').Lock()


def _emit_intelligence_event(subtype: str, payload: dict, event_type: str = 'INTELLIGENCE') -> None:
    """
    Append one event to donna_intelligence_log.json.
    Thread-safe. Never raises. Pass event_type to override the default INTELLIGENCE category.
    """
    import random, time as _time
    eid = f'INTEL_{int(_time.time() * 1000)}_{random.randint(100, 999)}'
    try:
        ny_ts = datetime.now(_NY_TZ).strftime('%Y-%m-%d %H:%M:%S ET')
        entry = {'id': eid, 'timestamp_et': ny_ts, 'event_type': event_type,
                 'subtype': subtype, **payload}
        with _INTEL_LOCK:
            data: list = []
            try:
                if _INTEL_FILE.exists():
                    data = json.loads(_INTEL_FILE.read_text(encoding='utf-8'))
                    if not isinstance(data, list):
                        data = []
            except Exception:
                data = []
            data.insert(0, entry)
            _INTEL_FILE.write_text(
                json.dumps(data[:_INTEL_MAX], indent=2, default=str),
                encoding='utf-8',
            )
    except Exception as exc:
        print(f'[synthesis] intel event write error: {exc}')


# ── Signal primitive ──────────────────────────────────────────────────────────

class Signal(NamedTuple):
    direction: str   # BULLISH / BEARISH / NEUTRAL
    weight:    int   # 3=major, 2=medium, 1=minor
    label:     str   # human-readable, shown in evidence
    source:    str   # market_reality / structure / liquidity / cross_market / participation


# ── Helpers ───────────────────────────────────────────────────────────────────

def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe(v, default: float = 0.0) -> float:
    try:
        f = float(v)
        return f if math.isfinite(f) else default
    except Exception:
        return default


def _fmt(v) -> str:
    if v is None:
        return '?'
    try:
        return f'{float(v):.0f}'
    except Exception:
        return str(v)


def _read_json(path: Path) -> dict:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        pass
    return {}


# ── Signal collection ─────────────────────────────────────────────────────────

def _mr2_signals(mr2: dict) -> list[Signal]:
    signals: list[Signal] = []
    direction  = mr2.get('direction', 'NEUTRAL')
    severity   = mr2.get('severity', 'NONE')
    nq_pct     = _safe(mr2.get('nq_pct', 0.0))
    weekly_str = mr2.get('weekly_structure', 'UNKNOWN')

    # Main direction signal — weight reflects severity
    if direction == 'BULLISH':
        w = 3 if severity in ('STRONG', 'MODERATE') else 2 if severity == 'MILD' else 1
        signals.append(Signal('BULLISH', w,
            f'MR2: NQ {nq_pct:+.2f}% -- {severity} bullish momentum', 'market_reality'))
    elif direction == 'BEARISH':
        w = 3 if severity in ('STRONG', 'MODERATE') else 2 if severity == 'MILD' else 1
        signals.append(Signal('BEARISH', w,
            f'MR2: NQ {nq_pct:+.2f}% -- {severity} bearish momentum', 'market_reality'))
    else:
        # Neutral MR2 is still data but carries no directional weight
        signals.append(Signal('NEUTRAL', 1,
            f'MR2: NQ {nq_pct:+.2f}% -- no dominant direction', 'market_reality'))

    # Weekly structure alignment (minor)
    if weekly_str == 'BULL_TREND':
        signals.append(Signal('BULLISH', 1, 'Weekly structure: BULL_TREND', 'market_reality'))
    elif weekly_str == 'BEAR_TREND':
        signals.append(Signal('BEARISH', 1, 'Weekly structure: BEAR_TREND', 'market_reality'))

    return signals


def _structure_signals(ms_nq: dict, part: dict) -> list[Signal]:
    """
    Structural position qualified by participation quality.

    This is the core V2 improvement: same structural position produces a
    different signal depending on whether participation confirms or denies it.

    Above PDH + strong participation = acceptance (BULLISH, major)
    Above PDH + weak participation   = stop-run risk (BEARISH, major)
    Above PDH + neutral              = testing (BULLISH, medium)
    """
    signals: list[Signal] = []

    vs_pdh = ms_nq.get('price_vs_pdh', 'UNKNOWN')
    vs_pdl = ms_nq.get('price_vs_pdl', 'UNKNOWN')
    vs_pwh = ms_nq.get('price_vs_pwh', 'UNKNOWN')
    vs_pwl = ms_nq.get('price_vs_pwl', 'UNKNOWN')
    pdh    = ms_nq.get('pdh')
    pdl    = ms_nq.get('pdl')
    pwh    = ms_nq.get('pwh')
    pwl    = ms_nq.get('pwl')
    gap    = ms_nq.get('gap_signal', 'UNKNOWN')
    gap_pct = _safe(ms_nq.get('gap_pct', 0.0))

    rvol       = _safe((part.get('nq') or {}).get('rvol', 0.0))
    rvol_label = (part.get('nq') or {}).get('rvol_label', 'UNCERTAIN')
    part_bias  = part.get('participation_bias', 'UNKNOWN')
    sess_type  = part.get('session_type', 'UNCERTAIN')

    high_part = part_bias == 'STRONG' or sess_type == 'TREND_DAY' or rvol >= 1.2
    low_part  = part_bias == 'WEAK'   or rvol <= 0.70

    # ── PWH (prior-week high) -- highest significance ceiling ─────────────
    if vs_pwh == 'ABOVE':
        if high_part:
            signals.append(Signal('BULLISH', 3,
                f'Above PWH ({_fmt(pwh)}) on {part_bias} participation -- major structural acceptance',
                'structure'))
        elif low_part:
            signals.append(Signal('BEARISH', 2,
                f'Above PWH ({_fmt(pwh)}) on weak volume ({rvol:.1f}x) -- extension without conviction',
                'structure'))
        else:
            signals.append(Signal('BULLISH', 2,
                f'Above PWH ({_fmt(pwh)}) -- prior-week range cleared',
                'structure'))
    elif vs_pwh == 'AT':
        if high_part:
            signals.append(Signal('BULLISH', 2,
                f'Testing PWH ({_fmt(pwh)}) with elevated volume -- breakout attempt developing',
                'structure'))
        elif low_part:
            signals.append(Signal('BEARISH', 2,
                f'Probing PWH ({_fmt(pwh)}) on thin volume ({rvol:.1f}x) -- rejection risk at major resistance',
                'structure'))
        else:
            signals.append(Signal('NEUTRAL', 1,
                f'Testing PWH ({_fmt(pwh)}) -- volume not yet confirming direction',
                'structure'))

    # ── PWL (prior-week low) -- highest significance floor ────────────────
    if vs_pwl == 'BELOW':
        if high_part:
            signals.append(Signal('BEARISH', 3,
                f'Below PWL ({_fmt(pwl)}) on {part_bias} participation -- major structural breakdown',
                'structure'))
        elif low_part:
            signals.append(Signal('BEARISH', 1,
                f'Below PWL ({_fmt(pwl)}) on weak volume -- breakdown lacks conviction',
                'structure'))
        else:
            signals.append(Signal('BEARISH', 2,
                f'Below PWL ({_fmt(pwl)}) -- prior-week range broken to downside',
                'structure'))
    elif vs_pwl == 'AT':
        if high_part:
            signals.append(Signal('BEARISH', 2,
                f'Testing PWL ({_fmt(pwl)}) with volume -- breakdown attempt, major support at risk',
                'structure'))
        elif low_part:
            signals.append(Signal('BULLISH', 1,
                f'Probing PWL ({_fmt(pwl)}) on thin volume -- major support likely to hold',
                'structure'))
        else:
            signals.append(Signal('NEUTRAL', 1,
                f'Testing PWL ({_fmt(pwl)}) -- directional resolution pending',
                'structure'))

    # ── PDH -- primary intraday ceiling (only when not overshadowed by PWH) ─
    if vs_pwh not in ('ABOVE', 'AT'):
        if vs_pdh == 'ABOVE':
            if high_part:
                signals.append(Signal('BULLISH', 3,
                    f'Above PDH ({_fmt(pdh)}) with {part_bias} participation -- acceptance above prior-day high',
                    'structure'))
            elif low_part:
                signals.append(Signal('BEARISH', 3,
                    f'Above PDH ({_fmt(pdh)}) on WEAK volume ({rvol:.1f}x) -- stop-run risk, no follow-through',
                    'structure'))
            else:
                signals.append(Signal('BULLISH', 2,
                    f'Above PDH ({_fmt(pdh)}) -- sellers cleared, participation neutral ({rvol:.1f}x)',
                    'structure'))
        elif vs_pdh == 'AT':
            if high_part:
                signals.append(Signal('BULLISH', 2,
                    f'Testing PDH ({_fmt(pdh)}) with elevated volume ({rvol:.1f}x) -- acceptance developing',
                    'structure'))
            elif low_part:
                signals.append(Signal('BEARISH', 2,
                    f'Probing PDH ({_fmt(pdh)}) on weak volume ({rvol:.1f}x) -- rejection risk',
                    'structure'))
            else:
                signals.append(Signal('NEUTRAL', 1,
                    f'Testing PDH ({_fmt(pdh)}) -- direction not yet confirmed',
                    'structure'))

    # ── PDL -- primary intraday floor (only when not overshadowed by PWL) ──
    if vs_pwl not in ('BELOW', 'AT'):
        if vs_pdl == 'BELOW':
            if high_part:
                signals.append(Signal('BEARISH', 3,
                    f'Below PDL ({_fmt(pdl)}) with {part_bias} participation -- acceptance below prior-day low',
                    'structure'))
            elif low_part:
                signals.append(Signal('BULLISH', 2,
                    f'Below PDL ({_fmt(pdl)}) on weak volume ({rvol:.1f}x) -- breakdown lacks conviction',
                    'structure'))
            else:
                signals.append(Signal('BEARISH', 2,
                    f'Below PDL ({_fmt(pdl)}) -- buyers cleared, prior-day support broken',
                    'structure'))
        elif vs_pdl == 'AT':
            if high_part:
                signals.append(Signal('BEARISH', 2,
                    f'Testing PDL ({_fmt(pdl)}) with volume ({rvol:.1f}x) -- breakdown attempt, support at risk',
                    'structure'))
            elif low_part:
                signals.append(Signal('BULLISH', 2,
                    f'Testing PDL ({_fmt(pdl)}) on thin volume -- support likely to hold, buyers absorbing',
                    'structure'))
            else:
                signals.append(Signal('NEUTRAL', 1,
                    f'Testing PDL ({_fmt(pdl)}) -- directional resolution pending',
                    'structure'))

    # ── Gap (medium weight) ───────────────────────────────────────────────
    if gap == 'GAP_UP':
        signals.append(Signal('BULLISH', 2,
            f'Gap up ({gap_pct:+.2f}%) -- opened above prior close, overnight buyers in control',
            'structure'))
    elif gap == 'GAP_DOWN':
        signals.append(Signal('BEARISH', 2,
            f'Gap down ({gap_pct:+.2f}%) -- opened below prior close, overnight sellers in control',
            'structure'))

    return signals


def _liquidity_signals(liq_nq: dict) -> list[Signal]:
    signals: list[Signal] = []

    draw    = liq_nq.get('primary_draw') or {}
    u_above = liq_nq.get('untapped_above', 0)
    u_below = liq_nq.get('untapped_below', 0)
    s_above = liq_nq.get('swept_above', 0)
    s_below = liq_nq.get('swept_below', 0)

    # ── Asymmetric liquidity -- MAJOR signal ──────────────────────────────
    if u_above == 0 and u_below > 0:
        signals.append(Signal('BEARISH', 3,
            f'Liquidity asymmetry -- 0 untapped above, {u_below} untapped below -- full downside draw',
            'liquidity'))
    elif u_below == 0 and u_above > 0:
        signals.append(Signal('BULLISH', 3,
            f'Liquidity asymmetry -- {u_above} untapped above, 0 untapped below -- full upside draw',
            'liquidity'))
    elif draw.get('label') and draw.get('side'):
        # Partial asymmetry: primary draw weighted by proximity
        d_pts   = abs(_safe(draw.get('distance_pts', 999)))
        d_side  = draw['side']
        d_lbl   = draw['label']
        d_px    = _fmt(draw.get('price'))
        d_dir   = 'BEARISH' if d_side == 'BELOW' else 'BULLISH'
        w = 3 if d_pts < 80 else 2 if d_pts < 200 else 1
        signals.append(Signal(d_dir, w,
            f'Primary draw {d_lbl} ({d_px}, {d_pts:.0f}pts {"below" if d_side == "BELOW" else "above"}) -- unfinished business',
            'liquidity'))

    # ── Swept levels context (minor) ──────────────────────────────────────
    if s_above >= 2:
        signals.append(Signal('BEARISH', 1,
            f'{s_above} levels swept above -- topside supply has been cleared, structural exhaustion possible',
            'liquidity'))
    elif s_above == 1:
        signals.append(Signal('BULLISH', 1,
            f'One level swept above -- PDH tested and cleared',
            'liquidity'))

    return signals


def _cross_market_signals(cm: dict) -> list[Signal]:
    signals: list[Signal] = []

    cm_bias   = cm.get('cross_market_bias', 'NEUTRAL')
    dxy_sig   = cm.get('dxy_signal', 'DXY_NEUTRAL')
    yield_sig = cm.get('yield_signal', 'YIELD_NEUTRAL')
    vix_move  = cm.get('vix_move', 'VIX_STABLE')
    nq_es_lbl = cm.get('nq_vs_es_label', 'ALIGNED')

    # ── Macro bias (medium) ───────────────────────────────────────────────
    if cm_bias == 'BULLISH_SUPPORT':
        signals.append(Signal('BULLISH', 2,
            'Cross-market: BULLISH_SUPPORT -- macro backdrop confirming equity strength',
            'cross_market'))
    elif cm_bias == 'BEARISH_PRESSURE':
        signals.append(Signal('BEARISH', 2,
            'Cross-market: BEARISH_PRESSURE -- macro backdrop opposing equity strength',
            'cross_market'))
    elif cm_bias == 'MILD_TAILWIND':
        signals.append(Signal('BULLISH', 1, 'Cross-market: mild macro tailwind', 'cross_market'))
    elif cm_bias == 'MILD_HEADWIND':
        signals.append(Signal('BEARISH', 1, 'Cross-market: mild macro headwind', 'cross_market'))

    # ── VIX (medium when spiking) ─────────────────────────────────────────
    if vix_move == 'FEAR_SPIKE':
        signals.append(Signal('BEARISH', 2,
            'VIX spiking -- fear elevated, risk-off environment',
            'cross_market'))
    elif vix_move == 'FEAR_CALMING':
        signals.append(Signal('BULLISH', 1, 'VIX falling -- fear receding, risk-on signal', 'cross_market'))
    elif vix_move == 'FEAR_RISING':
        signals.append(Signal('BEARISH', 1, 'VIX rising -- fear building', 'cross_market'))

    # ── DXY / Yields (minor) ──────────────────────────────────────────────
    if dxy_sig == 'DXY_HEADWIND':
        signals.append(Signal('BEARISH', 1, 'DXY rising -- dollar strength headwind for equities', 'cross_market'))
    elif dxy_sig == 'DXY_TAILWIND':
        signals.append(Signal('BULLISH', 1, 'DXY falling -- dollar weakness tailwind for equities', 'cross_market'))

    if yield_sig == 'YIELD_PRESSURE':
        signals.append(Signal('BEARISH', 1, 'Yield pressure -- rising rates headwind for growth', 'cross_market'))

    # ── NQ vs ES relative (minor) ─────────────────────────────────────────
    if nq_es_lbl == 'TECH_LEADING':
        signals.append(Signal('BULLISH', 1,
            'NQ leading ES -- tech breadth confirming, growth stocks in favor',
            'cross_market'))
    elif nq_es_lbl == 'TECH_LAGGING':
        signals.append(Signal('BEARISH', 1,
            'NQ lagging ES -- tech underperformance, quality rotation or risk-off signal',
            'cross_market'))

    return signals


def _participation_signals(part: dict) -> list[Signal]:
    """
    Standalone participation signals not already captured in structure signals.
    Breadth divergence and session-level confirmation are the main additions.
    """
    signals: list[Signal] = []

    breadth   = part.get('breadth_signal', 'UNKNOWN')
    sess_type = part.get('session_type', 'UNCERTAIN')
    rvol      = _safe((part.get('nq') or {}).get('rvol', 0.0))
    pvc       = (part.get('nq') or {}).get('price_vol_confirm', 'UNCERTAIN')
    spy_pct   = part.get('spy_pct')
    iwm_pct   = part.get('iwm_pct')

    # ── Breadth ───────────────────────────────────────────────────────────
    if breadth == 'BROAD_STRENGTH' and spy_pct and iwm_pct:
        signals.append(Signal('BULLISH', 1,
            f'Broad market strength -- SPY {spy_pct:+.2f}% and IWM {iwm_pct:+.2f}% both up',
            'participation'))
    elif breadth == 'BROAD_SELLING' and spy_pct and iwm_pct:
        signals.append(Signal('BEARISH', 1,
            f'Broad selling -- SPY {spy_pct:+.2f}% and IWM {iwm_pct:+.2f}% both down',
            'participation'))
    elif breadth == 'LARGE_CAP_LED':
        signals.append(Signal('BEARISH', 1,
            'Narrow breadth -- large-cap led, small caps lagging, market breadth is thin',
            'participation'))

    # ── Price-volume confirmation ─────────────────────────────────────────
    if pvc == 'DIVERGING':
        signals.append(Signal('NEUTRAL', 1,
            'Price-volume divergence -- price moving without volume support, possible absorption',
            'participation'))

    return signals


def _collect_all_signals(mr2: dict, ms_nq: dict, liq_nq: dict, cm: dict, part: dict) -> list[Signal]:
    return (
        _mr2_signals(mr2) +
        _structure_signals(ms_nq, part) +
        _liquidity_signals(liq_nq) +
        _cross_market_signals(cm) +
        _participation_signals(part)
    )


# ── Scoring and conflict detection ────────────────────────────────────────────

def _score_signals(signals: list[Signal]) -> tuple[int, int]:
    bull = sum(s.weight for s in signals if s.direction == 'BULLISH')
    bear = sum(s.weight for s in signals if s.direction == 'BEARISH')
    return bull, bear


def _detect_major_conflict(signals: list[Signal]) -> bool:
    """
    True if weight-2+ signals from different sources point in opposite directions.
    This is what CONTESTED state is built on: genuine disagreement at the major level.
    """
    major_bull_sources = {s.source for s in signals if s.direction == 'BULLISH' and s.weight >= 2}
    major_bear_sources = {s.source for s in signals if s.direction == 'BEARISH' and s.weight >= 2}
    # Conflict requires both sides to have major signals from different sources
    return bool(major_bull_sources and major_bear_sources)


# ── Thesis state determination ────────────────────────────────────────────────

def _determine_state(
    bull_score:    int,
    bear_score:    int,
    signals:       list[Signal],
    major_conflict: bool,
) -> str:
    """
    Derive thesis state from the weighted evidence.
    Order matters: specific structural patterns are checked before generic scoring.
    """
    struct_sigs = [s for s in signals if s.source == 'structure']
    liq_sigs    = [s for s in signals if s.source == 'liquidity']
    mr2_sigs    = [s for s in signals if s.source == 'market_reality']

    mr2_strong_bull = any(s.direction == 'BULLISH' and s.weight >= 3 for s in mr2_sigs)
    mr2_strong_bear = any(s.direction == 'BEARISH' and s.weight >= 3 for s in mr2_sigs)
    liq_strong_bear = any(s.direction == 'BEARISH' and s.weight >= 3 for s in liq_sigs)
    liq_strong_bull = any(s.direction == 'BULLISH' and s.weight >= 3 for s in liq_sigs)

    # ── ACCEPTANCE_DEVELOPING ─────────────────────────────────────────────
    # Structural breakout signal confirmed by participation (weight-3 bull from structure)
    # Requires: no strong opposing liquidity signal, bull score substantially dominant
    for s in struct_sigs:
        if s.direction == 'BULLISH' and s.weight == 3 and 'acceptance' in s.label.lower():
            if not liq_strong_bear and bull_score > bear_score + 2:
                return 'ACCEPTANCE_DEVELOPING'

    # ── REJECTION_DEVELOPING ──────────────────────────────────────────────
    # Probe at level without participation (stop-run risk or rejection labels)
    # Requires: no strong MR2 bull opposing it, bear score substantially dominant
    for s in struct_sigs:
        if (s.direction == 'BEARISH' and s.weight >= 2 and
                any(kw in s.label.lower() for kw in ('stop-run', 'rejection', 'breakdown lacks', 'breakdown attempt'))):
            if not mr2_strong_bull and bear_score > bull_score + 2:
                return 'REJECTION_DEVELOPING'

    # ── CONTESTED ────────────────────────────────────────────────────────
    # Major intelligence layers from different sources directly disagree
    if major_conflict:
        return 'CONTESTED'

    # ── LIQUIDITY_SEEKING ────────────────────────────────────────────────
    # Clear asymmetric liquidity draw + directional consistency
    for s in liq_sigs:
        if s.weight == 3 and 'asymmetry' in s.label.lower():
            if s.direction == 'BEARISH' and bear_score >= bull_score:
                return 'LIQUIDITY_SEEKING'
            if s.direction == 'BULLISH' and bull_score >= bear_score:
                return 'LIQUIDITY_SEEKING'

    # ── Standard directional scoring ──────────────────────────────────────
    total = bull_score + bear_score
    if total == 0:
        return 'NEUTRAL'

    bull_ratio = bull_score / total

    if bull_ratio >= 0.65:
        return 'BULLISH'
    if bull_ratio <= 0.35:
        return 'BEARISH'
    if abs(bull_score - bear_score) >= 2:
        return 'TRANSITIONING'
    return 'NEUTRAL'


# ── Thesis sentence ───────────────────────────────────────────────────────────

def _generate_thesis(
    state:   str,
    signals: list[Signal],
    ms_nq:   dict,
    liq_nq:  dict,
    part:    dict,
) -> str:
    vs_pdh = ms_nq.get('price_vs_pdh', 'UNKNOWN')
    vs_pdl = ms_nq.get('price_vs_pdl', 'UNKNOWN')
    vs_pwh = ms_nq.get('price_vs_pwh', 'UNKNOWN')
    vs_pwl = ms_nq.get('price_vs_pwl', 'UNKNOWN')
    pdh    = ms_nq.get('pdh')
    pdl    = ms_nq.get('pdl')
    pwh    = ms_nq.get('pwh')
    pwl    = ms_nq.get('pwl')
    draw   = liq_nq.get('primary_draw') or {}
    u_above = liq_nq.get('untapped_above', 0)
    u_below = liq_nq.get('untapped_below', 0)
    bull_score, bear_score = _score_signals(signals)

    if state == 'ACCEPTANCE_DEVELOPING':
        if vs_pwh == 'ABOVE' and pwh:
            return (
                f'Market is developing acceptance above prior-week highs ({_fmt(pwh)}) -- '
                f'buyers following through with participation confirming the structural breakout'
            )
        if vs_pdh == 'ABOVE' and pdh:
            return (
                f'Market is developing acceptance above prior-day high ({_fmt(pdh)}) -- '
                f'structural breakout confirmed by participation quality'
            )
        return 'Market is developing acceptance at a key structural level -- buyers confirming the move with volume'

    if state == 'REJECTION_DEVELOPING':
        stop_run = any('stop-run' in s.label.lower() for s in signals if s.source == 'structure')
        if vs_pdh == 'ABOVE' and stop_run and pdh:
            return (
                f'Market broke above PDH ({_fmt(pdh)}) on weak participation -- '
                f'stop-run risk elevated, structural follow-through absent'
            )
        if vs_pdh == 'AT' and pdh:
            return (
                f'Market is probing prior-day high ({_fmt(pdh)}) on thin volume -- '
                f'sellers defending, rejection risk elevated'
            )
        if vs_pdl == 'AT' and pdl:
            return (
                f'Market is testing prior-day low ({_fmt(pdl)}) on declining volume -- '
                f'buyers absorbing, support likely to hold'
            )
        return 'Market is probing a structural level without participation confirmation -- rejection risk elevated'

    if state == 'CONTESTED':
        bull_major = [s for s in signals if s.direction == 'BULLISH' and s.weight >= 2]
        bear_major = [s for s in signals if s.direction == 'BEARISH' and s.weight >= 2]
        # Specific contested patterns
        has_stop_run = any('stop-run' in s.label.lower() for s in bear_major)
        has_liq_down = any(s.source == 'liquidity' and 'downside' in s.label.lower() for s in bear_major)
        has_liq_asym = any('asymmetry' in s.label.lower() for s in bear_major if s.source == 'liquidity')
        if vs_pdh == 'ABOVE' and (has_stop_run or has_liq_asym) and pdh:
            return (
                f'Market is above PDH ({_fmt(pdh)}) but conviction is absent -- '
                f'weak participation and downside liquidity draw suggest stop-run over genuine acceptance'
            )
        if vs_pwh == 'ABOVE' and has_liq_asym and pwh:
            return (
                f'Market is above PWH ({_fmt(pwh)}) against downside liquidity draw -- '
                f'structural breakout and liquidity picture are in direct conflict'
            )
        # Macro vs structure conflict
        cm_bear = any(s.source == 'cross_market' and s.direction == 'BEARISH' and s.weight >= 2 for s in bear_major)
        if cm_bear and vs_pdh == 'ABOVE' and pdh:
            return (
                f'Market holds above PDH ({_fmt(pdh)}) against macro headwinds -- '
                f'internal structure and macro backdrop are directly opposed'
            )
        # Generic
        b_lbl = bull_major[0].label[:55] if bull_major else 'bullish price action'
        r_lbl = bear_major[0].label[:55] if bear_major else 'bearish signals'
        return f'Market is contested -- {b_lbl} conflicts directly with {r_lbl}'

    if state == 'LIQUIDITY_SEEKING':
        d_lbl = draw.get('label', '?')
        d_px  = _fmt(draw.get('price'))
        if u_above == 0 and u_below > 0:
            return (
                f'Market structure is resolved; price is seeking remaining liquidity below -- '
                f'{d_lbl} ({d_px}) is the primary untapped target'
            )
        if u_below == 0 and u_above > 0:
            return (
                f'Market structure is resolved; price is seeking remaining liquidity above -- '
                f'{d_lbl} ({d_px}) is the primary untapped target'
            )
        d_side = draw.get('side', '')
        if d_side == 'BELOW':
            return f'Market is targeting liquidity below at {d_lbl} ({d_px}) -- directional bias aligns with downside draw'
        return f'Market is targeting liquidity above at {d_lbl} ({d_px}) -- directional bias aligns with upside draw'

    if state == 'BULLISH':
        if vs_pwh == 'ABOVE' and pwh:
            return (
                f'Market is trending higher through prior-week highs ({_fmt(pwh)}) -- '
                f'structure, participation, and cross-market signals aligned'
            )
        if vs_pdh == 'ABOVE' and pdh:
            return (
                f'Market is trending higher above prior-day high ({_fmt(pdh)}) -- '
                f'sellers cleared, all major intelligence signals aligned bullish'
            )
        return 'Market is in a confirmed uptrend -- structure, participation, and cross-market all aligned'

    if state == 'BEARISH':
        if vs_pwl == 'BELOW' and pwl:
            return (
                f'Market is under sustained selling pressure through prior-week lows ({_fmt(pwl)}) -- '
                f'sellers in full control'
            )
        if vs_pdl == 'BELOW' and pdl:
            return (
                f'Market is trading below prior-day low ({_fmt(pdl)}) -- '
                f'buyers absent, downside confirmed across intelligence layers'
            )
        return 'Market is under sustained selling pressure -- structure, participation, and macro all point lower'

    if state == 'TRANSITIONING':
        if bull_score > bear_score:
            lvl = _fmt(pdh) if pdh else '?'
            return (
                f'Market bias is shifting bullish -- early signals favor upside but conviction is building; '
                f'PDH ({lvl}) is the directional trigger'
            )
        lvl = _fmt(pdl) if pdl else '?'
        return (
            f'Market bias is shifting bearish -- early signals favor downside but conviction is building; '
            f'PDL ({lvl}) is the directional trigger'
        )

    # NEUTRAL
    if pdh and pdl:
        return (
            f'Market has no dominant directional thesis -- '
            f'rotating between PDH ({_fmt(pdh)}) and PDL ({_fmt(pdl)}) without conviction'
        )
    return 'Market has no dominant directional thesis -- intelligence layers are balanced'


# ── Conditional branch ────────────────────────────────────────────────────────

def _generate_condition(
    state:   str,
    signals: list[Signal],
    ms_nq:   dict,
    liq_nq:  dict,
) -> str:
    """What would change the current interpretation."""
    pdh   = ms_nq.get('pdh')
    pdl   = ms_nq.get('pdl')
    pwh   = ms_nq.get('pwh')
    pwl   = ms_nq.get('pwl')
    vs_pdh = ms_nq.get('price_vs_pdh', 'UNKNOWN')
    vs_pdl = ms_nq.get('price_vs_pdl', 'UNKNOWN')
    draw  = liq_nq.get('primary_draw') or {}
    near_a = liq_nq.get('nearest_above') or {}
    near_b = liq_nq.get('nearest_below') or {}
    bull_score, bear_score = _score_signals(signals)

    if state == 'ACCEPTANCE_DEVELOPING':
        lvl = _fmt(pdh if vs_pdh == 'ABOVE' else pwh)
        return (
            f'Acceptance strengthens if RVOL sustains above 1.0 through mid-session; '
            f'thesis fails if price closes back below {lvl}'
        )

    if state == 'REJECTION_DEVELOPING':
        if vs_pdh == 'ABOVE' and pdh:
            return (
                f'Rejection confirmed if price accepts back below PDH ({_fmt(pdh)}); '
                f'bull case reopens only if RVOL expands above 1.2 on renewed push above PDH'
            )
        draw_lbl = draw.get('label', '?')
        draw_px  = _fmt(draw.get('price'))
        return (
            f'Rejection deepens on acceptance below {draw_lbl} ({draw_px}); '
            f'watch for buyer reclaim at {_fmt(near_a.get("price") or pdh)} as invalidation'
        )

    if state == 'CONTESTED':
        if vs_pdh == 'ABOVE' and pdh:
            return (
                f'Contest resolves bullish if PDH ({_fmt(pdh)}) holds and RVOL expands above 1.0; '
                f'resolves bearish if price accepts back below PDH'
            )
        if pdh and pdl:
            return (
                f'Contest resolves on structural confirmation -- '
                f'acceptance above PDH ({_fmt(pdh)}) is bullish; acceptance below PDL ({_fmt(pdl)}) is bearish'
            )
        return (
            'Contest resolves on volume confirmation -- '
            'RVOL expanding above 1.0 in the direction of the move defines the winner'
        )

    if state == 'BULLISH':
        key_support = _fmt(pdl or near_b.get('price'))
        return (
            f'Bullish thesis continues while price holds above {key_support}; '
            f'watch for RVOL decline below 0.8 as early warning of conviction fade'
        )

    if state == 'BEARISH':
        key_resist = _fmt(pdh or near_a.get('price'))
        return (
            f'Bearish thesis continues while price holds below {key_resist}; '
            f'watch for VIX reversal or broad breadth improvement as early reversal warning'
        )

    if state == 'LIQUIDITY_SEEKING':
        d_lbl = draw.get('label', '?')
        d_px  = _fmt(draw.get('price'))
        d_side = draw.get('side', '')
        if d_side == 'BELOW':
            above_lbl = near_a.get('label') or ms_nq.get('pdh') and 'PDH' or 'nearest resistance'
            above_px  = _fmt(near_a.get('price') or ms_nq.get('pdh'))
            return (
                f'Target is {d_lbl} ({d_px}); '
                f'thesis fails if price reclaims {above_lbl} ({above_px}) with volume'
            )
        below_lbl = near_b.get('label') or ms_nq.get('pdl') and 'PDL' or 'nearest support'
        below_px  = _fmt(near_b.get('price') or ms_nq.get('pdl'))
        return (
            f'Target is {d_lbl} ({d_px}); '
            f'thesis fails if price breaks below {below_lbl} ({below_px}) with volume'
        )

    if state == 'TRANSITIONING':
        lean = 'bullish' if bull_score > bear_score else 'bearish'
        return (
            f'Transition signals {lean} -- RVOL expansion above 1.0 in the direction of the move confirms; '
            f'RVOL contraction signals the lean is fading'
        )

    # NEUTRAL
    if pdh and pdl:
        return (
            f'Thesis defines on break above PDH ({_fmt(pdh)}) or acceptance below PDL ({_fmt(pdl)}) with volume'
        )
    return 'Wait for structural level test with participation confirmation to define the thesis'


# ── Invalidation ──────────────────────────────────────────────────────────────

def _generate_invalidation(state: str, signals: list[Signal], ms_nq: dict, liq_nq: dict) -> str:
    pdh    = ms_nq.get('pdh')
    pdl    = ms_nq.get('pdl')
    pwh    = ms_nq.get('pwh')
    vs_pdh = ms_nq.get('price_vs_pdh', 'UNKNOWN')
    vs_pdl = ms_nq.get('price_vs_pdl', 'UNKNOWN')
    near_a = liq_nq.get('nearest_above') or {}
    near_b = liq_nq.get('nearest_below') or {}
    bull_score, bear_score = _score_signals(signals)

    if state in ('BULLISH', 'ACCEPTANCE_DEVELOPING'):
        if vs_pdh == 'ABOVE' and pdh:
            return f'Acceptance back below PDH ({_fmt(pdh)}) would invalidate the bullish thesis'
        if pdl:
            return f'Acceptance below PDL ({_fmt(pdl)}) would invalidate the bullish thesis'
        return 'Sustained break below session lows would invalidate the bullish thesis'

    if state in ('BEARISH', 'REJECTION_DEVELOPING', 'LIQUIDITY_SEEKING'):
        if vs_pdl == 'BELOW' and pdl:
            return f'Acceptance back above PDL ({_fmt(pdl)}) would invalidate the bearish thesis'
        if pdh:
            return f'Acceptance above PDH ({_fmt(pdh)}) would invalidate the bearish thesis'
        return 'Sustained push above session highs would invalidate the bearish thesis'

    if state == 'CONTESTED':
        if vs_pdh == 'ABOVE' and pdh:
            return (
                f'Close above PDH ({_fmt(pdh)}) on RVOL > 1.0 resolves the bull case; '
                f'acceptance below PDH resolves the bear case'
            )
        if pdh and pdl:
            return (
                f'Bull case invalidated by acceptance below PDH ({_fmt(pdh)}); '
                f'bear case invalidated by close above PDL ({_fmt(pdl)})'
            )
        return 'Sustained directional move with volume expansion resolves the contested state'

    if state == 'TRANSITIONING':
        if bull_score > bear_score:
            return f'Bullish transition invalidated by acceptance below PDL ({_fmt(pdl)})' if pdl else 'Bullish transition invalidated by sustained break below session lows'
        return f'Bearish transition invalidated by acceptance above PDH ({_fmt(pdh)})' if pdh else 'Bearish transition invalidated by sustained push above session highs'

    # NEUTRAL
    if pdh and pdl:
        return f'Break above PDH ({_fmt(pdh)}) or acceptance below PDL ({_fmt(pdl)}) would define the thesis'
    return 'Structural level test with volume would define the thesis'


# ── Driver, confidence, risk ──────────────────────────────────────────────────

def _determine_primary_driver(signals: list[Signal]) -> str:
    source_weights: dict[str, int] = {}
    for s in signals:
        if s.direction != 'NEUTRAL':
            source_weights[s.source] = source_weights.get(s.source, 0) + s.weight
    if not source_weights:
        return 'UNKNOWN'
    top = max(source_weights, key=lambda k: source_weights[k])
    return {
        'market_reality': 'Market Reality',
        'structure':      'Structure',
        'liquidity':      'Liquidity',
        'cross_market':   'Cross-Market',
        'participation':  'Participation',
    }.get(top, top)


def _score_confidence(
    state:          str,
    bull_score:     int,
    bear_score:     int,
    major_conflict: bool,
) -> str:
    if state == 'NEUTRAL':
        return 'LOW'
    if state == 'CONTESTED':
        # We are confident in the contested read -- but not in a direction
        return 'MEDIUM'
    total = bull_score + bear_score
    if total == 0:
        return 'LOW'
    dominant = max(bull_score, bear_score)
    ratio = dominant / total
    if ratio >= 0.75 and total >= 6:
        return 'HIGH'
    if ratio >= 0.60 or total >= 4:
        return 'MEDIUM'
    return 'LOW'


def _score_risk(macro_risk: str, signals: list[Signal]) -> str:
    vix_spike = any('VIX spiking' in s.label for s in signals)
    n_bear_major = sum(1 for s in signals if s.direction == 'BEARISH' and s.weight >= 2)
    if macro_risk in ('EXTREME', 'HIGH') or vix_spike:
        return 'HIGH'
    if macro_risk == 'ELEVATED' or n_bear_major >= 3:
        return 'MEDIUM'
    return 'LOW'


# ── Evidence classification ───────────────────────────────────────────────────

def _classify_evidence(
    state:   str,
    signals: list[Signal],
    bull_score: int,
    bear_score: int,
) -> tuple[list[str], list[str]]:
    """
    Classify signals as confirming or conflicting evidence.

    For CONTESTED state: confirming = bull-case signals, conflicting = bear-case signals.
    For directional states: confirming = signals in thesis direction, conflicting = opposing.
    """
    if state == 'CONTESTED':
        confirming  = [f'Bull case: {s.label}' for s in signals if s.direction == 'BULLISH' and s.weight >= 2]
        conflicting = [f'Bear case: {s.label}' for s in signals if s.direction == 'BEARISH' and s.weight >= 2]
        return confirming, conflicting

    thesis_dir = (
        'BULLISH' if state in ('BULLISH', 'ACCEPTANCE_DEVELOPING') or
                    (state == 'TRANSITIONING' and bull_score > bear_score) or
                    (state == 'LIQUIDITY_SEEKING' and bull_score >= bear_score)
        else 'BEARISH' if state in ('BEARISH', 'REJECTION_DEVELOPING') or
                    (state == 'TRANSITIONING' and bear_score > bull_score) or
                    (state == 'LIQUIDITY_SEEKING' and bear_score > bull_score)
        else None
    )

    if thesis_dir is None:
        # NEUTRAL -- show all non-neutral signals as confirming the neutral read
        confirming  = [s.label for s in signals if s.direction != 'NEUTRAL' and s.weight >= 1]
        conflicting = []
        return confirming, conflicting

    confirming  = [s.label for s in signals if s.direction == thesis_dir]
    conflicting = [s.label for s in signals if s.direction not in (thesis_dir, 'NEUTRAL')]
    return confirming, conflicting


# ── Main compute ──────────────────────────────────────────────────────────────

def compute_synthesis() -> dict:
    """
    Evidence-first market synthesis. No network calls. Never raises.
    Called from process_finnhub_cycle() after all other intelligence engines.
    """
    try:
        mr2  = _read_json(_MR2_FILE)
        cm   = _read_json(_CM_FILE)
        ms   = _read_json(_MS_FILE)
        part = _read_json(_P_FILE)
        liq  = _read_json(_LIQ_FILE)
        risk = _read_json(_RISK_FILE)

        ms_nq  = ms.get('nq', {})
        liq_nq = liq.get('nq', {})
        macro_risk = risk.get('macro_risk', 'LOW')

        signals = _collect_all_signals(mr2, ms_nq, liq_nq, cm, part)

        bull_score, bear_score = _score_signals(signals)
        major_conflict = _detect_major_conflict(signals)
        state = _determine_state(bull_score, bear_score, signals, major_conflict)

        thesis      = _generate_thesis(state, signals, ms_nq, liq_nq, part)
        condition   = _generate_condition(state, signals, ms_nq, liq_nq)
        invalidation = _generate_invalidation(state, signals, ms_nq, liq_nq)
        driver      = _determine_primary_driver(signals)
        confidence  = _score_confidence(state, bull_score, bear_score, major_conflict)
        risk_level  = _score_risk(macro_risk, signals)

        confirming, conflicting = _classify_evidence(state, signals, bull_score, bear_score)

        state_obj = {
            'market_thesis':        thesis,
            'thesis_state':         state,
            'thesis_condition':     condition,
            'primary_driver':       driver,
            'confirming_evidence':  confirming,
            'conflicting_evidence': conflicting,
            'invalidation':         invalidation,
            'confidence':           confidence,
            'risk_level':           risk_level,
            'meta': {
                'bull_score':     bull_score,
                'bear_score':     bear_score,
                'major_conflict': major_conflict,
                'signal_count':   len(signals),
                'macro_risk':     macro_risk,
            },
            'last_updated': _utc_iso(),
        }

        # Detect thesis state change — emit INTELLIGENCE event when state flips
        prev_state = ''
        try:
            if _SYN_FILE.exists():
                _prev = json.loads(_SYN_FILE.read_text(encoding='utf-8'))
                prev_state = _prev.get('thesis_state', '')
        except Exception:
            pass

        _SYN_FILE.write_text(json.dumps(state_obj, indent=2, default=str), encoding='utf-8')

        if state != prev_state and prev_state:
            try:
                session = ''
                try:
                    from zoneinfo import ZoneInfo as _ZI
                    from core.config import now_ny as _nny
                    _h = _nny().hour
                    if _h < 4:    session = 'ASIA'
                    elif _h < 9:  session = 'LONDON'
                    elif _h < 11: session = 'NY_OPEN'
                    elif _h < 13: session = 'NY_AM'
                    else:         session = 'NY_PM'
                except Exception:
                    pass
                _emit_intelligence_event('SYNTHESIS_UPDATE', {
                    'thesis_state':         state,
                    'thesis_state_prev':    prev_state,
                    'thesis':               thesis,
                    'confidence':           confidence,
                    'condition':            condition,
                    'primary_driver':       driver,
                    'confirming_evidence':  confirming,
                    'conflicting_evidence': conflicting,
                    'bull_score':           bull_score,
                    'bear_score':           bear_score,
                    'major_conflict':       major_conflict,
                    'session':              session,
                })
                print(f'[synthesis] state change: {prev_state} -> {state} (event emitted)')
            except Exception as _ee:
                print(f'[synthesis] event emit error: {_ee}')

        print(
            f'[synthesis] state={state} | bull={bull_score} bear={bear_score} '
            f'conflict={major_conflict} | conf={confidence} risk={risk_level}'
        )
        return state_obj

    except Exception as exc:
        print(f'[synthesis] compute error: {exc}')
        return _neutral_state()


def _neutral_state() -> dict:
    return {
        'market_thesis':        'Market intelligence data unavailable.',
        'thesis_state':         'NEUTRAL',
        'thesis_condition':     'Insufficient data.',
        'primary_driver':       'UNKNOWN',
        'confirming_evidence':  [],
        'conflicting_evidence': [],
        'invalidation':         'Insufficient data.',
        'confidence':           'LOW',
        'risk_level':           'LOW',
        'meta':                 {},
        'last_updated':         _utc_iso(),
    }


# ── Load / format ─────────────────────────────────────────────────────────────

def load_synthesis() -> dict:
    data = _read_json(_SYN_FILE)
    return data if data else _neutral_state()


def format_for_prompt(syn: dict) -> str:
    """Full synthesis block for the Claude evaluation prompt."""
    thesis = syn.get('market_thesis', '')
    if not thesis or thesis.startswith('Market intelligence data'):
        return ''

    state     = syn.get('thesis_state', 'UNKNOWN')
    condition = syn.get('thesis_condition', '')
    driver    = syn.get('primary_driver', '?')
    conf      = syn.get('confidence', '?')
    risk      = syn.get('risk_level', '?')
    inv       = syn.get('invalidation', '')

    conf_lines = syn.get('confirming_evidence', [])
    cfl_lines  = syn.get('conflicting_evidence', [])

    # Label the evidence columns by state
    if state == 'CONTESTED':
        conf_hdr = 'Bull case:'
        cfl_hdr  = 'Bear case:'
    else:
        conf_hdr = 'Confirms:'
        cfl_hdr  = 'Conflicts:'

    lines = [
        '=== MARKET SYNTHESIS ===',
        f'State:      {state}',
        f'Thesis:     {thesis}',
        f'Driver:     {driver}',
        f'Confidence: {conf}  |  Risk: {risk}',
    ]
    if condition:
        lines.append(f'Condition:  {condition}')
    if conf_lines:
        lines.append(conf_hdr)
        lines.extend(f'    + {e}' for e in conf_lines)
    if cfl_lines:
        lines.append(cfl_hdr)
        lines.extend(f'    - {e}' for e in cfl_lines)
    if inv:
        lines.append(f'Invalidation: {inv}')
    lines.append('=== END SYNTHESIS ===')
    return '\n'.join(lines)


def format_for_assistant(syn: dict) -> str:
    """Compact single-line synthesis for the assistant session context."""
    thesis  = syn.get('market_thesis', '?')
    state   = syn.get('thesis_state', '?')
    driver  = syn.get('primary_driver', '?')
    conf    = syn.get('confidence', '?')
    risk    = syn.get('risk_level', '?')
    cond    = syn.get('thesis_condition', '')
    n_conf  = len(syn.get('confirming_evidence', []))
    n_cfl   = len(syn.get('conflicting_evidence', []))
    cond_s  = f' | cond: {cond[:70]}' if cond else ''
    return (
        f'SYNTHESIS [{state}]: "{thesis}" | '
        f'driver={driver} conf={conf} risk={risk} '
        f'[{n_conf} confirm/{n_cfl} conflict]{cond_s}'
    )
