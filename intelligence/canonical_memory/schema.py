"""Closed, fail-closed record schema for the CM-1 Git-mirror bootstrap (schema v1).

Standard library only. No I/O, no clock, no environment. Construction is
validation: an instance that exists has passed every check, and every rejection
carries a stable ``code``.

Enumerations follow docs/canonical-memory/ARCHITECTURE_V1.md §5 and §7, narrowed
for the bootstrap where the approved CM-1 boundary is narrower:

* ``authority`` is ``git`` only. Git decides every subject during bootstrap
  (AUTHORITY_AND_PROMOTION.md §2.1; decision D3 keeps PRIME Git-authoritative).
* ``source_kind`` is ``git_blob`` only and ``trust_class`` is
  ``authoritative_git`` only, because CM-1 reads nothing but verified Git blobs.

Governance fields (domain, kind, governance_class, status, authority) are set by
the caller's literal parameters and validated here. Nothing in this module parses
them from a statement, body, path, or heading.

Locked invariants: exactly three active ``prime_model`` entities (Strict OTE,
10AM Key Level Open, ORB); PROS exists only as historical/superseded lineage;
FVG is never a model; evidence can never hold a rule or a current status.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Iterable, Mapping, Sequence

from intelligence.canonical_memory import hashing
from intelligence.canonical_memory.hashing import CM1Error

SCHEMA_VERSION = 1

# ---------------------------------------------------------------------------
# Closed enumerations
# ---------------------------------------------------------------------------

DOMAIN_KNOWLEDGE = "knowledge"
DOMAIN_OPERATIONAL = "operational"
DOMAIN_EVIDENCE = "evidence"
DOMAINS: frozenset[str] = frozenset({DOMAIN_KNOWLEDGE, DOMAIN_OPERATIONAL, DOMAIN_EVIDENCE})

KIND_PAIRS: Mapping[str, frozenset[str]] = MappingProxyType(
    {
        DOMAIN_KNOWLEDGE: frozenset({"fact", "rule", "hypothesis", "definition", "decision"}),
        DOMAIN_OPERATIONAL: frozenset({"decision", "status", "blocker", "approval", "phase"}),
        DOMAIN_EVIDENCE: frozenset({"observation", "measurement", "test_result", "review_finding"}),
    }
)

GOVERNANCE_CLASSES: frozenset[str] = frozenset(
    {"strategy", "risk", "research", "engineering", "project", "market_context", "governance"}
)

_DECISION_STATUSES = frozenset(
    {"proposed", "validated", "current", "superseded", "rejected", "retracted"}
)
STATUSES_BY_DOMAIN: Mapping[str, frozenset[str]] = MappingProxyType(
    {
        DOMAIN_KNOWLEDGE: _DECISION_STATUSES,
        DOMAIN_OPERATIONAL: _DECISION_STATUSES,
        DOMAIN_EVIDENCE: frozenset({"recorded", "disputed", "retracted"}),
    }
)

AUTHORITY_GIT = "git"
#: Bootstrap authority enum. ``canonical_memory`` does not exist until an
#: explicit, Pedro-approved per-scope cutover; admitting it here would let a
#: record claim a decider that has not been granted.
AUTHORITIES: frozenset[str] = frozenset({AUTHORITY_GIT})

CONFIDENCE_NOT_APPLICABLE = "not_applicable"
CONFIDENCE_LEVELS: frozenset[str] = frozenset({"low", "medium", "high", CONFIDENCE_NOT_APPLICABLE})

ENTITY_TYPES: frozenset[str] = frozenset(
    {"prime_model", "symbol", "phase", "component", "document", "agent", "person", "project", "concept"}
)
LIFECYCLES: frozenset[str] = frozenset({"active", "historical", "superseded"})

SOURCE_KIND_GIT_BLOB = "git_blob"
SOURCE_KINDS: frozenset[str] = frozenset({SOURCE_KIND_GIT_BLOB})
TRUST_CLASS_AUTHORITATIVE_GIT = "authoritative_git"
TRUST_CLASSES: frozenset[str] = frozenset({TRUST_CLASS_AUTHORITATIVE_GIT})

ROLE_PRIMARY = "primary"
LINK_ROLES: frozenset[str] = frozenset({ROLE_PRIMARY, "supporting", "contradicting", "derived_from"})

# ---------------------------------------------------------------------------
# Locked PRIME universe
# ---------------------------------------------------------------------------

ENTITY_TYPE_PRIME_MODEL = "prime_model"
PRIME_MODEL_ENTITY_KEYS: Mapping[str, str] = MappingProxyType(
    {
        "prime.model.strict_ote": "Strict OTE",
        "prime.model.10am_key_level_open": "10AM Key Level Open",
        "prime.model.orb": "ORB",
    }
)
PROS_ENTITY_KEY = "prime.lineage.pros"
FVG_ENTITY_KEY = "prime.concept.fvg"

#: Keys a record body or entity attributes may never carry: governance is set by
#: literal parameters, never smuggled through a payload.
GOVERNANCE_PAYLOAD_KEYS: frozenset[str] = frozenset(
    {
        "approval",
        "approval_ref",
        "authority",
        "domain",
        "governance_class",
        "kind",
        "lifecycle",
        "record_key",
        "status",
        "version",
    }
)

_KEY_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
_OID_RE = re.compile(r"^[0-9a-f]{40}$|^[0-9a-f]{64}$")
_MAX_STATEMENT_CHARS = 4000
_MAX_REPO_PATH_CHARS = 512

#: C0 (except LF), DEL, C1, zero-width, bidirectional and BOM characters. A
#: statement is rendered to agents later; invisible or reordering characters are
#: an injection surface, so they are refused rather than stripped.
INVISIBLE_CODE_POINT_RANGES: tuple[tuple[int, int], ...] = (
    (0x200B, 0x200F),  # zero-width space/joiners, LRM, RLM
    (0x202A, 0x202E),  # bidirectional embeddings and overrides
    (0x2060, 0x2069),  # word joiner, invisible operators, bidi isolates
    (0xFEFF, 0xFEFF),  # BOM / zero-width no-break space
)
STATEMENT_FORBIDDEN_CHARACTER_RE = re.compile(
    r"[\x00-\x09\x0b-\x1f\x7f-\x9f"
    + "".join(chr(low) + "-" + chr(high) for low, high in INVISIBLE_CODE_POINT_RANGES)
    + "]"
)
#: A hydration section marker of the kind the Assistant neutralises. Matched
#: after NFKC folding so full-width look-alikes are caught too.
SOURCE_MARKER_RE = re.compile(r"\[\s*current\s+source\s*:", re.IGNORECASE)


class SchemaValidationError(CM1Error):
    """A record, link, entity, or source failed closed validation."""


@dataclass(frozen=True, slots=True)
class IntegrityIssue:
    code: str
    message: str
    subject: str | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fail(code: str, message: str, subject: str | None = None) -> None:
    raise SchemaValidationError(code, message, subject=subject)


def _clean_text(value: Any, code: str, name: str, subject: str | None) -> str:
    if not isinstance(value, str):
        _fail(code, f"{name} must be a string, got {type(value).__name__}", subject)
    if not value or value != value.strip():
        _fail(code, f"{name} must be non-empty and free of surrounding whitespace", subject)
    return value


def _member(value: Any, allowed: frozenset[str], code: str, name: str, subject: str | None) -> str:
    if not isinstance(value, str) or value not in allowed:
        _fail(code, f"{name} must be one of {sorted(allowed)}, got {value!r}", subject)
    return value


def _key(value: Any, code: str, name: str, subject: str | None) -> str:
    if not isinstance(value, str) or not _KEY_RE.match(value):
        _fail(code, f"{name} must match {_KEY_RE.pattern}, got {value!r}", subject)
    return value


def _positive_int(value: Any, code: str, name: str, subject: str | None) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        _fail(code, f"{name} must be an integer >= 1, got {value!r}", subject)
    return value


def _oid(value: Any, code: str, name: str, subject: str | None) -> str:
    if not isinstance(value, str) or not _OID_RE.match(value):
        _fail(code, f"{name} must be a full 40- or 64-character lowercase hex object id", subject)
    return value


def _sha256(value: Any, code: str, name: str, subject: str | None) -> str:
    if not hashing.is_sha256_hex(value):
        _fail(code, f"{name} must be exactly 64 lowercase hexadecimal characters", subject)
    return value


def validate_repo_path(value: Any, *, code: str = "REPO_PATH", subject: str | None = None) -> str:
    """Repository-relative POSIX path, or fail. No drive, UNC, home, dot segment."""
    if not isinstance(value, str) or not value:
        _fail(code, "repo_path must be a non-empty string", subject)
    if len(value) > _MAX_REPO_PATH_CHARS:
        _fail(code, "repo_path is too long", subject)
    if STATEMENT_FORBIDDEN_CHARACTER_RE.search(value) or "\n" in value:
        _fail(code, "repo_path contains a control or invisible character", subject)
    if "\\" in value or ":" in value:
        _fail(code, "repo_path must use '/' only and carry no drive or stream separator", subject)
    if value.startswith(("/", "~")):
        _fail(code, "repo_path must be repository-relative", subject)
    for segment in value.split("/"):
        if segment in ("", ".", "..") or segment != segment.strip():
            _fail(code, f"repo_path has an empty, dot, or padded segment: {value!r}", subject)
    return value


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze(item) for key, item in sorted(value.items())})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    return value


def _payload(value: Any, code: str, name: str, subject: str | None) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        _fail(code, f"{name} must be a mapping, got {type(value).__name__}", subject)
    try:
        hashing.canonical_json(value)
    except hashing.HashingError as exc:
        _fail(code, f"{name} is not canonical JSON: {exc}", subject)
    forbidden = sorted(GOVERNANCE_PAYLOAD_KEYS & set(value))
    if forbidden:
        _fail(f"{code}_GOVERNANCE", f"{name} may not carry governance keys {forbidden}", subject)
    return _freeze(value)


def check_statement(value: Any, subject: str | None = None) -> str:
    """Validate statement text as data: bounded, visible, and marker-free."""
    if not isinstance(value, str) or not value.strip():
        _fail("STATEMENT", "statement must be a non-empty string", subject)
    if len(value) > _MAX_STATEMENT_CHARS:
        _fail("STATEMENT", "statement is too long", subject)
    if STATEMENT_FORBIDDEN_CHARACTER_RE.search(value):
        _fail("STATEMENT_CONTROL_CHARACTER", "statement contains a control or invisible character", subject)
    if SOURCE_MARKER_RE.search(unicodedata.normalize("NFKC", value)):
        _fail("STATEMENT_MARKER", "statement contains a source-section marker", subject)
    return value


def _from_mapping(
    cls: type,
    data: Any,
    required: Sequence[str],
    optional: Sequence[str] = (),
) -> Any:
    if not isinstance(data, Mapping):
        _fail("RECORD_TYPE", f"{cls.__name__} input must be a mapping, got {type(data).__name__}")
    unknown = sorted(set(data) - set(required) - set(optional))
    if unknown:
        _fail("UNKNOWN_FIELD", f"unrecognized field(s) {unknown}; the schema is closed")
    missing = [name for name in required if name not in data]
    if missing:
        _fail("MISSING_FIELD", f"incomplete {cls.__name__}, missing field(s) {missing}")
    return cls(**{name: data[name] for name in (*required, *optional) if name in data})


# ---------------------------------------------------------------------------
# SourceRef
# ---------------------------------------------------------------------------

SOURCE_FIELDS: tuple[str, ...] = (
    "source_kind",
    "repo_path",
    "git_commit",
    "git_blob_oid",
    "content_hash",
    "trust_class",
    "copyright_restricted",
    "stable_ref",
    "source_identity",
)


@dataclass(frozen=True, slots=True)
class SourceRef:
    """A verified Git blob at a full commit. Identity is recomputed, never trusted."""

    source_kind: str
    repo_path: str
    git_commit: str
    git_blob_oid: str
    content_hash: str
    trust_class: str
    copyright_restricted: bool
    stable_ref: str
    source_identity: str

    def __post_init__(self) -> None:
        _member(self.source_kind, SOURCE_KINDS, "SOURCE_KIND", "source_kind", None)
        path = validate_repo_path(self.repo_path)
        _oid(self.git_commit, "GIT_COMMIT", "git_commit", path)
        _oid(self.git_blob_oid, "GIT_BLOB_OID", "git_blob_oid", path)
        if len(self.git_commit) != len(self.git_blob_oid):
            _fail("OID_FORMAT_MIXED", "commit and blob ids use different object formats", path)
        _sha256(self.content_hash, "CONTENT_HASH", "content_hash", path)
        _member(self.trust_class, TRUST_CLASSES, "TRUST_CLASS", "trust_class", path)
        if not isinstance(self.copyright_restricted, bool):
            _fail("COPYRIGHT_RESTRICTED", "copyright_restricted must be a bool", path)
        if self.copyright_restricted:
            _fail("COPYRIGHT_RESTRICTED", "a restricted source cannot back stored statements", path)
        expected_ref = hashing.stable_ref(self.source_kind, path)
        if self.stable_ref != expected_ref:
            _fail("STABLE_REF_MISMATCH", "claimed stable_ref does not match its recomputation", path)
        expected_identity = hashing.source_identity(
            self.source_kind, expected_ref, self.git_commit, self.content_hash
        )
        if self.source_identity != expected_identity:
            _fail("SOURCE_IDENTITY_MISMATCH", "claimed source_identity does not match its recomputation", path)

    @classmethod
    def build(cls, *, repo_path: str, git_commit: str, git_blob_oid: str, content_hash: str) -> "SourceRef":
        path = validate_repo_path(repo_path)
        ref = hashing.stable_ref(SOURCE_KIND_GIT_BLOB, path)
        if not isinstance(git_commit, str) or not hashing.is_sha256_hex(content_hash):
            identity = ""
        else:
            identity = hashing.source_identity(SOURCE_KIND_GIT_BLOB, ref, git_commit, content_hash)
        return cls(
            source_kind=SOURCE_KIND_GIT_BLOB,
            repo_path=path,
            git_commit=git_commit,
            git_blob_oid=git_blob_oid,
            content_hash=content_hash,
            trust_class=TRUST_CLASS_AUTHORITATIVE_GIT,
            copyright_restricted=False,
            stable_ref=ref,
            source_identity=identity,
        )

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "SourceRef":
        return _from_mapping(cls, data, SOURCE_FIELDS)

    def to_mapping(self) -> Mapping[str, Any]:
        return MappingProxyType({name: getattr(self, name) for name in SOURCE_FIELDS})


# ---------------------------------------------------------------------------
# EntityRecord
# ---------------------------------------------------------------------------

ENTITY_REQUIRED_FIELDS: tuple[str, ...] = ("entity_key", "entity_type", "display_name", "lifecycle")
ENTITY_OPTIONAL_FIELDS: tuple[str, ...] = ("attributes",)


@dataclass(frozen=True, slots=True)
class EntityRecord:
    entity_key: str
    entity_type: str
    display_name: str
    lifecycle: str
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        key = _key(self.entity_key, "ENTITY_KEY", "entity_key", None)
        _member(self.entity_type, ENTITY_TYPES, "ENTITY_TYPE", "entity_type", key)
        _clean_text(self.display_name, "DISPLAY_NAME", "display_name", key)
        check_statement(self.display_name, key)
        _member(self.lifecycle, LIFECYCLES, "LIFECYCLE", "lifecycle", key)
        object.__setattr__(self, "attributes", _payload(self.attributes, "ATTRIBUTES", "attributes", key))
        if self.entity_type == ENTITY_TYPE_PRIME_MODEL:
            if key not in PRIME_MODEL_ENTITY_KEYS:
                _fail("PRIME_MODEL_UNKNOWN", "not one of the three locked PRIME models", key)
            if self.display_name != PRIME_MODEL_ENTITY_KEYS[key]:
                _fail("PRIME_MODEL_DISPLAY_NAME", "display_name differs from the locked model name", key)
        elif key in PRIME_MODEL_ENTITY_KEYS:
            _fail("PRIME_MODEL_TYPE", "a locked PRIME model key must have entity_type prime_model", key)
        if key == PROS_ENTITY_KEY and self.lifecycle == "active":
            _fail("PROS_LIFECYCLE", "PROS exists only as historical or superseded lineage", key)

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "EntityRecord":
        return _from_mapping(cls, data, ENTITY_REQUIRED_FIELDS, ENTITY_OPTIONAL_FIELDS)

    def to_mapping(self) -> Mapping[str, Any]:
        return MappingProxyType(
            {
                "attributes": self.attributes,
                "display_name": self.display_name,
                "entity_key": self.entity_key,
                "entity_type": self.entity_type,
                "lifecycle": self.lifecycle,
            }
        )


# ---------------------------------------------------------------------------
# MemoryRecord
# ---------------------------------------------------------------------------

RECORD_FIELDS: tuple[str, ...] = (
    "record_key",
    "version",
    "domain",
    "kind",
    "governance_class",
    "status",
    "authority",
    "subject_entity_key",
    "statement",
    "statement_hash",
    "body",
    "confidence",
    "confidence_basis",
    "bound_commit",
    "supersedes_version",
    "proposed_by",
)


@dataclass(frozen=True, slots=True)
class MemoryRecord:
    """One immutable assertion, bound to the commit it was mirrored from."""

    record_key: str
    version: int
    domain: str
    kind: str
    governance_class: str
    status: str
    authority: str
    subject_entity_key: str | None
    statement: str
    statement_hash: str
    body: Mapping[str, Any]
    confidence: str
    confidence_basis: str | None
    bound_commit: str
    supersedes_version: int | None
    proposed_by: str

    def __post_init__(self) -> None:
        key = _key(self.record_key, "RECORD_KEY", "record_key", None)
        _positive_int(self.version, "VERSION", "version", key)
        domain = _member(self.domain, DOMAINS, "DOMAIN", "domain", key)
        _member(self.kind, KIND_PAIRS[domain], "KIND", f"kind for domain {domain!r}", key)
        _member(self.governance_class, GOVERNANCE_CLASSES, "GOVERNANCE_CLASS", "governance_class", key)
        _member(self.status, STATUSES_BY_DOMAIN[domain], "STATUS", f"status for domain {domain!r}", key)
        _member(self.authority, AUTHORITIES, "AUTHORITY", "authority", key)
        if self.subject_entity_key is not None:
            _key(self.subject_entity_key, "SUBJECT_ENTITY_KEY", "subject_entity_key", key)
        check_statement(self.statement, key)
        _sha256(self.statement_hash, "STATEMENT_HASH", "statement_hash", key)
        if self.statement_hash != hashing.text_hash(self.statement):
            _fail("STATEMENT_HASH_MISMATCH", "claimed statement_hash does not match the statement", key)
        body = _payload(self.body, "BODY", "body", key)
        if body.get("schema_version") != SCHEMA_VERSION or isinstance(body.get("schema_version"), bool):
            _fail("BODY_SCHEMA_VERSION", f"body must carry schema_version {SCHEMA_VERSION}", key)
        object.__setattr__(self, "body", body)
        confidence = _member(self.confidence, CONFIDENCE_LEVELS, "CONFIDENCE", "confidence", key)
        if confidence == CONFIDENCE_NOT_APPLICABLE:
            if self.confidence_basis is not None:
                _fail("CONFIDENCE_BASIS", "confidence_basis must be absent when not_applicable", key)
        else:
            _clean_text(self.confidence_basis, "CONFIDENCE_BASIS", "confidence_basis", key)
        _oid(self.bound_commit, "BOUND_COMMIT", "bound_commit", key)
        if self.supersedes_version is not None:
            _positive_int(self.supersedes_version, "SUPERSEDES_VERSION", "supersedes_version", key)
            if self.supersedes_version >= self.version:
                _fail("SUPERSEDES_VERSION", "supersedes_version must be lower than version", key)
        _key(self.proposed_by, "PROPOSED_BY", "proposed_by", key)

    @classmethod
    def build(cls, **fields: Any) -> "MemoryRecord":
        statement = fields.get("statement")
        if "statement_hash" not in fields and isinstance(statement, str):
            fields["statement_hash"] = hashing.text_hash(statement)
        return cls(**fields)

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "MemoryRecord":
        return _from_mapping(cls, data, RECORD_FIELDS)

    def to_mapping(self) -> Mapping[str, Any]:
        return MappingProxyType({name: getattr(self, name) for name in RECORD_FIELDS})


# ---------------------------------------------------------------------------
# RecordSourceLink
# ---------------------------------------------------------------------------

LINK_FIELDS: tuple[str, ...] = ("record_key", "version", "source_identity", "role", "excerpt_hash")


@dataclass(frozen=True, slots=True)
class RecordSourceLink:
    record_key: str
    version: int
    source_identity: str
    role: str
    excerpt_hash: str

    def __post_init__(self) -> None:
        key = _key(self.record_key, "RECORD_KEY", "record_key", None)
        _positive_int(self.version, "VERSION", "version", key)
        _sha256(self.source_identity, "SOURCE_IDENTITY", "source_identity", key)
        _member(self.role, LINK_ROLES, "ROLE", "role", key)
        _sha256(self.excerpt_hash, "EXCERPT_HASH", "excerpt_hash", key)

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "RecordSourceLink":
        return _from_mapping(cls, data, LINK_FIELDS)

    def to_mapping(self) -> Mapping[str, Any]:
        return MappingProxyType({name: getattr(self, name) for name in LINK_FIELDS})


# ---------------------------------------------------------------------------
# Set-level integrity
# ---------------------------------------------------------------------------


def _require_types(items: Iterable[Any], cls: type, name: str) -> tuple[Any, ...]:
    out = tuple(items)
    for item in out:
        if not isinstance(item, cls):
            _fail("RECORD_TYPE", f"{name} must contain only {cls.__name__}, got {type(item).__name__}")
    return out


def find_integrity_issues(
    sources: Iterable[SourceRef],
    entities: Iterable[EntityRecord],
    records: Iterable[MemoryRecord],
    links: Iterable[RecordSourceLink],
) -> tuple[IntegrityIssue, ...]:
    """Report every set-level problem, in a fixed order, without raising."""
    sources = _require_types(sources, SourceRef, "sources")
    entities = _require_types(entities, EntityRecord, "entities")
    records = _require_types(records, MemoryRecord, "records")
    links = _require_types(links, RecordSourceLink, "links")
    issues: list[IntegrityIssue] = []

    by_identity: dict[str, SourceRef] = {}
    paths: set[str] = set()
    for source in sources:
        if source.source_identity in by_identity:
            issues.append(IntegrityIssue("DUPLICATE_SOURCE_IDENTITY", "source identity repeated", source.repo_path))
        by_identity[source.source_identity] = source
        if source.repo_path in paths:
            issues.append(IntegrityIssue("DUPLICATE_SOURCE_PATH", "one path, two sources", source.repo_path))
        paths.add(source.repo_path)
    commits = {source.git_commit for source in sources}
    if len(commits) > 1:
        issues.append(IntegrityIssue("MIXED_COMMIT", "sources are bound to more than one commit"))

    entity_keys: dict[str, EntityRecord] = {}
    for entity in entities:
        if entity.entity_key in entity_keys:
            issues.append(IntegrityIssue("DUPLICATE_ENTITY_KEY", "entity key repeated", entity.entity_key))
        entity_keys[entity.entity_key] = entity
    active_models = sorted(
        e.entity_key for e in entities if e.entity_type == ENTITY_TYPE_PRIME_MODEL and e.lifecycle == "active"
    )
    if active_models != sorted(PRIME_MODEL_ENTITY_KEYS):
        issues.append(
            IntegrityIssue(
                "PRIME_MODEL_SET",
                f"active prime_model entities must be exactly {sorted(PRIME_MODEL_ENTITY_KEYS)}, got {active_models}",
            )
        )

    versions: set[tuple[str, int]] = set()
    current_keys: set[str] = set()
    domains_by_key: dict[str, set[str]] = {}
    for record in records:
        identity = (record.record_key, record.version)
        if identity in versions:
            issues.append(IntegrityIssue("DUPLICATE_RECORD_VERSION", "record version repeated", record.record_key))
        versions.add(identity)
        if record.status == "current":
            if record.record_key in current_keys:
                issues.append(IntegrityIssue("MULTIPLE_CURRENT", "more than one current version", record.record_key))
            current_keys.add(record.record_key)
        domains_by_key.setdefault(record.record_key, set()).add(record.domain)
        if record.subject_entity_key is not None and record.subject_entity_key not in entity_keys:
            issues.append(IntegrityIssue("SUBJECT_UNRESOLVED", "subject entity is not in the set", record.record_key))
        if record.bound_commit not in commits:
            issues.append(IntegrityIssue("RECORD_COMMIT_MISMATCH", "record is not bound to the source commit", record.record_key))
    for key, domains in sorted(domains_by_key.items()):
        if DOMAIN_EVIDENCE in domains and len(domains) > 1:
            issues.append(IntegrityIssue("EVIDENCE_KEY_COLLISION", "evidence shares a key with a decision record", key))

    seen_links: set[tuple[str, int, str, str]] = set()
    primaries: set[tuple[str, int]] = set()
    by_record = {(r.record_key, r.version): r for r in records}
    for link in links:
        identity = (link.record_key, link.version, link.source_identity, link.role)
        if identity in seen_links:
            issues.append(IntegrityIssue("DUPLICATE_LINK", "record source link repeated", link.record_key))
        seen_links.add(identity)
        record = by_record.get((link.record_key, link.version))
        if record is None:
            issues.append(IntegrityIssue("LINK_RECORD_UNRESOLVED", "link names no record in the set", link.record_key))
            continue
        source = by_identity.get(link.source_identity)
        if source is None:
            issues.append(IntegrityIssue("LINK_SOURCE_UNRESOLVED", "link names no source in the set", link.record_key))
            continue
        if source.git_commit != record.bound_commit:
            issues.append(IntegrityIssue("RECORD_COMMIT_MISMATCH", "linked source is from another commit", link.record_key))
        if link.role == ROLE_PRIMARY:
            primaries.add((link.record_key, link.version))
    for record in records:
        if (record.record_key, record.version) not in primaries:
            issues.append(IntegrityIssue("PROVENANCE_INCOMPLETE", "record has no resolving primary source", record.record_key))

    return tuple(issues)


def assert_integrity(
    sources: Iterable[SourceRef],
    entities: Iterable[EntityRecord],
    records: Iterable[MemoryRecord],
    links: Iterable[RecordSourceLink],
) -> None:
    issues = find_integrity_issues(sources, entities, records, links)
    if issues:
        first = issues[0]
        _fail(first.code, f"{first.message} ({len(issues)} integrity issue(s) total)", first.subject)


__all__ = [
    "AUTHORITIES",
    "AUTHORITY_GIT",
    "CONFIDENCE_LEVELS",
    "CONFIDENCE_NOT_APPLICABLE",
    "DOMAINS",
    "DOMAIN_EVIDENCE",
    "DOMAIN_KNOWLEDGE",
    "DOMAIN_OPERATIONAL",
    "ENTITY_OPTIONAL_FIELDS",
    "ENTITY_REQUIRED_FIELDS",
    "ENTITY_TYPES",
    "ENTITY_TYPE_PRIME_MODEL",
    "EntityRecord",
    "FVG_ENTITY_KEY",
    "GOVERNANCE_CLASSES",
    "GOVERNANCE_PAYLOAD_KEYS",
    "IntegrityIssue",
    "KIND_PAIRS",
    "LIFECYCLES",
    "LINK_FIELDS",
    "LINK_ROLES",
    "MemoryRecord",
    "PRIME_MODEL_ENTITY_KEYS",
    "PROS_ENTITY_KEY",
    "RECORD_FIELDS",
    "ROLE_PRIMARY",
    "RecordSourceLink",
    "SCHEMA_VERSION",
    "SOURCE_FIELDS",
    "SOURCE_KINDS",
    "SOURCE_KIND_GIT_BLOB",
    "SOURCE_MARKER_RE",
    "STATEMENT_FORBIDDEN_CHARACTER_RE",
    "STATUSES_BY_DOMAIN",
    "SchemaValidationError",
    "SourceRef",
    "TRUST_CLASSES",
    "TRUST_CLASS_AUTHORITATIVE_GIT",
    "assert_integrity",
    "check_statement",
    "find_integrity_issues",
    "validate_repo_path",
]
