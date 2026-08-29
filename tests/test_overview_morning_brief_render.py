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
# refreshMorningBrief() renders the brief body as markup through this helper,
# so the harness must carry it too -- omitting it fails at runtime with a
# ReferenceError rather than exercising any of the state logic under test.
_MB_BODY  = _extract_js_function(ui.scripts.DASHBOARD_SCRIPT, '_mbRenderBody')
# Display-only de-duplication of the body against the headline and the facts
# footer, plus humanizeCode() which the footer uses for `confidence`.
_MB_DEDUPE = _extract_js_function(ui.scripts.DASHBOARD_SCRIPT, '_mbDedupeBody')
_HUMANIZE  = _extract_js_function(ui.scripts.DASHBOARD_SCRIPT, 'humanizeCode')


def _extract_js_const(script: str, name: str) -> str:
    """Extract a single-line top-level `const name = ...;` declaration.
    humanizeCode() closes over one, so the harness has to carry it too."""
    for line in script.split('\n'):
        if line.startswith(f'const {name}'):
            return line
    raise AssertionError(f'const {name} not found in DASHBOARD_SCRIPT')


_KEEP_UPPER = _extract_js_const(ui.scripts.DASHBOARD_SCRIPT, '_KEEP_UPPER')
# _mbRenderBody() closes over this pattern to split "THESIS <value>" style
# engine lines into a label and its value, so the harness must carry it too.
_MB_SECTION = _extract_js_const(ui.scripts.DASHBOARD_SCRIPT, '_MB_SECTION')
_MB_MAIN  = _extract_js_function(ui.scripts.DASHBOARD_SCRIPT, 'refreshMorningBrief')

_MB_DOM_IDS = ('ovMbLoading', 'ovMbEmpty', 'ovMbError', 'ovMbStale', 'ovMbText',
               'ovMbDateLabel', 'ovMbHeadline', 'ovMbFooter')

_HARNESS_TEMPLATE = r'''
'use strict;'
const elements = {};
%(dom_ids)s.forEach(id => {
  const el = { id, style: { display: '' }, textContent: '' };
  // Emulate the single DOM behavior this code path relies on: assigning
  // innerHTML replaces the element's rendered text. The brief body is now
  // written as markup (_mbRenderBody), so a stub that only tracks
  // textContent would report an empty string for a brief that did render.
  Object.defineProperty(el, 'innerHTML', {
    get() { return el._html || ''; },
    set(v) {
      el._html = String(v);
      el.textContent = el._html
        .replace(/<[^>]*>/g, '')
        .replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&amp;/g, '&');
    },
  });
  elements[id] = el;
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
%(mb_section)s
%(mb_body)s
%(keep_upper)s
%(humanize)s
%(mb_dedupe)s
%(mb_main)s

refreshMorningBrief().then(() => {
  const out = {};
  for (const id of %(dom_ids)s) {
    out[id] = { display: elements[id].style.display, text: elements[id].textContent,
                html: elements[id]._html || '' };
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
        'mb_section': _MB_SECTION,
        'mb_body': _MB_BODY,
        'keep_upper': _KEEP_UPPER,
        'humanize': _HUMANIZE,
        'mb_dedupe': _MB_DEDUPE,
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
    # The engine's labelled line is now rendered as a real label/value pair
    # rather than a machine-style run-on. The label is title-cased for
    # display; the VALUE survives byte-for-byte.
    assert out['ovMbText']['html'] == (
        '<dl class="ov-mb-sections"><dt>Thesis</dt><dd>BULLISH -- test</dd></dl>'
    )
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


# ── Body de-duplication against the headline and facts footer ────────────
#
# build_compact_brief() emits brief_text as five labelled lines and ALSO
# returns three of those values as separate fields that Overview renders as
# the headline and the facts footer. These tests pin the display-only rule
# that a body line is dropped when, and only when, its value is genuinely
# already on screen. The engine payload is never modified.

_THESIS = 'NQ accepting above the overnight high with participation confirming'
_DRAW = 'PWH 18,825 (83pts above) -- 0 above / 6 below untapped'
_WATCH = 'Resolves bullish if PWH holds and RVOL expands above 1.0'
_PARTICIPATION = 'STRONG (RVOL 1.42x) -- session type: TREND'
_MACRO = 'LOW risk -- next event: CPI 10:00 ET'


def _full_brief_body():
    """The exact five-line shape build_compact_brief() assembles."""
    return (
        f'THESIS       CONTESTED [MEDIUM] -- {_THESIS}\n'
        f'DRAW         {_DRAW}\n'
        f'PARTICIPATION {_PARTICIPATION}\n'
        f'MACRO        {_MACRO}\n'
        f'WATCH        {_WATCH}'
    )


def _full_scenario(**overrides):
    body = {
        'date': _ny_today_str(),
        'date_label': 'Monday, Aug 17',
        'thesis': _THESIS,
        'liquidity_draw': _DRAW,
        'key_question': _WATCH,
        'confidence': 'MEDIUM',
        'brief_text': _full_brief_body(),
    }
    body.update(overrides)
    return {'ok': True, 'status': 200, 'body': body}


def test_body_does_not_repeat_the_rendered_headline():
    out = _run_scenario(_full_scenario())
    assert out['ovMbHeadline']['text'] == _THESIS
    body = out['ovMbText']['text']
    assert _THESIS not in body, (
        'the headline sentence must not be repeated in the body:\n' + body
    )


def test_body_does_not_repeat_facts_already_in_the_footer():
    out = _run_scenario(_full_scenario())
    body = out['ovMbText']['text']
    footer = out['ovMbFooter']['text']
    assert _DRAW in footer and _WATCH in footer, 'footer must still carry both facts'
    assert _DRAW not in body, 'Draw is in the footer; the body must not restate it'
    assert _WATCH not in body, 'Watch is in the footer; the body must not restate it'


def test_unique_intelligence_survives_deduplication():
    """The two lines with no duplicate elsewhere must always be preserved,
    along with the thesis STATE, which appears nowhere else on the page."""
    out = _run_scenario(_full_scenario())
    body = out['ovMbText']['text']
    assert _PARTICIPATION in body, 'PARTICIPATION is unique and must survive'
    assert _MACRO in body, 'MACRO is unique and must survive'
    assert 'CONTESTED' in body, 'thesis state is unique and must survive'
    assert out['ovMbText']['display'] == 'block'


def test_body_collapses_when_everything_is_already_rendered():
    """A brief whose body carries nothing beyond the headline and the footer
    facts must hide the body rather than render an empty block."""
    out = _run_scenario(_full_scenario(
        brief_text=f'THESIS  {_THESIS}\nDRAW    {_DRAW}\nWATCH   {_WATCH}',
    ))
    assert out['ovMbText']['display'] == 'none'
    assert out['ovMbHeadline']['text'] == _THESIS
    assert _DRAW in out['ovMbFooter']['text']


def test_non_duplicated_body_is_left_untouched():
    """Regression guard: when nothing is duplicated, every line survives
    exactly as the engine emitted it."""
    out = _run_scenario(_full_scenario(
        thesis='A headline that appears nowhere in the body',
        brief_text=f'PARTICIPATION {_PARTICIPATION}\nMACRO        {_MACRO}',
    ))
    body = out['ovMbText']['text']
    assert _PARTICIPATION in body
    assert _MACRO in body
    assert out['ovMbText']['display'] == 'block'


def test_deduplication_does_not_disturb_the_degraded_states():
    """Empty, error and stale paths must behave exactly as before."""
    empty = _run_scenario({'ok': True, 'status': 200, 'body': {}})
    assert empty['ovMbEmpty']['display'] == 'block'
    assert empty['ovMbText']['display'] == 'none'

    failed = _run_scenario({'ok': False, 'status': 500, 'body': {}})
    assert failed['ovMbError']['display'] == 'block'

    stale = _run_scenario(_full_scenario(date='2020-01-01'))
    assert stale['ovMbStale']['display'] == 'block'
    assert stale['ovMbText']['display'] == 'block', 'a stale brief still shows its body'


# ── Bracketed values already rendered in the facts footer ────────────────
#
# build_compact_brief() stamps the confidence grade into the THESIS line as a
# bracketed token ("CONTESTED [MEDIUM] -- <thesis>") AND returns it as the
# `confidence` field, which the facts footer renders inches away as
# "Confidence Medium". Once the headline sentence is cut out of that line,
# the surviving residue used to read "THESIS CONTESTED [MEDIUM]" -- the
# grade shown twice, side by side. These tests pin the rule that such a
# bracketed copy is dropped when, and ONLY when, that exact value is already
# on screen in the footer.


def test_confidence_is_not_shown_in_both_the_body_and_the_footer():
    out = _run_scenario(_full_scenario())
    body = out['ovMbText']['text']
    footer = out['ovMbFooter']['text']
    assert 'Medium' in footer, 'the footer is where Confidence belongs'
    assert '[MEDIUM]' not in body, (
        'confidence is already rendered in the facts footer; the body must '
        'not restate it as a bracketed token:\n' + body
    )
    assert 'MEDIUM' not in body, 'no casing of the duplicated grade may remain'


def test_thesis_state_still_survives_that_removal():
    """Dropping the duplicated grade must not take the thesis STATE with it --
    the state appears nowhere else on the page."""
    out = _run_scenario(_full_scenario())
    assert 'CONTESTED' in out['ovMbText']['text']
    assert out['ovMbText']['display'] == 'block'


def test_bracketed_value_not_in_the_footer_is_preserved():
    """Only values the footer is genuinely showing are removed. A bracketed
    token carrying something else must survive untouched."""
    out = _run_scenario(_full_scenario(
        brief_text=f'THESIS       CONTESTED [HIGH] -- {_THESIS}\n'
                   f'MACRO        {_MACRO}',
    ))
    body = out['ovMbText']['text']
    assert '[HIGH]' in body, (
        'HIGH is not the rendered confidence, so it is unique context and '
        'must be preserved:\n' + body
    )


def test_parenthesised_measurement_context_is_never_stripped():
    """Only square-bracketed tokens are candidates. Parenthesised groups carry
    measurements that appear nowhere else and must always survive."""
    out = _run_scenario(_full_scenario())
    assert '(RVOL 1.42x)' in out['ovMbText']['text']


def test_first_body_line_identical_to_the_headline_is_omitted():
    """The literal case from the requirement: a first body line that IS the
    headline, with no label and no extra context, is dropped entirely."""
    out = _run_scenario(_full_scenario(
        brief_text=f'{_THESIS}\nMACRO        {_MACRO}',
    ))
    body = out['ovMbText']['text']
    assert out['ovMbHeadline']['text'] == _THESIS
    assert _THESIS not in body, 'the duplicated first line must be omitted'
    assert _MACRO in body, 'the remaining unique line must survive'


def test_confidence_dedupe_leaves_the_engine_payload_untouched():
    """Display-only: the footer still renders the confidence the endpoint
    returned, and both other facts are unchanged."""
    out = _run_scenario(_full_scenario())
    footer = out['ovMbFooter']['text']
    assert _DRAW in footer
    assert _WATCH in footer
    assert 'Confidence' in footer and 'Medium' in footer


# ── Structured rendering of the engine's labelled lines ──────────────────
#
# build_compact_brief() emits THESIS / PARTICIPATION / MACRO as labelled
# lines. Those prefixes are structured engine output, so they are parsed into
# a description list: the prefix becomes a real <dt> label and its value a
# <dd> that reads as prose. These tests pin that the transform is confined to
# the LABEL and that no value is ever altered.


def test_engine_labels_render_as_a_description_list():
    out = _run_scenario(_full_scenario())
    markup = out['ovMbText']['html']
    assert '<dl class="ov-mb-sections">' in markup, (
        'labelled engine lines must render as a description list:\n' + markup
    )
    assert '<dt>Thesis</dt>' in markup
    assert '<dt>Participation</dt>' in markup
    assert '<dt>Macro</dt>' in markup


def test_no_raw_machine_prefix_survives_in_the_rendered_text():
    """The uppercase run-on prefixes must not appear as body prose."""
    out = _run_scenario(_full_scenario())
    markup = out['ovMbText']['html']
    for raw in ('THESIS', 'PARTICIPATION', 'MACRO'):
        assert f'<dd>{raw}' not in markup, f'{raw} still rendered as a value'
        assert f'<p>{raw}' not in markup, f'{raw} still rendered as raw prose'


def test_values_are_rendered_byte_for_byte():
    """Only the label is transformed. Every value the engine emitted survives
    exactly, including its casing and its punctuation."""
    out = _run_scenario(_full_scenario())
    markup = out['ovMbText']['html']
    assert f'<dd>{_PARTICIPATION}</dd>' in markup
    assert f'<dd>{_MACRO}</dd>' in markup
    assert '<dd>CONTESTED</dd>' in markup, 'thesis state keeps its engine casing'


def test_unlabelled_lines_still_render_as_paragraphs():
    """A line the engine did not label is prose and must stay a paragraph."""
    out = _run_scenario(_full_scenario(
        thesis='A headline that appears nowhere in the body',
        brief_text='Overnight balance held and the range is intact.',
    ))
    markup = out['ovMbText']['html']
    assert markup == '<p>Overnight balance held and the range is intact.</p>'
    assert '<dl' not in markup


def test_labelled_and_unlabelled_lines_coexist_in_order():
    """Mixed content keeps document order, with the labelled run grouped."""
    out = _run_scenario(_full_scenario(
        thesis='A headline that appears nowhere in the body',
        brief_text=f'Plain opening line.\nMACRO        {_MACRO}',
    ))
    markup = out['ovMbText']['html']
    assert markup.index('<p>Plain opening line.</p>') < markup.index('<dl')
    assert f'<dt>Macro</dt><dd>{_MACRO}</dd>' in markup


def test_structured_rendering_escapes_markup_in_values():
    """A value containing angle brackets must never become live markup."""
    out = _run_scenario(_full_scenario(
        thesis='A headline that appears nowhere in the body',
        brief_text='MACRO        risk <b>elevated</b> & rising',
    ))
    markup = out['ovMbText']['html']
    assert '<dd>risk &lt;b&gt;elevated&lt;/b&gt; &amp; rising</dd>' in markup


if __name__ == '__main__':
    raise SystemExit(pytest.main([__file__, '-v']))
