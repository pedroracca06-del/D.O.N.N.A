"""Deterministic hashing and identity for the CM-1 Git-mirror bootstrap.

Lowest layer of the package: standard library only, no I/O, no clock, no
environment. Every other module builds on these functions, so two machines with
different checkouts (CRLF or LF, with or without a UTF-8 BOM) derive the same
content hash, the same stable reference, and the same source identity.

Conventions (docs/canonical-memory/ARCHITECTURE_V1.md §4 C4, §7.2):

* content hash — SHA-256 over bytes with a leading UTF-8 BOM removed and CRLF/CR
  folded to LF, exactly as ``tools/cowork/obsidian_sync_planner.py`` does;
* stable reference — ``nova-`` + first 16 hex of SHA-256(kind NUL locator);
* source identity — SHA-256 over the canonical JSON of
  (source_kind, stable_ref, git_commit, content_hash), absent values encoded
  explicitly as JSON null;
* canonical JSON — sorted keys, no insignificant whitespace, UTF-8, and only
  strings, integers, booleans, null, sequences, and string-keyed mappings. A
  float is refused, because its text form is not a stable identity.

Nothing here decides what is true. A hash names bytes; it grants nothing.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping

_BOM = b"\xef\xbb\xbf"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class CM1Error(ValueError):
    """Base class for every fail-closed CM-1 rejection. ``code`` is stable."""

    def __init__(self, code: str, message: str, *, subject: str | None = None) -> None:
        parts = [f"[{code}]"]
        if subject:
            parts.append(f"subject={subject!r}")
        parts.append(message)
        super().__init__(" ".join(parts))
        self.code = code
        self.subject = subject


class HashingError(CM1Error):
    """Input could not be hashed or serialized deterministically."""


def sha256_hex(data: bytes) -> str:
    if not isinstance(data, (bytes, bytearray)):
        raise HashingError("HASH_INPUT_TYPE", f"expected bytes, got {type(data).__name__}")
    return hashlib.sha256(bytes(data)).hexdigest()


def is_sha256_hex(value: Any) -> bool:
    return isinstance(value, str) and _SHA256_RE.match(value) is not None


def normalize_bytes(raw: bytes) -> bytes:
    """Drop one leading UTF-8 BOM and fold CRLF/CR to LF."""
    if not isinstance(raw, (bytes, bytearray)):
        raise HashingError("HASH_INPUT_TYPE", f"expected bytes, got {type(raw).__name__}")
    data = bytes(raw)
    if data.startswith(_BOM):
        data = data[len(_BOM):]
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def content_hash(raw: bytes) -> str:
    """Normalized SHA-256 of source bytes (planner-compatible)."""
    return sha256_hex(normalize_bytes(raw))


def text_hash(text: str) -> str:
    """Normalized SHA-256 of text: UTF-8 encoded, then normalized like bytes."""
    if not isinstance(text, str):
        raise HashingError("HASH_INPUT_TYPE", f"expected str, got {type(text).__name__}")
    return content_hash(text.encode("utf-8"))


def _check_json_value(value: Any, where: str) -> None:
    if value is None or isinstance(value, (str, bool)):
        return
    if isinstance(value, int):
        return
    if isinstance(value, float):
        raise HashingError("CANONICAL_JSON_TYPE", f"float is not a stable identity at {where}")
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _check_json_value(item, f"{where}[{index}]")
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                raise HashingError("CANONICAL_JSON_TYPE", f"non-string key at {where}")
            _check_json_value(item, f"{where}.{key}")
        return
    raise HashingError(
        "CANONICAL_JSON_TYPE", f"unsupported type {type(value).__name__} at {where}"
    )


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    return value


def canonical_json(value: Any) -> bytes:
    """Canonical UTF-8 JSON bytes for hashing. Refuses floats and unknown types."""
    _check_json_value(value, "$")
    return json.dumps(
        _plain(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def canonical_hash(value: Any) -> str:
    return sha256_hex(canonical_json(value))


def stable_ref(source_kind: str, locator: str) -> str:
    """``nova-<16 hex>`` over ``source_kind NUL locator``. Recomputed, never trusted."""
    for name, value in (("source_kind", source_kind), ("locator", locator)):
        if not isinstance(value, str) or not value or "\x00" in value:
            raise HashingError("STABLE_REF_INPUT", f"{name} must be a non-empty string without NUL")
    payload = f"{source_kind}\x00{locator}".encode("utf-8")
    return "nova-" + hashlib.sha256(payload).hexdigest()[:16]


def source_identity(
    source_kind: str,
    stable_reference: str,
    git_commit: str | None,
    source_content_hash: str | None,
) -> str:
    """Natural identity of a source row. Absent values are explicit nulls."""
    return canonical_hash(
        {
            "content_hash": source_content_hash,
            "git_commit": git_commit,
            "source_kind": source_kind,
            "stable_ref": stable_reference,
        }
    )


__all__ = [
    "CM1Error",
    "HashingError",
    "canonical_hash",
    "canonical_json",
    "content_hash",
    "is_sha256_hex",
    "normalize_bytes",
    "sha256_hex",
    "source_identity",
    "stable_ref",
    "text_hash",
]
