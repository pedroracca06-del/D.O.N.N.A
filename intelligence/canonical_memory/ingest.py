"""Deterministic, all-or-nothing Git-mirror ingest for the CM-1 bootstrap.

Given a full commit id and an object reader, the ingest:

1. validates the literal spec (``ingest_spec.validate_spec``);
2. verifies the commit and walks its trees to exactly the eleven allowlisted
   paths, re-hashing every object (``git_objects.GitSnapshot``), and requires
   the PRIME tree to list exactly the seven Markdown files;
3. decodes each blob as strict UTF-8 after BOM/newline normalization and
   refuses control, zero-width, or bidirectional characters anywhere in it;
4. refuses to continue unless the seven PRIME blobs pass
   ``validate_current_prime_package`` (``prime_precondition``);
5. for every literal entity and record spec, requires its anchor lines to occur
   exactly once, consecutively, as whole lines; the record statement *is* that
   excerpt, byte for byte, and is refused if it carries boundary material;
6. binds every record to the commit, its source blob id, its normalized content
   hash, and a primary source link, then runs set-level integrity.

Kind, status, governance class, and authority come only from the spec. Nothing
is inferred from a path, heading, or content. No partial result exists: any
failure raises before an :class:`IngestResult` is built. No clock, environment,
network, database, hydration, or runtime surface is involved.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from intelligence.canonical_memory import git_objects, git_reader, hashing, ingest_spec, prime_precondition, schema
from intelligence.canonical_memory.hashing import CM1Error

MAX_SOURCE_BYTES = 1024 * 1024

#: Same invisible set as statements, but a source file may contain tabs and LF.
SOURCE_FORBIDDEN_CHARACTER_RE = re.compile(
    r"[\x00-\x08\x0b-\x1f\x7f-\x9f"
    + "".join(chr(low) + "-" + chr(high) for low, high in schema.INVISIBLE_CODE_POINT_RANGES)
    + "]"
)

#: Material that may never become a stored statement (gate G0 boundary). The
#: environment pattern covers both guarded activation flags without naming them.
BOUNDARY_PATTERNS: tuple[tuple[str, "re.Pattern[str]"], ...] = (
    ("environment_flag", re.compile(r"\b(?:NOVA|DONNA)_[A-Z0-9_]{2,}\b")),
    (
        "credential_assignment",
        re.compile(r"(?i)\b(?:api[_-]?key|secret|token|password|passphrase|private[_-]?key|access[_-]?key)\b\s*[:=]"),
    ),
    ("private_key_block", re.compile(r"-----BEGIN")),
    ("machine_path", re.compile(r"(?i)(?:\b[a-z]:[\\/]|\\\\[^\\\s]+\\|(?<![\w.])/(?:home|Users|tmp)/|~[\\/])")),
)


class IngestError(CM1Error):
    """A source, anchor, or statement failed the ingest contract."""


@dataclass(frozen=True, slots=True)
class IngestResult:
    """The complete, immutable output of one successful ingest run."""

    spec_version: str
    schema_version: int
    commit_oid: str
    object_format: str
    tree_oid: str
    prime_package_files: tuple[str, ...]
    sources: tuple[schema.SourceRef, ...]
    entities: tuple[schema.EntityRecord, ...]
    records: tuple[schema.MemoryRecord, ...]
    links: tuple[schema.RecordSourceLink, ...]
    result_hash: str

    def __post_init__(self) -> None:
        if self.result_hash != hashing.canonical_hash(self.payload()):
            raise IngestError("RESULT_HASH_MISMATCH", "claimed result_hash does not match the result content")

    def payload(self) -> Mapping[str, Any]:
        return _result_payload({name: getattr(self, name) for name in RESULT_CONTENT_FIELDS})


#: Every IngestResult field except ``result_hash``, which is computed over these.
RESULT_CONTENT_FIELDS: tuple[str, ...] = (
    "spec_version",
    "schema_version",
    "commit_oid",
    "object_format",
    "tree_oid",
    "prime_package_files",
    "sources",
    "entities",
    "records",
    "links",
)


def _result_payload(fields: Mapping[str, Any]) -> Mapping[str, Any]:
    return {
        "commit_oid": fields["commit_oid"],
        "entities": [entity.to_mapping() for entity in fields["entities"]],
        "links": [link.to_mapping() for link in fields["links"]],
        "object_format": fields["object_format"],
        "prime_package_files": list(fields["prime_package_files"]),
        "records": [record.to_mapping() for record in fields["records"]],
        "schema_version": fields["schema_version"],
        "sources": [source.to_mapping() for source in fields["sources"]],
        "spec_version": fields["spec_version"],
        "tree_oid": fields["tree_oid"],
    }


def decode_source(repo_path: str, raw: bytes) -> str:
    """Strict UTF-8 text of a verified blob, or fail."""
    if len(raw) > MAX_SOURCE_BYTES:
        raise IngestError("SOURCE_TOO_LARGE", "source exceeds the bootstrap size bound", subject=repo_path)
    try:
        text = hashing.normalize_bytes(raw).decode("utf-8")
    except UnicodeDecodeError as exc:
        raise IngestError("SOURCE_NOT_UTF8", "source is not valid UTF-8", subject=repo_path) from exc
    if SOURCE_FORBIDDEN_CHARACTER_RE.search(text):
        raise IngestError("SOURCE_CONTROL_CHARACTER", "source contains a control or invisible character", subject=repo_path)
    return text


def find_anchor(text: str, anchor_lines: tuple[str, ...], *, subject: str) -> tuple[int, int]:
    """1-based (first, last) line numbers of the unique whole-line occurrence."""
    lines = text.split("\n")
    width = len(anchor_lines)
    hits = [i for i in range(len(lines) - width + 1) if tuple(lines[i:i + width]) == anchor_lines]
    if not hits:
        raise IngestError("ANCHOR_MISSING", "anchor lines do not occur in the source", subject=subject)
    if len(hits) > 1:
        raise IngestError("ANCHOR_AMBIGUOUS", f"anchor lines occur {len(hits)} times", subject=subject)
    return hits[0] + 1, hits[0] + width


def check_boundary(statement: str, *, subject: str) -> None:
    for name, pattern in BOUNDARY_PATTERNS:
        if pattern.search(statement):
            raise IngestError("BOUNDARY_MATERIAL", f"statement contains {name} material", subject=subject)


def check_prime_listing(entries: tuple[git_objects.TreeEntry, ...]) -> None:
    """The PRIME tree at the commit must hold exactly the seven Markdown files.

    Mirrors the validator's exact-file-set invariant, which it can only see on
    disk: an eighth ``*.md`` in Git would otherwise go unnoticed because the
    ingest reads only allowlisted blobs.
    """
    names = {entry.name for entry in entries if entry.name.casefold().endswith(".md")}
    required = set(ingest_spec.PRIME_PACKAGE_FILE_NAMES)
    if names != required:
        raise prime_precondition.PrimePreconditionError(
            "PRIME_PACKAGE_FILESET",
            f"PRIME tree differs; missing={sorted(required - names)} unexpected={sorted(names - required)}",
        )


def ingest_objects(read_object: git_objects.ObjectReader, commit_oid: str) -> IngestResult:
    """Mirror the allowlisted sources at ``commit_oid``. All or nothing."""
    object_format = git_objects.object_format_of(commit_oid)
    ingest_spec.validate_spec(ingest_spec.ENTITY_SPECS, ingest_spec.RECORD_SPECS)
    paths = tuple(ingest_spec.require_allowed_path(path) for path in ingest_spec.ALLOWED_SOURCE_PATHS)

    snapshot = git_objects.GitSnapshot(read_object, commit_oid)
    blobs = tuple(snapshot.blob(path) for path in paths)
    check_prime_listing(snapshot.list_tree(ingest_spec.PRIME_ROOT))
    by_path = {blob.repo_path: blob for blob in blobs}
    if tuple(sorted(by_path)) != paths:
        raise IngestError("INGEST_SOURCE_SET", "resolved sources differ from the allowlist")
    tree_oids = {blob.tree_oid for blob in blobs}
    if len(tree_oids) != 1:
        raise IngestError("INGEST_SOURCE_SET", "sources resolved from more than one root tree")
    texts = {path: decode_source(path, by_path[path].content) for path in paths}

    prime_files = prime_precondition.validate_prime_blobs(
        {path.rsplit("/", 1)[1]: by_path[path].content for path in ingest_spec.PRIME_SOURCE_PATHS}
    )

    sources = {
        path: schema.SourceRef.build(
            repo_path=path,
            git_commit=commit_oid,
            git_blob_oid=by_path[path].blob_oid,
            content_hash=hashing.content_hash(by_path[path].content),
        )
        for path in paths
    }

    entities = []
    for spec in ingest_spec.ENTITY_SPECS:
        find_anchor(texts[spec.repo_path], spec.anchor_lines, subject=spec.entity_key)
        entities.append(
            schema.EntityRecord(
                entity_key=spec.entity_key,
                entity_type=spec.entity_type,
                display_name=spec.display_name,
                lifecycle=spec.lifecycle,
                attributes={},
            )
        )

    records = []
    links = []
    for spec in ingest_spec.RECORD_SPECS:
        first, last = find_anchor(texts[spec.repo_path], spec.anchor_lines, subject=spec.record_key)
        statement = "\n".join(spec.anchor_lines)
        check_boundary(statement, subject=spec.record_key)
        records.append(
            schema.MemoryRecord.build(
                record_key=spec.record_key,
                version=1,
                domain=spec.domain,
                kind=spec.kind,
                governance_class=spec.governance_class,
                status=spec.status,
                authority=spec.authority,
                subject_entity_key=spec.subject_entity_key,
                statement=statement,
                body={"schema_version": schema.SCHEMA_VERSION, "excerpt_lines": [first, last]},
                confidence=schema.CONFIDENCE_NOT_APPLICABLE,
                confidence_basis=None,
                bound_commit=commit_oid,
                supersedes_version=None,
                proposed_by=ingest_spec.INGEST_ACTOR,
            )
        )
        links.append(
            schema.RecordSourceLink(
                record_key=spec.record_key,
                version=1,
                source_identity=sources[spec.repo_path].source_identity,
                role=schema.ROLE_PRIMARY,
                excerpt_hash=hashing.text_hash(statement),
            )
        )

    ordered_sources = tuple(sources[path] for path in paths)
    ordered_entities = tuple(sorted(entities, key=lambda e: e.entity_key))
    ordered_records = tuple(sorted(records, key=lambda r: (r.record_key, r.version)))
    ordered_links = tuple(sorted(links, key=lambda l: (l.record_key, l.version, l.source_identity, l.role)))
    schema.assert_integrity(ordered_sources, ordered_entities, ordered_records, ordered_links)

    fields: dict[str, Any] = {
        "spec_version": ingest_spec.SPEC_VERSION,
        "schema_version": schema.SCHEMA_VERSION,
        "commit_oid": commit_oid,
        "object_format": object_format,
        "tree_oid": tree_oids.pop(),
        "prime_package_files": tuple(prime_files),
        "sources": ordered_sources,
        "entities": ordered_entities,
        "records": ordered_records,
        "links": ordered_links,
    }
    return IngestResult(**fields, result_hash=hashing.canonical_hash(_result_payload(fields)))


def ingest_repository(repo_root: str | Path, commit_oid: str) -> IngestResult:
    """Run :func:`ingest_objects` over the local object store via read-only cat-file."""
    git_objects.object_format_of(commit_oid)
    reader = git_reader.GitCatFileReader(repo_root)
    return ingest_objects(reader.read_object, commit_oid)


__all__ = [
    "BOUNDARY_PATTERNS",
    "RESULT_CONTENT_FIELDS",
    "check_prime_listing",
    "IngestError",
    "IngestResult",
    "MAX_SOURCE_BYTES",
    "SOURCE_FORBIDDEN_CHARACTER_RE",
    "check_boundary",
    "decode_source",
    "find_anchor",
    "ingest_objects",
    "ingest_repository",
]
