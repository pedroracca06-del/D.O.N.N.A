"""
test_phase_g_similarity.py — Phase G similar setup matching smoke tests.

Covers:
  1.  identical fingerprints score 1.0
  2.  one field mismatch lowers score (setup_type, weight 3.0)
  3.  direction mismatch lowers score (weight 3.0)
  4.  multiple mismatches compound (lower score than single mismatch)
  5.  missing fields skipped — does not crash or inflate score
  6.  market_family normalization — MES and ES fingerprints match on family
  7.  current snapshot skipped by timestamp match in _find_similar_setups
  8.  only decision snapshots compared (market_read excluded)
  9.  _find_similar_setups respects limit
 10.  results sorted descending by similarity_score
 11.  _similar_match_summary has all required fields
 12.  empty historical list returns []
 13.  /api/mcp-replay/similar with no snapshot file returns empty matches
 14.  _find_similar_setups builds fingerprint on-the-fly if missing from snapshot
 15.  comparing empty fingerprints returns score=0.0 (no comparable fields)

Run:  python tests/test_phase_g_similarity.py
      python -m pytest tests/test_phase_g_similarity.py -v
"""
from __future__ import annotations
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault('ALPACA_API_KEY',    '')
os.environ.setdefault('ALPACA_SECRET_KEY', '')

from engines.reasoning import (
    _compare_setup_fingerprints, _find_similar_setups, _similar_match_summary,
    _build_setup_fingerprint, _build_decision_snapshot,
    _normalize_market_family, _FP_WEIGHTS,
    _build_mcp_snapshot, parse_nova_tables, compute_mcp_health,
)
from main import _read_mcp_snapshots_raw, _filter_snapshots

# ── fingerprint fixture ───────────────────────────────────────────────────────

def _fp(**overrides) -> dict:
    """Build a reference fingerprint with all high-weight fields populated."""
    base = {
        'market_family':     'ES',
        'setup_type':        'PROS_CONT',
        'signal_type':       'EXECUTION_READY',
        'direction':         'LONG',
        'session':           'NY_CASH',
        'ib_status':         'COMPLETE',
        'ib_location':       'IB_H',
        'orb_active':        False,
        'orb_entry_type':    'EDGE',
        'pros_phase':        'CONTINUATION',
        'pros_quality':      'STRONG',
        'pros_continuation': 'CONFIRMED',
        'peer_alignment':    'CONFIRM',
        'mcp_status':        'HEALTHY',
        'time_bucket':       '10:00',
        'grade':             'A',
        'draw_direction':    'UP',
        'orb_in_context':    True,
        'pros_ote_status':   'TAGGED',
        'ticker_match':      True,
        'timeframe_match':   True,
    }
    base.update(overrides)
    return base

_TOTAL_WEIGHT = sum(_FP_WEIGHTS.values())


def _make_full_decision_snap(
    symbol='CME_MINI:MES1!',
    timestamp='2026-06-30T10:00:00Z',
    signal_type='EXECUTION_READY',
    setup_type='PROS_CONT',
    direction='LONG',
    is_execution_ready=True,
    is_rejected=False,
) -> dict:
    """Build a complete decision snapshot via the real builder."""
    tables    = [
        'NOVA BRIDGE',
        'CMD | WAIT', 'SYS_STATE | READING MARKET', 'SCORE | B 0 / S 48',
        'CONF | LOW 44%', 'PROS_ENG | BUILDING', 'P_DISPL | BULL',
        'P_RETRACE | TOO DEEP', 'P_OTE | DEEP', 'P_CONT | BUILDING',
        'P_QUALITY | GOOD', 'P_STDV | NORMAL',
        'IB H | 7489.75', 'IB L | 7409',
        'O_STATE | ORB_EXPIRED', 'O_BIAS | BULL DEAD', 'O_TYPE | EDGE DFND',
        'O_REJ_Q | 3 EDGE', 'O_HIGH | 7467.75', 'O_MID | 7464.5', 'O_LOW | 7461.25',
        'BRIDGE_VER | 2', 'TICKER | MES1!', 'TF | 1', 'IB_STATUS | COMPLETE',
        'SESSION | NY_CASH', 'ORB_ACTIVE | 0', 'PROS_ACTIVE | 1',
        'COOLDOWN | 0', 'TRAP | 0', 'ICT_STEP | 1',
        'PEER_ALIGN | CONFIRM', 'DRAW_TARGET | 7560.00', 'DRAW_DIR | UP',
    ]
    chart_ctx  = {'connected': True, 'symbol': symbol, 'timeframe': '1', 'nova_tables': [tables]}
    session    = {'session': 'NY_CASH', 'time_et': '10:00'}
    nova_state = parse_nova_tables([tables])
    health     = compute_mcp_health(chart_ctx, nova_state)
    base       = _build_mcp_snapshot(chart_ctx, nova_state, health, session)
    base['timestamp'] = timestamp

    pros_eval = {
        'phase': 'CONTINUATION', 'direction': 'BULL', 'setup_type': 'PROS_CONT',
        'has_signal': True, 'signal_strength': 'STRONG',
        'ote_status': 'TAGGED', 'cont_quality': 'CONFIRMED',
    }
    orb_eval = {
        'phase': 'ORB_EXPIRED', 'direction': 'BULL', 'setup_type': 'ORB_EDGE',
        'has_signal': False, 'entry_type': 'EDGE', 'entry_quality': 'GOOD',
        'in_context': True, 'orb_range': 25.5,
    }
    ib_eval = {
        'draw': 'IB_H', 'draw_source': 'pros_table', 'aligned': True,
        'ib_range': 80.75, 'ib_tight': False, 'ib_source': 'pros_table',
    }
    alert_type    = signal_type
    alert_required = not is_rejected
    decision = {
        'alert_required': alert_required, 'alert_type': alert_type,
        'setup_type': setup_type, 'direction': direction, 'grade': 'A',
        'entry_zone': '7475–7480', 'stop': '7460', 'tp1': '7520', 'rr': '3.0',
        'notes': '', 'reasoning': 'Test snap.', 'no_alert_reason': '',
    }
    return _build_decision_snapshot(
        base,
        pros_eval=pros_eval, orb_eval=orb_eval, ib_eval=ib_eval,
        pre_signal=signal_type, pre_setup=setup_type, pre_rationale='',
        decision=decision, claude_called=True, alert_generated=alert_required,
    )


# ── Test 1: identical fingerprints score 1.0 ─────────────────────────────────

def test_identical_fingerprints_score_1():
    fp = _fp()
    result = _compare_setup_fingerprints(fp, fp)
    assert result['similarity_score'] == 1.0, f"got {result['similarity_score']}"
    assert result['mismatched_fields'] == []
    assert result['total_weight'] == result['matched_weight']


# ── Test 2: setup_type mismatch lowers score ──────────────────────────────────

def test_setup_type_mismatch_lowers_score():
    a = _fp(setup_type='PROS_CONT')
    b = _fp(setup_type='ORB_EDGE')
    result = _compare_setup_fingerprints(a, b)
    assert result['similarity_score'] < 1.0
    assert 'setup_type' in result['mismatched_fields']
    # Score drop ≥ weight(setup_type) / total
    expected_max = round((_TOTAL_WEIGHT - _FP_WEIGHTS['setup_type']) / _TOTAL_WEIGHT, 4)
    assert result['similarity_score'] <= expected_max + 0.001


# ── Test 3: direction mismatch lowers score ───────────────────────────────────

def test_direction_mismatch_lowers_score():
    a = _fp(direction='LONG')
    b = _fp(direction='SHORT')
    result = _compare_setup_fingerprints(a, b)
    assert result['similarity_score'] < 1.0
    assert 'direction' in result['mismatched_fields']


# ── Test 4: multiple mismatches compound ─────────────────────────────────────

def test_multiple_mismatches_compound():
    a = _fp(setup_type='PROS_CONT', direction='LONG')
    b = _fp(setup_type='ORB_EDGE',  direction='SHORT')
    one_mismatch = _compare_setup_fingerprints(_fp(setup_type='PROS_CONT'), _fp(setup_type='ORB_EDGE'))
    two_mismatches = _compare_setup_fingerprints(a, b)
    assert two_mismatches['similarity_score'] < one_mismatch['similarity_score']


# ── Test 5: None fields skipped, no crash ────────────────────────────────────

def test_none_fields_skipped_no_crash():
    a = _fp(ib_location=None, pros_quality=None)
    b = _fp()
    result = _compare_setup_fingerprints(a, b)
    assert isinstance(result, dict)
    assert result['similarity_score'] >= 0.0
    # ib_location and pros_quality must not appear in matched or mismatched
    assert 'ib_location'  not in result['matched_fields']
    assert 'ib_location'  not in result['mismatched_fields']
    assert 'pros_quality' not in result['matched_fields']
    assert 'pros_quality' not in result['mismatched_fields']

    # Fully empty fingerprints
    empty_result = _compare_setup_fingerprints({}, {})
    assert empty_result['similarity_score'] == 0.0
    assert empty_result['total_weight'] == 0.0


# ── Test 6: market family normalization — MES and ES fingerprints match ───────

def test_market_family_normalization():
    assert _normalize_market_family('CME_MINI:MES1!') == 'ES'
    assert _normalize_market_family('CME_MINI:ES1!')  == 'ES'
    # Two fingerprints from MES and ES symbols get same market_family → full match
    a = _fp(market_family='ES')
    b = _fp(market_family='ES')
    result = _compare_setup_fingerprints(a, b)
    assert 'market_family' in result['matched_fields']
    # Contrast: MES vs NQ → mismatch
    c = _fp(market_family='NQ')
    result2 = _compare_setup_fingerprints(a, c)
    assert 'market_family' in result2['mismatched_fields']


# ── Test 7: current snapshot excluded by timestamp ───────────────────────────

def test_current_snapshot_not_matched_against_itself():
    current = _make_full_decision_snap(timestamp='2026-06-30T10:00:00Z')
    hist_same_ts = _make_full_decision_snap(timestamp='2026-06-30T10:00:00Z')
    hist_diff_ts = _make_full_decision_snap(timestamp='2026-06-30T10:30:00Z')
    results = _find_similar_setups(current, [hist_same_ts, hist_diff_ts])
    returned_ts = {r['snapshot']['timestamp'] for r in results}
    assert '2026-06-30T10:00:00Z' not in returned_ts
    assert '2026-06-30T10:30:00Z' in returned_ts


# ── Test 8: market_read snapshots excluded ────────────────────────────────────

def test_market_read_excluded_from_matching():
    from engines.reasoning import _build_mcp_snapshot
    tables    = [
        'NOVA BRIDGE', 'CMD | WAIT', 'SYS_STATE | READING MARKET',
        'SCORE | B 0 / S 48', 'CONF | LOW 44%', 'PROS_ENG | BUILDING',
        'P_DISPL | BULL', 'P_RETRACE | TOO DEEP', 'P_OTE | DEEP',
        'P_CONT | BUILDING', 'P_QUALITY | GOOD', 'P_STDV | NORMAL',
        'IB H | 7489.75', 'IB L | 7409', 'O_STATE | ORB_EXPIRED',
        'O_BIAS | BULL DEAD', 'O_TYPE | EDGE DFND', 'O_REJ_Q | 3 EDGE',
        'O_HIGH | 7467.75', 'O_MID | 7464.5', 'O_LOW | 7461.25',
        'BRIDGE_VER | 2', 'TICKER | MES1!', 'TF | 1', 'IB_STATUS | COMPLETE',
        'SESSION | NY_CASH', 'ORB_ACTIVE | 0', 'PROS_ACTIVE | 1',
        'COOLDOWN | 0', 'TRAP | 0', 'ICT_STEP | 1',
        'PEER_ALIGN | CONFIRM', 'DRAW_TARGET | 7560.00', 'DRAW_DIR | UP',
    ]
    ctx        = {'connected': True, 'symbol': 'CME_MINI:MES1!', 'timeframe': '1', 'nova_tables': [tables]}
    nova_state = parse_nova_tables([tables])
    health     = compute_mcp_health(ctx, nova_state)
    mr_snap    = _build_mcp_snapshot(ctx, nova_state, health, {'session': 'NY_CASH'})
    assert mr_snap['snapshot_type'] == 'market_read'

    current = _make_full_decision_snap(timestamp='2026-06-30T10:00:00Z')
    results = _find_similar_setups(current, [mr_snap])
    assert results == [], 'market_read snapshots must not appear in similar results'


# ── Test 9: limit is respected ────────────────────────────────────────────────

def test_limit_respected():
    current = _make_full_decision_snap(timestamp='2026-06-30T10:00:00Z')
    history = [
        _make_full_decision_snap(timestamp=f'2026-06-30T{h:02d}:00:00Z')
        for h in range(1, 9)   # 8 historical snaps
    ]
    results = _find_similar_setups(current, history, limit=3)
    assert len(results) <= 3


# ── Test 10: results sorted descending by score ───────────────────────────────

def test_results_sorted_descending():
    current = _make_full_decision_snap(
        timestamp='2026-06-30T10:00:00Z',
        direction='LONG', setup_type='PROS_CONT',
    )
    # One perfect match, one weaker match (different direction)
    perfect = _make_full_decision_snap(
        timestamp='2026-06-30T09:00:00Z',
        direction='LONG', setup_type='PROS_CONT',
    )
    weaker = _make_full_decision_snap(
        timestamp='2026-06-30T08:00:00Z',
        direction='SHORT', setup_type='PROS_CONT',
    )
    results = _find_similar_setups(current, [weaker, perfect])
    assert len(results) == 2
    assert results[0]['comparison']['similarity_score'] >= results[1]['comparison']['similarity_score']
    # Perfect match should be first
    assert results[0]['snapshot']['timestamp'] == '2026-06-30T09:00:00Z'


# ── Test 11: match summary has all required fields ────────────────────────────

_SUMMARY_KEYS = [
    'timestamp', 'symbol', 'session', 'setup_type', 'signal_type', 'direction',
    'similarity_score', 'matched_fields', 'mismatched_fields',
    'is_execution_ready', 'is_rejected', 'grade', 'rationale',
]

def test_match_summary_fields():
    current = _make_full_decision_snap(timestamp='2026-06-30T10:00:00Z')
    history = [_make_full_decision_snap(timestamp='2026-06-30T09:00:00Z')]
    results = _find_similar_setups(current, history)
    assert len(results) == 1
    summary = _similar_match_summary(results[0])
    for k in _SUMMARY_KEYS:
        assert k in summary, f'missing key: {k}'
    assert isinstance(summary['matched_fields'], list)
    assert isinstance(summary['mismatched_fields'], list)
    assert isinstance(summary['similarity_score'], float)


# ── Test 12: empty historical list returns [] ─────────────────────────────────

def test_empty_historical_returns_empty():
    current = _make_full_decision_snap(timestamp='2026-06-30T10:00:00Z')
    results = _find_similar_setups(current, [])
    assert results == []


# ── Test 13: no snapshot file returns empty matches ───────────────────────────

def test_no_file_returns_empty(tmp_path, monkeypatch):
    import core.config as _cfg
    orig = _cfg.MCP_SNAPSHOTS_FILE
    _cfg.MCP_SNAPSHOTS_FILE = tmp_path / 'nonexistent.json'
    try:
        raw = _read_mcp_snapshots_raw()
        decisions = _filter_snapshots(raw, snapshot_type='decision')
        assert decisions == []
    finally:
        _cfg.MCP_SNAPSHOTS_FILE = orig


# ── Test 14: fingerprint built on-the-fly if missing ─────────────────────────

def test_fingerprint_built_on_the_fly():
    current = _make_full_decision_snap(timestamp='2026-06-30T10:00:00Z')
    # Strip the pre-built fingerprint from a historical snap
    hist = _make_full_decision_snap(timestamp='2026-06-30T09:00:00Z')
    del hist['setup_fingerprint']
    assert 'setup_fingerprint' not in hist

    results = _find_similar_setups(current, [hist])
    assert len(results) == 1
    assert results[0]['comparison']['similarity_score'] > 0.0
    # On-the-fly fingerprint is present in the result
    assert isinstance(results[0]['fingerprint'], dict)
    assert results[0]['fingerprint'].get('market_family') == 'ES'


# ── Test 15: empty fingerprints → score 0.0 ──────────────────────────────────

def test_empty_fingerprints_score_zero():
    result = _compare_setup_fingerprints({}, {})
    assert result['similarity_score'] == 0.0
    assert result['total_weight']     == 0.0
    assert result['matched_fields']   == []
    assert result['mismatched_fields'] == []


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
