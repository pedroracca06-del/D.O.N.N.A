"""test_execution_bot_v2_phase4.py — Execution Bot v2 Phase 4 tests.

Tests cover:
- confirm_protective_orders_after_submit: position + stop + target → PROTECTIVE_ORDERS_CONFIRMED
- confirm_protective_orders_after_submit: position + stop only → TARGET_MISSING (not unprotected)
- confirm_protective_orders_after_submit: position + target only → STOP_MISSING (unprotected)
- confirm_protective_orders_after_submit: position + no orders → UNPROTECTED_POSITION
- confirm_protective_orders_after_submit: no position → INSUFFICIENT_DATA
- confirm_protective_orders_after_submit: bracket order → PROTECTIVE_ORDERS_CONFIRMED
- confirm_protective_orders_after_submit: pending entry order, no fill → ENTRY_NOT_FILLED
- build_unprotected_position_alert: correct fields present
- emergency alert created only when no stop
- emergency alert NOT created when stop is present
- get_execution_safety_status: no positions → NO_OPEN_POSITIONS
- get_execution_safety_status: protected position → ALL_POSITIONS_PROTECTED
- get_execution_safety_status: unprotected position → UNPROTECTED_POSITIONS_DETECTED + alert
- validate_and_record: Phase 4 fields present in req dict
- validate_and_record: trace_v2 includes Phase 4 fields
- validate_and_record: emergency_alert_severity=CRITICAL when position is unprotected
- dry-run never calls broker write methods
- live mode remains read-only (Phase 4 does not block live path)
- Phase 4 module error is non-blocking

All broker calls are mocked. All file I/O is isolated to tmp_path.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

import services.execution_reconcile as rcl


# ── Helpers ────────────────────────────────────────────────────────────────────

def _isolated_er(tmp_path: Path):
    for key in list(sys.modules.keys()):
        if key in ('services.execution_request', 'services.prop_risk',
                   'services.execution_reconcile'):
            del sys.modules[key]
    import services.execution_request as er
    er._registry_file = lambda: tmp_path / 'reg.json'
    er._trace_v2_file  = lambda: tmp_path / 'trace.json'
    return er


def _past_iso(seconds: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(seconds=seconds)).isoformat()


def _pos(symbol='QQQ', side='long', qty=10.0) -> dict:
    return {'symbol': symbol, 'side': side, 'qty': qty,
            'avg_entry_price': 400.0, 'market_value': 4000.0,
            'unrealized_pl': 50.0, 'raw': {}}


def _ord(symbol='QQQ', side='sell', order_type='stop',
         stop_price=390.0, limit_price=None, order_class='', legs=None) -> dict:
    return {
        'id': 'o1', 'symbol': symbol, 'side': side, 'type': order_type,
        'qty': 10.0, 'status': 'new',
        'limit_price': limit_price, 'stop_price': stop_price,
        'order_class': order_class, 'legs': legs or [], 'raw': {},
    }


def _req(symbol='MNQ', direction='LONG', exreq_id='EXREQ_TEST', decision_id=None):
    return {
        'symbol': symbol, 'direction': direction,
        'execution_request_id': exreq_id, 'decision_id': decision_id,
    }


# ── 1. confirm_protective_orders_after_submit ─────────────────────────────────

def test_position_stop_and_target_confirmed():
    positions = [_pos('QQQ', 'long', 10.0)]
    orders    = [
        _ord('QQQ', 'sell', 'stop',  stop_price=390.0),
        _ord('QQQ', 'sell', 'limit', limit_price=420.0),
    ]
    result = rcl.confirm_protective_orders_after_submit(_req(), orders, positions)
    assert result['confirmation_status']   == 'PROTECTIVE_ORDERS_CONFIRMED'
    assert result['position_found']        is True
    assert result['entry_filled']          is True
    assert result['stop_order_found']      is True
    assert result['target_order_found']    is True
    assert result['unprotected_position']  is False
    assert result['emergency_alert']       is None


def test_position_stop_only_returns_target_missing():
    positions = [_pos('QQQ', 'long', 10.0)]
    orders    = [_ord('QQQ', 'sell', 'stop', stop_price=390.0)]
    result    = rcl.confirm_protective_orders_after_submit(_req(), orders, positions)
    assert result['confirmation_status']  == 'TARGET_MISSING'
    assert result['stop_order_found']     is True
    assert result['target_order_found']   is False
    assert result['unprotected_position'] is False    # has stop — not unprotected
    assert result['emergency_alert']      is None     # stop present — no emergency


def test_position_target_only_returns_stop_missing():
    positions = [_pos('QQQ', 'long', 10.0)]
    orders    = [_ord('QQQ', 'sell', 'limit', limit_price=420.0)]
    result    = rcl.confirm_protective_orders_after_submit(_req(), orders, positions)
    assert result['confirmation_status']  == 'STOP_MISSING'
    assert result['stop_order_found']     is False
    assert result['target_order_found']   is True
    assert result['unprotected_position'] is True     # no stop = unprotected
    assert result['emergency_alert']      is not None
    assert result['emergency_alert']['severity'] == 'CRITICAL'


def test_position_no_orders_returns_unprotected():
    positions = [_pos('QQQ', 'long', 10.0)]
    result    = rcl.confirm_protective_orders_after_submit(_req(), [], positions)
    assert result['confirmation_status']  == 'UNPROTECTED_POSITION'
    assert result['stop_order_found']     is False
    assert result['target_order_found']   is False
    assert result['unprotected_position'] is True
    assert result['emergency_alert']      is not None


def test_no_position_returns_insufficient_data():
    result = rcl.confirm_protective_orders_after_submit(_req(), [], [])
    assert result['confirmation_status'] == 'INSUFFICIENT_DATA'
    assert result['position_found']      is False
    assert result['emergency_alert']     is None


def test_bracket_order_returns_confirmed():
    positions = [_pos('QQQ', 'long', 10.0)]
    orders    = [_ord('QQQ', 'sell', 'market', order_class='bracket')]
    result    = rcl.confirm_protective_orders_after_submit(_req(), orders, positions)
    assert result['confirmation_status']   == 'PROTECTIVE_ORDERS_CONFIRMED'
    assert result['bracket_or_oco_detected'] is True
    assert result['unprotected_position']  is False


def test_pending_entry_order_no_position_returns_entry_not_filled():
    """Limit entry order exists but position not yet open."""
    positions = []
    orders    = [_ord('QQQ', 'buy', 'limit', limit_price=400.0)]   # pending entry
    result    = rcl.confirm_protective_orders_after_submit(_req(), orders, positions)
    assert result['confirmation_status'] == 'ENTRY_NOT_FILLED'
    assert result['entry_order_found']   is True
    assert result['entry_filled']        is False
    assert result['position_found']      is False


# ── 2. build_unprotected_position_alert ──────────────────────────────────────

def test_emergency_alert_has_correct_fields():
    pos   = _pos('QQQ', 'long', 10.0)
    alert = rcl.build_unprotected_position_alert(
        symbol='MNQ', routed_etf='QQQ',
        broker_position=pos, broker_orders_seen=[],
        execution_request_id='EXREQ_TEST', decision_id='DEC-001',
    )
    assert alert['alert_type']           == 'UNPROTECTED_POSITION'
    assert alert['severity']             == 'CRITICAL'
    assert alert['symbol']               == 'MNQ'
    assert alert['instrument']           == 'QQQ'
    assert alert['qty']                  == 10.0
    assert alert['side']                 == 'long'
    assert alert['execution_request_id'] == 'EXREQ_TEST'
    assert alert['decision_id']          == 'DEC-001'
    assert alert['recommended_action']   == 'MANUAL_REVIEW_REQUIRED'
    assert 'CRITICAL' in alert['message']
    assert 'detected_at' in alert


def test_emergency_alert_not_created_when_protected():
    positions = [_pos('QQQ', 'long', 10.0)]
    orders    = [_ord('QQQ', 'sell', 'stop')]
    result    = rcl.confirm_protective_orders_after_submit(_req(), orders, positions)
    assert result['emergency_alert'] is None


# ── 3. get_execution_safety_status ───────────────────────────────────────────

def test_safety_status_no_positions():
    with patch.object(rcl, 'get_broker_positions_safe', return_value=[]), \
         patch.object(rcl, 'get_broker_orders_safe', return_value=[]), \
         patch.object(rcl, 'get_open_journal_trades_safe', return_value=[]):
        status = rcl.get_execution_safety_status()
    assert status['status']               == 'NO_OPEN_POSITIONS'
    assert status['open_positions_count'] == 0
    assert status['emergency_alerts']     == []
    assert status['unprotected_positions'] == []


def test_safety_status_protected_position():
    positions = [_pos('QQQ', 'long', 10.0)]
    orders    = [
        _ord('QQQ', 'sell', 'stop',  stop_price=390.0),
        _ord('QQQ', 'sell', 'limit', limit_price=420.0),
    ]
    with patch.object(rcl, 'get_broker_positions_safe', return_value=positions), \
         patch.object(rcl, 'get_broker_orders_safe', return_value=orders), \
         patch.object(rcl, 'get_open_journal_trades_safe', return_value=[]):
        status = rcl.get_execution_safety_status()
    assert status['status']                == 'ALL_POSITIONS_PROTECTED'
    assert len(status['protected_positions']) == 1
    assert status['emergency_alerts']        == []
    assert status['unprotected_positions']   == []


def test_safety_status_unprotected_position_raises_alert():
    positions = [_pos('QQQ', 'long', 10.0)]
    with patch.object(rcl, 'get_broker_positions_safe', return_value=positions), \
         patch.object(rcl, 'get_broker_orders_safe', return_value=[]), \
         patch.object(rcl, 'get_open_journal_trades_safe', return_value=[]):
        status = rcl.get_execution_safety_status()
    assert status['status']                    == 'UNPROTECTED_POSITIONS_DETECTED'
    assert len(status['unprotected_positions']) == 1
    assert len(status['emergency_alerts'])      == 1
    assert status['emergency_alerts'][0]['severity'] == 'CRITICAL'
    assert any('CRITICAL' in w for w in status['warnings'])


# ── 4. validate_and_record — Phase 4 fields present ──────────────────────────

def test_validate_and_record_has_phase4_fields(tmp_path):
    er = _isolated_er(tmp_path)
    with patch('services.execution_reconcile.get_broker_positions_safe', return_value=[]), \
         patch('services.execution_reconcile.get_broker_orders_safe', return_value=[]), \
         patch('services.execution_reconcile.get_open_journal_trades_safe', return_value=[]):
        req = er.validate_and_record(
            symbol='MNQ', direction='LONG', setup_type='PROS_LONG',
            signal_generated_at=_past_iso(5),
            dry_run_override=True,
        )
    assert 'protective_confirmation_status' in req
    assert 'entry_order_found'              in req
    assert 'entry_filled'                   in req
    assert 'position_found'                 in req
    assert 'stop_order_found'               in req
    assert 'target_order_found'             in req
    assert 'bracket_or_oco_detected'        in req
    assert 'emergency_alert'                in req
    assert 'emergency_alert_type'           in req
    assert 'emergency_alert_severity'       in req


def test_validate_and_record_emergency_alert_set_when_unprotected(tmp_path):
    er = _isolated_er(tmp_path)
    positions = [_pos('QQQ', 'long', 10.0)]
    with patch('services.execution_reconcile.get_broker_positions_safe', return_value=positions), \
         patch('services.execution_reconcile.get_broker_orders_safe', return_value=[]), \
         patch('services.execution_reconcile.get_open_journal_trades_safe', return_value=[]):
        req = er.validate_and_record(
            symbol='MNQ', direction='LONG', setup_type='PROS_LONG',
            signal_generated_at=_past_iso(5),
            dry_run_override=True,
        )
    # Emergency alert must be present and CRITICAL
    assert req['emergency_alert']          is not None
    assert req['emergency_alert_severity'] == 'CRITICAL'
    assert req['emergency_alert_type']     == 'UNPROTECTED_POSITION'
    # Also present in validation_warnings
    warnings = ' '.join(req.get('validation_warnings', []))
    assert 'EMERGENCY' in warnings or 'UNPROTECTED' in warnings


def test_validate_and_record_no_alert_when_clean(tmp_path):
    er = _isolated_er(tmp_path)
    with patch('services.execution_reconcile.get_broker_positions_safe', return_value=[]), \
         patch('services.execution_reconcile.get_broker_orders_safe', return_value=[]), \
         patch('services.execution_reconcile.get_open_journal_trades_safe', return_value=[]):
        req = er.validate_and_record(
            symbol='MNQ', direction='LONG', setup_type='PROS_LONG',
            signal_generated_at=_past_iso(5),
            dry_run_override=True,
        )
    assert req['emergency_alert']      is None
    assert req['emergency_alert_type'] is None


# ── 5. trace_v2 includes Phase 4 fields ──────────────────────────────────────

def test_trace_v2_includes_phase4_fields(tmp_path):
    er = _isolated_er(tmp_path)
    with patch('services.execution_reconcile.get_broker_positions_safe', return_value=[]), \
         patch('services.execution_reconcile.get_broker_orders_safe', return_value=[]), \
         patch('services.execution_reconcile.get_open_journal_trades_safe', return_value=[]):
        er.validate_and_record(
            symbol='MNQ', direction='LONG', setup_type='PROS_LONG',
            signal_generated_at=_past_iso(5),
            dry_run_override=True,
        )
    entries = er.get_trace_v2_recent(5)
    assert entries
    latest = entries[0]
    assert 'protective_confirmation_status' in latest
    assert 'entry_order_found'              in latest
    assert 'emergency_alert'                in latest
    assert 'emergency_alert_severity'       in latest


# ── 6. Dry-run never calls broker write methods ───────────────────────────────

def test_phase4_dry_run_never_calls_broker_writes(tmp_path):
    er = _isolated_er(tmp_path)
    cancel_calls  = []
    submit_calls  = []
    flatten_calls = []

    mock_client = MagicMock()
    mock_client.get_all_positions.return_value = []
    mock_client.get_orders.return_value        = []
    mock_client.cancel_order_by_id.side_effect = lambda *a: cancel_calls.append(a)
    mock_client.submit_order.side_effect        = lambda *a, **k: submit_calls.append(1)
    mock_client.close_all_positions.side_effect = lambda *a: flatten_calls.append(1)

    with patch('services.execution_reconcile._get_alpaca_client',
               return_value=(mock_client, None)):
        er.validate_and_record(
            symbol='MNQ', direction='LONG', setup_type='PROS_LONG',
            signal_generated_at=_past_iso(5),
            dry_run_override=True,
        )

    assert cancel_calls  == [], 'cancel_order_by_id must not be called'
    assert submit_calls  == [], 'submit_order must not be called'
    assert flatten_calls == [], 'close_all_positions must not be called'


# ── 7. Live mode remains read-only and non-blocking ──────────────────────────

def test_phase4_does_not_block_live_mode(tmp_path):
    """Phase 4 is observation only — does not affect final_status in live mode."""
    er = _isolated_er(tmp_path)
    # Inject an unprotected position (which would trigger CRITICAL alert)
    positions = [_pos('QQQ', 'long', 10.0)]
    with patch('services.execution_reconcile.get_broker_positions_safe', return_value=positions), \
         patch('services.execution_reconcile.get_broker_orders_safe', return_value=[]), \
         patch('services.execution_reconcile.get_open_journal_trades_safe', return_value=[]), \
         patch.dict('os.environ', {'NOVA_PROP_GATES_ENABLED': 'false'}):
        req = er.validate_and_record(
            symbol='MNQ', direction='LONG', setup_type='PROS_LONG',
            signal_generated_at=_past_iso(5),
            dry_run_override=False,
        )
    # Phase 4 emergency alert is present (logged) but does NOT block
    assert req['emergency_alert'] is not None
    # Open position conflict (Phase 3) blocks with NOVA_PROP_GATES_ENABLED=false?
    # No — it logs only. But wait: Phase 3 also detects the conflict (QQQ position = conflict).
    # With gates disabled in live mode, the final_status should still be RECEIVED.
    # However, Phase 3 conflict gate (REJECTED_OPEN_POSITION) in live mode with
    # NOVA_PROP_GATES_ENABLED=false returns RECEIVED (logs only).
    assert req['final_status'] == er.STATUS_RECEIVED
    assert req['emergency_alert_severity'] == 'CRITICAL'


# ── 8. Phase 4 error is non-blocking ─────────────────────────────────────────

def test_phase4_error_does_not_crash(tmp_path):
    er = _isolated_er(tmp_path)
    with patch('services.execution_reconcile.get_broker_positions_safe', return_value=[]), \
         patch('services.execution_reconcile.get_broker_orders_safe', return_value=[]), \
         patch('services.execution_reconcile.get_open_journal_trades_safe', return_value=[]), \
         patch('services.execution_reconcile.confirm_protective_orders_after_submit',
               side_effect=RuntimeError('Phase 4 exploded')):
        req = er.validate_and_record(
            symbol='MNQ', direction='LONG', setup_type='PROS_LONG',
            signal_generated_at=_past_iso(5),
            dry_run_override=True,
        )
    assert isinstance(req, dict)
    assert 'final_status' in req
    warnings = ' '.join(req.get('validation_warnings', []))
    assert 'Phase 4' in warnings


# ── 9. MES routes to SPY for Phase 4 confirmation ────────────────────────────

def test_phase4_mes_routes_to_spy(tmp_path):
    """MES signal should look for SPY positions, not QQQ."""
    er = _isolated_er(tmp_path)
    positions = [_pos('SPY', 'long', 20.0)]  # SPY position, no stop
    with patch('services.execution_reconcile.get_broker_positions_safe', return_value=positions), \
         patch('services.execution_reconcile.get_broker_orders_safe', return_value=[]), \
         patch('services.execution_reconcile.get_open_journal_trades_safe', return_value=[]):
        req = er.validate_and_record(
            symbol='MES', direction='LONG', setup_type='ORB_LONG',
            signal_generated_at=_past_iso(5),
            dry_run_override=True,
        )
    assert req['emergency_alert']      is not None
    assert req['emergency_alert']['instrument'] == 'SPY'


# ── 10. confirm_protective_orders: short position check ──────────────────────

def test_short_position_protective_orders():
    """For short positions, protective buy orders should be detected."""
    positions = [_pos('SPY', 'short', 15.0)]
    orders    = [
        _ord('SPY', 'buy', 'stop',  stop_price=450.0),   # protective buy stop
        _ord('SPY', 'buy', 'limit', limit_price=420.0),  # protective buy limit (target)
    ]
    req    = _req('MES', 'SHORT')
    result = rcl.confirm_protective_orders_after_submit(req, orders, positions)
    assert result['confirmation_status'] == 'PROTECTIVE_ORDERS_CONFIRMED'
    assert result['stop_order_found']    is True
    assert result['target_order_found']  is True
    assert result['unprotected_position'] is False
