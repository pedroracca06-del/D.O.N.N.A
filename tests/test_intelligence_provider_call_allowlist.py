"""
test_intelligence_provider_call_allowlist.py — NOVA Intelligence V1 commit #7:
the repository-wide direct-provider-call static safety check (spec §15,
test item 3; §15.1a's temporary allowlist; §15.1b's archived-code inventory).

This check was designed in the spec (nova_knowledge_core/NOVA_INTELLIGENCE_V1_SPECIFICATION.md
§15.1a) as early as commit #2, but was never actually implemented in commits
#2-#6 -- confirmed by its absence from every existing test file. Added alongside
the first feature (Market/News Summary) that has no legacy call site of its own
to migrate.

Enforces (§15's test item 3A): no file outside `intelligence/providers/*.py`,
and outside the current exact temporary allowlist below, may import
`anthropic`, import `openai`, or contain a raw HTTP call to a known
AI-provider hostname (api.anthropic.com, api.x.ai). Also confirms no
`grok_adapter.py` exists anywhere in `intelligence/` (spec §5, FINAL).

Allowlist entries name an exact file and function -- never a broad
directory, module, or wildcard glob (spec §15.1a). The allowlist contains
only the two Grok findings' three call sites, reserved for commit #8:
  - main.py::fetch_grok_intelligence  (raw requests.post to api.x.ai) -- spec
    §2 finding #7's production fetch path.
  - main.py::debug_grok               (its own independent raw requests.post
    to the same api.x.ai endpoint, for diagnostic probing) -- spec §2 finding
    #7's second cited line number (main.py:593 in the original audit). The
    spec's human-readable table collapses both into one "Grok market-sentiment
    card" row citing two line numbers; this AST-level check keys on
    (file, enclosing function) pairs, so the same feature correctly yields
    two separate allowlist entries here.
  - services/news.py::_llm_classify   (openai.OpenAI client, base_url=api.x.ai)
    -- spec §2 finding #8, maps 1:1.
Two spec findings (#7, #8) -> three allowlist entries. Verified by reading
main.py:220 (fetch_grok_intelligence) and main.py:576 (debug_grok) directly:
both independently construct a raw POST to https://api.x.ai/v1/chat/completions;
neither calls the other. Not a miscount, not an undocumented third Grok site.

The two Anthropic entries this allowlist held during commits #2-#6
(services/assistant.py's direct call, main.py's Journal Review direct call)
were removed by commits #5 and #6 respectively and must NEVER reappear here
-- this file explicitly asserts both call sites are gone, not just silently
omitted from the allowlist.

CORRECTIVE WORK (this commit, approved by Pedro): building this check
originally surfaced a pre-existing, unrelated gap -- core/config.py's shared
Anthropic `client` was being called directly, live, by two of the three
functions spec §4 lists as "deferred" in engines/engines.py: build_scenario_engine()
(reachable from GET /dashboard-data, GET /scenario-data, POST /scenario-data/refresh)
and generate_morning_brief()/send_morning_brief() (reachable from the daily
morning_brief_loop() background task and from GET /send-morning-brief). Both
have now been disconnected from active runtime (see _ARCHIVED_CODE_INVENTORY
below): the dashboard payload no longer calls build_scenario_engine(), the
three routes above return a static disabled-feature response and never invoke
their underlying deferred function, and morning_brief_loop() no longer
contains a send_morning_brief() branch (the unrelated, deterministic
compute_and_deliver_morning_brief() compact-brief branch is untouched and
still scheduled). The deferred function bodies themselves, and all historical
Morning Brief / Scenario Engine data, are preserved unmodified -- this is a
disconnection from active runtime, not a deletion. See
nova_knowledge_core/NOVA_INTELLIGENCE_V1_SPECIFICATION.md §15.1b and this
commit's report for the full writeup.

No reachable Anthropic call site is retained under any "known gap" label as
of this commit -- see _ARCHIVED_CODE_INVENTORY's docstring for exactly what
remains and why it is now archived-code, not a pending decision.

Run:  python -m pytest tests/test_intelligence_provider_call_allowlist.py -v
"""
from __future__ import annotations

import ast
import os
import socket
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('ALPACA_API_KEY', '')
os.environ.setdefault('ALPACA_SECRET_KEY', '')

REPO_ROOT = Path(__file__).resolve().parents[1]
INTELLIGENCE_DIR = REPO_ROOT / 'intelligence'

# Directories never scanned: version control, caches, the Node.js MCP
# submodule (not Python), and tests/ itself -- test files intentionally
# import anthropic/openai to mock provider behavior and are not reachable
# from the running application.
_EXCLUDED_DIR_PARTS = {'.git', '__pycache__', 'node_modules', 'tests', '.venv', 'venv'}

_FORBIDDEN_IMPORT_ROOTS = ('anthropic', 'openai')
_FORBIDDEN_HOSTNAMES = ('api.anthropic.com', 'api.x.ai')

# (relative file path, exact enclosing function name) -- §15.1a FINAL scope:
# only the two Grok findings' three call sites remain. Nothing else may be
# added; this only shrinks, in commit #8.
_ALLOWLIST: set[tuple[str, str]] = {
    ('main.py', 'fetch_grok_intelligence'),
    ('main.py', 'debug_grok'),
    ('services/news.py', '_llm_classify'),
}

# ── ARCHIVED-CODE INVENTORY (§15.1b, permanent) ──────────────────────────
#
# core/config.py's module-level `from anthropic import Anthropic` / `client`
# construction (core/config.py:~161) is the one direct-anthropic-import site
# this AST scan can ever detect outside intelligence/providers/*.py -- the
# scanner only flags direct `import anthropic`/`from anthropic import`
# statements and hostname literals, not indirect re-exports of an
# already-constructed client object. That means this entry can never shrink
# to zero purely by fixing call sites elsewhere: engines/engines.py and
# engines/reasoning.py both do `from core.config import client`, which is
# invisible to the scanner even after every consumer of that import is
# proven unreachable.
#
# What matters for safety is not the import itself but whether anything
# reachable from active application startup, routes, workers, schedules, or
# UI actually calls `.messages.create()` on that shared client. As of this
# commit, every known consumer is accounted for:
#
#   - build_scenario_engine() (engines/engines.py) -- was called
#     unconditionally from build_dashboard_payload() (GET /dashboard-data)
#     and directly from GET /scenario-data / POST /scenario-data/refresh.
#     All three call sites are now disconnected (see
#     test_archived_scenario_engine_is_unreachable_from_dashboard_route and
#     test_scenario_data_routes_return_disabled_status_and_never_call_engine
#     below). The function body itself is preserved, unmodified, as
#     historical/inert code.
#   - generate_morning_brief() / send_morning_brief() (engines/engines.py) --
#     was reachable from main.py's morning_brief_loop() background task
#     (started at app startup) and from GET /send-morning-brief. Both are
#     now disconnected (see
#     test_archived_morning_brief_is_unreachable_from_background_loop and
#     test_send_morning_brief_route_returns_disabled_status_and_never_calls_it
#     below). The unrelated, deterministic compute_and_deliver_morning_brief()
#     compact-brief branch in the same loop function is untouched and
#     remains scheduled (test_deterministic_compact_brief_remains_scheduled).
#   - build_performance_memory() (engines/engines.py) -- imported by main.py
#     but never called anywhere; confirmed dead before this commit and
#     unchanged by it (test_archived_performance_memory_is_currently_dead_code).
#   - engines/reasoning.py's legacy setup-grading pipeline
#     (evaluate_with_claude) -- already proven unreachable by the existing,
#     separate test_intelligence_phase0_safety.py; not re-proven here.
#
# This entry documents dead code -- it is never permission for a new,
# reachable direct provider call, and it must never be moved into
# _ALLOWLIST (§15.1a is for pending migration work; this is the opposite).
_ARCHIVED_CODE_INVENTORY: set[tuple[str, str]] = {
    ('core/config.py', '<module level>'),
}

# Explicitly retired entries -- must never reappear as findings, in the
# allowlist or otherwise (commits #5 and #6 moved these behind the gateway).
_RETIRED_ENTRIES: set[tuple[str, str]] = {
    ('services/assistant.py', 'call_assistant_llm'),
    ('main.py', 'journal_analyze'),
}


@pytest.fixture(autouse=True)
def _block_real_network(monkeypatch):
    """No test in this file should ever open a real network socket (spec §15
    item 18) -- this file is static AST analysis plus a handful of in-process
    FastAPI TestClient calls against routes that, after this commit's
    corrective work, never construct a live provider client or send an
    external Telegram request."""
    real_connect = socket.socket.connect

    def _guard(self, address, *args, **kwargs):
        host = address[0] if isinstance(address, tuple) else address
        if host in ('127.0.0.1', 'localhost', '::1'):
            return real_connect(self, address, *args, **kwargs)
        raise AssertionError(f'real network access attempted during provider-call allowlist tests: {address!r}')

    monkeypatch.setattr(socket.socket, 'connect', _guard)
    yield


def _iter_python_files():
    for root, dirs, files in os.walk(REPO_ROOT):
        dirs[:] = [d for d in dirs if d not in _EXCLUDED_DIR_PARTS]
        rel_root = Path(root).relative_to(REPO_ROOT)
        if str(rel_root).split(os.sep)[0] in _EXCLUDED_DIR_PARTS:
            continue
        for fname in files:
            if fname.endswith('.py'):
                yield Path(root) / fname


def _enclosing_function(tree: ast.Module, lineno: int) -> str | None:
    """Innermost def/async def whose body contains lineno, or None (module level)."""
    best = None
    best_span = None
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            end = getattr(node, 'end_lineno', None)
            if end is None:
                continue
            if node.lineno <= lineno <= end:
                span = end - node.lineno
                if best_span is None or span < best_span:
                    best = node.name
                    best_span = span
    return best


def _find_offenders() -> list[tuple[str, str, str]]:
    """Returns (relative_path, function_name_or_'<module level>', reason) for
    every direct-provider-call site found outside intelligence/providers/*.py."""
    offenders = []
    providers_dir = INTELLIGENCE_DIR / 'providers'

    for py_file in _iter_python_files():
        if providers_dir in py_file.parents:
            continue  # the one sanctioned location (spec §6.1)

        try:
            source = py_file.read_text(encoding='utf-8')
            tree = ast.parse(source, filename=str(py_file))
        except (SyntaxError, UnicodeDecodeError):
            continue

        rel_path = str(py_file.relative_to(REPO_ROOT)).replace('\\', '/')

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split('.')[0] in _FORBIDDEN_IMPORT_ROOTS:
                        fn = _enclosing_function(tree, node.lineno) or '<module level>'
                        offenders.append((rel_path, fn, f'import {alias.name}'))
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.module.split('.')[0] in _FORBIDDEN_IMPORT_ROOTS:
                    fn = _enclosing_function(tree, node.lineno) or '<module level>'
                    offenders.append((rel_path, fn, f'from {node.module} import ...'))
            elif isinstance(node, ast.Call):
                for arg in list(node.args) + [kw.value for kw in node.keywords]:
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        if any(host in arg.value for host in _FORBIDDEN_HOSTNAMES):
                            fn = _enclosing_function(tree, node.lineno) or '<module level>'
                            offenders.append((rel_path, fn, f'call with hostname literal {arg.value!r}'))

    return offenders


# ═══════════════════════════════════════════════════════════════════════
# (A) Active-runtime check (spec §15's test item 3A)
# ═══════════════════════════════════════════════════════════════════════

def test_every_direct_provider_call_site_is_on_the_exact_allowlist():
    """No NEW, unaccounted-for direct-provider-call site exists beyond the
    three Grok entries and the one archived-code entry documented above
    (core/config.py's module-level import). If a third category of finding
    ever appears, that is new and must be investigated -- it is not
    automatically covered by either exclusion."""
    offenders = _find_offenders()
    unexpected = [
        (path, fn, reason) for (path, fn, reason) in offenders
        if (path, fn) not in _ALLOWLIST and (path, fn) not in _ARCHIVED_CODE_INVENTORY
    ]
    assert unexpected == [], (
        f'Found direct provider call site(s) not on the temporary allowlist and not the '
        f'documented archived-code inventory: {unexpected}. Every file outside '
        'intelligence/providers/*.py must route through intelligence.gateway.request_intelligence(), '
        'except the exact §15.1a allowlist entries and the §15.1b archived-code inventory.'
    )


def test_allowlist_and_archived_code_never_overlap():
    assert _ALLOWLIST.isdisjoint(_ARCHIVED_CODE_INVENTORY)


def test_allowlist_contains_only_the_two_grok_findings_three_entries():
    """§15.1a FINAL scope -- no fourth entry, no wildcard, no directory-level
    entry may ever be added here. Exactly three function-level entries,
    corresponding to the specification's two Grok findings (finding #7's two
    call sites plus finding #8's one)."""
    assert _ALLOWLIST == {
        ('main.py', 'fetch_grok_intelligence'),
        ('main.py', 'debug_grok'),
        ('services/news.py', '_llm_classify'),
    }


def test_every_allowlist_entry_corresponds_to_a_real_reachable_call_site():
    """An allowlist entry is evidence of pending migration work, never a
    standing exception with nothing behind it (spec §15.1a)."""
    offenders = _find_offenders()
    found_pairs = {(path, fn) for (path, fn, _reason) in offenders}
    for entry in _ALLOWLIST:
        assert entry in found_pairs, f'allowlist entry {entry} does not correspond to any real direct-provider-call site'


def test_retired_assistant_and_journal_review_call_sites_are_gone():
    """Commits #5 and #6 moved these behind the gateway -- they must never
    appear as a direct-provider-call finding again, allowlisted or not."""
    offenders = _find_offenders()
    found_pairs = {(path, fn) for (path, fn, _reason) in offenders}
    for entry in _RETIRED_ENTRIES:
        assert entry not in found_pairs, f'retired call site {entry} reappeared as a direct provider call'
    for entry in _RETIRED_ENTRIES:
        assert entry not in _ALLOWLIST, f'retired call site {entry} must not be present in the allowlist'


def test_no_grok_adapter_module_exists_anywhere_in_intelligence():
    """spec §5 FINAL: no providers/grok_adapter.py, inert or otherwise, in any V1 commit."""
    matches = list(INTELLIGENCE_DIR.rglob('*grok*'))
    assert matches == [], f'unexpected grok-named file(s) found under intelligence/: {matches}'


def test_market_summary_prompt_module_is_not_itself_an_offender():
    """The commit #7 feature file must be clean under this same check -- it
    imports nothing from services/engines/anthropic/openai (also directly
    verified in test_intelligence_prompts_market_summary.py)."""
    offenders = _find_offenders()
    market_summary_hits = [o for o in offenders if o[0] == 'intelligence/prompts/market_summary.py']
    assert market_summary_hits == []


# ═══════════════════════════════════════════════════════════════════════
# (B) Archived-code inventory, proven unreachable (§15.1b) -- NOT §15.1a
# ═══════════════════════════════════════════════════════════════════════
#
# §15.1b requires every archived-code entry to be *proven* unreachable from
# startup/routes/workers/schedules/UI, via a named test. Prior to this
# commit's corrective work, two of core/config.py's three consumers in
# engines/engines.py were proven REACHABLE, not unreachable -- that gap has
# now been closed by disconnecting the routes/loop/dashboard-payload call
# sites (production code changes in main.py, engines/engines.py, ui/html.py),
# and the tests below prove the corrected state.

def test_archived_core_config_client_import_still_present():
    """Confirms the archived-code inventory entry is honest, not swept under
    the rug: engines/engines.py still imports core.config.client (the
    deferred function bodies -- build_scenario_engine, generate_morning_brief,
    send_morning_brief, build_performance_memory -- are preserved, not
    deleted). If this import is ever removed, this test starts failing and
    the _ARCHIVED_CODE_INVENTORY entry above should be reconsidered."""
    engines_source = (REPO_ROOT / 'engines' / 'engines.py').read_text(encoding='utf-8')
    tree = ast.parse(engines_source)
    imports_client = any(
        isinstance(node, ast.ImportFrom) and node.module == 'core.config'
        and any(alias.name == 'client' for alias in node.names)
        for node in ast.walk(tree)
    )
    assert imports_client, (
        'expected engines/engines.py to still import core.config.client (preserved, deferred '
        'function bodies) -- if this no longer holds, revisit the _ARCHIVED_CODE_INVENTORY entry above'
    )


def test_archived_scenario_engine_is_unreachable_from_dashboard_route():
    """Proves build_scenario_engine() -- one of §4's "deferred" features -- is
    no longer called from build_dashboard_payload(), which backs main.py's
    live GET /dashboard-data route. This is the corrective fix for what was
    previously a documented, live gap."""
    import inspect
    from engines.engines import build_dashboard_payload
    source = inspect.getsource(build_dashboard_payload)
    assert 'build_scenario_engine()' not in source, (
        'build_dashboard_payload() must never call build_scenario_engine() -- '
        'Scenario Engine is deferred per spec §4 and must stay disconnected from GET /dashboard-data'
    )
    assert "'scenarios'" not in source, (
        'build_dashboard_payload() must not surface a scenarios field sourced from the '
        'deferred Scenario Engine'
    )


def test_scenario_data_routes_return_disabled_status_and_never_call_engine(monkeypatch):
    """GET /scenario-data and POST /scenario-data/refresh must return the
    repository's established disabled-feature response contract (matching
    e.g. GET /close-all's {'status': 'TRADING_SUBSYSTEM_DISABLED'} pattern)
    and must never invoke build_scenario_engine() -- proven at runtime, not
    just by source inspection, by making the underlying function raise if
    called."""
    import main as _main
    from fastapi.testclient import TestClient

    def _boom(*a, **kw):
        raise AssertionError('build_scenario_engine() must not be called by a disabled route')

    monkeypatch.setattr('engines.engines.build_scenario_engine', _boom, raising=True)

    client = TestClient(_main.app)

    r1 = client.get('/scenario-data')
    assert r1.status_code == 200
    assert r1.json() == {'status': 'SCENARIO_ENGINE_DISABLED'}

    r2 = client.post('/scenario-data/refresh')
    assert r2.status_code == 200
    assert r2.json() == {'status': 'SCENARIO_ENGINE_DISABLED'}


def test_scenario_engine_source_no_longer_imported_by_main():
    """main.py must not import build_scenario_engine at all once its two
    routes and the dashboard payload no longer call it -- an unused import
    would misrepresent the route bodies as still wired to the live engine."""
    main_source = (REPO_ROOT / 'main.py').read_text(encoding='utf-8')
    tree = ast.parse(main_source)
    imported_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == 'engines.engines':
            imported_names.update(alias.name for alias in node.names)
    assert 'build_scenario_engine' not in imported_names


def test_scenario_engine_controls_absent_from_active_ui():
    """The deferred Scenario Engine panel, Generate button, request logic,
    and rendering code must be fully removed from the active dashboard --
    not merely hidden, and not left as a visible control that would only
    ever produce a deferred-feature error."""
    from ui.html import DASHBOARD_HTML
    html = DASHBOARD_HTML
    for marker in (
        'scenarioGenBtn', 'scenarioGrid', 'scenarioMeta',
        'renderScenarios', 'refreshScenarios',
        'scenario-grid', 'scenario-card', 'scenario-header', 'scenario-meta',
        '/scenario-data',
    ):
        assert marker not in html, f'dead/active Scenario Engine reference {marker!r} still present in DASHBOARD_HTML'


# ── Morning Brief ─────────────────────────────────────────────────────────

def test_archived_morning_brief_is_unreachable_from_background_loop():
    """Proves send_morning_brief() -- also listed under §4's deferred morning
    brief -- is no longer called from main.py's morning_brief_loop() startup
    background task. The unrelated deterministic compact brief must remain."""
    import inspect
    import main as _main
    loop_source = inspect.getsource(_main.morning_brief_loop)
    # Checks for an actual call/reference to the function object, not merely
    # its name appearing in an explanatory comment (the loop's own docstring
    # comment names both functions in prose to explain what was removed and why).
    assert 'send_morning_brief(' not in loop_source, (
        'morning_brief_loop() must never call send_morning_brief() -- the AI-generated '
        'Morning Brief is deferred per spec §4 and must stay disconnected from the startup loop'
    )
    assert 'await asyncio.to_thread(send_morning_brief)' not in loop_source


def test_deterministic_compact_brief_remains_scheduled():
    """The unrelated, deterministic compute_and_deliver_morning_brief() branch
    (engines/morning_brief.py -- contains no anthropic/client/request_intelligence
    call at all) must remain wired into the same startup loop on its existing
    9:00-9:25 AM schedule -- disconnecting the AI Morning Brief must not have
    taken this down with it."""
    import inspect
    import main as _main
    loop_source = inspect.getsource(_main.morning_brief_loop)
    assert 'compute_and_deliver_morning_brief' in loop_source
    assert "ny.hour == 9 and ny.minute < 25" in loop_source

    morning_brief_module_source = (REPO_ROOT / 'engines' / 'morning_brief.py').read_text(encoding='utf-8')
    tree = ast.parse(morning_brief_module_source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert node.names[0].name.split('.')[0] not in _FORBIDDEN_IMPORT_ROOTS
        if isinstance(node, ast.ImportFrom) and node.module:
            assert node.module.split('.')[0] not in _FORBIDDEN_IMPORT_ROOTS


def test_send_morning_brief_route_returns_disabled_status_and_never_calls_it(monkeypatch):
    """GET /send-morning-brief must return the established disabled-feature
    response contract and must never invoke send_morning_brief() -- proven at
    runtime by making the underlying function raise if called."""
    import main as _main
    from fastapi.testclient import TestClient

    def _boom(*a, **kw):
        raise AssertionError('send_morning_brief() must not be called by a disabled route')

    monkeypatch.setattr('engines.engines.send_morning_brief', _boom, raising=True)

    client = TestClient(_main.app)
    r = client.get('/send-morning-brief')
    assert r.status_code == 200
    assert r.json() == {'status': 'MORNING_BRIEF_DISABLED'}


def test_morning_brief_source_no_longer_imported_by_main():
    """main.py must not import send_morning_brief at all once its loop branch
    and its route no longer call it."""
    main_source = (REPO_ROOT / 'main.py').read_text(encoding='utf-8')
    tree = ast.parse(main_source)
    imported_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == 'engines.engines':
            imported_names.update(alias.name for alias in node.names)
    assert 'send_morning_brief' not in imported_names


def test_disabled_morning_brief_paths_never_send_telegram_or_write_state(monkeypatch):
    """Neither the disabled GET /send-morning-brief route nor the corrected
    morning_brief_loop() may send a Telegram message or write new
    last-sent-date delivery state. Proven at runtime by making both the
    Telegram sender and the JSON writer raise if called, then exercising the
    route and one iteration's worth of the loop's guarded body."""
    import inspect
    import main as _main
    from fastapi.testclient import TestClient

    def _telegram_boom(*a, **kw):
        raise AssertionError('send_telegram_message() must not be called by a disabled Morning Brief path')

    def _write_boom(*a, **kw):
        raise AssertionError('write_json_file() must not be called by a disabled Morning Brief path')

    monkeypatch.setattr('core.config.send_telegram_message', _telegram_boom, raising=True)
    monkeypatch.setattr('core.state.write_json_file', _write_boom, raising=True)

    client = TestClient(_main.app)
    r = client.get('/send-morning-brief')
    assert r.json() == {'status': 'MORNING_BRIEF_DISABLED'}

    # morning_brief_loop() itself no longer references either function --
    # confirmed statically, since actually running the infinite loop isn't
    # feasible in a unit test.
    loop_source = inspect.getsource(_main.morning_brief_loop)
    assert 'send_telegram_message' not in loop_source
    assert 'write_json_file' not in loop_source
    assert 'MORNING_BRIEF_FILE' not in loop_source


def test_archived_performance_memory_is_currently_dead_code():
    """Unlike the two entries above, build_performance_memory() is imported
    by main.py but never invoked anywhere -- confirming it does NOT need any
    corrective disconnection work; it was already dead before this commit
    and remains dead after it."""
    main_source = (REPO_ROOT / 'main.py').read_text(encoding='utf-8')
    tree = ast.parse(main_source)
    call_names = {
        node.func.id for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert 'build_performance_memory' not in call_names
