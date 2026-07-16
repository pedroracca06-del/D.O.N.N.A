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


@pytest.fixture(autouse=True)
def _default_empty_broker():
    """Empty broker state by default: no positions, no orders, no journal trades."""
    with patch('services.execution_reconcile.get_broker_positions_safe', return_value=[]), \
         patch('services.execution_reconcile.get_broker_orders_safe', return_value=[]), \
         patch('services.execution_reconcile.get_open_journal_trades_safe', return_value=[]):
        yield


@pytest.fixture(autouse=True)
def _trading_subsystem_enabled_for_existing_tests(monkeypatch):
    """Controlled retirement (2026-07-16): NOVA_TRADING_SUBSYSTEM_ENABLED now
    gates every broker-write function in services/execution.py, defaulting to
    False in production. Most tests in this suite pre-date that flag and call
    execute_signal()/close_position()/close_all_positions()/cancel_all_orders()/
    route_to_execution() directly, asserting on their real business-logic
    results (bracket protection, governance gates, cooldowns, etc.) -- so this
    autouse fixture keeps the flag enabled for the in-process test environment
    by default. Tests that specifically prove the disabled-by-default safety
    contract override it back within their own test body (see
    test_trading_subsystem_disablement.py) or run in a subprocess with a
    deliberately clean environment, which this fixture cannot reach.
    """
    monkeypatch.setenv('NOVA_TRADING_SUBSYSTEM_ENABLED', 'true')
    try:
        import services.execution as _ex
        monkeypatch.setattr(_ex, 'NOVA_TRADING_SUBSYSTEM_ENABLED', True)
    except Exception:
        pass
    yield
