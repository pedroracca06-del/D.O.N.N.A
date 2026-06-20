"""
engines/session_memory.py -- Multi-Session Memory + Narrative Continuity.

Purpose: teach NOVA to remember the recent market story, not just the current snapshot.

NOVA currently wakes up every session knowing what the market looks like today.
It does not know how we got here.
This engine fixes that.

Core question answered:
    "What has the market been trying to accomplish over the last several sessions?"

Architecture:
    - Maintains a rolling record of the last 5 completed trading sessions
    - Each record stores interpreted intelligence (not raw market data)
    - Detects patterns across sessions: persistence, rejection, acceptance, transition
    - Generates a compact rolling narrative -- an analyst's understanding of the ongoing story

Session record (per day):
    date, thesis_state, thesis (truncated), driver, confidence, direction,
    nq_pct, session_type, participation, rvol, key_events[], structural_events[], narrative

Rolling narrative examples:
    "This is the third attempt above PDH this week. Previous attempts failed on weak
     participation. Buyers are showing persistence but no acceptance yet."

    "Market has transitioned from bullish to contested over 3 sessions -- buyers losing
     structural control, sellers stepping in at PDH."

    "Market has rotated inside prior-week range for 4 sessions without directional
     resolution. Balanced auction awaiting a structural catalyst."

Consumes (no new APIs, no new data sources):
    donna_synthesis.json       -- thesis state, driver, confidence, condition
    donna_market_reality_v2.json -- direction, severity, nq_pct
    donna_market_structure.json  -- structural position vs key levels
    donna_participation.json     -- session type, RVOL, participation bias
    donna_liquidity.json         -- primary draw, swept/untapped counts

Critical architecture rule:
    Never reads PROS, ORB, or any strategy signal.
    No execution changes. No grading changes.
    Memory records interpreted intelligence only.

Called from: services/finnhub.py (after compute_synthesis)
Output: donna_session_memory.json
Endpoint: GET /session-memory
Injected into: engines/reasoning.py, services/assistant.py
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from core.config import (
    SESSION_MEMORY_FILE    as _MEM_FILE,
    SYNTHESIS_FILE         as _SYN_FILE,
    MARKET_REALITY_V2_FILE as _MR2_FILE,
    MARKET_STRUCTURE_FILE  as _MS_FILE,
    PARTICIPATION_FILE     as _P_FILE,
    LIQUIDITY_FILE         as _LIQ_FILE,
)

_NY_TZ   = ZoneInfo('America/New_York')
_MAX_SESSIONS = 5


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


def _current_et_date() -> str:
    return datetime.now(_NY_TZ).strftime('%Y-%m-%d')


def _day_of_week(date_str: str) -> int:
    """Return weekday integer: 0=Mon, 6=Sun. Returns 6 on parse failure."""
    try:
        return datetime.strptime(date_str, '%Y-%m-%d').weekday()
    except Exception:
        return 6


def _is_trading_day(date_str: str) -> bool:
    return _day_of_week(date_str) < 5


def _is_valid_session(record: dict) -> bool:
    """True if a session record has meaningful data worth storing in history."""
    return bool(
        record.get('date') and
        record.get('thesis_state', 'UNKNOWN') not in ('UNKNOWN', '') and
        _is_trading_day(record.get('date', ''))
    )


def _extract_level(text: str) -> str:
    """Extract the first structural level name found in a string."""
    for lvl in ('PWH', 'PWL', 'PDH', 'PDL', 'ONH', 'ONL'):
        if lvl in text:
            return lvl
    return ''


def _ordinal(n: int) -> str:
    return {1: 'first', 2: 'second', 3: 'third', 4: 'fourth', 5: 'fifth'}.get(n, f'{n}th')


# ── Session record construction ───────────────────────────────────────────────

def _build_session_record(
    date: str,
    synth: dict,
    ms_nq: dict,
    liq_nq: dict,
    part: dict,
    mr2: dict,
) -> dict:
    """
    Construct a single session record from current intelligence state.
    Stores interpreted signals only -- no raw market data.
    """
    # From synthesis
    thesis_state = synth.get('thesis_state', 'UNKNOWN')
    thesis       = (synth.get('market_thesis') or '')[:120]
    driver       = synth.get('primary_driver', '')
    confidence   = synth.get('confidence', '')
    condition    = (synth.get('thesis_condition') or '')[:120]

    # From MR2
    direction = mr2.get('direction', 'NEUTRAL')
    severity  = mr2.get('severity', 'NONE')
    nq_pct    = _safe(mr2.get('nq_pct', 0.0))

    # From participation
    sess_type = part.get('session_type', 'UNCERTAIN')
    part_bias = part.get('participation_bias', 'UNKNOWN')
    rvol      = _safe((part.get('nq') or {}).get('rvol', 0.0))

    # Key liquidity events
    key_events: list[str] = []
    swept_above = liq_nq.get('swept_above', 0)
    swept_below = liq_nq.get('swept_below', 0)
    u_above     = liq_nq.get('untapped_above', 0)
    u_below     = liq_nq.get('untapped_below', 0)
    draw        = liq_nq.get('primary_draw') or {}

    if swept_above:
        key_events.append(f'{swept_above} level(s) swept above -- topside cleared today')
    if swept_below:
        key_events.append(f'{swept_below} level(s) swept below -- downside cleared today')
    if draw.get('label') and draw.get('side'):
        d_pts  = abs(_safe(draw.get('distance_pts', 0)))
        d_side = draw['side']
        d_lbl  = draw['label']
        key_events.append(
            f'Primary draw: {d_lbl} ({d_pts:.0f}pts {"below" if d_side == "BELOW" else "above"}) -- untouched'
        )
    if u_above == 0 and u_below > 0:
        key_events.append(f'No untapped levels above -- all {u_below} remain below')
    elif u_below == 0 and u_above > 0:
        key_events.append(f'No untapped levels below -- all {u_above} remain above')

    # Key structural events (what levels was price at or beyond today?)
    structural_events: list[str] = []
    vs_pdh = ms_nq.get('price_vs_pdh', 'UNKNOWN')
    vs_pdl = ms_nq.get('price_vs_pdl', 'UNKNOWN')
    vs_pwh = ms_nq.get('price_vs_pwh', 'UNKNOWN')
    vs_pwl = ms_nq.get('price_vs_pwl', 'UNKNOWN')
    gap    = ms_nq.get('gap_signal', 'UNKNOWN')
    gap_pct = _safe(ms_nq.get('gap_pct', 0.0))

    if vs_pwh in ('ABOVE', 'AT'):
        structural_events.append(f'Price {vs_pwh} PWH ({_fmt(ms_nq.get("pwh"))})')
    if vs_pwl in ('BELOW', 'AT'):
        structural_events.append(f'Price {vs_pwl} PWL ({_fmt(ms_nq.get("pwl"))})')
    if vs_pwh not in ('ABOVE', 'AT'):
        if vs_pdh == 'ABOVE':
            structural_events.append(f'Price ABOVE PDH ({_fmt(ms_nq.get("pdh"))})')
        elif vs_pdh == 'AT':
            structural_events.append(f'Price AT PDH ({_fmt(ms_nq.get("pdh"))})')
    if vs_pwl not in ('BELOW', 'AT'):
        if vs_pdl == 'BELOW':
            structural_events.append(f'Price BELOW PDL ({_fmt(ms_nq.get("pdl"))})')
        elif vs_pdl == 'AT':
            structural_events.append(f'Price AT PDL ({_fmt(ms_nq.get("pdl"))})')
    if gap in ('GAP_UP', 'GAP_DOWN'):
        structural_events.append(f'{gap} ({gap_pct:+.2f}%)')

    record = {
        'date':              date,
        'thesis_state':      thesis_state,
        'thesis':            thesis,
        'driver':            driver,
        'confidence':        confidence,
        'condition':         condition,
        'direction':         direction,
        'severity':          severity,
        'nq_pct':            round(nq_pct, 2),
        'session_type':      sess_type,
        'participation':     part_bias,
        'rvol':              round(rvol, 2),
        'key_events':        key_events,
        'structural_events': structural_events,
        'narrative':         '',  # filled below
    }
    record['narrative'] = _session_narrative(record)
    return record


def _session_narrative(record: dict) -> str:
    """
    One sentence describing what happened (or is happening) in a single session.
    Used both in the per-session history and as the basis for the rolling narrative.
    """
    state    = record.get('thesis_state', 'UNKNOWN')
    part     = record.get('participation', 'UNKNOWN')
    nq_pct   = _safe(record.get('nq_pct', 0.0))
    key_evs  = record.get('key_events', [])
    struct   = record.get('structural_events', [])

    part_desc = {'STRONG': 'strong', 'MODERATE': 'moderate', 'WEAK': 'weak'}.get(part, 'uncertain')
    move_str  = f'{nq_pct:+.2f}%' if abs(nq_pct) >= 0.05 else 'flat'

    # Find the most significant structural level referenced today
    struct_level = ''
    for ev in struct:
        lvl = _extract_level(ev)
        if lvl in ('PWH', 'PWL'):
            struct_level = lvl
            break
        if lvl in ('PDH', 'PDL') and not struct_level:
            struct_level = lvl
    struct_ref = f' at {struct_level}' if struct_level else ''

    # Primary draw event for liquidity-driven sessions
    draw_event = next((e for e in key_evs if 'Primary draw' in e), '')

    if state == 'ACCEPTANCE_DEVELOPING':
        lvl = struct_level or 'key resistance'
        return (
            f'Buyers accepted above {lvl} with {part_desc} participation -- '
            f'structural breakout developing ({move_str})'
        )

    if state == 'REJECTION_DEVELOPING':
        lvl = struct_level or 'key resistance'
        return (
            f'Probe above {lvl} rejected on {part_desc} participation -- '
            f'sellers defended, buyers unable to hold ({move_str})'
        )

    if state == 'CONTESTED':
        lvl = struct_level or 'structural level'
        return (
            f'Contested session{struct_ref} -- {part_desc} participation created stop-run risk '
            f'with conflicting bull/bear signals ({move_str})'
        )

    if state == 'BULLISH':
        return (
            f'Buyers controlled ({move_str}) with {part_desc} participation -- '
            f'directional bullish session{struct_ref}'
        )

    if state == 'BEARISH':
        return (
            f'Sellers controlled ({move_str}) with {part_desc} participation -- '
            f'directional bearish session{struct_ref}'
        )

    if state == 'LIQUIDITY_SEEKING':
        if draw_event:
            return f'Market seeking liquidity ({move_str}): {draw_event}'
        return f'Market targeting remaining liquidity ({move_str}) with {part_desc} participation'

    if state == 'TRANSITIONING':
        lean = 'bullish' if nq_pct > 0 else 'bearish'
        return (
            f'Session drifting {lean} ({move_str}) on {part_desc} participation -- '
            f'transition signals developing'
        )

    # NEUTRAL or unknown
    return (
        f'Range session ({move_str}) -- no directional resolution with {part_desc} participation'
    )


# ── Pattern detection helpers ─────────────────────────────────────────────────

def _dominant_level(sessions: list[dict]) -> str:
    """Level that appears most frequently across session structural_events."""
    counts: dict[str, int] = {}
    for s in sessions:
        seen_this_session: set[str] = set()
        for ev in s.get('structural_events', []):
            lvl = _extract_level(ev)
            if lvl and lvl not in seen_this_session:
                counts[lvl] = counts.get(lvl, 0) + 1
                seen_this_session.add(lvl)
    if not counts:
        return ''
    return max(counts, key=lambda k: counts[k])


def _dominant_draw(sessions: list[dict]) -> str:
    """Primary draw label that appears in most sessions."""
    counts: dict[str, int] = {}
    for s in sessions:
        for ev in s.get('key_events', []):
            if 'Primary draw:' in ev:
                # "Primary draw: PDL (259pts below) -- untouched"
                try:
                    lbl = ev.split('Primary draw:')[1].split('(')[0].strip()
                    if lbl:
                        counts[lbl] = counts.get(lbl, 0) + 1
                except Exception:
                    pass
    if not counts:
        return ''
    top = max(counts, key=lambda k: counts[k])
    return top if counts[top] >= 2 else ''


def _sessions_with_level(sessions: list[dict], level: str) -> list[dict]:
    """Return sessions where the given level appeared in structural_events."""
    return [
        s for s in sessions
        if any(level in ev for ev in s.get('structural_events', []))
    ]


# ── Rolling narrative ─────────────────────────────────────────────────────────

def _generate_rolling_narrative(sessions: list[dict]) -> str:
    """
    1-3 sentence analyst narrative summarising the recent market story.

    sessions: list ordered most-recent first (current session at index 0).
    """
    if not sessions:
        return 'No session history available.'
    if len(sessions) == 1:
        return sessions[0].get('narrative', 'First session in memory -- building history.')

    states = [s.get('thesis_state', 'UNKNOWN') for s in sessions]
    parts  = [s.get('participation', 'UNKNOWN') for s in sessions]
    dirs   = [s.get('direction', 'NEUTRAL') for s in sessions]
    n      = len(sessions)

    # ── Pattern A: Repeated level tests ──────────────────────────────────
    # "This is the Nth attempt above PDH this week.
    #  Previous attempts failed on weak participation. Buyers are showing persistence."
    dom_level = _dominant_level(sessions)
    if dom_level:
        level_sessions = _sessions_with_level(sessions, dom_level)
        if len(level_sessions) >= 2:
            recent_level_state  = level_sessions[0].get('thesis_state', 'UNKNOWN')
            rejection_sessions  = [
                s for s in level_sessions
                if s.get('thesis_state') in ('REJECTION_DEVELOPING', 'CONTESTED')
            ]
            acceptance_sessions = [
                s for s in level_sessions
                if s.get('thesis_state') in ('ACCEPTANCE_DEVELOPING', 'BULLISH')
            ]
            n_tests = len(level_sessions)
            ord_str = _ordinal(n_tests)

            # Multiple rejections / contested at the same level
            if len(rejection_sessions) >= 2 and recent_level_state in ('REJECTION_DEVELOPING', 'CONTESTED'):
                weak_parts = [s for s in level_sessions if s.get('participation') == 'WEAK']
                if weak_parts:
                    part_context = (
                        'Each attempt has been on weak participation, suggesting buyers lack conviction.'
                    )
                else:
                    part_context = 'Sellers have consistently defended this level.'
                # Trajectory: is participation improving?
                if len(level_sessions) >= 2:
                    recent_p = level_sessions[0].get('participation', 'UNKNOWN')
                    oldest_p = level_sessions[-1].get('participation', 'UNKNOWN')
                    if recent_p in ('STRONG', 'MODERATE') and oldest_p == 'WEAK':
                        part_context = 'Participation is improving with each test -- buyers gaining conviction.'
                return (
                    f'This is the {ord_str} attempt above {dom_level} in recent sessions. '
                    f'Previous attempts were rejected. {part_context}'
                )

            # Building acceptance at the same level
            if len(acceptance_sessions) >= 2 and recent_level_state in ('ACCEPTANCE_DEVELOPING', 'BULLISH'):
                strong_parts = [s for s in level_sessions if s.get('participation') in ('STRONG', 'MODERATE')]
                if strong_parts:
                    return (
                        f'Market is building acceptance above {dom_level} across {n_tests} sessions '
                        f'with participation confirming the structural breakout. '
                        f'Sellers are failing to defend -- bullish case is gaining credibility.'
                    )
                return (
                    f'Market is making its {ord_str} attempt above {dom_level}, '
                    f'with prior sessions showing acceptance but participation remains inconsistent.'
                )

    # ── Pattern B: Consistent bearish / liquidity seeking ─────────────────
    bearish_states = [st for st in states if st in ('BEARISH', 'LIQUIDITY_SEEKING')]
    if len(bearish_states) >= 3 and states[0] in ('BEARISH', 'LIQUIDITY_SEEKING'):
        draw = _dominant_draw(sessions)
        if draw:
            return (
                f'Market has maintained a bearish bias across {len(bearish_states)} sessions '
                f'with {draw} as the persistent downside target. '
                f'Sellers remain in control -- upside attempts have lacked follow-through.'
            )
        return (
            f'Market has been under sustained selling pressure across {len(bearish_states)} sessions. '
            f'Buyers have shown no ability to establish structural control.'
        )

    # ── Pattern C: Consistent bullish ─────────────────────────────────────
    bullish_states = [st for st in states if st in ('BULLISH', 'ACCEPTANCE_DEVELOPING')]
    if len(bullish_states) >= 3 and states[0] in ('BULLISH', 'ACCEPTANCE_DEVELOPING'):
        return (
            f'Market has maintained a bullish posture across {len(bullish_states)} sessions '
            f'with buyers consistently controlling structure. '
            f'Sellers have been absent -- upside momentum remains intact.'
        )

    # ── Pattern D: Range / balance dominance ──────────────────────────────
    neutral_states = [st for st in states if st in ('NEUTRAL', 'TRANSITIONING')]
    if len(neutral_states) >= 3:
        return (
            f'Market has rotated inside prior session range for {len(neutral_states)} sessions '
            f'without directional resolution. '
            f'Balanced auction -- participants are waiting for a structural catalyst.'
        )

    # ── Pattern E: Transition (clear state shift) ─────────────────────────
    if n >= 3:
        older_states  = states[2:]          # sessions 3+ (older history)
        recent_states = states[:2]          # sessions 1-2 (recent)

        old_bull_count = sum(1 for st in older_states if st in ('BULLISH', 'ACCEPTANCE_DEVELOPING'))
        old_bear_count = sum(1 for st in older_states if st in ('BEARISH', 'REJECTION_DEVELOPING', 'CONTESTED'))
        new_bull_count = sum(1 for st in recent_states if st in ('BULLISH', 'ACCEPTANCE_DEVELOPING'))
        new_bear_count = sum(1 for st in recent_states if st in ('BEARISH', 'REJECTION_DEVELOPING', 'CONTESTED'))

        if old_bull_count >= 2 and new_bear_count >= 2:
            return (
                'Market has transitioned from bullish to contested/bearish over recent sessions -- '
                'buyers losing structural control, sellers stepping in. '
                'Watch for follow-through confirmation to define the new directional bias.'
            )
        if old_bear_count >= 2 and new_bull_count >= 2:
            return (
                'Market has transitioned from bearish to bullish over recent sessions -- '
                'sellers are exhausted and buyers are reclaiming structure. '
                'Watch for participation expansion to confirm the trend change is genuine.'
            )

    # ── Pattern F: Persistent liquidity draw ──────────────────────────────
    draw = _dominant_draw(sessions)
    if draw:
        draw_count = sum(
            1 for s in sessions
            if any(f'Primary draw: {draw}' in ev for ev in s.get('key_events', []))
        )
        if draw_count >= 2:
            return (
                f'Market has consistently drawn toward {draw} across {draw_count} recent sessions -- '
                f'this level is the primary unresolved target. '
                f'Until tagged or structurally negated, it remains the dominant liquidity objective.'
            )

    # ── Default: recent session + brief prior context ─────────────────────
    recent_narrative = sessions[0].get('narrative', '')
    if not recent_narrative:
        recent_narrative = f"Current session: {states[0]}"

    if n >= 2:
        prev = sessions[1]
        prev_state = prev.get('thesis_state', 'UNKNOWN')
        prev_date  = prev.get('date', '')
        if prev_state != states[0]:
            prev_label = prev_state.lower().replace('_', ' ')
            return (
                f'{recent_narrative} '
                f'Prior session ({prev_date}) was {prev_label} -- '
                f'market conditions are shifting.'
            )

    return recent_narrative


# ── Main compute ──────────────────────────────────────────────────────────────

def compute_session_memory() -> dict:
    """
    Update the session memory store. Called after compute_synthesis().

    On each call:
      - If today (ET) matches current_session.date: update current session with latest intelligence.
      - If the date has changed: promote current_session to completed history (capped at 5),
        start a fresh current_session for today.

    The rolling narrative is rebuilt on every call.
    """
    try:
        raw = _read_json(_MEM_FILE)

        synth  = _read_json(_SYN_FILE)
        mr2    = _read_json(_MR2_FILE)
        ms     = _read_json(_MS_FILE)
        part   = _read_json(_P_FILE)
        liq    = _read_json(_LIQ_FILE)

        ms_nq  = ms.get('nq', {})
        liq_nq = liq.get('nq', {})

        today    = _current_et_date()
        sessions = list(raw.get('sessions', []))   # completed sessions, most-recent first
        current  = dict(raw.get('current_session', {}))

        # ── Session transition ──────────────────────────────────────────
        current_date = current.get('date', '')
        if current_date and current_date != today:
            # The date changed: today is a new session.
            # Promote the previous current_session to completed history.
            if _is_valid_session(current):
                sessions = [current] + sessions
                sessions = sessions[:_MAX_SESSIONS]
            current = {}

        # ── Rebuild current session with latest intelligence ────────────
        current = _build_session_record(today, synth, ms_nq, liq_nq, part, mr2)

        # ── Rolling narrative from all sessions (current + history) ─────
        all_sessions = [current] + sessions   # current first, then history
        narrative    = _generate_rolling_narrative(all_sessions)

        state = {
            'current_session':   current,
            'sessions':          sessions,
            'rolling_narrative': narrative,
            'session_count':     len(sessions),
            'last_updated':      _utc_iso(),
        }

        _MEM_FILE.write_text(json.dumps(state, indent=2, default=str), encoding='utf-8')

        print(
            f'[session_memory] {today} state={current.get("thesis_state")} '
            f'part={current.get("participation")} | {len(sessions)} completed sessions'
        )
        return state

    except Exception as exc:
        print(f'[session_memory] compute error: {exc}')
        return _empty_state()


def _empty_state() -> dict:
    return {
        'current_session':   {},
        'sessions':          [],
        'rolling_narrative': 'Session memory unavailable.',
        'session_count':     0,
        'last_updated':      _utc_iso(),
    }


# ── Load / format ─────────────────────────────────────────────────────────────

def load_session_memory() -> dict:
    data = _read_json(_MEM_FILE)
    return data if data else _empty_state()


def format_for_prompt(mem: dict) -> str:
    """
    Session memory block for the Claude evaluation prompt.
    Placed before the synthesis block so Claude reads historical context first.
    """
    narrative = mem.get('rolling_narrative', '')
    current   = mem.get('current_session', {})
    sessions  = mem.get('sessions', [])

    if not narrative or narrative == 'Session memory unavailable.':
        return ''

    lines = ['=== SESSION MEMORY ===']
    lines.append(f'Narrative: {narrative}')

    all_sessions = [current] + sessions if current else sessions
    if len(all_sessions) > 1:
        lines.append('')
        lines.append('Recent sessions (most recent first):')
        for s in all_sessions:
            date        = s.get('date', '?')
            state       = s.get('thesis_state', '?')
            nq_pct      = s.get('nq_pct', 0.0)
            part        = s.get('participation', '?')
            session_nar = s.get('narrative', '')
            marker      = '(today)' if s is current else ''
            lines.append(
                f'  {date} {marker}: [{state}] {nq_pct:+.2f}% | {part} part'
                + (f' -- {session_nar}' if session_nar else '')
            )

    lines.append('=== END SESSION MEMORY ===')
    return '\n'.join(lines)


def format_for_assistant(mem: dict) -> str:
    """Compact single-line session memory for the assistant context."""
    narrative = mem.get('rolling_narrative', '')
    n_sess    = mem.get('session_count', 0)
    current   = mem.get('current_session', {})
    state     = current.get('thesis_state', '?')
    today     = current.get('date', '?')
    if not narrative or narrative == 'Session memory unavailable.':
        return ''
    horizon = f'{n_sess + 1} sessions' if n_sess > 0 else '1 session'
    return f'MEMORY ({horizon}): "{narrative}" | today={state} ({today})'
