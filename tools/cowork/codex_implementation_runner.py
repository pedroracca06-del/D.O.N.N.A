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

  L2  Protected in-repo paths are made read-only for the duration of the run
      and restored afterwards. These are inside the sandbox root, so L1 cannot
      speak for them; a filesystem attribute can.

  L3  The coordinator diffs the result and refuses to commit anything outside
      the assigned task paths, reverting it instead.

L3 alone would not be containment, and is not treated as such. It bounds task
paths inside a tree the operating system has already contained.

The model never commits, never pushes, and never sees git metadata. The
coordinator validates and commits. A verdict, a diff, and a task outcome are
all opinions and evidence offered to a human; none of them authorises anything.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import subprocess
import sys
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

OPERATIONS = ("validate-policy", "inspect", "submit-task", "implement-once")

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
    settled = {e.get("task_id") for e in ledger_doc.get("entries", [])
               if is_outcome(e)}
    pending = [e for e in ledger_doc.get("entries", [])
               if is_task(e) and e.get("task_id") not in settled]
    if not pending:
        raise sg.StoppedError("the ledger holds no pending implementation task")
    if len(pending) > 1:
        raise sg.StoppedError("more than one implementation task is pending; "
                              "the ledger is ambiguous")
    return pending[0]


def record_task(root, task_id, phase, repo_obs, registry_revision,
                assigned_paths, instruction, acceptance, policy,
                assigned_by="claude"):
    """Append one task. The coordinator assigns; the model never self-assigns."""
    doc = read_ledger(root)
    problems = verify_ledger(doc)
    if problems:
        raise sg.StoppedError("the implementation ledger does not verify: %s"
                              % problems[0][1])
    if task_id in {e.get("task_id") for e in doc["entries"]}:
        _bad("that task id is already recorded; a task runs at most once")

    entries = doc["entries"]
    previous = (hashlib.sha256(cr.canonical_bytes(entries[-1])).hexdigest()
                if entries else "0" * 64)
    entry = {
        "schema_version": SCHEMA_VERSION,
        "entry_id": str(uuid.uuid4()),
        "sequence": len(entries) + 1,
        "previous_sha256": previous,
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
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
    entries.append(entry)
    doc["revision"] = doc.get("revision", 0) + 1
    os.makedirs(os.path.abspath(root), exist_ok=True)
    cr._atomic_write(ledger_path(root),
                     json.dumps(doc, indent=2, sort_keys=True).encode("utf-8"))
    return entry


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


def _norm(path):
    """One spelling for a path, so a restore map key always matches."""
    return os.path.normcase(os.path.abspath(path))


def protect_paths(repo, policy, assigned):
    """Make everything outside the assignment read-only. Returns a restore map.

    This is a filesystem control, not a request. The child runs as the same
    user, so this is a guard rail rather than a privilege boundary -- which is
    exactly why it is layer TWO, behind the sandbox, and why the coordinator
    still verifies the result afterwards.
    """
    restore = {}
    for raw in _iter_protected(repo, policy, assigned):
        path = _norm(raw)
        if path in restore:
            continue
        try:
            mode = os.stat(path).st_mode
        except OSError:
            continue
        restore[path] = mode
        try:
            os.chmod(path, mode & ~stat.S_IWRITE)
        except OSError:
            restore.pop(path, None)
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
        elif is_outcome(entry):
            if task_id in settled:
                problems.append((index, "task %s is settled more than once"
                                 % task_id))
            if task_id not in assigned:
                problems.append((index, "entry %d settles a task that was "
                                        "never assigned" % index))
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


def record_outcome(root, task, category, exit_code, detail, changed,
                   max_changed=64):
    """Append exactly one outcome for a task.

    Recording is what stops a spent attempt from being invisible, and what
    stops a recovery re-running work that already ran. A task that already has
    an outcome is never given a second one.
    """
    if category not in OUTCOME_CATEGORIES:
        _bad("unknown outcome category %r" % category)
    doc = read_ledger(root)
    problems = verify_ledger(doc)
    if problems:
        raise sg.StoppedError("the implementation ledger does not verify: %s"
                              % problems[0][1])
    if task["task_id"] in settled_task_ids(doc):
        return "already-recorded"

    entries = doc["entries"]
    previous = (hashlib.sha256(cr.canonical_bytes(entries[-1])).hexdigest()
                if entries else "0" * 64)
    entry = {
        "schema_version": SCHEMA_VERSION,
        "entry_id": str(uuid.uuid4()),
        "sequence": len(entries) + 1,
        "previous_sha256": previous,
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
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
    }
    entries.append(entry)
    doc["revision"] = doc.get("revision", 0) + 1
    os.makedirs(os.path.abspath(root), exist_ok=True)
    cr._atomic_write(ledger_path(root),
                     json.dumps(doc, indent=2, sort_keys=True).encode("utf-8"))
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
                           "worktree; L2 read-only attribute on protected "
                           "paths; L3 coordinator scope check. L3 alone is not "
                           "containment."))

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
                restore = protect_paths(args.repo, policy,
                                        task["assigned_paths"])
                checks.append(_chk("W5", "protected paths", "pass",
                                   "%d file(s) made read-only for the run"
                                   % len(restore)))

                response_path = rr.make_response_path(root)
                prompt = build_prompt(task, policy)
                argv_used = build_argv(executable, repo_obs["repo"],
                                       response_path, policy)
                checks.append(_chk("W6", "argument array", "informational",
                                   "codex exec -C <worktree> -s workspace-write "
                                   "-c windows.sandbox=\"elevated\" "
                                   "-c approval_policy=\"never\" -m %s "
                                   "--ephemeral --ignore-user-config "
                                   "-o <private temp> -"
                                   % policy["fixed_flags"]["model"]))

                checks.append(_chk("W7", "attempt", "warning",
                                   "the attempt for task %s is now consumed"
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
