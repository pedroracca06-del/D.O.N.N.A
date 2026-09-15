from dataclasses import replace

from intelligence.canonical_memory.hydration import Budget, Relationship, hydrate

from tests.test_canonical_memory_hydration_schema import mission, snapshot


def test_synthetic_conflict_is_reported_and_excluded():
    snap = snapshot()
    key = "prime.framework.definition"
    snap = replace(snap, relationships=(Relationship("conflict", (key,)),))
    packet = hydrate(snap, mission(), "agent.codex.reviewer", Budget(20000))
    assert any(item["code"] == "UNRESOLVED_CONFLICT" for item in packet.manifest["excluded"])
    assert packet.manifest["notices"] == ({"record_keys": (key,), "type": "conflict"},)
