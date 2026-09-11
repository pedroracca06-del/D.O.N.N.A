from pathlib import Path

from tools.prime_indicator_audit import audit_market_map, phase1_gap_report


REPO = Path(__file__).resolve().parents[1]
MARKET_MAP = REPO / "indicators" / "nova_market_map_v1.pine"
EXECUTION = REPO / "indicators" / "nova_execution_v1.pine"


def test_market_map_foundation_invariants_are_clean():
    findings = audit_market_map(MARKET_MAP)
    failed = [item for item in findings if not item.passed]
    assert failed == []


def test_phase1_gap_is_explicit_not_silently_misclassified():
    gap = phase1_gap_report(MARKET_MAP)
    assert gap["visual_reference_through_1100"] is True
    assert gap["explicit_setup_validity_ends_1030"] is False
    assert gap["phase1_ready_for_implementation"] is True


def test_legacy_execution_indicator_is_not_a_clean_prime_foundation():
    findings = {item.check: item for item in audit_market_map(EXECUTION)}
    assert findings["no_signal_engine"].passed is False
    assert findings["visual_only"].passed is False
