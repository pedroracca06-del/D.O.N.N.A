from pathlib import Path

import pytest

from tools.prime_contamination_checker import CURRENT_MODELS, check_files

ROOT = Path(__file__).resolve().parents[1]
PRIME = ROOT / "nova_knowledge_core" / "CURRENT" / "PRIME"

REQUIRED = {
    "README.md",
    "PRIME_FRAMEWORK.md",
    "EXECUTION_MODELS.md",
    "STRICT_OTE.md",
    "10AM_KEY_LEVEL_OPEN.md",
    "ORB.md",
    "RISK_AND_SESSION_RULES.md",
}


def read(name: str) -> str:
    return (PRIME / name).read_text(encoding="utf-8")


def test_current_prime_package_has_required_files():
    assert REQUIRED <= {p.name for p in PRIME.glob("*.md")}


def test_execution_model_surface_has_exact_current_models():
    text = read("EXECUTION_MODELS.md")
    numbered = [line.split(". ", 1)[1] for line in text.splitlines() if line[:1].isdigit() and ". " in line]
    assert tuple(numbered) == CURRENT_MODELS


def test_pros_is_only_superseded_lineage():
    text = (read("README.md") + read("EXECUTION_MODELS.md")).lower()
    assert "dead/superseded" in text
    assert "parallel" not in text or "not a parallel" in text


def test_fvg_is_not_an_entry_model():
    text = (read("README.md") + read("EXECUTION_MODELS.md")).lower()
    assert "fvg is context/confluence only" in text
    assert "not an entry model" in text


def test_funded_eval_governance_is_current():
    text = read("RISK_AND_SESSION_RULES.md")
    assert "one real trade per day" in text
    assert "$500" in text
    assert "Before 09:45 ET, ORB is the only approved execution model" in text


def test_current_prime_markdown_passes_contamination_checker():
    paths = [str(PRIME / name) for name in sorted(REQUIRED)]
    assert check_files(paths) == {}


def test_current_package_does_not_authorize_runtime_execution():
    text = "\n".join(read(name) for name in REQUIRED).lower()
    assert "does not authorize broker execution" in text or "do not authorize broker execution" in text


@pytest.mark.parametrize("missing_doc", sorted(REQUIRED))
def test_each_required_document_is_present_on_disk(missing_doc):
    """Every name test_current_knowledge_integrity.py requires must actually exist here."""
    assert (PRIME / missing_doc).is_file()


# ─────────────────────────────────────────────────────────────────────────
# Strict OTE mechanics -- pinned to Pedro's locked definition. No element
# here may be inferred; each assertion checks the exact locked component.
# ─────────────────────────────────────────────────────────────────────────

def test_strict_ote_requires_a_liquidity_sweep_at_origin():
    text = read("STRICT_OTE.md").lower()
    assert "liquidity event" in text or "sweep" in text
    assert "origin" in text


def test_strict_ote_requires_displacement_that_proves_intent():
    text = read("STRICT_OTE.md").lower()
    assert "displacement" in text
    assert "breaks structure" in text
    assert "intent" in text and "control" in text


def test_strict_ote_dealing_range_is_objective_not_discretionary():
    text = read("STRICT_OTE.md").lower()
    assert "objective dealing range" in text
    assert "discretionary" in text


def test_strict_ote_fib_is_wick_to_wick_and_directional():
    text = read("STRICT_OTE.md").lower()
    assert "wick-to-wick" in text
    assert "low-to-high" in text  # long
    assert "high-to-low" in text  # short


def test_strict_ote_zone_is_618_786_with_5_as_equilibrium_only():
    text = read("STRICT_OTE.md").lower()
    assert "0.618-0.786" in text or ("0.618" in text and "0.786" in text)
    assert "0.5 is the equilibrium reference only" in text


def test_strict_ote_fib_touch_alone_is_not_ote():
    text = read("STRICT_OTE.md").lower()
    assert "a fib touch alone is not ote" in text


def test_strict_ote_requires_htf_context_and_pd_array_confluence():
    text = read("STRICT_OTE.md").lower()
    assert "htf" in text and "context" in text
    assert "pd-array" in text
    assert "confluence" in text


def test_strict_ote_requires_prime_reclaim_acceptance_confirmation():
    text = read("STRICT_OTE.md").lower()
    assert "prime reclaim/acceptance confirmation" in text


def test_strict_ote_risk_is_placed_by_structure():
    text = read("STRICT_OTE.md").lower()
    assert "risk is placed by structure" in text


def test_strict_ote_fvg_is_confluence_only_not_entry():
    text = read("STRICT_OTE.md").lower()
    assert "fvg is context/confluence only" in text
    assert "not an entry model" in text


def test_strict_ote_stdv_is_a_companion_not_a_fourth_model():
    text = read("STRICT_OTE.md").lower()
    assert "stdv" in text
    assert "companion" in text
    assert "not a fourth execution model" in text
