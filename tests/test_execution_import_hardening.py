"""
test_execution_import_hardening.py — Execution import safety smoke tests.

Context: services/execution.py used to (a) parse NOVA_SESSION_MAX_TRADES /
NOVA_RISK_PCT_PER_TRADE with bare int()/float() that could raise on a
malformed env value and crash import, and (b) call close_qqq_positions()
(a live Alpaca broker call) unconditionally at module load. Either one
failing took down `from services.execution import ...` in main.py, which
surfaces as dashboard EXECUTION PATH: ERROR. This file locks in the fix.

Covers:
  1.  services.execution imports with malformed NOVA_SESSION_MAX_TRADES
  2.  services.execution imports with malformed NOVA_RISK_PCT_PER_TRADE
  3.  core.config imports with malformed ALERT_COOLDOWN_MINUTES
  4.  core.config imports with malformed ALERT_DAILY_MAX
  5.  core.config imports with malformed NOVA_EXECUTION_SAFETY_ALERT_COOLDOWN_SECONDS
  6.  importing services.execution does not call close_qqq_positions
  7.  importing services.execution does not call submit_order
  8.  importing services.execution does not call cancel_order
  9.  importing services.execution does not call close_position
  10. main imports with _EXECUTION_AVAILABLE=True
  11. get_execution_status() runs cleanly end-to-end (no NameError etc.)

Tests 1-5 and 10 spawn a clean subprocess so module-level code actually
re-executes (sys.modules caching would otherwise hide an import crash).
Tests 6-9 statically walk the AST of services/execution.py and assert none
of the forbidden broker calls appear as a module-level (import-time)
statement — calls inside function bodies (the normal, on-demand trading
path) are untouched and expected.

Test 11 exists because a successful import is necessary but not sufficient
for the dashboard's EXECUTION PATH to be healthy: get_execution_status()
(the actual /execution-status response body) can still raise at call time
even when the module imports fine. Caught one real instance of this on
2026-07-10 — a dangling reference to a function (_get_asia_trade_taken)
removed in an earlier refactor (commit 14bea2a) but never cleaned out of
this dict literal, which 500'd the endpoint on every single call.

Run:  python tests/test_execution_import_hardening.py
      python -m pytest tests/test_execution_import_hardening.py -v
"""
from __future__ import annotations

import ast
import inspect
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

REPO_ROOT = Path(__file__).resolve().parents[1]

# Subprocess env is stripped of broker credentials for every test in this
# file — none of these tests should ever be able to reach a real broker,
# even if a future regression reintroduces an import-time call.
_SAFE_ENV_BASE = dict(os.environ)
_SAFE_ENV_BASE['ALPACA_API_KEY'] = ''
_SAFE_ENV_BASE['ALPACA_SECRET_KEY'] = ''


def _run_import(module_name: str, env_overrides: dict | None = None, timeout: int = 60) -> subprocess.CompletedProcess:
    """Import `module_name` in a fresh subprocess so module-level code
    genuinely re-executes, and report whether it raised."""
    env = dict(_SAFE_ENV_BASE)
    env.update(env_overrides or {})
    code = f'import {module_name}; print("IMPORT_OK")'
    return subprocess.run(
        [sys.executable, '-c', code],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _top_level_call_names(source: str) -> set[str]:
    """Names of every function/method called by code that executes
    immediately on import — i.e. every top-level statement EXCEPT
    function/class definitions, whose bodies only run when called later."""
    tree = ast.parse(source)
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        for sub in ast.walk(node):
            if isinstance(sub, ast.Call):
                func = sub.func
                if isinstance(func, ast.Name):
                    names.add(func.id)
                elif isinstance(func, ast.Attribute):
                    names.add(func.attr)
    return names


def _execution_import_time_calls() -> set[str]:
    import services.execution as ex
    return _top_level_call_names(inspect.getsource(ex))


# ── Tests 1-2: services.execution malformed env vars ──────────────────────

def test_execution_imports_with_malformed_session_max_trades():
    result = _run_import('services.execution', {'NOVA_SESSION_MAX_TRADES': 'not_a_number'})
    assert result.returncode == 0, f'import crashed: {result.stderr}'
    assert 'IMPORT_OK' in result.stdout


def test_execution_imports_with_malformed_risk_pct_per_trade():
    result = _run_import('services.execution', {'NOVA_RISK_PCT_PER_TRADE': 'garbage'})
    assert result.returncode == 0, f'import crashed: {result.stderr}'
    assert 'IMPORT_OK' in result.stdout


# ── Tests 3-5: core.config malformed env vars ──────────────────────────────

def test_config_imports_with_malformed_alert_cooldown_minutes():
    result = _run_import('core.config', {'ALERT_COOLDOWN_MINUTES': 'nope'})
    assert result.returncode == 0, f'import crashed: {result.stderr}'
    assert 'IMPORT_OK' in result.stdout


def test_config_imports_with_malformed_alert_daily_max():
    result = _run_import('core.config', {'ALERT_DAILY_MAX': 'nope'})
    assert result.returncode == 0, f'import crashed: {result.stderr}'
    assert 'IMPORT_OK' in result.stdout


def test_config_imports_with_malformed_safety_alert_cooldown_seconds():
    result = _run_import('core.config', {'NOVA_EXECUTION_SAFETY_ALERT_COOLDOWN_SECONDS': 'nope'})
    assert result.returncode == 0, f'import crashed: {result.stderr}'
    assert 'IMPORT_OK' in result.stdout


# ── Tests 6-9: no broker calls at import time ───────────────────────────────

def test_import_does_not_call_close_qqq_positions():
    calls = _execution_import_time_calls()
    assert 'close_qqq_positions' not in calls, (
        'close_qqq_positions must not run at module import time (broker call)'
    )


def test_import_does_not_call_submit_order():
    calls = _execution_import_time_calls()
    assert 'submit_order' not in calls, (
        'submit_order must not run at module import time (broker call)'
    )


def test_import_does_not_call_cancel_order():
    calls = _execution_import_time_calls()
    assert not ({'cancel_order', 'cancel_order_by_id'} & calls), (
        'cancel_order/cancel_order_by_id must not run at module import time (broker call)'
    )


def test_import_does_not_call_close_position():
    calls = _execution_import_time_calls()
    assert not ({'close_position', 'close_all_positions', 'close_all_positions_eod'} & calls), (
        'close_position and friends must not run at module import time (broker call)'
    )


# ── Test 10: main imports with _EXECUTION_AVAILABLE=True ──────────────────

def test_main_imports_with_execution_available_true():
    code = 'import main; print("EXECUTION_AVAILABLE=" + str(main._EXECUTION_AVAILABLE))'
    result = subprocess.run(
        [sys.executable, '-c', code],
        cwd=str(REPO_ROOT),
        env=_SAFE_ENV_BASE,
        capture_output=True,
        text=True,
        timeout=90,
    )
    assert result.returncode == 0, f'main import crashed: {result.stderr}'
    assert 'EXECUTION_AVAILABLE=True' in result.stdout, (
        f'expected _EXECUTION_AVAILABLE=True, got stdout={result.stdout!r} stderr={result.stderr!r}'
    )


# ── Test 11: get_execution_status() runs end-to-end without raising ───────

def test_get_execution_status_runs_without_raising():
    result = _run_import(
        'services.execution',
        env_overrides=None,
        timeout=30,
    )
    assert result.returncode == 0, f'import crashed: {result.stderr}'

    code = (
        'import services.execution as ex\n'
        'status = ex.get_execution_status()\n'
        'assert isinstance(status, dict)\n'
        'required = ("broker_mode", "daily_trades_taken", "asia_trade_taken", '
        '"account", "positions")\n'
        'missing = [k for k in required if k not in status]\n'
        'assert not missing, f"missing keys: {missing}"\n'
        'print("STATUS_OK")\n'
    )
    result = subprocess.run(
        [sys.executable, '-c', code],
        cwd=str(REPO_ROOT),
        env=_SAFE_ENV_BASE,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, (
        f'get_execution_status() raised — this is the exact failure mode that '
        f'produces a 500 on GET /execution-status: {result.stderr}'
    )
    assert 'STATUS_OK' in result.stdout


# ── Runner ────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    tests = [
        ('services.execution: malformed NOVA_SESSION_MAX_TRADES',              test_execution_imports_with_malformed_session_max_trades),
        ('services.execution: malformed NOVA_RISK_PCT_PER_TRADE',              test_execution_imports_with_malformed_risk_pct_per_trade),
        ('core.config: malformed ALERT_COOLDOWN_MINUTES',                      test_config_imports_with_malformed_alert_cooldown_minutes),
        ('core.config: malformed ALERT_DAILY_MAX',                             test_config_imports_with_malformed_alert_daily_max),
        ('core.config: malformed NOVA_EXECUTION_SAFETY_ALERT_COOLDOWN_SECONDS', test_config_imports_with_malformed_safety_alert_cooldown_seconds),
        ('import does not call close_qqq_positions',                           test_import_does_not_call_close_qqq_positions),
        ('import does not call submit_order',                                  test_import_does_not_call_submit_order),
        ('import does not call cancel_order',                                  test_import_does_not_call_cancel_order),
        ('import does not call close_position',                                test_import_does_not_call_close_position),
        ('main imports with _EXECUTION_AVAILABLE=True',                        test_main_imports_with_execution_available_true),
        ('get_execution_status() runs without raising',                        test_get_execution_status_runs_without_raising),
    ]

    passed = failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f'  PASS  {name}')
            passed += 1
        except Exception as exc:
            print(f'  FAIL  {name}: {exc}')
            failed += 1

    status = 'OK' if not failed else 'FAIL'
    print(f'\n{passed}/{passed + failed} tests passed [{status}]')
    if failed:
        raise SystemExit(1)
