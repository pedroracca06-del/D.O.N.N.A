"""
test_markets_render_states.py — executes the SHIPPED Markets renderers under
Node against literal fixtures, proving each required state renders honestly.

Nothing here touches production data: every scenario is a literal payload in
the shape the real routes return. The function sources are extracted from the
real ui/scripts.py by brace matching (not retyped), so a genuine bug in the
shipped renderer fails these tests rather than a hand-written mirror of it.

States covered:
  quote merge     — de-duplication across routes, absent BTC, symbol spelling
  freshness       — live / cached / loading / unavailable
  cross-asset     — populated / empty / partial / error / stale muting
  volatility      — VIX regime, equity-index direction, absent BTC
  market structure— levels, sweep status, missing liquidity, level collisions
"""
from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('ALPACA_API_KEY', '')
os.environ.setdefault('ALPACA_SECRET_KEY', '')

import pytest

import ui.scripts

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = ui.scripts.DASHBOARD_SCRIPT

pytestmark = pytest.mark.skipif(shutil.which('node') is None,
                                reason='node is not available in this environment')


def _fn(name: str) -> str:
    """Extract one function from the shipped bundle by brace matching."""
    for prefix in ('function ' + name + '(', 'async function ' + name + '('):
        i = SRC.find(prefix)
        if i != -1:
            break
    assert i != -1, f'{name}() not found in DASHBOARD_SCRIPT'
    j = SRC.index('{', i)
    depth, k = 0, j
    while k < len(SRC):
        if SRC[k] == '{':
            depth += 1
        elif SRC[k] == '}':
            depth -= 1
            if depth == 0:
                return SRC[i:k + 1]
        k += 1
    raise AssertionError(f'unbalanced braces in {name}()')


def _const(name: str) -> str:
    i = SRC.index('const ' + name)
    j = SRC.index(';', i)
    return SRC[i:j + 1]


_PARTS = [
    _const('_MK_GROUPS'), _const('_MK_EQUITY'),
    'let _mkQuotes = null;', 'let _mkQuotesFailed = false;', 'let _mkQuotesAt = null;',
    'let _mkIndexRows = null;', "let _mkSym = 'NQ';",
    'let _lastDashData = null;', 'let _lastMarketStructure = null;',
    'let _lastLiquidity = null;', 'let _structureFetchFailed = false;',
    'let _dbStateEngine = null;',
    _fn('_mkEsc'), _fn('_mkNorm'), _fn('_mkPctNum'), _fn('_mkDir'), _fn('_mkAge'),
    _fn('_mkFmt'), _fn('_mkSigned'), _fn('_mkMergeQuotes'), _fn('_mkQuoteState'),
    _fn('_mkSetFresh'), _fn('_mkRenderRail'), _fn('_mkRenderPulse'),
    _fn('_mkRenderVol'), _fn('_mkRenderNews'), _fn('_mkRenderStructure'),
    _fn('_mkRenderProv'), _fn('renderMarkets'),
]

_IDS = [
    'mkFresh', 'mkClock', 'mkSession', 'mkMacroRisk', 'mkHeadlineRisk',
    'mkMarketRisk', 'mkEventPhase', 'mkPulseBody', 'mkPulseMeta', 'mkPulseFoot',
    'mkVolBody', 'mkVolMeta', 'mkBreakingWire', 'mkNewsBody', 'mkNewsMeta', 'mkStructBody',
    'mkStructSym', 'mkProv',
]

_HARNESS = r'''
'use strict';
const elements = {};
%(ids)s.forEach(id => {
  const el = {
    id, textContent: '', className: '', dataset: {}, _attrs: {},
    style: {display: ''},
    setAttribute(k, v) { this._attrs[k] = String(v); },
    getAttribute(k) { return this._attrs[k] == null ? null : this._attrs[k]; },
    removeAttribute(k) { delete this._attrs[k]; },
    addEventListener() {}, querySelectorAll() { return []; }, focus() {},
    classList: {add(){}, remove(){}, toggle(){}, contains(){ return false; }},
  };
  Object.defineProperty(el, 'innerHTML', {
    get() { return el._html || ''; },
    set(v) {
      el._html = String(v);
      el.textContent = el._html.replace(/<[^>]*>/g, ' ')
        .replace(/&lt;/g,'<').replace(/&gt;/g,'>').replace(/&amp;/g,'&')
        .replace(/&mdash;/g,'-').replace(/\s+/g,' ').trim();
    },
  });
  elements[id] = el;
});
global.document = {
  getElementById: (id) => elements[id] || null,
  querySelectorAll: () => [],
};

%(parts)s

const scenario = %(scenario)s;
if (scenario.dash !== undefined) _lastDashData = scenario.dash;
if (scenario.structure !== undefined) _lastMarketStructure = scenario.structure;
if (scenario.liquidity !== undefined) _lastLiquidity = scenario.liquidity;
if (scenario.structureFailed) _structureFetchFailed = true;
if (scenario.sym) _mkSym = scenario.sym;
if (scenario.merge) {
  _mkQuotes = _mkMergeQuotes(scenario.merge.pulse, scenario.merge.indexes, scenario.merge.btcVix);
  _mkIndexRows = scenario.merge.indexes || [];
  _mkQuotesAt = scenario.at || new Date().toISOString();
}
if (scenario.quotes !== undefined) _mkQuotes = scenario.quotes;
if (scenario.indexRows !== undefined) _mkIndexRows = scenario.indexRows;
if (scenario.quotesFailed) _mkQuotesFailed = true;
if (scenario.at) _mkQuotesAt = scenario.at;

renderMarkets();

const out = {state: _mkQuoteState(), merged: _mkQuotes};
for (const id of %(ids)s) {
  out[id] = {text: elements[id].textContent, html: elements[id]._html || '',
             className: elements[id].className || ''};
}
process.stdout.write(JSON.stringify(out));
'''


def _run(scenario: dict) -> dict:
    script = _HARNESS % {
        'ids': json.dumps(_IDS),
        'parts': '\n'.join(_PARTS),
        'scenario': json.dumps(scenario),
    }
    # The script goes to a file rather than -e: Windows caps a command line at
    # ~32k and a full payload plus the renderers overruns it. encoding must be
    # explicit -- the renderers emit em dashes.
    with tempfile.TemporaryDirectory() as td:
        f = os.path.join(td, 'harness.mjs')
        with io.open(f, 'w', encoding='utf-8', newline='') as fh:
            fh.write(script)
        r = subprocess.run(['node', f], capture_output=True, text=True,
                           encoding='utf-8', cwd=str(REPO_ROOT), timeout=20)
    assert r.returncode == 0, f'harness failed: {r.stderr}'
    return json.loads(r.stdout)


# ── fixtures in the exact shape the real routes return ────────────────────

PULSE = [
    {'symbol': 'NQ', 'last': 29501.5, 'chg': 498.0, 'pct': '+1.72%', 'dir': 'up'},
    {'symbol': 'ES', 'last': 7685.5, 'chg': 40.5, 'pct': '+0.53%', 'dir': 'up'},
    {'symbol': 'OIL', 'last': 75.98, 'chg': -5.21, 'pct': '-6.42%', 'dir': 'down'},
    {'symbol': 'GOLD', 'last': 4143.7, 'chg': 35.5, 'pct': '+0.86%', 'dir': 'up'},
    {'symbol': 'SILVER', 'last': 60.01, 'chg': 1.1, 'pct': '+1.87%', 'dir': 'up'},
    {'symbol': 'DXY', 'last': 99.88, 'chg': -0.14, 'pct': '-0.14%', 'dir': 'down'},
    {'symbol': 'US10Y', 'last': 4.63, 'chg': -0.06, 'pct': '-1.28%', 'dir': 'down'},
    {'symbol': 'VIX', 'last': 16.01, 'chg': 0.15, 'pct': '+0.95%', 'dir': 'up'},
]
INDEXES = [
    {'symbol': 'NASDAQ', 'last': 26273.87, 'chg': 359.97, 'pct': '+1.39%', 'dir': 'up'},
    {'symbol': 'S&P 500', 'last': 7663.86, 'chg': 63.36, 'pct': '+0.83%', 'dir': 'up'},
    {'symbol': 'DJIA', 'last': 53766.15, 'chg': 587.74, 'pct': '+1.11%', 'dir': 'up'},
    {'symbol': 'VIX', 'last': 16.01, 'chg': 0.15, 'pct': '+0.95%', 'dir': 'up'},
    {'symbol': 'US 10Y', 'last': 4.63, 'chg': -0.06, 'pct': '-1.28%', 'dir': 'down'},
    {'symbol': 'DXY', 'last': 99.88, 'chg': -0.14, 'pct': '-0.14%', 'dir': 'down'},
]
# /btc-vix genuinely answers with empty objects when it has nothing
BTC_EMPTY = {'BTC': {}, 'VIX': {}, 'fetched_at': '2026-08-21T12:00:00+00:00'}
DASH = {'risk': {'macro_risk': 'low', 'headline_risk': 'high',
                 'market_news_risk': 'medium', 'event_phase': 'NONE',
                 'next_event': 'No scheduled event', 'donna_session': 'LONDON'},
        'news': [], 'calendar': {'source': 'ForexFactory', 'events': [
            {'title': 'President Trump Speaks', 'time_et': '15:00',
             'date': '2026-09-01',
             'importance': 'medium', 'category': 'macro', 'currency': 'USD',
             'source': 'ForexFactory'}]}}
STRUCTURE = {'nq': {'onh': 29282.25, 'onl': 28831.75, 'daily_open': 29234.25,
                    'pdh': 28964.25, 'pdl': 28313.5, 'pwh': 28763.25, 'pwl': 27201.5},
             'narrative': 'NQ gapped up at open', 'last_updated': '2026-08-04T14:05:09+00:00'}
LIQUIDITY = {'nq': {'price': 29501.5, 'levels': [
                 {'label': 'ONH', 'status': 'SWEPT'},
                 {'label': 'PDH', 'status': 'UNTAPPED'}]},
             'narrative': 'NQ primary draw: PDH 28964.25', 'last_updated': '2026-08-04T14:05:09+00:00'}

LIVE = {'merge': {'pulse': PULSE, 'indexes': INDEXES, 'btcVix': BTC_EMPTY},
        'dash': DASH, 'structure': STRUCTURE, 'liquidity': LIQUIDITY}


# ── quote merge and de-duplication ────────────────────────────────────────

def test_merge_deduplicates_to_the_real_instrument_count():
    """8 rows from /futures-macro-pulse plus 6 from /major-indexes overlap on
    VIX, DXY and the 10-year -- eleven unique instruments, not fourteen."""
    out = _run(LIVE)
    syms = [r['symbol'] for r in out['merged']]
    assert len(syms) == 11, syms
    assert len(set(syms)) == 11, 'a symbol was emitted twice'


def test_merge_normalises_the_two_spellings_of_the_ten_year():
    """/futures-macro-pulse says US10Y, /major-indexes says 'US 10Y'. Without
    normalisation they de-duplicate to two instruments instead of one."""
    syms = [r['symbol'] for r in _run(LIVE)['merged']]
    assert syms.count('US10Y') == 1
    assert 'US 10Y' not in syms


def test_absent_btc_is_never_invented():
    """/btc-vix answering {"BTC": {}} is a real state: no price exists."""
    out = _run(LIVE)
    assert 'BTC' not in [r['symbol'] for r in out['merged']]
    assert 'Not available' in out['mkVolBody']['text']
    assert 'BTC · risk proxy' in out['mkVolBody']['text']


def test_btc_appears_only_when_it_carries_a_price():
    btc = {'BTC': {'last': 94318, 'chg': 1204, 'pct': '+1.29%'}, 'VIX': {}}
    out = _run({'merge': {'pulse': PULSE, 'indexes': INDEXES, 'btcVix': btc},
                'dash': DASH})
    assert 'BTC' in [r['symbol'] for r in out['merged']]
    assert len(out['merged']) == 12


def test_rows_without_a_price_are_dropped_not_shown_blank():
    pulse = PULSE + [{'symbol': 'JUNK', 'last': None, 'pct': None}]
    out = _run({'merge': {'pulse': pulse, 'indexes': [], 'btcVix': BTC_EMPTY}, 'dash': DASH})
    assert 'JUNK' not in [r['symbol'] for r in out['merged']]


# ── freshness vocabulary ──────────────────────────────────────────────────

def test_freshness_reads_live_when_the_merge_succeeded():
    out = _run(LIVE)
    assert out['mkFresh']['className'] == 'mk-fresh live'
    assert 'Live' in out['mkFresh']['text']


def test_freshness_names_the_age_when_cached():
    out = _run(dict(LIVE, quotesFailed=True, at='2026-08-05T12:00:00+00:00'))
    assert out['mkFresh']['className'] == 'mk-fresh stale'
    assert 'Cached' in out['mkFresh']['text']
    assert 'old' in out['mkFresh']['text']


def test_freshness_is_loading_before_the_first_merge():
    out = _run({'dash': DASH})
    assert out['mkFresh']['className'] == 'mk-fresh loading'
    assert out['state'] == 'loading'


def test_freshness_is_unavailable_when_the_first_fetch_failed():
    out = _run({'dash': DASH, 'quotesFailed': True})
    assert out['mkFresh']['className'] == 'mk-fresh down'
    assert 'Unavailable' in out['mkFresh']['text']


# ── cross-asset pulse states ──────────────────────────────────────────────

def test_pulse_states_the_count_it_actually_drew():
    out = _run(LIVE)
    assert '11 instruments' in out['mkPulseMeta']['text']
    assert out['mkPulseBody']['html'].count('data-mk-row=') == 11


def test_pulse_error_shows_no_prices_at_all():
    out = _run({'dash': DASH, 'quotesFailed': True})
    assert 'unavailable' in out['mkPulseMeta']['text']
    assert 'data-mk-row=' not in out['mkPulseBody']['html']
    assert 'as if they were current' in out['mkPulseBody']['text']


def test_pulse_empty_is_distinct_from_failure():
    out = _run({'dash': DASH, 'quotes': []})
    assert out['state'] == 'empty'
    assert 'responded and returned no rows' in out['mkPulseBody']['text']
    assert 'data-mk-row=' not in out['mkPulseBody']['html']


def test_stale_prices_are_muted_and_labelled_never_shown_as_live():
    out = _run(dict(LIVE, quotesFailed=True, at='2026-08-05T12:00:00+00:00'))
    html = out['mkPulseBody']['html']
    assert 'mk-muted' in html, 'cached rows must not use the confident treatment'
    assert 'cached prices' in out['mkPulseBody']['text']
    assert 'must not be read as the current market' in out['mkPulseBody']['text']
    assert 'cached' in out['mkPulseMeta']['text']


def test_pulse_footer_names_both_source_routes():
    out = _run(LIVE)
    foot = out['mkPulseFoot']['text']
    assert '/futures-macro-pulse' in foot and '/major-indexes' in foot
    assert 'de-duplicated' in foot


def test_move_bar_is_proportional_to_the_largest_absolute_move():
    html = _run(LIVE)['mkPulseBody']['html']
    assert 'width:100.0%' in html, 'the largest mover anchors the scale'


# ── volatility and direction ──────────────────────────────────────────────

def test_index_direction_counts_only_the_equity_indexes():
    """VIX, DXY and the 10-year must never be folded into an advancing tally."""
    out = _run(LIVE)
    txt = out['mkVolBody']['text']
    assert '3 of 3 advancing' in txt
    assert 'NASDAQ, S&P 500, DJIA' in txt
    assert 'Not an exchange breadth feed' in txt


def test_index_direction_reflects_a_declining_index():
    idx = [dict(INDEXES[0], pct='-0.40%', dir='down')] + INDEXES[1:]
    out = _run({'merge': {'pulse': PULSE, 'indexes': idx, 'btcVix': BTC_EMPTY}, 'dash': DASH})
    assert '2 of 3 advancing' in out['mkVolBody']['text']


def test_vix_regime_is_derived_not_asserted():
    out = _run(LIVE)
    assert 'Below 20 · calm' in out['mkVolBody']['text']
    hi = [dict(r, last=34.0) if r['symbol'] == 'VIX' else r for r in PULSE]
    out2 = _run({'merge': {'pulse': hi, 'indexes': INDEXES, 'btcVix': BTC_EMPTY}, 'dash': DASH})
    assert 'stressed' in out2['mkVolBody']['text']


def test_volatility_error_state_explains_the_shared_cause():
    out = _run({'dash': DASH, 'quotesFailed': True})
    assert 'did not respond' in out['mkVolBody']['text']


# ── news and catalysts ────────────────────────────────────────────────────

def test_news_empty_feed_is_stated_not_padded():
    out = _run(LIVE)
    assert 'No headlines in the feed' in out['mkNewsBody']['text']
    assert 'as if it had just broken' in out['mkNewsBody']['text']
    assert 'President Trump Speaks' in out['mkNewsBody']['text']
    assert '09-01 · 15:00' in out['mkNewsBody']['text']


def test_news_headline_links_to_its_real_source_article():
    dash = dict(DASH, news=[{
        'headline': 'Powell signals rates may stay higher',
        'source': 'Reuters', 'severity': 'high', 'category': 'Fed & rates',
        'url': 'https://example.test/powell-rates',
    }])
    out = _run({'merge': {'pulse': PULSE, 'indexes': INDEXES, 'btcVix': BTC_EMPTY}, 'dash': dash})
    html = out['mkNewsBody']['html']
    assert 'href="https://example.test/powell-rates"' in html
    assert 'target="_blank"' in html
    assert 'rel="noopener noreferrer"' in html
    assert 'Powell signals rates may stay higher' in out['mkBreakingWire']['text']
    assert 'href="https://example.test/powell-rates"' in out['mkBreakingWire']['html']


def test_news_is_a_live_desk_with_timestamp_and_nq_and_es_driver_context():
    dash = dict(DASH, news=[{
        'headline': 'Iran escalation sends oil and index futures sharply higher',
        'summary': 'Energy prices and equity futures moved after the latest conflict update.',
        'source': 'Reuters', 'severity': 'high', 'category': 'Geopolitics',
        'market_score': 12, 'published_at': 1788271200,
        'url': 'https://example.test/iran-market-update',
    }])
    out = _run({'merge': {'pulse': PULSE, 'indexes': INDEXES, 'btcVix': BTC_EMPTY}, 'dash': dash})
    text = out['mkNewsBody']['text']
    html = out['mkNewsBody']['html']
    assert 'Top market driver' in text or 'Breaking' in text
    assert 'ET' in text
    assert 'Why NQ is moving' in text
    assert '+498.00 pts (+1.72%)' in text
    assert 'Why ES is moving' in text
    assert '+40.50 pts (+0.53%)' in text
    assert 'not verified causation' in text
    assert 'Open full article' in text
    assert 'href="https://example.test/iran-market-update"' in html


def test_news_quiet_tape_is_distinct_from_failure():
    dash = dict(DASH, news=[], calendar={'events': []})
    out = _run({'merge': {'pulse': PULSE, 'indexes': INDEXES, 'btcVix': BTC_EMPTY}, 'dash': dash})
    assert 'quiet tape, not a failure' in out['mkNewsBody']['text']


# ── market structure ──────────────────────────────────────────────────────

def test_structure_draws_every_level_it_has():
    out = _run(LIVE)
    html = out['mkStructBody']['html']
    assert html.count('class="mk-lvl ') == 7
    for label in ('ONH', 'ONL', 'PDH', 'PDL', 'PWH', 'PWL', 'Daily open'):
        assert label in html, label


def test_structure_uses_liquidity_sweep_status_when_present():
    html = _run(LIVE)['mkStructBody']['html']
    assert 'ONH<span class="mk-lvl-st"> · swept' in html
    assert 'PDH<span class="mk-lvl-st"> · untapped' in html


def test_structure_withdraws_sweep_status_rather_than_guessing_it():
    """With /liquidity missing the levels still draw -- the last price comes
    from the dashboard payload's market_snapshot -- but no level claims a
    sweep status, because that classification only exists on /liquidity."""
    dash = dict(DASH, risk=dict(DASH['risk'], market_snapshot={'NQ': {'last': 29501.5}},
                                last_updated='2026-08-21T11:00:00+00:00'))
    out = _run(dict(LIVE, liquidity=None, dash=dash))
    html = out['mkStructBody']['html']
    assert 'unclassified' in html
    assert 'swept' not in html.replace('Swept level', '')
    assert 'sweep status unavailable' in out['mkStructBody']['text'].lower()


def test_structure_refuses_to_draw_without_a_price_reference():
    out = _run({'dash': DASH, 'structureFailed': True})
    assert 'would mislead' in out['mkStructBody']['text']
    assert 'mk-lvl ' not in out['mkStructBody']['html']


def test_structure_says_so_when_no_levels_exist_yet():
    out = _run(dict(LIVE, structure={'nq': {}}, liquidity={'nq': {'price': 29501.5}}))
    assert 'No levels recorded yet' in out['mkStructBody']['text']


def test_close_levels_are_spread_across_lanes_not_stacked():
    """ONH and the daily open sit ~47pts apart on a 2500pt scale -- about 4px.
    Each label must land in a different lane or one hides the other."""
    html = _run(LIVE)['mkStructBody']['html']
    import re as _re
    # only the level rows carry a lane; the gridlines also use top: and must
    # not be swept into the comparison
    rows = _re.findall(r'top:([\d.]+)%;--lane:(\d+)', html)
    assert len(rows) == 7, rows
    lanes = [int(l) for _, l in rows]
    assert max(lanes) >= 1, 'a tight cluster must use more than one lane'
    pairs = sorted((float(t), int(l)) for t, l in rows)
    for (t1, l1), (t2, l2) in zip(pairs, pairs[1:]):
        if abs(t2 - t1) / 100 * 250 < 22:
            assert l1 != l2, f'labels at {t1}% and {t2}% share lane {l1}'


def test_structure_distance_is_signed_from_the_current_price():
    html = _run(LIVE)['mkStructBody']['html']
    assert '−219 pts' in html or '-219 pts' in html


def test_switching_instrument_redraws_from_that_instruments_levels():
    es = {'es': {'onh': 7666.0, 'onl': 7629.0, 'daily_open': 7657.25}}
    out = _run({'merge': {'pulse': PULSE, 'indexes': INDEXES, 'btcVix': BTC_EMPTY},
                'dash': DASH, 'structure': es,
                'liquidity': {'es': {'price': 7685.5, 'levels': []}}, 'sym': 'ES'})
    assert out['mkStructSym']['text'] == 'ES'
    assert '7,666' in out['mkStructBody']['html']


# ── rail and provenance ───────────────────────────────────────────────────

def test_rail_shows_the_real_session_and_risk_levels():
    out = _run(LIVE)
    assert 'LONDON' in out['mkSession']['text']
    assert 'low' in out['mkMacroRisk']['text'].lower()
    assert 'high' in out['mkHeadlineRisk']['text'].lower()
    assert 'medium' in out['mkMarketRisk']['text'].lower()
    assert 'NONE' in out['mkEventPhase']['text']


def test_rail_says_not_available_rather_than_inventing_a_level():
    out = _run({'merge': {'pulse': PULSE, 'indexes': INDEXES, 'btcVix': BTC_EMPTY},
                'dash': {'risk': {}, 'news': [], 'calendar': {'events': []}}})
    assert 'Not available' in out['mkMacroRisk']['text']


def test_provenance_names_each_source_and_its_age():
    out = _run(LIVE)
    prov = out['mkProv']['text']
    for token in ('Quotes', 'Structure', 'Liquidity', 'Calendar', 'News', 'Risk'):
        assert token in prov, token
    assert '/market-structure' in prov
    assert 'ForexFactory' in prov


def test_provenance_reports_the_structure_age_honestly():
    out = _run(LIVE)
    assert 'old' in out['mkProv']['text'], 'a dated snapshot must state its age'




# ── degraded current-price fallback ───────────────────────────────────────
#
# /liquidity carries the last price. When it fails the dashboard snapshot can
# stand in, but only as degraded data: labelled, aged, never called live, and
# refused outright when its own freshness cannot be established.

def _dash_with_snapshot(last_updated):
    risk = dict(DASH['risk'], market_snapshot={'NQ': {'last': 29501.5}})
    if last_updated is not None:
        risk['last_updated'] = last_updated
    return dict(DASH, risk=risk)


def test_snapshot_price_is_labelled_and_never_shown_as_live():
    out = _run(dict(LIVE, liquidity=None, dash=_dash_with_snapshot('2026-08-21T11:00:00+00:00')))
    html = out['mkStructBody']['html']
    assert 'is-fallback' in html, 'a snapshot price must not wear the live treatment'
    assert 'Snapshot' in html
    assert 'not live' in out['mkStructBody']['text']


def test_snapshot_price_states_its_age():
    out = _run(dict(LIVE, liquidity=None, dash=_dash_with_snapshot('2026-08-21T11:00:00+00:00')))
    txt = out['mkStructBody']['text']
    assert 'market_snapshot' in txt
    assert 'ago' in txt
    assert 'snapshot,' in txt.lower(), 'the legend must name the source too'


def test_snapshot_without_establishable_age_is_refused_not_trusted():
    """No timestamp means no freshness, and an unaged price cannot anchor a
    level ladder -- it is withheld rather than presented as trustworthy."""
    out = _run(dict(LIVE, liquidity=None, dash=_dash_with_snapshot(None)))
    assert 'Last price unavailable' in out['mkStructBody']['text']
    assert 'mk-lad-now' not in out['mkStructBody']['html']
    assert 'cannot be trusted' in out['mkStructBody']['text']


def test_snapshot_fallback_still_withdraws_sweep_status():
    out = _run(dict(LIVE, liquidity=None, dash=_dash_with_snapshot('2026-08-21T11:00:00+00:00')))
    html = out['mkStructBody']['html']
    assert html.count('unclassified') >= 7
    assert 'swept' not in html.replace('Swept level', '')


def test_live_price_keeps_the_live_treatment():
    out = _run(LIVE)
    html = out['mkStructBody']['html']
    assert 'is-fallback' not in html
    assert 'Snapshot' not in html
    assert 'Degraded' not in out['mkStructBody']['text']


def test_level_geometry_is_identical_whichever_price_source_is_used():
    """The fallback changes how the price is labelled, never where the levels
    are drawn -- the same price value must produce the same geometry."""
    live = _run(LIVE)['mkStructBody']['html']
    fb = _run(dict(LIVE, liquidity=None,
                   dash=_dash_with_snapshot('2026-08-21T11:00:00+00:00')))['mkStructBody']['html']
    import re as _re
    a = _re.findall(r'top:([\d.]+)%;--lane', live)
    b = _re.findall(r'top:([\d.]+)%;--lane', fb)
    assert a == b and len(a) == 7


if __name__ == '__main__':
    raise SystemExit(pytest.main([__file__, '-q']))
