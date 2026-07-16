"""conftest.py — shared pytest fixtures for all execution bot v2 tests.

Phase 1/2 tests were written without broker mocks (assuming no live positions).
This autouse fixture provides empty broker state by default so tests stay
deterministic regardless of what Alpaca holds at test time.

Tests that need specific broker state (Phase 3/4/5 etc.) already patch these
functions explicitly via patch() inside the test body — those patches take
precedence over the fixture.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

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
