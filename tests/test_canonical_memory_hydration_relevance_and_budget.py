from intelligence.canonical_memory.hydration import Budget, hydrate
from intelligence.canonical_memory.hydration.constants import TIERS
from intelligence.canonical_memory.hydration.estimator import estimate

from tests.test_canonical_memory_hydration_schema import mission, snapshot


def test_projection_exclusions_are_accounted_once():
    packet = hydrate(snapshot(), mission(), "agent.codex.reviewer", Budget(20000))
    identities = {(i["record_key"], i["version"]) for i in packet.manifest["included"]}
    excluded = {(i["record_key"], i["version"]) for i in packet.manifest["excluded"]}
    assert identities.isdisjoint(excluded)
    assert len(identities | excluded) == packet.manifest["evaluated"]


def test_tight_budget_only_cuts_nonmandatory_after_core_fits():
    full = hydrate(snapshot(), mission(), "agent.codex.reviewer", Budget(20000))
    core_bytes = sum(i["bytes"] for i in full.manifest["included"] if i["tier"] == "mandatory_invariants")
    header_bytes = sum(estimate(f"## {tier}\n") for tier in TIERS)
    packet = hydrate(snapshot(), mission(), "agent.codex.reviewer", Budget(header_bytes + core_bytes + 64))
    assert not hasattr(packet, "code")
    assert any(i["code"] == "BUDGET" for i in packet.manifest["excluded"])


def test_rendered_bytes_never_exceed_available_budget():
    packet = hydrate(snapshot(), mission(), "agent.codex.reviewer", Budget(20000, 137))
    assert packet.manifest["rendered_bytes"] <= 20000 - 137
