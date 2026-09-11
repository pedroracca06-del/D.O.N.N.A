from pathlib import Path

import pytest

from intelligence.current_knowledge import (
    CurrentKnowledgeIntegrityError,
    retrieve_current_prime,
    validate_current_prime_package,
)


def _write(root: Path, name: str, body: str) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / name).write_text(body, encoding="utf-8")


def _valid_package(root: Path) -> None:
    common = "Status: CURRENT\nAuthority: owner-approved\n"
    models = (
        "Exactly three active execution models:\n"
        "1. Strict OTE\n2. 10AM Key Level Open\n3. ORB\n"
        "PROS is dead and superseded.\n"
        "FVG is context only and is not an entry model.\n"
    )
    _write(root, "README.md", common + models)
    _write(root, "EXECUTION_MODELS.md", common + models)
    _write(root, "PRIME_FRAMEWORK.md", common + "PRIME = Position -> Relevant Level -> Interaction -> Market Confirmation -> Execution.\n")
    _write(root, "STRICT_OTE.md", common + "Strict OTE is one of the three current PRIME execution models.\n")
    _write(root, "10AM_KEY_LEVEL_OPEN.md", common + "Canonical model name: 10AM Key Level Open.\n")
    _write(root, "ORB.md", common + "ORB is one of the three current PRIME execution models.\n")
    _write(
        root,
        "RISK_AND_SESSION_RULES.md",
        common
        + "One real trade per day. $500 maximum risk.\n"
        + "Before 09:45 ET, ORB is the only approved execution model.\n",
    )


def test_live_current_prime_package_passes_integrity_gate():
    names = validate_current_prime_package()
    assert "README.md" in names
    assert "EXECUTION_MODELS.md" in names
    assert "RISK_AND_SESSION_RULES.md" in names


def test_conflicting_model_list_fails_closed(tmp_path: Path):
    _valid_package(tmp_path)
    bad = (tmp_path / "EXECUTION_MODELS.md").read_text(encoding="utf-8").replace(
        "3. ORB", "3. FVG"
    )
    (tmp_path / "EXECUTION_MODELS.md").write_text(bad, encoding="utf-8")
    with pytest.raises(CurrentKnowledgeIntegrityError, match="model list"):
        validate_current_prime_package(tmp_path)


def test_missing_risk_anchor_fails_closed(tmp_path: Path):
    _valid_package(tmp_path)
    risk = (tmp_path / "RISK_AND_SESSION_RULES.md").read_text(encoding="utf-8").replace(
        "$500 maximum risk", "$750 maximum risk"
    )
    (tmp_path / "RISK_AND_SESSION_RULES.md").write_text(risk, encoding="utf-8")
    with pytest.raises(CurrentKnowledgeIntegrityError, match=r"\$500 risk ceiling"):
        validate_current_prime_package(tmp_path)


def test_missing_current_status_fails_closed(tmp_path: Path):
    _valid_package(tmp_path)
    body = (tmp_path / "README.md").read_text(encoding="utf-8").replace("Status: CURRENT", "Status: DRAFT")
    (tmp_path / "README.md").write_text(body, encoding="utf-8")
    with pytest.raises(CurrentKnowledgeIntegrityError, match="Status: CURRENT"):
        validate_current_prime_package(tmp_path)


REQUIRED_DOCS = (
    "README.md",
    "PRIME_FRAMEWORK.md",
    "EXECUTION_MODELS.md",
    "STRICT_OTE.md",
    "10AM_KEY_LEVEL_OPEN.md",
    "ORB.md",
    "RISK_AND_SESSION_RULES.md",
)


@pytest.mark.parametrize("missing_doc", REQUIRED_DOCS)
def test_each_of_the_seven_required_documents_is_actually_required(tmp_path: Path, missing_doc: str):
    _valid_package(tmp_path)
    (tmp_path / missing_doc).unlink()
    with pytest.raises(CurrentKnowledgeIntegrityError, match="missing current authority documents"):
        validate_current_prime_package(tmp_path)


def test_missing_document_error_names_it(tmp_path: Path):
    _valid_package(tmp_path)
    (tmp_path / "STRICT_OTE.md").unlink()
    with pytest.raises(CurrentKnowledgeIntegrityError, match="STRICT_OTE.md"):
        validate_current_prime_package(tmp_path)


# ─────────────────────────────────────────────────────────────────────────
# Explicit-contradiction rejection: a required good phrase present ELSEWHERE
# in the same document must not mask an explicit contradictory statement
# injected alongside it. Each case keeps every approved anchor from
# _valid_package() and adds one adversarial sentence.
# ─────────────────────────────────────────────────────────────────────────

def test_fourth_active_model_contradicts_exactly_three_even_with_anchor_present(tmp_path: Path):
    _valid_package(tmp_path)
    body = (tmp_path / "EXECUTION_MODELS.md").read_text(encoding="utf-8")
    # The exactly-three anchor stays; a contradictory claim is appended.
    body += "\nThere are four active execution models including Legacy Bounce.\n"
    (tmp_path / "EXECUTION_MODELS.md").write_text(body, encoding="utf-8")
    with pytest.raises(CurrentKnowledgeIntegrityError, match="exactly-three-models invariant"):
        validate_current_prime_package(tmp_path)


def test_pros_declared_active_contradicts_supersession_even_with_anchor_present(tmp_path: Path):
    _valid_package(tmp_path)
    body = (tmp_path / "README.md").read_text(encoding="utf-8")
    body += "\nPROS is a current execution model for MNQ.\n"
    (tmp_path / "README.md").write_text(body, encoding="utf-8")
    with pytest.raises(CurrentKnowledgeIntegrityError, match="PROS supersession"):
        validate_current_prime_package(tmp_path)


def test_fvg_declared_entry_model_contradicts_boundary_even_with_anchor_present(tmp_path: Path):
    _valid_package(tmp_path)
    body = (tmp_path / "EXECUTION_MODELS.md").read_text(encoding="utf-8")
    body += "\nFVG is a valid entry model on the 5m chart.\n"
    (tmp_path / "EXECUTION_MODELS.md").write_text(body, encoding="utf-8")
    with pytest.raises(CurrentKnowledgeIntegrityError, match="FVG boundary"):
        validate_current_prime_package(tmp_path)


def test_second_funded_trade_permitted_contradicts_one_trade_rule_even_with_anchor_present(tmp_path: Path):
    _valid_package(tmp_path)
    body = (tmp_path / "RISK_AND_SESSION_RULES.md").read_text(encoding="utf-8")
    body += "\nA second funded trade is permitted if the first was a loss.\n"
    (tmp_path / "RISK_AND_SESSION_RULES.md").write_text(body, encoding="utf-8")
    with pytest.raises(CurrentKnowledgeIntegrityError, match="one-trade-per-day rule"):
        validate_current_prime_package(tmp_path)


def test_alternate_risk_ceiling_contradicts_500_even_with_anchor_present(tmp_path: Path):
    _valid_package(tmp_path)
    body = (tmp_path / "RISK_AND_SESSION_RULES.md").read_text(encoding="utf-8")
    body += "\n$1000 maximum risk is allowed on high-conviction setups.\n"
    (tmp_path / "RISK_AND_SESSION_RULES.md").write_text(body, encoding="utf-8")
    with pytest.raises(CurrentKnowledgeIntegrityError, match=r"\$500 maximum"):
        validate_current_prime_package(tmp_path)


def test_non_orb_model_approved_before_0945_contradicts_early_window_even_with_anchor_present(tmp_path: Path):
    _valid_package(tmp_path)
    body = (tmp_path / "RISK_AND_SESSION_RULES.md").read_text(encoding="utf-8")
    body += "\nBefore 09:45 ET, Strict OTE is also approved for entries.\n"
    (tmp_path / "RISK_AND_SESSION_RULES.md").write_text(body, encoding="utf-8")
    with pytest.raises(CurrentKnowledgeIntegrityError, match="ORB-only early window"):
        validate_current_prime_package(tmp_path)


def test_valid_package_with_all_seven_documents_still_passes(tmp_path: Path):
    _valid_package(tmp_path)
    names = validate_current_prime_package(tmp_path)
    assert set(names) == set(REQUIRED_DOCS)


def test_assistant_fails_closed_before_provider_call(monkeypatch):
    import services.assistant as svc

    def _boom(_query, **_kwargs):
        raise CurrentKnowledgeIntegrityError("conflict")

    called = {"provider": False}

    def _provider(*_args, **_kwargs):
        called["provider"] = True
        raise AssertionError("provider must not be called")

    monkeypatch.setattr(svc, "retrieve_current_prime", _boom)
    monkeypatch.setattr(svc, "request_intelligence", _provider)
    result = svc.call_assistant_llm("What are the current PRIME models?")

    assert result["outcome"] == "unavailable"
    assert result["knowledge_authority"] == "unavailable"
    assert result["knowledge_sources"] == []
    assert called["provider"] is False


def test_unexpected_markdown_document_fails_closed(tmp_path: Path):
    """CURRENT/PRIME is an allowlisted authority package, not an open folder."""
    _valid_package(tmp_path)
    _write(
        tmp_path,
        "UNREVIEWED_MODEL.md",
        "Status: CURRENT\nAuthority: owner-approved\nLegacy Bounce is current doctrine.\n",
    )
    with pytest.raises(
        CurrentKnowledgeIntegrityError,
        match=r"unexpected current authority documents: UNREVIEWED_MODEL\.md",
    ):
        validate_current_prime_package(tmp_path)
