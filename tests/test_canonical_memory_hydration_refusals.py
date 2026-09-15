import json
from dataclasses import replace
from pathlib import Path

import pytest

from intelligence.canonical_memory.hydration import Budget, Relationship, hydrate
from intelligence.canonical_memory.hydration.constants import TIERS
from intelligence.canonical_memory.hydration.estimator import estimate
from intelligence.canonical_memory.hydration.schema import HydrationError

from tests.test_canonical_memory_hydration_schema import mission, snapshot


def test_mandatory_core_budget_refusal():
    assert hydrate(snapshot(), mission(), "agent.codex.reviewer", Budget(64)).code == "MANDATORY_CORE_EXCEEDS_BUDGET"


def test_unknown_estimator_rejected_at_construction():
    with pytest.raises(HydrationError) as exc:
        Budget(1000, estimator_id="tokens")
    assert exc.value.code == "ESTIMATOR_UNKNOWN"


def test_versioned_refusal_fixture_codes_are_reachable():
    snap = snapshot()
    full = hydrate(snap, mission(), "agent.codex.reviewer", Budget(20000))
    header = sum(estimate(f"## {tier}\n") for tier in TIERS)
    core = sum(i["bytes"] for i in full.manifest["included"] if i["tier"] == "mandatory_invariants")
    notice_snap = replace(snap, relationships=(Relationship("conflict", ("prime.framework.definition",)),))
    without_core = replace(snap,
        records=tuple(r for r in snap.records if r.record_key != "prime.models.exactly_three"),
        links=tuple(l for l in snap.links if l.record_key != "prime.models.exactly_three"))
    observed = {
        "r.budget": hydrate(snap, mission(), "agent.codex.reviewer", Budget(64)).code,
        "r.notices": hydrate(notice_snap, mission(), "agent.codex.reviewer", Budget(header + core)).code,
        "r.core": hydrate(without_core, mission(), "agent.codex.reviewer", Budget(20000)).code,
        "r.commit": hydrate(snap, mission(bound_commit="f" * 40), "agent.codex.reviewer", Budget(20000)).code,
        "r.agent": hydrate(snap, mission(), "unknown.agent", Budget(20000)).code,
        "r.authority": hydrate(replace(snap, authority_package_valid=False), mission(), "agent.codex.reviewer", Budget(20000)).code,
        "r.empty": hydrate(snap, mission(scope_classes=(), scope_domains=()), "agent.codex.reviewer", Budget(20000)).code,
    }
    with pytest.raises(HydrationError) as exc:
        mission(as_of="")
    observed["r.as_of"] = exc.value.code
    fixture = json.loads((Path(__file__).parent / "fixtures" / "canonical_memory" / "golden_missions_v1.json").read_text(encoding="utf-8"))
    assert observed == {item["id"]: item["expected"] for item in fixture["refusals"]}


def test_snapshot_mismatch_and_high_water_fail_closed():
    snap = snapshot()
    with pytest.raises(HydrationError) as exc:
        replace(snap, commit_oid="f" * 40)
    assert exc.value.code == "SNAPSHOT_COMMIT_MISMATCH"
    with pytest.raises(HydrationError) as exc:
        mission(event_high_water="1")
    assert exc.value.code == "HIGH_WATER_REQUIRED"
