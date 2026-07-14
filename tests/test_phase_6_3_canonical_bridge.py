"""
test_phase_6_3_canonical_bridge.py — Phase 6.3 canonical BRIDGE v3 parser
and mismatch-telemetry regression tests.

Covers:
  1. BRIDGE_VER 3 canonical ORB BUY parses correctly
  2. BRIDGE_VER 3 canonical PROS SELL parses correctly
  3. Canonical WAIT + legacy ICT BUY -> no actionable BUY, mismatch logged
  4. Canonical NONE + legacy ELITE CONT LONG -> no trade signal
  5. canonical_buy and canonical_sell both true -> degraded, no actionable direction
  6. canonical_strategy = ICT -> rejected as invalid canonical strategy
  7. BRIDGE_VER 2 -> legacy behavior unchanged (no canonical data)
  8. Missing canonical fields -> safe degraded response
  9. log_cycle() entry keeps canonical and legacy fields separate
 10. No execution/broker import anywhere in this test file

Run:  python tests/test_phase_6_3_canonical_bridge.py
      python -m pytest tests/test_phase_6_3_canonical_bridge.py -v
"""
from __future__ import annotations
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault('ALPACA_API_KEY',    '')
os.environ.setdefault('ALPACA_SECRET_KEY', '')

from engines.reasoning import parse_nova_tables, derive_actionable_signal
from delivery.signal_log import log_cycle


# ── helpers ───────────────────────────────────────────────────────────────────

def _v3_rows(bridge_ver='3', **overrides) -> list[str]:
    base = {
        'CMD': 'WAIT', 'SYS_STATE': 'READING MARKET', 'SCORE': 'B 0 / S 48',
        'CONF': 'LOW 44%', 'PROS_ENG': 'BUILDING', 'P_DISPL': 'BULL',
        'P_RETRACE': 'TOO DEEP', 'P_OTE': 'DEEP', 'P_CONT': 'BUILDING',
        'P_QUALITY': 'GOOD', 'P_STDV': 'NORMAL',
        'IB H': '7489.75', 'IB L': '7409',
        'O_STATE': 'ORB_EXPIRED', 'O_BIAS': 'BULL DEAD', 'O_TYPE': 'EDGE DFND',
        'O_REJ_Q': '3 EDGE', 'O_HIGH': '7467.75', 'O_MID': '7464.5', 'O_LOW': '7461.25',
        'BRIDGE_VER': bridge_ver, 'TICKER': 'MES1!', 'TF': '1', 'IB_STATUS': 'COMPLETE',
        'SESSION': 'NY_CASH', 'ORB_ACTIVE': '0', 'PROS_ACTIVE': '1',
        'COOLDOWN': '0', 'TRAP': '0', 'ICT_STEP': '1',
        'PEER_ALIGN': 'CONFIRM', 'DRAW_TARGET': '7560.00', 'DRAW_DIR': 'UP',
        'CANON_STATE': 'WAIT', 'CANON_DIR': 'NONE', 'CANON_STRAT': 'NONE',
        'CANON_SETUP': 'NONE', 'CANON_GRADE': 'NA', 'CANON_LIQ_SRC': 'NONE',
        'CANON_INTERACT': 'NONE', 'CANON_BUY': '0', 'CANON_SELL': '0',
    }
    base.update(overrides)
    rows = ['NOVA BRIDGE']
    for k, v in base.items():
        rows.append(f'{k} | {v}')
    return rows


# ── Test 1: BRIDGE_VER 3 canonical ORB BUY parses correctly ──────────────────

def test_bridge_v3_orb_buy_parses_correctly():
    s = parse_nova_tables([_v3_rows(
        CANON_STATE='EXECUTION_READY', CANON_DIR='LONG', CANON_STRAT='ORB',
        CANON_SETUP='ORB_MID_REJECT', CANON_GRADE='A', CANON_BUY='1', CANON_SELL='0',
    )])
    c = s['canonical']
    assert c['canonical_available'] is True
    assert c['canonical_degraded']  is False
    assert c['canonical_state']     == 'EXECUTION_READY'
    assert c['canonical_direction'] == 'LONG'
    assert c['canonical_strategy']  == 'ORB'
    assert c['canonical_setup']     == 'ORB_MID_REJECT'
    assert c['canonical_grade']     == 'A'
    assert c['canonical_buy']       is True
    assert c['canonical_sell']      is False

    a = derive_actionable_signal(s)
    assert a['source']               == 'canonical'
    assert a['actionable_direction'] == 'LONG'
    assert a['actionable_strategy']  == 'ORB'
    assert a['actionable_buy']       is True
    assert a['actionable_sell']      is False


# ── Test 2: BRIDGE_VER 3 canonical PROS SELL parses correctly ────────────────

def test_bridge_v3_pros_sell_parses_correctly():
    s = parse_nova_tables([_v3_rows(
        CANON_STATE='EXECUTION_READY', CANON_DIR='SHORT', CANON_STRAT='PROS',
        CANON_SETUP='PROS_CONTINUATION', CANON_GRADE='B', CANON_BUY='0', CANON_SELL='1',
    )])
    c = s['canonical']
    assert c['canonical_degraded']  is False
    assert c['canonical_direction'] == 'SHORT'
    assert c['canonical_strategy']  == 'PROS'
    assert c['canonical_sell']      is True
    assert c['canonical_buy']       is False

    a = derive_actionable_signal(s)
    assert a['actionable_direction'] == 'SHORT'
    assert a['actionable_strategy']  == 'PROS'
    assert a['actionable_sell']      is True
    assert a['actionable_buy']       is False


# ── Test 3: canonical WAIT + legacy ICT BUY -> no actionable BUY, mismatch ───

def test_canonical_wait_legacy_ict_buy_no_actionable_signal():
    s = parse_nova_tables([_v3_rows(
        CMD='BUY', SYS_STATE='ELITE ICT LONG',
        CANON_STATE='WAIT', CANON_DIR='NONE', CANON_STRAT='NONE',
        CANON_BUY='0', CANON_SELL='0',
    )])
    c = s['canonical']
    assert c['canonical_degraded'] is False
    assert c['canonical_buy']  is False
    assert c['canonical_sell'] is False

    a = derive_actionable_signal(s)
    assert a['actionable_buy']       is False
    assert a['actionable_sell']      is False
    assert a['actionable_direction'] == 'NONE'

    m = s['canonical_mismatch']
    assert m is not None
    assert m['legacy_canonical_mismatch'] is True
    assert m['legacy_cmd']       == 'BUY'
    assert m['legacy_sys_state'] == 'ELITE ICT LONG'
    assert 'CMD' in m['mismatch_reason']


# ── Test 4: canonical NONE + legacy ELITE CONT LONG -> no trade signal ───────

def test_canonical_none_legacy_elite_cont_no_trade_signal():
    s = parse_nova_tables([_v3_rows(
        CMD='WAIT', SYS_STATE='ELITE CONT LONG',
        CANON_STATE='WAIT', CANON_DIR='NONE', CANON_STRAT='NONE',
        CANON_BUY='0', CANON_SELL='0',
    )])
    a = derive_actionable_signal(s)
    assert a['actionable_buy']       is False
    assert a['actionable_sell']      is False
    assert a['actionable_direction'] == 'NONE'
    assert a['actionable_strategy']  == 'NONE'
    # SYS_STATE mentions ICT-flavored text but canonical_strategy is NONE,
    # not ORB/PROS, so the ICT-specific mismatch reason should not fire —
    # only a legacy-vs-canonical mismatch is possible when CMD says BUY/SELL.
    m = s['canonical_mismatch']
    assert m is not None
    assert m['legacy_canonical_mismatch'] is False  # CMD=WAIT agrees with canonical_state=WAIT


# ── Test 5: canonical_buy and canonical_sell both true -> degraded ──────────

def test_canonical_buy_and_sell_both_true_is_degraded():
    s = parse_nova_tables([_v3_rows(
        CANON_STATE='EXECUTION_READY', CANON_DIR='LONG', CANON_STRAT='ORB',
        CANON_BUY='1', CANON_SELL='1',
    )])
    c = s['canonical']
    assert c['canonical_degraded'] is True
    assert any('both true' in w for w in c['canonical_warnings'])

    a = derive_actionable_signal(s)
    assert a['source'] == 'degraded'
    assert a['actionable_direction'] is None
    assert a['actionable_buy']  is None
    assert a['actionable_sell'] is None


# ── Test 6: canonical_strategy = ICT is rejected ─────────────────────────────

def test_canonical_strategy_ict_rejected():
    s = parse_nova_tables([_v3_rows(CANON_STRAT='ICT', CANON_DIR='LONG', CANON_BUY='1')])
    c = s['canonical']
    assert c['canonical_degraded'] is True
    assert any('ICT' in w and 'not an approved strategy' in w for w in c['canonical_warnings'])

    a = derive_actionable_signal(s)
    assert a['source'] == 'degraded'
    assert a['actionable_strategy'] is None


# ── Test 7: BRIDGE_VER 2 -> legacy behavior unchanged, no canonical data ────

def test_bridge_v2_unchanged_no_canonical():
    s = parse_nova_tables([_v3_rows(bridge_ver='2')])
    assert s['parser_mode']  == 'BRIDGE_V2'
    assert s['parse_status'] == 'ok'
    c = s['canonical']
    assert c['canonical_available'] is False
    assert c['canonical_degraded']  is False   # never degraded when simply unavailable
    assert s['canonical_mismatch'] is None      # no mismatch computed on v1/v2

    a = derive_actionable_signal(s)
    assert a['source'] == 'legacy_unavailable'
    assert a['actionable_direction'] is None
    # main/pros/orb dicts still populate exactly as before Phase 6.3
    assert s['main']['CMD'] == 'WAIT'


# ── Test 8: missing canonical fields -> safe degraded response ──────────────

def test_missing_canonical_fields_degraded_safely():
    rows = _v3_rows()
    rows = [r for r in rows if not r.startswith('CANON_GRADE')
                           and not r.startswith('CANON_LIQ_SRC')]
    s = parse_nova_tables([rows])
    c = s['canonical']
    assert c['canonical_available'] is True
    assert c['canonical_degraded']  is True
    assert any('CANON_GRADE' in w for w in c['canonical_warnings'])
    assert any('CANON_LIQ_SRC' in w for w in c['canonical_warnings'])

    a = derive_actionable_signal(s)
    assert a['source'] == 'degraded'
    assert a['actionable_direction'] is None  # malformed data never treated as a valid trade


# ── Test 9: log_cycle() keeps canonical and legacy fields separate ──────────

def test_log_cycle_keeps_canonical_and_legacy_fields_separate(tmp_path, monkeypatch=None):
    # Redirect the signal log file to a throwaway path so this test never
    # touches the real data/donna_signal_log.json.
    import delivery.signal_log as sl
    tmp_file = tmp_path / 'test_signal_log.json'
    orig_file = sl._LOG_FILE
    sl._LOG_FILE = tmp_file
    try:
        entry = log_cycle(
            symbol='MES',
            nova_cmd='BUY', nova_state_val='ELITE ICT LONG',
            canonical_state='WAIT', canonical_direction='NONE',
            canonical_strategy='NONE', canonical_setup='NONE',
            canonical_grade='NA', canonical_buy=False, canonical_sell=False,
            legacy_cmd='BUY', legacy_sys_state='ELITE ICT LONG',
            legacy_canonical_mismatch=True,
            mismatch_reason="legacy CMD='BUY' but canonical_state='WAIT'",
        )
        assert entry != {}
        # Canonical fields present and distinct from legacy fields
        assert entry['canonical_state']     == 'WAIT'
        assert entry['canonical_direction'] == 'NONE'
        assert entry['legacy_cmd']          == 'BUY'
        assert entry['legacy_sys_state']    == 'ELITE ICT LONG'
        assert entry['legacy_canonical_mismatch'] is True
        assert entry['mismatch_reason']
        # Never merged into one field
        assert entry['canonical_state'] != entry['legacy_cmd']
        # Existing legacy fields untouched by this phase
        assert entry['nova_cmd']   == 'BUY'
        assert entry['nova_state'] == 'ELITE ICT LONG'
    finally:
        sl._LOG_FILE = orig_file


# ── Test 10: no execution/broker import anywhere in this test file ──────────

def test_no_execution_or_broker_import_in_this_file():
    # AST-based check on actual import statements only, not a raw substring
    # search (which would trivially match this test's own assertion text
    # describing what it's checking for).
    import ast
    src = open(__file__, encoding='utf-8').read()
    tree = ast.parse(src)
    imported_modules = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.extend(n.name for n in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.append(node.module)
    forbidden = {'services.execution', 'services.execution_bridge', 'services'}
    assert not (set(imported_modules) & forbidden), (
        f'test file imports execution/broker modules: {imported_modules}')


# ── runner ────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    import inspect
    import tempfile
    from pathlib import Path

    tests = [(k, v) for k, v in globals().items() if k.startswith('test_')]
    passed = failed = 0
    for name, fn in tests:
        try:
            params = inspect.signature(fn).parameters
            if 'tmp_path' in params:
                with tempfile.TemporaryDirectory() as td:
                    fn(Path(td))
            else:
                fn()
            print(f'PASS  {name}')
            passed += 1
        except AssertionError as e:
            print(f'FAIL  {name}: {e}')
            failed += 1
        except Exception as e:
            print(f'ERROR {name}: {e}')
            failed += 1
    print(f'\n{passed}/{passed + failed} passed')
    sys.exit(1 if failed else 0)
