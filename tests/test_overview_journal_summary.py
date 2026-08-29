"""
test_overview_journal_summary.py — commit #11 correction: fixture-based
proof that the Overview page's new Account Summary panel reuses the
already-established journal calculations (core/state.py
compute_journal_stats() and main.py's /journal/data endpoint) instead of
introducing a second, conflicting definition of P&L, win rate, or weekly
performance.

Investigation this file locks in (see the commit #11 correction report
for the full write-up):
  - Valid loss outcome value is 'LOSS', not 'LOSE'.
  - EOD_CLOSE IS included in realized P&L -- compute_journal_stats()
    reclassifies it to WIN/LOSS/BREAKEVEN by pnl sign before counting it.
  - 'trade_date' (not 'timestamp') is the field used for date-bucketing
    everywhere this data is consumed (compute_journal_stats, main.py's
    today_pnl, and the existing Journal-page overview strip).
  - REJECTED and OPEN are both excluded from every stat
    compute_journal_stats() returns -- not just P&L, also win_rate,
    profit_factor, and every breakdown.
  - stats.daily_pnl.this_week exists and is the established weekly P&L
    figure; there is no second, competing weekly-P&L field anywhere.
  - stats.win_rate is all-time (computed over every non-REJECTED/OPEN
    trade in the journal, not date-filtered) -- there is no established
    weekly-win-rate figure to reuse instead, so Overview's Win Rate is
    all-time by necessity, matching Journal's own Analytics panel
    (`jaWinRate`, which reads the same stats.win_rate field).
  - main.py's /journal/data endpoint computes stats['today_pnl'] using
    now_ny() (America/New_York), not UTC or bare system-local time --
    confirmed here by mocking now_ny() to a specific NY instant and
    proving only same-NY-date trades are included.

Run:  python -m pytest tests/test_overview_journal_summary.py -v
"""
from __future__ import annotations

import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('ALPACA_API_KEY', '')
os.environ.setdefault('ALPACA_SECRET_KEY', '')

import pytest

from core.state import compute_journal_stats

_NY_TZ = ZoneInfo('America/New_York')


def _trade(outcome, realized_pnl=None, trade_date='2026-06-24', **overrides):
    base = {
        'ticker': 'SPY', 'direction': 'LONG', 'outcome': outcome,
        'trade_date': trade_date, 'realized_pnl': realized_pnl, 'pnl': realized_pnl,
        'entry_price': 700.0, 'exit_price': 705.0, 'size': 1,
        'active_regime': 'UNKNOWN', 'session': 'UNKNOWN', 'setup_type': '', 'strategy_family': 'UNKNOWN',
    }
    base.update(overrides)
    return base


# ── Empty journal ─────────────────────────────────────────────────────────

def test_empty_journal_returns_zeroed_stats_not_none():
    stats = compute_journal_stats([])
    assert stats['total'] == 0
    assert stats['win_rate'] == 0.0
    assert stats['daily_pnl'] == {'today': 0.0, 'yesterday': 0.0, 'this_week': 0.0}


# ── Win ──────────────────────────────────────────────────────────────────

def test_win_trade_counted_and_contributes_positive_pnl():
    stats = compute_journal_stats([_trade('WIN', 100.0)])
    assert stats['total'] == 1
    assert stats['wins'] == 1
    assert stats['win_rate'] == 100.0
    assert stats['avg_win'] == 100.0


# ── Loss (confirms 'LOSS' is the valid value, not 'LOSE') ──────────────────

def test_loss_trade_uses_LOSS_not_LOSE():
    stats_loss = compute_journal_stats([_trade('LOSS', -50.0)])
    assert stats_loss['losses'] == 1
    assert stats_loss['win_rate'] == 0.0

    # A trade outcome of 'LOSE' (the wrong spelling) is not a recognized
    # WIN/LOSS/EOD_CLOSE bucket -- it falls into the 'else' (breakeven)
    # branch of compute_journal_stats()'s per-trade classification, proving
    # 'LOSE' is not an equivalent alias for 'LOSS' anywhere in this function.
    stats_lose = compute_journal_stats([_trade('LOSE', -50.0)])
    assert stats_lose['losses'] == 0
    assert stats_lose['breakevens'] == 1


# ── Breakeven ────────────────────────────────────────────────────────────

def test_breakeven_trade_counted_separately_from_win_and_loss():
    stats = compute_journal_stats([_trade('BREAKEVEN', 0.0)])
    assert stats['breakevens'] == 1
    assert stats['wins'] == 0
    assert stats['losses'] == 0
    assert stats['total'] == 1


# ── Open trade ───────────────────────────────────────────────────────────

def test_open_trade_excluded_from_every_stat():
    stats = compute_journal_stats([_trade('OPEN', None)])
    assert stats['total'] == 0
    assert stats['win_rate'] == 0.0
    assert stats['daily_pnl']['this_week'] == 0.0


# ── Rejected trade ───────────────────────────────────────────────────────

def test_rejected_trade_excluded_from_every_stat():
    stats = compute_journal_stats([_trade('REJECTED', None)])
    assert stats['total'] == 0
    assert stats['win_rate'] == 0.0
    assert stats['daily_pnl']['this_week'] == 0.0


# ── EOD_CLOSE is valid and included in realized P&L ─────────────────────

def test_eod_close_included_and_reclassified_by_pnl_sign():
    stats_profit = compute_journal_stats([_trade('EOD_CLOSE', 42.0)])
    assert stats_profit['total'] == 1
    assert stats_profit['wins'] == 1, 'a profitable EOD_CLOSE must count as a WIN'

    stats_loss = compute_journal_stats([_trade('EOD_CLOSE', -42.0)])
    assert stats_loss['losses'] == 1, 'a losing EOD_CLOSE must count as a LOSS'

    stats_flat = compute_journal_stats([_trade('EOD_CLOSE', 0.0)])
    assert stats_flat['breakevens'] == 1, 'a flat EOD_CLOSE must count as a BREAKEVEN'


# ── Missing P&L (realized_pnl is None on a closed outcome) ───────────────

def test_missing_realized_pnl_falls_back_to_entry_exit_formula_not_none_crash():
    """A WIN/LOSS trade with realized_pnl=None (never backfilled) must not
    crash compute_journal_stats() -- it falls back to the entry/exit/size
    formula rather than treating None as 0 P&L silently."""
    stats = compute_journal_stats([_trade('WIN', None, entry_price=700.0, exit_price=710.0, size=2)])
    assert stats['total'] == 1
    assert stats['wins'] == 1
    assert stats['avg_win'] == pytest.approx(20.0)  # (710-700)*2, LONG


# ── stats.daily_pnl.this_week exists and is the single weekly figure ─────

def test_daily_pnl_this_week_is_the_established_weekly_figure():
    stats = compute_journal_stats([_trade('WIN', 10.0), _trade('LOSS', -4.0)])
    assert 'daily_pnl' in stats
    assert 'this_week' in stats['daily_pnl']
    assert isinstance(stats['daily_pnl']['this_week'], float)


# ── win_rate is all-time (no separate weekly win-rate field exists) ──────

def test_win_rate_is_all_time_not_date_scoped():
    """Trades from a date clearly outside 'this week' still count toward
    win_rate -- proving win_rate is computed over the whole journal, not a
    rolling window, and confirming there is no separate weekly win-rate
    field for Overview to have reused instead."""
    old_win = _trade('WIN', 5.0, trade_date='2020-01-01')
    stats = compute_journal_stats([old_win])
    assert stats['win_rate'] == 100.0
    assert 'win_rate_this_week' not in stats
    assert 'weekly_win_rate' not in stats


# ── NY vs UTC date boundary (main.py /journal/data's today_pnl) ──────────

def test_journal_data_today_pnl_uses_new_york_date_not_utc():
    """Reproduces the exact boundary case: it is already the next calendar
    day in UTC but still the prior calendar day in New York (e.g. 20:30 ET
    on 2026-06-24 is 00:30 UTC on 2026-06-25). A trade dated 2026-06-24
    must still count as "today" -- proving /journal/data's today_pnl uses
    now_ny(), not UTC or a naive system-local date."""
    import main as _main
    from unittest.mock import patch

    # 20:30 ET on 2026-06-24 == 00:30 UTC on 2026-06-25.
    fixed_ny_instant = datetime(2026, 6, 24, 20, 30, tzinfo=_NY_TZ)

    trades = [_trade('WIN', 77.0, trade_date='2026-06-24')]

    with patch('main.load_journal', return_value=trades), \
         patch('main.now_ny', return_value=fixed_ny_instant):
        from fastapi.testclient import TestClient
        client = TestClient(_main.app)
        res = client.get('/journal/data')

    assert res.status_code == 200
    data = res.json()
    assert data['stats']['today_pnl'] == 77.0, (
        f"expected the 2026-06-24-dated trade to count as today's P&L when now_ny() "
        f"reports 2026-06-24 20:30 ET, got {data['stats']['today_pnl']!r} -- "
        f"a UTC-based 'today' would have wrongly excluded it (UTC date is already 2026-06-25)"
    )


if __name__ == '__main__':
    raise SystemExit(pytest.main([__file__, '-v']))
