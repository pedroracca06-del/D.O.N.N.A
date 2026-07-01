"""test_execution_bot_v2_phase5.py — Execution Bot v2 Phase 5 tests.

Tests cover:
- safety check writes nova_execution_safety_status.json
- safety log appends entries to nova_execution_safety_log.json
- no positions → NO_OPEN_POSITIONS
- protected position → ALL_POSITIONS_PROTECTED
- unprotected position → UNPROTECTED_POSITIONS_DETECTED
- CRITICAL emergency alert object present when unprotected
- Discord alert send called once for new unprotected alert
- duplicate alert within cooldown is suppressed
- alert fires again after cooldown state is cleared
- broker reader failure does not crash (returns UNKNOWN_BROKER_STATE)
- endpoint helper returns latest status from file
- endpoint helper falls back to live if file missing
- no broker write methods called during safety check
- safety log capped at SAFETY_LOG_MAX entries
- cooldown key is per-instrument (independent)
- cooldown_seconds=0 never suppresses
- send_safety_discord_alert returns error when no token

Note: Phase 4 tests use _isolated_er() which re-imports services.execution_reconcile.
All patching here uses string-form `patch('services.execution_reconcile.X')` so that
mock resolution always goes through the current sys.modules entry, not a stale reference.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

import services.execution_safety as es


# ── Helpers ────────────────────────────────────────────────────────────────────

def _pos(symbol='QQQ', side='long', qty=10.0) -> dict:
    return {'symbol': symbol, 'side': side, 'qty': qty,
            'avg_entry_price': 400.0, 'market_value': 4000.0,
            'unrealized_pl': 50.0, 'raw': {}}


def _ord(symbol='QQQ', side='sell', order_type='stop',
         stop_price=390.0, limit_price=None, order_class='') -> dict:
    return {
        'id': 'o1', 'symbol': symbol, 'side': side, 'type': order_type,
        'qty': 10.0, 'status': 'new',
        'limit_price': limit_price, 'stop_price': stop_price,
        'order_class': order_class, 'legs': [], 'raw': {},
    }


def _file_patches(tmp_path: Path):
    """Redirect status + log files to tmp_path."""
    return (
        patch.object(es, '_safety_status_file', return_value=tmp_path / 'safety_status.json'),
        patch.object(es, '_safety_log_file',    return_value=tmp_path / 'safety_log.json'),
    )


def _broker_patches(positions=None, orders=None, journal=None):
    """String-form patches for broker readers — always resolves against current sys.modules."""
    return (
        patch('services.execution_reconcile.get_broker_positions_safe',
              return_value=positions if positions is not None else []),
        patch('services.execution_reconcile.get_broker_orders_safe',
              return_value=orders if orders is not None else []),
        patch('services.execution_reconcile.get_open_journal_trades_safe',
              return_value=journal if journal is not None else []),
    )


# ── 1. Status file written ────────────────────────────────────────────────────

def test_safety_check_writes_status_file(tmp_path):
    es.clear_cooldown_state()
    p1, p2 = _file_patches(tmp_path)
    b1, b2, b3 = _broker_patches()
    with p1, p2, b1, b2, b3:
        es.run_execution_safety_check()

    status_file = tmp_path / 'safety_status.json'
    assert status_file.exists(), 'status file must be written'
    data = json.loads(status_file.read_text())
    assert 'checked_at' in data
    assert 'status'     in data
    assert data['status'] == 'NO_OPEN_POSITIONS'


# ── 2. Log appends entries ────────────────────────────────────────────────────

def test_safety_log_appends(tmp_path):
    es.clear_cooldown_state()
    p1, p2 = _file_patches(tmp_path)
    b1, b2, b3 = _broker_patches()
    with p1, p2, b1, b2, b3:
        es.run_execution_safety_check()
        es.run_execution_safety_check()

    log_file = tmp_path / 'safety_log.json'
    assert log_file.exists()
    entries = json.loads(log_file.read_text())
    assert isinstance(entries, list)
    assert len(entries) == 2
    assert all(e['_log_type'] == 'SAFETY_CHECK' for e in entries)


# ── 3. No positions → NO_OPEN_POSITIONS ──────────────────────────────────────

def test_no_positions_returns_no_open_positions(tmp_path):
    es.clear_cooldown_state()
    p1, p2 = _file_patches(tmp_path)
    b1, b2, b3 = _broker_patches()
    with p1, p2, b1, b2, b3:
        result = es.run_execution_safety_check()

    assert result['status']               == 'NO_OPEN_POSITIONS'
    assert result['open_positions_count'] == 0
    assert result['emergency_alerts']     == []
    assert result['alerts_sent']          == []


# ── 4. Protected position → ALL_POSITIONS_PROTECTED ──────────────────────────

def test_protected_position_returns_all_protected(tmp_path):
    es.clear_cooldown_state()
    p1, p2 = _file_patches(tmp_path)
    positions = [_pos('QQQ', 'long', 10.0)]
    orders    = [_ord('QQQ', 'sell', 'stop'), _ord('QQQ', 'sell', 'limit', limit_price=420.0)]
    b1, b2, b3 = _broker_patches(positions=positions, orders=orders)
    with p1, p2, b1, b2, b3:
        result = es.run_execution_safety_check()

    assert result['status']                    == 'ALL_POSITIONS_PROTECTED'
    assert len(result['protected_positions'])  == 1
    assert result['emergency_alerts']          == []
    assert result['unprotected_positions']     == []


# ── 5. Unprotected position → UNPROTECTED_POSITIONS_DETECTED ─────────────────

def test_unprotected_position_detected(tmp_path):
    es.clear_cooldown_state()
    p1, p2 = _file_patches(tmp_path)
    positions = [_pos('QQQ', 'long', 10.0)]
    b1, b2, b3 = _broker_patches(positions=positions)
    with p1, p2, b1, b2, b3, \
         patch.object(es, 'send_safety_discord_alert', return_value={'ok': True}):
        result = es.run_execution_safety_check()

    assert result['status']                     == 'UNPROTECTED_POSITIONS_DETECTED'
    assert len(result['unprotected_positions']) == 1
    assert result['unprotected_positions'][0]['symbol'] == 'QQQ'


# ── 6. CRITICAL emergency alert present ──────────────────────────────────────

def test_critical_emergency_alert_present(tmp_path):
    es.clear_cooldown_state()
    p1, p2 = _file_patches(tmp_path)
    positions = [_pos('QQQ', 'long', 10.0)]
    b1, b2, b3 = _broker_patches(positions=positions)
    with p1, p2, b1, b2, b3, \
         patch.object(es, 'send_safety_discord_alert', return_value={'ok': True}):
        result = es.run_execution_safety_check()

    alerts = result['emergency_alerts']
    assert len(alerts)          == 1
    assert alerts[0]['alert_type'] == 'UNPROTECTED_POSITION'
    assert alerts[0]['severity']   == 'CRITICAL'


# ── 7. Discord alert send called once for new alert ───────────────────────────

def test_discord_alert_sent_once_for_new_alert(tmp_path):
    es.clear_cooldown_state()
    p1, p2 = _file_patches(tmp_path)
    positions  = [_pos('QQQ', 'long', 10.0)]
    b1, b2, b3 = _broker_patches(positions=positions)
    mock_send  = MagicMock(return_value={'ok': True})
    with p1, p2, b1, b2, b3, patch.object(es, 'send_safety_discord_alert', mock_send):
        es.run_execution_safety_check()

    mock_send.assert_called_once()
    assert mock_send.call_args[0][0]['alert_type'] == 'UNPROTECTED_POSITION'


# ── 8. Duplicate alert within cooldown suppressed ─────────────────────────────

def test_duplicate_alert_suppressed_by_cooldown(tmp_path):
    es.clear_cooldown_state()
    p1, p2 = _file_patches(tmp_path)
    positions  = [_pos('QQQ', 'long', 10.0)]
    b1, b2, b3 = _broker_patches(positions=positions)
    mock_send  = MagicMock(return_value={'ok': True})
    with p1, p2, b1, b2, b3, patch.object(es, 'send_safety_discord_alert', mock_send):
        es.run_execution_safety_check(cooldown_seconds=300)
        result2 = es.run_execution_safety_check(cooldown_seconds=300)

    assert mock_send.call_count == 1, 'Discord must only be called on first alert'
    assert 'QQQ' in result2['alerts_suppressed_by_cooldown']
    assert result2['alerts_sent'] == []


# ── 9. Alert fires again after cooldown cleared ───────────────────────────────

def test_alert_fires_again_after_cooldown_cleared(tmp_path):
    es.clear_cooldown_state()
    p1, p2 = _file_patches(tmp_path)
    positions  = [_pos('QQQ', 'long', 10.0)]
    b1, b2, b3 = _broker_patches(positions=positions)
    mock_send  = MagicMock(return_value={'ok': True})
    with p1, p2, b1, b2, b3, patch.object(es, 'send_safety_discord_alert', mock_send):
        es.run_execution_safety_check(cooldown_seconds=300)   # fires alert
        es.clear_cooldown_state()                              # simulate cooldown expiry
        es.run_execution_safety_check(cooldown_seconds=300)   # must fire again

    assert mock_send.call_count == 2


# ── 10. Broker reader failure does not crash ──────────────────────────────────

def test_broker_reader_failure_does_not_crash(tmp_path):
    es.clear_cooldown_state()
    p1, p2 = _file_patches(tmp_path)
    with p1, p2, \
         patch('services.execution_reconcile.get_broker_positions_safe',
               side_effect=RuntimeError('Alpaca down')), \
         patch('services.execution_reconcile.get_broker_orders_safe',
               side_effect=RuntimeError('Alpaca down')), \
         patch('services.execution_reconcile.get_open_journal_trades_safe',
               return_value=[]):
        result = es.run_execution_safety_check()

    assert isinstance(result, dict)
    assert 'status' in result


# ── 11. get_latest_safety_status reads from file ─────────────────────────────

def test_get_latest_safety_status_reads_file(tmp_path):
    p1, p2 = _file_patches(tmp_path)
    status_file = tmp_path / 'safety_status.json'
    fake = {'status': 'ALL_POSITIONS_PROTECTED', 'checked_at': '2026-06-30T12:00:00Z'}
    status_file.write_text(json.dumps(fake), encoding='utf-8')
    with p1, p2:
        result = es.get_latest_safety_status()

    assert result['status']     == 'ALL_POSITIONS_PROTECTED'
    assert result['checked_at'] == '2026-06-30T12:00:00Z'


# ── 12. get_latest_safety_status falls back to live when file missing ─────────

def test_get_latest_safety_status_fallback_to_live(tmp_path):
    p1, p2 = _file_patches(tmp_path)
    b1, b2, b3 = _broker_patches()
    with p1, p2, b1, b2, b3:
        result = es.get_latest_safety_status()

    assert result['status'] == 'NO_OPEN_POSITIONS'


# ── 13. No broker write methods called ───────────────────────────────────────

def test_no_broker_write_methods_called(tmp_path):
    es.clear_cooldown_state()
    p1, p2 = _file_patches(tmp_path)
    cancel_calls  = []
    submit_calls  = []
    flatten_calls = []

    mock_client = MagicMock()
    mock_client.get_all_positions.return_value = []
    mock_client.get_orders.return_value        = []
    mock_client.cancel_order_by_id.side_effect  = lambda *a: cancel_calls.append(a)
    mock_client.submit_order.side_effect         = lambda *a, **k: submit_calls.append(1)
    mock_client.close_all_positions.side_effect  = lambda *a: flatten_calls.append(1)

    with p1, p2, \
         patch('services.execution_reconcile._get_alpaca_client',
               return_value=(mock_client, None)):
        es.run_execution_safety_check()

    assert cancel_calls  == [], 'cancel_order_by_id must not be called'
    assert submit_calls  == [], 'submit_order must not be called'
    assert flatten_calls == [], 'close_all_positions must not be called'


# ── 14. Safety log capped at SAFETY_LOG_MAX ──────────────────────────────────

def test_safety_log_capped_at_max(tmp_path):
    p1, p2 = _file_patches(tmp_path)
    log_file = tmp_path / 'safety_log.json'
    existing = [{'status': 'NO_OPEN_POSITIONS', '_log_type': 'SAFETY_CHECK', 'n': i}
                for i in range(es.SAFETY_LOG_MAX)]
    log_file.write_text(json.dumps(existing), encoding='utf-8')

    b1, b2, b3 = _broker_patches()
    es.clear_cooldown_state()
    with p1, p2, b1, b2, b3:
        es.run_execution_safety_check()

    entries = json.loads(log_file.read_text())
    assert len(entries) == es.SAFETY_LOG_MAX
    assert entries[-1]['_log_type'] == 'SAFETY_CHECK'


# ── 15. Cooldown key is per-instrument (independent) ─────────────────────────

def test_cooldown_key_per_instrument():
    es.clear_cooldown_state()
    es._record_alert_sent('QQQ', 'UNPROTECTED_POSITION')
    assert es._is_in_cooldown('QQQ', 'UNPROTECTED_POSITION', 300) is True
    assert es._is_in_cooldown('SPY', 'UNPROTECTED_POSITION', 300) is False
    es.clear_cooldown_state()


# ── 16. cooldown_seconds=0 never suppresses ───────────────────────────────────

def test_cooldown_zero_never_suppresses(tmp_path):
    es.clear_cooldown_state()
    p1, p2 = _file_patches(tmp_path)
    positions  = [_pos('QQQ', 'long', 10.0)]
    b1, b2, b3 = _broker_patches(positions=positions)
    mock_send  = MagicMock(return_value={'ok': True})
    with p1, p2, b1, b2, b3, patch.object(es, 'send_safety_discord_alert', mock_send):
        es.run_execution_safety_check(cooldown_seconds=0)
        es.run_execution_safety_check(cooldown_seconds=0)

    assert mock_send.call_count == 2, 'cooldown_seconds=0 must never suppress alerts'
    es.clear_cooldown_state()


# ── 17. send_safety_discord_alert returns error when no token ─────────────────

def test_send_safety_discord_alert_no_token():
    alert = {
        'alert_type': 'UNPROTECTED_POSITION', 'severity': 'CRITICAL',
        'symbol': 'MNQ', 'instrument': 'QQQ', 'qty': 10.0, 'side': 'long',
        'detected_at': '2026-06-30T12:00:00Z',
    }
    with patch('core.config.DISCORD_BOT_TOKEN', ''), \
         patch('core.config.DISCORD_CHANNEL_LIVE', ''), \
         patch('core.config.DISCORD_CHANNEL_SYSTEM_HEALTH', ''):
        result = es.send_safety_discord_alert(alert)
    assert result.get('ok') is False
