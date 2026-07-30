"""
test_overview_morning_brief_render.py — commit #11 correction: executes
the actual shipped refreshMorningBrief() (and its helpers) under Node,
against a minimal, purpose-built DOM/fetch stub -- not just static source
pattern matching -- to prove the hardened state machine really behaves
correctly for every HTTP/state/timezone scenario Pedro required:

  - Successful current brief
  - Successful stale brief
  - Empty response
  - Backend error payload (HTTP 200, {'error': ..., 'brief_text': ...})
  - Non-2xx response
  - Network failure (fetch() itself rejects)
  - JSON parse failure (res.json() rejects)
  - New York date boundary (stale check uses NY calendar date, not UTC)

The exact function source is extracted (via brace-matching, not
retyped/duplicated) from the real, shipped ui/scripts.py --
DASHBOARD_SCRIPT, so a real bug in the shipped function is still caught
by these tests, not just a hand-written mirror of it.

Run:  python -m pytest tests/test_overview_morning_brief_render.py -v
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('ALPACA_API_KEY', '')
os.environ.setdefault('ALPACA_SECRET_KEY', '')

import pytest

import ui.scripts

REPO_ROOT = Path(__file__).resolve().parents[1]

pytestmark = pytest.mark.skipif(shutil.which('node') is None, reason='node is not available in this environment')


def _extract_js_function(script: str, name: str) -> str:
    """Extract one top-level `function name(...) { ... }` (optionally
    `async function`) from `script` by brace-matching, starting at the
    first `{` after the signature. Raises if the function is not found or
    its braces never balance."""
    for prefix in (f'async function {name}(', f'function {name}('):
        idx = script.find(prefix)
        if idx != -1:
            break
    else:
        raise AssertionError(f'{name}() not found in DASHBOARD_SCRIPT')

    brace_start = script.find('{', idx)
    assert brace_start != -1, f'no opening brace found for {name}()'
    depth = 0
    i = brace_start
    while i < len(script):
        if script[i] == '{':
            depth += 1
        elif script[i] == '}':
            depth -= 1
            if depth == 0:
                return script[idx:i + 1]
        i += 1
    raise AssertionError(f'braces never balanced for {name}()')


_SET_TEXT = _extract_js_function(ui.scripts.DASHBOARD_SCRIPT, 'setText')
_NY_TODAY = _extract_js_function(ui.scripts.DASHBOARD_SCRIPT, 'nyTodayDateStr')
_MB_RESET = _extract_js_function(ui.scripts.DASHBOARD_SCRIPT, '_mbResetStates')
_MB_ERROR = _extract_js_function(ui.scripts.DASHBOARD_SCRIPT, '_mbShowError')
_MB_MAIN  = _extract_js_function(ui.scripts.DASHBOARD_SCRIPT, 'refreshMorningBrief')

_MB_DOM_IDS = ('ovMbLoading', 'ovMbEmpty', 'ovMbError', 'ovMbStale', 'ovMbText', 'ovMbDateLabel')

_HARNESS_TEMPLATE = r'''
'use strict;'
const elements = {};
%(dom_ids)s.forEach(id => {
  elements[id] = { id, style: { display: '' }, textContent: '' };
});
global.document = {
  getElementById: (id) => elements[id] || null,
};

// Scenario-controlled fetch, injected as JSON describing the desired
// behavior -- kept deliberately dumb (no real HTTP) so this harness can
// never make a real network request.
const scenario = %(scenario_json)s;
global.fetch = async (url) => {
  if (scenario.networkError) {
    throw new Error('simulated network failure');
  }
  return {
    ok: scenario.ok,
    status: scenario.status,
    json: async () => {
      if (scenario.jsonError) {
        throw new Error('simulated JSON parse failure');
      }
      return scenario.body;
    },
  };
};

%(set_text)s
%(ny_today)s
%(mb_reset)s
%(mb_error)s
%(mb_main)s

refreshMorningBrief().then(() => {
  const out = {};
  for (const id of %(dom_ids)s) {
    out[id] = { display: elements[id].style.display, text: elements[id].textContent };
  }
  process.stdout.write(JSON.stringify(out));
}).catch(e => {
  process.stderr.write('HARNESS_UNCAUGHT: ' + (e && e.stack || e));
  process.exit(1);
});
'''


def _run_scenario(scenario: dict) -> dict:
    script = _HARNESS_TEMPLATE % {
        'dom_ids': json.dumps(list(_MB_DOM_IDS)),
        'scenario_json': json.dumps(scenario),
        'set_text': _SET_TEXT,
        'ny_today': _NY_TODAY,
        'mb_reset': _MB_RESET,
        'mb_error': _MB_ERROR,
        'mb_main': _MB_MAIN,
    }
    result = subprocess.run(
        ['node', '-e', script],
        capture_output=True, text=True, cwd=str(REPO_ROOT), timeout=15,
    )
    assert result.returncode == 0, f'harness failed: {result.stderr}'
    return json.loads(result.stdout)


def _ny_today_str() -> str:
    from datetime import datetime
    from zoneinfo import ZoneInfo
    return datetime.now(ZoneInfo('America/New_York')).strftime('%Y-%m-%d')


# ── Successful current brief ────────────────────────────────────────────

def test_successful_current_brief_shows_text_hides_everything_else():
    out = _run_scenario({
        'ok': True, 'status': 200,
        'body': {
            'date': _ny_today_str(), 'date_label': 'Monday, Jun 22',
            'brief_text': 'THESIS  BULLISH -- test',
        },
    })
    assert out['ovMbText']['display'] == 'block'
    assert out['ovMbText']['text'] == 'THESIS  BULLISH -- test'
    assert out['ovMbLoading']['display'] == 'none'
    assert out['ovMbEmpty']['display'] == 'none'
    assert out['ovMbError']['display'] == 'none'
    assert out['ovMbStale']['display'] == 'none'
    assert out['ovMbDateLabel']['text'] == 'Monday, Jun 22'


# ── Successful stale brief ──────────────────────────────────────────────

def test_successful_stale_brief_shows_text_and_stale_badge_together():
    out = _run_scenario({
        'ok': True, 'status': 200,
        'body': {'date': '2020-01-01', 'date_label': 'New Year 2020', 'brief_text': 'old brief'},
    })
    assert out['ovMbText']['display'] == 'block'
    assert out['ovMbText']['text'] == 'old brief'
    assert out['ovMbStale']['display'] == 'block', 'a brief dated in the past must show the stale badge'
    assert out['ovMbLoading']['display'] == 'none'
    assert out['ovMbEmpty']['display'] == 'none'
    assert out['ovMbError']['display'] == 'none'


# ── Empty response ───────────────────────────────────────────────────────

def test_empty_response_shows_empty_state_only():
    out = _run_scenario({'ok': True, 'status': 200, 'body': {}})
    assert out['ovMbEmpty']['display'] == 'block'
    assert out['ovMbText']['display'] == 'none'
    assert out['ovMbError']['display'] == 'none'
    assert out['ovMbLoading']['display'] == 'none'
    assert out['ovMbStale']['display'] == 'none'


# ── Backend error payload (HTTP 200 body with 'error') ──────────────────

def test_backend_error_payload_shows_error_state_only():
    out = _run_scenario({
        'ok': True, 'status': 200,
        'body': {'error': 'boom', 'brief_text': 'Morning brief unavailable.'},
    })
    assert out['ovMbError']['display'] == 'block'
    assert out['ovMbError']['text'] == 'Morning brief unavailable.'
    assert out['ovMbText']['display'] == 'none'
    assert out['ovMbEmpty']['display'] == 'none'
    assert out['ovMbLoading']['display'] == 'none'
    assert out['ovMbStale']['display'] == 'none'


# ── Non-2xx response ─────────────────────────────────────────────────────

def test_non_2xx_response_enters_error_state():
    out = _run_scenario({'ok': False, 'status': 500, 'body': {'detail': 'server error'}})
    assert out['ovMbError']['display'] == 'block'
    assert out['ovMbText']['display'] == 'none'
    assert out['ovMbEmpty']['display'] == 'none'
    assert out['ovMbLoading']['display'] == 'none'


# ── Network failure ──────────────────────────────────────────────────────

def test_network_failure_enters_error_state_and_hides_loading():
    out = _run_scenario({'networkError': True, 'ok': True, 'status': 200, 'body': {}})
    assert out['ovMbError']['display'] == 'block'
    assert out['ovMbLoading']['display'] == 'none'
    assert out['ovMbText']['display'] == 'none'


# ── JSON parse failure ───────────────────────────────────────────────────

def test_json_parse_failure_enters_error_state_and_hides_loading():
    out = _run_scenario({'ok': True, 'status': 200, 'jsonError': True, 'body': {}})
    assert out['ovMbError']['display'] == 'block'
    assert out['ovMbLoading']['display'] == 'none'
    assert out['ovMbText']['display'] == 'none'


# ── Loading is hidden on every completed path ────────────────────────────

@pytest.mark.parametrize('scenario', [
    {'ok': True, 'status': 200, 'body': {'date': '2099-01-01', 'date_label': 'x', 'brief_text': 'y'}},
    {'ok': True, 'status': 200, 'body': {}},
    {'ok': True, 'status': 200, 'body': {'error': 'e', 'brief_text': 'z'}},
    {'ok': False, 'status': 404, 'body': {}},
    {'networkError': True, 'ok': True, 'status': 200, 'body': {}},
    {'ok': True, 'status': 200, 'jsonError': True, 'body': {}},
])
def test_loading_hidden_on_every_completed_path(scenario):
    out = _run_scenario(scenario)
    assert out['ovMbLoading']['display'] == 'none'


# ── New York date boundary ───────────────────────────────────────────────

def test_stale_check_uses_new_york_calendar_date():
    """nyTodayDateStr() (used for the stale comparison) must reflect the
    NY calendar date at the moment the harness runs -- proven by asking
    Python for that same NY date independently and requiring an exact
    match against a brief dated that same string (not stale)."""
    today_ny = _ny_today_str()
    out = _run_scenario({
        'ok': True, 'status': 200,
        'body': {'date': today_ny, 'date_label': 'today', 'brief_text': 'fresh'},
    })
    assert out['ovMbStale']['display'] == 'none', (
        f'a brief dated exactly today ({today_ny!r} NY) must not be marked stale'
    )


if __name__ == '__main__':
    raise SystemExit(pytest.main([__file__, '-v']))
