import json
from pathlib import Path

from intelligence.canonical_memory.hydration import Budget, Mission, hydrate

from tests.test_canonical_memory_hydration_schema import PIN, snapshot

FIXTURE = Path(__file__).parent / "fixtures" / "canonical_memory" / "golden_missions_v1.json"


def test_golden_missions_have_perfect_required_recall():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert len(data["missions"]) == 28
    snap = snapshot()
    for item in data["missions"]:
        mission = Mission(item["id"], item["statement"], tuple(item["scope_entities"]),
                          tuple(item["scope_classes"]), tuple(item["scope_domains"]),
                          "2026-09-15T00:00:00Z", PIN)
        packet = hydrate(snap, mission, item["agent_id"], Budget(item["budget"]))
        included = {row["record_key"] for row in packet.manifest["included"]}
        assert set(item["must_include"]) <= included
        assert not set(item["must_exclude"]) & included
