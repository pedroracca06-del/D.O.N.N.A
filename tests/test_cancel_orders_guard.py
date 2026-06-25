"""
test_cancel_orders_guard.py — regression test for the bracket-protection
guard in cancel_all_orders(), added during Execution Management Phase 1B.

Background: the original cancel_all_orders() cancelled every open order
account-wide, including the stop-loss/take-profit legs protecting a
currently open position. A "Cancel Open Orders" button wired to that
directly could silently strip protection from a live position. The guard
skips any order that is a bracket leg on a symbol with a currently open
position, and reports what it skipped and why -- it never cancels
protective legs silently.

Run:  python -m pytest tests/test_cancel_orders_guard.py -v
      (or: python tests/test_cancel_orders_guard.py)
"""
from __future__ import annotations

import os
import sys

# Alpaca must stay unconfigured for plain imports of services.execution:
# it runs a one-time live "QQQ cleanup on load" call at module scope.
os.environ['ALPACA_API_KEY']    = ''
os.environ['ALPACA_SECRET_KEY'] = ''

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import services.execution as ex


class _FakeOrder:
    def __init__(self, id_, symbol, order_class):
        self.id          = id_
        self.symbol       = symbol
        self.order_class  = order_class  # e.g. 'OrderClass.BRACKET' or 'OrderClass.SIMPLE'


class _FakeApi:
    def __init__(self, orders):
        self._orders    = orders
        self.cancelled  = []

    def get_orders(self, *a, **kw):
        return self._orders

    def cancel_order_by_id(self, order_id):
        self.cancelled.append(order_id)


def test_protective_bracket_leg_on_open_position_is_skipped(monkeypatch):
    monkeypatch.setattr(ex, '_client', lambda: _FakeApi([
        _FakeOrder('leg-stop', 'SPY', 'OrderClass.BRACKET'),
        _FakeOrder('leg-target', 'SPY', 'OrderClass.BRACKET'),
    ]))
    monkeypatch.setattr(ex, 'get_positions', lambda: [
        {'symbol': 'SPY', 'qty': 101, 'side': 'long', 'avg_entry': 736.0,
         'market_value': 74000.0, 'unrealized_pnl': 10.0},
    ])

    result = ex.cancel_all_orders()

    assert result['status'] == 'ok'
    assert result['cancelled'] == 0
    assert len(result['protected_skipped']) == 2
    assert all(s['symbol'] == 'SPY' for s in result['protected_skipped'])


def test_orphaned_order_with_no_open_position_is_cancelled(monkeypatch):
    api = _FakeApi([_FakeOrder('orphan-1', 'QQQ', 'OrderClass.SIMPLE')])
    monkeypatch.setattr(ex, '_client', lambda: api)
    monkeypatch.setattr(ex, 'get_positions', lambda: [])  # no open positions at all

    result = ex.cancel_all_orders()

    assert result['status'] == 'ok'
    assert result['cancelled'] == 1
    assert result['protected_skipped'] == []
    assert api.cancelled == ['orphan-1']


def test_bracket_leg_on_a_symbol_with_no_open_position_is_cancelled(monkeypatch):
    """A leftover bracket leg with no live position behind it is safe to
    cancel -- it isn't protecting anything."""
    api = _FakeApi([_FakeOrder('stale-leg', 'TLT', 'OrderClass.BRACKET')])
    monkeypatch.setattr(ex, '_client', lambda: api)
    monkeypatch.setattr(ex, 'get_positions', lambda: [
        {'symbol': 'SPY', 'qty': 101, 'side': 'long', 'avg_entry': 736.0,
         'market_value': 74000.0, 'unrealized_pnl': 10.0},
    ])

    result = ex.cancel_all_orders()

    assert result['cancelled'] == 1
    assert result['protected_skipped'] == []
    assert api.cancelled == ['stale-leg']


def test_mixed_protected_and_unprotected_orders(monkeypatch):
    monkeypatch.setattr(ex, '_client', lambda: _FakeApi([
        _FakeOrder('spy-stop',   'SPY', 'OrderClass.BRACKET'),
        _FakeOrder('qqq-orphan', 'QQQ', 'OrderClass.SIMPLE'),
    ]))
    monkeypatch.setattr(ex, 'get_positions', lambda: [
        {'symbol': 'SPY', 'qty': 101, 'side': 'long', 'avg_entry': 736.0,
         'market_value': 74000.0, 'unrealized_pnl': 10.0},
    ])

    result = ex.cancel_all_orders()

    assert result['cancelled'] == 1
    assert len(result['protected_skipped']) == 1
    assert result['protected_skipped'][0]['symbol'] == 'SPY'


if __name__ == '__main__':
    import inspect

    class _MiniMonkeypatch:
        def __init__(self):
            self._undo = []
        def setattr(self, obj, name, value):
            self._undo.append((obj, name, getattr(obj, name)))
            setattr(obj, name, value)
        def undo(self):
            for obj, name, value in reversed(self._undo):
                setattr(obj, name, value)

    tests = [v for k, v in list(globals().items()) if k.startswith('test_')]
    failed = 0
    for t in tests:
        mp = _MiniMonkeypatch() if 'monkeypatch' in inspect.signature(t).parameters else None
        try:
            t(mp) if mp else t()
            print(f'PASS  {t.__name__}')
        except AssertionError as e:
            failed += 1
            print(f'FAIL  {t.__name__}: {e}')
        finally:
            if mp:
                mp.undo()
    print(f'\n{len(tests) - failed}/{len(tests)} passed')
    sys.exit(1 if failed else 0)
