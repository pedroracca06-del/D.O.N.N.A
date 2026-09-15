from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from intelligence.canonical_memory.ingest import ingest_repository
from intelligence.canonical_memory.hydration.schema import Budget, HydrationError, MemorySnapshot, Mission

ROOT = Path(__file__).resolve().parents[1]
PIN = "00024ccf1d6ef7f373cb400b52b9d85921ead33a"


def snapshot():
    return MemorySnapshot.from_ingest_result(ingest_repository(ROOT, PIN))


def mission(**changes):
    data = dict(mission_id="test.mission", statement="Review PRIME governance", scope_entities=(),
                scope_classes=("governance",), scope_domains=("knowledge",),
                as_of="2026-09-15T00:00:00Z", bound_commit=PIN)
    data.update(changes)
    return Mission(**data)


def test_snapshot_from_ingest_is_immutable_and_bound():
    value = snapshot()
    assert value.commit_oid == PIN
    with pytest.raises(FrozenInstanceError):
        value.commit_oid = "0" * 40


@pytest.mark.parametrize("limit,reserve", [(0, 0), (10, -1), (10, 10)])
def test_budget_fails_closed(limit, reserve):
    with pytest.raises(HydrationError) as exc:
        Budget(limit, reserve)
    assert exc.value.code == "BUDGET_INVALID"


def test_mission_requires_utc_as_of_and_full_pin():
    with pytest.raises(HydrationError) as exc:
        mission(as_of="2026-09-15")
    assert exc.value.code == "AS_OF_REQUIRED"
