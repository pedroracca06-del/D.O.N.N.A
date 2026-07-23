"""
test_intelligence_budget.py — NOVA Intelligence V1 commit #4: intelligence/budget.py.

Fully isolated from real runtime state: every test points BUDGET_FILE at a
temporary path and never touches data/nova_intelligence_budget.json. Clock
is injected via monkeypatching _now_ny() -- never relies on the machine's
local timezone.

Run:  python -m pytest tests/test_intelligence_budget.py -v
"""
from __future__ import annotations

import json
import os
import sys
import threading
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from intelligence import budget, config

NY_TZ = ZoneInfo('America/New_York')


@pytest.fixture
def budget_file(tmp_path, monkeypatch):
    path = tmp_path / 'nova_intelligence_budget.json'
    monkeypatch.setattr(budget, 'BUDGET_FILE', path)
    return path


@pytest.fixture(autouse=True)
def _fixed_clock(monkeypatch):
    fixed = datetime(2026, 7, 21, 12, 0, 0, tzinfo=NY_TZ)
    monkeypatch.setattr(budget, '_now_ny', lambda: fixed)
    yield


def _read_raw(path: Path) -> str:
    return path.read_text(encoding='utf-8')


# ── Missing file = valid first use ──────────────────────────────────────────
def test_missing_file_is_valid_first_use(budget_file):
    assert not budget_file.exists()
    reservation = budget.reserve(estimated_input_tokens=100, max_output_tokens=400, model='claude-haiku-4-5-20251001')
    assert reservation.attempts_reserved == 2
    assert budget_file.exists()
    state = json.loads(_read_raw(budget_file))
    assert state['reserved_count'] == 2
    assert state['request_count'] == 0


# ── Model support checked before any lock/state work ────────────────────────
def test_unsupported_model_raises_before_touching_file(budget_file):
    with pytest.raises(budget.ModelNotSupported):
        budget.reserve(estimated_input_tokens=100, max_output_tokens=400, model='not-a-real-model')
    assert not budget_file.exists()


# ── Reservation happens before any provider call (structural) ──────────────
def test_reserve_writes_state_synchronously_before_any_provider_interaction(budget_file):
    reservation = budget.reserve(estimated_input_tokens=100, max_output_tokens=400, model='claude-haiku-4-5-20251001')
    state = json.loads(_read_raw(budget_file))
    assert state['reserved_count'] == reservation.attempts_reserved
    assert state['reserved_cost'] == pytest.approx(reservation.cost_reserved)


# ── Settlement: success (real usage) ────────────────────────────────────────
def test_settle_success_uses_real_usage_and_releases_reservation(budget_file):
    reservation = budget.reserve(estimated_input_tokens=100, max_output_tokens=400, model='claude-haiku-4-5-20251001')
    real_cost = budget.settle(
        reservation,
        attempts=[budget.AttemptOutcome(had_usage=True, input_tokens=50, output_tokens=20)],
        model='claude-haiku-4-5-20251001',
    )
    expected = (50 / 1_000_000) * 1.00 + (20 / 1_000_000) * 5.00
    assert real_cost == pytest.approx(expected)

    state = json.loads(_read_raw(budget_file))
    assert state['reserved_count'] == 0
    assert state['reserved_cost'] == pytest.approx(0.0)
    assert state['request_count'] == 1
    assert state['accrued_cost'] == pytest.approx(expected)


# ── Settlement: failure with no reported usage settles at worst-case ───────
def test_settle_failure_without_usage_settles_at_worst_case_not_zero(budget_file):
    reservation = budget.reserve(estimated_input_tokens=100, max_output_tokens=400, model='claude-haiku-4-5-20251001')
    real_cost = budget.settle(
        reservation,
        attempts=[budget.AttemptOutcome(had_usage=False)],
        model='claude-haiku-4-5-20251001',
    )
    assert real_cost == pytest.approx(reservation.per_attempt_cost)
    assert real_cost > 0

    state = json.loads(_read_raw(budget_file))
    assert state['reserved_count'] == 0
    assert state['request_count'] == 1
    assert state['accrued_cost'] == pytest.approx(reservation.per_attempt_cost)


# ── Settlement: mixed (attempt 1 failed no-usage, attempt 2 succeeded) ─────
def test_settle_mixed_attempts_sums_per_attempt_correctly(budget_file):
    reservation = budget.reserve(estimated_input_tokens=100, max_output_tokens=400, model='claude-haiku-4-5-20251001')
    real_cost = budget.settle(
        reservation,
        attempts=[
            budget.AttemptOutcome(had_usage=False),
            budget.AttemptOutcome(had_usage=True, input_tokens=10, output_tokens=10),
        ],
        model='claude-haiku-4-5-20251001',
    )
    expected = reservation.per_attempt_cost + ((10 / 1_000_000) * 1.00 + (10 / 1_000_000) * 5.00)
    assert real_cost == pytest.approx(expected)
    state = json.loads(_read_raw(budget_file))
    assert state['request_count'] == 2


# ── release_reservation: zero attempts made, nothing accrued ───────────────
def test_release_reservation_touches_only_reserved_fields(budget_file):
    reservation = budget.reserve(estimated_input_tokens=100, max_output_tokens=400, model='claude-haiku-4-5-20251001')
    budget.release_reservation(reservation)
    state = json.loads(_read_raw(budget_file))
    assert state['reserved_count'] == 0
    assert state['reserved_cost'] == pytest.approx(0.0)
    assert state['request_count'] == 0
    assert state['accrued_cost'] == pytest.approx(0.0)


# ── Daily request limit: 20 attempts used, the next reservation fails ──────
def test_daily_request_limit_exhausted_raises_budget_exceeded(budget_file, monkeypatch):
    monkeypatch.setattr(config, 'NOVA_AI_DAILY_REQUEST_LIMIT', 20)
    for _ in range(10):
        r = budget.reserve(estimated_input_tokens=10, max_output_tokens=10, model='claude-haiku-4-5-20251001')
        budget.settle(r, attempts=[budget.AttemptOutcome(had_usage=True, input_tokens=1, output_tokens=1)] * 2, model='claude-haiku-4-5-20251001')

    state = json.loads(_read_raw(budget_file))
    assert state['request_count'] == 20

    with pytest.raises(budget.BudgetExceeded):
        budget.reserve(estimated_input_tokens=10, max_output_tokens=10, model='claude-haiku-4-5-20251001')


# ── Daily cost ceiling ───────────────────────────────────────────────────────
def test_daily_cost_ceiling_exceeded_raises_budget_exceeded(budget_file, monkeypatch):
    monkeypatch.setattr(config, 'NOVA_AI_DAILY_COST_LIMIT_USD', 0.0000001)
    with pytest.raises(budget.BudgetExceeded):
        budget.reserve(estimated_input_tokens=1000, max_output_tokens=400, model='claude-haiku-4-5-20251001')
    assert not budget_file.exists()


# ── Fail-closed: corrupt JSON is never silently reset ───────────────────────
def test_corrupt_json_fails_closed_and_is_never_overwritten(budget_file):
    budget_file.write_text('{not valid json', encoding='utf-8')
    original = _read_raw(budget_file)

    with pytest.raises(budget.BudgetStateUnavailable):
        budget.reserve(estimated_input_tokens=100, max_output_tokens=400, model='claude-haiku-4-5-20251001')

    assert _read_raw(budget_file) == original


def test_missing_required_fields_fails_closed(budget_file):
    budget_file.write_text(json.dumps({'date': '2026-07-21', 'request_count': 3}), encoding='utf-8')
    original = _read_raw(budget_file)

    with pytest.raises(budget.BudgetStateUnavailable):
        budget.reserve(estimated_input_tokens=100, max_output_tokens=400, model='claude-haiku-4-5-20251001')

    assert _read_raw(budget_file) == original


def test_invalid_field_types_fail_closed(budget_file):
    budget_file.write_text(json.dumps({
        'date': '2026-07-21', 'request_count': 'not-a-number',
        'accrued_cost': 0, 'reserved_count': 0, 'reserved_cost': 0,
    }), encoding='utf-8')
    original = _read_raw(budget_file)

    with pytest.raises(budget.BudgetStateUnavailable):
        budget.reserve(estimated_input_tokens=100, max_output_tokens=400, model='claude-haiku-4-5-20251001')

    assert _read_raw(budget_file) == original


# ── Settlement failure after a real attempt: corrective commit ─────────────
def test_settle_raises_on_corrupt_state_and_never_overwrites_it(budget_file):
    """Corruption arising between reserve() and settle() must fail closed
    without settle() ever writing over it -- proves the corrective commit's
    settlement-failure path has nothing to trust on disk to begin with."""
    reservation = budget.reserve(estimated_input_tokens=10, max_output_tokens=10, model='claude-haiku-4-5-20251001')
    budget_file.write_text('{not valid json at settlement time', encoding='utf-8')
    corrupted_content = _read_raw(budget_file)

    with pytest.raises(budget.BudgetStateUnavailable):
        budget.settle(
            reservation,
            attempts=[budget.AttemptOutcome(had_usage=True, input_tokens=5, output_tokens=5)],
            model='claude-haiku-4-5-20251001',
        )

    assert _read_raw(budget_file) == corrupted_content


def test_stuck_reservation_from_settle_failure_counts_against_daily_limits(budget_file, monkeypatch):
    """When settle() cannot acquire the lock, the reservation reserve() wrote
    is left exactly as-is -- valid, readable, still fully "reserved" -- and
    a fresh read (simulating a process restart) still observes it. It must
    keep consuming both the daily request-count and cost headroom until the
    next America/New_York rollover (spec §8.3 verified directly here)."""
    monkeypatch.setattr(config, 'NOVA_AI_DAILY_REQUEST_LIMIT', 2)
    reservation = budget.reserve(estimated_input_tokens=10, max_output_tokens=10, model='claude-haiku-4-5-20251001')

    monkeypatch.setattr(budget, '_LOCK_TIMEOUT_SECONDS', 0.05)
    acquired = budget._lock.acquire(timeout=1.0)
    assert acquired
    try:
        with pytest.raises(budget.BudgetStateUnavailable):
            budget.settle(
                reservation,
                attempts=[budget.AttemptOutcome(had_usage=True, input_tokens=5, output_tokens=5)],
                model='claude-haiku-4-5-20251001',
            )
    finally:
        budget._lock.release()

    # Untouched: still the original reservation, valid and readable.
    state = budget._read_state(budget_file)
    assert state.reserved_count == reservation.attempts_reserved
    assert state.reserved_cost == pytest.approx(reservation.cost_reserved)
    assert state.request_count == 0
    assert state.accrued_cost == pytest.approx(0.0)

    # A fresh, independent read (simulating a restart) sees the same stuck reservation.
    restarted_state = budget._read_state(budget_file)
    assert restarted_state.reserved_count == reservation.attempts_reserved

    # It continues to consume both daily limits: request_count(0) +
    # reserved_count(2) + 2 > NOVA_AI_DAILY_REQUEST_LIMIT(2) -- blocked.
    with pytest.raises(budget.BudgetExceeded):
        budget.reserve(estimated_input_tokens=10, max_output_tokens=10, model='claude-haiku-4-5-20251001')


# ── Fail-closed: lock cannot be acquired ────────────────────────────────────
def test_lock_failure_fails_closed(budget_file, monkeypatch):
    monkeypatch.setattr(budget, '_LOCK_TIMEOUT_SECONDS', 0.05)
    acquired = budget._lock.acquire(timeout=1.0)
    assert acquired
    try:
        with pytest.raises(budget.BudgetStateUnavailable):
            budget.reserve(estimated_input_tokens=100, max_output_tokens=400, model='claude-haiku-4-5-20251001')
    finally:
        budget._lock.release()


# ── Persistence survives a "restart" (fresh read on the same date) ────────
def test_persisted_state_survives_restart_on_same_date(budget_file):
    reservation = budget.reserve(estimated_input_tokens=100, max_output_tokens=400, model='claude-haiku-4-5-20251001')
    budget.settle(reservation, attempts=[budget.AttemptOutcome(had_usage=True, input_tokens=5, output_tokens=5)], model='claude-haiku-4-5-20251001')

    # Simulate a fresh process: read state directly, independent of any in-memory object.
    state = budget._read_state(budget_file)
    assert state.request_count == 1
    assert state.accrued_cost > 0


# ── America/New_York rollover is deterministic ──────────────────────────────
def test_rollover_at_midnight_america_new_york(budget_file, monkeypatch):
    late = datetime(2026, 7, 21, 23, 59, 0, tzinfo=NY_TZ)
    monkeypatch.setattr(budget, '_now_ny', lambda: late)
    r = budget.reserve(estimated_input_tokens=10, max_output_tokens=10, model='claude-haiku-4-5-20251001')
    budget.settle(r, attempts=[budget.AttemptOutcome(had_usage=True, input_tokens=1, output_tokens=1)], model='claude-haiku-4-5-20251001')
    before = json.loads(_read_raw(budget_file))
    assert before['date'] == '2026-07-21'
    assert before['request_count'] == 1

    early_next_day = datetime(2026, 7, 22, 0, 1, 0, tzinfo=NY_TZ)
    monkeypatch.setattr(budget, '_now_ny', lambda: early_next_day)
    state = budget._read_state(budget_file)
    assert state.date == '2026-07-22'
    assert state.request_count == 0  # fresh day, not the prior day's count

    # A UTC instant that is still "yesterday" in NY must not roll over early.
    # 2026-07-22 03:00 UTC == 2026-07-21 23:00 America/New_York (EDT, UTC-4).
    utc_instant = datetime(2026, 7, 22, 3, 0, 0, tzinfo=ZoneInfo('UTC'))
    monkeypatch.setattr(budget, '_now_ny', lambda: utc_instant)
    state2 = budget._read_state(budget_file)
    assert state2.date == '2026-07-21'
    assert state2.request_count == 1  # still today's (NY) accumulated state


# ── Concurrent-request atomicity ────────────────────────────────────────────
def test_concurrent_reservations_never_both_exceed_the_limit(budget_file, monkeypatch):
    # Only room for exactly one 2-attempt reservation.
    monkeypatch.setattr(config, 'NOVA_AI_DAILY_REQUEST_LIMIT', 2)

    results = {}
    barrier = threading.Barrier(2)

    def _attempt(name):
        barrier.wait(timeout=5)
        try:
            budget.reserve(estimated_input_tokens=10, max_output_tokens=10, model='claude-haiku-4-5-20251001')
            results[name] = 'ok'
        except budget.BudgetExceeded:
            results[name] = 'exceeded'

    t1 = threading.Thread(target=_attempt, args=('a',))
    t2 = threading.Thread(target=_attempt, args=('b',))
    t1.start()
    t2.start()
    t1.join(timeout=5)
    t2.join(timeout=5)

    outcomes = sorted(results.values())
    assert outcomes == ['exceeded', 'ok']
