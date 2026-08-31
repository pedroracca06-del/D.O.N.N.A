"""
test_journal_render_states.py — executes the SHIPPED Journal renderer under
Node against a minimal DOM stub and isolated fixtures, proving each required
state renders honestly.

Nothing here touches production Journal data: every scenario is a literal
`{trades, stats}` payload built in the test, exactly the shape GET
/journal/data returns.

The function sources are extracted from the real ui/scripts.py by brace
matching (not retyped), so a genuine bug in the shipped renderer fails these
tests rather than a hand-written mirror of it.

States covered:
  performance rail  — populated / empty / low sample / no-losses profit factor
  trade ledger      — populated / empty / filtered-empty / malformed record
  trade review      — selected / no selection / missing optional fields /
                      snapshot + evidence unavailable / selection removed
  by-direction      — both / one / empty / invalid direction excluded
  daily P&L         — multiple days / single day / none / +,-,flat /
                      invalid date excluded
  inclusion rules   — REJECTED and OPEN excluded, EOD_CLOSE classified by sign

Run:  python -m pytest tests/test_journal_render_states.py -v
"""
from __future__ import annotations

import tempfile
import io
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
pytestmark = pytest.mark.skipif(shutil.which('node') is None,
                                reason='node is not available in this environment')


def _fn(name: str) -> str:
    """Extract one top-level function from the shipped DASHBOARD_SCRIPT."""
    script = ui.scripts.DASHBOARD_SCRIPT
    for prefix in (f'async function {name}(', f'function {name}('):
        idx = script.find(prefix)
        if idx != -1:
            break
    else:
        raise AssertionError(f'{name}() not found in DASHBOARD_SCRIPT')
    start = script.find('{', idx)
    depth, i = 0, start
    while i < len(script):
        if script[i] == '{':
            depth += 1
        elif script[i] == '}':
            depth -= 1
            if depth == 0:
                return script[idx:i + 1]
        i += 1
    raise AssertionError(f'braces never balanced for {name}()')


def _const(name: str) -> str:
    for line in ui.scripts.DASHBOARD_SCRIPT.split('\n'):
        if line.startswith(f'const {name}') or line.startswith(f'let {name}'):
            return line
    raise AssertionError(f'{name} not found in DASHBOARD_SCRIPT')


_PARTS = [
    _const('_JN_EXCLUDED_OUTCOMES'), _const('_JN_LOW_SAMPLE'),
    _const('_JN_OUTCOMES'), _const('_JN_PERIODS'), _const('_JN_ABSENT_KEYS'),
    _const('_JN_DAILY_SLOTS'), _const('_JN_DAILY_DENSE'),
    'let _jnSelectedKey = null;', 'let _jnRows = [];',
    'let _journalData = null;', 'let journalFilter = "all";',
    'let _jnInstrument = "all";', 'let _jnPeriod = "all";', 'let _jnRegime = "all";',
    _fn('setText'),
    _fn('_jnNum'), _fn('_jnKey'), _fn('_jnPnl'), _fn('_jnOutcome'),
    _fn('_jnClosed'), _fn('_jnDir'), _fn('_jnEsc'), _fn('_jnMoney'),
    _fn('_jnPnlClass'), _fn('_jnPnlMark'), _fn('_jnValidDate'),
    _fn('_jnBucketLabel'), _fn('_jnIsAbsentBucket'), _fn('_jnMoneyAxis'),
    _fn('_jnDistinct'), _fn('_jnFilterGroup'),
    _fn('_jnRenderRail'), _fn('_jnRenderLedger'), _fn('_jnRenderReview'),
    _fn('_jnRenderBreakdown'), _fn('_jnRenderDaily'),
    _fn('_jnSelect'), _fn('_jnBindLedger'), _fn('renderJournal'),
]

_IDS = [
    'jnNetPnlLabel', 'jnNetPnl', 'jnNetPnlSub', 'jnWeekPnl', 'jnWeekPnlSub',
    'jnProfitFactor', 'jnProfitFactorSub', 'jnAvgWL', 'jnAvgWLSub',
    'jnWinRate', 'jnWinRateSub', 'jnRailNote',
    'jnLedgerBody', 'jnLedgerFoot', 'jFilterBar',
    'jnByRegime', 'jnBySession', 'jnByDirection', 'jnByDirectionNote',
    'jnBySetup', 'jnBreakdownMeta', 'jnDaily', 'jnDailyMeta', 'jnDailyNote', 'jnDailyCtx',
    'jnReviewInner', 'jTabCount-trades',
]

_HARNESS = r'''
'use strict';
const elements = {};
%(ids)s.forEach(id => {
  const el = {
    id, textContent: '', className: '', dataset: {},
    tabIndex: -1, _attrs: {}, _props: {},
    style: {display: '',
            setProperty(k, v) { this._p = this._p || {}; this._p[k] = String(v); },
            getPropertyValue(k) { return (this._p || {})[k] || ''; }},
    setAttribute(k, v) { this._attrs[k] = String(v); },
    getAttribute(k) { return this._attrs[k] == null ? null : this._attrs[k]; },
    removeAttribute(k) { delete this._attrs[k]; },
    addEventListener() {},
    querySelectorAll() { return []; },
    classList: {toggle(){}, add(){}, remove(){}},
    focus() {},
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
global.document = { getElementById: (id) => elements[id] || null };

%(parts)s

const scenario = %(scenario)s;
journalFilter = scenario.filter || 'all';
if (scenario.instrument) _jnInstrument = scenario.instrument;
if (scenario.period) _jnPeriod = scenario.period;
if (scenario.regime) _jnRegime = scenario.regime;
if (scenario.preselect) _jnSelectedKey = scenario.preselect;
renderJournal(scenario.payload);
if (scenario.thenPayload) renderJournal(scenario.thenPayload);

const _dstyle = elements['jnDaily'].style._p || {};
const out = {selectedKey: _jnSelectedKey, rowCount: _jnRows.length,
             jnDailyDense: elements['jnDaily'].getAttribute('data-dense'),
             jnDailyStyle: {pos: _dstyle['--pos'] || '', neg: _dstyle['--neg'] || '',
                            slots: _dstyle['--slots'] || '', n: _dstyle['--n'] || ''}};
for (const id of %(ids)s) {
  out[id] = {display: elements[id].style.display,
             text: elements[id].textContent,
             html: elements[id]._html || '',
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
    # ~32k and a many-session payload plus the renderer overruns it.
    # encoding must be explicit: the renderer emits em dashes, and the
    # Windows locale codec would mangle them into mojibake.
    with tempfile.TemporaryDirectory() as td:
        f = os.path.join(td, 'harness.mjs')
        with io.open(f, 'w', encoding='utf-8', newline='') as fh:
            fh.write(script)
        r = subprocess.run(['node', f], capture_output=True, text=True,
                           encoding='utf-8', cwd=str(REPO_ROOT), timeout=20)
    assert r.returncode == 0, f'harness failed: {r.stderr}'
    return json.loads(r.stdout)


def _trade(**kw):
    base = {'ticker': 'NQ', 'direction': 'LONG', 'trade_date': '2026-06-24',
            'entry_price': 100.0, 'exit_price': 110.0, 'size': 1,
            'realized_pnl': 10.0, 'outcome': 'WIN'}
    base.update(kw)
    return base


def _payload(trades, **stats):
    s = {'total': 0, 'wins': 0, 'losses': 0, 'win_rate': 0.0, 'avg_win': 0.0,
         'avg_loss': 0.0, 'profit_factor': 0.0, 'by_regime': {}, 'by_session': {},
         'by_setup_type': {}, 'daily_pnl': {'today': 0, 'yesterday': 0, 'this_week': 0}}
    s.update(stats)
    return {'trades': trades, 'stats': s}


# ── Performance rail ─────────────────────────────────────────────────────

def test_rail_empty_state():
    out = _run({'payload': _payload([])})
    assert out['jnNetPnl']['text'] == '—'
    assert 'No closed trades yet' in out['jnNetPnlSub']['text']
    assert out['jnWinRate']['text'] == '—'


def test_rail_populated_reports_sample_size():
    trades = [_trade(realized_pnl=10.0), _trade(realized_pnl=-4.0, outcome='LOSS')]
    out = _run({'payload': _payload(trades, avg_win=10.0, avg_loss=4.0, profit_factor=2.5)})
    assert '2 closed trades' in out['jnNetPnlSub']['text']
    assert 'n=2' in out['jnWinRateSub']['text'], 'win rate must always carry its sample size'


def test_rail_low_sample_is_labelled_not_headlined():
    """A 100% rate from one trade must be marked low-sample, not celebrated."""
    out = _run({'payload': _payload([_trade()], win_rate=100.0)})
    assert out['jnWinRate']['text'] == '100%'
    assert 'n=1' in out['jnWinRateSub']['text']
    assert 'low sample' in out['jnWinRateSub']['text']
    assert out['jnWinRate']['className'] == 'v lowsample', 'must not use the confident treatment'
    assert 'provisional' in out['jnRailNote']['text']


def test_profit_factor_with_no_losses_is_explained_not_zero():
    """compute_journal_stats returns 0.0 with no losses; rendering "0.00"
    would read as catastrophic rather than 'not yet meaningful'."""
    out = _run({'payload': _payload([_trade()], profit_factor=0.0)})
    assert out['jnProfitFactor']['text'] == '—'
    assert '0.00' not in out['jnProfitFactor']['text']
    assert 'No losing trades yet' in out['jnProfitFactorSub']['text']


# ── Inclusion rules ──────────────────────────────────────────────────────

def test_rejected_and_open_are_excluded_everywhere():
    trades = [_trade(), _trade(outcome='REJECTED', realized_pnl=999.0),
              _trade(outcome='OPEN', realized_pnl=888.0)]
    out = _run({'payload': _payload(trades)})
    assert out['rowCount'] == 1, 'REJECTED and OPEN must not reach the ledger'
    assert '1 closed trade' in out['jnNetPnlSub']['text']
    assert '999' not in out['jnNetPnl']['text'] and '888' not in out['jnNetPnl']['text']


def test_eod_close_is_classified_by_pnl_sign():
    trades = [_trade(outcome='EOD_CLOSE', realized_pnl=25.0),
              _trade(outcome='EOD_CLOSE', realized_pnl=-15.0)]
    out = _run({'payload': _payload(trades)})
    assert out['rowCount'] == 2
    assert '1 win' in out['jnAvgWLSub']['text'] and '1 loss' in out['jnAvgWLSub']['text']


# ── Trade ledger ─────────────────────────────────────────────────────────

def test_ledger_empty_state():
    out = _run({'payload': _payload([])})
    assert 'No trades logged yet' in out['jnLedgerBody']['text']


def test_ledger_filtered_to_empty_says_so():
    out = _run({'payload': _payload([_trade()]), 'filter': 'losses'})
    assert 'No trades match this filter' in out['jnLedgerBody']['text']
    assert 'filtered from 1' in out['jnLedgerFoot']['text']


def test_ledger_populated_and_footer_totals():
    trades = [_trade(realized_pnl=10.0), _trade(realized_pnl=-4.0, outcome='LOSS')]
    out = _run({'payload': _payload(trades)})
    assert out['rowCount'] == 2
    assert '2 closed trades shown' in out['jnLedgerFoot']['text']
    assert '+$6.00' in out['jnLedgerFoot']['text']


def test_ledger_malformed_record_renders_without_inventing_values():
    """A partial record must render its known fields and mark the rest absent."""
    bad = {'ticker': 'NQ', 'outcome': 'WIN'}   # no direction, price, date or pnl
    out = _run({'payload': _payload([bad])})
    assert out['rowCount'] == 1
    html = out['jnLedgerBody']['html']
    assert 'NQ' in html
    assert 'Not recorded' in html, 'absent session/regime must be stated'
    assert '$0.00' in html, 'unknown P&L is 0, never invented'


# ── Trade review ─────────────────────────────────────────────────────────

def test_review_no_selection_state():
    out = _run({'payload': _payload([])})
    assert 'Select a trade to review it' in out['jnReviewInner']['text']


def test_review_shows_selected_trade():
    out = _run({'payload': _payload([_trade(ticker='ES')])})
    assert 'ES' in out['jnReviewInner']['text']


def test_review_states_missing_optional_fields():
    out = _run({'payload': _payload([_trade()])})   # no setup/session/regime
    txt = out['jnReviewInner']['text']
    assert txt.count('Not recorded') >= 3


def test_review_snapshot_and_evidence_unavailable_states():
    out = _run({'payload': _payload([_trade()])})
    html = out['jnReviewInner']['html']
    assert 'No chart image attached to this trade' in html
    assert 'No reasoning timeline stored for this trade' in html
    assert 'No NOVA review stored for this trade' in html
    assert html.count('jn-empty-box') == 3


def test_selection_survives_refresh_when_trade_still_exists():
    t = _trade(order_id='keep-me')
    p = _payload([t, _trade(order_id='other', ticker='ES')])
    out = _run({'payload': p, 'preselect': 'keep-me', 'thenPayload': p})
    assert out['selectedKey'] == 'keep-me'


def test_selection_falls_back_when_selected_trade_disappears():
    first = _payload([_trade(order_id='gone'), _trade(order_id='stays', ticker='ES')])
    second = _payload([_trade(order_id='stays', ticker='ES')])
    out = _run({'payload': first, 'preselect': 'gone', 'thenPayload': second})
    assert out['selectedKey'] == 'stays', 'must fall back to a row that exists'
    assert 'ES' in out['jnReviewInner']['text']


# ── By-Direction ─────────────────────────────────────────────────────────

def test_by_direction_both_populated():
    trades = [_trade(direction='LONG'), _trade(direction='SHORT', realized_pnl=-5.0, outcome='LOSS')]
    out = _run({'payload': _payload(trades)})
    assert 'Long' in out['jnByDirection']['text']
    assert 'Short' in out['jnByDirection']['text']


def test_by_direction_one_side_only_is_stated():
    out = _run({'payload': _payload([_trade(direction='SHORT')])})
    assert 'Short' in out['jnByDirection']['text']
    assert 'Only short trades recorded so far' in out['jnByDirectionNote']['text']


def test_by_direction_excludes_invalid_direction_honestly():
    trades = [_trade(direction='LONG'), _trade(direction=''), _trade(direction='SIDEWAYS')]
    out = _run({'payload': _payload(trades)})
    assert 'excluded' in out['jnByDirectionNote']['text']
    assert '2 records excluded' in out['jnByDirectionNote']['text']


def test_by_direction_empty():
    out = _run({'payload': _payload([])})
    assert out['jnByDirection']['text'] in ('No trade carries a usable direction.', '—')


# ── Daily P&L ────────────────────────────────────────────────────────────

def test_daily_multiple_days_positive_negative_and_flat():
    trades = [_trade(trade_date='2026-06-22', realized_pnl=10.0),
              _trade(trade_date='2026-06-23', realized_pnl=-6.0, outcome='LOSS'),
              _trade(trade_date='2026-06-24', realized_pnl=0.0, outcome='BREAKEVEN')]
    out = _run({'payload': _payload(trades)})
    html = out['jnDaily']['html']
    assert html.count('class="jn-col-plot"') == 3
    assert 'up' in html and 'down' in html and 'flat' in html
    assert '3 sessions' in out['jnDailyMeta']['text']


def test_daily_single_day():
    out = _run({'payload': _payload([_trade()])})
    assert out['jnDaily']['html'].count('class="jn-col-plot"') == 1
    assert 'All time' in out['jnDailyMeta']['text'] and '1 session' in out['jnDailyMeta']['text']


def test_daily_no_closed_trades():
    out = _run({'payload': _payload([])})
    assert 'No closed trades yet' in out['jnDaily']['text']


def test_daily_excludes_invalid_dates_honestly():
    trades = [_trade(trade_date='2026-06-24'), _trade(trade_date=''), _trade(trade_date='nope')]
    out = _run({'payload': _payload(trades)})
    assert '2 records excluded' in out['jnDailyNote']['text']
    assert 'invalid date' in out['jnDailyNote']['text']


def test_daily_keeps_only_the_last_ten_sessions():
    trades = [_trade(trade_date=f'2026-06-{d:02d}', realized_pnl=1.0) for d in range(1, 15)]
    out = _run({'payload': _payload(trades)})
    assert out['jnDaily']['html'].count('class="jn-col-plot"') == 10




# ── Dynamic filters ──────────────────────────────────────────────────────
#
# Instrument and regime options are built from the values the records
# genuinely carry. Nothing is hard-coded, and a dimension with no usable
# values is disabled with a stated reason rather than invented.

def test_instrument_filter_is_derived_from_real_records():
    """The real dataset holds SPY, not NQ/ES -- the options must follow it."""
    trades = [_trade(ticker='SPY'), _trade(ticker='QQQ')]
    out = _run({'payload': _payload(trades)})
    html = out['jFilterBar']['html']
    assert 'data-fval="SPY"' in html
    assert 'data-fval="QQQ"' in html
    assert 'data-fval="NQ"' not in html, 'must not offer an instrument no record carries'


def test_instrument_filter_narrows_the_ledger():
    trades = [_trade(ticker='SPY'), _trade(ticker='QQQ')]
    out = _run({'payload': _payload(trades), 'instrument': 'SPY'})
    assert out['rowCount'] == 1
    assert 'SPY' in out['jnLedgerBody']['html']
    assert 'QQQ' not in out['jnLedgerBody']['html']


def test_regime_filter_disabled_with_reason_when_nothing_recorded():
    out = _run({'payload': _payload([_trade()])})
    html = out['jFilterBar']['html']
    assert 'is-disabled' in html
    assert 'No regime recorded on any trade' in html


def test_regime_filter_offers_only_recorded_regimes():
    trades = [_trade(active_regime='Trending Up'), _trade(active_regime='')]
    out = _run({'payload': _payload(trades)})
    html = out['jFilterBar']['html']
    assert 'data-fval="Trending Up"' in html
    assert 'All regimes' in html


def test_period_filter_narrows_by_date():
    import datetime
    today = datetime.date.today().isoformat()
    old = (datetime.date.today() - datetime.timedelta(days=200)).isoformat()
    trades = [_trade(trade_date=today), _trade(trade_date=old)]
    out = _run({'payload': _payload(trades), 'period': 'week'})
    assert out['rowCount'] == 1


def test_period_filter_recomputes_every_performance_region():
    """The period control is analytical scope, not a ledger-only hide/show."""
    import datetime
    today = datetime.date.today().isoformat()
    old = (datetime.date.today() - datetime.timedelta(days=200)).isoformat()
    trades = [
        _trade(trade_date=today, realized_pnl=100.0, outcome='WIN', active_regime='CURRENT'),
        _trade(trade_date=old, realized_pnl=-900.0, outcome='LOSS', active_regime='OLD'),
    ]
    out = _run({'payload': _payload(trades), 'period': 'week'})
    assert out['jnNetPnl']['text'] == '+$100.00'
    assert out['jnNetPnlLabel']['text'] == 'Net P&L · This week'
    assert '1 closed trade' in out['jnNetPnlSub']['text']
    assert out['jnWinRate']['text'] == '100%'
    assert 'CURRENT' in out['jnByRegime']['text']
    assert 'OLD' not in out['jnByRegime']['text']
    assert today[5:].replace('-', '/') in out['jnDaily']['text']
    assert old[5:].replace('-', '/') not in out['jnDaily']['text']


def test_this_month_uses_calendar_month_not_rolling_thirty_days():
    import datetime
    today = datetime.date.today()
    current = today.replace(day=1).isoformat()
    prior = (today.replace(day=1) - datetime.timedelta(days=1)).isoformat()
    trades = [
        _trade(trade_date=current, realized_pnl=75.0, outcome='WIN'),
        _trade(trade_date=prior, realized_pnl=-500.0, outcome='LOSS'),
    ]
    out = _run({'payload': _payload(trades), 'period': 'month'})
    assert out['rowCount'] == 1
    assert out['jnNetPnl']['text'] == '+$75.00'
    assert out['jnNetPnlLabel']['text'] == 'Net P&L · This month'


def test_selection_follows_the_filtered_ledger():
    """Filtering the selected trade out must move selection to a visible row."""
    trades = [_trade(order_id='win-1', outcome='WIN', realized_pnl=10.0),
              _trade(order_id='loss-1', outcome='LOSS', realized_pnl=-5.0)]
    out = _run({'payload': _payload(trades), 'preselect': 'win-1', 'filter': 'losses'})
    assert out['selectedKey'] == 'loss-1'
    assert out['rowCount'] == 1


def test_stale_instrument_selection_resets_when_it_disappears():
    first = _payload([_trade(ticker='SPY'), _trade(ticker='QQQ')])
    second = _payload([_trade(ticker='SPY')])
    out = _run({'payload': first, 'instrument': 'QQQ', 'thenPayload': second})
    assert out['rowCount'] == 1, 'filter must fall back to All when QQQ is gone'


# ── Humanised missing-data labels ────────────────────────────────────────

def test_unknown_buckets_render_as_not_recorded():
    out = _run({'payload': _payload([_trade()],
                by_regime={'UNKNOWN': {'wins': 1, 'losses': 0, 'breakevens': 0, 'pnl': 10.0, 'win_rate': 100.0}},
                by_session={'UNKNOWN': {'wins': 1, 'losses': 0, 'breakevens': 0, 'pnl': 10.0, 'win_rate': 100.0}})})
    assert 'Not recorded' in out['jnByRegime']['text']
    assert 'UNKNOWN' not in out['jnByRegime']['text']
    assert 'Not recorded' in out['jnBySession']['text']


def test_untagged_setup_keeps_the_established_vocabulary():
    out = _run({'payload': _payload([_trade()],
                by_setup_type={'Untagged': {'wins': 1, 'losses': 0, 'breakevens': 0, 'pnl': 10.0, 'win_rate': 100.0}})})
    assert 'Untagged' in out['jnBySetup']['text']


def test_sample_size_is_stated_once_per_row():
    out = _run({'payload': _payload([_trade()],
                by_regime={'Trending Up': {'wins': 1, 'losses': 0, 'breakevens': 0, 'pnl': 10.0, 'win_rate': 100.0}})})
    txt = out['jnByRegime']['text']
    assert '1 trade' in txt
    assert 'n=1' not in txt, 'sample size must not appear twice in the same row'


# ── Single-day Daily P&L presentation ────────────────────────────────────

def test_single_day_uses_the_compact_strip():
    out = _run({'payload': _payload([_trade()])})
    assert out['jnDaily']['html'].count('class="jn-col-plot"') == 1


def test_multiple_days_use_the_full_strip():
    trades = [_trade(trade_date='2026-06-22'), _trade(trade_date='2026-06-23')]
    out = _run({'payload': _payload(trades)})
    assert out['jnDaily']['html'].count('class="jn-col-plot"') == 2




# ── Daily P&L mini-bar chart ─────────────────────────────────────────────
#
# The chart aggregates genuine closed-trade P&L by trading date. It keeps ten
# session slots open, colours by sign, carries a zero baseline, and scales every
# bar against the largest absolute session result. It never invents a session.

def test_daily_single_real_session_renders_exactly_one_bar():
    """The live dataset holds one session; the chart must show one bar, not ten."""
    out = _run({'payload': _payload([_trade(trade_date='2026-06-24', realized_pnl=514.91)])})
    html = out['jnDaily']['html']
    assert html.count('class="jn-col-plot"') == 1
    assert html.count('jn-dbar') == 1
    assert '06/24' in html
    assert '+$514.91' in html
    assert out['jnDailyMeta']['text'] == 'All time · 1 session'


def test_daily_column_count_follows_the_real_sessions():
    out = _run({'payload': _payload([_trade(trade_date='2026-06-24')])})
    assert out['jnDailyStyle']['n'] == '1', 'one genuine session, one column'
    assert out['jnDaily']['html'].count('class="jn-col-plot"') == 1


def test_daily_sparse_history_says_so_without_an_empty_panel():
    out = _run({'payload': _payload([_trade(trade_date='2026-06-24')])})
    note = out['jnDailyNote']['text']
    assert 'Additional sessions will populate this history' in note
    assert len(note) < 200, 'the hint is a note, not an empty-state panel'


def test_daily_full_history_drops_the_sparse_hint():
    trades = [_trade(order_id='t%d' % i, trade_date='2026-06-%02d' % (10 + i)) for i in range(8)]
    out = _run({'payload': _payload(trades)})
    assert 'Additional sessions' not in out['jnDailyNote']['text']


def test_daily_zero_baseline_is_present():
    out = _run({'payload': _payload([_trade(trade_date='2026-06-24')])})
    assert 'class="jn-zero"' in out['jnDaily']['html']


def test_daily_colours_follow_the_sign():
    trades = [_trade(order_id='w', trade_date='2026-06-22', realized_pnl=300.0, outcome='WIN'),
              _trade(order_id='l', trade_date='2026-06-23', realized_pnl=-150.0, outcome='LOSS'),
              _trade(order_id='b', trade_date='2026-06-24', realized_pnl=0.0, outcome='BREAKEVEN')]
    html = _run({'payload': _payload(trades)})['jnDaily']['html']
    assert 'jn-dbar up' in html
    assert 'jn-dbar down' in html
    assert 'jn-dbar flat' in html


def test_daily_bar_heights_are_proportional_to_the_largest_absolute_result():
    trades = [_trade(order_id='a', trade_date='2026-06-22', realized_pnl=400.0),
              _trade(order_id='b', trade_date='2026-06-23', realized_pnl=100.0)]
    html = _run({'payload': _payload(trades)})['jnDaily']['html']
    assert '--mag:100.00%' in html, 'largest session anchors the scale'
    assert '--mag:25.00%' in html, '100 of 400 must render at a quarter height'


def test_daily_baseline_splits_by_the_positive_share_of_the_scale():
    trades = [_trade(order_id='a', trade_date='2026-06-22', realized_pnl=300.0),
              _trade(order_id='b', trade_date='2026-06-23', realized_pnl=-100.0, outcome='LOSS')]
    style = _run({'payload': _payload(trades)})['jnDailyStyle']
    assert style['pos'] == '75.000%', 'positive half is 300 of a 400 span'
    assert style['neg'] == '25.000%'


def test_daily_all_positive_puts_the_baseline_on_the_floor():
    trades = [_trade(order_id='a', trade_date='2026-06-22', realized_pnl=300.0),
              _trade(order_id='b', trade_date='2026-06-23', realized_pnl=100.0)]
    assert _run({'payload': _payload(trades)})['jnDailyStyle']['pos'] == '100.000%'


def test_daily_all_breakeven_keeps_the_ticks_on_the_line():
    trades = [_trade(order_id='a', trade_date='2026-06-22', realized_pnl=0.0, outcome='BREAKEVEN'),
              _trade(order_id='b', trade_date='2026-06-23', realized_pnl=0.0, outcome='BREAKEVEN')]
    out = _run({'payload': _payload(trades)})
    assert out['jnDailyStyle']['pos'] == '100.000%', 'no magnitude anywhere -- baseline to the floor'
    assert out['jnDaily']['html'].count('jn-dbar flat') == 2


def test_daily_breakeven_beside_losses_sits_on_the_lower_side():
    """With no positive side to stand on, the flat tick moves below the line."""
    trades = [_trade(order_id='a', trade_date='2026-06-22', realized_pnl=-200.0, outcome='LOSS'),
              _trade(order_id='b', trade_date='2026-06-23', realized_pnl=0.0, outcome='BREAKEVEN')]
    out = _run({'payload': _payload(trades)})
    assert out['jnDailyStyle']['pos'] == '0.000%'
    assert '<span class="jn-col-neg"><i class="jn-dbar flat"' in out['jnDaily']['html']


def test_daily_aggregates_multiple_trades_sharing_one_date():
    trades = [_trade(order_id='a', trade_date='2026-06-24', realized_pnl=200.0),
              _trade(order_id='b', trade_date='2026-06-24', realized_pnl=-50.0, outcome='LOSS'),
              _trade(order_id='c', trade_date='2026-06-24', realized_pnl=25.0)]
    out = _run({'payload': _payload(trades)})
    html = out['jnDaily']['html']
    assert html.count('class="jn-col-plot"') == 1, 'one date is one session'
    assert '+$175.00' in html, '200 - 50 + 25 must net to 175'


def test_daily_excludes_invalid_dates_from_the_chart_not_just_the_note():
    trades = [_trade(order_id='ok', trade_date='2026-06-24', realized_pnl=100.0),
              _trade(order_id='bad', trade_date='not-a-date', realized_pnl=999.0),
              _trade(order_id='none', trade_date='', realized_pnl=999.0)]
    out = _run({'payload': _payload(trades)})
    html = out['jnDaily']['html']
    assert html.count('class="jn-col-plot"') == 1
    assert '999' not in html, 'an undated trade must not reach the chart'
    assert '2 records excluded' in out['jnDailyNote']['text']


def test_daily_empty_state_is_honest_and_carries_no_bars():
    out = _run({'payload': _payload([])})
    assert 'No closed trades yet' in out['jnDaily']['text']
    assert 'jn-dbar' not in out['jnDaily']['html']
    assert 'is-empty' in out['jnDaily']['className']


def test_daily_dated_none_empty_state_names_the_real_reason():
    out = _run({'payload': _payload([_trade(trade_date='')])})
    assert 'No closed trade carries a usable date' in out['jnDaily']['text']
    assert 'jn-dbar' not in out['jnDaily']['html']


def test_daily_switches_to_the_row_form_only_when_dense():
    few = [_trade(order_id='t%d' % i, trade_date='2026-06-%02d' % (10 + i)) for i in range(6)]
    many = [_trade(order_id='t%d' % i, trade_date='2026-06-%02d' % (10 + i)) for i in range(7)]
    assert _run({'payload': _payload(few)})['jnDailyDense'] is None
    assert _run({'payload': _payload(many)})['jnDailyDense'] == '1'


def test_daily_every_session_label_and_value_is_rendered():
    trades = [_trade(order_id='a', trade_date='2026-06-22', realized_pnl=300.0),
              _trade(order_id='b', trade_date='2026-06-23', realized_pnl=-100.0, outcome='LOSS')]
    html = _run({'payload': _payload(trades)})['jnDaily']['html']
    for token in ('06/22', '06/23', '+$300.00', '-$100.00'):
        assert token in html, token


if __name__ == '__main__':
    raise SystemExit(pytest.main([__file__, '-v']))
