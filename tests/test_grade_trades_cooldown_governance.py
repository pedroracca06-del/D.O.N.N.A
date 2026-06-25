"""
test_grade_trades_cooldown_governance.py — regression test for Min Grade /
Max Trades Per Day / Cooldown enforcement, added after discovering they
saved and displayed correctly but execute_signal() never actually compared
against them (the same class of gap as the original strategy/instrument
bypass).

Background on the grade decision specifically: real PROS/ORB alerts from
the TradingView indicator always carry score="0" (confirmed against
production trace data -- a Pine-side bug, analytics_score is read before
buySignal/sellSignal are reassigned at alert time). Implementing grade
enforcement against score=0 would silently block 100% of real trading.
Per explicit decision: build the gate, but treat "no real grade data" as
not-enforced rather than grade D -- see _derive_signal_grade()'s docstring.

Run:  python -m pytest tests/test_grade_trades_cooldown_governance.py -v
      (or: python tests/test_grade_trades_cooldown_governance.py)
"""
from __future__ import annotations

import os
import sys

os.environ['ALPACA_API_KEY']     = ''
os.environ['ALPACA_SECRET_KEY']  = ''
os.environ['TELEGRAM_BOT_TOKEN'] = ''
os.environ['TELEGRAM_CHAT_ID']   = ''

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import services.execution as ex


def _profile(min_grade='A', max_trades_per_day=3, trade_cooldown_minutes=20,
             allowed_strategies=('PROS', 'ORB'), allowed_instruments=('MNQ', 'MES')):
    return {
        'min_grade': min_grade,
        'max_trades_per_day': max_trades_per_day,
        'trade_cooldown_minutes': trade_cooldown_minutes,
        'allowed_strategies': list(allowed_strategies),
        'allowed_instruments': list(allowed_instruments),
    }


# ── _derive_signal_grade ──────────────────────────────────────────────────

def test_derive_grade_buckets_match_pre_verdict_engine_thresholds():
    assert ex._derive_signal_grade(85) == 'A'
    assert ex._derive_signal_grade(80) == 'A'
    assert ex._derive_signal_grade(75) == 'B'
    assert ex._derive_signal_grade(70) == 'B'
    assert ex._derive_signal_grade(65) == 'C'
    assert ex._derive_signal_grade(60) == 'C'
    assert ex._derive_signal_grade(40) == 'D'


def test_derive_grade_returns_none_for_zero_or_missing_score():
    """The real-world signature of 'no grade data available' -- must not be
    treated as grade D."""
    assert ex._derive_signal_grade(0) is None
    assert ex._derive_signal_grade('0') is None
    assert ex._derive_signal_grade(None) is None
    assert ex._derive_signal_grade('') is None
    assert ex._derive_signal_grade(-5) is None


# ── check_grade_allowed ────────────────────────────────────────────────────

def test_grade_unavailable_does_not_block_real_pros_signal(monkeypatch):
    """The actual production case: score=0, min_grade=A configured. Must be
    allowed -- enforcing here would halt 100% of real PROS/ORB trading."""
    monkeypatch.setattr(ex, '_active_execution_profile', lambda: _profile(min_grade='A'))
    gate = ex.check_grade_allowed(0)
    assert gate['allowed'] is True


def test_real_grade_below_minimum_is_rejected(monkeypatch):
    monkeypatch.setattr(ex, '_active_execution_profile', lambda: _profile(min_grade='A'))
    gate = ex.check_grade_allowed(65)  # grade C
    assert gate['allowed'] is False
    assert gate['code'] == 'GRADE_BELOW_MIN'


def test_real_grade_meeting_minimum_is_allowed(monkeypatch):
    monkeypatch.setattr(ex, '_active_execution_profile', lambda: _profile(min_grade='B'))
    gate = ex.check_grade_allowed(75)  # grade B
    assert gate['allowed'] is True


def test_real_grade_below_relaxed_minimum_is_allowed(monkeypatch):
    monkeypatch.setattr(ex, '_active_execution_profile', lambda: _profile(min_grade='C'))
    gate = ex.check_grade_allowed(65)  # grade C, profile only requires C
    assert gate['allowed'] is True


# ── check_daily_trade_limit ────────────────────────────────────────────────

def test_under_daily_limit_is_allowed(monkeypatch):
    monkeypatch.setattr(ex, '_active_execution_profile', lambda: _profile(max_trades_per_day=3))
    monkeypatch.setattr(ex._state, 'get', lambda key, default=None: 2 if key == 'daily_trade_count' else default)
    gate = ex.check_daily_trade_limit()
    assert gate['allowed'] is True


def test_at_daily_limit_is_rejected(monkeypatch):
    """The actual production case: max_trades_per_day=1, daily_trade_count
    already 2 -- must be rejected, not silently allowed."""
    monkeypatch.setattr(ex, '_active_execution_profile', lambda: _profile(max_trades_per_day=1))
    monkeypatch.setattr(ex._state, 'get', lambda key, default=None: 2 if key == 'daily_trade_count' else default)
    gate = ex.check_daily_trade_limit()
    assert gate['allowed'] is False
    assert gate['code'] == 'DAILY_TRADE_LIMIT_EXCEEDED'
    assert '2/1' in gate['reason']


# ── cooldown duration source ───────────────────────────────────────────────

def test_cooldown_minutes_reads_active_profile(monkeypatch):
    monkeypatch.setattr(ex, '_active_execution_profile', lambda: _profile(trade_cooldown_minutes=45))
    assert ex._cooldown_minutes_for_active_profile() == 45


def test_cooldown_minutes_defaults_to_30_when_profile_missing_it(monkeypatch):
    monkeypatch.setattr(ex, '_active_execution_profile', lambda: {})
    assert ex._cooldown_minutes_for_active_profile() == 30


# ── check_execution_governance (the combined orchestrator) ─────────────────

def test_combined_orchestrator_checks_strategy_before_grade_before_trades(monkeypatch):
    """Order matters for clear rejection reasons: strategy first, since an
    ICT signal should say STRATEGY_NOT_ALLOWED, not get confused with a
    grade or trade-count rejection it would also technically fail."""
    monkeypatch.setattr(ex, '_active_execution_profile',
                         lambda: _profile(min_grade='A', max_trades_per_day=0))
    gate = ex.check_execution_governance(
        {'strategy_family': 'ICT', 'score': 0}, {}, 'MNQ')
    assert gate['code'] == 'STRATEGY_NOT_ALLOWED'


def test_combined_orchestrator_allows_real_pros_signal_with_default_config(monkeypatch):
    """The exact real-world shape: PROS, MNQ, score=0, under the daily
    trade limit, min_grade=A configured -- must pass end to end."""
    monkeypatch.setattr(ex, '_active_execution_profile',
                         lambda: _profile(min_grade='A', max_trades_per_day=3))
    monkeypatch.setattr(ex._state, 'get', lambda key, default=None: 0 if key == 'daily_trade_count' else default)
    gate = ex.check_execution_governance(
        {'strategy_family': 'PROS', 'score': '0'}, {}, 'MNQ')
    assert gate['allowed'] is True


# ── execute_signal() end-to-end ─────────────────────────────────────────────

def test_execute_signal_rejects_over_daily_limit_before_alpaca(monkeypatch):
    def _explode():
        raise AssertionError('Alpaca client must never be constructed once the daily limit is hit')

    monkeypatch.setattr(ex, '_client', _explode)
    monkeypatch.setattr(ex, '_active_execution_profile', lambda: _profile(max_trades_per_day=1))
    monkeypatch.setattr(ex._state, 'can_execute', lambda: True)

    real_get = ex._state.get
    monkeypatch.setattr(ex._state, 'get',
                         lambda key, default=None: 2 if key == 'daily_trade_count' else real_get(key, default))

    signal_result = {
        'data': {
            'ticker': 'MNQ1!', 'instrument': 'MNQ', 'signal': 'LONG',
            'setup_type': 'PROS_CONTINUATION', 'strategy_family': 'PROS', 'score': '0',
            'signal_id': 'test-daily-limit-signal-1',
        },
        'parsed': {'verdict': 'TAKE', 'confidence': '85.0%'},
    }
    result = ex.execute_signal(signal_result)
    assert result['status'] == 'skipped'
    assert result['code'] == 'DAILY_TRADE_LIMIT_EXCEEDED'


def test_execute_signal_rejects_low_grade_before_alpaca(monkeypatch):
    def _explode():
        raise AssertionError('Alpaca client must never be constructed for a below-minimum grade')

    monkeypatch.setattr(ex, '_client', _explode)
    monkeypatch.setattr(ex, '_active_execution_profile', lambda: _profile(min_grade='A'))
    monkeypatch.setattr(ex._state, 'can_execute', lambda: True)

    signal_result = {
        'data': {
            'ticker': 'MNQ1!', 'instrument': 'MNQ', 'signal': 'LONG',
            'setup_type': 'PROS_CONTINUATION', 'strategy_family': 'PROS', 'score': '65',  # grade C
            'signal_id': 'test-low-grade-signal-1',
        },
        'parsed': {'verdict': 'TAKE', 'confidence': '85.0%'},
    }
    result = ex.execute_signal(signal_result)
    assert result['status'] == 'skipped'
    assert result['code'] == 'GRADE_BELOW_MIN'


def test_execute_signal_does_not_block_real_shaped_pros_signal_on_grade(monkeypatch):
    """Regression guard for the exact bug this was built to avoid: a
    real-shaped PROS signal (score=0) must NOT be rejected by the grade
    gate, even with a strict min_grade=A configured. It may still be
    rejected by something else (state gate, duplicate signal, etc.) but
    never GRADE_BELOW_MIN."""
    monkeypatch.setattr(ex, '_active_execution_profile',
                         lambda: _profile(min_grade='A', max_trades_per_day=99))
    monkeypatch.setattr(ex._state, 'can_execute', lambda: True)

    signal_result = {
        'data': {
            'ticker': 'MNQ1!', 'instrument': 'MNQ', 'signal': 'LONG',
            'setup_type': 'PROS_CONTINUATION', 'strategy_family': 'PROS', 'score': '0',
            'signal_id': 'test-real-shaped-signal-1',
        },
        'parsed': {'verdict': 'TAKE', 'confidence': '85.0%'},
    }
    result = ex.execute_signal(signal_result)
    assert result.get('code') != 'GRADE_BELOW_MIN'


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
