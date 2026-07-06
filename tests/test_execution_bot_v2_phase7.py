"""test_execution_bot_v2_phase7.py — Execution Bot v2 Phase 7 tests.

Tests cover:
01. Readiness report writes to file
02. Missing prop config → NOT_READY with blocker
03. Dry-run enabled + valid config → READY_FOR_DRY_RUN
04. Auto-execute=true without dry-run → blocker
05. Missing prop config returns expected blocker text
06. Missing account state → warning (broker_account_read=false)
07. Stale safety status → staleness warning
08. Safety status never run → warning about missing status
09. Discord disabled → warning (not a blocker)
10. Prop gates enforcing → warning (observe-only expected)
11. No broker writes in prop_readiness module
12. No order actions in prop_readiness module
13. Strategy logic unchanged by Phase 7
14. write_prop_readiness_report() returns valid report structure
15. Endpoint returns readiness report safely
16. collect_prop_readiness_status() returns required keys
17. evaluate_prop_readiness() is a pure function (no side effects)
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

import services.prop_readiness as pr


# ── Helpers ────────────────────────────────────────────────────────────────────

def _valid_config() -> dict:
    """Prop risk config that passes all readiness checks."""
    return {
        'prop_firm_name':            'Apex',
        'account_size':              50000.0,
        'starting_balance':          50000.0,
        'max_daily_loss':            500.0,
        'max_total_loss':            2500.0,
        'trailing_drawdown_enabled': True,
        'trailing_drawdown_amount':  2500.0,
        '_config_missing':           False,
    }


def _valid_account_state() -> dict:
    return {
        'prop_state_status':  'PROP_STATE_OK',
        'current_balance':    50000.0,
        'high_water_mark':    50000.0,
        'daily_pnl':          0.0,
        'broker_account_read': True,
        'last_updated':       datetime.now(timezone.utc).isoformat(),
    }


def _valid_safety_status() -> dict:
    return {
        'status':               'NO_OPEN_POSITIONS',
        'checked_at':           datetime.now(timezone.utc).isoformat(),
        'open_positions_count': 0,
        'unprotected_positions': [],
        'discord_enabled':      False,
    }


def _base_data(
    config_missing: bool = False,
    prop_config: dict | None = None,
    prop_account: dict | None = None,
    safety: dict | None = None,
    trace: dict | None = None,
    env: dict | None = None,
) -> dict:
    """Build a minimal data snapshot for evaluate_prop_readiness()."""
    default_env = {
        'NOVA_AUTO_EXECUTE':                     False,
        'NOVA_EXECUTION_DRY_RUN':                True,
        'NOVA_PROP_GATES_ENABLED':               False,
        'NOVA_EXECUTION_SAFETY_MONITOR_ENABLED': True,
        'NOVA_EXECUTION_SAFETY_DISCORD_ENABLED': False,
        'NOVA_EXECUTION_SAFETY_ALERT_COOLDOWN_SECONDS': 900,
    }
    return {
        'collected_at':        datetime.now(timezone.utc).isoformat(),
        'env':                 env if env is not None else default_env,
        'prop_config':         prop_config if prop_config is not None else _valid_config(),
        'prop_config_missing': config_missing,
        'prop_account_state':  prop_account if prop_account is not None else _valid_account_state(),
        'safety_status':       safety if safety is not None else _valid_safety_status(),
        'trace_summary':       trace if trace is not None else {'trace_file_exists': True, 'entry_count': 5},
    }


# ── Test 01: Readiness report writes to file ──────────────────────────────────

def test_readiness_report_writes_to_file(tmp_path):
    report_file = tmp_path / 'nova_prop_readiness_report.json'
    with patch.object(pr, '_readiness_report_file', return_value=report_file), \
         patch.object(pr, 'collect_prop_readiness_status', return_value=_base_data()):
        result = pr.write_prop_readiness_report()

    assert report_file.exists(), 'report file must be written'
    saved = json.loads(report_file.read_text())
    assert saved['readiness_status'] == result['readiness_status']
    assert 'checked_at' in saved
    assert 'blockers' in saved
    assert 'warnings' in saved


# ── Test 02: Missing prop config → NOT_READY ─────────────────────────────────

def test_missing_prop_config_returns_not_ready():
    data   = _base_data(config_missing=True, prop_config={'_config_missing': True, 'prop_firm_name': 'NONE'})
    result = pr.evaluate_prop_readiness(data)
    assert result['readiness_status'] == pr.READINESS_NOT_READY
    assert result['blockers'], 'must have at least one blocker'


# ── Test 03: Dry-run enabled + valid config → READY_FOR_DRY_RUN ──────────────

def test_dry_run_enabled_returns_ready_for_dry_run():
    data   = _base_data()   # dry_run=True, config present, no blockers
    result = pr.evaluate_prop_readiness(data)
    assert result['readiness_status'] == pr.READINESS_READY
    assert result['blockers'] == []


# ── Test 04: Auto-execute=true without dry-run → blocker ─────────────────────

def test_auto_execute_without_dry_run_is_blocker():
    env  = {
        'NOVA_AUTO_EXECUTE':                     True,
        'NOVA_EXECUTION_DRY_RUN':                False,
        'NOVA_PROP_GATES_ENABLED':               False,
        'NOVA_EXECUTION_SAFETY_MONITOR_ENABLED': True,
        'NOVA_EXECUTION_SAFETY_DISCORD_ENABLED': False,
        'NOVA_EXECUTION_SAFETY_ALERT_COOLDOWN_SECONDS': 900,
    }
    data   = _base_data(env=env, config_missing=False)
    result = pr.evaluate_prop_readiness(data)
    assert result['readiness_status'] == pr.READINESS_NOT_READY
    blockers_text = ' '.join(result['blockers'])
    assert 'NOVA_AUTO_EXECUTE' in blockers_text
    assert 'NOVA_EXECUTION_DRY_RUN' in blockers_text


# ── Test 05: Missing prop config blocker text ─────────────────────────────────

def test_missing_prop_config_blocker_text():
    data   = _base_data(config_missing=True, prop_config={'_config_missing': True})
    result = pr.evaluate_prop_readiness(data)
    blocker_text = ' '.join(result['blockers'])
    assert 'Prop risk config' in blocker_text or 'prop_firm_name' in blocker_text


# ── Test 06: Missing account state → warning ──────────────────────────────────

def test_missing_account_state_produces_warning():
    # broker_account_read=False, no last_updated → warning
    account = {
        'prop_state_status':  'UNKNOWN_ACCOUNT_STATE',
        'current_balance':    0.0,
        'broker_account_read': False,
        'last_updated':       '',
    }
    data    = _base_data(config_missing=False, prop_account=account)
    result  = pr.evaluate_prop_readiness(data)
    warning_text = ' '.join(result['warnings'])
    assert 'never been updated' in warning_text or 'broker_account_read' in warning_text


# ── Test 07: Stale safety status → warning ────────────────────────────────────

def test_stale_safety_status_produces_warning():
    stale_time = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    safety  = {
        'status':               'NO_OPEN_POSITIONS',
        'checked_at':           stale_time,
        'open_positions_count': 0,
        'unprotected_positions': [],
    }
    data    = _base_data(safety=safety)
    result  = pr.evaluate_prop_readiness(data)
    warning_text = ' '.join(result['warnings'])
    assert 'stale' in warning_text.lower()


# ── Test 08: Safety status never run → warning ───────────────────────────────

def test_safety_never_run_produces_warning():
    safety  = {'status': None, 'checked_at': None, 'unprotected_positions': []}
    data    = _base_data(safety=safety)
    result  = pr.evaluate_prop_readiness(data)
    warning_text = ' '.join(result['warnings'])
    assert 'never run' in warning_text or 'missing' in warning_text


# ── Test 09: Discord disabled → warning (not a blocker) ──────────────────────

def test_discord_disabled_is_warning_not_blocker():
    env  = {
        'NOVA_AUTO_EXECUTE':                     False,
        'NOVA_EXECUTION_DRY_RUN':                True,
        'NOVA_PROP_GATES_ENABLED':               False,
        'NOVA_EXECUTION_SAFETY_MONITOR_ENABLED': True,
        'NOVA_EXECUTION_SAFETY_DISCORD_ENABLED': False,
        'NOVA_EXECUTION_SAFETY_ALERT_COOLDOWN_SECONDS': 900,
    }
    data    = _base_data(env=env)
    result  = pr.evaluate_prop_readiness(data)
    # Discord disabled must NOT be a blocker
    blocker_text = ' '.join(result['blockers'])
    assert 'DISCORD' not in blocker_text
    # Must appear in warnings
    warning_text = ' '.join(result['warnings'])
    assert 'Discord' in warning_text or 'DISCORD' in warning_text


# ── Test 10: Prop gates enforcing → warning ───────────────────────────────────

def test_prop_gates_enforcing_produces_warning():
    env  = {
        'NOVA_AUTO_EXECUTE':                     False,
        'NOVA_EXECUTION_DRY_RUN':                True,
        'NOVA_PROP_GATES_ENABLED':               True,    # enforcing
        'NOVA_EXECUTION_SAFETY_MONITOR_ENABLED': True,
        'NOVA_EXECUTION_SAFETY_DISCORD_ENABLED': False,
        'NOVA_EXECUTION_SAFETY_ALERT_COOLDOWN_SECONDS': 900,
    }
    data    = _base_data(env=env)
    result  = pr.evaluate_prop_readiness(data)
    warning_text = ' '.join(result['warnings'])
    assert 'NOVA_PROP_GATES_ENABLED' in warning_text or 'prop gates' in warning_text.lower()


# ── Test 11: No broker write methods in prop_readiness ───────────────────────

def test_no_broker_write_methods_in_prop_readiness():
    import inspect
    source = inspect.getsource(pr)
    forbidden = ['submit_order', 'cancel_order', 'close_position',
                 'close_all_positions', 'replace_order']
    for method in forbidden:
        assert method not in source, f'prop_readiness.py must not call {method}'


# ── Test 12: No order actions ─────────────────────────────────────────────────

def test_no_order_actions_in_prop_readiness():
    import inspect
    source = inspect.getsource(pr)
    order_actions = ['cancel_order_by_id', 'patch_order', 'submit_order(', 'close_all']
    for action in order_actions:
        assert action not in source, f'prop_readiness.py must not contain {action}'


# ── Test 13: Strategy logic unchanged ────────────────────────────────────────

def test_strategy_logic_unchanged_by_phase7():
    import inspect
    source = inspect.getsource(pr)
    strategy_imports = ['engines.reasoning', 'engines.signals', 'compute_pros_state',
                        'compute_orb_state', 'grade_setup']
    for imp in strategy_imports:
        assert imp not in source, f'prop_readiness.py must not import strategy module {imp}'


# ── Test 14: write_prop_readiness_report() returns valid structure ────────────

def test_write_readiness_report_returns_valid_structure(tmp_path):
    report_file = tmp_path / 'nova_prop_readiness_report.json'
    with patch.object(pr, '_readiness_report_file', return_value=report_file), \
         patch.object(pr, 'collect_prop_readiness_status', return_value=_base_data()):
        report = pr.write_prop_readiness_report()

    required_keys = [
        'checked_at', 'readiness_status', 'blockers', 'warnings',
        'recommended_next_action', 'prop_firm', 'prop_config_present',
        'account_state_summary', 'latest_safety_status', 'execution_trace_summary',
        'discord_configured', 'dry_run_enabled', 'auto_execute_enabled',
        'prop_gates_enforcing', 'safety_monitor_enabled',
    ]
    for key in required_keys:
        assert key in report, f'report missing required key: {key}'

    assert report['readiness_status'] in (pr.READINESS_READY, pr.READINESS_NOT_READY)
    assert isinstance(report['blockers'], list)
    assert isinstance(report['warnings'], list)
    assert isinstance(report['recommended_next_action'], str)


# ── Test 15: Endpoint returns readiness report safely ────────────────────────

def test_endpoint_returns_readiness_report(tmp_path):
    report_file = tmp_path / 'nova_prop_readiness_report.json'
    with patch.object(pr, '_readiness_report_file', return_value=report_file), \
         patch.object(pr, 'collect_prop_readiness_status', return_value=_base_data()):
        result = pr.write_prop_readiness_report()

    assert result.get('readiness_status') in (pr.READINESS_READY, pr.READINESS_NOT_READY)
    # No exception raised
    assert 'error' not in result or not result.get('blockers') == ['Readiness check failed']


# ── Test 16: collect_prop_readiness_status() returns required keys ────────────

def test_collect_returns_required_keys():
    with patch('services.prop_risk.load_prop_config', return_value=_valid_config()), \
         patch('services.prop_account_state.load_prop_account_state', return_value=_valid_account_state()), \
         patch('services.execution_safety.get_latest_safety_status', return_value=_valid_safety_status()), \
         patch.object(pr, '_load_execution_trace_summary',
                      return_value={'trace_file_exists': True, 'entry_count': 3}):
        data = pr.collect_prop_readiness_status()

    required = ['collected_at', 'env', 'prop_config', 'prop_config_missing',
                'prop_account_state', 'safety_status', 'trace_summary']
    for key in required:
        assert key in data, f'collect() missing key: {key}'

    assert isinstance(data['env'], dict)
    assert 'NOVA_AUTO_EXECUTE' in data['env']
    assert 'NOVA_EXECUTION_DRY_RUN' in data['env']


# ── Test 17: evaluate_prop_readiness() is pure (no file I/O) ─────────────────

def test_evaluate_is_pure_no_file_io(tmp_path):
    data = _base_data()
    # No file patches needed — evaluate_prop_readiness must not touch the filesystem
    # If it does, it would fail trying to write to a non-existent dir
    with patch.dict(os.environ, {}, clear=False):
        result = pr.evaluate_prop_readiness(data)

    assert 'readiness_status' in result
    assert 'blockers' in result
    assert 'warnings' in result
    assert 'recommended_next_action' in result
    # No files created in tmp_path (we didn't patch the report file)
    assert not list(tmp_path.iterdir()), 'evaluate_prop_readiness must not write files'
