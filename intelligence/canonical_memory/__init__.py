"""NOVA Canonical Memory CM-1 — read-only Git-mirroring bootstrap (schema v1).

A standard-library-only package that mirrors a fixed, literal set of
Git-authoritative statements into immutable, provenance-bound records. It is the
CM-1 increment described in ``docs/canonical-memory/CM1_SCHEMA_AND_INGEST.md``
and ``docs/canonical-memory/MIGRATION_AND_VALIDATION_GATES.md`` §5.

Modules
-------
``hashing``             BOM/newline-normalized content hash, canonical JSON,
                        stable refs, source identities
``schema``              closed enums; frozen ``SourceRef``, ``EntityRecord``,
                        ``MemoryRecord``, ``RecordSourceLink``; set integrity
``git_objects``         pure SHA-1/SHA-256 object verification and verified
                        commit → tree → blob traversal
``ingest_spec``         the exact eleven-path allowlist and literal specs
``prime_precondition``  ``validate_current_prime_package`` over the pinned blobs
``git_reader``          argument-array, read-only ``git cat-file --batch`` only
``ingest``              deterministic, all-or-nothing extraction and hashing

Hard boundaries. This package does not, and must not be extended to:

* open, create, or write any database, or define any status-transition API;
* hydrate an agent, or wire into the Assistant or any live surface;
* apply anything to Obsidian, or write repository or ``data/`` runtime state;
* infer a kind, status, class, or authority from a path, heading, or content;
* hold any authority other than ``git`` — Git remains the only decider;
* read or assign any environment value, the wall clock, or the network;
* touch execution, broker, risk-runtime state, or either guarded flag.

Locked universe: exactly three active PRIME execution models (Strict OTE, 10AM
Key Level Open, ORB). FVG is confluence only. PROS is superseded lineage.
Evidence never changes a rule.
"""

from __future__ import annotations

from intelligence.canonical_memory.git_objects import (
    GitObjectError,
    TreeEntry,
    VerifiedBlob,
    hash_object,
    object_format_of,
    parse_commit_tree,
    parse_tree,
    resolve_blobs,
    verify_object,
)
from intelligence.canonical_memory.git_reader import GitCatFileReader, GitReaderError
from intelligence.canonical_memory.hashing import (
    CM1Error,
    HashingError,
    canonical_hash,
    canonical_json,
    content_hash,
    normalize_bytes,
    source_identity,
    stable_ref,
    text_hash,
)
from intelligence.canonical_memory.ingest import (
    IngestError,
    IngestResult,
    ingest_objects,
    ingest_repository,
)
from intelligence.canonical_memory.ingest_spec import (
    ALLOWED_SOURCE_PATHS,
    ENTITY_SPECS,
    RECORD_SPECS,
    SPEC_VERSION,
    EntitySpec,
    IngestSpecError,
    RecordSpec,
    require_allowed_path,
    validate_spec,
)
from intelligence.canonical_memory.prime_precondition import (
    PrimePreconditionError,
    validate_prime_blobs,
)
from intelligence.canonical_memory.schema import (
    AUTHORITIES,
    SCHEMA_VERSION,
    EntityRecord,
    IntegrityIssue,
    MemoryRecord,
    RecordSourceLink,
    SchemaValidationError,
    SourceRef,
    assert_integrity,
    find_integrity_issues,
)

#: Restated here so an importer sees it without opening a document.
AUTHORIZATION_NOTICE = (
    "Git-mirroring infrastructure only. Git remains the only authority; nothing "
    "here is canonical, hydrates an agent, writes a database, or changes live "
    "behavior. Nothing here grants runtime authority or authorizes autonomous "
    "or funded trading. Execution remains disabled."
)

__all__ = [
    "ALLOWED_SOURCE_PATHS",
    "AUTHORITIES",
    "AUTHORIZATION_NOTICE",
    "CM1Error",
    "ENTITY_SPECS",
    "EntityRecord",
    "EntitySpec",
    "GitCatFileReader",
    "GitObjectError",
    "GitReaderError",
    "HashingError",
    "IngestError",
    "IngestResult",
    "IngestSpecError",
    "IntegrityIssue",
    "MemoryRecord",
    "PrimePreconditionError",
    "RECORD_SPECS",
    "RecordSourceLink",
    "RecordSpec",
    "SCHEMA_VERSION",
    "SPEC_VERSION",
    "SchemaValidationError",
    "SourceRef",
    "TreeEntry",
    "VerifiedBlob",
    "assert_integrity",
    "canonical_hash",
    "canonical_json",
    "content_hash",
    "find_integrity_issues",
    "hash_object",
    "ingest_objects",
    "ingest_repository",
    "normalize_bytes",
    "object_format_of",
    "parse_commit_tree",
    "parse_tree",
    "require_allowed_path",
    "resolve_blobs",
    "source_identity",
    "stable_ref",
    "text_hash",
    "validate_prime_blobs",
    "validate_spec",
    "verify_object",
]
