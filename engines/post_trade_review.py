"""
post_trade_review.py — Post-trade self-review layer for NOVA.

Generates a structured narrative review of a decision snapshot paired with its
outcome link.  Answers five questions:
  1. What did NOVA see?
  2. What did NOVA decide?
  3. What actually happened?
  4. Did the read / decision / outcome align?
  5. What should be remembered for future similar setups?

Observability only — no execution impact, no rule changes, no strategy mutations.
"""
from __future__ import annotations


# ── Conclusion classifier ──────────────────────────────────────────────────────

_VALID_CONCLUSIONS = frozenset({
    'GOOD_READ_GOOD_DECISION',
    'GOOD_READ_BAD_DECISION',
    'BAD_READ_DECISION_UNRELIABLE',
    'NO_TRADE_CORRECT',
    'NO_TRADE_MISSED_OPPORTUNITY',
    'INSUFFICIENT_DATA',
})


def _classify_conclusion(snapshot: dict, link: dict) -> str:
    """Return one conclusion label.  Conservative — defaults to INSUFFICIENT_DATA."""
    confidence = (link.get('match_confidence') or 'NONE').upper()
    outcome    = (link.get('outcome') or 'UNKNOWN').upper()
    is_rej     = bool(snapshot.get('is_rejected'))
    is_no_tr   = bool(snapshot.get('is_no_trade'))

    # No-trade / rejected snapshots: governance worked — trade was not entered
    if is_rej or is_no_tr:
        return 'NO_TRADE_CORRECT'

    # No linked outcome — cannot draw any conclusion
    if confidence == 'NONE':
        return 'INSUFFICIENT_DATA'

    # Require at least MEDIUM confidence to claim anything about live trades
    if confidence not in ('HIGH', 'MEDIUM'):
        return 'INSUFFICIENT_DATA'

    if outcome == 'WIN':
        return 'GOOD_READ_GOOD_DECISION'

    if outcome == 'LOSS':
        # HIGH confidence loss: read triggered the trade, so decision was the variable
        if confidence == 'HIGH':
            return 'GOOD_READ_BAD_DECISION'
        return 'INSUFFICIENT_DATA'

    if outcome in ('REJECTED', 'UNKNOWN'):
        return 'INSUFFICIENT_DATA'

    return 'INSUFFICIENT_DATA'


# ── Lesson generator ───────────────────────────────────────────────────────────

def _build_lesson(snapshot: dict, link: dict, conclusion: str) -> str:
    """Short structured lesson note.  Never a hard rule.  Always qualified by confidence."""
    confidence = (link.get('match_confidence') or 'NONE').upper()
    outcome    = (link.get('outcome') or 'UNKNOWN').upper()
    setup      = snapshot.get('setup_type') or 'unknown setup'
    direction  = (snapshot.get('direction') or '').upper()
    session    = snapshot.get('session') or 'unknown session'
    grade      = snapshot.get('grade') or ''
    did        = snapshot.get('decision_id') or ''

    pe = snapshot.get('pros_eval_summary') or {}
    ie = snapshot.get('ib_eval_summary') or {}
    ib_draw    = ie.get('draw') or ''
    ib_aligned = ie.get('aligned')
    pros_phase = pe.get('phase') or ''
    pros_ote   = pe.get('ote_status') or ''
    pros_cont  = pe.get('cont_quality') or ''

    mcp_h      = snapshot.get('mcp_health') or {}
    mcp_status = (mcp_h.get('status') or '').upper()
    mcp_note   = (
        ' MCP data was DEGRADED — indicator reliability uncertain.'
        if mcp_status == 'DEGRADED' else ''
    )

    conf_tag: str = {
        'HIGH':   '',
        'MEDIUM': ' Outcome confidence is MEDIUM — treat as early signal, not a rule.',
        'LOW':    ' Outcome data is LOW-confidence (journal-only match) — note only, not a rule.',
        'NONE':   ' No outcome data linked yet — structural observation only.',
    }.get(confidence, ' Outcome confidence unknown.')

    if conclusion == 'INSUFFICIENT_DATA':
        return (
            f"{setup} {direction} in {session} ({did}) — insufficient outcome data to draw lessons."
            f"{mcp_note} Monitor until outcome is confirmed.{conf_tag}"
        )

    if conclusion == 'NO_TRADE_CORRECT':
        return (
            f"No trade taken for {setup} {direction} in {session}.{mcp_note}"
            f" Governance blocked entry — no conflicting outcome linked.{conf_tag}"
        )

    if conclusion == 'GOOD_READ_GOOD_DECISION':
        ib_note    = f' IB draw={ib_draw}, aligned={ib_aligned}.' if ib_draw else ''
        pros_note  = (
            f' PROS phase={pros_phase}, OTE={pros_ote}, cont={pros_cont}.'
            if pros_phase else ''
        )
        grade_note = f' Grade {grade}.' if grade else ''
        return (
            f"{setup} {direction} in {session} produced a WIN.{grade_note}"
            f"{ib_note}{pros_note}{mcp_note}{conf_tag}"
        )

    if conclusion == 'GOOD_READ_BAD_DECISION':
        ib_note = f' IB draw={ib_draw}, aligned={ib_aligned}.' if ib_draw else ''
        return (
            f"{setup} {direction} in {session} went to a LOSS despite signal.{ib_note}"
            f" Review entry timing, IB alignment, and OTE quality at entry.{mcp_note}{conf_tag}"
        )

    if conclusion == 'BAD_READ_DECISION_UNRELIABLE':
        return (
            f"{setup} {direction} in {session} — read reliability in question."
            f"{mcp_note}{conf_tag}"
        )

    if conclusion == 'NO_TRADE_MISSED_OPPORTUNITY':
        return (
            f"No trade taken for {setup} {direction} in {session}."
            f" Possible missed opportunity — requires price replay to confirm.{mcp_note}{conf_tag}"
        )

    return f"{setup} {direction} in {session} — review complete.{mcp_note}{conf_tag}"


# ── Section builders ───────────────────────────────────────────────────────────

def _section_a_what_nova_saw(snapshot: dict) -> dict:
    h  = snapshot.get('mcp_health') or {}
    pe = snapshot.get('pros_eval_summary') or {}
    oe = snapshot.get('orb_eval_summary') or {}
    ie = snapshot.get('ib_eval_summary') or {}
    return {
        'session':         snapshot.get('session'),
        'ib_status':       snapshot.get('ib_status'),
        'ib_draw':         ie.get('draw'),
        'ib_draw_source':  ie.get('draw_source'),
        'ib_aligned':      ie.get('aligned'),
        'ib_range':        ie.get('ib_range'),
        'ib_tight':        ie.get('ib_tight'),
        'orb_active':      snapshot.get('orb_active'),
        'orb_phase':       oe.get('phase'),
        'orb_entry_type':  oe.get('entry_type'),
        'orb_in_context':  oe.get('in_context'),
        'orb_range':       oe.get('orb_range'),
        'pros_active':     snapshot.get('pros_active'),
        'pros_phase':      pe.get('phase'),
        'pros_ote_status': pe.get('ote_status'),
        'pros_cont':       pe.get('cont_quality'),
        'pros_strength':   pe.get('signal_strength'),
        'peer_alignment':  snapshot.get('peer_alignment'),
        'draw_direction':  snapshot.get('draw_direction'),
        'mcp_status':      h.get('status'),
        'mcp_confidence':  h.get('confidence'),
        'parser_mode':     snapshot.get('parser_mode'),
        'parse_status':    snapshot.get('parse_status'),
    }


def _section_b_what_nova_decided(snapshot: dict) -> dict:
    return {
        'pre_signal':         snapshot.get('pre_signal'),
        'pre_setup':          snapshot.get('pre_setup'),
        'pre_rationale':      snapshot.get('pre_rationale'),
        'final_signal_type':  snapshot.get('signal_type'),
        'final_setup_type':   snapshot.get('setup_type'),
        'direction':          snapshot.get('direction'),
        'grade':              snapshot.get('grade'),
        'entry_zone':         snapshot.get('entry_zone'),
        'stop':               snapshot.get('stop'),
        'tp1':                snapshot.get('tp1'),
        'rr':                 snapshot.get('rr'),
        'rationale':          snapshot.get('rationale'),
        'claude_called':      snapshot.get('claude_called'),
        'is_execution_ready': snapshot.get('is_execution_ready'),
        'is_heads_up':        snapshot.get('is_heads_up'),
        'is_no_trade':        snapshot.get('is_no_trade'),
        'is_rejected':        snapshot.get('is_rejected'),
        'rejection_reason':   snapshot.get('rejection_reason'),
        'alert_generated':    snapshot.get('alert_generated'),
    }


def _section_c_what_happened(link: dict) -> dict:
    confidence = (link.get('match_confidence') or 'NONE').upper()
    return {
        'trade_status':       link.get('trade_status', 'UNKNOWN'),
        'outcome':            link.get('outcome', 'UNKNOWN'),
        'realized_pnl':       link.get('realized_pnl'),
        'r_multiple':         link.get('r_multiple'),
        'entry_price':        link.get('entry_price'),
        'exit_price':         link.get('exit_price'),
        'entry_time':         link.get('entry_time'),
        'exit_time':          link.get('exit_time'),
        'close_reason':       link.get('close_reason', ''),
        'rejection_reason':   link.get('rejection_reason', ''),
        'match_confidence':   confidence,
        'match_method':       link.get('match_method', 'NONE'),
        'linked_signal_id':   link.get('linked_signal_id', ''),
        'linked_trace_id':    link.get('linked_trace_id', ''),
        'low_confidence_note': (
            'Outcome data is LOW-confidence (journal-only match). '
            'Do not treat this as a confirmed result.'
            if confidence == 'LOW' else ''
        ),
    }


# ── Main review builder ────────────────────────────────────────────────────────

def build_post_trade_review(snapshot: dict, outcome_link: dict) -> dict:
    """Build a structured post-trade review from a decision snapshot + outcome link.

    Observability only — no mutations, no execution impact, no rule changes.
    """
    if not isinstance(snapshot, dict):
        snapshot = {}
    if not isinstance(outcome_link, dict):
        outcome_link = {}

    h   = snapshot.get('mcp_health') or {}
    fp  = snapshot.get('setup_fingerprint') or {}

    conclusion = _classify_conclusion(snapshot, outcome_link)
    lesson     = _build_lesson(snapshot, outcome_link, conclusion)

    return {
        # ── Identity ──────────────────────────────────────────────────────────
        'decision_id':       snapshot.get('decision_id'),
        'timestamp':         snapshot.get('timestamp'),
        'symbol':            snapshot.get('symbol'),
        'setup_type':        snapshot.get('setup_type'),
        'direction':         snapshot.get('direction'),
        'signal_type':       snapshot.get('signal_type'),
        'parser_mode':       snapshot.get('parser_mode'),
        'parse_status':      snapshot.get('parse_status'),
        'mcp_status':        h.get('status'),
        'mcp_confidence':    h.get('confidence'),
        'setup_fingerprint': fp,
        # ── Outcome ───────────────────────────────────────────────────────────
        'trade_status':      outcome_link.get('trade_status', 'UNKNOWN'),
        'outcome':           outcome_link.get('outcome', 'UNKNOWN'),
        'realized_pnl':      outcome_link.get('realized_pnl'),
        'r_multiple':        outcome_link.get('r_multiple'),
        'match_method':      outcome_link.get('match_method', 'NONE'),
        'match_confidence':  outcome_link.get('match_confidence', 'NONE'),
        # ── Review sections ───────────────────────────────────────────────────
        'section_a_what_nova_saw':     _section_a_what_nova_saw(snapshot),
        'section_b_what_nova_decided': _section_b_what_nova_decided(snapshot),
        'section_c_what_happened':     _section_c_what_happened(outcome_link),
        # ── Conclusion ────────────────────────────────────────────────────────
        'conclusion': conclusion,
        'lesson':     lesson,
    }


# ── Compact record for listing endpoints ──────────────────────────────────────

def post_trade_review_compact(review: dict) -> dict:
    """One-row record per review — suitable for the /api/mcp-replay/post-trade-reviews endpoint."""
    sa = review.get('section_a_what_nova_saw') or {}
    sb = review.get('section_b_what_nova_decided') or {}
    return {
        'decision_id':      review.get('decision_id'),
        'timestamp':        review.get('timestamp'),
        'symbol':           review.get('symbol'),
        'session':          sa.get('session'),
        'setup_type':       review.get('setup_type'),
        'direction':        review.get('direction'),
        'signal_type':      review.get('signal_type'),
        'grade':            sb.get('grade'),
        'trade_status':     review.get('trade_status'),
        'outcome':          review.get('outcome'),
        'realized_pnl':     review.get('realized_pnl'),
        'r_multiple':       review.get('r_multiple'),
        'match_confidence': review.get('match_confidence'),
        'match_method':     review.get('match_method'),
        'conclusion':       review.get('conclusion'),
        'lesson':           review.get('lesson'),
        'mcp_status':       review.get('mcp_status'),
        'mcp_confidence':   review.get('mcp_confidence'),
    }
