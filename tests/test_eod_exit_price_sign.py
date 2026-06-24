"""
test_eod_exit_price_sign.py — regression test for the EOD short-exit-price
sign bug.

Background: close_all_positions_eod() computed exit_price as
market_value / abs(qty). Alpaca's market_value carries the position's sign
(negative for shorts), so dividing by an already-abs()'d qty left the sign on
the result -- every SHORT EOD close was journaled with a negative exit_price
(e.g. -743.30 instead of 743.30). realized_pnl/outcome come from Alpaca's own
unrealized_pnl directly, never from exit_price, so stored P&L and win/loss
were never wrong -- only the exit_price field itself was corrupted.

Fixed in services/execution.py via _eod_exit_price(), which divides by the
SIGNED qty. services/audit.py's fix_negative_short_exit_prices() repairs any
pre-existing record and is wired into reconcile_execution_audit() so a future
recurrence is never silent.

Run:  python -m pytest tests/test_eod_exit_price_sign.py -v
      (or: python tests/test_eod_exit_price_sign.py)
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

from services.execution import _eod_exit_price
from services.audit import fix_negative_short_exit_prices
from core.state import compute_journal_stats


def test_short_exit_price_is_positive():
    # SPY SHORT, 100 shares, market_value negative (short liability) -- the
    # exact shape of the real production position at EOD close.
    price = _eod_exit_price(market_value=-74330.0, qty_signed=-100, avg_entry=748.4491)
    assert price == 743.3
    assert price > 0


def test_long_exit_price_unaffected():
    # LONG, 50 shares @ 105 -- must keep working exactly as before the fix.
    price = _eod_exit_price(market_value=5250.0, qty_signed=50, avg_entry=100.0)
    assert price == 105.0


def test_zero_qty_falls_back_to_avg_entry():
    price = _eod_exit_price(market_value=0.0, qty_signed=0, avg_entry=123.45)
    assert price == 123.45


def test_fix_negative_short_exit_prices_repairs_sign():
    trades = [{
        'source':       'DONNA_AUTO',
        'order_id':     '77ee938b-da7e-4176-b625-3d63bb1e3f35',
        'ticker':       'SPY',
        'direction':    'SHORT',
        'trade_date':   '2026-06-23',
        'entry_price':  733.23,
        'exit_price':   -734.53,
        'size':         100,
        'realized_pnl': -182.0,
        'pnl':          -182.0,
        'outcome':      'EOD_CLOSE',
    }]
    fixed = fix_negative_short_exit_prices(trades)

    assert len(fixed) == 1
    assert fixed[0]['order_id'] == '77ee938b-da7e-4176-b625-3d63bb1e3f35'
    assert trades[0]['exit_price'] == 734.53
    # realized_pnl is untouched -- it was never derived from exit_price
    assert trades[0]['realized_pnl'] == -182.0


def test_fix_is_noop_when_no_negative_prices_exist():
    trades = [{'ticker': 'QQQ', 'exit_price': 450.0, 'realized_pnl': 10.0}]
    fixed = fix_negative_short_exit_prices(trades)
    assert fixed == []
    assert trades[0]['exit_price'] == 450.0


def test_fix_is_idempotent():
    trades = [{'ticker': 'SPY', 'exit_price': -734.53, 'realized_pnl': -182.0}]
    fix_negative_short_exit_prices(trades)
    second_pass = fix_negative_short_exit_prices(trades)
    assert second_pass == []
    assert trades[0]['exit_price'] == 734.53


def test_validate_trade_matches_after_sign_fix():
    """
    engines/analytics.py's validate_trade() re-derives pnl from entry/exit
    and would flag a mismatch with the buggy negative exit_price. After the
    sign fix it must agree with the stored realized_pnl.
    """
    from engines.analytics import validate_trade

    trade = {
        'direction':    'SHORT',
        'entry_price':  733.23,
        'exit_price':   -735.05,   # buggy, pre-fix value (mutually consistent with pnl below)
        'size':         100,
        'realized_pnl': -182.0,
        'outcome':      'LOSS',
    }
    before = validate_trade(trade)
    assert before['valid'] is False, 'buggy negative exit_price must mismatch stored pnl'

    fix_negative_short_exit_prices([trade])
    after = validate_trade(trade)
    assert after['valid'] is True
    assert after['correct_pnl'] == -182.0


def test_stats_unaffected_by_exit_price_sign_because_realized_pnl_wins():
    """
    compute_journal_stats() prefers realized_pnl over entry/exit recompute,
    so the sign bug never reached weekly P&L / win-rate for trades that have
    realized_pnl set (every auto-EOD trade does). This locks in that the
    consumer-level audit conclusion holds even before exit_price is fixed.
    """
    trade_buggy = {
        'direction': 'SHORT', 'entry_price': 733.23, 'exit_price': -734.53,
        'size': 100, 'realized_pnl': -182.0, 'outcome': 'LOSS', 'trade_date': '2026-06-23',
    }
    trade_fixed = dict(trade_buggy, exit_price=734.53)

    stats_buggy = compute_journal_stats([trade_buggy])
    stats_fixed = compute_journal_stats([trade_fixed])

    assert stats_buggy['daily_pnl']['yesterday'] == stats_fixed['daily_pnl']['yesterday']
    assert stats_buggy['losses'] == stats_fixed['losses'] == 1


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
