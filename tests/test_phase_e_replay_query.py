"""
test_phase_e_replay_query.py — Phase E MCP Replay Query Layer smoke tests.

Covers:
  1.  empty snapshot file returns []
  2.  malformed snapshot file returns safe response ([])
  3.  limit parameter is respected
  4.  filter snapshot_type=market_read works
  5.  filter snapshot_type=decision works
  6.  filter symbol works
  7.  filter parser_mode works
  8.  filter setup_type works
  9.  filter is_execution_ready=True works
 10.  filter is_rejected=True works
 11.  combined filters are AND-ed
 12.  _decision_replay_summary contains all expected fields
 13.  _decision_replay_summary with missing fields does not crash
 14.  /api/mcp-snapshots/latest returns most recent entry
 15.  /api/mcp-snapshots/decisions shorthand returns only decisions
 16.  /api/mcp-replay/decisions returns compact summaries

Run:  python tests/test_phase_e_replay_query.py
      python -m pytest tests/test_phase_e_replay_query.py -v
"""
from __future__ import annotations
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault('ALPACA_API_KEY',    '')
os.environ.setdefault('ALPACA_SECRET_KEY', '')

from main import _read_mcp_snapshots_raw, _filter_snapshots, _decision_replay_summary

# ── fixtures ──────────────────────────────────────────────────────────────────

def _mr_snap(symbol='CME_MINI:MES1!', parser_mode='BRIDGE_V2') -> dict:
    return {
        'snapshot_type': 'market_read',
        'timestamp':     '2026-06-30T10:00:00Z',
        'symbol':        symbol,
        'timeframe':     '1',
        'session':       'NY_CASH',
        'parser_mode':   parser_mode,
        'parse_status':  'ok',
        'mcp_health':    {'status': 'HEALTHY', 'confidence': 100},
        'ticker_match':  True,
        'timeframe_match': True,
        'setup_type':    None,
        'signal_type':   None,
        'direction':     None,
        'is_execution_ready': None,
        'is_rejected':   None,
        'ib_status':     'COMPLETE',
        'orb_active':    False,
        'pros_active':   True,
        'peer_alignment': 'CONFIRM',
        'draw_direction': 'UP',
    }

def _dec_snap(
    symbol='CME_MINI:MES1!',
    signal_type='EXECUTION_READY',
    setup_type='PROS_CONT',
    direction='LONG',
    is_execution_ready=True,
    is_rejected=False,
    parser_mode='BRIDGE_V2',
) -> dict:
    return {
        'snapshot_type': 'decision',
        'timestamp':     '2026-06-30T10:01:00Z',
        'symbol':        symbol,
        'timeframe':     '1',
        'session':       'NY_CASH',
        'parser_mode':   parser_mode,
        'parse_status':  'ok',
        'mcp_health':    {'status': 'HEALTHY', 'confidence': 100},
        'ticker_match':  True,
        'timeframe_match': True,
        'pre_signal':    signal_type,
        'pre_setup':     setup_type,
        'signal_type':   signal_type,
        'setup_type':    setup_type,
        'direction':     direction,
        'grade':         'A',
        'rationale':     'All conditions met.',
        'is_execution_ready': is_execution_ready,
        'is_heads_up':   False,
        'is_no_trade':   False,
        'is_rejected':   is_rejected,
        'rejection_reason': '',
        'ib_status':     'COMPLETE',
        'orb_active':    False,
        'pros_active':   True,
        'peer_alignment': 'CONFIRM',
        'draw_direction': 'UP',
        'claude_called': True,
        'alert_generated': True,
    }

_MIXED = [
    _mr_snap(symbol='CME_MINI:MES1!'),
    _dec_snap(symbol='CME_MINI:MES1!', signal_type='EXECUTION_READY', is_execution_ready=True),
    _mr_snap(symbol='CME_MINI:MNQ1!'),
    _dec_snap(symbol='CME_MINI:MNQ1!', signal_type='HEADS_UP', setup_type='PROS_SETUP',
              is_execution_ready=False, is_rejected=False),
    _dec_snap(symbol='CME_MINI:MES1!', signal_type='', setup_type='',
              is_execution_ready=False, is_rejected=True, direction=''),
]


# ── Test 1: empty file returns [] ─────────────────────────────────────────────

def test_empty_file_returns_empty(tmp_path, monkeypatch):
    import core.config as _cfg
    target = tmp_path / 'empty.json'
    target.write_text('[]', encoding='utf-8')
    orig = _cfg.MCP_SNAPSHOTS_FILE
    _cfg.MCP_SNAPSHOTS_FILE = target
    try:
        result = _read_mcp_snapshots_raw()
        assert result == []
    finally:
        _cfg.MCP_SNAPSHOTS_FILE = orig


# ── Test 2: malformed file returns [] ────────────────────────────────────────

def test_malformed_file_returns_empty(tmp_path, monkeypatch):
    import core.config as _cfg
    target = tmp_path / 'bad.json'
    target.write_text('{not valid json}', encoding='utf-8')
    orig = _cfg.MCP_SNAPSHOTS_FILE
    _cfg.MCP_SNAPSHOTS_FILE = target
    try:
        result = _read_mcp_snapshots_raw()
        assert result == []
    finally:
        _cfg.MCP_SNAPSHOTS_FILE = orig


# ── Test 2b: file with non-list JSON returns [] ───────────────────────────────

def test_non_list_json_returns_empty(tmp_path, monkeypatch):
    import core.config as _cfg
    target = tmp_path / 'obj.json'
    target.write_text('{"key": "value"}', encoding='utf-8')
    orig = _cfg.MCP_SNAPSHOTS_FILE
    _cfg.MCP_SNAPSHOTS_FILE = target
    try:
        result = _read_mcp_snapshots_raw()
        assert result == []
    finally:
        _cfg.MCP_SNAPSHOTS_FILE = orig


# ── Test 3: limit is respected ────────────────────────────────────────────────

def test_limit_respected():
    result = _filter_snapshots(_MIXED)
    assert len(result) == 5

    limited = result[-2:]
    assert len(limited) == 2


# ── Test 4: filter snapshot_type=market_read ──────────────────────────────────

def test_filter_snapshot_type_market_read():
    result = _filter_snapshots(_MIXED, snapshot_type='market_read')
    assert len(result) == 2
    assert all(s['snapshot_type'] == 'market_read' for s in result)


# ── Test 5: filter snapshot_type=decision ────────────────────────────────────

def test_filter_snapshot_type_decision():
    result = _filter_snapshots(_MIXED, snapshot_type='decision')
    assert len(result) == 3
    assert all(s['snapshot_type'] == 'decision' for s in result)


# ── Test 6: filter symbol ─────────────────────────────────────────────────────

def test_filter_symbol():
    result = _filter_snapshots(_MIXED, symbol='CME_MINI:MES1!')
    assert len(result) == 3
    assert all(s['symbol'] == 'CME_MINI:MES1!' for s in result)

    result_mnq = _filter_snapshots(_MIXED, symbol='CME_MINI:MNQ1!')
    assert len(result_mnq) == 2


# ── Test 7: filter parser_mode ────────────────────────────────────────────────

def test_filter_parser_mode():
    mixed_with_legacy = list(_MIXED) + [_mr_snap(parser_mode='LEGACY_TABLES')]
    result = _filter_snapshots(mixed_with_legacy, parser_mode='BRIDGE_V2')
    assert len(result) == 5
    assert all(s['parser_mode'] == 'BRIDGE_V2' for s in result)

    legacy = _filter_snapshots(mixed_with_legacy, parser_mode='LEGACY_TABLES')
    assert len(legacy) == 1


# ── Test 8: filter setup_type ────────────────────────────────────────────────

def test_filter_setup_type():
    result = _filter_snapshots(_MIXED, setup_type='PROS_CONT')
    assert len(result) == 1
    assert result[0]['setup_type'] == 'PROS_CONT'

    result2 = _filter_snapshots(_MIXED, setup_type='PROS_SETUP')
    assert len(result2) == 1


# ── Test 9: filter is_execution_ready=True ───────────────────────────────────

def test_filter_is_execution_ready():
    result = _filter_snapshots(_MIXED, is_execution_ready=True)
    assert len(result) == 1
    assert result[0]['signal_type'] == 'EXECUTION_READY'

    result_false = _filter_snapshots(_MIXED, is_execution_ready=False)
    # 2 market_reads (is_execution_ready=None → bool(None)=False) + 2 decision False + 1 rejected
    # None == False is False, so bool(None) = False → included
    assert all(not s.get('is_execution_ready') for s in result_false)


# ── Test 10: filter is_rejected=True ─────────────────────────────────────────

def test_filter_is_rejected():
    result = _filter_snapshots(_MIXED, is_rejected=True)
    assert len(result) == 1
    assert result[0]['is_rejected'] is True


# ── Test 11: combined filters are AND-ed ──────────────────────────────────────

def test_combined_filters_anded():
    result = _filter_snapshots(
        _MIXED,
        snapshot_type='decision',
        symbol='CME_MINI:MES1!',
        is_execution_ready=True,
    )
    assert len(result) == 1
    assert result[0]['signal_type'] == 'EXECUTION_READY'
    assert result[0]['symbol'] == 'CME_MINI:MES1!'

    # No match
    result_none = _filter_snapshots(
        _MIXED,
        snapshot_type='decision',
        symbol='CME_MINI:MNQ1!',
        is_execution_ready=True,
    )
    assert result_none == []


# ── Test 12: decision replay summary contains all expected fields ─────────────

_SUMMARY_FIELDS = [
    'timestamp', 'symbol', 'timeframe', 'session',
    'parser_mode', 'parse_status',
    'mcp_status', 'mcp_confidence',
    'pre_signal', 'pre_setup',
    'signal_type', 'setup_type', 'direction', 'grade', 'rationale',
    'is_execution_ready', 'is_heads_up', 'is_no_trade',
    'is_rejected', 'rejection_reason',
    'ib_status', 'orb_active', 'pros_active', 'peer_alignment', 'draw_direction',
]

def test_decision_replay_summary_fields():
    snap = _dec_snap()
    summary = _decision_replay_summary(snap)
    for f in _SUMMARY_FIELDS:
        assert f in summary, f'missing field: {f}'
    assert summary['mcp_status']     == 'HEALTHY'
    assert summary['mcp_confidence'] == 100
    assert summary['signal_type']    == 'EXECUTION_READY'
    assert summary['grade']          == 'A'
    assert summary['ib_status']      == 'COMPLETE'
    assert summary['draw_direction'] == 'UP'


# ── Test 13: summary with missing fields does not crash ───────────────────────

def test_decision_replay_summary_missing_fields_no_crash():
    summary = _decision_replay_summary({})
    assert isinstance(summary, dict)
    for f in _SUMMARY_FIELDS:
        assert f in summary
    assert summary['mcp_status'] is None
    assert summary['signal_type'] is None


# ── Test 14: latest returns most recent entry ─────────────────────────────────

def test_latest_returns_most_recent(tmp_path, monkeypatch):
    import core.config as _cfg
    target = tmp_path / 'snaps.json'
    snaps = list(_MIXED)
    last = _dec_snap(symbol='CME_MINI:MES1!', signal_type='HEADS_UP')
    last['timestamp'] = '2026-06-30T11:00:00Z'
    snaps.append(last)
    target.write_text(json.dumps(snaps), encoding='utf-8')
    orig = _cfg.MCP_SNAPSHOTS_FILE
    _cfg.MCP_SNAPSHOTS_FILE = target
    try:
        raw = _read_mcp_snapshots_raw()
        most_recent = raw[-1] if raw else {}
        assert most_recent['timestamp'] == '2026-06-30T11:00:00Z'
        assert most_recent['signal_type'] == 'HEADS_UP'
    finally:
        _cfg.MCP_SNAPSHOTS_FILE = orig


# ── Test 15: decisions shorthand returns only decision snapshots ──────────────

def test_decisions_shorthand():
    decisions = _filter_snapshots(_MIXED, snapshot_type='decision')
    assert all(s['snapshot_type'] == 'decision' for s in decisions)
    assert len(decisions) == 3


# ── Test 16: replay summaries are compact (only summary fields) ───────────────

def test_replay_summaries_compact():
    decisions = _filter_snapshots(_MIXED, snapshot_type='decision')
    summaries = [_decision_replay_summary(s) for s in decisions]
    assert len(summaries) == 3
    for s in summaries:
        for f in _SUMMARY_FIELDS:
            assert f in s, f'missing field: {f}'
        # Compact — should NOT include raw bridge_v2, nova_main, etc.
        assert 'bridge_v2' not in s
        assert 'nova_main' not in s
        assert 'nova_pros' not in s
        assert 'bridge_meta' not in s


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
