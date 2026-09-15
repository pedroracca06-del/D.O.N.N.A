from intelligence.canonical_memory.hydration import Budget, hydrate
from intelligence.canonical_memory.hydration.schema import HydrationPacket, HydrationRefusal

from tests.test_canonical_memory_hydration_schema import mission, snapshot


def test_hydrate_returns_provenance_packet():
    packet = hydrate(snapshot(), mission(), "agent.codex.reviewer", Budget(20000))
    assert isinstance(packet, HydrationPacket)
    assert packet.manifest["evaluated"] == packet.manifest["included_count"] + packet.manifest["excluded_count"]
    assert all("nova-" in line for name, lines in packet.sections if name != "conflicts" for line in lines)


def test_commit_mismatch_refuses():
    result = hydrate(snapshot(), mission(bound_commit="0" * 40), "agent.codex.reviewer", Budget(20000))
    assert isinstance(result, HydrationRefusal)
    assert result.code == "COMMIT_MISMATCH"


def test_empty_structured_scope_refuses():
    result = hydrate(snapshot(), mission(scope_classes=(), scope_domains=()), "agent.codex.reviewer", Budget(20000))
    assert result.code == "SCOPE_EMPTY"


def test_unknown_agent_refuses():
    assert hydrate(snapshot(), mission(), "unknown.agent", Budget(20000)).code == "UNKNOWN_AGENT"
