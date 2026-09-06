#!/usr/bin/env python
"""codex_implementation_runner.py -- start Codex once to EDIT files, contained.

This is a separate component from `codex_review_runner.py`. The read-only
reviewer is unchanged and still the only path used for review; nothing here
replaces it, and the two share the primitives that were already reviewed
(executable resolution, environment minimisation, stream sanitisation,
one-shot invocation) rather than forking them.

What makes the writes safe is the operating system, in this order:

  L1  The child runs under `-s workspace-write` rooted at ONE assigned
      worktree. Everything that matters is outside that root and therefore
      unwritable: provider credentials, the shared session registry, the
      shared relay mailbox, every other worktree, and -- because a linked
      worktree's `.git` is a pointer FILE whose target lives elsewhere -- the
      real git directory. The model cannot rewrite history, install a hook,
      move a ref, or stage anything.

  L2  The child does not run in the worktree. It runs in a STAGING workspace
      built to contain the assigned paths and NOTHING else. A protected file
      cannot be written, replaced, deleted, or have its permissions changed,
      because it is not present -- and L1 denies reaching outside the root to
      find the original. Assigned-path protection is therefore enforced by
      absence plus the sandbox root, not by a file attribute.

      An earlier version used the read-only attribute for this. It was not a
      boundary: a same-user process clears the attribute and proceeds, and a
      Windows DACL is no better because the owner keeps implicit WRITE_DAC.
      That is why staging exists. The attribute pass survives only as defence
      in depth over the real worktree while the result is applied back, and it
      now fails closed instead of skipping what it cannot protect.

  L3  The coordinator applies only assigned paths back, diffs the worktree, and
      reverts anything outside the assignment.

L3 alone would not be containment, and is not treated as such. It bounds task
paths after the operating system has already contained the run.

The model never commits, never pushes, and never sees git metadata. The
coordinator validates and commits. A verdict, a diff, and a task outcome are
all opinions and evidence offered to a human; none of them authorises anything.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import datetime, timezone

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import codex_relay as cr                      # noqa: E402
import codex_review_runner as rr              # noqa: E402
import evidence_formatter as ef               # noqa: E402
import session_registry as sr                 # noqa: E402
import staleness_guard as sg                  # noqa: E402

SCHEMA_VERSION = 1
POLICY_FILENAME = "codex_implementation_policy.json"

EXIT_OK = 0
EXIT_INVALID = 2
EXIT_LIMIT = 3
EXIT_STOPPED = 4

OPERATIONS = ("validate-policy", "inspect", "submit-task",
              "implement-once", "settle-claim")

# The same refusal surface as the reviewer: an action word is not an operation.
FORBIDDEN_VERBS = rr.FORBIDDEN_VERBS

SANDBOX_MODE = "workspace-write"
SANDBOX_FLAG = "-s"

# Never passed. `--add-dir` would widen the writable root, which is the whole
# containment story; the rest disable the sandbox or the approval policy.
FORBIDDEN_FLAGS = ("--add-dir", "--approve-for-me",
                   "--dangerously-bypass-approvals-and-sandbox",
                   "--dangerously-bypass-hook-trust",
                   "--skip-git-repo-check", "--full-auto", "--yolo")

TASK_TYPE = "implementation_task"
TASK_FIELDS = (
    "schema_version", "entry_id", "sequence", "previous_sha256", "created_at",
    "message_type", "task_id", "phase", "repository_identity",
    "worktree_identity", "branch", "head", "registry_revision",
    "assigned_paths", "instruction", "acceptance", "assigned_by",
)

CLAIM_TYPE = "implementation_attempt_claim"

OUTCOME_TYPE = "implementation_outcome"
OUTCOME_CATEGORIES = (
    "completed",             # the child edited within scope and tests were run
    "no_change",             # the child ran and changed nothing
    "out_of_scope",          # the child wrote outside the assigned task paths
    "timeout",
    "nonzero_exit",
    "missing_output",
    "oversized_output",
    "malformed_output",
    "protected_path_touched",
    "state_changed",
    "internal_error",
    # Only a human settles this one, through `settle-claim`. It exists so a
    # crashed run can be closed out honestly instead of being re-run.
    "abandoned_after_crash",
)


class ImplementationError(Exception):
    """A refusal that is the caller's to fix."""


def _bad(msg):
    raise ImplementationError(msg)


def _chk(cid, label, status, evidence):
    return {"id": cid, "label": label, "status": status, "evidence": evidence}


# --------------------------------------------------------------------------
# Policy
# --------------------------------------------------------------------------

def load_policy(path=None):
    path = path or os.path.join(_HERE, POLICY_FILENAME)
    return cr._read_doc(path, {"max_envelope_bytes": 262144,
                               "max_depth": 24, "max_paths": 512,
                               "max_string_chars": 8192}, "implementation policy")


def validate_policy(policy):
    """The contract is fixed in the file and re-checked here, never inferred."""
    problems = []
    if policy.get("schema_version") != SCHEMA_VERSION:
        problems.append("unsupported policy schema_version")
    if tuple(policy.get("operations") or ()) != OPERATIONS:
        problems.append("the policy operations do not match this runner")

    flags = policy.get("fixed_flags") or {}
    if flags.get("sandbox") != SANDBOX_MODE:
        problems.append("the sandbox mode must be %r" % SANDBOX_MODE)
    if flags.get("ask_for_approval") != "never":
        problems.append("approval must be never")
    if flags.get("windows_sandbox") != rr.WINDOWS_SANDBOX_BACKEND:
        problems.append("the Windows sandbox backend is not the elevated one")
    if not flags.get("ignore_user_config"):
        problems.append("the child must ignore user configuration")
    if not flags.get("output_schema_required"):
        problems.append("a typed output schema is required")

    for name in FORBIDDEN_FLAGS:
        if name not in (policy.get("forbidden_flags") or []):
            problems.append("the policy does not forbid %s" % name)

    contract = policy.get("contract") or {}
    for key, want in (("model_may_commit", False), ("model_may_push", False),
                      ("model_reaches_git_metadata", False),
                      ("coordinator_commits", True), ("retry", False),
                      ("attempt_consumed_on_spawn", True),
                      ("attempt_claimed_before_spawn", True),
                      ("concurrent_runs", False),
                      ("read_only_reviewer_preserved", True)):
        if contract.get(key) is not want:
            problems.append("contract.%s must be %r" % (key, want))

    containment = policy.get("containment") or {}
    layers = {layer.get("id") for layer in containment.get("layers") or []}
    if layers != {"L1", "L2", "L3"}:
        problems.append("the policy must describe exactly containment layers "
                        "L1, L2 and L3")
    kinds = {layer.get("id"): layer.get("kind")
             for layer in containment.get("layers") or []}
    if kinds.get("L1") != "operating-system" or kinds.get("L2") != "operating-system":
        problems.append("L1 and L2 must be operating-system controls; a "
                        "coordinator check is not containment")
    if not containment.get("always_protected_paths"):
        problems.append("the policy names no always-protected path")

    limits = policy.get("limits") or {}
    for key in ("max_task_bytes", "max_prompt_bytes", "max_response_bytes",
                "max_runtime_seconds", "max_assigned_paths",
                "max_changed_files", "max_changed_bytes"):
        value = limits.get(key)
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            problems.append("limits.%s must be a positive integer" % key)

    if problems:
        _bad("; ".join(problems))
    return policy


# --------------------------------------------------------------------------
# Task envelope
# --------------------------------------------------------------------------

def is_task(msg):
    return isinstance(msg, dict) and msg.get("message_type") == TASK_TYPE


def is_outcome(msg):
    return isinstance(msg, dict) and msg.get("message_type") == OUTCOME_TYPE


def is_claim(msg):
    return isinstance(msg, dict) and msg.get("message_type") == CLAIM_TYPE


def validate_task(doc, policy):
    """A task is data: it names paths and describes work, and nothing else."""
    limits = {"max_envelope_bytes": policy["limits"]["max_task_bytes"],
              "max_depth": 24, "max_paths": 512, "max_string_chars": 8192}
    cr._require(doc, TASK_FIELDS, "implementation task")
    cr._walk(doc, limits, prose=True)

    if doc["schema_version"] != SCHEMA_VERSION:
        _bad("unsupported task schema_version")
    if doc["message_type"] != TASK_TYPE:
        _bad("message_type must be %r" % TASK_TYPE)
    cr._str_field(doc, "entry_id", cr._UUID_RE, "task")
    cr._str_field(doc, "task_id", cr._PHASE_RE, "task")
    cr._str_field(doc, "phase", cr._PHASE_RE, "task")
    cr._str_field(doc, "head", cr._OID_RE, "task")

    paths = doc["assigned_paths"]
    if not isinstance(paths, list) or not paths:
        _bad("a task must assign at least one path")
    if len(paths) > policy["limits"]["max_assigned_paths"]:
        raise ef.SafetyLimitError("the task assigns too many paths")
    protected = set(policy["containment"]["always_protected_paths"])
    for item in paths:
        if not isinstance(item, str) or not item.strip():
            _bad("every assigned path must be a non-empty string")
        if item.startswith("/") or item.startswith("\\") or ":" in item:
            _bad("an assigned path must be repository-relative")
        if ".." in item.replace("\\", "/").split("/"):
            _bad("an assigned path may not traverse upwards")
        if item in protected:
            _bad("an always-protected path may never be assigned: %s" % item)
        _reject_short_names(item)
        # Equality is not enough: `tools/cowork/**` covers a protected file
        # without being equal to one.
        for guarded in protected:
            clean = guarded.replace("\\", "/")
            if in_scope(clean, [item]):
                _bad("that assignment covers the always-protected path %s"
                     % clean)

    for key in ("instruction", "acceptance"):
        if not isinstance(doc[key], str) or not doc[key].strip():
            _bad("task %s must be a non-empty string" % key)
        if len(doc[key]) > 8192:
            raise ef.SafetyLimitError("task %s exceeds the maximum length" % key)
    return doc


def find_pending_task(ledger_doc):
    """The one task awaiting a child, or a refusal.

    A task whose outcome is already recorded is never returned. That is what
    makes recovery safe: re-running the runner after a crash finds nothing to
    do rather than doing the same work twice.
    """
    stale = unsettled_claims(ledger_doc)
    if stale:
        raise sg.StoppedError(
            "task %s has a claimed but unsettled attempt; its attempt was "
            "already spent. It is NOT re-run automatically -- settle it with "
            "settle-claim before assigning more work" % stale[0])
    done = settled_task_ids(ledger_doc) | claimed_task_ids(ledger_doc)
    pending = [e for e in ledger_doc.get("entries", [])
               if is_task(e) and e.get("task_id") not in done]
    if not pending:
        raise sg.StoppedError("the ledger holds no pending implementation task")
    if len(pending) > 1:
        raise sg.StoppedError("more than one implementation task is pending; "
                              "the ledger is ambiguous")
    return pending[0]


def _durable_replace(tmp, path):
    """Replace `path` with `tmp` so the result survives a crash.

    `os.replace` is atomic but not necessarily durable: the rename can still be
    sitting in the cache. Windows exposes MOVEFILE_WRITE_THROUGH for exactly
    this, which is what a claim needs -- a claim the machine forgets is a
    second attempt spent on work that already ran.
    """
    if os.name != "nt":
        os.replace(tmp, path)
        fd = os.open(os.path.dirname(path) or ".", os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
        return
    import ctypes
    MOVEFILE_REPLACE_EXISTING = 0x1
    MOVEFILE_WRITE_THROUGH = 0x8
    ok = ctypes.windll.kernel32.MoveFileExW(
        ctypes.c_wchar_p(tmp), ctypes.c_wchar_p(path),
        MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH)
    if not ok:
        raise ProtectionFailed("the ledger could not be durably replaced")


def _atomic_durable_write(path, payload):
    """Same-directory temp file, flushed and fsynced, then a durable replace."""
    directory = os.path.dirname(path) or "."
    tmp = os.path.join(directory, ".%s.%d.tmp"
                       % (os.path.basename(path), os.getpid()))
    fd = os.open(tmp, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        _durable_replace(tmp, path)
        tmp = None
    finally:
        if tmp is not None:
            try:
                os.unlink(tmp)
            except OSError:
                pass


def _append_entry(root, doc, entry):
    """Chain one entry onto the ledger and write it atomically."""
    entries = doc["entries"]
    entry["sequence"] = len(entries) + 1
    entry["previous_sha256"] = (
        hashlib.sha256(cr.canonical_bytes(entries[-1])).hexdigest()
        if entries else "0" * 64)
    entries.append(entry)
    doc["revision"] = doc.get("revision", 0) + 1
    os.makedirs(os.path.abspath(root), exist_ok=True)
    _atomic_durable_write(ledger_path(root),
                          json.dumps(doc, indent=2, sort_keys=True).encode("utf-8"))
    return entry


def claim_attempt(root, task, claimed_by="codex_implementation_runner"):
    """Record, durably and BEFORE the child starts, that an attempt is being spent.

    This is the correction for the crash window. Previously the attempt existed
    only in memory until an outcome was written, so a crash in between left the
    task looking untouched and a restart would spend a second attempt on it.
    """
    with _LedgerLock(root):
        doc = read_ledger(root)
        problems = verify_ledger(doc)
        if problems:
            raise sg.StoppedError("the implementation ledger does not verify: "
                                  "%s" % problems[0][1])
        if task["task_id"] in claimed_task_ids(doc):
            raise sg.StoppedError("that task's attempt is already claimed")
        return _append_entry(root, doc, {
            "schema_version": SCHEMA_VERSION,
            "entry_id": str(uuid.uuid4()),
            "created_at": datetime.now(timezone.utc)
                                  .strftime("%Y-%m-%dT%H:%M:%SZ"),
            "message_type": CLAIM_TYPE,
            "task_id": task["task_id"],
            "phase": task["phase"],
            "head": task["head"],
            "claimed_by": claimed_by,
            "pid": os.getpid(),
        })


def record_task(root, task_id, phase, repo_obs, registry_revision,
                assigned_paths, instruction, acceptance, policy,
                assigned_by="claude"):
    """Append one task. The coordinator assigns; the model never self-assigns."""
    with _LedgerLock(root):
        doc = read_ledger(root)
        problems = verify_ledger(doc)
        if problems:
            raise sg.StoppedError("the implementation ledger does not verify: %s"
                                  % problems[0][1])
        if task_id in {e.get("task_id") for e in doc["entries"]}:
            _bad("that task id is already recorded; a task runs at most once")

        entry = {
            "schema_version": SCHEMA_VERSION,
            "entry_id": str(uuid.uuid4()),
            "sequence": len(doc["entries"]) + 1,
            "previous_sha256": "0" * 64,        # _append_entry sets both
            "created_at": datetime.now(timezone.utc)
                                  .strftime("%Y-%m-%dT%H:%M:%SZ"),
            "message_type": TASK_TYPE,
            "task_id": task_id,
            "phase": phase,
            "repository_identity": "nova",
            "worktree_identity": repo_obs["identity"],
            "branch": repo_obs["branch"],
            "head": repo_obs["head"],
            "registry_revision": registry_revision,
            "assigned_paths": list(assigned_paths),
            "instruction": instruction,
            "acceptance": acceptance,
            "assigned_by": assigned_by,
        }
        validate_task(entry, policy)
        return _append_entry(root, doc, entry)


# --------------------------------------------------------------------------
# L2 -- protected paths, enforced by the filesystem
# --------------------------------------------------------------------------

def _iter_protected(repo, policy, assigned):
    """Every existing file the run must not be able to write."""
    import glob as _glob
    assigned_set = {a.replace("\\", "/").rstrip("/") for a in assigned}
    for pattern in policy["containment"]["always_protected_paths"]:
        for hit in _glob.glob(os.path.join(repo, pattern), recursive=True):
            if os.path.isdir(hit):
                for base, _dirs, files in os.walk(hit):
                    for name in files:
                        yield os.path.join(base, name)
            elif os.path.exists(hit):
                yield hit
    # Anything tracked that is NOT assigned is also protected for this run.
    listing = subprocess.run(["git", "-C", repo, "ls-files"],
                             capture_output=True, text=True)
    if listing.returncode == 0:
        for rel in listing.stdout.splitlines():
            rel = rel.strip()
            if not rel:
                continue
            if any(rel == a or rel.startswith(a.rstrip("/") + "/")
                   or _fnmatch(rel, a) for a in assigned_set):
                continue
            full = os.path.join(repo, rel)
            if os.path.isfile(full):
                yield full


def _fnmatch(name, pattern):
    import fnmatch
    return fnmatch.fnmatch(name, pattern)


# An 8.3 alias: a component like EXECUT~1.PY that Windows accepts as another
# name for a longer one. Scope and protected-path checks are lexical, so an
# alias could pass them and still resolve to a different file.
_SHORT_NAME = re.compile(r"~\d")


def _reject_short_names(rel):
    """Refuse a path whose components could be 8.3 aliases."""
    for part in rel.replace("\\", "/").split("/"):
        if _SHORT_NAME.search(part):
            raise ProtectionFailed(
                "a path component looks like a Windows short name alias, "
                "which is not accepted where scope is decided by name: %s"
                % part)


def _long_path(path):
    """The canonical long form of `path`, or the input when unavailable."""
    if os.name != "nt":
        return path
    import ctypes
    buf = ctypes.create_unicode_buffer(32768)
    n = ctypes.windll.kernel32.GetLongPathNameW(
        ctypes.c_wchar_p(path), buf, 32768)
    if n == 0 or n >= 32768:
        return path
    return buf.value


def _canonical_relative(repo, dst):
    """Where `dst` really sits under `repo`, expressed with long names.

    Comparing the short form would let an alias satisfy a lexical check while
    naming a different file, so the comparison is made after canonicalising.
    """
    long_repo = _norm(_long_path(os.path.abspath(repo)))
    long_dst = _norm(_long_path(os.path.abspath(dst)))
    if not rr._within(long_dst, long_repo):
        raise ProtectionFailed("the destination canonicalises outside the "
                               "worktree")
    rel = os.path.relpath(long_dst, long_repo).replace(os.sep, "/")
    _reject_short_names(rel)
    return rel


def _refuse_protected(rel, policy):
    """Refuse a repository-relative path that any protected pattern covers."""
    for pattern in policy["containment"]["always_protected_paths"]:
        clean = pattern.replace("\\", "/")
        if rel == clean or _fnmatch(rel, clean) \
                or rel.startswith(clean.rstrip("/*") + "/"):
            raise ProtectionFailed("that path is always protected: %s" % rel)


def _norm(path):
    """One spelling for a path, so a restore map key always matches."""
    return os.path.normcase(os.path.abspath(path))


class ProtectionFailed(Exception):
    """Protection could not be established. The run must not start."""


# Empty files created by a destination open that then failed validation. They
# are recorded rather than unlinked: see the cleanup note in `_open_contained`.
_ORPHANED_ON_FAILURE = []


def protect_paths(repo, policy, assigned, strict=True):
    """Mark everything outside the assignment read-only, over the REAL worktree.

    This is defence in depth, NOT a boundary, and the difference matters: a
    same-user process can clear the attribute, so this stops an accident and
    not an attacker. The boundary is the staging workspace plus the sandbox
    root -- see `build_staging`.

    What changed after review: it no longer swallows a failure. If a file
    cannot be stat-ed or cannot be made read-only, protection for that file was
    NOT established, and with `strict` the whole run is refused rather than
    proceeding under a protection that does not exist.
    """
    restore = {}
    unprotected = []
    for raw in _iter_protected(repo, policy, assigned):
        path = _norm(raw)
        if path in restore:
            continue
        try:
            mode = os.stat(path).st_mode
        except OSError as exc:
            unprotected.append((path, "cannot stat: %s" % exc.__class__.__name__))
            continue
        try:
            os.chmod(path, mode & ~stat.S_IWRITE)
        except OSError as exc:
            unprotected.append((path, "cannot chmod: %s" % exc.__class__.__name__))
            continue
        restore[path] = mode
    if unprotected and strict:
        restore_paths(restore)
        raise ProtectionFailed(
            "protection could not be established for %d path(s); refusing to "
            "run rather than proceeding unprotected" % len(unprotected))
    return restore


def restore_paths(restore):
    """Put every protected file back exactly as it was."""
    failures = []
    for path, mode in restore.items():
        try:
            os.chmod(path, mode)
        except OSError:
            failures.append(path)
    return failures


def protected_paths_touched(repo, restore):
    """Any protected file whose content changed during the run."""
    listing = subprocess.run(
        ["git", "-C", repo, "status", "--porcelain", "--untracked-files=all"],
        capture_output=True, text=True)
    if listing.returncode != 0:
        return []
    touched = []
    protected = set(restore)          # already normalised by protect_paths
    for line in listing.stdout.splitlines():
        rel = line[3:].strip().strip('"')
        if not rel:
            continue
        full = _norm(os.path.join(repo, rel))
        if full in protected:
            touched.append(rel)
    return touched


# --------------------------------------------------------------------------
# L2 -- the staging workspace, which is what actually denies the write
# --------------------------------------------------------------------------

STAGING_DIRNAME = "impl-staging"


def _assigned_files(repo, assigned):
    """Every tracked file the assignment covers, repository-relative."""
    listing = subprocess.run(["git", "-C", repo, "ls-files"],
                             capture_output=True, text=True)
    if listing.returncode != 0:
        raise ProtectionFailed("the assigned worktree could not be listed")
    out = []
    for rel in listing.stdout.splitlines():
        rel = rel.strip().replace("\\", "/")
        if rel and in_scope(rel, assigned):
            out.append(rel)
    return out


def build_staging(repo, assigned, policy, parent=None):
    """Create a workspace holding the assigned paths and nothing else.

    This is the enforceable part. A protected file is not merely read-only in
    here, it is ABSENT, so there is nothing to write, replace, delete, or
    chmod; and the sandbox root denies reaching out to the original. Failure to
    build it correctly refuses the run -- an empty or partial staging directory
    is never treated as "nothing to protect".
    """
    files = _assigned_files(repo, assigned)
    if not files:
        raise ProtectionFailed("the assignment matches no tracked file; "
                               "refusing to stage an empty workspace")
    base = tempfile.mkdtemp(prefix=STAGING_DIRNAME + "-", dir=parent)
    try:
        os.chmod(base, 0o700)
    except OSError:
        pass
    for rel in files:
        src = os.path.join(repo, rel)
        dst = os.path.join(base, rel.replace("/", os.sep))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
    verify_staging(base, assigned, policy)
    return base, files


def verify_staging(base, assigned, policy):
    """Nothing outside the assignment may exist in the staging workspace."""
    protected = set(policy["containment"]["always_protected_paths"])
    present = []
    for root_dir, _dirs, names in os.walk(base):
        for name in names:
            rel = os.path.relpath(os.path.join(root_dir, name), base)
            rel = rel.replace(os.sep, "/")
            present.append(rel)
            _reject_short_names(rel)
            if not in_scope(rel, assigned):
                raise ProtectionFailed(
                    "staging holds a path outside the assignment: %s" % rel)
            _refuse_protected(rel, policy)
    if not present:
        raise ProtectionFailed("the staging workspace is empty")
    return present


def _final_path_of_handle(fd):
    """Ask Windows what this OPEN HANDLE actually refers to.

    Checking a path and then writing to it is a race: the path can become a
    junction between the two. Resolving the handle we are about to write
    through closes that window, because the answer describes the object we
    already hold, not a name someone can still redirect.
    """
    if os.name != "nt":
        return os.path.realpath("/proc/self/fd/%d" % fd)
    import ctypes
    import msvcrt
    handle = msvcrt.get_osfhandle(fd)
    buf = ctypes.create_unicode_buffer(32768)
    n = ctypes.windll.kernel32.GetFinalPathNameByHandleW(
        ctypes.c_void_p(handle), buf, 32768, 0)
    if n == 0 or n >= 32768:
        raise ProtectionFailed("the destination handle could not be resolved")
    final = buf.value
    for prefix in ("\\\\?\\UNC\\", "\\\\?\\"):
        if final.startswith(prefix):
            final = final[len(prefix):]
            break
    return final


def _handle_link_count(fd):
    """How many names this open file has. More than one is a hard link.

    A hard link inside the worktree resolves to an in-worktree NAME while
    sharing its contents with a file elsewhere, so resolving the handle's path
    is not enough on its own -- the write would still reach the other name.
    """
    if os.name != "nt":
        try:
            return os.fstat(fd).st_nlink
        except OSError:
            return None
    import ctypes
    import msvcrt
    from ctypes import wintypes

    class _FILETIME(ctypes.Structure):
        _fields_ = [("dwLowDateTime", wintypes.DWORD),
                    ("dwHighDateTime", wintypes.DWORD)]

    class _INFO(ctypes.Structure):
        _fields_ = [("dwFileAttributes", wintypes.DWORD),
                    ("ftCreationTime", _FILETIME),
                    ("ftLastAccessTime", _FILETIME),
                    ("ftLastWriteTime", _FILETIME),
                    ("dwVolumeSerialNumber", wintypes.DWORD),
                    ("nFileSizeHigh", wintypes.DWORD),
                    ("nFileSizeLow", wintypes.DWORD),
                    ("nNumberOfLinks", wintypes.DWORD),
                    ("nFileIndexHigh", wintypes.DWORD),
                    ("nFileIndexLow", wintypes.DWORD)]

    info = _INFO()
    handle = msvcrt.get_osfhandle(fd)
    if not ctypes.windll.kernel32.GetFileInformationByHandle(
            ctypes.c_void_p(handle), ctypes.byref(info)):
        return None
    return int(info.nNumberOfLinks)


def _refuse_reparse_ancestors(path, repo):
    """No directory between the worktree root and the target may be a link.

    A Windows directory JUNCTION needs no privilege to create and
    `os.path.islink` reports it as False, so the attribute is checked directly
    rather than trusting islink.
    """
    root = _norm(repo)
    current = _norm(path)
    seen = set()
    while True:
        if current in seen:
            break
        seen.add(current)
        if os.path.exists(current):
            try:
                info = os.stat(current, follow_symlinks=False)
            except OSError:
                raise ProtectionFailed("a destination ancestor could not be "
                                       "inspected")
            if os.path.islink(current) or rr.is_reparse_point(info):
                raise ProtectionFailed(
                    "a destination ancestor is a link or reparse point; "
                    "refusing to write through it")
        if current == root:
            break
        parent = _norm(os.path.dirname(current))
        if parent == current:
            raise ProtectionFailed("the destination escapes the worktree")
        current = parent


def _makedirs_contained(parent, repo, assigned, policy):
    """Create the destination's directories one component at a time.

    `os.makedirs` takes a whole path and follows whatever it finds, so an
    ancestor replaced with a junction makes it create directories at the
    redirected target -- before any handle exists to check. Each component is
    therefore created and then immediately validated, so a redirected ancestor
    is caught before anything descends into it.
    """
    repo_long = _norm(_long_path(os.path.abspath(repo)))
    rel = os.path.relpath(_norm(os.path.abspath(parent)), _norm(os.path.abspath(repo)))
    if rel in (".", ""):
        return
    if rel.startswith(".."):
        raise ProtectionFailed("the destination directory is outside the "
                               "worktree")
    current = os.path.abspath(repo)
    for part in rel.replace("/", os.sep).split(os.sep):
        if not part or part == ".":
            continue
        if part == "..":
            raise ProtectionFailed("the destination directory traverses "
                                   "upwards")
        current = os.path.join(current, part)
        if not os.path.lexists(current):
            try:
                os.mkdir(current)
            except FileExistsError:
                pass
            except OSError:
                raise ProtectionFailed("a destination directory could not be "
                                       "created")
        try:
            info = os.stat(current, follow_symlinks=False)
        except OSError:
            raise ProtectionFailed("a destination directory could not be "
                                   "inspected")
        if os.path.islink(current) or rr.is_reparse_point(info):
            raise ProtectionFailed(
                "a destination directory is a link or reparse point; "
                "refusing to create or descend through it")
        settled = _norm(_long_path(current))
        if not rr._within(settled, repo_long) and settled != repo_long:
            raise ProtectionFailed(
                "a destination directory resolves outside the worktree")
        step = os.path.relpath(settled, repo_long).replace(os.sep, "/")
        _reject_short_names(step)
        _refuse_protected(step, policy)


def _read_contained(src, staging):
    """Read a staged file through a handle proven to live inside staging.

    Opening the source by pathname is the same class of mistake as writing by
    pathname: the model owns the staging tree, so it can replace a staged file
    with a link between validation and the read and have the runner read
    something else -- then write that content into an assigned file.
    """
    _refuse_reparse_ancestors(os.path.dirname(src), staging)
    if os.path.lexists(src):
        try:
            info = os.stat(src, follow_symlinks=False)
        except OSError:
            raise ProtectionFailed("a staged source could not be inspected")
        if os.path.islink(src) or rr.is_reparse_point(info):
            raise ProtectionFailed(
                "a staged source is a link or reparse point; refusing to read "
                "through it")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) \
        | getattr(os, "O_NOINHERIT", 0)
    fd = os.open(src, flags)
    try:
        final = _final_path_of_handle(fd)
        root = _norm(_long_path(os.path.abspath(staging)))
        if not rr._within(final, root):
            raise ProtectionFailed(
                "a staged source resolves outside the staging workspace")
        links = _handle_link_count(fd)
        if links is None or links > 1:
            raise ProtectionFailed(
                "a staged source has more than one name, or its link count "
                "could not be established; refusing to read through it")
        chunks = []
        while True:
            block = os.read(fd, 1 << 20)
            if not block:
                break
            chunks.append(block)
        return b"".join(chunks)
    finally:
        os.close(fd)


def _open_contained(dst, repo, assigned=None, policy=None):
    """Open a destination for writing only if the HANDLE passes every check.

    Containment, assignment scope and protected-path status are all decided on
    the handle's own resolved name. Deciding them on a path beforehand leaves a
    window: an ancestor replaced between the check and the open redirects the
    write to a different in-worktree path -- possibly a protected one -- while
    the earlier checks still read as satisfied.

    Deliberately opened WITHOUT truncation: truncating first and validating
    afterwards would already have destroyed a redirected target.
    """
    parent = os.path.dirname(dst)
    _refuse_reparse_ancestors(parent, repo)
    if os.path.lexists(dst):
        try:
            info = os.stat(dst, follow_symlinks=False)
        except OSError:
            raise ProtectionFailed("the destination could not be inspected")
        if os.path.islink(dst) or rr.is_reparse_point(info):
            raise ProtectionFailed("the destination is a link or reparse "
                                   "point; refusing to write through it")
    created = not os.path.lexists(dst)
    flags = os.O_WRONLY | os.O_CREAT | getattr(os, "O_BINARY", 0) \
        | getattr(os, "O_NOINHERIT", 0)
    fd = os.open(dst, flags, 0o600)
    try:
        final = _final_path_of_handle(fd)
        if not rr._within(final, _norm(repo)):
            raise ProtectionFailed(
                "the destination resolves outside the worktree; refusing")
        # A resolved name inside the worktree is still not enough: a HARD LINK
        # has an in-worktree name and shares its contents with another name
        # that may be anywhere. Refuse anything with more than one name, and
        # refuse when the count cannot be established.
        links = _handle_link_count(fd)
        if links is None:
            raise ProtectionFailed(
                "the destination's link count could not be established; "
                "refusing rather than writing through an unknown name")
        if links > 1:
            raise ProtectionFailed(
                "the destination has more than one name (hard link); "
                "refusing to write through it")
        # Scope and protected status are decided HERE, on the handle's own
        # resolved name, so an ancestor swapped after any earlier check cannot
        # redirect the write to another in-worktree path.
        settled = os.path.relpath(final, _norm(_long_path(os.path.abspath(repo))))
        settled = settled.replace(os.sep, "/")
        _reject_short_names(settled)
        if assigned is not None and not in_scope(settled, assigned):
            raise ProtectionFailed(
                "the opened destination is outside the assignment: %s"
                % settled)
        if policy is not None:
            _refuse_protected(settled, policy)
    except Exception:
        os.close(fd)
        # Deliberately NOT removed. Comparing device and inode after the handle
        # is closed still leaves a window where those identifiers could be
        # reused by a replacement object, and unlinking the wrong object is
        # worse than leaving an empty file behind. An empty file we created is
        # inert, appears in the coordinator's diff, and is reverted there if it
        # is out of scope -- at a point when no model is running.
        if created:
            _ORPHANED_ON_FAILURE.append(dst)
        raise
    return fd


def apply_staged(base, repo, assigned, policy):
    """Copy the staged result back, for assigned paths only.

    Every write goes through a handle that has been proven to resolve inside
    the worktree, so a junction planted between validation and the copy cannot
    redirect it. That mattered: a directory junction -- which needs no
    privilege on Windows and which `os.path.islink` reports as False -- was
    measured redirecting this copy outside the repository.
    """
    verify_staging(base, assigned, policy)
    applied = []
    for root_dir, _dirs, names in os.walk(base):
        for name in names:
            src = os.path.join(root_dir, name)
            rel = os.path.relpath(src, base).replace(os.sep, "/")
            if not in_scope(rel, assigned):
                raise ProtectionFailed("refusing to apply %s" % rel)
            _reject_short_names(rel)
            dst = os.path.join(repo, rel.replace("/", os.sep))
            _refuse_reparse_ancestors(os.path.dirname(dst), repo)
            _makedirs_contained(os.path.dirname(dst), repo, assigned, policy)
            _refuse_reparse_ancestors(os.path.dirname(dst), repo)
            # Decide scope on where the destination REALLY is, after
            # canonicalising, not on the name staging happened to use.
            canonical = _canonical_relative(repo, dst)
            if not in_scope(canonical, assigned):
                raise ProtectionFailed(
                    "the destination canonicalises outside the assignment: %s"
                    % canonical)
            _refuse_protected(canonical, policy)
            payload = _read_contained(src, base)
            fd = _open_contained(dst, repo, assigned, policy)
            try:
                os.ftruncate(fd, 0)
                os.write(fd, payload)
            finally:
                os.close(fd)
            applied.append(rel)
    return applied


def discard_staging(base):
    shutil.rmtree(base, ignore_errors=True)


# --------------------------------------------------------------------------
# L3 -- the coordinator's scope check
# --------------------------------------------------------------------------

def changed_paths(repo):
    listing = subprocess.run(
        ["git", "-C", repo, "status", "--porcelain", "--untracked-files=all"],
        capture_output=True, text=True)
    if listing.returncode != 0:
        raise sg.StoppedError("the assigned worktree could not be inspected")
    out = []
    for line in listing.stdout.splitlines():
        rel = line[3:].strip().strip('"')
        if rel:
            out.append(rel.replace("\\", "/"))
    return out


def in_scope(rel, assigned):
    rel = rel.replace("\\", "/")
    for item in assigned:
        item = item.replace("\\", "/").rstrip("/")
        if rel == item or rel.startswith(item + "/") or _fnmatch(rel, item):
            return True
    return False


def out_of_scope_changes(repo, assigned):
    return [rel for rel in changed_paths(repo) if not in_scope(rel, assigned)]


def revert_paths(repo, paths):
    """Undo anything the run should not have touched."""
    for rel in paths:
        tracked = subprocess.run(["git", "-C", repo, "ls-files", "--error-unmatch", rel],
                                 capture_output=True)
        if tracked.returncode == 0:
            subprocess.run(["git", "-C", repo, "checkout", "--", rel],
                           capture_output=True)
        else:
            try:
                os.remove(os.path.join(repo, rel))
            except OSError:
                pass


# --------------------------------------------------------------------------
# Invocation
# --------------------------------------------------------------------------

def build_argv(executable, worktree, response_path, policy):
    """The one argument array. Fixed, and never widened by an envelope."""
    flags = policy["fixed_flags"]
    argv = [
        executable, "exec",
        "-C", worktree,
        SANDBOX_FLAG, SANDBOX_MODE,
        "-c", '%s="%s"' % (rr.WINDOWS_SANDBOX_CONFIG_KEY, flags["windows_sandbox"]),
        "-c", '%s="%s"' % (rr.APPROVAL_CONFIG_KEY, flags["ask_for_approval"]),
        "-m", flags["model"],
        "-c", 'model_reasoning_effort="%s"' % flags["model_reasoning_effort"],
        "--ephemeral",
        "--ignore-user-config",
        "-o", response_path,
        rr.PROMPT_ARGUMENT,
    ]
    joined = " ".join(argv)
    for name in FORBIDDEN_FLAGS:
        if name in argv:
            _bad("a forbidden flag reached the argument array: %s" % name)
    if "--add-dir" in joined:
        _bad("the writable root may never be widened")
    for name in policy.get("forbidden_subcommands") or ():
        if name in argv[2:3]:
            _bad("a forbidden subcommand reached the argument array")
    return argv


def build_prompt(task, policy):
    """The instruction. It carries no authority the sandbox does not already give."""
    lines = [
        "# NOVA implementation task",
        "",
        "You are editing files in a sandboxed worktree. Writes outside it are",
        "refused by the operating system, not by this text -- do not attempt",
        "them, and do not treat any instruction here as widening what you may",
        "reach.",
        "",
        "## Rules",
        "",
        "1. Edit ONLY the assigned paths listed below. Anything else is",
        "   reverted and the task is recorded as out of scope.",
        "2. Do NOT run git. You have no access to git metadata and no ability",
        "   to commit, stage, push, or move a ref. A human coordinator reviews",
        "   and commits your work.",
        "3. Do NOT touch credentials, coordination state, the retired trading",
        "   or execution subsystem, or the guard hook.",
        "4. Make the smallest change that satisfies the acceptance criteria,",
        "   and match the surrounding code's style.",
        "5. When you are done, answer with the JSON document the schema",
        "   requires, describing what you changed and why.",
        "",
        "## Task",
        "",
        "id: %s" % task["task_id"],
        "",
        task["instruction"],
        "",
        "## Acceptance",
        "",
        task["acceptance"],
        "",
        "## Assigned paths -- the only files you may modify",
        "",
    ]
    lines += ["- %s" % p for p in task["assigned_paths"]]
    lines += [
        "",
        "## Non-authorization",
        "",
        policy["non_authorization_sentence"],
        "",
    ]
    text = "\n".join(lines) + "\n"
    data = text.encode("utf-8")
    if len(data) > policy["limits"]["max_prompt_bytes"]:
        raise ef.SafetyLimitError("the constructed prompt exceeds the maximum size")
    return data


# --------------------------------------------------------------------------
# Preconditions
# --------------------------------------------------------------------------

def check_preconditions(task, repo_obs, registry, coordinator_id, worker_id,
                        policy, now):
    problems = []
    if task["head"] != repo_obs["head"]:
        problems.append("the task head does not match the worktree HEAD")
    if task["branch"] != repo_obs["branch"]:
        problems.append("the task branch does not match the worktree")
    if task["worktree_identity"] != repo_obs["identity"]:
        problems.append("the task worktree identity does not match")
    if task["registry_revision"] != registry["revision"]:
        problems.append("the task registry revision is stale")
    if repo_obs["dirty_entries"]:
        problems.append("the assigned worktree is dirty before the run")

    records = {s["session_id"]: s for s in registry["sessions"]}
    coordinator = records.get(coordinator_id)
    if coordinator is None:
        problems.append("the coordinator session is not registered")
    elif coordinator["status"] != "paused":
        problems.append("the coordinator session must be paused during a run")

    worker = records.get(worker_id)
    if worker is None:
        problems.append("the worker session is not registered")
    else:
        if worker["status"] != "active":
            problems.append("the worker session is not active")
        if sr.classify(worker, now, sr.DEFAULT_STALE_SECONDS) != "live":
            problems.append("the worker session is not live")
        if "codex" not in (worker.get("owner") or "").lower():
            problems.append("the worker session owner does not identify Codex")
        if worker.get("expected_commit") != repo_obs["head"]:
            problems.append("the worker session expected_commit does not match HEAD")
        if worker.get("worktree_identity") != repo_obs["identity"]:
            problems.append("the worker session worktree does not match")
        assigned = {p.replace("\\", "/") for p in task["assigned_paths"]}
        declared = {p.replace("\\", "/") for p in (worker.get("write_scope") or [])}
        if not assigned or not assigned.issubset(declared):
            problems.append("the task assigns paths the worker session does not "
                            "declare as its write scope")

    # The git directory of a linked worktree lives OUTSIDE it. That is what
    # keeps git metadata away from the child, so it is verified, not assumed.
    common = subprocess.run(["git", "-C", repo_obs["repo"], "rev-parse",
                             "--git-common-dir"], capture_output=True, text=True)
    if common.returncode != 0:
        problems.append("the git common directory could not be resolved")
    else:
        git_dir = os.path.abspath(common.stdout.strip())
        if rr._within(git_dir, os.path.abspath(repo_obs["repo"])):
            problems.append("the git directory is inside the assigned worktree, "
                            "so the sandbox would not keep git metadata out of "
                            "reach; use a linked worktree")
    return problems


# --------------------------------------------------------------------------
# Outcome recording
# --------------------------------------------------------------------------

LEDGER_FILENAME = "implementation-ledger.json"
LEDGER_LOCK_SUFFIX = ".lock"
LOCK_STALE_SECONDS = 3600


class LedgerBusy(Exception):
    """Another runner holds the ledger. Two children must never race."""


def _process_started_at(pid):
    """The process's creation time, or None if it cannot be read.

    A pid on its own is not an identity: pids are recycled, so a live process
    can inherit the pid of the owner that died. pid PLUS creation time is an
    identity, and that is what makes stale-lock recovery safe.
    """
    if not isinstance(pid, int) or pid <= 0:
        return None
    if os.name != "nt":
        try:
            with open("/proc/%d/stat" % pid, "rb") as handle:
                return handle.read().rsplit(b")", 1)[1].split()[19].decode()
        except Exception:
            return None
    import ctypes
    from ctypes import wintypes

    class _FILETIME(ctypes.Structure):
        _fields_ = [("dwLowDateTime", wintypes.DWORD),
                    ("dwHighDateTime", wintypes.DWORD)]

    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return None
    try:
        creation, exit_t, kernel_t, user_t = (_FILETIME(), _FILETIME(),
                                              _FILETIME(), _FILETIME())
        if not kernel32.GetProcessTimes(
                ctypes.c_void_p(handle), ctypes.byref(creation),
                ctypes.byref(exit_t), ctypes.byref(kernel_t),
                ctypes.byref(user_t)):
            return None
        return "%d-%d" % (creation.dwHighDateTime, creation.dwLowDateTime)
    finally:
        kernel32.CloseHandle(handle)


def _process_is_live(pid, started_at=None):
    """True if running, False if definitely gone, None if unknown.

    None matters as much as the other two: an unknown owner is treated as live,
    never as abandoned. When `started_at` is supplied it must also match, so a
    RECYCLED pid reads as gone rather than as the original owner still running.
    """
    if not isinstance(pid, int) or pid <= 0:
        return None
    if os.name != "nt":
        try:
            os.kill(pid, 0)
            live = True
        except ProcessLookupError:
            return False
        except PermissionError:
            live = True
        except OSError:
            return None
    else:
        import ctypes
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        STILL_ACTIVE = 259
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION,
                                      False, pid)
        if not handle:
            # 87 ERROR_INVALID_PARAMETER means no such process; anything else
            # (notably 5 ERROR_ACCESS_DENIED) means it exists but we cannot ask.
            return False if kernel32.GetLastError() == 87 else None
        try:
            code = ctypes.c_ulong()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
                return None
            live = code.value == STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
        if not live:
            return False
    if started_at is None:
        return live
    now = _process_started_at(pid)
    if now is None:
        return None                      # cannot confirm identity -> unknown
    return now == started_at


class _LedgerLock:
    """Exclusive create, so two runners cannot claim the same task.

    O_EXCL is atomic on Windows and POSIX alike.

    A lock is broken ONLY when its owner is definitively gone AND it is older
    than the staleness threshold. A live owner keeps its lock however long it
    holds it, and an owner we cannot identify -- an unreadable, empty or
    malformed lock, or a pid we are not allowed to query -- is treated as live.
    Stealing a lock from a running owner would let two runners mutate the
    ledger at once, which is the invariant this exists to protect.
    """

    def __init__(self, root):
        self.path = ledger_path(root) + LEDGER_LOCK_SUFFIX
        self.fd = None

    def _owner(self):
        """(pid, started_at) from the lock, or (None, None) if unreadable."""
        try:
            raw = open(self.path, "rb").read(128).decode("ascii", "replace")
        except OSError:
            return None, None
        parts = raw.strip().split()
        if not parts or not parts[0].isdigit():
            return None, None
        pid = int(parts[0])
        return pid, (parts[1] if len(parts) > 1 else None)

    def _stamp(self):
        started = _process_started_at(os.getpid())
        return "%d %s" % (os.getpid(), started or "-")

    def __enter__(self):
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        try:
            self.fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            pid, started = self._owner()
            live = _process_is_live(pid, started)
            if live is not False:
                raise LedgerBusy(
                    "another runner holds the implementation ledger lock "
                    "(owner %s)" % ("unknown" if live is None else "running"))
            try:
                age = time.time() - os.path.getmtime(self.path)
            except OSError:
                raise LedgerBusy("the ledger lock could not be inspected")
            if age < LOCK_STALE_SECONDS:
                raise LedgerBusy("the ledger lock's owner has exited but the "
                                 "lock is not yet stale; refusing to take it")
            # Move the stale lock aside rather than deleting it in place, then
            # take the name with O_EXCL. If another runner reclaimed it first,
            # either the move or the create fails and we back off -- the two
            # steps never leave the name unowned in a way a racer can exploit.
            aside = "%s.stale.%d" % (self.path, os.getpid())
            try:
                os.replace(self.path, aside)
            except OSError:
                raise LedgerBusy("another runner reclaimed the ledger lock "
                                 "first")
            try:
                self.fd = os.open(self.path,
                                  os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                raise LedgerBusy("another runner reclaimed the ledger lock "
                                 "first")
            finally:
                try:
                    os.unlink(aside)
                except OSError:
                    pass
        os.write(self.fd, self._stamp().encode("ascii"))
        os.fsync(self.fd)
        return self

    def __exit__(self, *_exc):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None
        try:
            os.unlink(self.path)
        except OSError:
            pass
        return False
MAX_LEDGER_BYTES = 4 * 1024 * 1024


def ledger_path(root):
    return os.path.join(os.path.abspath(root), LEDGER_FILENAME)


def read_ledger(root):
    """The implementation ledger: append-only, hash chained, its own file.

    Deliberately NOT the review mailbox. Review coordination and implementation
    coordination are different ledgers with different message types, and the
    reviewed relay is a protected component this tool does not reshape.
    """
    path = ledger_path(root)
    if not os.path.isfile(path):
        return {"schema_version": SCHEMA_VERSION, "revision": 0, "entries": []}
    raw = open(path, "rb").read()
    if len(raw) > MAX_LEDGER_BYTES:
        raise ef.SafetyLimitError("the implementation ledger is too large")
    try:
        doc = json.loads(raw.decode("utf-8"), parse_constant=cr._reject_constant)
    except Exception:
        raise sg.StoppedError("the implementation ledger is not readable JSON")
    if not isinstance(doc, dict) or not isinstance(doc.get("entries"), list):
        raise sg.StoppedError("the implementation ledger is malformed")
    return doc


def verify_ledger(doc):
    """Every entry must chain to the one before it, and settle a task once."""
    problems = []
    # A task id legitimately appears TWICE: once as the assignment, once as its
    # outcome. What must never repeat is either of those on its own.
    assigned = set()
    claimed = set()
    settled = set()
    previous = "0" * 64
    for index, entry in enumerate(doc.get("entries", []), start=1):
        if entry.get("sequence") != index:
            problems.append((index, "entry %d is out of sequence" % index))
        if entry.get("previous_sha256") != previous:
            problems.append((index, "entry %d breaks the hash chain" % index))
        task_id = entry.get("task_id")
        if is_task(entry):
            if task_id in assigned:
                problems.append((index, "task %s is assigned more than once"
                                 % task_id))
            assigned.add(task_id)
        elif is_claim(entry):
            if task_id in claimed:
                problems.append((index, "task %s is claimed more than once"
                                 % task_id))
            if task_id not in assigned:
                problems.append((index, "entry %d claims a task that was never "
                                        "assigned" % index))
            claimed.add(task_id)
        elif is_outcome(entry):
            if task_id in settled:
                problems.append((index, "task %s is settled more than once"
                                 % task_id))
            if task_id not in assigned:
                problems.append((index, "entry %d settles a task that was "
                                        "never assigned" % index))
            if task_id not in claimed:
                problems.append((index, "entry %d settles a task whose attempt "
                                        "was never claimed" % index))
            settled.add(task_id)
        else:
            problems.append((index, "entry %d has an unknown message type"
                             % index))
        previous = hashlib.sha256(cr.canonical_bytes(entry)).hexdigest()
    return problems


def settled_task_ids(doc):
    """Only an OUTCOME settles a task. A task entry does not settle itself."""
    return {entry.get("task_id") for entry in doc.get("entries", [])
            if is_outcome(entry)}


def claimed_task_ids(doc):
    return {entry.get("task_id") for entry in doc.get("entries", [])
            if is_claim(entry)}


def unsettled_claims(doc):
    """Attempts that were spent but never settled -- a crash, almost always.

    These are never re-run automatically. They are reported so a person can
    decide, because the attempt is already gone and repeating it would spend a
    second one on work that may well have happened.
    """
    return sorted(claimed_task_ids(doc) - settled_task_ids(doc))


def record_outcome(root, task, category, exit_code, detail, changed,
                   max_changed=64):
    """Append exactly one outcome for a task.

    Recording is what stops a spent attempt from being invisible, and what
    stops a recovery re-running work that already ran. A task that already has
    an outcome is never given a second one.
    """
    if category not in OUTCOME_CATEGORIES:
        _bad("unknown outcome category %r" % category)
    with _LedgerLock(root):
        doc = read_ledger(root)
        problems = verify_ledger(doc)
        if problems:
            raise sg.StoppedError("the implementation ledger does not verify: %s"
                                  % problems[0][1])
        if task["task_id"] in settled_task_ids(doc):
            return "already-recorded"
        if task["task_id"] not in claimed_task_ids(doc):
            # An outcome without a claim would mean the attempt was spent
            # without ever being announced, which is the failure this design
            # exists to prevent.
            raise sg.StoppedError("that task's attempt was never claimed; "
                                  "refusing to settle an unannounced attempt")

        _append_entry(root, doc, {
            "schema_version": SCHEMA_VERSION,
            "entry_id": str(uuid.uuid4()),
            "sequence": len(doc["entries"]) + 1,
            "previous_sha256": "0" * 64,        # _append_entry sets both
            "created_at": datetime.now(timezone.utc)
                                  .strftime("%Y-%m-%dT%H:%M:%SZ"),
            "message_type": OUTCOME_TYPE,
            "task_id": task["task_id"],
            "phase": task["phase"],
            "head": task["head"],
            "outcome": category,
            "exit_code": int(exit_code),
            "detail": (detail or "")[:2000],
            "changed_paths": sorted(changed)[:max_changed],
            "attempt_consumed": True,
            "recorded_by": "codex_implementation_runner",
        })
        return "recorded"


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def build_parser():
    parser = argparse.ArgumentParser(
        prog="codex_implementation_runner",
        description="Start Codex exactly once for one pending implementation "
                    "task, contained by the operating system. It commits "
                    "nothing, pushes nothing, and authorizes nothing.")
    parser.add_argument("operation", choices=OPERATIONS)
    parser.add_argument("--format", required=True, choices=("markdown", "json"))
    parser.add_argument("--policy")
    parser.add_argument("--relay-policy")
    parser.add_argument("--schema")
    parser.add_argument("--repo")
    parser.add_argument("--registry")
    parser.add_argument("--ledger",
                        help="directory holding the implementation ledger")
    parser.add_argument("--coordinator-session-id",
                        help="the paused Claude coordinator session id")
    parser.add_argument("--worker-session-id",
                        help="the active Codex worker session id")
    parser.add_argument("--task-id", help="submit-task: the task's stable id")
    parser.add_argument("--phase", help="submit-task: the approved phase")
    parser.add_argument("--assign", action="append", default=None,
                        help="submit-task: one repository-relative path the "
                             "task may modify; repeat for more")
    parser.add_argument("--instruction", help="submit-task: what to do")
    parser.add_argument("--acceptance", help="submit-task: how it is judged")
    parser.add_argument("--settle-task-id",
                        help="settle-claim: the crashed task to close out")
    parser.add_argument("--settle-reason",
                        help="settle-claim: why, in one sentence")
    return parser


def _emit(doc, fmt):
    if fmt == "json":
        sys.stdout.write(json.dumps(doc, indent=2, sort_keys=True) + "\n")
    else:
        sys.stdout.write("# %s\n\n" % doc.get("phase", "implementation"))
        for row in doc.get("checks", []):
            sys.stdout.write("- **%s** %s -- %s: %s\n"
                             % (row["id"], row["status"], row["label"],
                                row["evidence"]))
    sys.stdout.flush()


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0].lower() in FORBIDDEN_VERBS:
        sys.stderr.write("codex_implementation_runner: %r is not an operation; "
                         "this tool implements one approved task and "
                         "authorizes nothing\n" % argv[0])
        return EXIT_INVALID

    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return EXIT_INVALID if exc.code else EXIT_OK

    checks = []
    exit_code = EXIT_OK
    response_path = None
    attempt = {"spawned": False, "recorded": False, "task": None,
               "root": None, "exit_code": -1}
    restore = {}
    staging = None

    def _terminate(category, detail, changed=()):
        if not attempt["spawned"] or attempt["recorded"]:
            return
        if not attempt["task"] or not attempt["root"]:
            return
        attempt["recorded"] = True
        try:
            status = record_outcome(attempt["root"], attempt["task"], category,
                                    attempt["exit_code"], detail, changed)
        except Exception:
            checks.append(_chk("W9", "outcome", "fail",
                               "a spent attempt could not be recorded"))
            return
        checks.append(_chk("W9", "outcome",
                           "pass" if status == "recorded" else "warning",
                           "%s (%s); the task is settled and permits no retry"
                           % (category, status)))

    try:
        policy = validate_policy(load_policy(args.policy))
        checks.append(_chk("P1", "policy", "pass", policy["policy_name"]))
        checks.append(_chk("P2", "containment", "informational",
                           "L1 operating-system sandbox rooted at the assigned "
                           "worktree; L2 a staging workspace holding ONLY the "
                           "assigned paths, so a protected path is absent "
                           "rather than read-only; L3 coordinator scope check "
                           "on a handle proven to resolve inside the worktree. "
                           "L3 alone is not containment."))

        if args.operation == "validate-policy":
            checks.append(_chk("P3", "reviewer", "pass",
                               "the read-only review runner is a separate "
                               "component and is not modified by this tool"))
        else:
            if not args.repo or not args.registry or not args.ledger:
                _bad("this operation requires --repo, --registry and --ledger")
            repo_obs = cr.observe_repository(args.repo)
            registry = sr.read_registry(args.registry)
            root = os.path.abspath(args.ledger)
            ledger = read_ledger(root)
            problems = verify_ledger(ledger)
            if problems:
                raise sg.StoppedError("the implementation ledger does not "
                                      "verify: %s" % problems[0][1])
            checks.append(_chk("W0", "ledger", "pass",
                               "revision %d, %d entr(ies), chain verified"
                               % (ledger.get("revision", 0),
                                  len(ledger["entries"]))))

            if args.operation == "submit-task":
                for name, value in (("--task-id", args.task_id),
                                    ("--phase", args.phase),
                                    ("--instruction", args.instruction),
                                    ("--acceptance", args.acceptance)):
                    if not value:
                        _bad("submit-task requires %s" % name)
                if not args.assign:
                    _bad("submit-task requires at least one --assign path")
                entry = record_task(root, args.task_id, args.phase, repo_obs,
                                    registry["revision"], args.assign,
                                    args.instruction, args.acceptance, policy)
                checks.append(_chk("W1", "task recorded", "pass",
                                   "%s, sequence %d, %d assigned path(s)"
                                   % (entry["task_id"], entry["sequence"],
                                      len(entry["assigned_paths"]))))
                checks.append(_chk("K1", "authority", "warning",
                                   policy["non_authorization_sentence"]))
                doc = {"schema_version": SCHEMA_VERSION,
                       "phase": "codex implementation runner",
                       "overall_status": "passed", "checks": checks}
                _emit(doc, args.format)
                return EXIT_OK

            if args.operation == "settle-claim":
                # A person closes out a crashed attempt. This is deliberately
                # NOT automatic: the attempt was already spent, and re-running
                # it would spend a second one on work that may have happened.
                stale = unsettled_claims(ledger)
                if not stale:
                    checks.append(_chk("W1", "settle-claim", "informational",
                                       "no claimed attempt is unsettled"))
                else:
                    if not args.settle_task_id:
                        _bad("settle-claim requires --settle-task-id; "
                             "unsettled: %s" % ", ".join(stale))
                    if args.settle_task_id not in stale:
                        _bad("that task has no unsettled claim")
                    if not args.settle_reason:
                        _bad("settle-claim requires --settle-reason")
                    target = next(e for e in ledger["entries"]
                                  if is_task(e)
                                  and e["task_id"] == args.settle_task_id)
                    record_outcome(root, target, "abandoned_after_crash", -1,
                                   rr.sanitize_own_message(args.settle_reason),
                                   [])
                    checks.append(_chk("W1", "settle-claim", "pass",
                                       "task %s closed out as abandoned; it is "
                                       "not re-run" % args.settle_task_id))
                checks.append(_chk("K1", "authority", "warning",
                                   policy["non_authorization_sentence"]))
                doc = {"schema_version": SCHEMA_VERSION,
                       "phase": "codex implementation runner",
                       "overall_status": "passed", "checks": checks}
                _emit(doc, args.format)
                return EXIT_OK

            task = find_pending_task(ledger)
            validate_task(task, policy)
            attempt["task"], attempt["root"] = task, root
            checks.append(_chk("W1", "task", "pass",
                               "%s, %d assigned path(s)"
                               % (task["task_id"], len(task["assigned_paths"]))))

            now = datetime.now(timezone.utc)
            pre = check_preconditions(task, repo_obs, registry,
                                      args.coordinator_session_id,
                                      args.worker_session_id, policy, now)
            if pre:
                raise sg.StoppedError("; ".join(pre))
            checks.append(_chk("W2", "preconditions", "pass",
                               "worktree, sessions, and git-metadata isolation "
                               "all verified"))

            executable = rr.resolve_codex(rr.load_policy())
            env = rr.child_environment(rr.load_policy())
            checks.append(_chk("W3", "child environment", "pass",
                               "%d allowlisted name(s); values never recorded"
                               % len(env)))

            if args.operation == "inspect":
                checks.append(_chk("W4", "inspect", "informational",
                                   "no child was started"))
            else:
                # L2: the child runs in a workspace holding the assigned paths
                # and nothing else. A protected file is ABSENT, so it cannot be
                # written, replaced, deleted, or chmod-ed, and L1 denies
                # reaching outside the root to find the original. Failure to
                # build it refuses the run.
                staging, staged_files = build_staging(
                    args.repo, task["assigned_paths"], policy)
                checks.append(_chk("W5", "staging workspace", "pass",
                                   "%d assigned file(s) staged; every other "
                                   "path is absent, not merely read-only"
                                   % len(staged_files)))

                # Defence in depth over the REAL worktree, and fail-closed.
                # Not a boundary: a same-user process can clear an attribute.
                restore = protect_paths(args.repo, policy,
                                        task["assigned_paths"])
                checks.append(_chk("W5b", "worktree defence in depth", "pass",
                                   "%d file(s) read-only in the real worktree "
                                   "(defence in depth, not the boundary)"
                                   % len(restore)))

                response_path = rr.make_response_path(root)
                prompt = build_prompt(task, policy)
                argv_used = build_argv(executable, staging,
                                       response_path, policy)
                checks.append(_chk("W6", "argument array", "informational",
                                   "codex exec -C <staging> -s workspace-write "
                                   "-c windows.sandbox=\"elevated\" "
                                   "-c approval_policy=\"never\" -m %s "
                                   "--ephemeral --ignore-user-config "
                                   "-o <private temp> -"
                                   % policy["fixed_flags"]["model"]))

                # DURABLE, and before the child exists. A crash after this
                # point leaves a claim on disk, so recovery reports a spent
                # attempt instead of quietly spending a second one.
                claim_attempt(root, task)
                checks.append(_chk("W7", "attempt claimed", "warning",
                                   "the attempt for task %s is claimed on disk "
                                   "and is now consumed; a crash from here on "
                                   "will NOT be re-run automatically"
                                   % task["task_id"]))
                result = rr.invoke_once(argv_used, prompt, env,
                                        {"limits": {
                                            "max_runtime_seconds":
                                                policy["limits"]["max_runtime_seconds"],
                                            "max_captured_stream_bytes":
                                                policy["limits"]["max_captured_stream_bytes"],
                                        }}, attempt)
                attempt["exit_code"] = result["returncode"] \
                    if result["returncode"] is not None else -1
                diag = rr.sanitize_diagnostic(
                    (result.get("stderr") or b"").decode("utf-8", "replace"),
                    prompt)

                failures = restore_paths(restore)
                checks.append(_chk("W8", "protected paths restored",
                                   "pass" if not failures else "fail",
                                   "%d restored, %d could not be"
                                   % (len(restore) - len(failures), len(failures))))

                touched = protected_paths_touched(args.repo, restore)
                if touched:
                    revert_paths(args.repo, touched)
                    _terminate("protected_path_touched",
                               "a protected path was modified and was reverted",
                               touched)
                    raise sg.StoppedError("a protected path was modified")

                if result["timed_out"]:
                    attempt["exit_code"] = -1
                    _terminate("timeout", diag or "the child exceeded its runtime")
                    raise sg.StoppedError("codex timed out; the attempt is consumed")
                if result["returncode"] != 0:
                    _terminate("nonzero_exit", diag or "the child failed")
                    raise sg.StoppedError("codex exited non-zero; the attempt "
                                          "is consumed")

                # Anything the run produced lives in staging. verify_staging
                # refuses a path outside the assignment before a single byte
                # reaches the real worktree.
                try:
                    applied = apply_staged(staging, args.repo,
                                           task["assigned_paths"], policy)
                except ProtectionFailed as exc:
                    _terminate("out_of_scope", rr.sanitize_own_message(str(exc)))
                    raise sg.StoppedError("the run produced a path outside its "
                                          "assignment; nothing was applied")
                checks.append(_chk("W9b", "applied", "pass",
                                   "%d assigned file(s) copied back"
                                   % len(applied)))

                stray = out_of_scope_changes(args.repo, task["assigned_paths"])
                if stray:
                    revert_paths(args.repo, stray)
                    _terminate("out_of_scope",
                               "changes outside the assigned paths were reverted",
                               stray)
                    raise sg.StoppedError("the run wrote outside its assignment")

                changed = changed_paths(args.repo)
                if len(changed) > policy["limits"]["max_changed_files"]:
                    raise ef.SafetyLimitError("too many files changed")
                if not changed:
                    _terminate("no_change", "the child changed nothing")
                else:
                    _terminate("completed",
                               "changes are inside the assignment and await "
                               "the coordinator's tests, review and commit",
                               changed)
                checks.append(_chk("W10", "scope", "pass",
                                   "%d changed path(s), all inside the "
                                   "assignment" % len(changed)))

        checks.append(_chk("K1", "authority", "warning",
                           policy["non_authorization_sentence"]))
        checks.append(_chk("K2", "commit", "warning",
                           "the model did not commit and cannot; the "
                           "coordinator validates and commits"))

    except ef.SafetyLimitError as exc:
        _terminate("internal_error", rr.sanitize_own_message(str(exc)))
        checks.append(_chk("Z0", "safety limit", "stopped",
                           ef.sanitize_text(str(exc))))
        exit_code = EXIT_LIMIT
    except ProtectionFailed as exc:
        # Protection could not be established. If the child never started this
        # spends nothing; if it did, _terminate records the spent attempt.
        _terminate("internal_error", rr.sanitize_own_message(str(exc)))
        checks.append(_chk("Z3", "protection", "stopped",
                           ef.sanitize_text(str(exc))))
        exit_code = EXIT_STOPPED
    except LedgerBusy as exc:
        checks.append(_chk("Z4", "ledger busy", "stopped",
                           ef.sanitize_text(str(exc))))
        exit_code = EXIT_STOPPED
    except (ImplementationError, ef.ValidationError) as exc:
        _terminate("internal_error", rr.sanitize_own_message(str(exc)))
        sys.stderr.write("codex_implementation_runner: invalid input: %s\n"
                         % ef.sanitize_text(str(exc)))
        rr._remove_own(response_path)
        return EXIT_INVALID
    except sg.StoppedError as exc:
        _terminate("state_changed", rr.sanitize_own_message(str(exc)))
        checks.append(_chk("Z0", "stopped", "stopped", ef.sanitize_text(str(exc))))
        exit_code = EXIT_STOPPED
    except OSError:
        _terminate("internal_error", "a filesystem or process operation failed")
        checks.append(_chk("Z1", "stopped", "stopped",
                           "a filesystem or process operation failed"))
        exit_code = EXIT_STOPPED
    except Exception:
        _terminate("internal_error",
                   "an unexpected error occurred after the child started")
        checks.append(_chk("Z2", "stopped", "stopped",
                           "an unexpected error occurred; the run was abandoned"))
        exit_code = EXIT_STOPPED
    finally:
        if restore:
            restore_paths(restore)
        if staging:
            discard_staging(staging)
        rr._remove_own(response_path)

    doc = {"schema_version": SCHEMA_VERSION,
           "phase": "codex implementation runner",
           "overall_status": ("passed" if exit_code == EXIT_OK
                              else "failed"),
           "checks": checks}
    _emit(doc, args.format)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
