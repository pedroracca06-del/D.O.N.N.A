"""Read-only Git object reader for CM-1: ``git cat-file --batch`` and nothing else.

BOUNDARY:

* The only subcommand ever constructed is ``cat-file``; the argument vector is
  fixed by :func:`build_cat_file_argv` and never accepts caller arguments.
* An argument array is always passed; a shell is never involved.
* Only a full 40- or 64-hex object id is ever sent on stdin — never a ref name,
  ``HEAD``, a revision expression, or an abbreviated id.
* ``--no-replace-objects`` disables replace refs and ``--no-optional-locks``
  keeps the read from refreshing the index. Neither is relied on for trust:
  every returned object is re-hashed by ``git_objects`` before use, so a
  redirected or replaced object store can cause a refusal, never a forgery.
* No environment is read or assigned here. No fetch, no network, no write.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from intelligence.canonical_memory import git_objects
from intelligence.canonical_memory.hashing import CM1Error

GIT_EXECUTABLE = "git"
GIT_SUBCOMMAND = "cat-file"
GIT_TIMEOUT_SECONDS = 30
_MAX_HEADER_BYTES = 256


class GitReaderError(CM1Error):
    """Git could not be run, or its batch output was not a single clean object."""


def build_cat_file_argv(repo_root: str) -> list[str]:
    """The one argument vector this module runs."""
    return [
        GIT_EXECUTABLE,
        "--no-optional-locks",
        "--no-replace-objects",
        "-C",
        repo_root,
        GIT_SUBCOMMAND,
        "--batch",
    ]


def parse_batch_output(oid: str, stdout: Any) -> tuple[str, bytes]:
    """Parse exactly one ``cat-file --batch`` response for ``oid``."""
    if not isinstance(stdout, (bytes, bytearray)):
        raise GitReaderError("BATCH_MALFORMED", "batch output must be bytes", subject=oid)
    data = bytes(stdout)
    newline = data.find(b"\n")
    if newline < 0 or newline > _MAX_HEADER_BYTES:
        raise GitReaderError("BATCH_MALFORMED", "batch header is missing or too long", subject=oid)
    try:
        parts = data[:newline].decode("ascii").split(" ")
    except UnicodeDecodeError as exc:
        raise GitReaderError("BATCH_MALFORMED", "batch header is not ASCII", subject=oid) from exc
    if len(parts) == 2 and parts[0] == oid and parts[1] == "missing":
        raise GitReaderError("OBJECT_MISSING", "object is not present in the repository", subject=oid)
    if len(parts) != 3:
        raise GitReaderError("BATCH_MALFORMED", "batch header does not name one object", subject=oid)
    got_oid, obj_type, size_text = parts
    if got_oid != oid:
        raise GitReaderError("BATCH_OID_MISMATCH", "git answered for a different object", subject=oid)
    if not size_text or not all("0" <= ch <= "9" for ch in size_text):
        raise GitReaderError("BATCH_MALFORMED", "batch size is not a decimal integer", subject=oid)
    size = int(size_text)
    if size > git_objects.MAX_OBJECT_BYTES:
        raise GitReaderError("OBJECT_TOO_LARGE", "object exceeds the bootstrap size bound", subject=oid)
    start = newline + 1
    body = data[start:start + size]
    if len(body) != size or data[start + size:] != b"\n":
        raise GitReaderError("BATCH_MALFORMED", "batch body length or terminator is wrong", subject=oid)
    return obj_type, body


class GitCatFileReader:
    """``read_object(oid) -> (type, body)`` backed by one read-only cat-file call per object."""

    __slots__ = ("_repo_root", "_timeout")

    def __init__(self, repo_root: str | Path, *, timeout: int = GIT_TIMEOUT_SECONDS) -> None:
        if isinstance(repo_root, Path):
            root = str(repo_root)
        elif isinstance(repo_root, str):
            root = repo_root
        else:
            raise GitReaderError("REPO_ROOT", "repo_root must be a str or Path")
        if not root or "\x00" in root or "\n" in root or "\r" in root:
            raise GitReaderError("REPO_ROOT", "repo_root must be a non-empty single-line path")
        if isinstance(timeout, bool) or not isinstance(timeout, int) or timeout < 1:
            raise GitReaderError("GIT_TIMEOUT", "timeout must be a positive integer number of seconds")
        self._repo_root = root
        self._timeout = timeout

    def read_object(self, oid: str) -> tuple[str, bytes]:
        git_objects.object_format_of(oid)
        argv = build_cat_file_argv(self._repo_root)
        try:
            proc = subprocess.run(
                argv,
                input=(oid + "\n").encode("ascii"),
                capture_output=True,
                timeout=self._timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise GitReaderError("GIT_TIMEOUT", "git cat-file exceeded its timeout", subject=oid) from exc
        except OSError as exc:
            raise GitReaderError("GIT_UNAVAILABLE", "git could not be executed", subject=oid) from exc
        if proc.returncode != 0:
            raise GitReaderError("GIT_FAILED", f"git cat-file exited with status {proc.returncode}", subject=oid)
        return parse_batch_output(oid, proc.stdout)


__all__ = [
    "GIT_EXECUTABLE",
    "GIT_SUBCOMMAND",
    "GIT_TIMEOUT_SECONDS",
    "GitCatFileReader",
    "GitReaderError",
    "build_cat_file_argv",
    "parse_batch_output",
]
