"""
engines/directional_pressure.py

Directional Dominance Engine.

Architecture principle:
  Binary BULL/BEAR logic treats every intelligence source as a switch.
  Real markets accumulate directional pressure from multiple sources.
  This engine scores each source independently, sums weighted pressure,
  and produces: dominance label, conviction level, and an explicit list
  of internal disagreements — conflicts the system cannot resolve
  deterministically become visible signals for AI interpretation.

Sources:
  market_reality → live price truth (direction, severity, session drive)
  pine_state     → NOVA indicator (PROS phase, CONT quality, CMD)
  ib_eval        → IB draw, alignment, position
  market_memory  → OTE defenses, continuation persistence (session evidence)
  macro          → VIX regime, volatility pressure

Output feeds:
  _build_evaluation_prompt() → DIRECTIONAL DOMINANCE block for Claude
  pre_assess dict            → available for future _classify_signal gating
"""

from __future__ import annotations
from typing import Optional

# ── Source weight ceilings (max pts per direction per source) ─────────────────
_W_REALITY  = 20
_W_PINE     = 25
_W_IB       = 15
_W_MEMORY   = 20
_W_MACRO    = 10
_W_MOMENTUM = 12   # MACD curl/slope evidence at OTE

# ── Decision thresholds ───────────────────────────────────────────────────────
_DOMINANT_THRESHOLD  = 30   # net score for DOMINANT label
_LEANING_THRESHOLD   = 15   # net score for LEANING label
_DISAGREE_THRESHOLD  = 6    # losing-side pts to flag a source as disagreeing


# ── Individual source scorers ─────────────────────────────────────────────────

def _score_reality(mr: dict, mr2: dict | None = None) -> tuple[int, int, str]:
    """
    Live price truth layer — highest-authority source.
    Uses Market Reality 2.0 fact score when provided (passed from compute()).
    Falls back to v1 direction/severity when mr2 is unavailable.
    """
    bull = bear = 0
    notes: list[str] = []

    # V2 path — pure fact-based score, no V1 narrative blending
    if mr2:
        state = mr2.get('state', 'NEUTRAL')
        score = mr2.get('score', 0)
        if state not in ('NEUTRAL',) and score != 0:
            scaled = min(abs(score) * 1.0, _W_REALITY)
            if score > 0:
                bull = round(scaled)
            else:
                bear = round(scaled)
            notes.append(f'MR2:{state} score={score:+d}')
            return min(bull, _W_REALITY), min(bear, _W_REALITY), ' | '.join(notes)

    # Fallback to v1 direction/severity scoring
    direction = (mr.get('direction')    or 'UNKNOWN').upper()
    severity  = (mr.get('severity')     or 'LOW').upper()
    drive     = (mr.get('session_drive')or '').upper()
    structure = (mr.get('structure')    or 'RANGE').upper()
    grok      = (mr.get('grok_sentiment') or 'UNKNOWN').upper()

    sev_pts = {'LOW': 5, 'MEDIUM': 10, 'HIGH': 15, 'EXTREME': 20}.get(severity, 5)

    if direction == 'BULLISH':
        bull += sev_pts
        notes.append(f'BULLISH {severity}')
    elif direction == 'BEARISH':
        bear += sev_pts
        notes.append(f'BEARISH {severity}')
    elif direction == 'MIXED':
        bull += 2; bear += 2
        notes.append('MIXED')
    else:
        notes.append('NEUTRAL')

    if 'BULL' in drive:   bull += 4
    elif 'BEAR' in drive: bear += 4
    if structure == 'WEEKLY_HIGH_BREAK': bull += 3
    elif structure == 'WEEKLY_LOW_BREAK': bear += 3
    if grok == 'BULLISH': bull += 2
    elif grok == 'BEARISH': bear += 2

    return min(bull, _W_REALITY), min(bear, _W_REALITY), ' | '.join(notes)


def _score_pine(pros_eval: dict) -> tuple[int, int, str]:
    """NOVA indicator state — what Pine has computed from price action."""
    direction    = (pros_eval.get('direction')    or 'N/A').upper()
    phase        = (pros_eval.get('phase')        or 'NO_SIGNAL').upper()
    cont_quality = (pros_eval.get('cont_quality') or 'UNKNOWN').upper()
    has_signal   = pros_eval.get('has_signal', False)

    phase_pts = {
        'ACCEPTED_CONTINUATION': 15,
        'SETUP_READY':           15,
        'OTE_TAGGED':            12,
        'OTE_APPROACHING':        8,
        'BUILDING':               6,
    }.get(phase, 0)

    cont_pts = {
        'STRONG':   5,
        'BUILDING': 3,
        'MODERATE': 1,
    }.get(cont_quality, 0)

    bull = bear = 0
    note = f'{direction} {phase} cont={cont_quality}'

    if direction == 'LONG' and has_signal:
        bull = phase_pts + cont_pts
    elif direction == 'SHORT' and has_signal:
        bear = phase_pts + cont_pts

    return min(bull, _W_PINE), min(bear, _W_PINE), note


def _score_ib(ib_eval: dict) -> tuple[int, int, str]:
    """IB draw and alignment — primary directional signal within IB window."""
    draw    = (ib_eval.get('draw') or 'UNCLEAR').upper()
    aligned = ib_eval.get('aligned', False)

    bull = bear = 0

    if draw == 'IB HIGH':
        bull = 12 if aligned else 6
        note = f'draw=HIGH aligned={aligned}'
    elif draw == 'IB LOW':
        bear = 12 if aligned else 6
        note = f'draw=LOW aligned={aligned}'
    else:
        note = 'draw=UNCLEAR'

    return min(bull, _W_IB), min(bear, _W_IB), note


def _score_memory(mem: dict) -> tuple[int, int, str]:
    """
    Session structural evidence — persists across Pine trigger cycles.
    OTE defenses and continuation persistence are accumulated evidence
    that Pine's single-bar events cannot represent.
    """
    lt = mem.get('long',  {})
    st = mem.get('short', {})

    bull = bear = 0
    notes: list[str] = []

    # Long structural evidence
    long_def     = min(lt.get('ote_holds', 0), 3)
    long_cont_m  = lt.get('cont_minutes', 0)
    opp_failures = min(st.get('ote_failures', 0), 2)   # short side failed → long evidence

    bull += long_def * 4
    if lt.get('cont_active'):
        bull += 4 + min(int(long_cont_m / 5), 4)       # base 4 + up to 4 from duration
    elif lt.get('cont_starts', 0) > 0:
        bull += 2
    bull += opp_failures * 3

    if long_def or lt.get('cont_active') or lt.get('cont_starts', 0):
        notes.append(
            f'LONG: def={long_def}x '
            f'cont={"active " + str(int(long_cont_m)) + "min" if lt.get("cont_active") else "closed" if lt.get("cont_starts") else "none"}'
        )

    # Short structural evidence
    short_def    = min(st.get('ote_holds', 0), 3)
    short_cont_m = st.get('cont_minutes', 0)
    opp_failures = min(lt.get('ote_failures', 0), 2)   # long side failed → short evidence

    bear += short_def * 4
    if st.get('cont_active'):
        bear += 4 + min(int(short_cont_m / 5), 4)
    elif st.get('cont_starts', 0) > 0:
        bear += 2
    bear += opp_failures * 3

    if short_def or st.get('cont_active') or st.get('cont_starts', 0):
        notes.append(
            f'SHORT: def={short_def}x '
            f'cont={"active " + str(int(short_cont_m)) + "min" if st.get("cont_active") else "closed" if st.get("cont_starts") else "none"}'
        )

    if not notes:
        notes.append('no structural evidence yet')

    return min(bull, _W_MEMORY), min(bear, _W_MEMORY), ' | '.join(notes)


def _score_momentum(momentum_eval: dict) -> tuple[int, int, str]:
    """
    MACD slope/curl evidence of buyer or seller control returning at OTE.
    momentum_confirmation is ABSOLUTE: STRONG_BULLISH always → bull pts.
    Agreement vs conflict with the OTE direction surfaces via the existing
    disagreement-detection loop — no special casing needed here.
    """
    state = (momentum_eval.get('momentum_confirmation') or 'NEUTRAL').upper()
    slope = momentum_eval.get('macd_slope', 0)
    curl  = 'CURL_UP' if momentum_eval.get('curl_up') else ('CURL_DOWN' if momentum_eval.get('curl_down') else '')
    ote   = momentum_eval.get('ote_context', 'N/A')

    pts_map = {
        'STRONG_BULLISH': (12, 0),
        'BULLISH':         (7, 0),
        'NEUTRAL':         (0, 0),
        'BEARISH':         (0, 7),
        'STRONG_BEARISH':  (0, 12),
    }
    bull, bear = pts_map.get(state, (0, 0))
    note = f'momentum={state} slope={slope:+.4f}'
    if curl:
        note += f' {curl}'
    if ote and ote != 'N/A':
        note += f' OTE={ote}'

    return min(bull, _W_MOMENTUM), min(bear, _W_MOMENTUM), note


def _score_macro(mr: dict) -> tuple[int, int, str]:
    """VIX and volatility regime — creates directional headwinds."""
    vix    = float(mr.get('vix', 0) or 0)
    regime = (mr.get('market_regime') or '').upper()

    bear = 0
    note_parts: list[str] = []

    if vix >= 25:
        bear = 10
        note_parts.append(f'VIX={vix:.1f} extreme fear')
    elif vix >= 20:
        bear = 6
        note_parts.append(f'VIX={vix:.1f} elevated')
    elif vix >= 17:
        bear = 3
        note_parts.append(f'VIX={vix:.1f} mild risk-off')
    else:
        note_parts.append(f'VIX={vix:.1f} calm')

    if 'VOLATILE' in regime:
        bear = min(bear + 3, _W_MACRO)
        note_parts.append('volatile regime')

    return 0, min(bear, _W_MACRO), ' | '.join(note_parts) or 'no macro signal'


# ── Main compute ──────────────────────────────────────────────────────────────

def compute(
    pros_eval:     dict,
    ib_eval:       dict,
    session_ctx:   dict,
    mem_summary:   dict,
    mr:            Optional[dict] = None,
    momentum_eval: Optional[dict] = None,
) -> dict:
    """
    Compute directional pressure from all intelligence sources.

    Args:
        pros_eval:     return value of _evaluate_pros_phase()
        ib_eval:       return value of _evaluate_ib_alignment()
        session_ctx:   session context dict from _build_session_context()
        mem_summary:   return value of market_memory.get_summary(symbol)
        mr:            market reality state (loaded from file if None)
        momentum_eval: return value of compute_momentum() from engines.momentum

    Returns:
        {
          bullish:       int,          # accumulated bullish pressure (0-100)
          bearish:       int,          # accumulated bearish pressure (0-100)
          net:           int,          # positive = bullish, negative = bearish
          dominance:     str,          # BULL_DOMINANT / BEAR_DOMINANT / BULL_LEANING / BEAR_LEANING / CONTESTED
          conviction:    str,          # HIGH / MODERATE / LOW / CONFLICTED / NONE
          sources:       dict,         # per-source {bull, bear, note}
          disagreements: list[str],    # source conflicts — explicit for AI interpretation
          session_quality: str,
        }
    """
    # Load V2 once — authoritative source when available
    _mr2: dict | None = None
    try:
        from engines.market_reality_v2 import load_market_reality_v2
        _loaded = load_market_reality_v2()
        if _loaded.get('state'):
            _mr2 = _loaded
    except Exception:
        pass

    # Load V1 only as fallback when V2 is unavailable
    if mr is None:
        if _mr2 is None:
            try:
                from engines.market_reality import load_market_reality
                mr = load_market_reality()
            except Exception:
                mr = {}
        else:
            mr = {}

    quality  = (session_ctx.get('session_quality') or 'dead').upper()
    is_dead  = session_ctx.get('is_dead_zone', False) or quality in ('DEAD', 'dead')

    if is_dead:
        return {
            'bullish': 0, 'bearish': 0, 'net': 0,
            'dominance': 'NEUTRAL', 'conviction': 'NONE',
            'sources': {}, 'disagreements': [],
            'session_quality': quality,
        }

    # Score each source independently
    r_b,  r_s,  r_n  = _score_reality(mr, _mr2)
    p_b,  p_s,  p_n  = _score_pine(pros_eval)
    ib_b, ib_s, ib_n = _score_ib(ib_eval)
    m_b,  m_s,  m_n  = _score_memory(mem_summary)
    mo_b, mo_s, mo_n = _score_momentum(momentum_eval) if momentum_eval else (0, 0, 'momentum=not_computed')

    # V2 already scores VIX as a hard fact — skip macro to avoid double-counting
    if _mr2 is not None:
        x_b, x_s, x_n = 0, 0, f'VIX in MR2 facts (score={_mr2.get("score", 0):+d})'
    else:
        x_b, x_s, x_n = _score_macro(mr)

    sources = {
        'market_reality': {'bull': r_b,  'bear': r_s,  'note': r_n},
        'pine_state':     {'bull': p_b,  'bear': p_s,  'note': p_n},
        'ib_eval':        {'bull': ib_b, 'bear': ib_s, 'note': ib_n},
        'market_memory':  {'bull': m_b,  'bear': m_s,  'note': m_n},
        'macro':          {'bull': x_b,  'bear': x_s,  'note': x_n},
        'momentum':       {'bull': mo_b, 'bear': mo_s, 'note': mo_n},
    }

    # Session quality multiplier (A=1.0 B=0.85 C=0.70)
    q_mult = {'A': 1.0, 'B': 0.85, 'C': 0.70}.get(quality, 0.5)

    raw_bull = r_b + p_b + ib_b + m_b + x_b + mo_b
    raw_bear = r_s + p_s + ib_s + m_s + x_s + mo_s

    bull = round(raw_bull * q_mult)
    bear = round(raw_bear * q_mult)
    net  = bull - bear

    # Dominance
    if net >= _DOMINANT_THRESHOLD:
        dominance = 'BULL_DOMINANT'
    elif net >= _LEANING_THRESHOLD:
        dominance = 'BULL_LEANING'
    elif net <= -_DOMINANT_THRESHOLD:
        dominance = 'BEAR_DOMINANT'
    elif net <= -_LEANING_THRESHOLD:
        dominance = 'BEAR_LEANING'
    else:
        dominance = 'CONTESTED'

    # Disagreement detection — explicit source conflicts visible to Claude
    winning_is_bull = net > 0
    label_map = {
        'market_reality': 'Market Reality',
        'pine_state':     'Pine indicator',
        'ib_eval':        'IB analysis',
        'market_memory':  'Market memory',
        'macro':          'Macro/VIX',
        'momentum':       'MACD momentum',
    }
    disagreements: list[str] = []
    disagree_count = 0

    for key, s in sources.items():
        losing_pts = s['bear'] if winning_is_bull else s['bull']
        if losing_pts >= _DISAGREE_THRESHOLD:
            losing_dir  = 'BEARISH' if winning_is_bull else 'BULLISH'
            winning_dir = 'BULLISH' if winning_is_bull else 'BEARISH'
            disagreements.append(
                f'{label_map[key]} {losing_dir} ({losing_pts}pts) vs dominant {winning_dir}'
            )
            disagree_count += 1

    # Conviction
    if dominance == 'CONTESTED':
        conviction = 'CONFLICTED'
    elif disagree_count == 0:
        conviction = 'HIGH'
    elif disagree_count == 1:
        conviction = 'MODERATE'
    else:
        conviction = 'LOW'

    return {
        'bullish':         bull,
        'bearish':         bear,
        'net':             net,
        'dominance':       dominance,
        'conviction':      conviction,
        'sources':         sources,
        'disagreements':   disagreements,
        'session_quality': quality,
    }


def format_for_prompt(dp: dict) -> str:
    """
    Compact directional pressure block for Claude prompt injection.

    Example:
      DIRECTIONAL PRESSURE: bull=42 bear=18 net=+24 | dominance=BULL_LEANING | conviction=MODERATE
        market_reality    bull=12 bear= 5 | BULLISH MEDIUM | BULL_TREND
        pine_state        bull=18 bear= 0 | LONG ACCEPTED_CONTINUATION cont=STRONG
        ib_eval           bull=12 bear= 0 | draw=HIGH aligned=True
        market_memory     bull= 0 bear= 0 | no structural evidence yet
        macro             bull= 0 bear= 3 | VIX=17.2 mild risk-off
        DISAGREEMENTS:
          ⚑ Macro/VIX BEARISH (3pts) — conflicts with dominant BULLISH
    """
    if not dp or dp.get('dominance') == 'NEUTRAL':
        return 'DIRECTIONAL PRESSURE: session inactive / dead zone'

    lines = [
        f'DIRECTIONAL PRESSURE: bull={dp["bullish"]} bear={dp["bearish"]} '
        f'net={dp["net"]:+d} | dominance={dp["dominance"]} | conviction={dp["conviction"]}'
    ]

    for key, s in dp.get('sources', {}).items():
        if s['bull'] > 0 or s['bear'] > 0:
            lines.append(
                f'  {key:<16} bull={s["bull"]:>2} bear={s["bear"]:>2} | {s["note"]}'
            )

    disagreements = dp.get('disagreements', [])
    if disagreements:
        lines.append('  DISAGREEMENTS:')
        for d in disagreements:
            lines.append(f'    >> {d}')

    return '\n'.join(lines)
