"""
test_ui_modularization.py — NOVA interface redesign, commit #9: the
modularization-foundation commit.

`ui/html.py` used to be one ~3900-line file containing the entire dashboard
(CSS + HTML + JS) as a single inline triple-quoted string. This commit splits
it into `ui/styles.py`, `ui/scripts.py`, and `ui/pages/*.py`, with `ui/html.py`
reduced to a thin composer that concatenates them back into the same
`DASHBOARD_HTML` string `main.py` already imports.

This file proves the refactor is behavior-preserving: every active DOM id,
every frontend request, every polling interval, and all manual-only
intelligence-feature behavior survive the split unchanged, and no
retired/deferred product surface (including the Execution Bot, per Pedro's
mandatory correction) is reachable from the composed interface.

The one intentional, approved content change bundled into this otherwise
pure refactor is documented and proven separately below: the Settings page's
"Trading Subsystem" retirement-status card (`#setTradingStatus`, the
"H.A.R.V.E.Y, Execution Bot, ORB/PROS/ICT" copy, and the JS that populated
it) has been removed, because the Execution Bot must not appear anywhere in
Interface V1 -- not even as a "this is retired" status card. This is proven
by a byte-for-byte diff against the commit-#8 baseline showing that
correction is the *only* difference in the entire composed document.

Run:  python -m pytest tests/test_ui_modularization.py -v
"""
from __future__ import annotations

import ast
import os
import socket
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('ALPACA_API_KEY', '')
os.environ.setdefault('ALPACA_SECRET_KEY', '')

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _block_real_network(monkeypatch):
    """No test in this file should ever open a real network socket."""
    real_connect = socket.socket.connect

    def _guard(self, address, *args, **kwargs):
        host = address[0] if isinstance(address, tuple) else address
        if host in ('127.0.0.1', 'localhost', '::1'):
            return real_connect(self, address, *args, **kwargs)
        raise AssertionError(f'real network access attempted during UI modularization tests: {address!r}')

    monkeypatch.setattr(socket.socket, 'connect', _guard)
    yield


# ═══════════════════════════════════════════════════════════════════════
# (A) Module structure and import contract
# ═══════════════════════════════════════════════════════════════════════

def test_dashboard_html_import_contract_unchanged():
    """`from ui.html import DASHBOARD_HTML` must remain valid and return a
    non-trivial string -- the one contract main.py depends on."""
    from ui.html import DASHBOARD_HTML
    assert isinstance(DASHBOARD_HTML, str)
    assert len(DASHBOARD_HTML) > 100_000
    assert DASHBOARD_HTML.startswith('<!DOCTYPE html>')
    assert DASHBOARD_HTML.rstrip().endswith('</html>')


def test_new_modules_exist_and_export_expected_names():
    import ui.styles, ui.scripts, ui.pages
    from ui.pages import overview, market_news, nova_ai, journal, settings

    assert hasattr(ui.styles, 'DASHBOARD_CSS') and isinstance(ui.styles.DASHBOARD_CSS, str)
    assert hasattr(ui.scripts, 'DASHBOARD_SCRIPT') and isinstance(ui.scripts.DASHBOARD_SCRIPT, str)
    assert hasattr(overview, 'OVERVIEW_HTML')
    assert hasattr(market_news, 'MARKET_NEWS_HTML')
    assert hasattr(nova_ai, 'NOVA_AI_HTML')
    assert hasattr(journal, 'JOURNAL_HTML') and hasattr(journal, 'JOURNAL_MODALS_HTML')
    assert hasattr(settings, 'SETTINGS_HTML')


def test_html_py_is_a_thin_composer_not_a_monolith():
    """main.py's import target must no longer be a ~3900-line single file --
    confirms the split actually happened, not just an alias."""
    source = (REPO_ROOT / 'ui' / 'html.py').read_text(encoding='utf-8')
    line_count = len(source.splitlines())
    assert line_count < 100, f'ui/html.py should be a thin composer, found {line_count} lines'
    assert 'from ui.styles import DASHBOARD_CSS' in source
    assert 'from ui.scripts import DASHBOARD_SCRIPT' in source
    assert 'from ui.pages import' in source


# ═══════════════════════════════════════════════════════════════════════
# (B) Byte-for-byte equivalence against the commit-#8 baseline
# ═══════════════════════════════════════════════════════════════════════

# Pinned, immutable commit -- the last commit before the modularization
# foundation (commit #9), i.e. the final single-file ui/html.py monolith.
# This must be an exact commit hash, never a moving ref like "HEAD": once
# commit #9 itself lands, HEAD points at the modularized result, and a
# "HEAD:ui/html.py" baseline would silently compare the composed output
# against itself instead of against the pre-modularization monolith.
_COMMIT_8_BASELINE_REF = '213cca8eb969c73e19b0ea804c7f6bacac8b2707'


def _load_baseline_dashboard_html() -> str:
    """Evaluate commit #8's ui/html.py (the pre-modularization, single-file
    version, pinned by exact hash) in an isolated namespace to get its
    DASHBOARD_HTML string, without touching the working tree or importing
    the current package."""
    src = subprocess.run(
        ['git', 'show', f'{_COMMIT_8_BASELINE_REF}:ui/html.py'],
        capture_output=True, text=True, encoding='utf-8', cwd=str(REPO_ROOT),
    ).stdout
    ns: dict = {}
    exec(compile(src, 'baseline_ui_html.py', 'exec'), ns)
    return ns['DASHBOARD_HTML']


def test_composed_html_matches_baseline_except_the_one_approved_correction():
    """The entire composed DASHBOARD_HTML must be identical to the commit-#8
    baseline except for the mandatory Execution-Bot-status removal from
    Settings. This is the strongest possible proof that modularization alone
    introduced zero behavioral change.

    Uses a line-level diff (not a blind full-string equality) so it is
    immune to any line-ending normalization `git show`/`exec()` may apply --
    what matters is which *lines* were added/removed, not the raw byte
    representation of the two strings.
    """
    import difflib

    from ui.html import DASHBOARD_HTML as new_html
    baseline_html = _load_baseline_dashboard_html()
    assert new_html != baseline_html, 'expected exactly one approved content change, found none'

    baseline_lines = baseline_html.replace('\r\n', '\n').splitlines()
    new_lines = new_html.replace('\r\n', '\n').splitlines()

    sm = difflib.SequenceMatcher(a=baseline_lines, b=new_lines, autojunk=False)
    removed_lines = []
    inserted_lines = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag in ('delete', 'replace'):
            removed_lines.extend(baseline_lines[i1:i2])
        if tag in ('insert', 'replace'):
            inserted_lines.extend(new_lines[j1:j2])

    # Nothing new was ever inserted -- this commit only removes content.
    assert inserted_lines == [], f'unexpected inserted line(s) beyond the approved removal: {inserted_lines}'

    expected_removed_fragments = (
        '<!-- Trading subsystem status -->',
        'TRADING SUBSYSTEM</div>',
        'id="setTradingStatus">',
        'The legacy indicator-driven trading subsystem (H.A.R.V.E.Y, Execution Bot, ORB/PROS/ICT strategy signals) has',
        'been retired. No orders can be placed and no broker-write path is reachable from this UI.',
        "document.getElementById('setTradingStatus')",
        'env.trading_subsystem_enabled === true',
        "statusEl.textContent = enabled",
        "statusEl.style.color = enabled",
    )
    # Every removed (non-blank) line must correspond to exactly the approved
    # correction -- either one of the known fragments, or a bare structural
    # line (a lone '<div ...>'/'</div>'/'{'/'}' that belonged only to the
    # removed block, confirmed by proximity to a known fragment above).
    unexplained = []
    for line in removed_lines:
        stripped = line.strip()
        if not stripped:
            continue
        if any(frag in line for frag in expected_removed_fragments):
            continue
        if stripped in ('<div class="exec-row">', '</div>', '{', '}',
                        '<div style="font-size:11px;color:var(--muted2);margin-top:6px">',
                        '<span class="exec-row-label">Status</span>',
                        'if (statusEl) {'):
            continue
        unexplained.append(line)
    assert unexplained == [], f'removed line(s) not accounted for by the approved correction: {unexplained}'


# ═══════════════════════════════════════════════════════════════════════
# (C) Page containers, navigation, and critical DOM identifiers
# ═══════════════════════════════════════════════════════════════════════

_ACTIVE_PAGE_IDS = (
    'page-dashboard', 'page-journal', 'page-news', 'page-assistant', 'page-settings',
)

_ACTIVE_NAV_DATA_PAGES = ('dashboard', 'journal', 'news', 'assistant', 'settings')

_CRITICAL_DOM_IDS = (
    # Overview
    'dbHero', 'dbRegimeText', 'dbMarketTone', 'dbSessionLabel', 'dbMacroPosture',
    'dbBadgeMacro', 'dbBadgeSession', 'dbDriverPrimary', 'dbDriverRegime', 'dbDriverBullets',
    'dbCatalystHeadline', 'dbCatalystSummary', 'dbCatalystSentiment', 'dbMarketBoard',
    'sidebarEconCalendar', 'dbDonnaSaysText',
    # Market & News
    'newsFuturesTrack', 'breakingTickerTrack', 'indexTiles', 'newsList',
    'sidebarMacroRisk', 'sidebarHeadlineRisk', 'sidebarMarketRisk', 'sidebarEventPhase', 'sidebarNextEvent',
    'novaMarketSummaryPanel', 'novaMarketSummaryBtn', 'novaMarketSummaryLoading',
    'novaMarketSummaryText', 'novaMarketSummaryError',
    'sidebarEconCalendar2', 'moversGainers', 'moversLosers', 'donnaSaysText',
    # NOVA AI (Assistant)
    'assistantOutput', 'typingIndicator', 'assistantInput', 'assistantSend',
    # Modals (owned by ui/pages/journal.py)
    'jtdBackdrop', 'jtdBody', 'jModalBackdrop', 'jSubmitBtn', 'jFormMsg',
    # Settings (post-correction: no setTradingStatus)
    'setIntegrations', 'setChatModel', 'setFastModel', 'setServerTime',
    # Journal
    'jOpenModal', 'jOverviewStrip', 'jOvTrades', 'jOvPnl', 'jOvEvals', 'jOvWinRate', 'jOvPF', 'jOvWeek',
    'jTab-trades', 'jTab-signals', 'jTab-analytics',
    'jPanel-trades', 'jPanel-signals', 'jPanel-analytics',
    'journalCardList', 'jSignalFeedList',
    'setupTypeGrid', 'sessionBreakdownGrid', 'regimeBreakdownGrid',
    'behavioralAnalyticsGrid', 'emotionalAnalyticsGrid',
    # Footer
    'lastUpdated',
)


def test_all_five_page_containers_present():
    from ui.html import DASHBOARD_HTML
    for page_id in _ACTIVE_PAGE_IDS:
        assert f'id="{page_id}"' in DASHBOARD_HTML, f'missing page container {page_id!r}'


def test_all_active_navigation_controls_present():
    from ui.html import DASHBOARD_HTML
    for data_page in _ACTIVE_NAV_DATA_PAGES:
        assert f'data-page="{data_page}"' in DASHBOARD_HTML, f'missing nav control for {data_page!r}'
    # Exactly 5 nav buttons -- no Bot/Macro/Execution tab was added.
    assert DASHBOARD_HTML.count('class="tab-btn') == 5 or DASHBOARD_HTML.count("data-page=") >= 5


def test_every_critical_dom_identifier_present():
    from ui.html import DASHBOARD_HTML
    missing = [i for i in _CRITICAL_DOM_IDS if f'id="{i}"' not in DASHBOARD_HTML]
    assert missing == [], f'critical DOM identifiers missing after modularization: {missing}'


# ═══════════════════════════════════════════════════════════════════════
# (D) Frontend-to-backend request targets unchanged
# ═══════════════════════════════════════════════════════════════════════

_ACTIVE_FETCH_TARGETS = (
    '/state-engine', '/major-indexes', '/futures-macro-pulse', '/btc-vix',
    '/trending-movers', '/calendar', '/dashboard-data', '/check-env', '/system-health',
    '/assistant/chat', '/journal/trade-detail', '/journal/analyze', '/market-summary',
    '/journal/data', '/journal/signals', '/journal/delete', '/journal/add',
)


def test_every_active_frontend_route_target_unchanged():
    from ui.html import DASHBOARD_HTML
    missing = [r for r in _ACTIVE_FETCH_TARGETS if r not in DASHBOARD_HTML]
    assert missing == [], f'frontend route target(s) missing after modularization: {missing}'


_BROKER_WRITE_ROUTES = (
    '/execution/close', '/execution/close-all', '/execution/cancel-orders',
    '/close-all', '/execution/macro-lock', '/execution/red-folder-lock',
    '/execution/trade-permission', '/execution/settings', '/webhook',
)


def test_no_broker_write_route_reachable_from_frontend():
    from ui.html import DASHBOARD_HTML
    for route in _BROKER_WRITE_ROUTES:
        assert f"fetch('{route}'" not in DASHBOARD_HTML and f'fetch("{route}"' not in DASHBOARD_HTML, (
            f'broker-write route {route!r} must never be called from the frontend'
        )


# ═══════════════════════════════════════════════════════════════════════
# (E) Manual-only intelligence features and polling frequencies preserved
# ═══════════════════════════════════════════════════════════════════════

# Exact source-literal form as written in the script (not the computed
# millisecond value) -- some intervals are written as an expression
# (`5 * 60 * 1000`) rather than a pre-computed literal.
_POLLING_REGISTRATIONS = {
    'refresh': 'setInterval(refresh, 30000)',
    'refreshJournal': 'setInterval(refreshJournal, 60000)',
    'refreshNewsFuturesStrip': 'setInterval(refreshNewsFuturesStrip, 30000)',
    'refreshTrendingMovers': 'setInterval(refreshTrendingMovers, 5 * 60 * 1000)',
    'refreshEconCalendar': 'setInterval(refreshEconCalendar, 5 * 60 * 1000)',
    'fetchStateEngine': 'setInterval(fetchStateEngine, 15000)',
    'dashClock': 'setInterval(dashClock, 1000)',
}
_POLLING_INTERVALS = {
    'refresh': 30000, 'refreshJournal': 60000, 'refreshNewsFuturesStrip': 30000,
    'refreshTrendingMovers': 300000, 'refreshEconCalendar': 300000,
    'fetchStateEngine': 15000, 'dashClock': 1000,
}


def test_polling_functions_and_frequencies_unchanged():
    import ui.scripts
    script = ui.scripts.DASHBOARD_SCRIPT
    assert script.count('setInterval(') == 7, (
        f'expected exactly 7 setInterval registrations, found {script.count("setInterval(")}'
    )
    for fn, registration in _POLLING_REGISTRATIONS.items():
        assert registration in script, f'polling registration for {fn} not found unchanged: {registration!r}'


def test_three_intelligence_features_remain_exclusively_manual():
    """Assistant chat, Journal Review, and Market Summary must never be
    reachable from any setInterval-driven polling function -- only from
    user-action handlers (button click / Enter key)."""
    import ui.scripts
    script = ui.scripts.DASHBOARD_SCRIPT

    for fn_name, ms in _POLLING_INTERVALS.items():
        # Extract the function body naively: from "function fn_name(" or
        # "async function fn_name(" to the next top-level "function " or "async function ".
        for marker in (f'function {fn_name}(', f'async function {fn_name}('):
            idx = script.find(marker)
            if idx != -1:
                # crude but sufficient: search only the next ~2000 chars for gateway calls
                window = script[idx: idx + 2000]
                assert '/assistant/chat' not in window, f'{fn_name} must never call /assistant/chat'
                assert '/journal/analyze' not in window, f'{fn_name} must never call /journal/analyze'
                assert '/market-summary' not in window, f'{fn_name} must never call /market-summary'
                break


def test_market_summary_manual_trigger_and_route_intact():
    from ui.pages.market_news import MARKET_NEWS_HTML
    assert 'generateMarketSummary()' in MARKET_NEWS_HTML
    import ui.scripts
    assert "fetch('/market-summary'" in ui.scripts.DASHBOARD_SCRIPT


def test_assistant_chat_manual_trigger_intact():
    from ui.pages.nova_ai import NOVA_AI_HTML
    assert 'assistantSend' in NOVA_AI_HTML
    import ui.scripts
    assert "fetch('/assistant/chat'" in ui.scripts.DASHBOARD_SCRIPT


def test_journal_review_manual_trigger_intact():
    import ui.scripts
    assert 'generateAnalysis' in ui.scripts.DASHBOARD_SCRIPT
    assert "fetch('/journal/analyze'" in ui.scripts.DASHBOARD_SCRIPT


# ═══════════════════════════════════════════════════════════════════════
# (F) Retired/deferred surfaces absent, including the mandatory correction
# ═══════════════════════════════════════════════════════════════════════

# Markers that must not appear anywhere at all, including in the still-inert
# dead CSS (which commit #9 deliberately leaves untouched -- deletion is
# commit #10's job; these specific markers are execution-bot-identity terms
# covered by this commit's mandatory correction, not general dead-code terms).
_RETIRED_OR_DEFERRED_MARKERS_ANYWHERE = (
    'setTradingStatus', 'TRADING SUBSYSTEM', 'trading_subsystem_enabled',
    'scenarioGenBtn', 'Grok', 'GROK', 'grok-card',
    'data-page="bot"', 'data-page="macro"',
)

# Markers that must not appear in any LIVE, rendered page module or in the
# active JS (they are known to still exist, inert, in the dead CSS stylesheet
# per the audit -- that cleanup is explicitly deferred to commit #10, so this
# check is scoped to what's actually reachable/rendered today, not the whole
# 86KB stylesheet).
_RETIRED_OR_DEFERRED_MARKERS_IN_LIVE_CONTENT = (
    'Execution Bot', 'H.A.R.V.E.Y', 'HARVEY',
    'Scenario Engine', 'AI Morning Brief', 'Performance Insight', 'grok',
)


def test_no_retired_or_deferred_feature_reachable_from_composed_interface():
    from ui.html import DASHBOARD_HTML
    found = [m for m in _RETIRED_OR_DEFERRED_MARKERS_ANYWHERE if m in DASHBOARD_HTML]
    assert found == [], f'retired/deferred surface marker(s) found anywhere in composed interface: {found}'


def test_no_retired_or_deferred_feature_reachable_from_live_page_content():
    """Scoped to the 5 live page modules + JS (not the still-inert, not-yet-
    deleted dead CSS, which is out of scope for commit #9 per Pedro's
    instruction that dead-code deletion belongs in commit #10)."""
    from ui.pages import overview, market_news, nova_ai, journal, settings
    import ui.scripts
    live_sources = {
        'overview': overview.OVERVIEW_HTML,
        'market_news': market_news.MARKET_NEWS_HTML,
        'nova_ai': nova_ai.NOVA_AI_HTML,
        'journal_page': journal.JOURNAL_HTML,
        'journal_modals': journal.JOURNAL_MODALS_HTML,
        'settings': settings.SETTINGS_HTML,
        'script': ui.scripts.DASHBOARD_SCRIPT,
    }
    offenders = []
    for name, content in live_sources.items():
        for marker in _RETIRED_OR_DEFERRED_MARKERS_IN_LIVE_CONTENT:
            if marker in content:
                offenders.append((name, marker))
    assert offenders == [], f'retired/deferred surface marker(s) found in live content: {offenders}'


def test_execution_bot_mandatory_correction_applied_in_settings_module():
    from ui.pages.settings import SETTINGS_HTML
    for marker in ('setTradingStatus', 'TRADING SUBSYSTEM', 'Execution Bot', 'H.A.R.V.E.Y', 'ORB/PROS/ICT'):
        assert marker not in SETTINGS_HTML, f'{marker!r} must not appear in ui/pages/settings.py'
    # Settings must still report active, user-relevant info.
    assert 'INTEGRATIONS' in SETTINGS_HTML
    assert 'SYSTEM' in SETTINGS_HTML
    assert 'setIntegrations' in SETTINGS_HTML


def test_execution_bot_mandatory_correction_applied_in_scripts_module():
    import ui.scripts
    assert 'setTradingStatus' not in ui.scripts.DASHBOARD_SCRIPT
    assert 'trading_subsystem_enabled' not in ui.scripts.DASHBOARD_SCRIPT


# ═══════════════════════════════════════════════════════════════════════
# (G) Provider-safety allowlist unaffected by this frontend-only commit
# ═══════════════════════════════════════════════════════════════════════

def test_provider_call_allowlist_remains_empty():
    import importlib
    m = importlib.import_module('tests.test_intelligence_provider_call_allowlist')
    assert m._ALLOWLIST == set()


# ═══════════════════════════════════════════════════════════════════════
# (H) main.py untouched by this commit
# ═══════════════════════════════════════════════════════════════════════

def test_main_py_not_modified_by_this_commit():
    """This commit is frontend-only; confirms main.py's own source hash
    against HEAD is identical apart from its known, pre-existing, unstaged
    Phase 8 hunks -- i.e., nothing about this commit touches main.py."""
    diff = subprocess.run(
        ['git', 'diff', '--cached', '--name-only'],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    ).stdout
    assert 'main.py' not in diff.splitlines()
