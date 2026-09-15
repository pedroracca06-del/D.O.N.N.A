"""Immutable, fail-closed types for CM-2 hydration."""

from __future__ import annotations

import re
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping

from intelligence.canonical_memory import hashing, schema as cm1_schema
from .constants import BUDGET_UNIT, CURRENTNESS_MODEL, ESTIMATOR_ID, EXCLUSION_CODES, REFUSAL_CODES, TIERS

_KEY_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
_OID_RE = re.compile(r"^[0-9a-f]{40}$|^[0-9a-f]{64}$")
_UTC_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$")


class HydrationError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"[{code}] {message}")
        self.code = code


def _tuple_strings(value: Any, name: str) -> tuple[str, ...]:
    if not isinstance(value, tuple) or any(not isinstance(v, str) or not v for v in value):
        raise HydrationError("INPUT_TYPE", f"{name} must be a tuple of non-empty strings")
    if len(value) != len(set(value)):
        raise HydrationError("INPUT_DUPLICATE", f"{name} contains duplicates")
    return value


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({k: _freeze(v) for k, v in sorted(value.items())})
    if isinstance(value, (tuple, list)):
        return tuple(_freeze(v) for v in value)
    return value


@dataclass(frozen=True, slots=True)
class Relationship:
    relationship_type: str
    record_keys: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.relationship_type not in {"conflict", "stale"}:
            raise HydrationError("RELATIONSHIP_TYPE", "relationship type is closed")
        keys = _tuple_strings(self.record_keys, "record_keys")
        if not keys:
            raise HydrationError("RELATIONSHIP_KEYS", "relationship needs records")


@dataclass(frozen=True, slots=True)
class MemorySnapshot:
    commit_oid: str
    tree_oid: str
    spec_version: str
    schema_version: int
    ingest_result_hash: str
    sources: tuple[cm1_schema.SourceRef, ...]
    entities: tuple[cm1_schema.EntityRecord, ...]
    records: tuple[cm1_schema.MemoryRecord, ...]
    links: tuple[cm1_schema.RecordSourceLink, ...]
    relationships: tuple[Relationship, ...] = ()
    authority_package_valid: bool = True

    def __post_init__(self) -> None:
        if not _OID_RE.fullmatch(self.commit_oid) or not _OID_RE.fullmatch(self.tree_oid):
            raise HydrationError("SNAPSHOT_OID", "snapshot object ids must be full lowercase hex")
        if not hashing.is_sha256_hex(self.ingest_result_hash):
            raise HydrationError("SNAPSHOT_HASH", "invalid ingest result hash")
        if not isinstance(self.authority_package_valid, bool):
            raise HydrationError("AUTHORITY_PACKAGE_INVALID", "authority package verdict must be boolean")
        cm1_schema.assert_integrity(self.sources, self.entities, self.records, self.links)
        if any(r.bound_commit != self.commit_oid for r in self.records):
            raise HydrationError("SNAPSHOT_COMMIT_MISMATCH", "record bound to another commit")

    @classmethod
    def from_ingest_result(cls, result: Any) -> "MemorySnapshot":
        return cls(
            commit_oid=result.commit_oid, tree_oid=result.tree_oid,
            spec_version=result.spec_version, schema_version=result.schema_version,
            ingest_result_hash=result.result_hash, sources=result.sources,
            entities=result.entities, records=result.records, links=result.links,
        )


@dataclass(frozen=True, slots=True)
class Mission:
    mission_id: str
    statement: str
    scope_entities: tuple[str, ...]
    scope_classes: tuple[str, ...]
    scope_domains: tuple[str, ...]
    as_of: str
    bound_commit: str
    event_high_water: None = None

    def __post_init__(self) -> None:
        if not _KEY_RE.fullmatch(self.mission_id):
            raise HydrationError("MISSION_ID", "invalid mission id")
        if not isinstance(self.statement, str) or not self.statement.strip():
            raise HydrationError("MISSION_STATEMENT", "statement must be non-empty text")
        _tuple_strings(self.scope_entities, "scope_entities")
        _tuple_strings(self.scope_classes, "scope_classes")
        _tuple_strings(self.scope_domains, "scope_domains")
        if not _UTC_RE.fullmatch(self.as_of or ""):
            raise HydrationError("AS_OF_REQUIRED", "as_of must be caller-supplied UTC RFC3339")
        if not _OID_RE.fullmatch(self.bound_commit):
            raise HydrationError("COMMIT_MISMATCH", "bound commit must be a full oid")
        if self.event_high_water is not None:
            raise HydrationError("HIGH_WATER_REQUIRED", "event high water is unsupported in bootstrap")


@dataclass(frozen=True, slots=True)
class Budget:
    limit: int
    reserve: int = 0
    estimator_id: str = ESTIMATOR_ID
    unit: str = BUDGET_UNIT

    def __post_init__(self) -> None:
        if isinstance(self.limit, bool) or not isinstance(self.limit, int) or self.limit <= 0:
            raise HydrationError("BUDGET_INVALID", "limit must be a positive integer")
        if isinstance(self.reserve, bool) or not isinstance(self.reserve, int) or self.reserve < 0 or self.reserve >= self.limit:
            raise HydrationError("BUDGET_INVALID", "reserve must be non-negative and below limit")
        if self.estimator_id != ESTIMATOR_ID or self.unit != BUDGET_UNIT:
            raise HydrationError("ESTIMATOR_UNKNOWN", "CM-2 supports utf8 bytes only")


@dataclass(frozen=True, slots=True)
class Exclusion:
    record_key: str
    version: int
    code: str

    def __post_init__(self) -> None:
        if self.code not in EXCLUSION_CODES:
            raise HydrationError("EXCLUSION_CODE", "unknown exclusion code")


@dataclass(frozen=True, slots=True)
class Notice:
    notice_type: str
    record_keys: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.notice_type not in {"conflict", "stale"}:
            raise HydrationError("NOTICE_TYPE", "unknown notice type")
        _tuple_strings(self.record_keys, "record_keys")


@dataclass(frozen=True, slots=True)
class HydrationRefusal:
    code: str
    detail: str

    def __post_init__(self) -> None:
        if self.code not in REFUSAL_CODES:
            raise HydrationError("REFUSAL_CODE", "unknown refusal code")


@dataclass(frozen=True, slots=True)
class HydrationPacket:
    sections: tuple[tuple[str, tuple[str, ...]], ...]
    manifest: Mapping[str, Any]
    rendered: str
    packet_hash: str

    def __post_init__(self) -> None:
        if tuple(name for name, _ in self.sections) != TIERS:
            raise HydrationError("SECTION_ORDER", "all tiers must appear in fixed order")
        object.__setattr__(self, "manifest", _freeze(self.manifest))
        expected = hashing.canonical_hash({"manifest": self.manifest, "rendered": self.rendered})
        if self.packet_hash != expected:
            raise HydrationError("PACKET_HASH_MISMATCH", "packet hash does not match content")


__all__ = ["Budget", "Exclusion", "HydrationError", "HydrationPacket", "HydrationRefusal", "MemorySnapshot", "Mission", "Notice", "Relationship"]
