"""
engines/synthesis.py --Market Synthesis Layer.

Consumes all five Level 1 intelligence engines and answers one question:

    "What is the market trying to do?"

Not "What setup is present?"
Not "Should I buy or sell?"

Market interpretation only. Analyst's internal thought process.
Compact, actionable, deterministic.

Critical architecture rule:
  This engine NEVER reads PROS, ORB, or any strategy signal.
  Intelligence must exist before strategy. Strategy consumes intelligence.
  If PROS and ORB were deleted tomorrow, this engine must still work correctly.

Inputs consumed:
  donna_market_reality_v2.json   --direction, severity, key levels, weekly structure
  donna_cross_market.json        --DXY, yields, gold, BTC, NQ/ES spread, macro bias
  donna_market_structure.json    --PDH/PDL, ONH/ONL, PWH/PWL, monthly open, gap
  donna_participation.json       --RVOL, session type, breadth, volume confirmation
  donna_liquidity.json           --primary draw, swept/untapped levels, nearest targets
  donna_risk_state.json          --macro_risk level

Outputs:
  market_thesis       One sentence: what is the market attempting?
  primary_driver      What is most responsible: Liquidity / Structure /
                      Cross-Market / Participation / Macro
  confirming_evidence List of signals supporting the thesis
  conflicting_evidence List of signals working against the thesis
  invalidation        What would make the thesis wrong
  confidence          LOW / MEDIUM / HIGH
  risk_level          LOW / MEDIUM / HIGH

No new APIs. No new data sources. No strategy references. No execution changes.
Called from process_finnhub_cycle() after all other intelligence engines.
Output: donna_synthesis.json
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from core.config import (
    SYNTHESIS_FILE         as _SYN_FILE,
    MARKET_REALITY_V2_FILE as _MR2_FILE,
    CROSS_MARKET_FILE      as _CM_FILE,
    MARKET_STRUCTURE_FILE  as _MS_FILE,
    PARTICIPATION_FILE     as _P_FILE,
    LIQUIDITY_FILE         as _LIQ_FILE,
    RISK_STATE_FILE        as _RISK_FILE,
)

_NY_TZ = ZoneInfo('America/New_York')


# ── Helpers ───────────────────────────────────────────────────────────────────

def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe(v, default: float = 0.0) -> float:
    try:
        f = float(v)
        return f if math.isfinite(f) else default
    except Exception:
        return default


def _eff_direction(direction: str, liq_nq: dict) -> str:
    """
    Effective thesis direction for evidence classification.
    When MR2 direction is NEUTRAL, fall back to the liquidity picture:
    all untapped below -> BEARISH bias; all untapped above -> BULLISH bias.
    Evidence is classified relative to this effective direction so signals
    confirm or conflict with what the market is actually attempting.
    """
    if direction in ('BULLISH', 'BEARISH'):
        return direction
    u_above = liq_nq.get('untapped_above', 0)
    u_below = liq_nq.get('untapped_below', 0)
    if u_above == 0 and u_below > 0:
        return 'BEARISH'
    if u_below == 0 and u_above > 0:
        return 'BULLISH'
    draw_side = (liq_nq.get('primary_draw') or {}).get('side', '')
    if draw_side == 'BELOW':
        return 'BEARISH'
    if draw_side == 'ABOVE':
        return 'BULLISH'
    return 'NEUTRAL'


def _read_json(path: Path) -> dict:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        pass
    return {}


def _fmt(v) -> str:
    """Format a price level for display."""
    if v is None:
        return '?'
    try:
        return f'{float(v):.0f}'
    except Exception:
        return str(v)


# ── Thesis determination ──────────────────────────────────────────────────────

def _determine_thesis(
    direction:  str,
    severity:   str,
    nq_pct:     float,
    ms_nq:      dict,
    liq_nq:     dict,
    cm:         dict,
    part:       dict,
) -> str:
    """
    Determine the one-sentence market thesis.

    Priority hierarchy (highest match wins):
      1. Trend day with structural breakout
      2. Repricing against macro (notable divergence)
      3. Out of prior-week range
      4. Gap behavior
      5. All untapped liquidity on one side
      6. Testing key level (AT)
      7. Outside prior-day range
      8. Inside prior-day range with session type context
      9. Default drift
    """
    vs_pdh  = ms_nq.get('price_vs_pdh', 'UNKNOWN')
    vs_pdl  = ms_nq.get('price_vs_pdl', 'UNKNOWN')
    vs_pwh  = ms_nq.get('price_vs_pwh', 'UNKNOWN')
    vs_pwl  = ms_nq.get('price_vs_pwl', 'UNKNOWN')
    vs_mo   = ms_nq.get('price_vs_monthly', 'UNKNOWN')
    gap     = ms_nq.get('gap_signal', 'UNKNOWN')
    gap_pct = _safe(ms_nq.get('gap_pct', 0.0))
    pdh     = ms_nq.get('pdh')
    pdl     = ms_nq.get('pdl')
    pwh     = ms_nq.get('pwh')
    pwl     = ms_nq.get('pwl')

    draw    = liq_nq.get('primary_draw') or {}
    u_above = liq_nq.get('untapped_above', 0)
    u_below = liq_nq.get('untapped_below', 0)
    near_b  = liq_nq.get('nearest_below') or {}
    near_a  = liq_nq.get('nearest_above') or {}

    sess_type  = part.get('session_type', 'UNCERTAIN')
    part_bias  = part.get('participation_bias', 'UNKNOWN')
    rvol_label = (part.get('nq') or {}).get('rvol_label', 'UNCERTAIN')

    cm_bias    = cm.get('cross_market_bias', 'NEUTRAL')
    is_bull    = direction == 'BULLISH'
    is_bear    = direction == 'BEARISH'
    strong     = severity in ('STRONG', 'MODERATE')

    # ── 1. Trend day with structural breakout ─────────────────────────────
    if sess_type == 'TREND_DAY' and part_bias == 'STRONG':
        if is_bull and vs_pwh == 'ABOVE':
            return (
                f'Market is trending higher through prior-week highs ({_fmt(pwh)}) '
                f'on elevated participation'
            )
        if is_bear and vs_pwl == 'BELOW':
            return (
                f'Market is trending lower through prior-week lows ({_fmt(pwl)}) '
                f'on elevated participation'
            )
        if is_bull and vs_pdh == 'ABOVE':
            return (
                f'Market is trending higher above prior-day high ({_fmt(pdh)}) '
                f'with confirming volume'
            )
        if is_bear and vs_pdl == 'BELOW':
            return (
                f'Market is trending lower below prior-day low ({_fmt(pdl)}) '
                f'with confirming volume'
            )
        if is_bull:
            return 'Market is in a strong uptrend -- elevated volume confirming directional move'
        if is_bear:
            return 'Market is in a strong downtrend -- elevated volume confirming directional move'

    # ── 2. Repricing against macro (notable divergence) ───────────────────
    macro_bearish = cm_bias in ('BEARISH_PRESSURE', 'MILD_HEADWIND')
    macro_bullish = cm_bias in ('BULLISH_SUPPORT', 'MILD_TAILWIND')
    if is_bull and macro_bearish and strong:
        return 'Market is repricing higher despite macro headwinds -- internal strength leading'
    if is_bear and macro_bullish and strong:
        return 'Market is repricing lower despite macro tailwinds -- internal weakness dominant'

    # ── 3. Outside prior-week range ───────────────────────────────────────
    if vs_pwh == 'ABOVE' and is_bull:
        return f'Market is attempting acceptance above prior-week highs ({_fmt(pwh)})'
    if vs_pwl == 'BELOW' and is_bear:
        return f'Market is attempting acceptance below prior-week lows ({_fmt(pwl)})'
    if vs_pwh == 'AT':
        return f'Market is testing prior-week high ({_fmt(pwh)}) -- acceptance extends the trend'
    if vs_pwl == 'AT':
        return f'Market is testing prior-week low ({_fmt(pwl)}) -- acceptance extends the downtrend'

    # ── 4. Gap behavior ───────────────────────────────────────────────────
    if gap == 'GAP_UP':
        if is_bull:
            return (
                f'Market gapped up ({gap_pct:+.2f}%) and is holding --'
                f'bulls defending the gap'
            )
        elif is_bear:
            return (
                f'Market gapped up ({gap_pct:+.2f}%) but is fading --'
                f'potential gap fill toward prior close'
            )
    if gap == 'GAP_DOWN':
        if is_bear:
            return (
                f'Market gapped down ({gap_pct:+.2f}%) and is pressing --'
                f'sellers in control post-gap'
            )
        elif is_bull:
            return (
                f'Market gapped down ({gap_pct:+.2f}%) but is recovering --'
                f'potential gap fill toward prior close'
            )

    # ── 5. All untapped liquidity on one side ─────────────────────────────
    if u_above == 0 and u_below > 0 and draw:
        return (
            f'Market is seeking remaining liquidity below -- '
            f'{draw.get("label","?")} ({_fmt(draw.get("price"))}) is the primary untapped target'
        )
    if u_below == 0 and u_above > 0 and draw:
        return (
            f'Market is seeking remaining liquidity above -- '
            f'{draw.get("label","?")} ({_fmt(draw.get("price"))}) is the primary untapped target'
        )

    # ── 6. Testing key level ──────────────────────────────────────────────
    if vs_pdh == 'AT':
        return (
            f'Market is testing prior-day high ({_fmt(pdh)}) --'
            f'acceptance above continues upside, rejection targets PDL'
        )
    if vs_pdl == 'AT':
        return (
            f'Market is testing prior-day low ({_fmt(pdl)}) --'
            f'acceptance below extends downside, rejection targets PDH'
        )

    # ── 7. Outside prior-day range (but inside prior week) ────────────────
    if vs_pdh == 'ABOVE' and is_bull:
        return (
            f'Market is trading above prior-day high ({_fmt(pdh)}) --'
            f'sellers cleared, upside liquidity in focus'
        )
    if vs_pdl == 'BELOW' and is_bear:
        return (
            f'Market is trading below prior-day low ({_fmt(pdl)}) --'
            f'buyers absent, downside liquidity in focus'
        )

    # ── 8. Inside prior-day range ─────────────────────────────────────────
    if sess_type in ('RANGE_DAY', 'LOW_CONVICTION') or part_bias == 'WEAK':
        return 'Market is rotating inside prior-day value -- no directional conviction'
    if is_bull and vs_pdh == 'BELOW':
        return (
            f'Market is drifting higher inside prior-day range --'
            f'PDH ({_fmt(pdh)}) is the next structural target above'
        )
    if is_bear and vs_pdl == 'ABOVE':
        return (
            f'Market is drifting lower inside prior-day range --'
            f'PDL ({_fmt(pdl)}) is the next structural target below'
        )
    if draw:
        d_side = draw.get('side', '')
        d_lbl  = draw.get('label', '?')
        d_px   = _fmt(draw.get('price'))
        if d_side == 'BELOW':
            return f'Market is rotating lower -- primary liquidity draw at {d_lbl} ({d_px})'
        if d_side == 'ABOVE':
            return f'Market is rotating higher -- primary liquidity draw at {d_lbl} ({d_px})'

    # ── 9. Default ────────────────────────────────────────────────────────
    if direction == 'NEUTRAL':
        return 'Market is in balance -- no dominant directional theme'
    return f'Market is in {direction.lower()} drift -- structure is developing'


# ── Primary driver ────────────────────────────────────────────────────────────

def _determine_driver(
    direction:  str,
    ms_nq:      dict,
    liq_nq:     dict,
    cm:         dict,
    part:       dict,
    macro_risk: str,
) -> str:
    """
    Identify the single most responsible factor for the current market thesis.
    """
    cm_bias    = cm.get('cross_market_bias', 'NEUTRAL')
    sess_type  = part.get('session_type', 'UNCERTAIN')
    rvol_label = (part.get('nq') or {}).get('rvol_label', 'UNCERTAIN')
    u_above    = liq_nq.get('untapped_above', 0)
    u_below    = liq_nq.get('untapped_below', 0)
    gap        = ms_nq.get('gap_signal', 'UNKNOWN')
    vs_pwh     = ms_nq.get('price_vs_pwh', 'UNKNOWN')
    vs_pwl     = ms_nq.get('price_vs_pwl', 'UNKNOWN')

    # Score each driver
    scores: dict[str, int] = {
        'Liquidity':      0,
        'Structure':      0,
        'Cross-Market':   0,
        'Participation':  0,
        'Macro':          0,
    }

    # Liquidity: clear asymmetric draw
    if u_above == 0 and u_below >= 2:
        scores['Liquidity'] += 3
    elif u_below == 0 and u_above >= 2:
        scores['Liquidity'] += 3
    elif u_above == 0 and u_below == 1:
        scores['Liquidity'] += 2
    draw = liq_nq.get('primary_draw') or {}
    if draw and abs(_safe(draw.get('distance_pts', 999))) < 80:
        scores['Liquidity'] += 2     # nearby draw is magnetic

    # Structure: outside prior-week range or gap
    if vs_pwh in ('ABOVE', 'AT') or vs_pwl in ('BELOW', 'AT'):
        scores['Structure'] += 3
    if gap in ('GAP_UP', 'GAP_DOWN'):
        scores['Structure'] += 2

    # Cross-Market: strong non-neutral macro backdrop
    if cm_bias in ('BULLISH_SUPPORT', 'BEARISH_PRESSURE'):
        scores['Cross-Market'] += 3
    elif cm_bias in ('MILD_TAILWIND', 'MILD_HEADWIND'):
        scores['Cross-Market'] += 1

    # Participation: trend day with elevated volume
    if sess_type == 'TREND_DAY' and rvol_label in ('HIGH', 'ABOVE_AVERAGE'):
        scores['Participation'] += 3
    elif sess_type == 'HIGH_PARTICIPATION':
        scores['Participation'] += 2

    # Macro: risk state elevated
    if macro_risk in ('EXTREME', 'HIGH'):
        scores['Macro'] += 3
    elif macro_risk == 'ELEVATED':
        scores['Macro'] += 1

    return max(scores, key=lambda k: scores[k])


# ── Evidence collection ───────────────────────────────────────────────────────

def _collect_evidence(
    direction: str,
    mr2:       dict,
    ms_nq:     dict,
    liq_nq:    dict,
    cm:        dict,
    part:      dict,
) -> tuple[list[str], list[str]]:
    """
    Return (confirming_evidence, conflicting_evidence).
    Each item is a concise observation string.
    A signal confirms the thesis if it aligns with direction.
    A signal conflicts if it works against the stated direction.
    """
    confirming: list[str] = []
    conflicting: list[str] = []

    # Use effective direction for evidence classification.
    # When MR2 reports NEUTRAL, the liquidity picture determines thesis bias.
    eff_dir = _eff_direction(direction, liq_nq)
    is_bull = eff_dir == 'BULLISH'
    is_bear = eff_dir == 'BEARISH'

    nq_pct     = _safe(mr2.get('nq_pct', 0.0))
    weekly_str = mr2.get('weekly_structure', 'UNKNOWN')
    vix_move   = cm.get('vix_move', 'VIX_STABLE')
    cm_bias    = cm.get('cross_market_bias', 'NEUTRAL')
    dxy_sig    = cm.get('dxy_signal', 'DXY_NEUTRAL')
    yield_sig  = cm.get('yield_signal', 'YIELD_NEUTRAL')
    nq_es_lbl  = cm.get('nq_vs_es_label', 'ALIGNED')

    vs_pdh  = ms_nq.get('price_vs_pdh', 'UNKNOWN')
    vs_pdl  = ms_nq.get('price_vs_pdl', 'UNKNOWN')
    vs_pwh  = ms_nq.get('price_vs_pwh', 'UNKNOWN')
    vs_pwl  = ms_nq.get('price_vs_pwl', 'UNKNOWN')
    vs_mo   = ms_nq.get('price_vs_monthly', 'UNKNOWN')
    gap     = ms_nq.get('gap_signal', 'UNKNOWN')
    pdh     = ms_nq.get('pdh')
    pdl     = ms_nq.get('pdl')
    pwh     = ms_nq.get('pwh')
    pwl     = ms_nq.get('pwl')

    draw    = liq_nq.get('primary_draw') or {}
    u_above = liq_nq.get('untapped_above', 0)
    u_below = liq_nq.get('untapped_below', 0)
    s_above = liq_nq.get('swept_above', 0)

    sess_type  = part.get('session_type', 'UNCERTAIN')
    part_bias  = part.get('participation_bias', 'UNKNOWN')
    rvol       = _safe((part.get('nq') or {}).get('rvol', 0.0))
    rvol_label = (part.get('nq') or {}).get('rvol_label', 'UNCERTAIN')
    pvc        = (part.get('nq') or {}).get('price_vol_confirm', 'UNCERTAIN')
    breadth    = part.get('breadth_signal', 'UNKNOWN')
    spy_pct    = part.get('spy_pct')
    iwm_pct    = part.get('iwm_pct')

    # ── MR2 evidence ─────────────────────────────────────────────────────
    if abs(nq_pct) >= 0.1:
        label = f'NQ {nq_pct:+.2f}% vs prior close'
        if (is_bull and nq_pct > 0) or (is_bear and nq_pct < 0):
            confirming.append(label)
        else:
            conflicting.append(label)

    if weekly_str in ('BULL_TREND',) and is_bull:
        confirming.append(f'Weekly structure: {weekly_str}')
    elif weekly_str in ('BEAR_TREND',) and is_bear:
        confirming.append(f'Weekly structure: {weekly_str}')
    elif weekly_str in ('BULL_TREND',) and is_bear:
        conflicting.append(f'Weekly structure: {weekly_str} (opposing)')
    elif weekly_str in ('BEAR_TREND',) and is_bull:
        conflicting.append(f'Weekly structure: {weekly_str} (opposing)')

    # ── Structure evidence ────────────────────────────────────────────────
    if vs_pdh == 'ABOVE' and pdh:
        ev = f'Trading above prior-day high ({_fmt(pdh)})'
        (confirming if is_bull else conflicting).append(ev)
    if vs_pdl == 'BELOW' and pdl:
        ev = f'Trading below prior-day low ({_fmt(pdl)})'
        (confirming if is_bear else conflicting).append(ev)
    if vs_pwh == 'ABOVE' and pwh:
        ev = f'Above prior-week high ({_fmt(pwh)}) -- major structural breakout'
        (confirming if is_bull else conflicting).append(ev)
    if vs_pwl == 'BELOW' and pwl:
        ev = f'Below prior-week low ({_fmt(pwl)}) -- major structural breakdown'
        (confirming if is_bear else conflicting).append(ev)
    if gap == 'GAP_UP':
        (confirming if is_bull else conflicting).append(
            f'Gap up ({ms_nq.get("gap_pct", 0):+.2f}%) -- opens above prior close'
        )
    if gap == 'GAP_DOWN':
        (confirming if is_bear else conflicting).append(
            f'Gap down ({ms_nq.get("gap_pct", 0):+.2f}%) -- opens below prior close'
        )
    if vs_mo == 'ABOVE' and is_bull:
        confirming.append('Trading above monthly open -- monthly bias bullish')
    elif vs_mo == 'BELOW' and is_bear:
        confirming.append('Trading below monthly open -- monthly bias bearish')
    elif vs_mo == 'ABOVE' and is_bear:
        conflicting.append('Trading above monthly open (opposing bearish thesis)')
    elif vs_mo == 'BELOW' and is_bull:
        conflicting.append('Trading below monthly open (opposing bullish thesis)')

    # ── Liquidity evidence ────────────────────────────────────────────────
    if s_above >= 1 and is_bull:
        confirming.append(f'{s_above} level(s) above swept -- upside resistance cleared')
    elif s_above >= 1 and is_bear:
        conflicting.append(f'{s_above} level(s) above swept -- upside resistance already tested')
    if u_above == 0 and u_below > 0:
        ev = f'No untapped levels above -- {u_below} untapped below, draw is lower'
        (confirming if is_bear else conflicting).append(ev)
    if u_below == 0 and u_above > 0:
        ev = f'No untapped levels below -- {u_above} untapped above, draw is higher'
        (confirming if is_bull else conflicting).append(ev)
    if draw and draw.get('label'):
        d_pts = _safe(draw.get('distance_pts', 0.0))
        d_lbl = draw.get('label', '?')
        d_side = draw.get('side', '')
        if (is_bull and d_side == 'ABOVE') or (is_bear and d_side == 'BELOW'):
            confirming.append(
                f'Primary draw {d_lbl} ({d_pts:+.0f}pts) aligns with direction'
            )
        elif d_side:
            conflicting.append(
                f'Primary draw {d_lbl} ({d_pts:+.0f}pts) pulls against thesis'
            )

    # ── Cross-market evidence ─────────────────────────────────────────────
    if cm_bias in ('BULLISH_SUPPORT', 'MILD_TAILWIND'):
        (confirming if is_bull else conflicting).append(
            f'Cross-market: {cm_bias}'
        )
    elif cm_bias in ('BEARISH_PRESSURE', 'MILD_HEADWIND'):
        (confirming if is_bear else conflicting).append(
            f'Cross-market: {cm_bias}'
        )
    if dxy_sig == 'DXY_HEADWIND':
        (conflicting if is_bull else confirming).append('DXY rising (equity headwind)')
    if yield_sig == 'YIELD_PRESSURE':
        (conflicting if is_bull else confirming).append('Yield pressure (growth headwind)')
    if vix_move == 'FEAR_SPIKE':
        (conflicting if is_bull else confirming).append('VIX spiking (fear elevated)')
    elif vix_move == 'FEAR_CALMING':
        (confirming if is_bull else conflicting).append('VIX falling (risk-on signal)')
    if nq_es_lbl == 'TECH_LEADING' and is_bull:
        confirming.append('NQ leading ES -- tech breadth confirming')
    elif nq_es_lbl == 'TECH_LAGGING' and is_bull:
        conflicting.append('NQ lagging ES -- tech underperformance')

    # ── Participation evidence ────────────────────────────────────────────
    if sess_type == 'TREND_DAY' and rvol_label in ('HIGH', 'ABOVE_AVERAGE'):
        ev = f'TREND_DAY -- RVOL {rvol:.1f}x, volume confirming move'
        (confirming if part_bias == 'STRONG' else conflicting).append(ev)
    elif sess_type == 'LOW_CONVICTION':
        conflicting.append(f'LOW_CONVICTION session --RVOL {rvol:.1f}x ({rvol_label})')
    elif rvol_label in ('BELOW_AVERAGE', 'LOW') and direction != 'NEUTRAL':
        conflicting.append(f'Thin volume ({rvol_label}, RVOL {rvol:.1f}x) -- low conviction')
    if pvc == 'UP_CONFIRMED' and is_bull:
        confirming.append('Volume confirming up-bars (buyers active)')
    elif pvc == 'DOWN_CONFIRMED' and is_bear:
        confirming.append('Volume confirming down-bars (sellers active)')
    elif pvc == 'DIVERGING':
        conflicting.append('Price-volume divergence -- absorption or distribution possible')
    if breadth == 'BROAD_STRENGTH' and is_bull:
        confirming.append(
            f'Broad market strength (SPY {spy_pct:+.2f}% / IWM {iwm_pct:+.2f}%)'
            if spy_pct and iwm_pct else 'Broad market strength'
        )
    elif breadth == 'LARGE_CAP_LED' and is_bull:
        conflicting.append('Narrow breadth -- large-cap led, small caps lagging')
    elif breadth == 'BROAD_SELLING' and is_bear:
        confirming.append('Broad selling across large and small caps')

    return confirming, conflicting


# ── Invalidation condition ────────────────────────────────────────────────────

def _determine_invalidation(
    direction: str,
    ms_nq:     dict,
    liq_nq:    dict,
) -> str:
    """
    State the condition that would make the current thesis wrong.
    Anchored to the most relevant structural level in the opposing direction.
    """
    is_bull = direction == 'BULLISH'
    is_bear = direction == 'BEARISH'

    vs_pdh = ms_nq.get('price_vs_pdh', 'UNKNOWN')
    vs_pdl = ms_nq.get('price_vs_pdl', 'UNKNOWN')
    vs_pwh = ms_nq.get('price_vs_pwh', 'UNKNOWN')
    vs_pwl = ms_nq.get('price_vs_pwl', 'UNKNOWN')
    pdh    = ms_nq.get('pdh')
    pdl    = ms_nq.get('pdl')
    pwh    = ms_nq.get('pwh')
    pwl    = ms_nq.get('pwl')

    near_b = liq_nq.get('nearest_below') or {}
    near_a = liq_nq.get('nearest_above') or {}

    if is_bull:
        # Invalidated if bears push price below a key level and it's accepted there
        if vs_pdh == 'ABOVE' and pdh:
            return (
                f'Acceptance back below prior-day high ({_fmt(pdh)}) would invalidate '
                f'the bullish structure'
            )
        if pdl:
            return (
                f'Acceptance below prior-day low ({_fmt(pdl)}) would invalidate '
                f'the bullish thesis'
            )
        if near_b.get('price'):
            return (
                f'Acceptance below {near_b["label"]} ({_fmt(near_b["price"])}) would '
                f'invalidate the bullish thesis'
            )
        return 'A sustained break below session lows would invalidate the bullish thesis'

    if is_bear:
        # Invalidated if bulls push price above a key level and acceptance forms
        if vs_pdl == 'BELOW' and pdl:
            return (
                f'Acceptance back above prior-day low ({_fmt(pdl)}) would invalidate '
                f'the bearish structure'
            )
        if pdh:
            return (
                f'Acceptance above prior-day high ({_fmt(pdh)}) would invalidate '
                f'the bearish thesis'
            )
        if near_a.get('price'):
            return (
                f'Acceptance above {near_a["label"]} ({_fmt(near_a["price"])}) would '
                f'invalidate the bearish thesis'
            )
        return 'A sustained push above session highs would invalidate the bearish thesis'

    # Neutral
    if pdh and pdl:
        return (
            f'Break and acceptance above PDH ({_fmt(pdh)}) or below PDL ({_fmt(pdl)}) '
            f'would define the directional thesis'
        )
    return 'A sustained directional break with volume would define the next thesis'


# ── Confidence and risk ───────────────────────────────────────────────────────

def _score_confidence(
    confirming:  list[str],
    conflicting: list[str],
    direction:   str,
) -> str:
    if direction == 'NEUTRAL':
        return 'LOW'
    n_conf = len(confirming)
    n_confl = len(conflicting)
    net = n_conf - n_confl
    if net >= 3 and n_confl <= 1:
        return 'HIGH'
    if net >= 1:
        return 'MEDIUM'
    return 'LOW'


def _score_risk(macro_risk: str, vix_move: str, conflicting: list[str]) -> str:
    if macro_risk in ('EXTREME', 'HIGH') or vix_move == 'FEAR_SPIKE':
        return 'HIGH'
    if macro_risk == 'ELEVATED' or vix_move == 'FEAR_RISING' or len(conflicting) >= 3:
        return 'MEDIUM'
    return 'LOW'


# ── Main compute ──────────────────────────────────────────────────────────────

def compute_synthesis() -> dict:
    """
    Compute the market synthesis. Called from process_finnhub_cycle()
    after all other intelligence engines have run.

    Reads five JSON files. No network calls. Never raises.
    """
    try:
        mr2  = _read_json(_MR2_FILE)
        cm   = _read_json(_CM_FILE)
        ms   = _read_json(_MS_FILE)
        part = _read_json(_P_FILE)
        liq  = _read_json(_LIQ_FILE)
        risk = _read_json(_RISK_FILE)

        if not mr2 and not ms and not liq:
            return _neutral_state()

        direction  = mr2.get('direction', 'NEUTRAL')
        severity   = mr2.get('severity', 'NONE')
        nq_pct     = _safe(mr2.get('nq_pct', 0.0))
        macro_risk = risk.get('macro_risk', 'LOW')
        vix_move   = cm.get('vix_move', 'VIX_STABLE')

        ms_nq  = ms.get('nq', {})
        liq_nq = liq.get('nq', {})

        thesis = _determine_thesis(
            direction, severity, nq_pct, ms_nq, liq_nq, cm, part
        )
        driver = _determine_driver(direction, ms_nq, liq_nq, cm, part, macro_risk)
        confirming, conflicting = _collect_evidence(
            direction, mr2, ms_nq, liq_nq, cm, part
        )
        invalidation = _determine_invalidation(direction, ms_nq, liq_nq)
        confidence   = _score_confidence(confirming, conflicting, direction)
        risk_level   = _score_risk(macro_risk, vix_move, conflicting)

        state = {
            'market_thesis':       thesis,
            'primary_driver':      driver,
            'confirming_evidence': confirming,
            'conflicting_evidence': conflicting,
            'invalidation':        invalidation,
            'confidence':          confidence,
            'risk_level':          risk_level,
            'meta': {
                'direction':   direction,
                'severity':    severity,
                'nq_pct':      nq_pct,
                'macro_risk':  macro_risk,
                'vix_move':    vix_move,
                'session_type': part.get('session_type', 'UNCERTAIN'),
            },
            'last_updated': _utc_iso(),
        }

        _SYN_FILE.write_text(json.dumps(state, indent=2, default=str), encoding='utf-8')

        print(
            f'[synthesis] "{thesis[:72]}..." | '
            f'driver={driver} | conf={confidence} | risk={risk_level} | '
            f'evidence: {len(confirming)} confirm / {len(conflicting)} conflict'
        )
        return state

    except Exception as exc:
        print(f'[synthesis] compute error: {exc}')
        return _neutral_state()


def _neutral_state() -> dict:
    return {
        'market_thesis':        'Market intelligence data unavailable.',
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
    """Load cached synthesis state. No network calls."""
    data = _read_json(_SYN_FILE)
    return data if data else _neutral_state()


def format_for_prompt(syn: dict) -> str:
    """
    Compact synthesis block for the Claude evaluation prompt.
    Placed last in the intelligence stack --Claude reads full context
    before seeing the synthesis, then the synthesis anchors interpretation.
    """
    if not syn.get('market_thesis') or syn['market_thesis'].startswith('Market intelligence'):
        return ''

    conf_lines  = '\n'.join(f'    + {e}' for e in syn.get('confirming_evidence', []))
    confl_lines = '\n'.join(f'    - {e}' for e in syn.get('conflicting_evidence', []))

    lines = [
        '=== MARKET SYNTHESIS ===',
        f'Thesis:    {syn["market_thesis"]}',
        f'Driver:    {syn["primary_driver"]}',
        f'Confidence: {syn["confidence"]}  |  Risk: {syn["risk_level"]}',
    ]
    if conf_lines:
        lines.append(f'Confirms:\n{conf_lines}')
    if confl_lines:
        lines.append(f'Conflicts:\n{confl_lines}')
    lines.append(f'Invalidation: {syn["invalidation"]}')
    lines.append('=== END SYNTHESIS ===')
    return '\n'.join(lines)


def format_for_assistant(syn: dict) -> str:
    """Single-line synthesis for the assistant session context."""
    thesis = syn.get('market_thesis', '?')
    driver = syn.get('primary_driver', '?')
    conf   = syn.get('confidence', '?')
    risk   = syn.get('risk_level', '?')
    n_conf = len(syn.get('confirming_evidence', []))
    n_cfl  = len(syn.get('conflicting_evidence', []))
    return (
        f'SYNTHESIS: "{thesis}" | '
        f'driver={driver} conf={conf} risk={risk} '
        f'[{n_conf} confirm/{n_cfl} conflict]'
    )
