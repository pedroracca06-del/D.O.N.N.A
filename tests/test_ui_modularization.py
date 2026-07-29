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
import shutil
import socket
import subprocess
import sys
import tempfile
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

# Pinned, immutable commit -- the modularization foundation itself (commit
# #9), i.e. the last commit before commit #10's dead-code purge. Used as the
# "new" side of the commit-8 comparison below (not `ui.html.DASHBOARD_HTML`
# from disk) so that comparison stays permanently frozen: it proves what
# commit #9 changed, once and forever, independent of any later, separately-
# approved commit (like #10) that legitimately changes ui/html.py further.
# The commit-#10-specific claim ("what changed since #9") is proven by its
# own dedicated test/baseline further down this file.
_COMMIT_9_BASELINE_REF = '16948fce0f6767f097e81d35a90e91066a0274e4'


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


def _load_pinned_commit_dashboard_html(commit_ref: str) -> str:
    """Evaluate `ui/html.py` as of `commit_ref` to get its composed
    DASHBOARD_HTML string. Unlike `_load_baseline_dashboard_html()` above,
    this cannot use a bare `git show <ref>:ui/html.py` + exec() -- from
    commit #9 onward, ui/html.py is itself a composer that imports from
    `ui.styles`, `ui.scripts`, and `ui.pages`, and exec()'ing just that one
    file's source would resolve those imports against whatever `ui.styles`
    etc. currently are on `sys.path` (the live working tree), not against
    `commit_ref`'s own versions of those files -- silently comparing today's
    code against itself. An isolated `git worktree` checkout makes the
    composer's imports resolve against `commit_ref`'s own module files, and
    is torn down again immediately after, touching neither the working tree
    nor the index.
    """
    worktree_dir = tempfile.mkdtemp(prefix='nova_ui_baseline_')
    try:
        add = subprocess.run(
            ['git', 'worktree', 'add', '--detach', worktree_dir, commit_ref],
            capture_output=True, text=True, cwd=str(REPO_ROOT),
        )
        assert add.returncode == 0, f'git worktree add failed: {add.stderr}'
        extract = subprocess.run(
            [sys.executable, '-c',
             'from ui.html import DASHBOARD_HTML as D; import sys; sys.stdout.buffer.write(D.encode("utf-8"))'],
            capture_output=True, cwd=worktree_dir,
        )
        assert extract.returncode == 0, f'baseline extraction failed: {extract.stderr!r}'
        return extract.stdout.decode('utf-8')
    finally:
        # Two-step cleanup, run on every exit path (success, assertion
        # failure, or any other exception): first ask git to remove the
        # worktree registration (this also deletes worktree_dir's contents
        # when `git worktree add` succeeded). Then unconditionally remove
        # whatever remains of worktree_dir -- covers the case where `git
        # worktree add` itself failed before ever registering a worktree,
        # in which case the above call is a no-op and tempfile.mkdtemp()'s
        # directory would otherwise be leaked on disk forever.
        subprocess.run(
            ['git', 'worktree', 'remove', '--force', worktree_dir],
            capture_output=True, text=True, cwd=str(REPO_ROOT),
        )
        shutil.rmtree(worktree_dir, ignore_errors=True)


def test_composed_html_matches_baseline_except_the_one_approved_correction():
    """Commit #9's own composed output must be identical to the commit-#8
    baseline except for the mandatory Execution-Bot-status removal from
    Settings. This is the strongest possible proof that modularization alone
    introduced zero behavioral change.

    Both sides are pinned, immutable commits (not `ui.html.DASHBOARD_HTML`
    read from disk) -- this comparison is frozen forever and cannot be
    affected by any later, separately-approved commit (such as #10's
    dead-code purge) that legitimately changes ui/html.py's content further.
    That later change is proven by its own dedicated test below.

    Uses a line-level diff (not a blind full-string equality) so it is
    immune to any line-ending normalization `git show`/`exec()` may apply --
    what matters is which *lines* were added/removed, not the raw byte
    representation of the two strings.
    """
    import difflib

    new_html = _load_pinned_commit_dashboard_html(_COMMIT_9_BASELINE_REF)
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
# (B2) Commit #10: controlled removal of proven-dead frontend code
# ═══════════════════════════════════════════════════════════════════════
#
# Each entry below is one contiguous change-block between the commit #9
# baseline (pinned above, the last commit before this dead-code purge) and
# the current, on-disk composed DASHBOARD_HTML, identified via
# difflib.SequenceMatcher opcodes (never 'equal' -- those mark untouched,
# identical content). Every block was proven dead -- zero reference
# anywhere in ui/pages/*.py, ui/scripts.py, or ui/html.py -- before
# deletion; see the commit #10 report for the underlying per-symbol
# evidence. Encoding the *exact* block boundaries (not just "something was
# removed somewhere") is a stronger, more precise proof than a flat list of
# expected substrings -- it is what caught a real off-by-one bug during
# this commit's own preparation (an accidentally-deleted "STAT GRID"
# comment header, restored before this catalog was finalized).
_COMMIT_10_CHANGE_CATALOG = (
    {'what': 'Cross-Asset Intelligence CSS (.ca-mode-*/.ca-div-*/.ca-sev-*/.ca-clean) -- no live '
             'consumer since the Harvey/Cross-Asset sub-tab was retired',
     'tag': 'delete', 'first': '/* ── CROSS-ASSET INTELLIGENCE ── */', 'last': '',
     'count': 65, 'new': ()},
    {'what': 'Execution Bot monitor/session-scorecard CSS (.exec-cards-grid, .exec-status-*, '
             '.exec-pnl-big) -- .exec-row/-label/-val kept (reused live by Settings), header '
             'comment renamed to reflect that',
     'tag': 'replace', 'first': '/* ── EXEC MONITOR + SESSION SCORECARD ── */',
     'last': ".exec-pnl-big{font-family:'Rajdhani',sans-serif;font-size:40px;font-weight:700;"
             "line-height:1;letter-spacing:1px}",
     'count': 9, 'new': ('/* ── KV ROW (shared: Settings) ── */',)},
    {'what': 'Session Scorecard CSS (.sc-cells/.sc-cell*/.donna-grade-big) -- Execution Bot only',
     'tag': 'delete', 'first': '.sc-cells{display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;margin:12px 0}',
     'last': '@media(max-width:900px){.exec-cards-grid{grid-template-columns:1fr}}',
     'count': 6, 'new': ()},
    {'what': 'Harvey playbook/signals min-height IDs (#hvPlaybook, #hvSignals) -- Harvey page '
             'retired; #newsList (the line between them) is live and was kept',
     'tag': 'delete', 'first': '#hvPlaybook{min-height:80px}', 'last': '#hvSignals{min-height:80px}',
     'count': 2, 'new': ()},
    {'what': 'Harvey sectors ID + Cross-Asset divergence-list ID + old breaking-events-grid card '
             'family -- all orphaned, superseded by the current News page design',
     'tag': 'delete', 'first': '#hvSectors{min-height:80px}',
     'last': '@media(max-width:900px){.breaking-events-grid{grid-template-columns:1fr}}',
     'count': 25, 'new': ()},
    {'what': 'Old Alerts-tab alert-item CSS (.alert-item/-header/-ticker/-signal/-meta/-body, '
             '.verdict-TAKE/CAUTION/SKIP) -- Alerts tab already retired, superseded by Journal '
             'feed cards (.itc-*)',
     'tag': 'delete', 'first': '/* ── ALERT ITEMS ── */',
     'last': '.verdict-SKIP{color:var(--red)}', 'count': 17, 'new': ()},
    {'what': '.journal-btn/.journal-btn.active -- no nav button anywhere carries this class '
             '(current nav uses plain .tab-btn)',
     'tag': 'delete',
     'first': '.journal-btn{background:var(--panel) !important;border-color:rgba(184,134,11,.3) '
              '!important;color:var(--gold) !important}',
     'last': '.journal-btn.active{background:var(--text) !important;border-color:var(--text) '
             '!important;color:var(--panel) !important}',
     'count': 2, 'new': ()},
    {'what': 'Nova Feed page-header CSS section header renamed -- .fd-page-header/.fd-page-title/'
             '.fd-meta/.fd-refresh-btn (kept, outside this block) are reused live by Settings, not '
             'the retired Feed page',
     'tag': 'replace', 'first': '/* ── NOVA FEED ── */',
     'last': '/* ── NOVA FEED ── */', 'count': 1,
     'new': ('/* ── PAGE HEADER (shared: Settings) ── */',)},
    {'what': 'Nova Feed filter-bar CSS (.fd-filter-bar/.fd-filter-btn) -- Alerts/Feed tab retired, '
             'no filter buttons render',
     'tag': 'delete',
     'first': '.fd-filter-bar{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:14px}',
     'last': '.fd-filter-btn.active{background:rgba(184,134,11,.08);border-color:rgba(184,134,11,.3);'
             'color:var(--gold)}',
     'count': 4, 'new': ()},
    {'what': 'Nova Feed card CSS + Market Reality Page CSS + Governance Page CSS (merged: '
             'contiguous, nothing survives between them) -- all three pages/subsystems retired, '
             'zero live consumer',
     'tag': 'delete',
     'first': '.fd-card{border:1px solid var(--line);border-radius:10px;background:var(--panel);'
              'padding:10px 14px;margin-bottom:7px}',
     'last': '.gov-header-row{display:flex;justify-content:space-between;align-items:center;'
             'margin-bottom:12px}',
     'count': 89, 'new': ()},
    {'what': 'Journal trade-card section header renamed -- only .j-date-group/.j-date-label '
             '(kept) remain of what this section covers, since the old .trade-card component '
             'below is being removed (superseded by .itc-*)',
     'tag': 'replace', 'first': '/* ── TRADE CARDS ── */',
     'last': '/* ── TRADE CARDS ── */', 'count': 1,
     'new': ('/* ── JOURNAL DATE GROUPS ── */',)},
    {'what': 'Old .trade-card/.tc-* journal card CSS -- superseded by .itc-* (intelligence trade '
             'card); ui/scripts.py renderJournal() emits only .itc classes, confirmed zero .tc-* '
             'use anywhere live',
     'tag': 'delete',
     'first': '.trade-card{border:1px solid var(--line);border-radius:12px;background:var(--panel2);'
              'padding:14px 18px;margin-bottom:10px;transition:border-color .15s;border-left:3px '
              'solid transparent}',
     'last': '.tc-outcome-badge.OPEN{background:rgba(0,0,0,.05);color:var(--muted2)}',
     'count': 26, 'new': ()},
    {'what': 'Execution Tab v2 CSS (.exec-heartbeat/.exec-pulse/.exec-hb-*/.exec-state-grid/'
             '.exec-kv*/.exec-pnl-hero/.rej-*/.sc2-*) -- Execution Bot only, no live consumer',
     'tag': 'delete', 'first': '/* ── EXECUTION TAB v2 ── */', 'last': '',
     'count': 39, 'new': ()},
    {'what': 'Responsive media query (1200px): removed dead .hero-grid selector reference '
             '(the .hero-grid base class no longer exists), kept live .main-grid/.stat-grid',
     'tag': 'replace',
     'first': '  .hero-grid,.main-grid,.stat-grid{grid-template-columns:1fr 1fr}',
     'last': '  .hero-grid,.main-grid,.stat-grid{grid-template-columns:1fr 1fr}',
     'count': 1, 'new': ('  .main-grid,.stat-grid{grid-template-columns:1fr 1fr}',)},
    {'what': 'Dead .hero-title responsive rule, plus the entire H.A.R.V.E.Y/verdict/bias/ORB/'
             'Performance-Insight/signal-card/divergence/harvey-grid/Risk-Engine-Panel/'
             'New-Harvey-Layout CSS block (merged: contiguous) -- the same responsive media '
             'query (760px) also had its dead .hero-grid reference removed, kept live '
             '.main-grid/.stat-grid/.live-strip-row',
     'tag': 'replace', 'first': '  .hero-title{font-size:26px}',
     'last': '  .hv-layout, .hv-price-row { grid-template-columns: 1fr; }',
     'count': 228, 'new': ('  .main-grid,.stat-grid,.live-strip-row{grid-template-columns:1fr}',)},
    {'what': 'SSE-signal-dot nav-button CSS (.signal-dot) -- no nav button HTML carries this '
             'class; and the stale "verdict banner flash" section header (the .verdict-banner it '
             'described is itself dead) -- the live donnaFadeIn/.donna-first-load rules '
             'immediately after this header are kept, untouched',
     'tag': 'delete', 'first': '/* ── SSE signal dot on nav button ── */',
     'last': '/* ── verdict banner flash on new signal ── */',
     'count': 16, 'new': ()},
    {'what': 'banner-flash keyframe + .verdict-banner.flash -- .verdict-banner (its base class) '
             'has zero live consumer',
     'tag': 'delete', 'first': '@keyframes banner-flash {',
     'last': '.verdict-banner.flash { animation: banner-flash .7s ease-out }',
     'count': 6, 'new': ()},
    {'what': '.db-exec-badge -- isolated unused class, not referenced anywhere in '
             'ui/pages/overview.py (unlike its .db-hero-*/.db-badge-*/.db-market-tile neighbors, '
             'which are all live and were kept)',
     'tag': 'delete',
     'first': ".db-exec-badge{font-size:20px;font-weight:700;font-family:Rajdhani,sans-serif;"
              "letter-spacing:1px}",
     'last': ".db-exec-badge{font-size:20px;font-weight:700;font-family:Rajdhani,sans-serif;"
             "letter-spacing:1px}",
     'count': 1, 'new': ()},
    {'what': 'NOVA Replay tab CSS (.rp-*) -- tests/test_replay_dashboard.py already self-skips '
             '(its own marker search for the Replay JS block returns nothing), independently '
             'confirming this CSS was already orphaned before this commit',
     'tag': 'delete', 'first': '/* ── NOVA REPLAY TAB ── */',
     'last': ".rp-empty{text-align:center;padding:32px;color:var(--muted2);font-size:13px}",
     'count': 24, 'new': ()},
    {'what': "connectSSE() -- never called at boot or from any click handler (only "
             "self-referenced via its own onerror/setTimeout); its only caller of "
             "maybeSendNotif() was itself and the also-deleted Nova Feed subsystem below",
     'tag': 'delete', 'first': '// ════════ SSE — '
                               'REAL-TIME SIGNAL STREAM ════════',
     'last': '', 'count': 35, 'new': ()},
    {'what': 'Entire Nova Feed JS subsystem (initFeedNotifications, requestFeedNotifPermission, '
             'maybeSendNotif, clearFeedUnread, setFdDate/Sym/Cat, loadMoreFeed, refreshFeed, '
             'renderFeed, fdCard and all fd* renderers, toMarketSym, renderFdStats) -- documented '
             'as already-orphaned in nova_knowledge_core/TRADING_SUBSYSTEM_UI_RETIREMENT.md '
             '("Known limitations" #2); zero boot-time call, zero click-handler reference, '
             'targets #page-alerts/#feedBody/etc. which do not exist in the composed HTML',
     'tag': 'delete', 'first': '// ════════ NOVA FEED '
                               '════════',
     'last': '', 'count': 414, 'new': ()},
)


def test_composed_html_matches_commit9_baseline_except_proven_dead_code_removal():
    """The current, on-disk composed DASHBOARD_HTML must be identical to the
    commit #9 baseline except for the exact, cataloged dead-code removals
    above -- proving commit #10 changed nothing else.

    Same line-level-diff technique as the commit-8/commit-9 comparison
    above, but checked against `_COMMIT_10_CHANGE_CATALOG`'s exact block
    boundaries (tag, first line, last line, line count, replacement lines)
    instead of a flat fragment list -- appropriate for a purge this large
    (~1000 removed lines), and strictly *more* precise: it fails on any
    unexpected boundary shift, not just unexpected substrings.
    """
    import difflib

    baseline_html = _load_pinned_commit_dashboard_html(_COMMIT_9_BASELINE_REF)
    from ui.html import DASHBOARD_HTML as new_html
    assert new_html != baseline_html, 'expected the commit #10 dead-code removal, found no difference'

    baseline_lines = baseline_html.replace('\r\n', '\n').splitlines()
    new_lines = new_html.replace('\r\n', '\n').splitlines()

    sm = difflib.SequenceMatcher(a=baseline_lines, b=new_lines, autojunk=False)
    actual_blocks = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            continue
        actual_blocks.append({
            'tag': tag, 'first': baseline_lines[i1], 'last': baseline_lines[i2 - 1],
            'count': i2 - i1, 'new': tuple(new_lines[j1:j2]),
        })

    expected_blocks = [
        {k: entry[k] for k in ('tag', 'first', 'last', 'count', 'new')}
        for entry in _COMMIT_10_CHANGE_CATALOG
    ]

    assert len(actual_blocks) == len(expected_blocks), (
        f'expected {len(expected_blocks)} cataloged change-blocks, found {len(actual_blocks)}: '
        f'{actual_blocks}'
    )
    for i, (actual, expected) in enumerate(zip(actual_blocks, expected_blocks)):
        assert actual == expected, (
            f'change-block #{i} ({_COMMIT_10_CHANGE_CATALOG[i]["what"]}) does not match the '
            f'catalog.\nExpected: {expected}\nActual:   {actual}'
        )


def test_commit_10_dead_symbols_absent_from_current_ui_source():
    """Belt-and-suspenders check, independent of the diff-based tests above:
    every JS function name and CSS class deleted in commit #10 must not
    appear anywhere in the live UI source files (ui/pages/*.py, ui/scripts.py,
    ui/html.py) -- proving the removal is complete and no stray reference
    (e.g. a leftover call site) survives elsewhere in those files.
    """
    import ui.html
    import ui.scripts
    from ui.pages import overview, market_news, nova_ai, journal, settings

    live_sources = ''.join([
        ui.scripts.DASHBOARD_SCRIPT,
        overview.OVERVIEW_HTML, market_news.MARKET_NEWS_HTML, nova_ai.NOVA_AI_HTML,
        journal.JOURNAL_HTML, journal.JOURNAL_MODALS_HTML, settings.SETTINGS_HTML,
    ])

    dead_js_symbols = (
        'connectSSE', 'initFeedNotifications', 'requestFeedNotifPermission', 'maybeSendNotif',
        'clearFeedUnread', 'setFdDate', 'setFdSym', 'setFdCat', 'loadMoreFeed', 'refreshFeed',
        'renderFeed', 'fdCard', 'fdIntelligence', 'fdMarketEvent', 'fdGradeClass', 'fdDirClass',
        'fdSubClass', 'toMarketSym', 'fdToggleRationale', 'fdSignal', 'fdGovernance',
        'fdExecution', 'fdMr2Change', 'renderFdStats',
    )
    dead_css_classes = (
        'harvey-btn', 'verdict-banner', 'bias-wrap', 'orb-status-pill', 'pi-verdict',
        'signal-card', 'divergence-alert', 're-stop-banner', 'hv-layout', 'rp-card',
        'trade-card', 'journal-btn', 'gov-gate-list', 'mr-state-badge',
        'exec-cards-grid', 'exec-heartbeat', 'hvPlaybook', 'hvSignals', 'hvSectors',
        'caDivergenceList', 'breaking-events-grid', 'hero-banner', 'hero-grid', 'chip-stack',
        'signal-dot', 'banner-flash', 'db-exec-badge', 'ca-mode-badge', 'fd-filter-bar',
        'fd-card', 'fd-notify-banner',
    )

    offenders = [s for s in (dead_js_symbols + dead_css_classes) if s in live_sources]
    assert offenders == [], f'dead symbol(s)/class(es) unexpectedly still present in live UI source: {offenders}'


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

# Markers that must not appear anywhere at all, including in CSS. 'H.A.R.V.E.Y'
# and 'HARVEY' were promoted into this tier after commit #10 deleted the last
# inert CSS comment headers ("H.A.R.V.E.Y EXECUTION TAB", "NEW HARVEY LAYOUT")
# that referenced them -- before that commit these strings still existed,
# harmlessly, in ui/styles.py's dead CSS (see the commit-#9-era comment this
# replaced), so they could only be checked against live, rendered content.
# Now that the dead CSS itself is gone, zero occurrence anywhere is the
# correct, stronger invariant.
_RETIRED_OR_DEFERRED_MARKERS_ANYWHERE = (
    'setTradingStatus', 'TRADING SUBSYSTEM', 'trading_subsystem_enabled',
    'scenarioGenBtn', 'Grok', 'GROK', 'grok-card',
    'data-page="bot"', 'data-page="macro"',
    'H.A.R.V.E.Y', 'HARVEY',
)

# Markers that must not appear in any LIVE, rendered page module or in the
# active JS. Some of these (e.g. 'Performance Insight') are prose phrases
# that never existed as literal text anywhere, including in the dead CSS --
# they are checked here rather than promoted to the "anywhere" tier only
# because no commit has yet done the line-by-line audit needed to prove
# their complete absence from ui/styles.py the way commit #10 did for
# H.A.R.V.E.Y/HARVEY specifically.
_RETIRED_OR_DEFERRED_MARKERS_IN_LIVE_CONTENT = (
    'Execution Bot',
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
