"""Deterministic tiering and relevance scoring."""

import re

from .constants import TOKEN_OVERLAP_CAP

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOP = frozenset({"a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "in", "is", "it", "of", "on", "or", "the", "to", "with"})


def tokens(text: str) -> frozenset[str]:
    return frozenset(t for t in _TOKEN_RE.findall(text.casefold()) if t not in _STOP)


def tier_for(record) -> str:
    if record.domain == "evidence":
        return "evidence"
    if record.status in {"proposed", "validated"}:
        return "unvalidated"
    if record.kind == "hypothesis":
        return "hypotheses"
    if record.kind in {"status", "phase", "blocker"}:
        return "project_state"
    if record.kind in {"decision", "approval"}:
        return "current_decisions"
    if record.kind in {"rule", "definition"}:
        return "current_rules"
    return "current_facts"


def score(record, mission) -> int:
    value = 0
    if record.subject_entity_key and record.subject_entity_key in mission.scope_entities:
        value += 8
    if record.governance_class in mission.scope_classes:
        value += 4
    if record.domain in mission.scope_domains:
        value += 2
    tier = tier_for(record)
    if tier in {"current_facts", "evidence", "hypotheses", "unvalidated"}:
        value += min(TOKEN_OVERLAP_CAP, len(tokens(record.statement) & tokens(mission.statement)))
    return value


__all__ = ["score", "tier_for", "tokens"]
