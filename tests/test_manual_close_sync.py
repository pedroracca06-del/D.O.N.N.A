"""
test_manual_close_sync.py — regression test for Phase 1A of Execution
Management: manual Close Position / Close All Positions must keep broker,
journal, and analytics state in sync, the same way close_all_positions_eod()
already does for the EOD sweep.

Background: close_position()/close_all_positions() used to call Alpaca and
return -- the journal was never touched, leaving manually-closed trades stuck
OPEN forever (the same bug class fixed for the EOD path and the
DONNA_AUTO_RECONSTRUCTED journal split earlier this session).

_close_symbol_and_sync() is now the single shared path for both buttons:
  - cancels pending bracket legs, then closes the position
  - on a broker error, the journal is NOT touched (no closed-but-still-open lie)
  - on success, exit_price comes from the sign-correct _eod_exit_price() helper
    and realized_pnl comes straight from Alpaca's unrealized_pnl (never derived)
  - tags close_reason='MANUAL', closed_via='NOVA_EXECUTION_TAB' so a future
    audit can tell this apart from EOD / autonomous target / autonomous stop

Run:  python -m pytest tests/test_manual_close_sync.py -v
      (or: python tests/test_manual_close_sync.py)
"""
from __future__ import annotations

import os
import sys

# Alpaca must stay unconfigured for plain imports of services.execution:
# it runs a one-time live "QQQ cleanup on load" call at module scope.
# Blanking the keys makes that call no-op safely.
os.environ['ALPACA_API_KEY']    = ''
os.environ['ALPACA_SECRET_KEY'] = ''

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import services.execution as ex
from core.state import compute_journal_stats


class _FakeApi:
    """Minimal stand-in for alpaca-py's TradingClient, no network calls."""
    def __init__(self, fail_close: bool = False):
        self.fail_close   = fail_close
        self.closed       = []
        self.cancelled    = []

    def get_orders(self, *a, **kw):
        return []  # no pending bracket legs in these tests

    def cancel_order_by_id(self, order_id):
        self.cancelled.append(order_id)

    def close_position(self, symbol):
        if self.fail_close:
            raise RuntimeError('insufficient qty available for order')
        self.closed.append(symbol)


def _short_snapshot():
    # Mirrors the real production shape: SPY short, profitable close.
    return {
        'symbol': 'SPY', 'qty': -100, 'side': 'short',
        'avg_entry': 748.4491, 'market_value': -74330.0, 'unrealized_pnl': 514.91,
    }


def _open_journal_entry():
    return {
        'source':       'DONNA_AUTO_RECONSTRUCTED',
        'order_id':     '81f6fccc-4dfd-48c5-9058-b7124af5b68d',
        'ticker':       'SPY',
        'direction':    'SHORT',
        'trade_date':   '2026-06-24',
        'entry_price':  748.47,
        'exit_price':   None,
        'size':         100,
        'realized_pnl': None,
        'pnl':          None,
        'outcome':      'OPEN',
        'notes':        'DONNA autonomous trade.',
    }


def test_successful_close_updates_matching_open_entry():
    trades = [_open_journal_entry()]
    ex.save_journal(trades)
    api = _FakeApi()

    result = ex._close_symbol_and_sync(
        api, 'SPY', _short_snapshot(),
        close_reason=ex.CLOSE_REASON_MANUAL, closed_via='NOVA_EXECUTION_TAB',
    )

    assert result['status'] == 'ok'
    assert result['outcome'] == 'WIN'
    assert result['realized_pnl'] == 514.91
    assert api.closed == ['SPY'], 'broker close must actually be called'

    journal = ex.load_journal()
    assert len(journal) == 1, 'must update in place, not append a duplicate'
    entry = journal[0]
    assert entry['outcome'] == 'WIN'
    assert entry['realized_pnl'] == 514.91
    assert entry['exit_price'] > 0, 'must use the sign-correct helper, not a raw negative value'
    assert entry['close_reason'] == 'MANUAL'
    assert entry['closed_via']   == 'NOVA_EXECUTION_TAB'


def test_failed_broker_close_leaves_journal_untouched():
    original = [_open_journal_entry()]
    ex.save_journal(original)
    api = _FakeApi(fail_close=True)

    result = ex._close_symbol_and_sync(
        api, 'SPY', _short_snapshot(),
        close_reason=ex.CLOSE_REASON_MANUAL, closed_via='NOVA_EXECUTION_TAB',
    )

    assert result['status'] == 'error'
    assert api.closed == [], 'close_position must have been attempted, then failed'

    journal = ex.load_journal()
    assert journal == original, 'a failed broker call must never mutate the journal'
    assert journal[0]['outcome'] == 'OPEN'


def test_no_matching_open_entry_creates_tagged_fallback_row():
    ex.save_journal([])  # nothing open in the journal at all
    api = _FakeApi()

    result = ex._close_symbol_and_sync(
        api, 'SPY', _short_snapshot(),
        close_reason=ex.CLOSE_REASON_MANUAL, closed_via='NOVA_EXECUTION_TAB',
    )

    assert result['status'] == 'ok'
    journal = ex.load_journal()
    assert len(journal) == 1
    assert journal[0]['source'] == 'DONNA_EOD', 'reuses existing fallback taxonomy the audit already understands'
    assert journal[0]['close_reason'] == 'MANUAL'
    assert journal[0]['outcome'] == 'WIN'


def test_has_open_journal_match_true_for_matching_open_entry():
    ex.save_journal([_open_journal_entry()])
    assert ex.has_open_journal_match('SPY') is True


def test_has_open_journal_match_false_when_no_match():
    ex.save_journal([])
    assert ex.has_open_journal_match('SPY') is False
    ex.save_journal([{**_open_journal_entry(), 'outcome': 'WIN'}])  # closed, not OPEN
    assert ex.has_open_journal_match('SPY') is False


def test_close_all_positions_syncs_each_symbol_independently(monkeypatch):
    spy_entry = _open_journal_entry()
    qqq_entry = {**_open_journal_entry(), 'ticker': 'QQQ', 'order_id': 'qqq-order-1'}
    ex.save_journal([spy_entry, qqq_entry])

    api = _FakeApi()
    monkeypatch.setattr(ex, '_client', lambda: api)
    monkeypatch.setattr(ex, 'get_positions', lambda: [
        _short_snapshot(),
        {'symbol': 'QQQ', 'qty': 50, 'side': 'long', 'avg_entry': 450.0,
         'market_value': 22750.0, 'unrealized_pnl': 250.0},
    ])

    result = ex.close_all_positions()

    assert result['status'] == 'ok'
    assert result['closed'] == 2
    assert sorted(api.closed) == ['QQQ', 'SPY']

    journal = ex.load_journal()
    assert len(journal) == 2
    by_ticker = {t['ticker']: t for t in journal}
    assert by_ticker['SPY']['outcome'] == 'WIN'
    assert by_ticker['QQQ']['outcome'] == 'WIN'
    assert by_ticker['QQQ']['realized_pnl'] == 250.0
    assert all(t['close_reason'] == 'MANUAL' for t in journal)


def test_close_position_errors_when_symbol_not_open(monkeypatch):
    api = _FakeApi()
    monkeypatch.setattr(ex, '_client', lambda: api)
    monkeypatch.setattr(ex, 'get_positions', lambda: [])

    result = ex.close_position('SPY')
    assert result['status'] == 'error'
    assert 'No open position' in result['error']


def test_stats_reflect_manual_close_correctly():
    """compute_journal_stats() needs no special-casing -- once the journal
    entry is correct, analytics is correct automatically (no cache to sync)."""
    trades = [_open_journal_entry()]
    ex.save_journal(trades)
    api = _FakeApi()
    ex._close_symbol_and_sync(
        api, 'SPY', _short_snapshot(),
        close_reason=ex.CLOSE_REASON_MANUAL, closed_via='NOVA_EXECUTION_TAB',
    )

    stats = compute_journal_stats(ex.load_journal())
    assert stats['wins'] == 1
    assert stats['losses'] == 0


if __name__ == '__main__':
    import inspect

    # The monkeypatch-using tests need pytest's fixture; fall back to a tiny
    # manual stand-in when run as a plain script.
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
