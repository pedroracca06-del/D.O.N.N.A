from intelligence.canonical_memory.hydration import Budget, hydrate

from tests.test_canonical_memory_hydration_schema import mission, snapshot


def test_every_inclusion_has_stable_git_reference_and_no_machine_path():
    packet = hydrate(snapshot(), mission(), "agent.codex.reviewer", Budget(20000))
    lines = [line for name, rows in packet.sections if name != "conflicts" for line in rows]
    assert lines
    assert all("nova-" in line for line in lines)
    assert all("C:\\" not in line and "/Users/" not in line for line in lines)
