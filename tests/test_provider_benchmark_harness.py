from tools.provider_benchmark_harness import (
    BenchmarkFixture,
    fixture_hash,
    score_response,
)


def fixture() -> BenchmarkFixture:
    return BenchmarkFixture(
        fixture_id="PB-001",
        version=1,
        feature="authority",
        context="Current PRIME overrides historical PROS research.",
        question="What are the active models?",
        required_substrings=("Strict OTE", "10AM Key Level Open", "ORB"),
        forbidden_substrings=("PROS is active", "FVG is an entry model"),
    )


def test_fixture_hash_is_stable_for_same_payload():
    a = fixture()
    b = fixture()
    assert fixture_hash(a) == fixture_hash(b)


def test_fixture_hash_changes_when_version_or_context_changes():
    a = fixture()
    changed = BenchmarkFixture(**{**a.__dict__, "version": 2})
    assert fixture_hash(a) != fixture_hash(changed)


def test_hard_gate_passes_only_when_all_required_present_and_forbidden_absent():
    result = score_response(
        fixture(),
        "Active models: Strict OTE, 10AM Key Level Open, ORB. PROS is historical.",
        provider="mock",
        model="mock-a",
        latency_ms=12,
    )
    assert result.hard_pass is True
    assert result.failures == ()
    assert result.latency_ms == 12
    assert result.request_count == 1
    assert result.retries == 0
    assert result.fallback_used is False


def test_missing_required_invariant_fails():
    result = score_response(fixture(), "Strict OTE and ORB only", provider="mock", model="mock-a")
    assert result.hard_pass is False
    assert any("10AM Key Level Open" in failure for failure in result.failures)


def test_forbidden_invariant_fails():
    text = "Strict OTE, 10AM Key Level Open, ORB. PROS is active."
    result = score_response(fixture(), text, provider="mock", model="mock-a")
    assert result.hard_pass is False
    assert any("PROS is active" in failure for failure in result.failures)


def test_fixture_validation_rejects_bad_identity_and_overlap():
    bad = BenchmarkFixture(
        fixture_id="bad", version=0, feature="authority", context="ctx", question="q",
    )
    import pytest
    with pytest.raises(ValueError):
        fixture_hash(bad)

    overlap = BenchmarkFixture(
        fixture_id="PB-009", version=1, feature="authority", context="ctx", question="q",
        required_substrings=("ORB",), forbidden_substrings=("orb",),
    )
    with pytest.raises(ValueError):
        fixture_hash(overlap)


def test_attempt_accounting_and_cost_are_preserved():
    result = score_response(
        fixture(),
        "Strict OTE, 10AM Key Level Open, ORB.",
        provider="mock", model="mock-a", latency_ms=21,
        request_count=2, retries=1, fallback_used=True, marginal_cost=0.004,
    )
    assert result.request_count == 2
    assert result.retries == 1
    assert result.fallback_used is True
    assert result.marginal_cost == 0.004


def test_invalid_attempt_accounting_is_rejected():
    import pytest
    with pytest.raises(ValueError):
        score_response(
            fixture(), "Strict OTE, 10AM Key Level Open, ORB.",
            provider="mock", model="mock-a", request_count=1, retries=1,
        )


def test_result_record_is_json_safe_and_complete():
    import json
    result = score_response(
        fixture(), "Strict OTE, 10AM Key Level Open, ORB.",
        provider="mock", model="mock-a", marginal_cost=0.001,
    )
    record = result.to_record()
    assert record["fixture_hash"] == fixture_hash(fixture())
    assert record["failures"] == []
    assert json.loads(json.dumps(record))["hard_pass"] is True


def test_hard_fail_is_ineligible_even_if_cheaper():
    from tools.provider_benchmark_harness import eligible_results
    passing = score_response(
        fixture(), "Strict OTE, 10AM Key Level Open, ORB.",
        provider="expensive", model="a", marginal_cost=0.10,
    )
    failing = score_response(
        fixture(), "ORB only. PROS is active.",
        provider="cheap", model="b", marginal_cost=0.00001,
    )
    assert eligible_results([failing, passing]) == [passing]


def test_frozen_v1_fixture_pack_loads_with_unique_ids():
    from pathlib import Path
    from tools.provider_benchmark_harness import load_fixtures
    path = Path(__file__).resolve().parents[1] / "benchmarks" / "provider_fixtures_v1.json"
    fixtures = load_fixtures(path)
    assert [f.fixture_id for f in fixtures] == [f"PB-{i:03d}" for i in range(1, 9)]
    assert all(f.version == 1 for f in fixtures)
    assert len({fixture_hash(f) for f in fixtures}) == 8


def test_loader_rejects_duplicate_identity(tmp_path):
    import json
    import pytest
    from tools.provider_benchmark_harness import load_fixtures
    payload = [fixture().canonical_payload(), fixture().canonical_payload()]
    path = tmp_path / "dupe.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate fixture identity"):
        load_fixtures(path)


def test_fixture_validation_rejects_non_discriminating_short_invariants():
    import pytest
    weak = BenchmarkFixture(
        fixture_id="PB-010", version=1, feature="risk", context="ctx", question="q",
        required_substrings=("no",),
    )
    with pytest.raises(ValueError, match="at least 3 characters"):
        fixture_hash(weak)


def test_frozen_pack_uses_discriminating_negative_phrases():
    from pathlib import Path
    from tools.provider_benchmark_harness import load_fixtures

    path = Path(__file__).resolve().parents[1] / "benchmarks" / "provider_fixtures_v1.json"
    fixtures = {fixture.fixture_id: fixture for fixture in load_fixtures(path)}
    assert "not established" in fixtures["PB-002"].required_substrings
    assert "no second trade" in fixtures["PB-006"].required_substrings
