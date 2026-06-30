"""
test_phase_f_fingerprint.py — Phase F setup fingerprinting smoke tests.

Covers:
  1.  fingerprint builds from a full decision snapshot
  2.  fingerprint handles completely missing fields (empty dict)
  3.  market family normalization — ES/MES → 'ES', NQ/MNQ → 'NQ'
  4.  fingerprint is deterministic for same input (call twice, same result)
  5.  time_bucket floors correctly (30-min intervals)
  6.  time_bucket handles missing / malformed timestamps
  7.  setup_fingerprint is embedded in decision snapshots via _build_decision_snapshot
  8.  setup_fingerprint NOT embedded in market_read snapshots
  9.  fingerprint endpoint helper returns compact records with all required keys
 10.  no snapshot file → empty list (via _read_mcp_snapshots_raw)
 11.  fingerprint identity fields correct
 12.  fingerprint market structure fields pulled from eval summaries
 13.  fingerprint MCP reliability fields match snapshot values
 14.  fingerprint decision flags match snapshot values

Run:  python tests/test_phase_f_fingerprint.py
      python -m pytest tests/test_phase_f_fingerprint.py -v
"""
from __future__ import annotations
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault('ALPACA_API_KEY',    '')
os.environ.setdefault('ALPACA_SECRET_KEY', '')

from engines.reasoning import (
    _build_setup_fingerprint, _build_decision_snapshot,
    _normalize_market_family, _time_bucket_utc,
    _build_mcp_snapshot, parse_nova_tables, compute_mcp_health,
)
from main import _read_mcp_snapshots_raw, _filter_snapshots

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

def _make_base_snap(symbol='CME_MINI:MES1!', ticker='MES1!') -> dict:
    tables    = [_v2_rows(ticker=ticker)]
    chart_ctx = {'connected': True, 'symbol': symbol, 'timeframe': '1', 'nova_tables': tables}
    session   = {'session': 'NY_CASH', 'time_et': '10:15'}
    nova_state = parse_nova_tables(tables)
    health     = compute_mcp_health(chart_ctx, nova_state)
    return _build_mcp_snapshot(chart_ctx, nova_state, health, session)

_PROS_EVAL = {
    'phase': 'CONTINUATION', 'direction': 'BULL', 'setup_type': 'PROS_CONT',
    'has_signal': True, 'signal_strength': 'STRONG',
    'ote_status': 'TAGGED', 'cont_quality': 'CONFIRMED',
}
_ORB_EVAL = {
    'phase': 'ORB_EXPIRED', 'direction': 'BULL', 'setup_type': 'ORB_EDGE',
    'has_signal': False, 'entry_type': 'EDGE', 'entry_quality': 'GOOD',
    'in_context': True, 'orb_range': 25.5,
}
_IB_EVAL = {
    'draw': 'IB_H', 'draw_source': 'pros_table', 'aligned': True,
    'ib_range': 80.75, 'ib_tight': False, 'ib_source': 'pros_table',
}
_DECISION = {
    'alert_required': True, 'alert_type': 'EXECUTION_READY',
    'setup_type': 'PROS_CONT', 'direction': 'LONG', 'grade': 'A',
    'entry_zone': '7475–7480', 'stop': '7460', 'tp1': '7520', 'rr': '3.0',
    'notes': 'Clean OTE + IB alignment', 'reasoning': 'All conditions met.',
    'no_alert_reason': '',
}

def _make_decision_snap(**kwargs) -> dict:
    base = _make_base_snap()
    base['timestamp'] = '2026-06-30T14:01:00Z'
    return _build_decision_snapshot(
        base,
        pros_eval=_PROS_EVAL, orb_eval=_ORB_EVAL, ib_eval=_IB_EVAL,
        pre_signal='EXECUTION_READY', pre_setup='PROS_CONT', pre_rationale='all met',
        decision=_DECISION, claude_called=True, alert_generated=True,
        **kwargs,
    )


# ── Test 1: full fingerprint build ────────────────────────────────────────────

def test_fingerprint_builds_from_decision_snap():
    ds = _make_decision_snap()
    fp = _build_setup_fingerprint(ds)
    assert isinstance(fp, dict)
    assert fp['symbol']        == 'CME_MINI:MES1!'
    assert fp['market_family'] == 'ES'
    assert fp['session']       == 'NY_CASH'
    assert fp['setup_type']    == 'PROS_CONT'
    assert fp['direction']     == 'LONG'
    assert fp['grade']         == 'A'
    assert fp['signal_type']   == 'EXECUTION_READY'
    assert fp['ib_location']   == 'IB_H'
    assert fp['pros_phase']    == 'CONTINUATION'
    assert fp['pros_quality']  == 'STRONG'
    assert fp['pros_continuation'] == 'CONFIRMED'
    assert fp['orb_entry_type']    == 'EDGE'
    assert fp['parser_mode']   == 'BRIDGE_V2'
    assert fp['mcp_status']    == 'HEALTHY'
    assert fp['is_execution_ready'] is True
    assert fp['is_rejected']   is False


# ── Test 2: empty dict does not crash ────────────────────────────────────────

def test_fingerprint_missing_fields_no_crash():
    fp = _build_setup_fingerprint({})
    assert isinstance(fp, dict)
    assert fp['symbol']        is None
    assert fp['market_family'] == ''   # _normalize_market_family('') → ''
    assert fp['time_bucket']   is None
    assert fp['mcp_status']    is None
    assert fp['ib_location']   is None
    assert fp['liquidity_context'] is None


# ── Test 3: market family normalization ───────────────────────────────────────

def test_normalize_market_family():
    assert _normalize_market_family('CME_MINI:MES1!') == 'ES'
    assert _normalize_market_family('CME_MINI:ES1!')  == 'ES'
    assert _normalize_market_family('CME_MINI:MNQ1!') == 'NQ'
    assert _normalize_market_family('CME_MINI:NQ1!')  == 'NQ'
    assert _normalize_market_family('MES1!')           == 'ES'
    assert _normalize_market_family('MNQ1!')           == 'NQ'
    assert _normalize_market_family('ES1!')            == 'ES'
    assert _normalize_market_family('NQ1!')            == 'NQ'
    assert _normalize_market_family('MES')             == 'ES'
    assert _normalize_market_family('NQ')              == 'NQ'
    assert _normalize_market_family('')                == ''


# ── Test 4: deterministic for same input ─────────────────────────────────────

def test_fingerprint_is_deterministic():
    ds = _make_decision_snap()
    fp1 = _build_setup_fingerprint(ds)
    fp2 = _build_setup_fingerprint(ds)
    assert fp1 == fp2


# ── Test 5: time bucket 30-min floor ─────────────────────────────────────────

def test_time_bucket_floor():
    assert _time_bucket_utc('2026-06-30T09:30:00Z') == '09:30'
    assert _time_bucket_utc('2026-06-30T09:45:00Z') == '09:30'
    assert _time_bucket_utc('2026-06-30T10:00:00Z') == '10:00'
    assert _time_bucket_utc('2026-06-30T10:29:00Z') == '10:00'
    assert _time_bucket_utc('2026-06-30T10:30:00Z') == '10:30'
    assert _time_bucket_utc('2026-06-30T14:01:00Z') == '14:00'
    assert _time_bucket_utc('2026-06-30T23:59:00Z') == '23:30'


# ── Test 6: time bucket handles bad timestamps ────────────────────────────────

def test_time_bucket_bad_input():
    assert _time_bucket_utc('')      is None
    assert _time_bucket_utc(None)    is None   # type: ignore
    assert _time_bucket_utc('not-a-ts') is None


# ── Test 7: setup_fingerprint embedded in decision snapshots ──────────────────

def test_fingerprint_embedded_in_decision_snapshot():
    ds = _make_decision_snap()
    assert 'setup_fingerprint' in ds
    fp = ds['setup_fingerprint']
    assert isinstance(fp, dict)
    assert fp['market_family'] == 'ES'
    assert fp['setup_type']    == 'PROS_CONT'


# ── Test 8: market_read snapshots do NOT have setup_fingerprint ───────────────

def test_fingerprint_not_in_market_read():
    base = _make_base_snap()
    assert 'setup_fingerprint' not in base


# ── Test 9: fingerprint endpoint compact record keys ─────────────────────────

_COMPACT_KEYS = [
    'timestamp', 'symbol', 'setup_type', 'direction', 'signal_type',
    'session', 'fingerprint', 'mcp_confidence', 'is_execution_ready', 'is_rejected',
]

def test_fingerprint_endpoint_compact_keys():
    from main import _read_mcp_snapshots_raw, _filter_snapshots
    ds = _make_decision_snap()
    # Build the compact record the same way the endpoint does
    from engines.reasoning import _build_setup_fingerprint as _bsf
    fp = ds.get('setup_fingerprint') or _bsf(ds)
    record = {
        'timestamp':          ds.get('timestamp'),
        'symbol':             ds.get('symbol'),
        'setup_type':         ds.get('setup_type'),
        'direction':          ds.get('direction'),
        'signal_type':        ds.get('signal_type'),
        'session':            ds.get('session'),
        'fingerprint':        fp,
        'mcp_confidence':     (ds.get('mcp_health') or {}).get('confidence'),
        'is_execution_ready': ds.get('is_execution_ready'),
        'is_rejected':        ds.get('is_rejected'),
    }
    for k in _COMPACT_KEYS:
        assert k in record, f'missing key: {k}'
    assert record['fingerprint']['market_family'] == 'ES'
    assert record['mcp_confidence'] == 100


# ── Test 10: no snapshot file returns [] ──────────────────────────────────────

def test_no_file_returns_empty(tmp_path, monkeypatch):
    import core.config as _cfg
    orig = _cfg.MCP_SNAPSHOTS_FILE
    _cfg.MCP_SNAPSHOTS_FILE = tmp_path / 'nonexistent.json'
    try:
        result = _read_mcp_snapshots_raw()
        assert result == []
    finally:
        _cfg.MCP_SNAPSHOTS_FILE = orig


# ── Test 11: fingerprint identity fields ─────────────────────────────────────

def test_fingerprint_identity_fields():
    ds = _make_decision_snap()
    fp = ds['setup_fingerprint']
    assert fp['symbol']      == 'CME_MINI:MES1!'
    assert fp['market_family'] == 'ES'
    assert fp['timeframe']   == '1'
    assert fp['session']     == 'NY_CASH'
    assert fp['time_bucket'] == '14:00'   # timestamp is 14:01 → bucket 14:00


# ── Test 12: fingerprint market structure from eval summaries ─────────────────

def test_fingerprint_market_structure_from_evals():
    ds = _make_decision_snap()
    fp = ds['setup_fingerprint']
    assert fp['ib_location']       == 'IB_H'
    assert fp['ib_range']          == 80.75
    assert fp['ib_tight']          is False
    assert fp['orb_phase']         == 'ORB_EXPIRED'
    assert fp['orb_entry_type']    == 'EDGE'
    assert fp['orb_entry_quality'] == 'GOOD'
    assert fp['orb_in_context']    is True
    assert fp['draw_direction']    == 'UP'
    assert fp['peer_alignment']    == 'CONFIRM'
    assert fp['liquidity_context'] is None  # Phase G


# ── Test 13: fingerprint MCP reliability fields ───────────────────────────────

def test_fingerprint_mcp_reliability():
    ds = _make_decision_snap()
    fp = ds['setup_fingerprint']
    assert fp['parser_mode']    == 'BRIDGE_V2'
    assert fp['parse_status']   == 'ok'
    assert fp['mcp_status']     == 'HEALTHY'
    assert fp['mcp_confidence'] == 100
    assert fp['ticker_match']   is True
    assert fp['timeframe_match'] is True


# ── Test 14: fingerprint decision flags ───────────────────────────────────────

def test_fingerprint_decision_flags():
    ds = _make_decision_snap()
    fp = ds['setup_fingerprint']
    assert fp['is_execution_ready'] is True
    assert fp['is_heads_up']        is False
    assert fp['is_no_trade']        is False
    assert fp['is_rejected']        is False
    assert fp['rejection_reason']   == ''


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
