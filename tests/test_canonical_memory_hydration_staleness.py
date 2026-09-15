from intelligence.canonical_memory.hydration import Budget, hydrate, is_packet_fresh

from tests.test_canonical_memory_hydration_schema import mission, snapshot


def test_packet_freshness_is_commit_exact():
    packet = hydrate(snapshot(), mission(), "agent.codex.reviewer", Budget(20000))
    assert is_packet_fresh(packet, packet.manifest["inputs"]["bound_commit"])
    assert not is_packet_fresh(packet, "0" * 40)


def test_moved_expected_commit_refuses():
    assert hydrate(snapshot(), mission(bound_commit="f" * 40), "agent.codex.reviewer", Budget(20000)).code == "COMMIT_MISMATCH"
