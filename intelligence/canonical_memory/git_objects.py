"""Pure Git object verification and verified tree/blob traversal for CM-1.

Standard library only. No subprocess, no I/O, no clock, no environment. Bytes
come from a caller-supplied ``read_object(oid) -> (type, body)`` callable; every
object is re-hashed here before it is trusted, so a reader that returns the
wrong bytes (or a replaced, forged, or truncated object) is refused rather than
believed.

Verification rule: ``hash("<type> <size>\\0" + body) == oid``, using SHA-1 for a
40-hex id and SHA-256 for a 64-hex id. A traversal never mixes formats.

Traversal starts at a **full commit id**, reads its tree, and walks exact path
components. Only a regular-file blob (mode ``100644``) is accepted as a source;
a symlink, gitlink/submodule, executable, or directory is refused. Tree entries
are parsed strictly: known modes only, no empty/dot/``.git`` names, no
duplicates, canonical Git ordering, and no case-folded twin of a looked-up name.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Callable, Iterable

from intelligence.canonical_memory.hashing import CM1Error

OBJECT_FORMAT_SHA1 = "sha1"
OBJECT_FORMAT_SHA256 = "sha256"
_HEX_LENGTH = {OBJECT_FORMAT_SHA1: 40, OBJECT_FORMAT_SHA256: 64}
_RAW_LENGTH = {OBJECT_FORMAT_SHA1: 20, OBJECT_FORMAT_SHA256: 32}

OBJECT_TYPES: frozenset[str] = frozenset({"blob", "tree", "commit", "tag"})

MODE_BLOB = "100644"
MODE_EXECUTABLE = "100755"
MODE_TREE = "40000"
MODE_SYMLINK = "120000"
MODE_GITLINK = "160000"
TREE_MODES: frozenset[str] = frozenset({MODE_BLOB, MODE_EXECUTABLE, MODE_TREE, MODE_SYMLINK, MODE_GITLINK})

MAX_OBJECT_BYTES = 4 * 1024 * 1024

_OID_RE = re.compile(r"^[0-9a-f]{40}$|^[0-9a-f]{64}$")

ObjectReader = Callable[[str], "tuple[str, bytes]"]


class GitObjectError(CM1Error):
    """A Git object, tree entry, or traversal failed verification."""


@dataclass(frozen=True, slots=True)
class TreeEntry:
    mode: str
    name: str
    oid: str


@dataclass(frozen=True, slots=True)
class VerifiedBlob:
    repo_path: str
    commit_oid: str
    tree_oid: str
    blob_oid: str
    object_format: str
    content: bytes


def object_format_of(oid: object) -> str:
    """Return ``sha1`` or ``sha256`` for a full lowercase hex id, or fail."""
    if not isinstance(oid, str) or not _OID_RE.match(oid):
        raise GitObjectError("OID_INVALID", "expected a full 40- or 64-character lowercase hex object id")
    return OBJECT_FORMAT_SHA1 if len(oid) == 40 else OBJECT_FORMAT_SHA256


def hash_object(obj_type: str, body: bytes, object_format: str) -> str:
    """Git object id of ``body`` as ``obj_type`` in ``object_format``."""
    if obj_type not in OBJECT_TYPES:
        raise GitObjectError("OBJECT_TYPE_INVALID", f"unknown object type {obj_type!r}")
    if not isinstance(body, (bytes, bytearray)):
        raise GitObjectError("OBJECT_BODY_TYPE", "object body must be bytes")
    if object_format not in _HEX_LENGTH:
        raise GitObjectError("OBJECT_FORMAT", f"unknown object format {object_format!r}")
    data = f"{obj_type} {len(body)}\x00".encode("ascii") + bytes(body)
    digest = hashlib.sha1 if object_format == OBJECT_FORMAT_SHA1 else hashlib.sha256
    return digest(data).hexdigest()


def verify_object(oid: str, claimed_type: object, body: object, expected_type: str) -> bytes:
    """Return ``body`` only if it really is the ``expected_type`` object named ``oid``."""
    object_format = object_format_of(oid)
    if not isinstance(claimed_type, str) or claimed_type not in OBJECT_TYPES:
        raise GitObjectError("OBJECT_TYPE_INVALID", f"reader returned unknown type {claimed_type!r}", subject=oid)
    if claimed_type != expected_type:
        raise GitObjectError(
            "OBJECT_TYPE_MISMATCH", f"expected {expected_type}, reader returned {claimed_type}", subject=oid
        )
    if not isinstance(body, (bytes, bytearray)):
        raise GitObjectError("OBJECT_BODY_TYPE", "reader returned a non-bytes body", subject=oid)
    if len(body) > MAX_OBJECT_BYTES:
        raise GitObjectError("OBJECT_TOO_LARGE", "object exceeds the bootstrap size bound", subject=oid)
    if hash_object(expected_type, bytes(body), object_format) != oid:
        raise GitObjectError("OBJECT_HASH_MISMATCH", "object bytes do not hash to the requested id", subject=oid)
    return bytes(body)


def parse_commit_tree(body: bytes, object_format: str) -> str:
    """The root tree id of a verified commit body. Only the first header is read."""
    end = body.find(b"\n")
    if not body.startswith(b"tree ") or end < 0:
        raise GitObjectError("COMMIT_MALFORMED", "commit does not begin with a tree header")
    try:
        tree_oid = body[5:end].decode("ascii")
    except UnicodeDecodeError as exc:
        raise GitObjectError("COMMIT_MALFORMED", "commit tree header is not ASCII") from exc
    if not _OID_RE.match(tree_oid) or len(tree_oid) != _HEX_LENGTH[object_format]:
        raise GitObjectError("COMMIT_MALFORMED", "commit tree id is not a full id of the commit's format")
    return tree_oid


def _sort_key(entry: TreeEntry) -> bytes:
    name = entry.name.encode("utf-8")
    return name + b"/" if entry.mode == MODE_TREE else name


def _check_entry_name(raw: bytes) -> str:
    try:
        name = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise GitObjectError("TREE_ENTRY_NAME", "tree entry name is not UTF-8") from exc
    if name in ("", ".", "..") or "/" in name or name.casefold() == ".git":
        raise GitObjectError("TREE_ENTRY_NAME", f"tree entry name is not allowed: {name!r}")
    return name


def parse_tree(body: bytes, object_format: str) -> tuple[TreeEntry, ...]:
    """Strictly parse a verified tree body into entries."""
    raw_length = _RAW_LENGTH[object_format]
    entries: list[TreeEntry] = []
    names: set[str] = set()
    pos = 0
    size = len(body)
    while pos < size:
        space = body.find(b" ", pos)
        if space < 0:
            raise GitObjectError("TREE_MALFORMED", "tree entry has no mode separator")
        nul = body.find(b"\x00", space + 1)
        if nul < 0:
            raise GitObjectError("TREE_MALFORMED", "tree entry has no name terminator")
        oid_end = nul + 1 + raw_length
        if oid_end > size:
            raise GitObjectError("TREE_MALFORMED", "tree entry is truncated")
        try:
            mode = body[pos:space].decode("ascii")
        except UnicodeDecodeError as exc:
            raise GitObjectError("TREE_MODE_INVALID", "tree entry mode is not ASCII") from exc
        if mode not in TREE_MODES:
            raise GitObjectError("TREE_MODE_INVALID", f"tree entry mode {mode!r} is not allowed")
        name = _check_entry_name(body[space + 1:nul])
        if name in names:
            raise GitObjectError("TREE_DUPLICATE_ENTRY", f"tree lists {name!r} more than once")
        names.add(name)
        entry = TreeEntry(mode=mode, name=name, oid=body[nul + 1:oid_end].hex())
        if entries and _sort_key(entries[-1]) >= _sort_key(entry):
            raise GitObjectError("TREE_NOT_SORTED", "tree entries are not in canonical Git order")
        entries.append(entry)
        pos = oid_end
    return tuple(entries)


def encode_tree(entries: Iterable[TreeEntry]) -> bytes:
    """Serialize entries in canonical order. Pure helper for fixtures and checks."""
    ordered = sorted(entries, key=_sort_key)
    return b"".join(
        f"{entry.mode} {entry.name}".encode("utf-8") + b"\x00" + bytes.fromhex(entry.oid) for entry in ordered
    )


def _read(read_object: ObjectReader, oid: str, expected_type: str) -> bytes:
    result = read_object(oid)
    if not isinstance(result, tuple) or len(result) != 2:
        raise GitObjectError("OBJECT_READER_RESULT", "reader must return (type, body)", subject=oid)
    return verify_object(oid, result[0], result[1], expected_type)


class GitSnapshot:
    """A verified, read-only view of one commit. Each tree is read at most once."""

    __slots__ = ("_read_object", "_trees", "commit_oid", "object_format", "tree_oid")

    def __init__(self, read_object: ObjectReader, commit_oid: str) -> None:
        self.object_format = object_format_of(commit_oid)
        self.commit_oid = commit_oid
        self._read_object = read_object
        self._trees: dict[str, tuple[TreeEntry, ...]] = {}
        self.tree_oid = parse_commit_tree(_read(read_object, commit_oid, "commit"), self.object_format)

    def entries_of(self, tree_oid: str) -> tuple[TreeEntry, ...]:
        if tree_oid not in self._trees:
            self._trees[tree_oid] = parse_tree(_read(self._read_object, tree_oid, "tree"), self.object_format)
        return self._trees[tree_oid]

    def lookup(self, repo_path: str) -> TreeEntry:
        """The entry at an exact path. Intermediates must be real trees."""
        if not isinstance(repo_path, str) or not repo_path:
            raise GitObjectError("TREE_PATH_INVALID", "path must be a non-empty string")
        components = repo_path.split("/")
        if any(part in ("", ".", "..") for part in components):
            raise GitObjectError("TREE_PATH_INVALID", "path has an empty or dot component", subject=repo_path)
        current = self.tree_oid
        entry: TreeEntry | None = None
        for index, part in enumerate(components):
            entries = self.entries_of(current)
            matches = [item for item in entries if item.name == part]
            if not matches:
                raise GitObjectError("TREE_PATH_MISSING", "path component not found", subject=repo_path)
            folded = [item for item in entries if item.name.casefold() == part.casefold()]
            if len(folded) != 1:
                raise GitObjectError("TREE_CASE_COLLISION", "path component has a case-folded twin", subject=repo_path)
            entry = matches[0]
            if index < len(components) - 1:
                if entry.mode != MODE_TREE:
                    raise GitObjectError("TREE_PATH_NOT_TREE", "intermediate component is not a tree", subject=repo_path)
                current = entry.oid
        assert entry is not None
        return entry

    def list_tree(self, repo_path: str) -> tuple[TreeEntry, ...]:
        """Entries of the tree at ``repo_path`` (names and modes only; no blob is read)."""
        entry = self.lookup(repo_path)
        if entry.mode != MODE_TREE:
            raise GitObjectError("TREE_PATH_NOT_TREE", "path is not a tree", subject=repo_path)
        return self.entries_of(entry.oid)

    def blob(self, repo_path: str) -> VerifiedBlob:
        """The verified regular-file blob at ``repo_path``."""
        entry = self.lookup(repo_path)
        if entry.mode != MODE_BLOB:
            raise GitObjectError(
                "TREE_ENTRY_MODE", f"source must be a regular file (100644), got {entry.mode}", subject=repo_path
            )
        return VerifiedBlob(
            repo_path=repo_path,
            commit_oid=self.commit_oid,
            tree_oid=self.tree_oid,
            blob_oid=entry.oid,
            object_format=self.object_format,
            content=_read(self._read_object, entry.oid, "blob"),
        )


def resolve_blobs(read_object: ObjectReader, commit_oid: str, repo_paths: Iterable[str]) -> tuple[VerifiedBlob, ...]:
    """Verify ``commit_oid`` and return each path's regular-file blob, in order.

    All or nothing: the first failure raises and nothing is returned.
    """
    snapshot = GitSnapshot(read_object, commit_oid)
    return tuple(snapshot.blob(repo_path) for repo_path in repo_paths)


__all__ = [
    "GitObjectError",
    "GitSnapshot",
    "MAX_OBJECT_BYTES",
    "MODE_BLOB",
    "MODE_EXECUTABLE",
    "MODE_GITLINK",
    "MODE_SYMLINK",
    "MODE_TREE",
    "OBJECT_FORMAT_SHA1",
    "OBJECT_FORMAT_SHA256",
    "OBJECT_TYPES",
    "ObjectReader",
    "TREE_MODES",
    "TreeEntry",
    "VerifiedBlob",
    "encode_tree",
    "hash_object",
    "object_format_of",
    "parse_commit_tree",
    "parse_tree",
    "resolve_blobs",
    "verify_object",
]
