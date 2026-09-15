"""Closed constants for the CM-2 Git-only hydration prototype."""

SPEC_VERSION = "cm2-git-hydration-v1"
ESTIMATOR_ID = "utf8-bytes-v1"
BUDGET_UNIT = "utf8_bytes"
CURRENTNESS_MODEL = "bound_commit_only"

MANDATORY_CORE_KEYS = (
    "prime.models.exactly_three",
    "prime.lineage.pros_superseded",
    "prime.fvg.confluence_only",
    "prime.runtime.no_execution_authority",
    "prime.risk.no_execution_authority",
    "governance.agents.no_autonomous_trading",
    "project.roadmap.phase_2f_next",
)

TIERS = (
    "mandatory_invariants", "current_rules", "current_decisions",
    "project_state", "current_facts", "evidence", "hypotheses",
    "unvalidated", "conflicts",
)

EXCLUSION_CODES = frozenset({
    "BOUNDARY", "AUTHORITY_MISMATCH", "STATUS_NOT_CURRENT",
    "NOT_CURRENT_AT_AS_OF", "SUPERSEDED", "RETRACTED", "STALE_SOURCE",
    "PROVENANCE_INCOMPLETE", "UNRESOLVED_CONFLICT", "PROJECTION_EXCLUDED",
    "NOT_RELEVANT", "CANDIDATE_CAP", "BUDGET",
})
REFUSAL_CODES = frozenset({
    "AS_OF_REQUIRED", "AUTHORITY_PACKAGE_INVALID", "BUDGET_INVALID",
    "COMMIT_MISMATCH", "ESTIMATOR_UNKNOWN", "HIGH_WATER_REQUIRED",
    "MANDATORY_CORE_EXCEEDS_BUDGET", "MANDATORY_CORE_UNAVAILABLE",
    "REQUIRED_NOTICES_EXCEED_BUDGET", "SCOPE_EMPTY",
    "SNAPSHOT_COMMIT_MISMATCH", "UNKNOWN_AGENT",
})

PROJECTIONS = {
    "nova.assistant": frozenset({"strategy", "risk", "governance"}),
    "agent.claude.engineering": frozenset({"engineering", "project", "governance"}),
    "agent.codex.implementer": frozenset({"engineering", "project", "governance"}),
    "agent.codex.reviewer": frozenset({"engineering", "project", "governance"}),
    "person.pedro.briefing": frozenset({"strategy", "risk", "project", "governance"}),
    "projection.obsidian": frozenset({"strategy", "risk", "project", "governance"}),
}

CANDIDATE_CAP = 512
ENTITY_EXPANSION_DEPTH = 2
ENTITY_EXPANSION_CAP = 64
TOKEN_OVERLAP_CAP = 6
