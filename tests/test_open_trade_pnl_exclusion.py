"""
test_open_trade_pnl_exclusion.py — regression test for the OPEN-trade P&L
contamination bug in compute_journal_stats().

Background: a trade with outcome='OPEN' has realized_pnl=None by
definition (it hasn't closed yet). compute_journal_stats()'s
realized_pnl-is-None fallback computed (exit_price - entry_price) * size
(or the SHORT-direction mirror) instead -- and since an open trade's
exit_price is also None, that defaulted to 0, producing
(entry_price - 0) * size: pure notional/entry-value, not P&L.

Live incident: a real open SPY SHORT position (entry_price=734.56,
size=101) contaminated "This Week" with +$74,190.56 (734.56 * 101) on top
of $271.36 of real realized P&L, displaying as +$74,461.92. Confirmed by
hand-tracing the exact live journal before any fix was applied.

Fix: OPEN (like REJECTED) is now skipped entirely at the top of
compute_journal_stats()'s per-trade loop -- before pnl is computed at all,
so the entry/exit fallback formula never runs for it. This means OPEN
trades contribute 0 to total, wins/losses/breakevens, win_rate,
profit_factor, daily_pnl (today/yesterday/this_week), and every
regime/session/setup_type/strategy_family/emotional_state breakdown --
not just daily_pnl specifically.

Run:  python -m pytest tests/test_open_trade_pnl_exclusion.py -v
      (or: python tests/test_open_trade_pnl_exclusion.py)
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.state import compute_journal_stats


def _closed_trade(realized_pnl, trade_date='2026-06-24', outcome=None):
    return {
        'ticker': 'SPY', 'direction': 'SHORT', 'outcome': outcome or ('WIN' if realized_pnl > 0 else 'LOSS'),
        'trade_date': trade_date, 'realized_pnl': realized_pnl, 'pnl': realized_pnl,
        'entry_price': 700.0, 'exit_price': 700.0 - realized_pnl / 100, 'size': 100,
        'active_regime': 'UNKNOWN', 'session': 'UNKNOWN', 'setup_type': '', 'strategy_family': 'UNKNOWN',
    }


# ── 1. OPEN trade with realized_pnl=None ────────────────────────────────────

def test_open_trade_with_realized_pnl_none_contributes_zero():
    trade = {
        'ticker': 'SPY', 'direction': 'SHORT', 'outcome': 'OPEN', 'trade_date': '2026-06-25',
        'realized_pnl': None, 'pnl': None, 'entry_price': 734.56, 'exit_price': None, 'size': 1,
        'active_regime': 'UNKNOWN', 'session': 'UNKNOWN', 'setup_type': '', 'strategy_family': 'UNKNOWN',
    }
    stats = compute_journal_stats([trade])
    assert stats['total'] == 0
    assert stats['wins'] == 0
    assert stats['losses'] == 0
    assert stats['breakevens'] == 0
    assert stats['daily_pnl']['today'] == 0.0
    assert stats['daily_pnl']['this_week'] == 0.0
    assert stats['win_rate'] == 0.0
    assert stats['profit_factor'] == 0.0


# ── 2. OPEN trade with exit_price=None specifically ─────────────────────────

def test_open_trade_with_exit_price_none_does_not_default_to_zero_and_multiply():
    """The exact mechanism: exit_price=None must never be treated as 0 and
    multiplied by entry_price/size for an open trade -- because the trade
    is skipped before that formula ever runs."""
    trade = {
        'ticker': 'SPY', 'direction': 'SHORT', 'outcome': 'OPEN', 'trade_date': '2026-06-25',
        'realized_pnl': None, 'exit_price': None, 'entry_price': 9999.0, 'size': 1,
        'active_regime': 'UNKNOWN', 'session': 'UNKNOWN', 'setup_type': '', 'strategy_family': 'UNKNOWN',
    }
    stats = compute_journal_stats([trade])
    # A high entry_price with the old bug would have produced a huge phantom
    # value (9999 * 1). It must not appear anywhere.
    assert stats['daily_pnl']['this_week'] == 0.0
    assert stats['daily_pnl']['today'] == 0.0
    assert stats['total'] == 0


# ── 3. OPEN trade with size > 1 -- the exact live incident shape ───────────

def test_open_trade_with_size_greater_than_one_reproduces_and_fixes_live_incident():
    """Exact reproduction of the live incident: SPY SHORT, entry_price=734.56,
    size=101, OPEN. The old bug computed (734.56 - 0) * 101 = 74190.56 and
    added it to this_week. Must now contribute exactly 0."""
    trade = {
        'ticker': 'SPY', 'direction': 'SHORT', 'outcome': 'OPEN', 'trade_date': '2026-06-25',
        'realized_pnl': None, 'pnl': None, 'entry_price': 734.56, 'exit_price': None, 'size': 101,
        'order_id': '4e21f3b5-01a1-48f8-9614-1b7c71e94495', 'source': 'DONNA_AUTO',
        'active_regime': 'UNKNOWN', 'session': 'UNKNOWN', 'setup_type': '', 'strategy_family': 'UNKNOWN',
    }
    stats = compute_journal_stats([trade])
    assert stats['daily_pnl']['this_week'] == 0.0
    assert stats['daily_pnl']['today'] == 0.0
    assert stats['total'] == 0
    assert stats['breakevens'] == 0, 'must not be miscounted as a breakeven either'


# ── 4. Mixed open + closed journal -- only closed trades count ─────────────

def test_mixed_open_and_closed_journal_only_counts_closed():
    """Reproduces the exact live journal shape: 8 real closed trades summing
    to $271.36, plus the one open SPY position that previously contaminated
    the total with +$74,190.56. After the fix, only the closed trades count."""
    closed_trades = [
        _closed_trade(495.0,   '2026-06-22'),
        _closed_trade(514.91,  '2026-06-22'),
        _closed_trade(-182.0,  '2026-06-23', outcome='EOD_CLOSE'),
        _closed_trade(-700.0,  '2026-06-24'),
        _closed_trade(15.15,   '2026-06-24'),
        _closed_trade(-492.88, '2026-06-24'),
        _closed_trade(677.74,  '2026-06-24', outcome='EOD_CLOSE'),
        _closed_trade(-56.56,  '2026-06-24', outcome='EOD_CLOSE'),
    ]
    open_trade = {
        'ticker': 'SPY', 'direction': 'SHORT', 'outcome': 'OPEN', 'trade_date': '2026-06-25',
        'realized_pnl': None, 'pnl': None, 'entry_price': 734.56, 'exit_price': None, 'size': 101,
        'active_regime': 'UNKNOWN', 'session': 'UNKNOWN', 'setup_type': '', 'strategy_family': 'UNKNOWN',
    }

    stats_closed_only = compute_journal_stats(closed_trades)
    stats_mixed        = compute_journal_stats(closed_trades + [open_trade])

    # The open trade must change NOTHING about the realized metrics.
    assert stats_mixed['total']         == stats_closed_only['total']         == 8
    assert stats_mixed['wins']          == stats_closed_only['wins']
    assert stats_mixed['losses']        == stats_closed_only['losses']
    assert stats_mixed['breakevens']    == stats_closed_only['breakevens']    == 0
    assert stats_mixed['profit_factor'] == stats_closed_only['profit_factor']
    assert stats_mixed['daily_pnl']['this_week'] == stats_closed_only['daily_pnl']['this_week']

    # And that shared value must be the real sum, not 74,461.92.
    assert round(stats_mixed['daily_pnl']['this_week'], 2) == 271.36
    assert stats_mixed['daily_pnl']['this_week'] != 74461.92


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
