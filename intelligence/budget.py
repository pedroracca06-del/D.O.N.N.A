"""intelligence/budget.py — daily request/cost ceiling with pre-call reservation (spec §8's #8-#9, §8.1, §8.2, §8.3).

Persists at DATA_DIR/nova_intelligence_budget.json, keyed by an
America/New_York calendar date. Fails closed on any unreadable, corrupt, or
lock-unavailable state — a missing file is the only condition treated as a
fresh day. Never imports a provider SDK; keyed by feature is left to the
caller (gateway.py) — this module tracks one shared daily total, per spec.
"""
from __future__ import annotations

import json
import os
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from core.config import DATA_DIR, NY_TZ

from . import config, model_registry

BUDGET_FILE: Path = DATA_DIR / 'nova_intelligence_budget.json'

_MAX_ATTEMPTS_PER_RESERVATION = 2
_LOCK_TIMEOUT_SECONDS = 5.0

_lock = threading.Lock()


class BudgetStateUnavailable(Exception):
    """The persisted state is corrupt, unreadable, has invalid fields, or the lock could not be acquired (spec §8.3 step 7)."""


class BudgetExceeded(Exception):
    """Reserving this request would exceed the daily request limit or cost ceiling (spec §8.3 step 3)."""


class ModelNotSupported(Exception):
    """NOVA_AI_MODEL has no entry in model_registry.py — cost cannot be verified (spec §8.2)."""


def _now_ny() -> datetime:
    """Injectable for tests — never rely on the machine's local timezone (spec: timezone-aware dates only)."""
    return datetime.now(NY_TZ)


def _today_key() -> str:
    return _now_ny().astimezone(NY_TZ).strftime('%Y-%m-%d')


@dataclass
class _DayState:
    date: str
    request_count: int = 0
    accrued_cost: float = 0.0
    reserved_count: int = 0
    reserved_cost: float = 0.0


@dataclass(frozen=True)
class Reservation:
    date: str
    attempts_reserved: int
    cost_reserved: float
    per_attempt_cost: float


@dataclass(frozen=True)
class AttemptOutcome:
    had_usage: bool
    input_tokens: int = 0
    output_tokens: int = 0


@contextmanager
def _locked():
    acquired = _lock.acquire(timeout=_LOCK_TIMEOUT_SECONDS)
    if not acquired:
        raise BudgetStateUnavailable('could not acquire the budget state lock')
    try:
        yield
    finally:
        _lock.release()


def _read_state(path: Path) -> _DayState:
    """Missing file -> valid first use (zero state). Anything else that fails to
    parse cleanly fails closed -- never silently treated as a fresh day."""
    if not path.exists():
        return _DayState(date=_today_key())

    try:
        raw = path.read_text(encoding='utf-8')
        data = json.loads(raw)
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise BudgetStateUnavailable('budget state file is unreadable or not valid JSON') from exc

    if not isinstance(data, dict):
        raise BudgetStateUnavailable('budget state file does not contain a JSON object')

    required_fields = ('date', 'request_count', 'accrued_cost', 'reserved_count', 'reserved_cost')
    if not all(f in data for f in required_fields):
        raise BudgetStateUnavailable('budget state file is missing required fields')

    try:
        state = _DayState(
            date=str(data['date']),
            request_count=int(data['request_count']),
            accrued_cost=float(data['accrued_cost']),
            reserved_count=int(data['reserved_count']),
            reserved_cost=float(data['reserved_cost']),
        )
    except (TypeError, ValueError) as exc:
        raise BudgetStateUnavailable('budget state file has invalid field types') from exc

    if state.request_count < 0 or state.accrued_cost < 0 or state.reserved_count < 0 or state.reserved_cost < 0:
        raise BudgetStateUnavailable('budget state file has invalid negative values')

    if state.date != _today_key():
        # A new calendar day (NY) with no matching key -- a legitimate reset,
        # not corruption. The stale prior-day record is simply superseded on
        # the next successful write.
        return _DayState(date=_today_key())

    return state


def _write_state(path: Path, state: _DayState) -> None:
    tmp = path.with_suffix('.tmp')
    payload = {
        'date': state.date,
        'request_count': state.request_count,
        'accrued_cost': state.accrued_cost,
        'reserved_count': state.reserved_count,
        'reserved_cost': state.reserved_cost,
    }
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(payload, f, indent=2)
    os.replace(tmp, path)


def _project_cost(estimated_input_tokens: int, max_output_tokens: int, pricing: model_registry.ModelPricing) -> float:
    return (
        (estimated_input_tokens / 1_000_000) * pricing.input_price_per_mtok
        + (max_output_tokens / 1_000_000) * pricing.output_price_per_mtok
    )


def reserve(*, estimated_input_tokens: int, max_output_tokens: int, model: str, path: Optional[Path] = None) -> Reservation:
    """Pre-call reservation (spec §8.3). Model support is checked before the
    lock is touched at all -- an unregistered model never reserves anything."""
    path = path or BUDGET_FILE

    pricing = model_registry.get_model_pricing(model)
    if pricing is None:
        raise ModelNotSupported(model)

    per_attempt_cost = _project_cost(estimated_input_tokens, max_output_tokens, pricing)
    projected_cost = per_attempt_cost * _MAX_ATTEMPTS_PER_RESERVATION

    with _locked():
        state = _read_state(path)

        if state.request_count + state.reserved_count + _MAX_ATTEMPTS_PER_RESERVATION > config.NOVA_AI_DAILY_REQUEST_LIMIT:
            raise BudgetExceeded('daily request limit would be exceeded')
        if state.accrued_cost + state.reserved_cost + projected_cost > config.NOVA_AI_DAILY_COST_LIMIT_USD:
            raise BudgetExceeded('daily cost ceiling would be exceeded')

        state.reserved_count += _MAX_ATTEMPTS_PER_RESERVATION
        state.reserved_cost += projected_cost
        _write_state(path, state)

    return Reservation(
        date=state.date,
        attempts_reserved=_MAX_ATTEMPTS_PER_RESERVATION,
        cost_reserved=projected_cost,
        per_attempt_cost=per_attempt_cost,
    )


def release_reservation(reservation: Reservation, path: Optional[Path] = None) -> None:
    """Releases a reservation with zero attempts made (e.g. prompt construction
    failed before the provider was ever called) -- no settlement, nothing billed."""
    path = path or BUDGET_FILE
    with _locked():
        state = _read_state(path)
        state.reserved_count = max(0, state.reserved_count - reservation.attempts_reserved)
        state.reserved_cost = max(0.0, state.reserved_cost - reservation.cost_reserved)
        _write_state(path, state)


def settle(reservation: Reservation, *, attempts: list[AttemptOutcome], model: str, path: Optional[Path] = None) -> float:
    """Settles the real outcome of however many attempts were actually made (1
    or 2), releasing the rest of the reservation. An attempt with no reported
    usage settles at its own worst-case projected cost, never zero (spec §8.3
    step 6). Returns the total real cost settled."""
    path = path or BUDGET_FILE
    pricing = model_registry.get_model_pricing(model)

    total_cost = 0.0
    for outcome in attempts:
        if outcome.had_usage and pricing is not None:
            total_cost += (
                (outcome.input_tokens / 1_000_000) * pricing.input_price_per_mtok
                + (outcome.output_tokens / 1_000_000) * pricing.output_price_per_mtok
            )
        else:
            total_cost += reservation.per_attempt_cost

    with _locked():
        state = _read_state(path)
        state.reserved_count = max(0, state.reserved_count - reservation.attempts_reserved)
        state.reserved_cost = max(0.0, state.reserved_cost - reservation.cost_reserved)
        state.request_count += len(attempts)
        state.accrued_cost += total_cost
        _write_state(path, state)

    return total_cost
