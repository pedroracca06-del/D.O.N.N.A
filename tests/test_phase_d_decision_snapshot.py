"""
test_phase_d_decision_snapshot.py — Phase D decision snapshot smoke tests.

Covers:
  1.  market_read snapshot has snapshot_type='market_read'
  2.  decision snapshot has snapshot_type='decision'
  3.  decision snapshot preserves base market_read fields (identity, parser, bridge)
  4.  evaluator summaries populated from pros/orb/ib eval dicts
  5.  Claude decision fields propagated (alert_type, grade, setup_type, direction, tp1, rr, stop)
  6.  is_execution_ready flag correct
  7.  is_heads_up flag correct
  8.  is_rejected flag correct (claude called, no alert required)
  9.  rejection_reason populated when rejected
 10.  no-signal exit: signal_type='' pre_signal='' claude_called=False
 11.  daily-loss exit: alert_generated=True claude_called=False is_no_trade=True
 12.  no-Claude-decision exit: claude_called=True alert_generated=False is_rejected=True
 13.  missing fields (empty dicts) do not crash
 14.  write failure from _fire_decision_snapshot does not propagate

Run:  python tests/test_phase_d_decision_snapshot.py
      python -m pytest tests/test_phase_d_decision_snapshot.py -v
"""
from __future__ import annotations
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault('ALPACA_API_KEY',    '')
os.environ.setdefault('ALPACA_SECRET_KEY', '')

from engines.reasoning import (
    _build_mcp_snapshot, _build_decision_snapshot, _fire_decision_snapshot,
    _append_mcp_snapshot, _MCP_SNAPSHOT_CAP,
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

def _make_base_snap(symbol='CME_MINI:MES1!') -> dict:
    tables    = [_v2_rows()]
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
_DECISION_EXEC = {
    'alert_required': True, 'alert_type': 'EXECUTION_READY',
    'setup_type': 'PROS_CONT', 'direction': 'LONG', 'grade': 'A',
    'entry_zone': '7475–7480', 'stop': '7460', 'tp1': '7520', 'rr': '3.0',
    'notes': 'Clean OTE + IB alignment', 'reasoning': 'All conditions met.',
    'no_alert_reason': '',
}
_DECISION_REJECT = {
    'alert_required': False, 'alert_type': '',
    'setup_type': '', 'direction': '', 'grade': '',
    'entry_zone': '', 'stop': '', 'tp1': '', 'rr': '',
    'notes': '', 'reasoning': '',
    'no_alert_reason': 'OTE not confirmed',
}
_DECISION_HEADS_UP = {
    'alert_required': True, 'alert_type': 'HEADS_UP',
    'setup_type': 'PROS_SETUP', 'direction': 'LONG', 'grade': 'B',
    'entry_zone': '7470–7475', 'stop': '7455', 'tp1': '7510', 'rr': '2.7',
    'notes': '', 'reasoning': 'Watching for entry.', 'no_alert_reason': '',
}


# ── Test 1: market_read has correct snapshot_type ─────────────────────────────

def test_market_read_snapshot_type():
    snap = _make_base_snap()
    assert snap['snapshot_type'] == 'market_read', f"got {snap['snapshot_type']}"


# ── Test 2: decision snapshot has snapshot_type='decision' ────────────────────

def test_decision_snapshot_type():
    base = _make_base_snap()
    ds = _build_decision_snapshot(base, decision=_DECISION_EXEC, claude_called=True)
    assert ds['snapshot_type'] == 'decision', f"got {ds['snapshot_type']}"


# ── Test 3: decision preserves base identity fields ───────────────────────────

def test_decision_preserves_base_fields():
    base = _make_base_snap()
    ds   = _build_decision_snapshot(base, decision=_DECISION_EXEC, claude_called=True)
    assert ds['symbol']      == base['symbol']
    assert ds['timeframe']   == base['timeframe']
    assert ds['session']     == base['session']
    assert ds['parser_mode'] == 'BRIDGE_V2'
    assert ds['parse_status'] == 'ok'
    assert ds['mcp_health']['status'] == 'HEALTHY'
    assert ds['bridge_meta'] == base['bridge_meta']


# ── Test 4: evaluator summaries populated ────────────────────────────────────

def test_evaluator_summaries_populated():
    base = _make_base_snap()
    ds   = _build_decision_snapshot(
        base, pros_eval=_PROS_EVAL, orb_eval=_ORB_EVAL, ib_eval=_IB_EVAL,
        decision=_DECISION_EXEC, claude_called=True,
    )
    ps = ds['pros_eval_summary']
    assert ps['phase']          == 'CONTINUATION'
    assert ps['direction']      == 'BULL'
    assert ps['has_signal']     is True
    assert ps['signal_strength'] == 'STRONG'
    assert ps['ote_status']     == 'TAGGED'

    os = ds['orb_eval_summary']
    assert os['phase']       == 'ORB_EXPIRED'
    assert os['has_signal']  is False
    assert os['orb_range']   == 25.5

    ib = ds['ib_eval_summary']
    assert ib['draw']     == 'IB_H'
    assert ib['aligned']  is True
    assert ib['ib_range'] == 80.75


# ── Test 5: Claude decision fields propagated ─────────────────────────────────

def test_claude_decision_fields():
    base = _make_base_snap()
    ds   = _build_decision_snapshot(base, decision=_DECISION_EXEC, claude_called=True)
    assert ds['signal_type']  == 'EXECUTION_READY'
    assert ds['setup_type']   == 'PROS_CONT'
    assert ds['direction']    == 'LONG'
    assert ds['grade']        == 'A'
    assert ds['entry_zone']   == '7475–7480'
    assert ds['stop']         == '7460'
    assert ds['tp1']          == '7520'
    assert ds['rr']           == '3.0'
    assert ds['rationale']    == 'All conditions met.'


# ── Test 6: is_execution_ready flag ──────────────────────────────────────────

def test_is_execution_ready():
    base = _make_base_snap()
    ds   = _build_decision_snapshot(base, decision=_DECISION_EXEC, claude_called=True, alert_generated=True)
    assert ds['is_execution_ready'] is True
    assert ds['is_heads_up']        is False
    assert ds['is_no_trade']        is False
    assert ds['alert_required']     is True
    assert ds['alert_generated']    is True
    assert ds['is_rejected']        is False


# ── Test 7: is_heads_up flag ──────────────────────────────────────────────────

def test_is_heads_up():
    base = _make_base_snap()
    ds   = _build_decision_snapshot(base, decision=_DECISION_HEADS_UP, claude_called=True)
    assert ds['is_heads_up']        is True
    assert ds['is_execution_ready'] is False
    assert ds['is_rejected']        is False


# ── Test 8: is_rejected flag ──────────────────────────────────────────────────

def test_is_rejected():
    base = _make_base_snap()
    ds   = _build_decision_snapshot(base, decision=_DECISION_REJECT, claude_called=True)
    assert ds['is_rejected']    is True
    assert ds['alert_required'] is False
    assert ds['alert_generated'] is False


# ── Test 9: rejection_reason populated ────────────────────────────────────────

def test_rejection_reason():
    base = _make_base_snap()
    ds   = _build_decision_snapshot(base, decision=_DECISION_REJECT, claude_called=True)
    assert ds['rejection_reason'] == 'OTE not confirmed'

    # When alert IS required, rejection_reason is empty
    ds2  = _build_decision_snapshot(base, decision=_DECISION_EXEC, claude_called=True)
    assert ds2['rejection_reason'] == ''


# ── Test 10: no-signal exit ───────────────────────────────────────────────────

def test_no_signal_exit():
    base = _make_base_snap()
    ds   = _build_decision_snapshot(
        base,
        pros_eval=_PROS_EVAL, orb_eval=_ORB_EVAL, ib_eval=_IB_EVAL,
        pre_signal='', pre_setup='', pre_rationale='no evaluator triggered',
        decision=None, claude_called=False, alert_generated=False,
    )
    assert ds['snapshot_type']  == 'decision'
    assert ds['claude_called']  is False
    assert ds['signal_type']    == ''
    assert ds['alert_generated'] is False
    assert ds['is_rejected']    is False
    assert ds['is_execution_ready'] is False


# ── Test 11: daily-loss exit ──────────────────────────────────────────────────

def test_daily_loss_exit():
    base = _make_base_snap()
    ds   = _build_decision_snapshot(
        base,
        pros_eval=_PROS_EVAL, orb_eval=_ORB_EVAL, ib_eval=_IB_EVAL,
        pre_signal='NO_TRADE', pre_setup='N/A', pre_rationale='daily loss limit',
        decision=None, claude_called=False, alert_generated=True,
    )
    assert ds['is_no_trade']     is True
    assert ds['claude_called']   is False
    assert ds['alert_generated'] is True
    assert ds['is_rejected']     is False  # no Claude call, not a rejection


# ── Test 12: no-Claude-decision exit ─────────────────────────────────────────

def test_no_claude_decision_exit():
    base = _make_base_snap()
    ds   = _build_decision_snapshot(
        base,
        pros_eval=_PROS_EVAL, orb_eval=_ORB_EVAL, ib_eval=_IB_EVAL,
        pre_signal='HEADS_UP', pre_setup='PROS_SETUP', pre_rationale='signal detected',
        decision=None, claude_called=True, alert_generated=False,
    )
    assert ds['claude_called']   is True
    assert ds['alert_generated'] is False
    assert ds['is_rejected']     is True   # Claude called, no alert_required
    assert ds['signal_type']     == 'HEADS_UP'  # falls back to pre_signal


# ── Test 13: empty inputs do not crash ───────────────────────────────────────

def test_empty_inputs_no_crash():
    base = _make_base_snap()
    ds   = _build_decision_snapshot(base)
    assert isinstance(ds, dict)
    assert ds['snapshot_type'] == 'decision'
    assert ds['pros_eval_summary']['phase'] is None
    assert ds['orb_eval_summary']['has_signal'] is None
    assert ds['ib_eval_summary']['draw'] is None
    assert ds['claude_called'] is False
    assert ds['alert_generated'] is False


# ── Test 14: _fire_decision_snapshot write failure does not propagate ─────────

def test_fire_decision_snapshot_write_failure_silent(monkeypatch):
    from pathlib import Path
    import core.config as _cfg
    orig = _cfg.MCP_SNAPSHOTS_FILE
    _cfg.MCP_SNAPSHOTS_FILE = Path('/nonexistent_dir_xyz/snaps.json')
    crashed = False
    try:
        base = _make_base_snap()
        _fire_decision_snapshot(base, decision=_DECISION_EXEC, claude_called=True)
        import time; time.sleep(0.05)  # let daemon thread attempt write
    except Exception:
        crashed = True
    finally:
        _cfg.MCP_SNAPSHOTS_FILE = orig
    assert not crashed, '_fire_decision_snapshot must never propagate write errors'


# ── runner ────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    import inspect

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
        try:
            kw = {}
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

    print(f'\n{passed}/{passed + failed} passed')
    sys.exit(1 if failed else 0)
