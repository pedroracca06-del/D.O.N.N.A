"""
test_phase_i_post_trade_review.py — Phase I post-trade self-review smoke tests.

Covers:
  1.  HIGH-confidence WIN snapshot: GOOD_READ_GOOD_DECISION
  2.  HIGH-confidence LOSS snapshot: GOOD_READ_BAD_DECISION
  3.  MEDIUM-confidence WIN snapshot: GOOD_READ_GOOD_DECISION
  4.  MEDIUM-confidence LOSS snapshot: INSUFFICIENT_DATA (conservative)
  5.  LOW-confidence journal match: INSUFFICIENT_DATA with cautious lesson
  6.  No linked outcome: INSUFFICIENT_DATA
  7.  Rejected snapshot: NO_TRADE_CORRECT regardless of confidence
  8.  No-trade snapshot: NO_TRADE_CORRECT
  9.  Malformed / None snapshot does not crash
 10.  Malformed / None outcome_link does not crash
 11.  Compact record has all required fields
 12.  No win_rate / avg_r / performance claims in any output
 13.  Low-confidence section_c includes low_confidence_note
 14.  DEGRADED MCP status appears in lesson note

Run:  python tests/test_phase_i_post_trade_review.py
      python -m pytest tests/test_phase_i_post_trade_review.py -v
"""
from __future__ import annotations
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault('ALPACA_API_KEY',    '')
os.environ.setdefault('ALPACA_SECRET_KEY', '')

from engines.reasoning import (
    _build_decision_snapshot, _build_mcp_snapshot,
    parse_nova_tables, compute_mcp_health,
)
from engines.post_trade_review import (
    build_post_trade_review, post_trade_review_compact,
    _classify_conclusion, _build_lesson,
    _section_a_what_nova_saw, _section_b_what_nova_decided, _section_c_what_happened,
)

# ── Fixtures ──────────────────────────────────────────────────────────────────

_FORBIDDEN_KEYS = frozenset({'win_rate', 'avg_r', 'expected_value', 'hit_rate'})

_REQUIRED_COMPACT_KEYS = {
    'decision_id', 'timestamp', 'symbol', 'session', 'setup_type', 'direction',
    'signal_type', 'grade', 'trade_status', 'outcome', 'realized_pnl',
    'r_multiple', 'match_confidence', 'match_method', 'conclusion', 'lesson',
    'mcp_status', 'mcp_confidence',
}


def _v2_rows(ticker: str = 'MES1!') -> list[str]:
    return [
        'NOVA BRIDGE',
        'CMD | WAIT', 'SYS_STATE | READING MARKET', 'SCORE | B 0 / S 48',
        'CONF | LOW 44%', 'PROS_ENG | BUILDING', 'P_DISPL | BULL',
        'P_RETRACE | TOO DEEP', 'P_OTE | DEEP', 'P_CONT | BUILDING',
        'P_QUALITY | GOOD', 'P_STDV | NORMAL',
        'IB H | 21480.00', 'IB L | 21340.00',
        'O_STATE | ORB_EXPIRED', 'O_BIAS | BULL DEAD', 'O_TYPE | EDGE DFND',
        'O_REJ_Q | 3 EDGE', 'O_HIGH | 21420.00', 'O_MID | 21380.00', 'O_LOW | 21340.00',
        'BRIDGE_VER | 2', f'TICKER | {ticker}', 'TF | 1', 'IB_STATUS | COMPLETE',
        'SESSION | NY_CASH', 'ORB_ACTIVE | 0', 'PROS_ACTIVE | 1',
        'COOLDOWN | 0', 'TRAP | 0', 'ICT_STEP | 1',
        'PEER_ALIGN | CONFIRM', 'DRAW_TARGET | 21560.00', 'DRAW_DIR | UP',
    ]


def _base_snap(symbol: str = 'CME_MINI:MES1!', ts: str = '2026-06-30T14:00:00Z') -> dict:
    tables     = [_v2_rows()]
    chart_ctx  = {'connected': True, 'symbol': symbol, 'timeframe': '1', 'nova_tables': tables}
    session    = {'session': 'NY_CASH', 'time_et': '10:00'}
    nova_state = parse_nova_tables(tables)
    health     = compute_mcp_health(chart_ctx, nova_state)
    snap       = _build_mcp_snapshot(chart_ctx, nova_state, health, session)
    snap['timestamp'] = ts
    return snap


def _decision_snap(
    signal_type: str   = 'EXECUTION_READY',
    direction:   str   = 'LONG',
    is_exec_ready: bool = True,
    is_rejected:   bool = False,
    is_no_trade:   bool = False,
    is_heads_up:   bool = False,
    grade:         str  = 'A',
    mcp_status:    str  = 'OK',
) -> dict:
    base = _base_snap()
    if mcp_status != 'OK':
        h = dict(base.get('mcp_health') or {})
        h['status'] = mcp_status
        base['mcp_health'] = h

    pros = {'phase': 'CONTINUATION', 'direction': 'BULL', 'setup_type': 'PROS_CONT',
            'has_signal': True, 'signal_strength': 'STRONG', 'ote_status': 'TAGGED',
            'cont_quality': 'CONFIRMED'}
    orb  = {'phase': 'ORB_EXPIRED', 'direction': 'BULL', 'setup_type': 'ORB_EDGE',
            'has_signal': False, 'entry_type': 'EDGE', 'entry_quality': 'GOOD',
            'in_context': True, 'orb_range': 80.0}
    ib   = {'draw': 'IB_H', 'draw_source': 'pros_table', 'aligned': True,
            'ib_range': 140.0, 'ib_tight': False, 'ib_source': 'pros_table'}
    claude_dec = {
        'alert_required': is_exec_ready or is_heads_up,
        'alert_type':     signal_type if (is_exec_ready or is_heads_up) else 'NO_TRADE',
        'setup_type':     'PROS_CONT', 'direction': direction, 'grade': grade,
        'entry_zone':     '21365-21375', 'stop': '21330', 'tp1': '21480', 'rr': '3.0',
        'notes': 'IB alignment + OTE tagged', 'reasoning': 'Clean PROS continuation.',
        'no_alert_reason': '' if (is_exec_ready or is_heads_up) else 'low conviction',
    }
    ds = _build_decision_snapshot(
        base, pros_eval=pros, orb_eval=orb, ib_eval=ib,
        pre_signal=signal_type, pre_setup='PROS_CONT', pre_rationale='All conditions met',
        decision=claude_dec, claude_called=True, alert_generated=is_exec_ready or is_heads_up,
    )
    # Force flags for test cases where signal_type alone doesn't set them
    ds['is_execution_ready'] = is_exec_ready
    ds['is_rejected']        = is_rejected
    ds['is_no_trade']        = is_no_trade
    ds['is_heads_up']        = is_heads_up
    return ds


def _link(
    confidence: str   = 'HIGH',
    outcome:    str   = 'WIN',
    method:     str   = 'SIGNAL_TIMESTAMP_FUZZY',
    trade_status: str = 'TAKEN',
) -> dict:
    return {
        'trade_status':     trade_status,
        'outcome':          outcome,
        'realized_pnl':     None,
        'r_multiple':       None,
        'entry_price':      None,
        'exit_price':       None,
        'entry_time':       None,
        'exit_time':        None,
        'close_reason':     '',
        'rejection_reason': '',
        'match_confidence': confidence,
        'match_method':     method,
        'linked_signal_id': 'SIG_001',
        'linked_trace_id':  '',
    }


def _no_link() -> dict:
    return {
        'trade_status': 'EXECUTION_READY_NOT_EXECUTED', 'outcome': 'UNKNOWN',
        'realized_pnl': None, 'r_multiple': None,
        'entry_price': None, 'exit_price': None, 'entry_time': None, 'exit_time': None,
        'close_reason': '', 'rejection_reason': '',
        'match_confidence': 'NONE', 'match_method': 'NONE',
        'linked_signal_id': '', 'linked_trace_id': '',
    }


def _no_forbidden(obj: dict) -> bool:
    return not any(k in obj for k in _FORBIDDEN_KEYS)


# ── Tests ──────────────────────────────────────────────────────────────────────

def test_high_confidence_win_is_good_read_good_decision():
    snap   = _decision_snap()
    link   = _link('HIGH', 'WIN')
    review = build_post_trade_review(snap, link)
    assert review['conclusion'] == 'GOOD_READ_GOOD_DECISION', review['conclusion']
    assert review['lesson'], 'lesson must be non-empty'
    assert 'WIN' in review['lesson'] or 'win' in review['lesson'].lower()
    assert _no_forbidden(review)


def test_high_confidence_loss_is_good_read_bad_decision():
    snap   = _decision_snap()
    link   = _link('HIGH', 'LOSS', trade_status='TAKEN')
    review = build_post_trade_review(snap, link)
    assert review['conclusion'] == 'GOOD_READ_BAD_DECISION', review['conclusion']
    assert 'LOSS' in review['lesson'] or 'loss' in review['lesson'].lower()
    assert _no_forbidden(review)


def test_medium_confidence_win_is_good_read_good_decision():
    snap   = _decision_snap()
    link   = _link('MEDIUM', 'WIN', method='SIGNAL_TIMESTAMP_FUZZY')
    review = build_post_trade_review(snap, link)
    assert review['conclusion'] == 'GOOD_READ_GOOD_DECISION', review['conclusion']
    # MEDIUM label should appear in lesson
    assert 'MEDIUM' in review['lesson'] or 'early signal' in review['lesson']
    assert _no_forbidden(review)


def test_medium_confidence_loss_is_insufficient_data():
    snap   = _decision_snap()
    link   = _link('MEDIUM', 'LOSS', trade_status='TAKEN')
    review = build_post_trade_review(snap, link)
    assert review['conclusion'] == 'INSUFFICIENT_DATA', review['conclusion']
    assert _no_forbidden(review)


def test_low_confidence_journal_match_is_insufficient_data():
    snap   = _decision_snap()
    link   = _link('LOW', 'WIN', method='DATE_TICKER_DIR', trade_status='TAKEN')
    review = build_post_trade_review(snap, link)
    assert review['conclusion'] == 'INSUFFICIENT_DATA', review['conclusion']
    # Lesson must carry a low-confidence qualifier
    assert 'LOW' in review['lesson'] or 'note only' in review['lesson']
    assert _no_forbidden(review)


def test_no_linked_outcome_is_insufficient_data():
    snap   = _decision_snap()
    link   = _no_link()
    review = build_post_trade_review(snap, link)
    assert review['conclusion'] == 'INSUFFICIENT_DATA', review['conclusion']
    assert _no_forbidden(review)


def test_rejected_snapshot_is_no_trade_correct():
    snap   = _decision_snap(is_exec_ready=False, is_rejected=True)
    # Even with a WIN link, a rejected snapshot stays NO_TRADE_CORRECT
    for confidence in ('HIGH', 'MEDIUM', 'LOW', 'NONE'):
        link   = _link(confidence, 'WIN')
        review = build_post_trade_review(snap, link)
        assert review['conclusion'] == 'NO_TRADE_CORRECT', (
            f'confidence={confidence}: expected NO_TRADE_CORRECT, got {review["conclusion"]}'
        )
        assert _no_forbidden(review)


def test_no_trade_snapshot_is_no_trade_correct():
    snap   = _decision_snap(signal_type='NO_TRADE', is_exec_ready=False, is_no_trade=True)
    link   = _no_link()
    review = build_post_trade_review(snap, link)
    assert review['conclusion'] == 'NO_TRADE_CORRECT', review['conclusion']
    assert _no_forbidden(review)


def test_malformed_snapshot_does_not_crash():
    bad_inputs = [None, {}, {'timestamp': None, 'symbol': None}, 'not a dict', 42]
    link = _no_link()
    for inp in bad_inputs:
        review = build_post_trade_review(inp, link)   # type: ignore[arg-type]
        assert isinstance(review, dict), f'Expected dict, got {type(review)}'
        assert 'conclusion' in review
        assert 'lesson' in review
        assert _no_forbidden(review)


def test_malformed_outcome_link_does_not_crash():
    snap = _decision_snap()
    bad_links = [None, {}, {'match_confidence': None}, 'not a dict', 42]
    for lnk in bad_links:
        review = build_post_trade_review(snap, lnk)   # type: ignore[arg-type]
        assert isinstance(review, dict), f'Expected dict, got {type(review)}'
        assert 'conclusion' in review
        assert _no_forbidden(review)


def test_compact_record_has_all_required_fields():
    snap    = _decision_snap()
    link    = _link('HIGH', 'WIN')
    review  = build_post_trade_review(snap, link)
    compact = post_trade_review_compact(review)
    missing = _REQUIRED_COMPACT_KEYS - compact.keys()
    assert not missing, f'compact record missing fields: {missing}'
    assert _no_forbidden(compact)


def test_no_performance_claims_in_output():
    for outcome in ('WIN', 'LOSS', 'UNKNOWN', 'REJECTED'):
        for confidence in ('HIGH', 'MEDIUM', 'LOW', 'NONE'):
            snap    = _decision_snap()
            link    = _link(confidence, outcome)
            review  = build_post_trade_review(snap, link)
            compact = post_trade_review_compact(review)
            assert _no_forbidden(review),  f'forbidden key in review (conf={confidence}, out={outcome})'
            assert _no_forbidden(compact), f'forbidden key in compact (conf={confidence}, out={outcome})'


def test_low_confidence_section_c_has_note():
    snap   = _decision_snap()
    link   = _link('LOW', 'WIN', method='DATE_TICKER_DIR', trade_status='TAKEN')
    review = build_post_trade_review(snap, link)
    sc     = review['section_c_what_happened']
    assert sc['low_confidence_note'], 'LOW confidence must produce a note'
    assert 'LOW' in sc['low_confidence_note']


def test_degraded_mcp_appears_in_lesson():
    snap   = _decision_snap(mcp_status='DEGRADED')
    link   = _link('HIGH', 'WIN')
    review = build_post_trade_review(snap, link)
    assert 'DEGRADED' in review['lesson'], (
        f'DEGRADED mcp_status should appear in lesson. Got: {review["lesson"]}'
    )


# ── Runner ────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    tests = [
        ('HIGH conf WIN: GOOD_READ_GOOD_DECISION',       test_high_confidence_win_is_good_read_good_decision),
        ('HIGH conf LOSS: GOOD_READ_BAD_DECISION',       test_high_confidence_loss_is_good_read_bad_decision),
        ('MEDIUM conf WIN: GOOD_READ_GOOD_DECISION',     test_medium_confidence_win_is_good_read_good_decision),
        ('MEDIUM conf LOSS: INSUFFICIENT_DATA',          test_medium_confidence_loss_is_insufficient_data),
        ('LOW conf journal: INSUFFICIENT_DATA',          test_low_confidence_journal_match_is_insufficient_data),
        ('No linked outcome: INSUFFICIENT_DATA',         test_no_linked_outcome_is_insufficient_data),
        ('Rejected snap: NO_TRADE_CORRECT',              test_rejected_snapshot_is_no_trade_correct),
        ('No-trade snap: NO_TRADE_CORRECT',              test_no_trade_snapshot_is_no_trade_correct),
        ('Malformed snapshot does not crash',            test_malformed_snapshot_does_not_crash),
        ('Malformed outcome_link does not crash',        test_malformed_outcome_link_does_not_crash),
        ('Compact record has all required fields',       test_compact_record_has_all_required_fields),
        ('No performance claims in output',              test_no_performance_claims_in_output),
        ('LOW conf section_c has low_confidence_note',  test_low_confidence_section_c_has_note),
        ('DEGRADED MCP appears in lesson',              test_degraded_mcp_appears_in_lesson),
    ]

    passed = failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f'  PASS  {name}')
            passed += 1
        except Exception as exc:
            print(f'  FAIL  {name}: {exc}')
            failed += 1

    status = 'OK' if not failed else 'FAIL'
    print(f'\n{passed}/{passed + failed} tests passed [{status}]')
    if failed:
        raise SystemExit(1)
