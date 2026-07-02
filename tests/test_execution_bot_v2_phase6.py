"""test_execution_bot_v2_phase6.py — Execution Bot v2 Phase 6 tests.

Tests cover:
01. Default state loads safely (no file)
02. Missing state file does not crash
03. State saves and loads round-trip
04. Daily reset on new trading day
05. HWM updates when balance increases
06. HWM does not decrease when balance falls
07. Trailing drawdown threshold computed correctly
08. Trailing drawdown warning at ≤25% buffer
09. Trailing drawdown breached status
10. Daily loss warning triggers
11. Daily loss breached status
12. Total loss warning triggers
13. Total loss breached status
14. Broker account read failure → UNKNOWN_ACCOUNT_STATE
15. Safety status includes prop_account_summary key
16. No broker write methods called during prop account update
17. Prop warning alert sent when near breach (Discord mock)

Note: All patches on services.execution_reconcile.* use string-form to survive
Phase 4's module re-import in _isolated_er(). Prop module patches use patch.object.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch, MagicMock, call
from datetime import datetime, timezone

import pytest

import services.prop_account_state as pas
import services.execution_safety as es

# ── Helpers ───────────────────────────────────────────────────────────────────

def _mock_account(equity: float = 50_000.0) -> MagicMock:
    """Return a mock Alpaca account object."""
    acc = MagicMock()
    acc.model_dump.return_value = {
        'equity':          str(equity),
        'last_equity':     str(equity - 100),
        'portfolio_value': str(equity),
        'buying_power':    str(equity * 4),
    }
    return acc


def _mock_client(equity: float = 50_000.0) -> MagicMock:
    client = MagicMock()
    client.get_account.return_value = _mock_account(equity)
    return client


def _file_patch(tmp_path: Path):
    return patch.object(
        pas, '_prop_account_state_file',
        return_value=tmp_path / 'prop_account_state.json',
    )


def _client_patch(equity: float = 50_000.0):
    client = _mock_client(equity)
    return patch(
        'services.execution_reconcile._get_alpaca_client',
        return_value=(client, None),
    ), client


def _safety_file_patches(tmp_path: Path):
    return (
        patch.object(es, '_safety_status_file', return_value=tmp_path / 'ss.json'),
        patch.object(es, '_safety_log_file',    return_value=tmp_path / 'sl.json'),
    )


def _broker_patches(positions=None, orders=None, journal=None):
    return (
        patch('services.execution_reconcile.get_broker_positions_safe',
              return_value=positions or []),
        patch('services.execution_reconcile.get_broker_orders_safe',
              return_value=orders or []),
        patch('services.execution_reconcile.get_open_journal_trades_safe',
              return_value=journal or []),
    )


# ── 01. Default state loads safely ───────────────────────────────────────────

def test_default_state_loads_safely(tmp_path):
    with _file_patch(tmp_path):
        state = pas.load_prop_account_state()
    assert isinstance(state, dict)
    assert 'prop_state_status' in state
    assert 'current_balance'   in state
    assert 'high_water_mark'   in state
    assert state['prop_state_status'] == pas.UNKNOWN_ACCOUNT_STATE


# ── 02. Missing state file does not crash ────────────────────────────────────

def test_missing_state_file_does_not_crash(tmp_path):
    with _file_patch(tmp_path):
        state = pas.load_prop_account_state()
    assert isinstance(state, dict)
    assert state['current_balance'] == 0.0


# ── 03. State saves and loads round-trip ─────────────────────────────────────

def test_state_saves_and_loads_round_trip(tmp_path):
    with _file_patch(tmp_path):
        state = pas.load_prop_account_state()
        state['current_balance'] = 52_000.0
        state['high_water_mark'] = 52_000.0
        state['prop_firm_name']  = 'Apex'
        pas.save_prop_account_state(state)
        loaded = pas.load_prop_account_state()
    assert loaded['current_balance'] == 52_000.0
    assert loaded['high_water_mark'] == 52_000.0
    assert loaded['prop_firm_name']  == 'Apex'


# ── 04. Daily reset on new trading day ───────────────────────────────────────

def test_daily_reset_on_new_trading_day():
    state = pas._default_state()
    state['trading_day']         = '2026-01-01'   # stale date
    state['current_balance']     = 51_000.0
    state['daily_pnl']           = 500.0
    state['trade_count_today']   = 3

    with patch('services.prop_account_state._today_et', return_value='2026-01-02'):
        updated = pas.reset_daily_state_if_new_day(state)

    assert updated['trading_day']       == '2026-01-02'
    assert updated['daily_pnl']         == 0.0
    assert updated['trade_count_today'] == 0
    assert updated['daily_start_balance'] == 51_000.0   # snapshotted from current


def test_no_daily_reset_when_same_day():
    state = pas._default_state()
    state['trading_day']  = '2026-06-30'
    state['daily_pnl']    = 250.0

    with patch('services.prop_account_state._today_et', return_value='2026-06-30'):
        updated = pas.reset_daily_state_if_new_day(state)

    assert updated['daily_pnl']   == 250.0   # unchanged
    assert updated['trading_day'] == '2026-06-30'


# ── 05. HWM updates when balance increases ───────────────────────────────────

def test_hwm_updates_when_balance_increases(tmp_path):
    with _file_patch(tmp_path):
        state = pas.load_prop_account_state()
        state['starting_balance']    = 50_000.0
        state['account_size']        = 50_000.0
        state['high_water_mark']     = 50_000.0
        state['daily_start_balance'] = 50_000.0
        state['trading_day']         = '2026-06-30'
        pas.save_prop_account_state(state)

    client_patch, client = _client_patch(equity=51_500.0)
    with _file_patch(tmp_path), client_patch, \
         patch('services.prop_account_state._today_et', return_value='2026-06-30'):
        result = pas.update_prop_account_state_from_broker()

    assert result['current_balance']  == 51_500.0
    assert result['high_water_mark']  == 51_500.0
    assert result['broker_account_read'] is True


# ── 06. HWM does not decrease when balance falls ─────────────────────────────

def test_hwm_never_decreases(tmp_path):
    with _file_patch(tmp_path):
        state = pas.load_prop_account_state()
        state['starting_balance']    = 50_000.0
        state['account_size']        = 50_000.0
        state['high_water_mark']     = 52_000.0   # previous peak
        state['daily_start_balance'] = 50_000.0
        state['trading_day']         = '2026-06-30'
        pas.save_prop_account_state(state)

    client_patch, _ = _client_patch(equity=49_000.0)   # below HWM
    with _file_patch(tmp_path), client_patch, \
         patch('services.prop_account_state._today_et', return_value='2026-06-30'):
        result = pas.update_prop_account_state_from_broker()

    assert result['high_water_mark'] == 52_000.0   # must stay at 52000
    assert result['current_balance'] == 49_000.0


# ── 07. Trailing drawdown threshold computed correctly ───────────────────────

def test_trailing_drawdown_threshold_trailing():
    state = pas._default_state()
    state['trailing_drawdown_enabled'] = True
    state['trailing_drawdown_amount']  = 2_500.0
    state['trailing_drawdown_type']    = 'trailing'
    state['high_water_mark']           = 52_000.0
    state['current_balance']           = 51_000.0

    result = pas.compute_trailing_drawdown_state(state)

    assert result['trailing_drawdown_threshold'] == 49_500.0   # 52000 - 2500
    assert result['trailing_drawdown_remaining'] == 1_500.0    # 51000 - 49500
    assert result['trailing_drawdown_status']    == pas.PROP_STATE_OK


def test_trailing_drawdown_threshold_static():
    state = pas._default_state()
    state['trailing_drawdown_enabled'] = True
    state['trailing_drawdown_amount']  = 2_500.0
    state['trailing_drawdown_type']    = 'static'
    state['starting_balance']          = 50_000.0
    state['high_water_mark']           = 52_000.0
    state['current_balance']           = 51_000.0

    result = pas.compute_trailing_drawdown_state(state)

    assert result['trailing_drawdown_threshold'] == 47_500.0   # 50000 - 2500
    assert result['trailing_drawdown_remaining'] == 3_500.0    # 51000 - 47500


# ── 08. Trailing drawdown WARNING at ≤25% buffer ────────────────────────────

def test_trailing_drawdown_warning_at_25pct():
    state = pas._default_state()
    state['trailing_drawdown_enabled'] = True
    state['trailing_drawdown_amount']  = 2_500.0
    state['trailing_drawdown_type']    = 'trailing'
    state['high_water_mark']           = 52_000.0
    # remaining = current - (hwm - dd_amount) = 49_500 + 625 - 49500 = 625
    # 625 <= 2500 * 0.25 = 625 → exactly at threshold → WARNING
    state['current_balance']           = 49_500.0 + 625.0   # = 50_125

    result = pas.compute_trailing_drawdown_state(state)

    assert result['trailing_drawdown_status'] == pas.PROP_TRAILING_DRAWDOWN_WARNING


# ── 09. Trailing drawdown BREACHED ───────────────────────────────────────────

def test_trailing_drawdown_breached():
    state = pas._default_state()
    state['trailing_drawdown_enabled'] = True
    state['trailing_drawdown_amount']  = 2_500.0
    state['trailing_drawdown_type']    = 'trailing'
    state['high_water_mark']           = 52_000.0
    state['current_balance']           = 49_400.0   # below threshold (49500)

    result = pas.compute_trailing_drawdown_state(state)

    assert result['trailing_drawdown_status']    == pas.PROP_TRAILING_DRAWDOWN_BREACHED
    assert result['trailing_drawdown_remaining'] < 0


# ── 10. Daily loss WARNING ───────────────────────────────────────────────────

def test_daily_loss_warning():
    state = pas._default_state()
    state['max_daily_loss'] = 500.0
    state['daily_pnl']      = -376.0   # 124 remaining = 24.8% of 500 → WARNING

    result = pas.compute_daily_loss_state(state)

    assert result['daily_loss_status']    == pas.PROP_DAILY_LOSS_WARNING
    assert result['daily_loss_remaining'] == pytest.approx(124.0)


# ── 11. Daily loss BREACHED ──────────────────────────────────────────────────

def test_daily_loss_breached():
    state = pas._default_state()
    state['max_daily_loss'] = 500.0
    state['daily_pnl']      = -501.0   # over limit

    result = pas.compute_daily_loss_state(state)

    assert result['daily_loss_status']    == pas.PROP_DAILY_LOSS_BREACHED
    assert result['daily_loss_remaining'] < 0


# ── 12. Total loss WARNING ───────────────────────────────────────────────────

def test_total_loss_warning():
    state = pas._default_state()
    state['max_total_loss']  = 2_500.0
    state['starting_balance'] = 50_000.0
    # floor = 50000 - 2500 = 47500; remaining = 48125 - 47500 = 625
    # 625 <= 2500 * 0.25 = 625 → WARNING
    state['current_balance'] = 48_125.0

    result = pas.compute_total_loss_state(state)

    assert result['total_loss_status']    == pas.PROP_TOTAL_LOSS_WARNING
    assert result['total_loss_remaining'] == pytest.approx(625.0)


# ── 13. Total loss BREACHED ──────────────────────────────────────────────────

def test_total_loss_breached():
    state = pas._default_state()
    state['max_total_loss']   = 2_500.0
    state['starting_balance'] = 50_000.0
    state['current_balance']  = 47_400.0   # below floor (47500)

    result = pas.compute_total_loss_state(state)

    assert result['total_loss_status']    == pas.PROP_TOTAL_LOSS_BREACHED
    assert result['total_loss_remaining'] < 0


# ── 14. Broker read failure → UNKNOWN_ACCOUNT_STATE ─────────────────────────

def test_broker_read_failure_gives_unknown_state(tmp_path):
    with _file_patch(tmp_path), \
         patch('services.prop_account_state._get_alpaca_account_safe', return_value=None), \
         patch('services.prop_account_state._today_et', return_value='2026-06-30'):
        result = pas.update_prop_account_state_from_broker()

    assert result['prop_state_status']   == pas.UNKNOWN_ACCOUNT_STATE
    assert result['broker_account_read'] is False


# ── 15. Safety status includes prop_account_summary ─────────────────────────

def test_safety_status_includes_prop_summary(tmp_path):
    es.clear_cooldown_state()
    pas.clear_prop_cooldown_state()

    sf1, sf2 = _safety_file_patches(tmp_path)
    b1, b2, b3 = _broker_patches()

    mock_prop_state = {
        'current_balance':             50_000.0,
        'high_water_mark':             50_000.0,
        'trailing_drawdown_threshold': 47_500.0,
        'trailing_drawdown_remaining': 2_500.0,
        'daily_pnl':                   0.0,
        'daily_loss_remaining':        500.0,
        'prop_state_status':           pas.PROP_STATE_OK,
        'broker_account_read':         True,
    }

    with sf1, sf2, b1, b2, b3, \
         patch.object(pas, 'update_prop_account_state_from_broker',
                      return_value=mock_prop_state), \
         patch.object(pas, 'check_and_send_prop_alerts',
                      return_value={'alerts_sent': [], 'alerts_suppressed': []}):
        result = es.run_execution_safety_check()

    assert 'prop_account_summary' in result
    ps = result['prop_account_summary']
    assert ps['prop_state_status']    == pas.PROP_STATE_OK
    assert ps['current_balance']      == 50_000.0
    assert ps['broker_account_read']  is True
    assert 'starting_balance'         in ps
    assert 'total_loss_remaining'     in ps


# ── 16. No broker write methods called during prop update ───────────────────

def test_no_broker_write_methods_called_in_prop_update(tmp_path):
    cancel_calls  = []
    submit_calls  = []
    flatten_calls = []

    client = _mock_client(equity=50_000.0)
    client.cancel_order_by_id.side_effect  = lambda *a: cancel_calls.append(a)
    client.submit_order.side_effect         = lambda *a, **k: submit_calls.append(1)
    client.close_all_positions.side_effect  = lambda *a: flatten_calls.append(1)

    with _file_patch(tmp_path), \
         patch('services.execution_reconcile._get_alpaca_client',
               return_value=(client, None)), \
         patch('services.prop_account_state._today_et', return_value='2026-06-30'):
        pas.update_prop_account_state_from_broker()

    assert cancel_calls  == [], 'cancel_order_by_id must NOT be called'
    assert submit_calls  == [], 'submit_order must NOT be called'
    assert flatten_calls == [], 'close_all_positions must NOT be called'


# ── 17. Prop warning alert sent when near breach ─────────────────────────────

def test_prop_warning_alert_sent_when_near_breach(tmp_path):
    pas.clear_prop_cooldown_state()

    # State near trailing drawdown breach (warning)
    state = pas._default_state()
    state['trailing_drawdown_enabled'] = True
    state['trailing_drawdown_amount']  = 2_500.0
    state['trailing_drawdown_type']    = 'trailing'
    state['high_water_mark']           = 52_000.0
    state['current_balance']           = 50_125.0   # 625 remaining → WARNING
    state['trailing_drawdown_status']  = pas.PROP_TRAILING_DRAWDOWN_WARNING
    state['daily_loss_status']         = pas.PROP_STATE_OK
    state['total_loss_status']         = pas.PROP_STATE_OK
    state['prop_state_status']         = pas.PROP_TRAILING_DRAWDOWN_WARNING

    mock_send = MagicMock(return_value={'ok': True})
    with patch.object(pas, 'send_prop_alert_discord', mock_send):
        result = pas.check_and_send_prop_alerts(state, cooldown_seconds=0)

    mock_send.assert_called_once()
    assert len(result['alerts_sent']) == 1
    assert result['alerts_sent'][0]['alert_key'] == pas.PROP_TRAILING_DRAWDOWN_WARNING

    pas.clear_prop_cooldown_state()


# ── 18. Endpoint returns latest state safely ─────────────────────────────────

def test_get_latest_prop_account_state_from_file(tmp_path):
    """get_latest_prop_account_state() reads from file first (no API call)."""
    saved = {
        'current_balance':  51_500.0,
        'high_water_mark':  51_500.0,
        'prop_state_status': pas.PROP_STATE_OK,
        'last_updated':     '2026-06-30T14:00:00+00:00',
    }
    file_path = tmp_path / 'prop_account_state.json'
    file_path.write_text(json.dumps(saved), encoding='utf-8')

    client_patch, client = _client_patch(equity=99_999.0)
    with patch.object(pas, '_prop_account_state_file', return_value=file_path), \
         client_patch:
        result = pas.get_latest_prop_account_state()

    # Must have returned file data — broker was never needed
    assert result['current_balance']   == 51_500.0
    assert result['prop_state_status'] == pas.PROP_STATE_OK
    client.get_account.assert_not_called()   # file-first: no API call


def test_get_latest_prop_account_state_live_fallback(tmp_path):
    """get_latest_prop_account_state() falls back to live read when file missing."""
    file_path = tmp_path / 'prop_account_state.json'   # does NOT exist yet

    client_patch, _ = _client_patch(equity=50_000.0)
    with patch.object(pas, '_prop_account_state_file', return_value=file_path), \
         client_patch, \
         patch('services.prop_account_state._today_et', return_value='2026-06-30'):
        result = pas.get_latest_prop_account_state()

    assert result.get('current_balance') == 50_000.0
    assert result.get('broker_account_read') is True


# ── 19. Strategy logic unchanged by prop module ──────────────────────────────

def test_strategy_logic_unchanged_by_prop_update(tmp_path):
    """
    update_prop_account_state_from_broker() must never touch strategy/reasoning/
    signal-processing modules. Patch the critical ones to raise if called.
    """
    def _must_not_call(*a, **k):
        raise AssertionError('Strategy module called from prop state updater')

    client_patch, _ = _client_patch(equity=50_000.0)
    with patch.object(pas, '_prop_account_state_file',
                      return_value=tmp_path / 'state.json'), \
         client_patch, \
         patch('services.prop_account_state._today_et', return_value='2026-06-30'), \
         patch.dict('sys.modules', {
             'engines.reasoning': type('M', (), {'__getattr__': _must_not_call})(),
             'engines.signals':   type('M', (), {'__getattr__': _must_not_call})(),
         }):
        result = pas.update_prop_account_state_from_broker()

    # If we reach here, no strategy module was called
    assert result['broker_account_read'] is True
    assert 'prop_state_status' in result
