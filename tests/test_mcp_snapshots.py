"""
test_mcp_snapshots.py — Phase C snapshot logging smoke tests.

Covers:
  1. _build_mcp_snapshot returns all required keys
  2. Snapshot append works — file created, entry persists
  3. Rolling cap works — never exceeds _MCP_SNAPSHOT_CAP entries
  4. Bad / missing fields do not crash _build_mcp_snapshot
  5. File missing returns gracefully from _append_mcp_snapshot (creates file)
  6. Write failure does not propagate (non-blocking safety)
  7. Snapshot schema: mcp_health sub-dict correct
  8. Snapshot schema: market structure fields populated from bridge_v2 + pros/orb
  9. Snapshot schema: signal fields are None (captured before evaluators)
 10. Legacy / no-bridge path produces a valid snapshot without crashing

Run:  python tests/test_mcp_snapshots.py
      python -m pytest tests/test_mcp_snapshots.py -v
"""
from __future__ import annotations
import json, os, sys, tempfile, threading
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault('ALPACA_API_KEY',    '')
os.environ.setdefault('ALPACA_SECRET_KEY', '')

from engines.reasoning import (
    _build_mcp_snapshot, _append_mcp_snapshot,
    _MCP_SNAPSHOT_CAP,
    parse_nova_tables, compute_mcp_health,
)

# ── fixtures ──────────────────────────────────────────────────────────────────

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

def _make_snap(symbol='CME_MINI:MES1!', tf='1', ticker='MES1!') -> dict:
    tables     = [_v2_rows(ticker=ticker)]
    chart_ctx  = {'connected': True, 'symbol': symbol, 'timeframe': tf, 'nova_tables': tables}
    session    = {'session': 'NY_CASH', 'time_et': '10:15'}
    nova_state = parse_nova_tables(tables)
    health     = compute_mcp_health(chart_ctx, nova_state)
    return _build_mcp_snapshot(chart_ctx, nova_state, health, session)


# ── Test 1: required keys ─────────────────────────────────────────────────────

def test_snapshot_has_required_keys():
    snap = _make_snap()
    required = [
        'timestamp', 'symbol', 'timeframe', 'session',
        'parser_mode', 'parse_status',
        'mcp_health', 'bridge_v2', 'bridge_meta',
        'nova_main', 'nova_pros', 'nova_orb',
        'chart_symbol', 'chart_timeframe',
        'parsed_ticker', 'parsed_timeframe',
        'ticker_match', 'timeframe_match',
        'ib_high', 'ib_low', 'ib_status',
        'orb_high', 'orb_mid', 'orb_low',
        'orb_active', 'pros_active', 'peer_alignment',
        'draw_target', 'draw_direction',
        'setup_type', 'signal_type', 'direction', 'confidence', 'rationale',
        'warnings', 'errors',
    ]
    for k in required:
        assert k in snap, f'missing key: {k}'


# ── Test 2: append works ──────────────────────────────────────────────────────

def test_snapshot_append_creates_and_persists(tmp_path, monkeypatch):
    target = tmp_path / 'snaps.json'
    import engines.reasoning as _r
    monkeypatch.setattr(_r, '_MCP_SNAPSHOT_CAP', 500)

    import core.config as _cfg
    orig = _cfg.MCP_SNAPSHOTS_FILE
    _cfg.MCP_SNAPSHOTS_FILE = target
    try:
        snap = _make_snap()
        _append_mcp_snapshot(snap)
        data = json.loads(target.read_text())
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]['symbol'] == 'CME_MINI:MES1!'
        assert data[0]['parser_mode'] == 'BRIDGE_V2'

        # Second append
        _append_mcp_snapshot(snap)
        data2 = json.loads(target.read_text())
        assert len(data2) == 2
    finally:
        _cfg.MCP_SNAPSHOTS_FILE = orig


# ── Test 3: rolling cap ───────────────────────────────────────────────────────

def test_rolling_cap_never_exceeds_limit(tmp_path, monkeypatch):
    target = tmp_path / 'snaps.json'
    import core.config as _cfg
    orig = _cfg.MCP_SNAPSHOTS_FILE
    _cfg.MCP_SNAPSHOTS_FILE = target

    import engines.reasoning as _r
    orig_cap = _r._MCP_SNAPSHOT_CAP
    _r._MCP_SNAPSHOT_CAP = 10
    try:
        snap = _make_snap()
        for _ in range(15):
            _append_mcp_snapshot(snap)
        data = json.loads(target.read_text())
        assert len(data) == 10, f'expected 10, got {len(data)}'
        # Verify it keeps the LATEST entries (last 10)
        assert all(e['symbol'] == 'CME_MINI:MES1!' for e in data)
    finally:
        _cfg.MCP_SNAPSHOTS_FILE = orig
        _r._MCP_SNAPSHOT_CAP    = orig_cap


# ── Test 4: bad / missing fields do not crash ─────────────────────────────────

def test_bad_inputs_do_not_crash():
    # Empty everything
    snap = _build_mcp_snapshot({}, {}, {}, {})
    assert isinstance(snap, dict)
    assert 'timestamp' in snap
    assert snap['parser_mode'] is None   # nova_state.get('parser_mode') → None
    assert snap['warnings'] == []

    # Partially populated
    snap2 = _build_mcp_snapshot(
        {'symbol': 'TEST', 'timeframe': '5'},
        {'parser_mode': 'NO_BRIDGE', 'parse_status': 'bridge_missing'},
        {'status': 'BROKEN', 'confidence': 0, 'warnings': ['w1'], 'errors': ['e1']},
        {'session': 'UNKNOWN'},
    )
    assert snap2['parser_mode']  == 'NO_BRIDGE'
    assert snap2['parse_status'] == 'bridge_missing'
    assert snap2['warnings']     == ['w1']
    assert snap2['errors']       == ['e1']


# ── Test 5: missing file creates it ──────────────────────────────────────────

def test_missing_file_is_created(tmp_path, monkeypatch):
    target = tmp_path / 'new_snaps.json'
    assert not target.exists()
    import core.config as _cfg
    orig = _cfg.MCP_SNAPSHOTS_FILE
    _cfg.MCP_SNAPSHOTS_FILE = target
    try:
        snap = _make_snap()
        _append_mcp_snapshot(snap)
        assert target.exists()
        data = json.loads(target.read_text())
        assert len(data) == 1
    finally:
        _cfg.MCP_SNAPSHOTS_FILE = orig


# ── Test 6: write failure does not propagate ──────────────────────────────────

def test_write_failure_is_silent(monkeypatch):
    from pathlib import Path
    import core.config as _cfg
    orig = _cfg.MCP_SNAPSHOTS_FILE
    # Point to an impossible path
    _cfg.MCP_SNAPSHOTS_FILE = Path('/nonexistent_directory_xyz/snaps.json')
    crashed = False
    try:
        snap = _make_snap()
        _append_mcp_snapshot(snap)   # must not raise
    except Exception:
        crashed = True
    finally:
        _cfg.MCP_SNAPSHOTS_FILE = orig
    assert not crashed, '_append_mcp_snapshot must never propagate write errors'


# ── Test 7: mcp_health sub-dict ───────────────────────────────────────────────

def test_mcp_health_subdict():
    snap = _make_snap()
    h = snap['mcp_health']
    assert h['status']             == 'HEALTHY'
    assert h['confidence']         == 100
    assert h['bridge_v2_detected'] is True
    assert h['ticker_match']       is True
    assert h['timeframe_match']    is True
    assert h['warnings']           == []
    assert h['errors']             == []


# ── Test 8: market structure fields ──────────────────────────────────────────

def test_market_structure_fields():
    snap = _make_snap()
    assert snap['ib_high']        == '7489.75'
    assert snap['ib_low']         == '7409'
    assert snap['ib_status']      == 'COMPLETE'
    assert snap['orb_high']       == '7467.75'
    assert snap['orb_mid']        == '7464.5'
    assert snap['orb_low']        == '7461.25'
    assert snap['orb_active']     is False
    assert snap['pros_active']    is True
    assert snap['peer_alignment'] == 'CONFIRM'
    assert snap['draw_target']    == 7560.0
    assert snap['draw_direction'] == 'UP'


# ── Test 9: signal fields are None at capture time ───────────────────────────

def test_signal_fields_none_at_capture():
    snap = _make_snap()
    assert snap['setup_type']  is None
    assert snap['signal_type'] is None
    assert snap['direction']   is None
    assert snap['confidence']  is None
    assert snap['rationale']   is None


# ── Test 10: legacy / no-bridge path ─────────────────────────────────────────

def test_legacy_path_produces_valid_snapshot():
    tables = [
        ['NOVA ENGINE', 'CMD | SELL', 'STATE | BEAR TREND'],
        ['PROS ENGINE', 'DISPL | BEAR'],
    ]
    ctx        = {'connected': True, 'symbol': 'CME_MINI:MES1!', 'timeframe': '1', 'nova_tables': tables}
    nova_state = parse_nova_tables(tables)
    health     = compute_mcp_health(ctx, nova_state)
    snap       = _build_mcp_snapshot(ctx, nova_state, health, {'session': 'NY_AM'})

    assert snap['parser_mode']  == 'LEGACY_TABLES'
    assert snap['parse_status'] == 'legacy_fallback'
    assert snap['mcp_health']['status'] == 'BROKEN'
    assert snap['bridge_v2']    == {}    # no bridge_v2 in legacy path
    assert snap['bridge_meta']  == {}    # no bridge_meta in legacy path
    assert isinstance(snap['warnings'], list)
    assert isinstance(snap['errors'],   list)


# ── runner ────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    import pathlib, types

    class _TmpPath:
        def __enter__(self):
            import tempfile
            self._d = tempfile.mkdtemp()
            return pathlib.Path(self._d)
        def __exit__(self, *a):
            import shutil
            shutil.rmtree(self._d, ignore_errors=True)

    class _MP:
        def __init__(self): self._undo = []
        def setattr(self, obj, name, val):
            self._undo.append((obj, name, getattr(obj, name)))
            setattr(obj, name, val)
        def undo(self):
            for o, n, v in reversed(self._undo): setattr(o, n, v)

    import inspect
    tests = [(k, v) for k, v in globals().items() if k.startswith('test_')]
    passed = failed = 0
    for name, fn in tests:
        sig = inspect.signature(fn)
        mp  = _MP()
        try:
            kw = {}
            if 'tmp_path'   in sig.parameters:
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
            print(f'ERROR {name}: {e}')
            failed += 1
        finally:
            mp.undo()
            if 'tp' in dir() and 'tmp_path' in sig.parameters:
                try: tp.__exit__(None, None, None)
                except Exception: pass

    print(f'\n{passed}/{passed + failed} passed')
    sys.exit(1 if failed else 0)
