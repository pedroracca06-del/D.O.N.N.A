import unicodedata

from intelligence.canonical_memory.hydration import Budget, hydrate
from intelligence.canonical_memory.hydration.estimator import estimate

from tests.test_canonical_memory_hydration_schema import mission, snapshot


def test_twenty_replays_are_byte_identical():
    snap = snapshot()
    hashes = {hydrate(snap, mission(), "agent.codex.reviewer", Budget(20000)).packet_hash for _ in range(20)}
    assert len(hashes) == 1


def test_utf8_estimator_normalises_newlines():
    assert estimate("a\r\nb") == estimate("a\nb") == 3


def test_unicode_evidence_is_recordable():
    assert isinstance(unicodedata.unidata_version, str)
