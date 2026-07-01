"""test_execution_bot_v2_phase3.py — Execution Bot v2 Phase 3 tests.

Tests cover:
- check_open_position_conflict: no positions → no conflict
- check_open_position_conflict: same ETF position → REJECTED_OPEN_POSITION
- check_open_position_conflict: opposite direction still conflicts
- get_broker_positions_safe / get_broker_orders_safe: failure → []
- reconcile_execution_state: empty data → INSUFFICIENT_DATA
- reconcile_execution_state: position + stop + target → SYNCED
- reconcile_execution_state: position + no stop → UNPROTECTED_POSITION
- reconcile_execution_state: journal open but broker missing → BROKER_POSITION_MISSING
- reconcile_execution_state: broker position but no journal → JOURNAL_MISSING
- reconcile_execution_state: size mismatch detected
- reconcile_execution_state: direction mismatch detected
- detect_protective_orders: stop found for long position
- detect_protective_orders: bracket order = fully protected
- detect_protective_orders: no orders = unprotected
- validate_and_record Phase 3: REJECTED_OPEN_POSITION in dry-run
- validate_and_record Phase 3: open conflict does NOT block live (NOVA_PROP_GATES_ENABLED=false)
- validate_and_record Phase 3: reconciliation fields in req dict
- validate_and_record Phase 3: trace_v2 includes Phase 3 fields
- validate_and_record Phase 3: reconcile module error is non-blocking

All broker calls are mocked — no real Alpaca connections made.
All file I/O is isolated to tmp_path.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


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


def _make_position(symbol='QQQ', side='long', qty=10.0) -> dict:
    return {'symbol': symbol, 'side': side, 'qty': qty,
            'avg_entry_price': 400.0, 'market_value': 4000.0, 'unrealized_pl': 100.0, 'raw': {}}


def _make_order(symbol='QQQ', side='sell', order_type='stop',
                stop_price=390.0, order_class='', legs=None) -> dict:
    return {
        'id': 'ord-001', 'symbol': symbol, 'side': side, 'type': order_type,
        'qty': 10.0, 'status': 'new', 'limit_price': None,
        'stop_price': stop_price, 'order_class': order_class,
        'legs': legs or [], 'raw': {},
    }


def _make_journal_trade(ticker='QQQ', direction='LONG', qty=10.0) -> dict:
    return {'ticker': ticker, 'direction': direction, 'qty': qty,
            'outcome': 'OPEN', 'source': 'NOVA_AUTO'}


# ── Import reconcile module ───────────────────────────────────────────────────

import services.execution_reconcile as rcl


# ── 1. check_open_position_conflict ──────────────────────────────────────────

def test_no_broker_positions_passes_conflict_check():
    result = rcl.check_open_position_conflict('MNQ', 'LONG', 'QQQ', broker_positions=[])
    assert result['conflict'] is False
    assert result['rejection_code'] is None


def test_same_instrument_triggers_conflict():
    positions = [_make_position('QQQ', 'long', 10.0)]
    result = rcl.check_open_position_conflict('MNQ', 'LONG', 'QQQ', positions)
    assert result['conflict'] is True
    assert result['rejection_code'] == 'REJECTED_OPEN_POSITION'
    assert result['existing_side'] == 'long'
    assert result['existing_qty']  == 10.0


def test_opposite_direction_same_instrument_still_conflicts():
    """Any position = conflict, regardless of direction."""
    positions = [_make_position('QQQ', 'short', 5.0)]
    result = rcl.check_open_position_conflict('MNQ', 'LONG', 'QQQ', positions)
    assert result['conflict'] is True
    assert result['rejection_code'] == 'REJECTED_OPEN_POSITION'


def test_different_etf_does_not_conflict():
    """SPY position should not block a MNQ (→QQQ) signal."""
    positions = [_make_position('SPY', 'long', 20.0)]
    result = rcl.check_open_position_conflict('MNQ', 'LONG', 'QQQ', positions)
    assert result['conflict'] is False


def test_mes_routes_to_spy_for_conflict_check():
    positions = [_make_position('SPY', 'long', 20.0)]
    result = rcl.check_open_position_conflict('MES', 'LONG', 'SPY', positions)
    assert result['conflict'] is True


# ── 2. Broker reader failures ─────────────────────────────────────────────────

def test_get_broker_positions_safe_returns_empty_on_failure():
    with patch('services.execution_reconcile._get_alpaca_client',
               return_value=(None, 'no credentials')):
        result = rcl.get_broker_positions_safe()
    assert result == []


def test_get_broker_orders_safe_returns_empty_on_failure():
    with patch('services.execution_reconcile._get_alpaca_client',
               return_value=(None, 'no credentials')):
        result = rcl.get_broker_orders_safe()
    assert result == []


def test_get_broker_positions_safe_catches_api_exception():
    mock_client = MagicMock()
    mock_client.get_all_positions.side_effect = RuntimeError('API error')
    with patch('services.execution_reconcile._get_alpaca_client',
               return_value=(mock_client, None)):
        result = rcl.get_broker_positions_safe()
    assert result == []


# ── 3. reconcile_execution_state ─────────────────────────────────────────────

def test_empty_broker_and_journal_returns_insufficient_data():
    recon = rcl.reconcile_execution_state(
        execution_request={'symbol': 'MNQ', 'direction': 'LONG'},
        broker_positions=[], broker_orders=[], journal_trades=[],
    )
    assert recon['reconciliation_status'] == 'INSUFFICIENT_DATA'
    assert recon['broker_position_found'] is False
    assert recon['journal_trade_found'] is False


def test_position_with_stop_and_target_returns_synced():
    positions = [_make_position('QQQ', 'long', 10.0)]
    orders    = [
        _make_order('QQQ', 'sell', 'stop',  stop_price=390.0),
        _make_order('QQQ', 'sell', 'limit', stop_price=None),
    ]
    orders[1]['limit_price'] = 420.0
    journal   = [_make_journal_trade('QQQ', 'LONG', 10.0)]

    recon = rcl.reconcile_execution_state(
        execution_request={'symbol': 'MNQ', 'direction': 'LONG'},
        broker_positions=positions, broker_orders=orders, journal_trades=journal,
    )
    assert recon['reconciliation_status'] == 'SYNCED'
    assert recon['protective_stop_found']   is True
    assert recon['protective_target_found'] is True


def test_position_without_stop_returns_unprotected():
    positions = [_make_position('QQQ', 'long', 10.0)]
    journal   = [_make_journal_trade('QQQ', 'LONG', 10.0)]

    recon = rcl.reconcile_execution_state(
        execution_request={'symbol': 'MNQ', 'direction': 'LONG'},
        broker_positions=positions, broker_orders=[], journal_trades=journal,
    )
    assert recon['reconciliation_status'] == 'UNPROTECTED_POSITION'
    assert recon['protective_stop_found'] is False


def test_journal_missing_when_broker_has_position():
    positions = [_make_position('QQQ', 'long', 10.0)]
    orders    = [_make_order('QQQ', 'sell', 'stop')]  # protected

    recon = rcl.reconcile_execution_state(
        execution_request={'symbol': 'MNQ', 'direction': 'LONG'},
        broker_positions=positions, broker_orders=orders, journal_trades=[],
    )
    assert recon['reconciliation_status'] == 'JOURNAL_MISSING'
    assert recon['broker_position_found']  is True
    assert recon['journal_trade_found']    is False


def test_journal_missing_and_unprotected_returns_unprotected():
    """UNPROTECTED takes priority over JOURNAL_MISSING."""
    positions = [_make_position('QQQ', 'long', 10.0)]

    recon = rcl.reconcile_execution_state(
        execution_request={'symbol': 'MNQ', 'direction': 'LONG'},
        broker_positions=positions, broker_orders=[], journal_trades=[],
    )
    assert recon['reconciliation_status'] == 'UNPROTECTED_POSITION'


def test_broker_position_missing_when_journal_is_open():
    journal = [_make_journal_trade('QQQ', 'LONG', 10.0)]

    recon = rcl.reconcile_execution_state(
        execution_request={'symbol': 'MNQ', 'direction': 'LONG'},
        broker_positions=[], broker_orders=[], journal_trades=journal,
    )
    assert recon['reconciliation_status'] == 'BROKER_POSITION_MISSING'
    assert recon['journal_trade_found']   is True
    assert recon['broker_position_found'] is False
    assert recon['errors']  # error was recorded


def test_size_mismatch_detected():
    positions = [_make_position('QQQ', 'long', 5.0)]   # broker has 5
    orders    = [_make_order('QQQ', 'sell', 'stop')]
    journal   = [_make_journal_trade('QQQ', 'LONG', 10.0)]  # journal says 10

    recon = rcl.reconcile_execution_state(
        execution_request={'symbol': 'MNQ', 'direction': 'LONG'},
        broker_positions=positions, broker_orders=orders, journal_trades=journal,
    )
    assert recon['reconciliation_status'] == 'SIZE_MISMATCH'
    assert recon['size_match'] is False


def test_direction_mismatch_detected():
    positions = [_make_position('QQQ', 'short', 10.0)]  # broker SHORT
    orders    = [_make_order('QQQ', 'buy', 'stop')]       # protective buy stop
    journal   = [_make_journal_trade('QQQ', 'LONG', 10.0)]  # journal says LONG

    recon = rcl.reconcile_execution_state(
        execution_request={'symbol': 'MNQ', 'direction': 'LONG'},
        broker_positions=positions, broker_orders=orders, journal_trades=journal,
    )
    assert recon['reconciliation_status'] == 'DIRECTION_MISMATCH'
    assert recon['direction_match'] is False


# ── 4. detect_protective_orders ───────────────────────────────────────────────

def test_detect_stop_for_long_position():
    positions = [_make_position('QQQ', 'long', 10.0)]
    orders    = [_make_order('QQQ', 'sell', 'stop', stop_price=390.0)]
    result    = rcl.detect_protective_orders('QQQ', positions, orders)
    assert result['position_found'] is True
    assert result['stop_found']     is True
    assert result['unprotected']    is False


def test_bracket_order_is_fully_protected():
    positions = [_make_position('QQQ', 'long', 10.0)]
    orders    = [_make_order('QQQ', 'sell', 'market', order_class='bracket')]
    result    = rcl.detect_protective_orders('QQQ', positions, orders)
    assert result['bracket_detected'] is True
    assert result['stop_found']       is True
    assert result['target_found']     is True
    assert result['unprotected']      is False


def test_no_orders_means_unprotected():
    positions = [_make_position('QQQ', 'long', 10.0)]
    result    = rcl.detect_protective_orders('QQQ', positions, [])
    assert result['unprotected'] is True
    assert result['stop_found']  is False


def test_wrong_side_order_does_not_count_as_protection():
    """A buy stop for a long position is not a protective order."""
    positions = [_make_position('QQQ', 'long', 10.0)]
    orders    = [_make_order('QQQ', 'buy', 'stop')]   # wrong side for long
    result    = rcl.detect_protective_orders('QQQ', positions, orders)
    assert result['unprotected'] is True


def test_no_position_returns_clean_result():
    result = rcl.detect_protective_orders('QQQ', [], [])
    assert result['position_found'] is False
    assert result['unprotected']    is False


# ── 5. validate_and_record — open position conflict in dry-run ────────────────

def test_open_position_conflict_blocks_in_dry_run(tmp_path):
    er = _isolated_er(tmp_path)
    positions = [_make_position('QQQ', 'long', 10.0)]

    with patch('services.execution_reconcile.get_broker_positions_safe', return_value=positions), \
         patch('services.execution_reconcile.get_broker_orders_safe', return_value=[]), \
         patch('services.execution_reconcile.get_open_journal_trades_safe', return_value=[]):
        req = er.validate_and_record(
            symbol='MNQ', direction='LONG', setup_type='PROS_LONG',
            signal_generated_at=_past_iso(5),
            dry_run_override=True,
        )

    assert req['final_status'] == 'REJECTED_OPEN_POSITION'
    assert req['open_position_check']['conflict'] is True
    assert req['broker_called'] is False


def test_open_position_conflict_does_not_block_live_by_default(tmp_path):
    """NOVA_PROP_GATES_ENABLED defaults false — conflict logged but live path continues."""
    er = _isolated_er(tmp_path)
    positions = [_make_position('QQQ', 'long', 10.0)]

    with patch('services.execution_reconcile.get_broker_positions_safe', return_value=positions), \
         patch('services.execution_reconcile.get_broker_orders_safe', return_value=[]), \
         patch('services.execution_reconcile.get_open_journal_trades_safe', return_value=[]), \
         patch.dict('os.environ', {'NOVA_PROP_GATES_ENABLED': 'false'}):
        req = er.validate_and_record(
            symbol='MNQ', direction='LONG', setup_type='PROS_LONG',
            signal_generated_at=_past_iso(5),
            dry_run_override=False,
        )

    assert req['final_status'] == er.STATUS_RECEIVED
    assert req['open_position_check']['conflict'] is True   # logged
    assert req['broker_called'] is False


def test_open_position_conflict_blocks_live_when_gates_enabled(tmp_path):
    er = _isolated_er(tmp_path)
    positions = [_make_position('QQQ', 'long', 10.0)]

    with patch('services.execution_reconcile.get_broker_positions_safe', return_value=positions), \
         patch('services.execution_reconcile.get_broker_orders_safe', return_value=[]), \
         patch('services.execution_reconcile.get_open_journal_trades_safe', return_value=[]), \
         patch.dict('os.environ', {'NOVA_PROP_GATES_ENABLED': 'true'}):
        req = er.validate_and_record(
            symbol='MNQ', direction='LONG', setup_type='PROS_LONG',
            signal_generated_at=_past_iso(5),
            dry_run_override=False,
        )

    assert req['final_status'] == 'REJECTED_OPEN_POSITION'


# ── 6. validate_and_record — reconciliation fields present ───────────────────

def test_validate_and_record_has_phase3_fields(tmp_path):
    er = _isolated_er(tmp_path)

    with patch('services.execution_reconcile.get_broker_positions_safe', return_value=[]), \
         patch('services.execution_reconcile.get_broker_orders_safe', return_value=[]), \
         patch('services.execution_reconcile.get_open_journal_trades_safe', return_value=[]):
        req = er.validate_and_record(
            symbol='MNQ', direction='LONG', setup_type='PROS_LONG',
            signal_generated_at=_past_iso(5),
            dry_run_override=True,
        )

    assert 'open_position_check'          in req
    assert 'broker_positions_count'       in req
    assert 'broker_orders_count'          in req
    assert 'journal_open_trades_count'    in req
    assert 'reconciliation_status'        in req
    assert 'protective_stop_found'        in req
    assert 'protective_target_found'      in req
    assert 'unprotected_position_warning' in req
    assert 'reconciliation_warnings'      in req
    assert 'reconciliation_errors'        in req


def test_unprotected_position_warning_logged(tmp_path):
    er = _isolated_er(tmp_path)
    positions = [_make_position('QQQ', 'long', 10.0)]
    journal   = [_make_journal_trade('QQQ', 'LONG', 10.0)]

    with patch('services.execution_reconcile.get_broker_positions_safe', return_value=positions), \
         patch('services.execution_reconcile.get_broker_orders_safe', return_value=[]), \
         patch('services.execution_reconcile.get_open_journal_trades_safe', return_value=journal):
        req = er.validate_and_record(
            symbol='MNQ', direction='LONG', setup_type='PROS_LONG',
            signal_generated_at=_past_iso(5),
            dry_run_override=True,
        )

    # Conflict gate fires first (blocks in dry-run) but unprotected is also recorded
    assert req['unprotected_position_warning'] is True
    warnings_text = ' '.join(req.get('validation_warnings', []))
    assert 'UNPROTECTED' in warnings_text or 'unprotected' in warnings_text.lower()


# ── 7. trace_v2 includes Phase 3 fields ──────────────────────────────────────

def test_trace_v2_includes_phase3_fields(tmp_path):
    er = _isolated_er(tmp_path)

    with patch('services.execution_reconcile.get_broker_positions_safe', return_value=[]), \
         patch('services.execution_reconcile.get_broker_orders_safe', return_value=[]), \
         patch('services.execution_reconcile.get_open_journal_trades_safe', return_value=[]):
        req = er.validate_and_record(
            symbol='MNQ', direction='LONG', setup_type='PROS_LONG',
            signal_generated_at=_past_iso(5),
            dry_run_override=True,
        )

    entries = er.get_trace_v2_recent(5)
    assert entries, 'trace_v2 must have at least one entry'
    latest = entries[0]
    assert 'open_position_check'       in latest
    assert 'reconciliation_status'     in latest
    assert 'protective_stop_found'     in latest
    assert 'broker_positions_count'    in latest


# ── 8. Phase 3 error is non-blocking ─────────────────────────────────────────

def test_phase3_reconcile_error_does_not_crash(tmp_path):
    er = _isolated_er(tmp_path)

    with patch.dict('sys.modules', {'services.execution_reconcile': None}):
        req = er.validate_and_record(
            symbol='MNQ', direction='LONG', setup_type='PROS_LONG',
            signal_generated_at=_past_iso(5),
            dry_run_override=True,
        )

    # Should not raise; Phase 3 error recorded as warning
    assert isinstance(req, dict)
    assert 'final_status' in req
    warnings = ' '.join(req.get('validation_warnings', []))
    assert 'Phase 3' in warnings or 'reconcile' in warnings.lower()


# ── 9. Dry-run never calls broker write methods ───────────────────────────────

def test_dry_run_never_calls_broker_write_methods(tmp_path):
    er = _isolated_er(tmp_path)
    cancel_calls  = []
    submit_calls  = []
    flatten_calls = []

    mock_client = MagicMock()
    mock_client.get_all_positions.return_value = []
    mock_client.get_orders.return_value = []
    mock_client.cancel_order_by_id.side_effect = lambda *a: cancel_calls.append(a)
    mock_client.submit_order.side_effect         = lambda *a, **k: submit_calls.append((a, k))
    mock_client.close_all_positions.side_effect  = lambda *a: flatten_calls.append(a)

    with patch('services.execution_reconcile._get_alpaca_client',
               return_value=(mock_client, None)):
        er.validate_and_record(
            symbol='MNQ', direction='LONG', setup_type='PROS_LONG',
            signal_generated_at=_past_iso(5),
            dry_run_override=True,
        )

    assert cancel_calls  == [], 'cancel_order_by_id must not be called in Phase 3'
    assert submit_calls  == [], 'submit_order must not be called in Phase 3'
    assert flatten_calls == [], 'close_all_positions must not be called in Phase 3'


# ── 10. normalize helpers ─────────────────────────────────────────────────────

def test_normalize_position_record_from_dict():
    pos = {'symbol': 'qqq', 'side': 'long', 'qty': '10',
           'avg_entry_price': '400.00', 'market_value': '4000', 'unrealized_pl': '100'}
    result = rcl.normalize_position_record(pos)
    assert result['symbol'] == 'QQQ'
    assert result['side']   == 'long'
    assert result['qty']    == 10.0


def test_normalize_order_record_from_dict():
    order = {'id': 'abc', 'symbol': 'qqq', 'side': 'sell', 'type': 'stop',
             'qty': '10', 'status': 'new', 'limit_price': None,
             'stop_price': '390', 'order_class': '', 'legs': []}
    result = rcl.normalize_order_record(order)
    assert result['symbol']      == 'QQQ'
    assert result['type']        == 'stop'
    assert result['stop_price']  == 390.0
    assert result['legs']        == []
