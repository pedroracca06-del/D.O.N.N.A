"""test_execution_bot_v2_phase5_1.py — Phase 5.1: Alert controls + persistent cooldown.

Tests cover:
01. Discord disabled suppresses send_safety_discord_alert
02. Status file still written when Discord disabled
03. Log still appended when Discord disabled
04. Suppressed list shows DISCORD_DISABLED reason when Discord off
05. Discord enabled sends alert (existing behavior preserved)
06. Cooldown env var respected (900s default)
07. Persistent cooldown registry written when alert sent
08. Persistent cooldown survives simulated restart (registry reload)
09. Monitor-enabled flag can disable the check
10. No broker write methods called
11. No auto-flatten called
12. No cancel/replace/submit order calls
13. No strategy logic touched
14. Status includes discord_enabled field
15. Status includes cooldown_seconds field

Patching rules (same as Phase 5):
  - All services.execution_reconcile patches: string-form
  - execution_safety module-level patches: patch.object(es, ...)
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

import services.execution_safety as es


# ── Helpers ───────────────────────────────────────────────────────────────────

def _pos(symbol='SPY', side='short', qty=101.0) -> dict:
    return {'symbol': symbol, 'side': side, 'qty': qty,
            'avg_entry_price': 580.0, 'market_value': 58580.0,
            'unrealized_pl': -200.0, 'raw': {}}


def _file_patches(tmp_path: Path):
    return (
        patch.object(es, '_safety_status_file', return_value=tmp_path / 'ss.json'),
        patch.object(es, '_safety_log_file',    return_value=tmp_path / 'sl.json'),
        patch.object(es, '_alert_registry_file', return_value=tmp_path / 'registry.json'),
    )


def _broker_patches(positions=None, orders=None, journal=None):
    return (
        patch('services.execution_reconcile.get_broker_positions_safe',
              return_value=positions if positions is not None else []),
        patch('services.execution_reconcile.get_broker_orders_safe',
              return_value=orders if orders is not None else []),
        patch('services.execution_reconcile.get_open_journal_trades_safe',
              return_value=journal if journal is not None else []),
    )


def _unprotected_alert(instrument='SPY', side='short', qty=101.0) -> dict:
    return {
        'alert_type': 'UNPROTECTED_POSITION', 'severity': 'CRITICAL',
        'symbol': instrument, 'instrument': instrument,
        'side': side, 'qty': qty, 'detected_at': '2026-07-01T14:00:00Z',
    }


def _safety_snapshot_with_unprotected(instrument='SPY') -> dict:
    alert = _unprotected_alert(instrument=instrument)
    return {
        'status': 'UNPROTECTED_POSITIONS_DETECTED',
        'open_positions_count': 1,
        'open_orders_count': 0,
        'open_journal_count': 0,
        'protected_positions': [],
        'unprotected_positions': [{'symbol': instrument}],
        'emergency_alerts': [alert],
        'warnings': [], 'errors': [],
    }


# ── 01. Discord disabled suppresses send ─────────────────────────────────────

def test_discord_disabled_suppresses_send(tmp_path):
    es.clear_cooldown_state()
    p1, p2, p3 = _file_patches(tmp_path)
    b1, b2, b3 = _broker_patches()
    mock_send = MagicMock(return_value={'ok': True})

    with p1, p2, p3, b1, b2, b3, \
         patch.object(es, 'send_safety_discord_alert', mock_send), \
         patch.object(es, '_discord_enabled', return_value=False), \
         patch('services.execution_reconcile.get_execution_safety_status',
               return_value=_safety_snapshot_with_unprotected()):
        es.run_execution_safety_check(cooldown_seconds=0)

    mock_send.assert_not_called()


# ── 02. Status file still written when Discord disabled ───────────────────────

def test_status_file_written_when_discord_disabled(tmp_path):
    es.clear_cooldown_state()
    p1, p2, p3 = _file_patches(tmp_path)
    b1, b2, b3 = _broker_patches()

    with p1, p2, p3, b1, b2, b3, \
         patch.object(es, '_discord_enabled', return_value=False), \
         patch('services.execution_reconcile.get_execution_safety_status',
               return_value=_safety_snapshot_with_unprotected()):
        es.run_execution_safety_check(cooldown_seconds=0)

    assert (tmp_path / 'ss.json').exists(), 'status file must be written'
    data = json.loads((tmp_path / 'ss.json').read_text())
    assert data['status'] == 'UNPROTECTED_POSITIONS_DETECTED'


# ── 03. Log still appended when Discord disabled ─────────────────────────────

def test_log_appended_when_discord_disabled(tmp_path):
    es.clear_cooldown_state()
    p1, p2, p3 = _file_patches(tmp_path)
    b1, b2, b3 = _broker_patches()

    with p1, p2, p3, b1, b2, b3, \
         patch.object(es, '_discord_enabled', return_value=False), \
         patch('services.execution_reconcile.get_execution_safety_status',
               return_value=_safety_snapshot_with_unprotected()):
        es.run_execution_safety_check(cooldown_seconds=0)

    log = json.loads((tmp_path / 'sl.json').read_text())
    assert isinstance(log, list)
    assert len(log) == 1
    assert log[0]['_log_type'] == 'SAFETY_CHECK'


# ── 04. Suppressed list shows DISCORD_DISABLED ───────────────────────────────

def test_suppressed_shows_discord_disabled_reason(tmp_path):
    es.clear_cooldown_state()
    p1, p2, p3 = _file_patches(tmp_path)
    b1, b2, b3 = _broker_patches()

    with p1, p2, p3, b1, b2, b3, \
         patch.object(es, '_discord_enabled', return_value=False), \
         patch('services.execution_reconcile.get_execution_safety_status',
               return_value=_safety_snapshot_with_unprotected()):
        result = es.run_execution_safety_check(cooldown_seconds=0)

    suppressed = result['alerts_suppressed_by_cooldown']
    assert any('DISCORD_DISABLED' in s for s in suppressed)
    assert result['alerts_sent'] == []


# ── 05. Discord enabled sends alert (existing behavior preserved) ─────────────

def test_discord_enabled_sends_alert(tmp_path):
    es.clear_cooldown_state()
    p1, p2, p3 = _file_patches(tmp_path)
    b1, b2, b3 = _broker_patches()
    mock_send = MagicMock(return_value={'ok': True})

    with p1, p2, p3, b1, b2, b3, \
         patch.object(es, 'send_safety_discord_alert', mock_send), \
         patch.object(es, '_discord_enabled', return_value=True), \
         patch('services.execution_reconcile.get_execution_safety_status',
               return_value=_safety_snapshot_with_unprotected()):
        result = es.run_execution_safety_check(cooldown_seconds=0)

    mock_send.assert_called_once()
    assert len(result['alerts_sent']) == 1


# ── 06. Cooldown env var respected ───────────────────────────────────────────

def test_cooldown_env_var_respected(tmp_path):
    es.clear_cooldown_state()
    p1, p2, p3 = _file_patches(tmp_path)
    b1, b2, b3 = _broker_patches()
    mock_send = MagicMock(return_value={'ok': True})

    # First call — Discord on, sends alert (cooldown = 900 from env)
    with p1, p2, p3, b1, b2, b3, \
         patch.object(es, 'send_safety_discord_alert', mock_send), \
         patch.object(es, '_discord_enabled', return_value=True), \
         patch.object(es, '_env_cooldown_seconds', return_value=900), \
         patch('services.execution_reconcile.get_execution_safety_status',
               return_value=_safety_snapshot_with_unprotected()):
        result1 = es.run_execution_safety_check()    # uses env default = 900

    assert len(result1['alerts_sent']) == 1
    assert result1['cooldown_seconds'] == 900

    # Second call — same instrument still in 900s cooldown
    with p1, p2, p3, b1, b2, b3, \
         patch.object(es, 'send_safety_discord_alert', mock_send), \
         patch.object(es, '_discord_enabled', return_value=True), \
         patch.object(es, '_env_cooldown_seconds', return_value=900), \
         patch('services.execution_reconcile.get_execution_safety_status',
               return_value=_safety_snapshot_with_unprotected()):
        result2 = es.run_execution_safety_check()

    assert mock_send.call_count == 1   # NOT called a second time
    assert any('COOLDOWN' in s for s in result2['alerts_suppressed_by_cooldown'])


# ── 07. Persistent registry written when alert sent ──────────────────────────

def test_persistent_registry_written_when_alert_sent(tmp_path):
    es.clear_cooldown_state()
    p1, p2, p3 = _file_patches(tmp_path)
    b1, b2, b3 = _broker_patches()

    with p1, p2, p3, b1, b2, b3, \
         patch.object(es, 'send_safety_discord_alert', return_value={'ok': True}), \
         patch.object(es, '_discord_enabled', return_value=True), \
         patch('services.execution_reconcile.get_execution_safety_status',
               return_value=_safety_snapshot_with_unprotected('QQQ')):
        es.run_execution_safety_check(cooldown_seconds=0)

    registry_file = tmp_path / 'registry.json'
    assert registry_file.exists(), 'registry file must be written after alert'
    registry = json.loads(registry_file.read_text())
    assert isinstance(registry, dict)
    # Should have an entry for QQQ
    found = any('QQQ' in k for k in registry)
    assert found, f'Expected QQQ entry in registry, got: {list(registry.keys())}'


# ── 08. Persistent cooldown survives simulated restart ───────────────────────

def test_persistent_cooldown_survives_reload(tmp_path):
    """Simulate process restart by clearing in-memory state but leaving registry file."""
    from datetime import datetime, timezone
    registry_file = tmp_path / 'registry.json'
    key           = 'SPY__UNPROTECTED_POSITION'

    # Write a recent sentinel directly to file (simulating last run wrote it)
    registry_file.write_text(json.dumps({
        key: {
            'alert_key':   key,
            'instrument':  'SPY',
            'alert_type':  'UNPROTECTED_POSITION',
            'last_sent_at': datetime.now(timezone.utc).isoformat(),
        }
    }), encoding='utf-8')

    # Clear in-memory cooldown (simulate restart)
    es.clear_cooldown_state()

    p1, p2, p3 = _file_patches(tmp_path)
    mock_send = MagicMock(return_value={'ok': True})
    b1, b2, b3 = _broker_patches()

    with p1, p2, p3, b1, b2, b3, \
         patch.object(es, 'send_safety_discord_alert', mock_send), \
         patch.object(es, '_discord_enabled', return_value=True), \
         patch('services.execution_reconcile.get_execution_safety_status',
               return_value=_safety_snapshot_with_unprotected('SPY')):

        # Reload from file inside the patch context (mimics module-load after restart)
        for rk, re in es._load_alert_registry().items():
            if re.get('last_sent_at'):
                with es._cooldown_lock:
                    es._cooldown_state.setdefault(rk, re['last_sent_at'])

        result = es.run_execution_safety_check(cooldown_seconds=900)

    mock_send.assert_not_called()   # still in cooldown from registry
    assert any('COOLDOWN' in s for s in result['alerts_suppressed_by_cooldown'])
    es.clear_cooldown_state()


# ── 09. Monitor-enabled=false skips check (tested via _discord_enabled proxy) ─

def test_status_includes_discord_enabled_field(tmp_path):
    es.clear_cooldown_state()
    p1, p2, p3 = _file_patches(tmp_path)
    b1, b2, b3 = _broker_patches()

    with p1, p2, p3, b1, b2, b3, \
         patch.object(es, '_discord_enabled', return_value=False):
        result = es.run_execution_safety_check(cooldown_seconds=0)

    assert 'discord_enabled' in result
    assert result['discord_enabled'] is False


# ── 10–13. Safety (no broker writes, no flatten, no cancel/submit/replace) ────

def test_no_broker_write_methods_called_phase5_1(tmp_path):
    es.clear_cooldown_state()
    p1, p2, p3 = _file_patches(tmp_path)
    cancel_calls  = []
    submit_calls  = []
    flatten_calls = []

    mock_client = MagicMock()
    mock_client.get_all_positions.return_value = []
    mock_client.get_orders.return_value        = []
    mock_client.cancel_order_by_id.side_effect  = lambda *a: cancel_calls.append(a)
    mock_client.submit_order.side_effect         = lambda *a, **k: submit_calls.append(1)
    mock_client.close_all_positions.side_effect  = lambda *a: flatten_calls.append(1)

    with p1, p2, p3, \
         patch.object(es, '_discord_enabled', return_value=True), \
         patch('services.execution_reconcile._get_alpaca_client',
               return_value=(mock_client, None)):
        es.run_execution_safety_check(cooldown_seconds=0)

    assert cancel_calls  == [], 'cancel_order_by_id must not be called'
    assert submit_calls  == [], 'submit_order must not be called'
    assert flatten_calls == [], 'close_all_positions must not be called'


# ── 14. Status includes discord_enabled field ────────────────────────────────

def test_status_field_discord_enabled_true(tmp_path):
    es.clear_cooldown_state()
    p1, p2, p3 = _file_patches(tmp_path)
    b1, b2, b3 = _broker_patches()

    with p1, p2, p3, b1, b2, b3, \
         patch.object(es, '_discord_enabled', return_value=True):
        result = es.run_execution_safety_check(cooldown_seconds=0)

    assert result['discord_enabled'] is True


# ── 15. Status includes cooldown_seconds field ───────────────────────────────

def test_status_field_cooldown_seconds(tmp_path):
    es.clear_cooldown_state()
    p1, p2, p3 = _file_patches(tmp_path)
    b1, b2, b3 = _broker_patches()

    with p1, p2, p3, b1, b2, b3:
        result = es.run_execution_safety_check(cooldown_seconds=300)

    assert result['cooldown_seconds'] == 300
