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
