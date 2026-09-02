"""conftest.py — shared pytest fixtures for all execution bot v2 tests.

Phase 1/2 tests were written without broker mocks (assuming no live positions).
This autouse fixture provides empty broker state by default so tests stay
deterministic regardless of what Alpaca holds at test time.

Tests that need specific broker state (Phase 3/4/5 etc.) already patch these
functions explicitly via patch() inside the test body — those patches take
precedence over the fixture.
"""
from __future__ import annotations

import datetime as _datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest

import core.state_engine
import services.execution


@pytest.fixture(autouse=True)
def _default_empty_broker():
    """Empty broker state by default: no positions, no orders, no journal trades."""
    with patch('services.execution_reconcile.get_broker_positions_safe', return_value=[]), \
         patch('services.execution_reconcile.get_broker_orders_safe', return_value=[]), \
         patch('services.execution_reconcile.get_open_journal_trades_safe', return_value=[]):
        yield


@pytest.fixture
def legacy_trading_enabled(monkeypatch):
    """Controlled retirement (2026-07-16): NOVA_TRADING_SUBSYSTEM_ENABLED now
    gates every broker-write function in services/execution.py and Gate 0 of
    services/execution_bridge.py's route_to_execution(), defaulting to False
    in production and, since 2026-07-16, in the test suite too -- the same
    safe default as the real application.

    This fixture is NOT autouse. It exists only for the small set of legacy
    execution tests that were written before the retirement flag existed and
    intentionally need to exercise the archived business logic (bracket
    protection, governance gates, cooldowns, Phase 1 request validation).
    Every other test -- Journal, Market/News, NOVA Assistant, main
    application/startup, and the retirement safety tests themselves -- runs
    with trading disabled unless it explicitly requests this fixture (directly,
    or via `pytestmark = pytest.mark.usefixtures('legacy_trading_enabled')` at
    the top of a legacy execution test file). No test accidentally inherits
    trading-enabled state.
    """
    monkeypatch.setenv('NOVA_TRADING_SUBSYSTEM_ENABLED', 'true')
    monkeypatch.setattr(services.execution, 'NOVA_TRADING_SUBSYSTEM_ENABLED', True)
    yield


# A Wednesday at 10:30 ET: a normal weekday, comfortably inside the 09:30-16:00
# NY cash window, and in the same ISO week as the June-2026 journal fixtures.
NY_SESSION_INSTANT = _datetime.datetime(
    2026, 6, 24, 10, 30, tzinfo=ZoneInfo('America/New_York'))


@pytest.fixture
def ny_session_clock(monkeypatch):
    """Freeze the clock the NY session gate reads, at a fixed in-session instant.

    `execute_signal()` opens with Rule 0: `_state.block_reason()`, which calls
    `core.state_engine._now_ny()` and returns a reason string outside
    09:30-16:00 ET. Tests that target a governance branch *further down*
    (strategy allow-list, daily limit, grade minimum) never reach it when the
    suite happens to run outside market hours.

    Older tests tried to sidestep this with
    `monkeypatch.setattr(ex._state, 'can_execute', lambda: True)`. That patch is
    inert: production calls `block_reason()`, and `can_execute()` is *defined as*
    `block_reason() is None`, so patching the derived method cannot affect the
    one production uses. Those tests only passed when the wall clock happened to
    be inside the session window.

    This fixture controls the clock instead of the gate. The gate still runs and
    still enforces every rule -- it simply sees a known instant. It is NOT
    autouse: only tests that request it are affected, so session-boundary tests
    continue to exercise the real behaviour.
    """
    monkeypatch.setattr(core.state_engine, '_now_ny', lambda: NY_SESSION_INSTANT)
    return NY_SESSION_INSTANT


@pytest.fixture
def frozen_today(monkeypatch):
    """Return a callable that pins `date.today()` to an explicit ISO date.

    `core.state.compute_journal_stats()` derives today/yesterday/this-week from
    `date.today()` via a function-local `from datetime import date`, so the seam
    is the attribute on the `datetime` module itself, read at call time.

    Journal fixtures carry fixed calendar dates (June 2026). Without pinning the
    date, "this week" drifts away from those fixtures as real time passes and
    the weekly totals silently fall to zero -- which is exactly what happened.
    monkeypatch restores the attribute after each test, so nothing persists.
    """
    def _freeze(iso_date: str):
        anchor = _datetime.date.fromisoformat(iso_date)
        real_date = _datetime.date

        class _FrozenDate(real_date):
            @classmethod
            def today(cls):
                return anchor

        monkeypatch.setattr(_datetime, 'date', _FrozenDate)
        return anchor

    return _freeze
