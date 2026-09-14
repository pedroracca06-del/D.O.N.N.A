"""CURRENT PRIME package precondition for the CM-1 ingest.

The ingest refuses to mirror anything unless the seven PRIME blobs, exactly as
read from the pinned commit, satisfy ``validate_current_prime_package`` — the
same fail-closed validator the live Assistant path already uses. The validator
reads a directory, so the verified blob bytes (BOM-stripped, LF-normalized) are
written into a private ``tempfile.TemporaryDirectory`` that is removed when the
check ends. This is the only write in the package; it never touches the
repository, the working tree, or ``data/``.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Mapping

from intelligence.canonical_memory import hashing
from intelligence.canonical_memory.hashing import CM1Error
from intelligence.canonical_memory.ingest_spec import PRIME_PACKAGE_FILE_NAMES
from intelligence.current_knowledge import (
    CurrentKnowledgeIntegrityError,
    validate_current_prime_package,
)

_REQUIRED: frozenset[str] = frozenset(PRIME_PACKAGE_FILE_NAMES)


class PrimePreconditionError(CM1Error):
    """The PRIME package at the pinned commit is incomplete or invalid."""


def validate_prime_blobs(blobs: Mapping[str, bytes]) -> tuple[str, ...]:
    """Validate the seven PRIME blobs, keyed by file name. All or nothing."""
    if not isinstance(blobs, Mapping):
        raise PrimePreconditionError("PRIME_PACKAGE_TYPE", "blobs must be a mapping of file name to bytes")
    names = set(blobs)
    if names != _REQUIRED:
        missing = sorted(_REQUIRED - names)
        unexpected = sorted(repr(name) for name in names - _REQUIRED)
        raise PrimePreconditionError(
            "PRIME_PACKAGE_FILESET", f"PRIME file set differs; missing={missing} unexpected={unexpected}"
        )
    normalized: dict[str, bytes] = {}
    for name in sorted(_REQUIRED):
        raw = blobs[name]
        if not isinstance(raw, (bytes, bytearray)):
            raise PrimePreconditionError("PRIME_PACKAGE_TYPE", "blob content must be bytes", subject=name)
        data = hashing.normalize_bytes(raw)
        try:
            data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise PrimePreconditionError("PRIME_PACKAGE_ENCODING", "blob is not UTF-8", subject=name) from exc
        normalized[name] = data

    with tempfile.TemporaryDirectory(prefix="cm1-prime-") as scratch:
        root = Path(scratch)
        for name in sorted(normalized):
            (root / name).write_bytes(normalized[name])
        try:
            return validate_current_prime_package(root)
        except CurrentKnowledgeIntegrityError as exc:
            raise PrimePreconditionError("PRIME_PACKAGE_INVALID", str(exc)) from exc


__all__ = ["PrimePreconditionError", "validate_prime_blobs"]
