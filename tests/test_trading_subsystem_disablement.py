"""
test_trading_subsystem_disablement.py — controlled retirement (2026-07-16).

Background: Pedro ordered a full controlled retirement of the legacy trading/
execution subsystem (indicator, ORB/PROS/ICT/IB, Harvey, Execution Bot v2) --
see nova_knowledge_core/TRADING_SUBSYSTEM_RETIREMENT_AUDIT.md and
TRADING_SUBSYSTEM_DISABLEMENT.md. NOVA_TRADING_SUBSYSTEM_ENABLED is the new
authoritative, top-level flag (default false) checked directly inside every
broker-write function in services/execution.py -- independent of, and before,
NOVA_AUTO_EXECUTE -- so no caller (webhook, monitor.py, execution_bridge.py,
a future consumer) can place, modify, cancel, or close a trade while it is
false, even if NOVA_AUTO_EXECUTE=true.

Note: conftest.py's autouse `_trading_subsystem_enabled_for_existing_tests`
fixture defaults this flag to True for the in-process test environment so
pre-existing execution tests keep exercising real business logic. Every test
below that needs to prove the *disabled* (production-default) behavior
explicitly overrides that back to False, or runs in a subprocess with a
deliberately clean environment that the fixture never touches.

This file does not touch Journal, Market/News, or NOVA Assistant behavior --
tests 11-12 confirm those still import and run cleanly with trading disabled.

Run:  python -m pytest tests/test_trading_subsystem_disablement.py -v
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Alpaca must stay unconfigured for plain imports of services.execution
# (matches the convention already used by test_cancel_orders_guard.py and
# test_strategy_governance_gate.py in this directory).
os.environ['ALPACA_API_KEY']    = ''
os.environ['ALPACA_SECRET_KEY'] = ''

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

REPO_ROOT = Path(__file__).resolve().parents[1]

import services.execution as ex
import services.execution_bridge as eb


class _FakeAlert:
    """Minimal stand-in for delivery.alert_engine.AlertData."""
    symbol              = 'MNQ'
    alert_type          = 'EXECUTION_READY'
    grade               = 'A'
    direction           = 'LONG'
    setup_type          = 'PROS'
    session             = 'NY_OPEN'
    decision_id         = ''
    signal_generated_at = ''


def _clean_env(**overrides) -> dict:
    """A copy of the real process env with the retirement flag removed (so
    subprocess tests see the true, un-fixture-patched default) plus overrides."""
    env = dict(os.environ)
    env.pop('NOVA_TRADING_SUBSYSTEM_ENABLED', None)
    env['ALPACA_API_KEY'] = ''
    env['ALPACA_SECRET_KEY'] = ''
    env.update(overrides)
    return env


# ── 1. execute_signal cannot submit an order ──────────────────────────────

def test_execute_signal_blocked_by_default(monkeypatch):
    monkeypatch.setattr(ex, 'NOVA_TRADING_SUBSYSTEM_ENABLED', False)
    with patch('services.execution._client') as mock_client:
        result = ex.execute_signal({'data': {'instrument': 'MNQ', 'ticker': 'MNQ1!'}, 'parsed': {}})
    assert result['status'] == 'TRADING_SUBSYSTEM_DISABLED'
    mock_client.assert_not_called()


def test_execute_signal_proceeds_past_guard_when_flag_enabled(monkeypatch):
    """Proves the guard is a real switch, not a hardcoded block -- with the
    flag enabled (the fixture default), execution proceeds to the next
    (governance) gate instead of stopping at TRADING_SUBSYSTEM_DISABLED."""
    monkeypatch.setattr(ex, 'NOVA_TRADING_SUBSYSTEM_ENABLED', True)
    result = ex.execute_signal({'data': {'instrument': 'MNQ', 'ticker': 'MNQ1!', 'signal_id': 'test-1'}, 'parsed': {}})
    assert result.get('status') != 'TRADING_SUBSYSTEM_DISABLED'


# ── 6/7/8. Cancel, close, flatten, stop/target creation all blocked ───────
# (stop/target creation happens inside _execute_alpaca_etf, only reachable
# through execute_signal -- already covered above.)

@pytest.mark.parametrize('fn_name, args', [
    ('close_position',        ('MNQ',)),
    ('close_all_positions',   ()),
    ('cancel_all_orders',     ()),
    ('close_qqq_positions',   ()),
])
def test_broker_write_functions_blocked_by_default(monkeypatch, fn_name, args):
    monkeypatch.setattr(ex, 'NOVA_TRADING_SUBSYSTEM_ENABLED', False)
    fn = getattr(ex, fn_name)
    with patch('services.execution._client') as mock_client:
        result = fn(*args)
    assert result['status'] == 'TRADING_SUBSYSTEM_DISABLED'
    mock_client.assert_not_called()


def test_close_all_positions_eod_blocked_by_default(monkeypatch):
    monkeypatch.setattr(ex, 'NOVA_TRADING_SUBSYSTEM_ENABLED', False)
    with patch('services.execution._client') as mock_client, \
         patch('services.execution.get_positions') as mock_positions:
        n = ex.close_all_positions_eod()
    assert n == 0
    mock_client.assert_not_called()
    mock_positions.assert_not_called()  # guard exits before even reading positions


# ── 2. Execution requests cannot reach a broker ───────────────────────────

def test_route_to_execution_blocked_by_default(monkeypatch):
    monkeypatch.setenv('NOVA_TRADING_SUBSYSTEM_ENABLED', 'false')
    with patch('services.execution.execute_signal') as mock_exec, \
         patch('services.execution_request.validate_and_record') as mock_validate:
        result = eb.route_to_execution(_FakeAlert())
    assert result['status'] == 'TRADING_SUBSYSTEM_DISABLED'
    mock_exec.assert_not_called()
    mock_validate.assert_not_called()  # no execution request is even recorded


# ── 3. Webhooks cannot cause execution ────────────────────────────────────
# main.py's POST /webhook calls services.execution.execute_signal() directly
# (the same function proven blocked above) after governance checks -- this
# confirms the exact call the webhook makes, without booting the full app
# and its startup-event side effects (finnhub/news/Discord).

def test_webhook_execution_path_blocked_by_default(monkeypatch):
    monkeypatch.setattr(ex, 'NOVA_TRADING_SUBSYSTEM_ENABLED', False)
    signal_result = {
        'data': {'instrument': 'MNQ', 'ticker': 'MNQ1!', 'signal': 'LONG', 'signal_id': 'webhook-test-1'},
        'parsed': {'grade': 'A'},
    }
    with patch('services.execution._client') as mock_client:
        execution = ex.execute_signal(signal_result)
    assert execution['status'] == 'TRADING_SUBSYSTEM_DISABLED'
    mock_client.assert_not_called()


# ── 4. monitor.py cannot cause execution ──────────────────────────────────

def test_monitor_main_exits_cleanly_when_disabled():
    """monitor.py's only purpose is the retired reasoning->execution pipeline.
    Runs in a subprocess so we observe the real process exit, not a mocked one,
    with a clean env the autouse fixture never touches."""
    code = "import monitor; monitor.main(); print('MONITOR_RETURNED_CLEANLY')"
    result = subprocess.run(
        [sys.executable, '-c', code],
        cwd=str(REPO_ROOT), env=_clean_env(), capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, f'monitor.main() crashed: {result.stderr}'
    assert 'MONITOR_RETURNED_CLEANLY' in result.stdout
    assert 'TRADING_SUBSYSTEM_DISABLED' in result.stderr  # logging module writes to stderr by default


# ── 5. Scheduled startup cannot enable auto-execution ─────────────────────

def test_session_launcher_script_does_not_force_auto_execute():
    script = (REPO_ROOT / 'scripts' / 'start_trading_session.ps1').read_text(encoding='utf-8')
    assert "NOVA_AUTO_EXECUTE = 'true'" not in script
    assert "NOVA_TRADING_SUBSYSTEM_ENABLED = 'false'" in script
    assert 'monitor.py"' not in script  # no longer launched


# ── 9. Missing environment variables default safely to disabled ──────────

def test_missing_env_var_defaults_to_disabled():
    code = (
        "import os\n"
        "os.environ.pop('NOVA_TRADING_SUBSYSTEM_ENABLED', None)\n"
        "os.environ['ALPACA_API_KEY'] = ''\n"
        "os.environ['ALPACA_SECRET_KEY'] = ''\n"
        "import services.execution as ex\n"
        "assert ex.NOVA_TRADING_SUBSYSTEM_ENABLED is False\n"
        "print('DEFAULT_DISABLED_OK')\n"
    )
    result = subprocess.run(
        [sys.executable, '-c', code],
        cwd=str(REPO_ROOT), env=_clean_env(), capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, f'crashed: {result.stderr}'
    assert 'DEFAULT_DISABLED_OK' in result.stdout


# ── 10. NOVA_AUTO_EXECUTE=true alone cannot bypass the retirement flag ────

def test_auto_execute_true_alone_cannot_bypass_retirement_flag(monkeypatch):
    monkeypatch.setenv('NOVA_AUTO_EXECUTE', 'true')
    monkeypatch.setenv('NOVA_TRADING_SUBSYSTEM_ENABLED', 'false')
    monkeypatch.setattr(ex, 'NOVA_TRADING_SUBSYSTEM_ENABLED', False)

    # services.execution's guard doesn't look at NOVA_AUTO_EXECUTE at all
    with patch('services.execution._client') as mock_client:
        result = ex.execute_signal({'data': {'instrument': 'MNQ', 'ticker': 'MNQ1!'}, 'parsed': {}})
    assert result['status'] == 'TRADING_SUBSYSTEM_DISABLED'
    mock_client.assert_not_called()

    # execution_bridge's Gate 0 is checked before its own NOVA_AUTO_EXECUTE gate
    with patch('services.execution.execute_signal') as mock_exec:
        bridge_result = eb.route_to_execution(_FakeAlert())
    assert bridge_result['status'] == 'TRADING_SUBSYSTEM_DISABLED'
    mock_exec.assert_not_called()


# ── 11. Journal, Market, NOVA Assistant imports still load ───────────────

def test_journal_market_assistant_modules_still_import():
    for module_name in (
        'core.state',            # journal load/save/stats
        'services.finnhub',      # market data
        'services.news',         # news feed
        'services.headlines',    # economic calendar
        'services.assistant',    # NOVA Assistant
        'engines.analytics',     # journal analytics
        'engines.thesis_analysis',
    ):
        result = subprocess.run(
            [sys.executable, '-c', f'import {module_name}; print("IMPORT_OK")'],
            cwd=str(REPO_ROOT), env=_clean_env(), capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0, f'{module_name} failed to import: {result.stderr}'
        assert 'IMPORT_OK' in result.stdout


# ── 12. Application startup succeeds with trading disabled ───────────────

def test_main_imports_cleanly_with_trading_subsystem_disabled():
    code = 'import main; print("MAIN_IMPORT_OK")'
    result = subprocess.run(
        [sys.executable, '-c', code],
        cwd=str(REPO_ROOT), env=_clean_env(), capture_output=True, text=True, timeout=90,
    )
    assert result.returncode == 0, f'main import crashed: {result.stderr}'
    assert 'MAIN_IMPORT_OK' in result.stdout


if __name__ == '__main__':
    raise SystemExit(pytest.main([__file__, '-v']))
