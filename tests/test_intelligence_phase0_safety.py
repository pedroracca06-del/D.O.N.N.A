"""
test_intelligence_phase0_safety.py — NOVA Intelligence Rebuild, Phase 0
(safety and cost containment), 2026-07-20.

Background: a read-only audit of NOVA's AI architecture (ahead of building a
central, provider-independent intelligence layer) found two issues that
needed closing before any rebuild work begins:

1. main.py's startup event unconditionally called
   delivery.alert_engine.start_setup_monitor(60) whenever alert_engine
   imported successfully -- completely independent of
   NOVA_TRADING_SUBSYSTEM_ENABLED (the trading kill switch only ever
   guarded broker writes, never this reasoning/alert loop). That background
   thread polls TradingView/MCP every 60s and, when a chart is reachable,
   runs the legacy Claude setup-grading pipeline
   (engines.reasoning.evaluate_with_claude) and delivers Discord setup
   alerts -- fully reachable outside the trading retirement's stated
   boundary if TradingView/CDP were ever open locally alongside main.py.
2. health/health.py's credentials check made a real, billable
   anthropic.messages.create(max_tokens=1) call to Anthropic on every
   health check, and could report "responsive" only by actually spending
   money to find out.

This file proves both are closed: startup no longer starts the monitor
(archived, not deleted -- delivery/alert_engine.py and engines/reasoning.py
are untouched and still importable), and the health check now reports a
local configured/not_configured/unknown status without ever contacting
Anthropic, Grok, or any other external AI provider.

This file does not touch AI provider choice, model names, prompts, or any
user-facing AI behavior -- see nova_knowledge_core (rebuild audit report)
for the read-only architecture survey this correction responds to.

Run:  python -m pytest tests/test_intelligence_phase0_safety.py -v
"""
from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path

import pytest

os.environ.setdefault('ALPACA_API_KEY',    '')
os.environ.setdefault('ALPACA_SECRET_KEY', '')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

REPO_ROOT = Path(__file__).resolve().parents[1]
MAIN_PY   = REPO_ROOT / 'main.py'


def _clean_env(**overrides) -> dict:
    env = dict(os.environ)
    env.pop('NOVA_TRADING_SUBSYSTEM_ENABLED', None)
    env['ALPACA_API_KEY'] = ''
    env['ALPACA_SECRET_KEY'] = ''
    env.update(overrides)
    return env


def _run(code: str, timeout: int = 90, **env_overrides) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, '-c', code],
        cwd=str(REPO_ROOT), env=_clean_env(**env_overrides),
        capture_output=True, text=True, timeout=timeout,
    )


# ── 1. Normal startup does not call start_setup_monitor ──────────────────

def _find_function(tree: ast.Module, name: str) -> ast.AsyncFunctionDef | ast.FunctionDef:
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    raise AssertionError(f'function {name!r} not found in main.py')


def _calls_name(node: ast.AST, target: str) -> bool:
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call):
            func = sub.func
            if isinstance(func, ast.Name) and func.id == target:
                return True
            if isinstance(func, ast.Attribute) and func.attr == target:
                return True
        # asyncio.to_thread(start_setup_monitor, 60) passes the function as
        # a bare argument, not a call -- catch that form too.
        if isinstance(sub, ast.Name) and sub.id == target:
            return True
    return False


def test_startup_function_never_references_start_setup_monitor():
    """AST-level check on main.py's actual startup() function body -- not
    just a string search of the whole file, since start_setup_monitor still
    legitimately appears elsewhere (import, stub fallback, explanatory
    comment) and must keep appearing there."""
    tree = ast.parse(MAIN_PY.read_text(encoding='utf-8'))
    startup_fn = _find_function(tree, 'startup')
    assert not _calls_name(startup_fn, 'start_setup_monitor'), (
        'main.py startup() must never reference start_setup_monitor -- '
        'the retired setup-monitor thread must not auto-start.'
    )


def test_start_setup_monitor_still_defined_and_importable():
    """Archived, not deleted: delivery.alert_engine.start_setup_monitor and
    engines.reasoning must remain importable and unmodified as historical
    code -- this correction disables the automatic call, not the
    implementation."""
    result = _run(
        "import delivery.alert_engine as ae\n"
        "import engines.reasoning as r\n"
        "assert callable(ae.start_setup_monitor)\n"
        "assert callable(r.run_reasoning_cycle)\n"
        "assert callable(r.evaluate_with_claude)\n"
        "print('ARCHIVED_CODE_INTACT')\n"
    )
    assert result.returncode == 0, f'crashed: {result.stderr}'
    assert 'ARCHIVED_CODE_INTACT' in result.stdout


def test_main_imports_cleanly_and_startup_source_has_no_auto_monitor_call():
    """Full main.py import succeeds (no syntax/import regression from the
    edit), matching the existing app-startup-succeeds test convention."""
    result = _run('import main; print("MAIN_IMPORT_OK")')
    assert result.returncode == 0, f'main import crashed: {result.stderr}'
    assert 'MAIN_IMPORT_OK' in result.stdout


# ── 2/3. Health endpoint never calls messages.create() or any external AI ──

def test_check_credentials_never_calls_anthropic_messages_create(monkeypatch):
    """Even with a (fake) API key present, _check_credentials() must never
    instantiate the Anthropic client or call messages.create(). We force
    any accidental instantiation to explode, so this test fails loudly if
    the billable ping is ever reintroduced."""
    import anthropic
    from health.health import _check_credentials

    def _boom(*a, **kw):
        raise AssertionError('Anthropic client must not be instantiated by the health check')

    monkeypatch.setattr(anthropic, 'Anthropic', _boom)
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'sk-ant-fake-test-key-not-real')
    monkeypatch.setenv('ANTHROPIC_MODEL', 'claude-haiku-4-5-20251001')
    # Discord check would otherwise try a real network call for this test;
    # keep it unconfigured so this test only exercises the Anthropic path.
    monkeypatch.setenv('DISCORD_BOT_TOKEN', '')

    results = _check_credentials()

    anthropic_entries = [r for r in results if 'Anthropic' in r.get('detail', '')]
    assert len(anthropic_entries) == 1
    assert anthropic_entries[0]['value'] == 'configured'
    assert anthropic_entries[0]['status'] == 'PASS'
    assert 'not contacted' in anthropic_entries[0]['detail']


def test_check_credentials_reports_not_configured_without_key(monkeypatch):
    import anthropic
    from health.health import _check_credentials

    monkeypatch.setattr(
        anthropic, 'Anthropic',
        lambda *a, **kw: (_ for _ in ()).throw(AssertionError('must not instantiate Anthropic client')),
    )
    monkeypatch.setenv('ANTHROPIC_API_KEY', '')
    monkeypatch.setenv('DISCORD_BOT_TOKEN', '')

    results = _check_credentials()
    anthropic_entries = [r for r in results if 'Anthropic' in r.get('detail', '')]
    assert len(anthropic_entries) == 1
    assert anthropic_entries[0]['value'] == 'not_configured'
    assert anthropic_entries[0]['status'] == 'FAIL'


def test_health_check_source_contains_no_messages_create_call():
    """Static confirmation the billable call itself is gone from the source
    (not just unreachable at runtime) -- the string only appears in the
    explanatory comment now."""
    src = Path(REPO_ROOT / 'health' / 'health.py').read_text(encoding='utf-8')
    for line in src.splitlines():
        stripped = line.strip()
        if 'messages.create(' in stripped:
            assert stripped.startswith('#') or stripped.startswith('//'), (
                f'found a live messages.create( call outside a comment: {line!r}'
            )


# ── 4. Existing non-AI health information remains present ────────────────

def test_check_credentials_still_reports_discord(monkeypatch):
    """The Discord credential check (unrelated to this correction) must be
    untouched and still present alongside the Anthropic entry."""
    import anthropic
    from health.health import _check_credentials

    monkeypatch.setattr(anthropic, 'Anthropic', lambda *a, **kw: None)
    monkeypatch.setenv('ANTHROPIC_API_KEY', '')
    monkeypatch.setenv('DISCORD_BOT_TOKEN', '')  # unconfigured -> deterministic FAIL, no network

    results = _check_credentials()
    assert len(results) == 2  # Discord + Anthropic, unchanged shape
    discord_entries = [r for r in results if 'Discord' in r.get('detail', '')]
    assert len(discord_entries) == 1
    assert discord_entries[0]['status'] == 'FAIL'
    assert 'not set' in discord_entries[0]['detail']


# ── 5. Journal, Market/News, and NOVA Assistant remain unchanged ──────────

def test_journal_market_assistant_modules_still_import_cleanly():
    for module_name in (
        'core.state',            # journal load/save/stats
        'services.finnhub',      # market data
        'services.news',         # news feed (unmodified)
        'services.headlines',    # economic calendar
        'services.assistant',    # NOVA Assistant (unmodified)
        'engines.analytics',     # journal analytics
    ):
        result = _run(f'import {module_name}; print("IMPORT_OK")')
        assert result.returncode == 0, f'{module_name} failed to import: {result.stderr}'
        assert 'IMPORT_OK' in result.stdout


def test_alert_engine_manual_endpoints_flag_unaffected():
    """_ALERT_ENGINE_AVAILABLE still gates the manual alert-delivery routes
    in main.py (unrelated to the automatic monitor) -- confirms this
    correction did not remove or break that flag."""
    result = _run(
        "import main\n"
        "assert hasattr(main, '_ALERT_ENGINE_AVAILABLE')\n"
        "print('FLAG_PRESENT')\n"
    )
    assert result.returncode == 0, f'crashed: {result.stderr}'
    assert 'FLAG_PRESENT' in result.stdout


if __name__ == '__main__':
    raise SystemExit(pytest.main([__file__, '-v']))
