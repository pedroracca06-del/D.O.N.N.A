"""
test_ui_retirement.py — Phase 3 UI retirement (2026-07-16).

Background: the legacy indicator-driven trading subsystem (H.A.R.V.E.Y,
Execution Bot, NOVA Replay tab, ORB/PROS/ICT/IB strategy controls, broker
controls) was already disabled server-side by NOVA_TRADING_SUBSYSTEM_ENABLED
(see test_trading_subsystem_disablement.py). This file proves the *frontend*
no longer presents that subsystem as active: the retired tabs/controls are
gone from navigation, retired background polling no longer starts, no
frontend interaction can reach a broker-write route, and the four active
pillars (Journal, Market/News, NOVA Assistant, Settings) remain intact and
their backend routes still load. See
nova_knowledge_core/TRADING_SUBSYSTEM_UI_RETIREMENT.md for the full record.

This file does not touch backend business logic -- it inspects the
DASHBOARD_HTML template as a string (matching the convention already used by
test_replay_dashboard.py) and, for routes/startup, spawns a clean subprocess
(matching the convention used by test_trading_subsystem_disablement.py) so
main.py's on_event('startup') background loops are never actually started
in-process during the test run.

Run:  python -m pytest tests/test_ui_retirement.py -v
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

os.environ.setdefault('ALPACA_API_KEY',    '')
os.environ.setdefault('ALPACA_SECRET_KEY', '')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

REPO_ROOT = Path(__file__).resolve().parents[1]

from ui.html import DASHBOARD_HTML

HTML = DASHBOARD_HTML


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


# ── 1-4. Active navigation contains the four retained pillars ────────────

@pytest.mark.parametrize('label, data_page', [
    ('Journal',   'journal'),
    ('News',      'news'),      # Market/News pillar
    ('Assistant', 'assistant'), # NOVA AI Assistant pillar
    ('Settings',  'settings'),
])
def test_active_navigation_contains_pillar(label, data_page):
    assert f'data-page="{data_page}"' in HTML
    assert f'id="page-{data_page}"' in HTML


# ── 5-10. Retired surfaces absent from active navigation ─────────────────

def test_harvey_absent_from_active_nav():
    """No *visible* Harvey branding: nav button, page, and tab-button markup
    must be gone. A dead CSS section comment ('H.A.R.V.E.Y EXECUTION TAB')
    and this file's own Settings-page disclosure sentence ("...H.A.R.V.E.Y,
    Execution Bot...has been retired") are not user-visible product surface
    and are intentionally allowed -- see test_only_harvey_mentions_are_dead_or_disclosure."""
    assert 'data-page="harvey"' not in HTML
    assert 'id="page-harvey"' not in HTML
    assert '>H.A.R.V.E.Y<' not in HTML
    assert 'class="tab-btn harvey-btn"' not in HTML


def test_only_harvey_mentions_are_dead_or_disclosure():
    """Every remaining 'H.A.R.V.E.Y' occurrence must be either inside an
    orphaned CSS block comment (harmless, invisible) or this retirement's
    own explicit 'has been retired' disclosure -- never presented as active
    branding."""
    for m in re.finditer(r'H\.A\.R\.V\.E\.Y', HTML):
        window_start = max(0, m.start() - 200)
        before = HTML[window_start:m.start()]
        after  = HTML[m.end():m.end() + 300]
        is_css_comment = before.rfind('/*') > before.rfind('*/') and '*/' in after
        is_retirement_disclosure = 'retired' in after
        assert is_css_comment or is_retirement_disclosure, (
            f'unexpected H.A.R.V.E.Y reference near offset {m.start()}: {HTML[window_start:m.end()+40]!r}'
        )


def test_execution_tab_absent_from_active_nav():
    assert 'data-page="execution"' not in HTML
    assert 'id="page-execution"' not in HTML


def test_nova_replay_absent_from_active_nav():
    assert 'data-page="replay"' not in HTML
    assert 'id="page-replay"' not in HTML
    assert '>NOVA REPLAY<' not in HTML
    assert 'data-page="replay">NOVA REPLAY' not in HTML


def test_alerts_feed_tab_absent_from_active_nav():
    """The Alerts tab's only backend source (/api/feed) is 100% retired-
    subsystem content (SIGNAL/EXECUTION/GOVERNANCE/MR2_CHANGE) with no
    economic-event or breaking-news source wired in -- removed rather than
    shown empty or filled with stale/fabricated content."""
    assert 'data-page="alerts"' not in HTML
    assert 'id="page-alerts"' not in HTML


def test_legacy_strategy_controls_absent():
    forbidden_controls = [
        'data-fd-cat="execution"',   # feed EXECUTION category filter
        'id="hvTab-harvey"',
        'id="hvTab-mr"',
        'id="hvTab-draws"',
    ]
    for marker in forbidden_controls:
        assert marker not in HTML, f'found forbidden legacy control marker: {marker}'


def test_broker_and_auto_execute_controls_absent():
    """Checks for interactive-control phrasing, not prose. This file's own
    Settings-page disclosure ("no broker-write path is reachable") uses the
    word 'broker' honestly to describe what was removed -- it is not a
    control, so bare 'broker' is deliberately excluded from this list."""
    lowered = HTML.lower()
    for phrase in ('close position', 'close all', 'cancel order', 'flatten', 'auto execute',
                   'autoexecute', 'broker position', 'broker order', 'broker control'):
        assert phrase not in lowered, f'found forbidden broker/auto-execute control text: {phrase!r}'


# ── 11. Retired frontend polling does not start ──────────────────────────

def test_retired_frontend_polling_does_not_start():
    forbidden_boot_calls = [
        'initFeedNotifications();',
        'connectSSE();',
        'setInterval(refreshFeed',
    ]
    for call in forbidden_boot_calls:
        assert call not in HTML, f'retired boot-time call still present: {call}'


# ── 12-14. Journal / Market / NOVA Assistant routes still load ───────────

@pytest.mark.parametrize('path', ['/journal/data', '/journal/signals'])
def test_journal_routes_still_registered(path):
    code = (
        "import main\n"
        f"assert any(getattr(r, 'path', None) == {path!r} for r in main.app.routes), "
        f"'{path} not registered'\n"
        "print('ROUTE_OK')\n"
    )
    result = _run(code)
    assert result.returncode == 0, f'crashed: {result.stderr}'
    assert 'ROUTE_OK' in result.stdout


@pytest.mark.parametrize('path', ['/market-data', '/dashboard-data', '/calendar'])
def test_market_routes_still_registered(path):
    code = (
        "import main\n"
        f"assert any(getattr(r, 'path', None) == {path!r} for r in main.app.routes), "
        f"'{path} not registered'\n"
        "print('ROUTE_OK')\n"
    )
    result = _run(code)
    assert result.returncode == 0, f'crashed: {result.stderr}'
    assert 'ROUTE_OK' in result.stdout


def test_nova_assistant_route_still_registered():
    code = (
        "import main\n"
        "assert any(getattr(r, 'path', None) == '/assistant/chat' for r in main.app.routes)\n"
        "print('ROUTE_OK')\n"
    )
    result = _run(code)
    assert result.returncode == 0, f'crashed: {result.stderr}'
    assert 'ROUTE_OK' in result.stdout


# ── 15. Application startup succeeds with trading disabled ───────────────

def test_main_imports_cleanly_with_trading_disabled():
    result = _run('import main; print("MAIN_IMPORT_OK")')
    assert result.returncode == 0, f'main import crashed: {result.stderr}'
    assert 'MAIN_IMPORT_OK' in result.stdout


# ── 16. No frontend interaction can invoke a broker-write route ──────────

_BROKER_WRITE_PATHS = (
    '/execution/close', '/execution/close-all', '/execution/cancel-orders',
    '/execution/macro-lock', '/execution/red-folder-lock', '/execution/trade-permission',
    '/execution/settings', '/close-all', '/harvey-data',
    '/api/governance', '/api/execution-state',
)

def test_no_frontend_fetch_targets_a_broker_write_route():
    fetch_urls = re.findall(r"fetch\(\s*[`'\"]([^`'\"]+)[`'\"]", HTML)
    assert fetch_urls, 'expected at least one fetch() call in DASHBOARD_HTML'
    for url in fetch_urls:
        for forbidden in _BROKER_WRITE_PATHS:
            assert not url.startswith(forbidden), f'frontend fetch() targets broker-write route: {url}'


# ── 17. Historical journal and replay data / access are not deleted ──────

def test_historical_journal_access_preserved():
    code = (
        "import main\n"
        "from core.state import load_journal, save_journal\n"
        "assert any(getattr(r, 'path', None) == '/journal/data' for r in main.app.routes)\n"
        "print('JOURNAL_ACCESS_OK')\n"
    )
    result = _run(code)
    assert result.returncode == 0, f'crashed: {result.stderr}'
    assert 'JOURNAL_ACCESS_OK' in result.stdout


def test_historical_replay_backend_routes_preserved():
    """NOVA Replay's tab is gone from active nav, but its backend
    (decisions/fingerprints/similarity/outcomes/post-trade-reviews) must
    remain reachable -- this phase is UI retirement, not data destruction."""
    replay_paths = [
        '/api/mcp-replay/decisions', '/api/mcp-replay/fingerprints',
        '/api/mcp-replay/similar', '/api/mcp-replay/outcomes',
        '/api/mcp-replay/similar-with-outcomes', '/api/mcp-replay/post-trade-reviews',
        '/api/mcp-replay/shadow',
    ]
    code = (
        "import main\n"
        "paths = {getattr(r, 'path', None) for r in main.app.routes}\n"
        f"missing = [p for p in {replay_paths!r} if p not in paths]\n"
        "assert not missing, f'missing replay routes: {missing}'\n"
        "print('REPLAY_BACKEND_OK')\n"
    )
    result = _run(code)
    assert result.returncode == 0, f'crashed: {result.stderr}'
    assert 'REPLAY_BACKEND_OK' in result.stdout


# ── 18. No Pine or TradingView files modified ─────────────────────────────

def test_no_pine_write_calls_introduced():
    """Static proxy: the UI retirement must never call MCP Pine-write
    functions. Full confirmation that indicators/ and the live TradingView
    chart were untouched is a manual git-diff check reported alongside this
    commit (this phase does not touch TradingView automation at all)."""
    for marker in ('pine_set', 'pine_save', 'pine_new'):
        assert marker not in HTML


if __name__ == '__main__':
    raise SystemExit(pytest.main([__file__, '-v']))
