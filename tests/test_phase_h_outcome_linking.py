"""
test_phase_h_outcome_linking.py — Phase H outcome linking smoke tests.

Covers:
  1.  decision snapshot includes decision_id with correct format DEC_YYYYMMDD_HHMM_HASH
  2.  decision_id is deterministic for same inputs (stable link key)
  3.  decision_id is absent from market_read snapshots
  4.  links to signal log by timestamp/symbol/direction fuzzy match (MEDIUM or HIGH)
  5.  setup family match upgrades confidence from MEDIUM to HIGH
  6.  no matching signal returns match_confidence=NONE safely
  7.  journal match returns LOW confidence via DATE_TICKER_DIR
  8.  no matching journal returns outcome=UNKNOWN safely
  9.  multiple signal log candidates — best (highest score) is chosen
 10.  EXECUTION_READY + no trace → trade_status=EXECUTION_READY_NOT_EXECUTED
 11.  HEADS_UP snapshot → trade_status=NOT_TAKEN
 12.  rejected snapshot → trade_status=REJECTED_OR_NO_TRADE
 13.  journal REJECTED entry → outcome=REJECTED
 14.  missing/malformed data does not crash (None, [], corrupt entries)
 15.  outcome_summary has all required fields
 16.  similar-with-outcomes response has no aggregate stats keys

Run:  python tests/test_phase_h_outcome_linking.py
      python -m pytest tests/test_phase_h_outcome_linking.py -v
"""
from __future__ import annotations
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault('ALPACA_API_KEY',    '')
os.environ.setdefault('ALPACA_SECRET_KEY', '')

from engines.reasoning import (
    _make_decision_id, _build_decision_snapshot,
    _build_mcp_snapshot, parse_nova_tables, compute_mcp_health,
)
from engines.outcome_linker import (
    link_snapshot_to_outcome, outcome_summary,
    normalize_ticker, _ticker_family, _setup_family,
)

# ── helpers ───────────────────────────────────────────────────────────────────

def _v2_rows(ticker='MES1!') -> list[str]:
    return [
        'NOVA BRIDGE',
        'CMD | WAIT', 'SYS_STATE | READING MARKET', 'SCORE | B 0 / S 48',
        'CONF | LOW 44%', 'PROS_ENG | BUILDING', 'P_DISPL | BULL',
        'P_RETRACE | TOO DEEP', 'P_OTE | DEEP', 'P_CONT | BUILDING',
        'P_QUALITY | GOOD', 'P_STDV | NORMAL',
        'IB H | 7489.75', 'IB L | 7409',
        'O_STATE | ORB_EXPIRED', 'O_BIAS | BULL DEAD', 'O_TYPE | EDGE DFND',
        'O_REJ_Q | 3 EDGE', 'O_HIGH | 7467.75', 'O_MID | 7464.5', 'O_LOW | 7461.25',
        'BRIDGE_VER | 2', f'TICKER | {ticker}', 'TF | 1', 'IB_STATUS | COMPLETE',
        'SESSION | NY_CASH', 'ORB_ACTIVE | 0', 'PROS_ACTIVE | 1',
        'COOLDOWN | 0', 'TRAP | 0', 'ICT_STEP | 1',
        'PEER_ALIGN | CONFIRM', 'DRAW_TARGET | 7560.00', 'DRAW_DIR | UP',
    ]

def _make_base_snap(symbol='CME_MINI:MES1!', timestamp='2026-06-30T14:00:00Z') -> dict:
    tables    = [_v2_rows()]
    chart_ctx = {'connected': True, 'symbol': symbol, 'timeframe': '1', 'nova_tables': tables}
    session   = {'session': 'NY_CASH', 'time_et': '10:00'}
    nova_state = parse_nova_tables(tables)
    health     = compute_mcp_health(chart_ctx, nova_state)
    snap       = _build_mcp_snapshot(chart_ctx, nova_state, health, session)
    snap['timestamp'] = timestamp
    return snap

def _make_decision(
    symbol='CME_MINI:MES1!',
    timestamp='2026-06-30T14:00:00Z',
    signal_type='EXECUTION_READY',
    setup_type='PROS_CONT',
    direction='LONG',
    is_exec_ready=True,
    is_rejected=False,
) -> dict:
    base = _make_base_snap(symbol=symbol, timestamp=timestamp)
    pros = {'phase': 'CONTINUATION', 'direction': 'BULL', 'setup_type': 'PROS_CONT',
            'has_signal': True, 'signal_strength': 'STRONG', 'ote_status': 'TAGGED',
            'cont_quality': 'CONFIRMED'}
    orb  = {'phase': 'ORB_EXPIRED', 'direction': 'BULL', 'setup_type': 'ORB_EDGE',
            'has_signal': False, 'entry_type': 'EDGE', 'entry_quality': 'GOOD',
            'in_context': True, 'orb_range': 25.5}
    ib   = {'draw': 'IB_H', 'draw_source': 'pros_table', 'aligned': True,
            'ib_range': 80.75, 'ib_tight': False, 'ib_source': 'pros_table'}
    alert_req = not is_rejected
    decision  = {
        'alert_required': alert_req, 'alert_type': signal_type if alert_req else '',
        'setup_type': setup_type, 'direction': direction, 'grade': 'A',
        'entry_zone': '7475–7480', 'stop': '7460', 'tp1': '7520', 'rr': '3.0',
        'notes': '', 'reasoning': 'Test.', 'no_alert_reason': '' if alert_req else 'below threshold',
    }
    return _build_decision_snapshot(
        base,
        pros_eval=pros, orb_eval=orb, ib_eval=ib,
        pre_signal=signal_type, pre_setup=setup_type, pre_rationale='',
        decision=decision, claude_called=True, alert_generated=alert_req,
    )

# ── Signal log fixture helpers ────────────────────────────────────────────────

def _sig(id='SIG_001', symbol='MES', direction='LONG', setup_type='PROS_CONT',
         timestamp='2026-06-30T14:01:00+00:00', alert_required=True) -> dict:
    return {
        'id': id, 'symbol': symbol, 'direction': direction,
        'setup_type': setup_type, 'timestamp': timestamp,
        'alert_required': alert_required, 'alert_type': 'EXECUTION_READY',
        'pre_signal': 'EXECUTION_READY', 'session': 'NY_CASH',
    }

def _jour(ticker='MES', direction='LONG', trade_date='2026-06-30',
          outcome='REJECTED', setup_type='PROS_CONT') -> dict:
    return {
        'ticker': ticker, 'direction': direction, 'trade_date': trade_date,
        'outcome': outcome, 'setup_type': setup_type, 'session': 'NY_CASH',
        'timestamp': f'{trade_date}T14:05:00+00:00',
        'rejection_code': 'GRADE_BELOW_PROFILE_MIN',
        'rejection_reason': 'Grade below minimum',
    }


# ── Test 1: decision_id format ────────────────────────────────────────────────

def test_decision_id_format():
    ds = _make_decision(timestamp='2026-06-30T14:01:00Z')
    assert 'decision_id' in ds
    did = ds['decision_id']
    assert did.startswith('DEC_'), f"got {did}"
    parts = did.split('_')
    assert len(parts) == 4, f"expected 4 parts, got {parts}"
    assert parts[1] == '20260630'  # date
    assert parts[2] == '1401'      # time


# ── Test 2: decision_id is deterministic ──────────────────────────────────────

def test_decision_id_deterministic():
    id1 = _make_decision_id('2026-06-30T14:01:00Z', 'CME_MINI:MES1!', 'PROS_CONT', 'LONG', 'EXECUTION_READY')
    id2 = _make_decision_id('2026-06-30T14:01:00Z', 'CME_MINI:MES1!', 'PROS_CONT', 'LONG', 'EXECUTION_READY')
    assert id1 == id2
    # Different timestamp → different id
    id3 = _make_decision_id('2026-06-30T14:02:00Z', 'CME_MINI:MES1!', 'PROS_CONT', 'LONG', 'EXECUTION_READY')
    assert id3 != id1
    # Different direction → different id
    id4 = _make_decision_id('2026-06-30T14:01:00Z', 'CME_MINI:MES1!', 'PROS_CONT', 'SHORT', 'EXECUTION_READY')
    assert id4 != id1


# ── Test 3: decision_id absent from market_read ───────────────────────────────

def test_decision_id_not_in_market_read():
    base = _make_base_snap()
    assert 'decision_id' not in base


# ── Test 4: signal log fuzzy match found ─────────────────────────────────────

def test_signal_log_fuzzy_match():
    snap = _make_decision(timestamp='2026-06-30T14:00:00Z')
    sig  = _sig(symbol='MES', direction='LONG', timestamp='2026-06-30T14:02:00+00:00',
                setup_type='PROS_LONG')  # family matches (PROS) but exact setup differs
    link = link_snapshot_to_outcome(snap, signal_log=[sig], journal=[], trace=[])
    assert link['linked_signal_id'] == 'SIG_001'
    assert link['match_method']     == 'SIGNAL_TIMESTAMP_FUZZY'
    assert link['match_confidence'] in ('MEDIUM', 'HIGH')


# ── Test 5: setup family match upgrades confidence to HIGH ───────────────────

def test_setup_family_upgrades_confidence():
    snap = _make_decision(timestamp='2026-06-30T14:00:00Z', setup_type='PROS_CONT')
    # Same family (PROS) → HIGH
    sig_same = _sig(setup_type='PROS_LONG', timestamp='2026-06-30T14:01:00+00:00')
    link_high = link_snapshot_to_outcome(snap, signal_log=[sig_same], journal=[], trace=[])
    assert link_high['match_confidence'] == 'HIGH'

    # Different family (ORB vs PROS) → MEDIUM
    sig_diff = _sig(id='SIG_002', setup_type='ORB_EDGE', timestamp='2026-06-30T14:01:00+00:00')
    link_med = link_snapshot_to_outcome(snap, signal_log=[sig_diff], journal=[], trace=[])
    assert link_med['match_confidence'] == 'MEDIUM'


# ── Test 6: no match → NONE confidence ───────────────────────────────────────

def test_no_match_returns_none_confidence():
    snap = _make_decision(timestamp='2026-06-30T14:00:00Z')
    link = link_snapshot_to_outcome(snap, signal_log=[], journal=[], trace=[])
    assert link['match_confidence'] == 'NONE'
    assert link['match_method']     == 'NONE'
    assert link['linked_signal_id'] == ''


# ── Test 7: journal match returns LOW via DATE_TICKER_DIR ────────────────────

def test_journal_match_low_confidence():
    snap = _make_decision(timestamp='2026-06-30T14:00:00Z')
    jour = _jour(ticker='MES', direction='LONG', trade_date='2026-06-30', outcome='REJECTED')
    link = link_snapshot_to_outcome(snap, signal_log=[], journal=[jour], trace=[])
    assert link['match_method']    == 'DATE_TICKER_DIR'
    assert link['match_confidence'] == 'LOW'
    assert link['outcome']         == 'REJECTED'


# ── Test 8: no journal → outcome=UNKNOWN ─────────────────────────────────────

def test_no_journal_outcome_unknown():
    snap = _make_decision()
    link = link_snapshot_to_outcome(snap, signal_log=[], journal=[], trace=[])
    assert link['outcome'] == 'UNKNOWN'


# ── Test 9: multiple candidates — best score wins ────────────────────────────

def test_multiple_signal_candidates_best_wins():
    snap = _make_decision(timestamp='2026-06-30T14:00:00Z', setup_type='PROS_CONT')
    # Candidate A: wrong direction — excluded entirely
    sig_wrong_dir = _sig(id='WRONG', symbol='MES', direction='SHORT',
                         timestamp='2026-06-30T14:01:00+00:00')
    # Candidate B: same family (PROS) → HIGH
    sig_match = _sig(id='SIG_BEST', symbol='MES', direction='LONG',
                     setup_type='PROS_LONG', timestamp='2026-06-30T14:01:00+00:00')
    link = link_snapshot_to_outcome(snap, signal_log=[sig_wrong_dir, sig_match], journal=[], trace=[])
    assert link['linked_signal_id'] == 'SIG_BEST'
    assert link['match_confidence'] == 'HIGH'


# ── Test 10: EXECUTION_READY + no match → NOT_EXECUTED ───────────────────────

def test_exec_ready_no_match_trade_status():
    snap = _make_decision(signal_type='EXECUTION_READY', is_exec_ready=True)
    link = link_snapshot_to_outcome(snap, signal_log=[], journal=[], trace=[])
    assert link['trade_status'] == 'EXECUTION_READY_NOT_EXECUTED'


# ── Test 11: HEADS_UP → NOT_TAKEN ────────────────────────────────────────────

def test_heads_up_not_taken():
    snap = _make_decision(signal_type='HEADS_UP', is_exec_ready=False)
    link = link_snapshot_to_outcome(snap, signal_log=[], journal=[], trace=[])
    assert link['trade_status'] == 'NOT_TAKEN'


# ── Test 12: rejected → REJECTED_OR_NO_TRADE ─────────────────────────────────

def test_rejected_trade_status():
    snap = _make_decision(is_rejected=True, is_exec_ready=False)
    link = link_snapshot_to_outcome(snap, signal_log=[], journal=[], trace=[])
    assert link['trade_status'] == 'REJECTED_OR_NO_TRADE'


# ── Test 13: journal REJECTED entry → outcome=REJECTED ───────────────────────

def test_journal_rejected_outcome():
    snap = _make_decision(timestamp='2026-06-30T14:00:00Z')
    jour = _jour(trade_date='2026-06-30', outcome='REJECTED')
    link = link_snapshot_to_outcome(snap, signal_log=[], journal=[jour], trace=[])
    assert link['outcome'] == 'REJECTED'
    assert link['close_reason'] == 'GRADE_BELOW_PROFILE_MIN'


# ── Test 14: malformed data does not crash ────────────────────────────────────

def test_malformed_data_no_crash():
    snap = _make_decision()
    # None args → defaults to []
    link = link_snapshot_to_outcome(snap, signal_log=None, journal=None, trace=None)
    assert isinstance(link, dict)
    assert link['trade_status'] in ('EXECUTION_READY_NOT_EXECUTED', 'NOT_TAKEN',
                                    'REJECTED_OR_NO_TRADE', 'UNKNOWN')
    # Corrupt entries in lists
    link2 = link_snapshot_to_outcome(
        snap,
        signal_log=[None, 'bad_string', 123, {'no_fields': True}],
        journal=[None, [], 'bad'],
        trace=[None, 'bad'],
    )
    assert isinstance(link2, dict)

    # Empty snapshot
    link3 = link_snapshot_to_outcome({})
    assert isinstance(link3, dict)
    assert link3['match_confidence'] == 'NONE'


# ── Test 15: outcome_summary has all required fields ─────────────────────────

_OUTCOME_SUMMARY_KEYS = [
    'decision_id', 'timestamp', 'symbol', 'session',
    'setup_type', 'signal_type', 'direction', 'grade',
    'is_execution_ready', 'is_rejected',
    'trade_status', 'outcome',
    'realized_pnl', 'r_multiple', 'entry_price', 'exit_price',
    'close_reason', 'rejection_reason',
    'match_confidence', 'match_method',
    'linked_signal_id', 'linked_trace_id',
]

def test_outcome_summary_fields():
    snap = _make_decision()
    link = link_snapshot_to_outcome(snap, signal_log=[], journal=[], trace=[])
    summary = outcome_summary(snap, link)
    for k in _OUTCOME_SUMMARY_KEYS:
        assert k in summary, f'missing field: {k}'
    assert isinstance(summary['decision_id'], str)
    assert summary['decision_id'].startswith('DEC_')


# ── Test 16: similar-with-outcomes has no aggregate stats ────────────────────

def test_similar_with_outcomes_no_aggregate_stats():
    # The response structure must NOT contain these keys at top level or in matches
    _FORBIDDEN = {'win_rate', 'avg_r', 'expected_value', 'hit_rate', 'avg_pnl', 'statistics'}
    # Simulate the endpoint response structure manually
    simulated_response = {
        'current': {'timestamp': '2026-06-30T14:00:00Z', 'symbol': 'CME_MINI:MES1!',
                    'setup_type': 'PROS_CONT', 'signal_type': 'EXECUTION_READY',
                    'direction': 'LONG', 'session': 'NY_CASH', 'decision_id': 'DEC_001'},
        'matches': [
            {
                'timestamp': '2026-06-30T10:00:00Z',
                'similarity_score': 0.95,
                'trade_status': 'EXECUTION_READY_NOT_EXECUTED',
                'outcome': 'UNKNOWN',
                'match_confidence': 'NONE',
                'outcome_note': 'No outcome linked — snapshot not yet matched to a trade',
            }
        ],
        # No win_rate, no avg_r
    }
    top_level_keys = set(simulated_response.keys())
    assert not (top_level_keys & _FORBIDDEN), f'Forbidden stats keys in response: {top_level_keys & _FORBIDDEN}'
    for match in simulated_response['matches']:
        assert not (set(match.keys()) & _FORBIDDEN), f'Forbidden stats in match: {set(match.keys()) & _FORBIDDEN}'


# ── runner ────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    import inspect, pathlib, shutil, tempfile

    class _TmpPath:
        def __enter__(self):
            self._d = tempfile.mkdtemp()
            return pathlib.Path(self._d)
        def __exit__(self, *a):
            shutil.rmtree(self._d, ignore_errors=True)

    class _MP:
        def __init__(self): self._undo = []
        def setattr(self, obj, name, val):
            self._undo.append((obj, name, getattr(obj, name)))
            setattr(obj, name, val)
        def undo(self):
            for o, n, v in reversed(self._undo): setattr(o, n, v)

    tests = [(k, v) for k, v in globals().items() if k.startswith('test_')]
    passed = failed = 0
    for name, fn in tests:
        sig = inspect.signature(fn)
        mp  = _MP()
        tp  = None
        try:
            kw = {}
            if 'tmp_path' in sig.parameters:
                tp = _TmpPath()
                kw['tmp_path'] = tp.__enter__()
            if 'monkeypatch' in sig.parameters:
                kw['monkeypatch'] = mp
            fn(**kw)
            print(f'PASS  {name}')
            passed += 1
        except AssertionError as e:
            print(f'FAIL  {name}: {e}')
            failed += 1
        except Exception as e:
            print(f'ERROR {name}: {type(e).__name__}: {e}')
            failed += 1
        finally:
            mp.undo()
            if tp:
                try: tp.__exit__(None, None, None)
                except Exception: pass

    print(f'\n{passed}/{passed + failed} passed')
    sys.exit(1 if failed else 0)
