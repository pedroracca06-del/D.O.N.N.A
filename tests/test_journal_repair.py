"""
test_journal_repair.py — regression test for the DONNA_AUTO_RECONSTRUCTED /
DONNA_EOD journal-split bug.

Background: the EOD-close matcher and check_position_outcomes() used to filter
strictly on source == 'DONNA_AUTO'. A DONNA_AUTO_RECONSTRUCTED entry (the same
trade, recovered by services/audit.py after a lost-update journal write) never
matched that filter, so its real EOD close landed as a brand-new, unlinked
DONNA_EOD row instead of updating the original entry. One real trade then
showed up as two journal records: an OPEN entry that never closes, plus an
orphaned close with no order_id — corrupting win rate, P&L, and profit factor.

execution.py now matches on AUTONOMOUS_JOURNAL_SOURCES (DONNA_AUTO +
DONNA_AUTO_RECONSTRUCTED) going forward. This test locks in the one-time
repair functions in services/audit.py that fix pre-existing splits and flag
any future recurrence.

Run:  python -m pytest tests/test_journal_repair.py -v
      (or: python tests/test_journal_repair.py)
"""
from __future__ import annotations

import os
import sys

# Alpaca must stay unconfigured for this test: importing services.execution
# runs a one-time live "QQQ cleanup on load" call at module scope. Blanking
# the keys makes that call no-op safely instead of touching a real account.
os.environ['ALPACA_API_KEY']    = ''
os.environ['ALPACA_SECRET_KEY'] = ''

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.audit import _merge_orphaned_eod_closes, find_unlinked_reconstructed_closes
from core.state import compute_journal_stats


def _split_trade_fixture() -> list[dict]:
    """Minimal reproduction of the real production split (order_id 81f6fccc...)."""
    return [
        {
            'source':        'DONNA_AUTO_RECONSTRUCTED',
            'order_id':      '81f6fccc-4dfd-48c5-9058-b7124af5b68d',
            'ticker':        'SPY',
            'direction':     'SHORT',
            'trade_date':    '2026-06-22',
            'entry_price':   748.47,
            'exit_price':    None,
            'size':          100,
            'realized_pnl':  None,
            'pnl':           None,
            'outcome':       'OPEN',
            'notes':         'RECONSTRUCTED by audit.py from execution_trace.',
        },
        {
            'source':        'DONNA_EOD',
            'ticker':        'SPY',
            'direction':     'SHORT',
            'trade_date':    '2026-06-22',
            'entry_price':   748.4491,
            'exit_price':    -743.3,
            'exit_time':     '15:45:31 ET',
            'size':          100,
            'realized_pnl':  514.91,
            'pnl':           514.91,
            'outcome':       'EOD_CLOSE',
            'notes':         'EOD forced close @ -743.3',
        },
    ]


def test_unlinked_split_is_flagged():
    trades = _split_trade_fixture()
    flags = find_unlinked_reconstructed_closes(trades)
    assert len(flags) == 1
    assert flags[0]['order_id'] == '81f6fccc-4dfd-48c5-9058-b7124af5b68d'


def test_merge_collapses_split_into_one_record():
    trades = _split_trade_fixture()
    merged = _merge_orphaned_eod_closes(trades)

    assert len(merged) == 1
    assert len(trades) == 1, 'orphaned DONNA_EOD row must be removed after merge'

    repaired = trades[0]
    assert repaired['order_id'] == '81f6fccc-4dfd-48c5-9058-b7124af5b68d'
    assert repaired['outcome'] == 'WIN'
    assert repaired['realized_pnl'] == 514.91
    assert repaired['pnl'] == 514.91
    assert repaired['exit_price'] is not None
    assert repaired['exit_price'] > 0, 'exit_price must be sign-corrected, not the raw -743.3'
    assert 'RECONSTRUCTED' in repaired['notes'], 'original audit note must survive the merge'
    assert 'Merged orphaned EOD close' in repaired['notes']


def test_no_unlinked_entries_remain_after_merge():
    trades = _split_trade_fixture()
    _merge_orphaned_eod_closes(trades)
    assert find_unlinked_reconstructed_closes(trades) == []


def test_merge_is_a_noop_when_nothing_is_split():
    trades = [{
        'source':       'DONNA_AUTO',
        'order_id':     '77ee938b-da7e-4176-b625-3d63bb1e3f35',
        'ticker':       'SPY',
        'direction':    'SHORT',
        'trade_date':   '2026-06-23',
        'entry_price':  733.23,
        'exit_price':   734.53,
        'size':         100,
        'realized_pnl': -182.0,
        'pnl':          -182.0,
        'outcome':      'EOD_CLOSE',
        'notes':        'DONNA autonomous trade.',
    }]
    merged = _merge_orphaned_eod_closes(trades)
    assert merged == []
    assert len(trades) == 1
    assert find_unlinked_reconstructed_closes(trades) == []


def test_stats_are_correct_after_merge_not_double_counted():
    """
    Regression for the actual production symptom: before the merge, the
    unlinked OPEN entry fell into compute_journal_stats()'s breakeven branch
    with a phantom P&L derived from a null exit_price, corrupting weekly P&L
    and diluting win rate. After the merge there must be exactly one WIN.
    """
    trades = _split_trade_fixture()

    stats_before = compute_journal_stats(trades)
    assert stats_before['total'] == 2          # the trade is double-counted

    _merge_orphaned_eod_closes(trades)
    stats_after = compute_journal_stats(trades)

    assert stats_after['total'] == 1
    assert stats_after['wins'] == 1
    assert stats_after['losses'] == 0
    assert stats_after['breakevens'] == 0
    assert stats_after['daily_pnl']['this_week'] == 514.91


if __name__ == '__main__':
    tests = [v for k, v in list(globals().items()) if k.startswith('test_')]
    failed = 0
    for t in tests:
        try:
            t()
            print(f'PASS  {t.__name__}')
        except AssertionError as e:
            failed += 1
            print(f'FAIL  {t.__name__}: {e}')
    print(f'\n{len(tests) - failed}/{len(tests)} passed')
    sys.exit(1 if failed else 0)
