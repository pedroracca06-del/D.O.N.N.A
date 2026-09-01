#!/usr/bin/env python
"""staleness_guard.py -- read-only repository staleness observer.

Compares live repository state against an explicit baseline document and renders
the result through the Evidence Formatter, so a report can never claim a state
that was not re-measured at the moment of reporting.

BOUNDARY:
  * Only a fixed, internally defined allowlist of read-only Git subcommands is
    ever run. See ``_GIT_READ_ONLY``. A baseline can never supply a command,
    an argument, a script, a hook, or an environment value.
  * Every invocation passes an argument array; ``shell=True`` is never used.
  * No mutating Git subcommand appears anywhere in command construction:
    no fetch, pull, push, merge, rebase, checkout, switch, reset, restore,
    clean, add, commit, tag/branch mutation, submodule update, config write,
    maintenance, or gc.
  * ``--no-optional-locks`` is used so inspection does not refresh or rewrite
    the index.
  * No network by default. ``--check-remote <name>`` opts in to exactly one
    additional command, ``git ls-remote --heads <validated-remote>``, which
    reads refs without fetching and updates nothing.
  * Writes no file. Output goes to stdout; errors go to stderr.
  * Standard library only.

PRIVACY: the repository root is normalized to ``${REPO}``, home directories to
``${HOME}``, and remote URLs are never printed. The permission file is inspected
only for its SHA-256 and its parsed array lengths -- never its entries. Tracked
files are compared by Git blob ID, not by on-disk hash, so ``core.autocrlf``
cannot produce a false alarm.

Exit codes:
  0  every required check is fresh
  1  observation completed and staleness was detected
  2  invalid CLI usage, or baseline schema/content validation failure
  3  safety-limit rejection (size, depth, or collection count)
  4  observation stopped or unavailable, including an unreachable remote
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import evidence_formatter as ef  # noqa: E402  (sibling module, stdlib-only)

sys.path.pop(0)

SCHEMA_VERSION = 1
GIT_TIMEOUT_SECONDS = 30
_OID_RE = re.compile(r"^[0-9a-f]{40}$|^[0-9a-f]{64}$")
_REMOTE_NAME_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")

REQUIRED_FIELDS = ("schema_version", "expected_branch", "expected_head")
OPTIONAL_FIELDS = (
    "expected_local_refs", "expected_remote_refs", "require_clean_index",
    "require_clean_worktree", "expected_tracked_blobs",
    "expected_permission_state", "expected_submodule_gitlinks",
    "expected_worktree_identity", "notes",
)

# The complete set of Git subcommands this tool may ever run. Anything not
# listed here cannot be constructed, and every entry is read-only.
_GIT_READ_ONLY = frozenset({
    "rev-parse", "status", "ls-files", "ls-tree", "show-ref",
    "remote", "ls-remote", "diff",
})


class StoppedError(Exception):
    """Observation could not be completed -> exit 4."""


# --------------------------------------------------------------------------
# Git access
# --------------------------------------------------------------------------

def _git(repo: str, args: list, timeout: int = GIT_TIMEOUT_SECONDS):
    """Run one allowlisted read-only Git command. Never uses a shell."""
    if not args or args[0] not in _GIT_READ_ONLY:
        raise StoppedError("refused a git subcommand outside the read-only allowlist")
    cmd = ["git", "--no-optional-locks", "-C", repo] + args
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise StoppedError("a git command exceeded its timeout")
    except OSError:
        raise StoppedError("git could not be executed")
    out = proc.stdout.decode("utf-8", "replace")
    err = ef.sanitize_text(proc.stderr.decode("utf-8", "replace").strip())
    return proc.returncode, out, err


def _git_ok(repo: str, args: list) -> str:
    rc, out, err = _git(repo, args)
    if rc != 0:
        raise StoppedError("git %s failed: %s" % (args[0], err[:120]))
    return out.strip()


# --------------------------------------------------------------------------
# Baseline validation
# --------------------------------------------------------------------------

def _bad(msg: str):
    raise ef.ValidationError(msg)


def _check_rel_path(path: str, what: str) -> None:
    if not isinstance(path, str) or not path.strip():
        _bad("%s must be a non-empty string" % what)
    norm = path.replace("\\", "/")
    if norm.startswith("/") or re.match(r"^[A-Za-z]:", norm):
        _bad("%s must be repository-relative, not absolute" % what)
    if ".." in norm.split("/"):
        _bad("%s must not contain a parent-directory traversal" % what)


def _check_oid(value: str, what: str) -> None:
    if not isinstance(value, str) or not _OID_RE.match(value.strip()):
        _bad("%s must be a full git object id" % what)


def _check_no_dupe_keys(mapping: dict, what: str) -> None:
    seen = {}
    for key in mapping:
        folded = key.replace("\\", "/").lower()
        if folded in seen:
            _bad("%s contains duplicate keys after case normalization" % what)
        seen[folded] = key


def validate_baseline(doc) -> dict:
    if not isinstance(doc, dict):
        _bad("the baseline must be a JSON object")
    for field in REQUIRED_FIELDS:
        if field not in doc:
            _bad("missing required field: %s" % field)
    if doc["schema_version"] != SCHEMA_VERSION:
        _bad("unsupported schema_version (expected %d)" % SCHEMA_VERSION)

    unknown = set(doc) - set(REQUIRED_FIELDS) - set(OPTIONAL_FIELDS)
    if unknown:
        _bad("unrecognized baseline field(s): %s" % ", ".join(sorted(unknown)))

    if not isinstance(doc["expected_branch"], str) or not doc["expected_branch"].strip():
        _bad("expected_branch must be a non-empty string")
    _check_oid(doc["expected_head"], "expected_head")

    for field in ("expected_local_refs", "expected_remote_refs"):
        if field in doc:
            refs = doc[field]
            if not isinstance(refs, dict):
                _bad("%s must be a mapping" % field)
            _check_no_dupe_keys(refs, field)
            for name, oid in refs.items():
                if not isinstance(name, str) or not name.strip():
                    _bad("%s contains an invalid ref name" % field)
                _check_oid(oid, "%s[%s]" % (field, name))

    for field in ("require_clean_index", "require_clean_worktree"):
        if field in doc and not isinstance(doc[field], bool):
            _bad("%s must be a boolean" % field)

    if "expected_tracked_blobs" in doc:
        blobs = doc["expected_tracked_blobs"]
        if not isinstance(blobs, dict):
            _bad("expected_tracked_blobs must be a mapping")
        _check_no_dupe_keys(blobs, "expected_tracked_blobs")
        for path, oid in blobs.items():
            _check_rel_path(path, "expected_tracked_blobs path")
            _check_oid(oid, "expected_tracked_blobs[%s]" % path)

    if "expected_permission_state" in doc:
        ps = doc["expected_permission_state"]
        if not isinstance(ps, dict):
            _bad("expected_permission_state must be a mapping")
        allowed = {"path", "sha256", "allow", "ask", "deny"}
        extra = set(ps) - allowed
        if extra:
            _bad("unrecognized expected_permission_state field(s): %s"
                 % ", ".join(sorted(extra)))
        if "path" not in ps:
            _bad("expected_permission_state requires a path")
        _check_rel_path(ps["path"], "expected_permission_state path")
        if "sha256" in ps and not re.match(r"^[0-9a-f]{64}$", str(ps["sha256"])):
            _bad("expected_permission_state sha256 must be a 64-character digest")
        for k in ("allow", "ask", "deny"):
            if k in ps and (not isinstance(ps[k], int) or isinstance(ps[k], bool)):
                _bad("expected_permission_state %s must be an integer" % k)

    if "expected_submodule_gitlinks" in doc:
        subs = doc["expected_submodule_gitlinks"]
        if not isinstance(subs, dict):
            _bad("expected_submodule_gitlinks must be a mapping")
        _check_no_dupe_keys(subs, "expected_submodule_gitlinks")
        for path, oid in subs.items():
            _check_rel_path(path, "expected_submodule_gitlinks path")
            _check_oid(oid, "expected_submodule_gitlinks[%s]" % path)

    if "expected_worktree_identity" in doc:
        if not isinstance(doc["expected_worktree_identity"], str):
            _bad("expected_worktree_identity must be a string")

    if "notes" in doc and not isinstance(doc["notes"], list):
        _bad("notes must be a list")
    return doc


# --------------------------------------------------------------------------
# Repository resolution
# --------------------------------------------------------------------------

def resolve_repo(path: str):
    """Return (canonical_top_level, worktree_identity). Never searches beyond
    git's own top-level resolution."""
    if not os.path.isdir(path):
        raise StoppedError("the supplied repository path does not exist")
    rc, out, err = _git(path, ["rev-parse", "--show-toplevel"])
    if rc != 0 or not out.strip():
        raise StoppedError("the supplied path is not a git worktree")
    top = os.path.realpath(out.strip())
    return top, os.path.basename(top)


# --------------------------------------------------------------------------
# Checks
# --------------------------------------------------------------------------

def _chk(cid, label, ok, evidence, stopped=False):
    return {"id": cid, "label": label,
            "status": "stopped" if stopped else ("pass" if ok else "fail"),
            "evidence": evidence}


def observe(repo: str, identity: str, base: dict, remote: str | None) -> list:
    checks = []

    checks.append(_chk("A01", "repository identity", True,
                       "resolved worktree ${REPO} (%s)" % identity))

    branch = _git_ok(repo, ["rev-parse", "--abbrev-ref", "HEAD"])
    checks.append(_chk("A02", "current branch",
                       branch == base["expected_branch"],
                       "expected %s, observed %s" % (base["expected_branch"], branch)))

    head = _git_ok(repo, ["rev-parse", "HEAD"])
    checks.append(_chk("A03", "current HEAD",
                       head == base["expected_head"],
                       "expected %s, observed %s" % (base["expected_head"], head)))

    if "expected_local_refs" in base:
        actual = {}
        for line in _git_ok(repo, ["show-ref"]).splitlines():
            parts = line.split(" ", 1)
            if len(parts) == 2:
                actual[parts[1].strip()] = parts[0].strip()
        for i, (name, oid) in enumerate(sorted(base["expected_local_refs"].items())):
            seen = actual.get(name)
            checks.append(_chk("B%02d" % (i + 1), "local ref %s" % name,
                               seen == oid,
                               "expected %s, observed %s" % (oid, seen or "absent")))

    if base.get("require_clean_index"):
        staged = [l for l in _git_ok(repo, ["diff", "--cached", "--name-only"]).splitlines() if l.strip()]
        checks.append(_chk("C01", "index cleanliness", not staged,
                           "staged paths: %d" % len(staged)))

    if base.get("require_clean_worktree"):
        # Porcelain omits ignored files by default, so ignored artifacts never
        # count as drift.
        entries = [l for l in _git_ok(repo, ["status", "--porcelain", "-uall"]).splitlines() if l.strip()]
        modified = [l for l in entries if not l.startswith("?? ")]
        untracked = [l for l in entries if l.startswith("?? ")]
        checks.append(_chk("C02", "working-tree cleanliness", not entries,
                           "tracked modifications: %d, visible untracked: %d"
                           % (len(modified), len(untracked))))

    if "expected_tracked_blobs" in base:
        for i, (path, oid) in enumerate(sorted(base["expected_tracked_blobs"].items())):
            rc, out, _ = _git(repo, ["rev-parse", "HEAD:%s" % path])
            seen = out.strip() if rc == 0 else None
            checks.append(_chk("D%02d" % (i + 1), "tracked blob %s" % path,
                               seen == oid,
                               "expected %s, observed %s" % (oid, seen or "absent")))

    if "expected_permission_state" in base:
        ps = base["expected_permission_state"]
        target = os.path.join(repo, ps["path"].replace("\\", "/"))
        if not os.path.isfile(target):
            checks.append(_chk("E01", "permission file present", False,
                               "expected at ${REPO}/%s, not found" % ps["path"]))
        else:
            digest = hashlib.sha256(open(target, "rb").read()).hexdigest()
            if "sha256" in ps:
                checks.append(_chk("E01", "permission file hash",
                                   digest == ps["sha256"],
                                   "expected %s, observed %s" % (ps["sha256"], digest)))
            wanted = {k: ps[k] for k in ("allow", "ask", "deny") if k in ps}
            if wanted:
                try:
                    perms = json.load(open(target, encoding="utf-8"))["permissions"]
                    counts = {k: len(perms.get(k, [])) for k in wanted}
                except Exception:
                    counts = None
                if counts is None:
                    checks.append(_chk("E02", "permission counts", False,
                                       "permission file could not be parsed"))
                else:
                    checks.append(_chk("E02", "permission counts", counts == wanted,
                                       "expected %s, observed %s"
                                       % (json.dumps(wanted, sort_keys=True),
                                          json.dumps(counts, sort_keys=True))))

    if "expected_submodule_gitlinks" in base:
        for i, (path, oid) in enumerate(sorted(base["expected_submodule_gitlinks"].items())):
            rc, out, _ = _git(repo, ["ls-tree", "HEAD", path])
            seen = None
            if rc == 0 and out.strip():
                parts = out.split()
                if len(parts) >= 3:
                    seen = parts[2]
            checks.append(_chk("F%02d" % (i + 1), "submodule gitlink %s" % path,
                               seen == oid,
                               "expected %s, observed %s" % (oid, seen or "absent")))

    if "expected_worktree_identity" in base:
        checks.append(_chk("G01", "worktree identity",
                           identity == base["expected_worktree_identity"],
                           "expected %s, observed %s"
                           % (base["expected_worktree_identity"], identity)))

    if remote is not None:
        checks.extend(_observe_remote(repo, base, remote))
    return checks


def _observe_remote(repo: str, base: dict, remote: str) -> list:
    """The ONLY networked path. Reads refs; fetches and updates nothing."""
    checks = []
    if not _REMOTE_NAME_RE.match(remote) or "://" in remote or "@" in remote:
        return [_chk("R00", "remote name", False,
                     "the --check-remote value must be a configured remote name, not a URL")]
    configured = _git_ok(repo, ["remote"]).split()
    if remote not in configured:
        return [_chk("R00", "remote name", False,
                     "remote is not configured in this repository")]

    rc, out, err = _git(repo, ["ls-remote", "--heads", remote])
    if rc != 0:
        return [_chk("R00", "remote reachable", False,
                     "remote could not be read: %s" % (err[:120] or "unavailable"),
                     stopped=True)]

    actual = {}
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) == 2 and _OID_RE.match(parts[0].strip()):
            actual[parts[1].strip()] = parts[0].strip()

    expected = base.get("expected_remote_refs", {})
    if not expected:
        checks.append(_chk("R00", "remote refs observed", True,
                           "observed %d head refs; no expectation supplied" % len(actual)))
        return checks
    for i, (name, oid) in enumerate(sorted(expected.items())):
        seen = actual.get(name)
        checks.append(_chk("R%02d" % (i + 1), "remote ref %s" % name,
                           seen == oid,
                           "expected %s, observed %s" % (oid, seen or "absent")))
    return checks


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def _read_baseline(path):
    if path is None:
        raw = sys.stdin.buffer.read()
    else:
        try:
            with open(path, "rb") as fh:
                raw = fh.read(ef.MAX_INPUT_BYTES + 1)
        except OSError:
            raise ef.ValidationError("baseline file could not be read")
    if len(raw) > ef.MAX_INPUT_BYTES:
        raise ef.SafetyLimitError(
            "baseline exceeds the maximum accepted size of %d bytes" % ef.MAX_INPUT_BYTES)
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise ef.ValidationError("baseline is not valid UTF-8")
    try:
        return json.loads(text, parse_constant=_reject_constant)
    except ef.ValidationError:
        raise
    except Exception:
        raise ef.ValidationError("baseline is not valid JSON")


def _reject_constant(name):
    raise ef.ValidationError("non-standard numeric value is not permitted")


def _emit(doc, fmt):
    norm = ef.normalize(doc)
    text = ef.render_markdown(norm) if fmt == "markdown" else ef.render_json(norm)
    sys.stdout.buffer.write(text.encode("utf-8"))
    sys.stdout.buffer.flush()
    return norm


def _err(text):
    sys.stderr.buffer.write(text.encode("utf-8"))
    sys.stderr.buffer.flush()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="staleness_guard",
        description="Compare live repository state with a baseline. Read-only.")
    parser.add_argument("--repo", default=".", help="path to a git worktree")
    parser.add_argument("--format", choices=("markdown", "json"), required=True)
    parser.add_argument("--input", default=None,
                        help="baseline JSON file; stdin if omitted")
    parser.add_argument("--check-remote", default=None, metavar="REMOTE",
                        help="also read refs from a configured remote (no fetch)")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return 0 if exc.code == 0 else 2

    try:
        base = _read_baseline(args.input)
        ef.enforce_limits(base)
        validate_baseline(base)
    except ef.SafetyLimitError as exc:
        _err("staleness_guard: safety limit: %s\n" % ef.sanitize_text(str(exc)))
        return 3
    except ef.ValidationError as exc:
        _err("staleness_guard: invalid baseline: %s\n" % ef.sanitize_text(str(exc)))
        return 2

    stopped_reason = None
    try:
        repo, identity = resolve_repo(args.repo)
        checks = observe(repo, identity, base, args.check_remote)
    except StoppedError as exc:
        stopped_reason = ef.sanitize_text(str(exc))
        checks = [_chk("A00", "observation", False, stopped_reason, stopped=True)]

    doc = {
        "schema_version": ef.SCHEMA_VERSION,
        "phase": "staleness guard",
        "scope": "repository freshness vs supplied baseline",
        "checks": checks,
    }
    if "notes" in base:
        doc["notes"] = base["notes"]

    try:
        norm = _emit(doc, args.format)
    except (ef.ValidationError, ef.SafetyLimitError) as exc:
        _err("staleness_guard: %s\n" % ef.sanitize_text(str(exc)))
        return 2

    overall = norm["overall_status"]
    if overall == "stopped":
        return 4
    if overall == "failed":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
