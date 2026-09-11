#!/usr/bin/env python
"""worktree_bootstrap_validator.py -- read-only worktree bootstrap validator.

Answers one question: *is this Git worktree safely configured for its declared
NOVA role before an automated session begins?*

It observes and reports. It NEVER:
  * creates or removes a worktree, or creates/switches a branch
  * copies, writes, or edits any file
  * initializes, updates, fetches, or checks out a submodule
  * installs settings, hooks, or permissions
  * stages, commits, fetches, or contacts a remote
  * executes a test command, or anything from the manifest
  * initializes or mutates the Session Registry
  * repairs a mismatch

Every Git call goes through the A7 battery's existing fixed read-only allowlist,
so this tool adds no new Git capability. Rendering goes through the Evidence
Formatter, so the overall verdict is derived from the checks and cannot be
asserted by a caller.

WHY GIT BLOB IDS: tracked files are compared by blob id, never by raw worktree
bytes. Under ``core.autocrlf`` a fresh checkout stores CRLF while an older one
holds LF, so identical content has different file hashes. Blob identity is the
only comparison that is stable across worktrees.

Exit codes:
  0  bootstrap valid
  1  a declared expectation does not hold
  2  invalid CLI, manifest, or record
  3  safety-limit rejection
  4  stopped: observation could not be completed safely
  5  approval required: state is stale or ambiguous
"""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import evidence_formatter as ef       # noqa: E402
import staleness_guard as sg          # noqa: E402
import session_registry as sr         # noqa: E402
import a7_battery as a7               # noqa: E402  (its read-only git allowlist)

sys.path.pop(0)

SCHEMA_VERSION = 1

MANIFEST_REQUIRED = ("schema_version", "worktree_identity", "branch", "head")
MANIFEST_OPTIONAL = (
    "canonical_worktree_path", "git_common_dir_identity", "require_clean_index",
    "require_clean_worktree", "tracked_blobs", "local_ignored_files",
    "permission_state", "submodules", "casing_rules", "forbidden_artifacts",
    "registry", "notes",
)

_OID_RE = re.compile(r"^[0-9a-f]{40}$|^[0-9a-f]{64}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_WILDCARD_RE = re.compile(r"[*?\[]")

# Manifest content that would smuggle in execution, environment, or credentials.
_UNSAFE_VALUE_RE = re.compile(
    r"(?i)(\$\(|`|&&|\|\||;\s*\w+|\bsudo\b|\bcurl\b|\bwget\b|\bbash\b|\bsh\s+-c\b|"
    r"https?://|ssh://|git@|api[_-]?key|secret|token|password|passphrase|"
    r"authorization|bearer|sk-ant-|ghp_|AKIA[0-9A-Z]{16})")

# Git state markers meaning an operation was interrupted.
_INTERRUPTED_MARKERS = (
    "index.lock", "MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD",
    "BISECT_LOG", "rebase-merge", "rebase-apply",
)

# Cowork tooling residue that must not be inherited by a fresh worktree.
_COWORK_RESIDUE = ("*.lock", ".nova-registry-*", "*.tmp")


class StoppedError(Exception):
    """Observation could not be completed -> exit 4."""


# --------------------------------------------------------------------------
# Manifest validation
# --------------------------------------------------------------------------

def _scan_unsafe(node, where="manifest"):
    if isinstance(node, dict):
        for k, v in node.items():
            _scan_unsafe(k, where)
            _scan_unsafe(v, where)
    elif isinstance(node, list):
        for v in node:
            _scan_unsafe(v, where)
    elif isinstance(node, str):
        if _UNSAFE_VALUE_RE.search(node):
            sg._bad("%s contains a command, URL, environment value, or "
                    "credential-shaped string and was rejected" % where)


def _check_paths(values, field):
    if not isinstance(values, (list, dict)):
        sg._bad("%s must be a list or mapping" % field)
    keys = values if isinstance(values, dict) else values
    seen = {}
    for item in keys:
        sg._check_rel_path(item, "%s entry" % field)
        folded = item.replace("\\", "/").lower()
        if folded in seen:
            sg._bad("%s contains duplicate or case-conflicting entries" % field)
        seen[folded] = item


def validate_manifest(doc):
    if not isinstance(doc, dict):
        sg._bad("the manifest must be a JSON object")
    for f in MANIFEST_REQUIRED:
        if f not in doc:
            sg._bad("missing required field: %s" % f)
    if doc["schema_version"] != SCHEMA_VERSION:
        sg._bad("unsupported schema_version (expected %d)" % SCHEMA_VERSION)
    unknown = set(doc) - set(MANIFEST_REQUIRED) - set(MANIFEST_OPTIONAL)
    if unknown:
        sg._bad("unrecognized manifest field(s): %s" % ", ".join(sorted(unknown)))
    _scan_unsafe(doc)

    if not isinstance(doc["worktree_identity"], str) or not doc["worktree_identity"].strip():
        sg._bad("worktree_identity must be a non-empty string")
    if not isinstance(doc["branch"], str) or not doc["branch"].strip():
        sg._bad("branch must be a non-empty string")
    sg._check_oid(doc["head"], "head")

    if "canonical_worktree_path" in doc:
        if not isinstance(doc["canonical_worktree_path"], str):
            sg._bad("canonical_worktree_path must be a string")

    for flag in ("require_clean_index", "require_clean_worktree"):
        if flag in doc and not isinstance(doc[flag], bool):
            sg._bad("%s must be a boolean" % flag)

    if "tracked_blobs" in doc:
        blobs = doc["tracked_blobs"]
        if not isinstance(blobs, dict):
            sg._bad("tracked_blobs must be a mapping")
        _check_paths(blobs, "tracked_blobs")
        for path, oid in blobs.items():
            sg._check_oid(oid, "tracked_blobs[%s]" % path)

    if "local_ignored_files" in doc:
        files = doc["local_ignored_files"]
        if not isinstance(files, dict):
            sg._bad("local_ignored_files must be a mapping")
        _check_paths(files, "local_ignored_files")
        for path, spec in files.items():
            if not isinstance(spec, dict):
                sg._bad("local_ignored_files[%s] must be a mapping" % path)
            extra = set(spec) - {"sha256", "must_be_json", "must_be_ignored",
                                 "must_not_be_tracked"}
            if extra:
                sg._bad("unrecognized local_ignored_files field(s): %s"
                        % ", ".join(sorted(extra)))
            if "sha256" in spec and not _SHA256_RE.match(str(spec["sha256"])):
                sg._bad("local_ignored_files[%s] sha256 must be a 64-char digest" % path)
            for b in ("must_be_json", "must_be_ignored", "must_not_be_tracked"):
                if b in spec and not isinstance(spec[b], bool):
                    sg._bad("local_ignored_files[%s].%s must be a boolean" % (path, b))

    if "permission_state" in doc:
        ps = doc["permission_state"]
        if not isinstance(ps, dict):
            sg._bad("permission_state must be a mapping")
        extra = set(ps) - {"path", "allow", "ask", "deny", "require_no_duplicates"}
        if extra:
            sg._bad("unrecognized permission_state field(s): %s" % ", ".join(sorted(extra)))
        if "path" not in ps:
            sg._bad("permission_state requires a path")
        sg._check_rel_path(ps["path"], "permission_state path")
        for k in ("allow", "ask", "deny"):
            if k in ps and (not isinstance(ps[k], int) or isinstance(ps[k], bool)):
                sg._bad("permission_state %s must be an integer" % k)
        if "require_no_duplicates" in ps and not isinstance(ps["require_no_duplicates"], bool):
            sg._bad("permission_state require_no_duplicates must be a boolean")

    if "submodules" in doc:
        subs = doc["submodules"]
        if not isinstance(subs, dict):
            sg._bad("submodules must be a mapping")
        _check_paths(subs, "submodules")
        for path, spec in subs.items():
            if not isinstance(spec, dict):
                sg._bad("submodules[%s] must be a mapping" % path)
            extra = set(spec) - {"gitlink", "populated", "head", "require_clean"}
            if extra:
                sg._bad("unrecognized submodules field(s): %s" % ", ".join(sorted(extra)))
            if "gitlink" not in spec:
                sg._bad("submodules[%s] requires a gitlink" % path)
            sg._check_oid(spec["gitlink"], "submodules[%s].gitlink" % path)
            if "populated" in spec and not isinstance(spec["populated"], bool):
                sg._bad("submodules[%s].populated must be a boolean" % path)
            if "head" in spec:
                sg._check_oid(spec["head"], "submodules[%s].head" % path)
            if "require_clean" in spec and not isinstance(spec["require_clean"], bool):
                sg._bad("submodules[%s].require_clean must be a boolean" % path)

    if "casing_rules" in doc:
        rules = doc["casing_rules"]
        if not isinstance(rules, dict):
            sg._bad("casing_rules must be a mapping")
        extra = set(rules) - {"required_prefixes", "forbidden_prefixes",
                              "forbid_normalized_collisions"}
        if extra:
            sg._bad("unrecognized casing_rules field(s): %s" % ", ".join(sorted(extra)))
        for key in ("required_prefixes", "forbidden_prefixes"):
            if key in rules:
                if not isinstance(rules[key], list):
                    sg._bad("casing_rules %s must be a list" % key)
                for p in rules[key]:
                    if not isinstance(p, str) or not p.strip():
                        sg._bad("casing_rules %s entries must be non-empty strings" % key)
                    if p.startswith("/") or ".." in p.replace("\\", "/").split("/"):
                        sg._bad("casing_rules %s entries must be repository-relative "
                                "without traversal" % key)
        if "forbid_normalized_collisions" in rules and \
                not isinstance(rules["forbid_normalized_collisions"], bool):
            sg._bad("casing_rules forbid_normalized_collisions must be a boolean")

    if "forbidden_artifacts" in doc:
        fa = doc["forbidden_artifacts"]
        if not isinstance(fa, dict):
            sg._bad("forbidden_artifacts must be a mapping")
        extra = set(fa) - {"patterns", "exceptions"}
        if extra:
            sg._bad("unrecognized forbidden_artifacts field(s): %s" % ", ".join(sorted(extra)))
        for key in ("patterns", "exceptions"):
            if key in fa:
                if not isinstance(fa[key], list):
                    sg._bad("forbidden_artifacts %s must be a list" % key)
                for p in fa[key]:
                    if not isinstance(p, str) or not p.strip():
                        sg._bad("forbidden_artifacts %s entries must be non-empty strings" % key)
                    norm = p.replace("\\", "/")
                    if norm.startswith("/") or re.match(r"^[A-Za-z]:", norm) \
                            or ".." in norm.split("/"):
                        sg._bad("forbidden_artifacts %s entries must be "
                                "repository-relative without traversal" % key)
                    # These patterns are matched against a concrete, enumerated
                    # path list, so ordinary globs like `data/*.json` are exact.
                    # (The Session Registry's ambiguity rule is about deciding
                    # intersection between two globs, which is a different
                    # problem and does not apply here.) The safety requirement
                    # is only that a pattern cannot match everything, so at
                    # least one segment must be a literal.
                    segments = [s for s in norm.split("/") if s]
                    if not segments or all(_WILDCARD_RE.search(s) for s in segments):
                        sg._bad("forbidden_artifacts %s entry %r is too broad; "
                                "at least one path segment must be literal"
                                % (key, p))

    if "registry" in doc:
        reg = doc["registry"]
        if not isinstance(reg, dict):
            sg._bad("registry must be a mapping")
        extra = set(reg) - {"path", "session_id", "stale_seconds"}
        if extra:
            sg._bad("unrecognized registry field(s): %s" % ", ".join(sorted(extra)))
        for k in ("path", "session_id"):
            if k not in reg or not isinstance(reg[k], str) or not reg[k].strip():
                sg._bad("registry requires a non-empty %s" % k)
        if "stale_seconds" in reg and (not isinstance(reg["stale_seconds"], int)
                                       or isinstance(reg["stale_seconds"], bool)
                                       or reg["stale_seconds"] < 0):
            sg._bad("registry stale_seconds must be a nonnegative integer")

    if "notes" in doc and not isinstance(doc["notes"], list):
        sg._bad("notes must be a list")
    return doc


# --------------------------------------------------------------------------
# Helpers (all Git access through the A7 read-only allowlist)
# --------------------------------------------------------------------------

def _git(repo, args):
    return a7._git(repo, args)


def _git_ok(repo, args):
    return a7._git_ok(repo, args).strip()


def _sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _chk(cid, label, ok, evidence, stopped=False, warning=False):
    status = "stopped" if stopped else ("warning" if warning
                                        else ("pass" if ok else "fail"))
    return {"id": cid, "label": label, "status": status, "evidence": evidence}


def _matches(path, pattern):
    p = path.replace("\\", "/")
    pat = pattern.replace("\\", "/")
    if pat.endswith("/**"):
        base = pat[:-3]
        return p == base or p.startswith(base + "/")
    return fnmatch.fnmatch(p, pat) or fnmatch.fnmatch(os.path.basename(p), pat)


# --------------------------------------------------------------------------
# Gates
# --------------------------------------------------------------------------

def gate_identity(repo, identity, manifest, supplied_path):
    checks = [_chk("A1", "worktree resolves", True, "resolved as ${REPO} (%s)" % identity)]
    checks.append(_chk("A2", "worktree identity",
                       identity == manifest["worktree_identity"],
                       "expected %s, observed %s"
                       % (manifest["worktree_identity"], identity)))

    if "canonical_worktree_path" in manifest:
        declared = os.path.normcase(os.path.normpath(
            manifest["canonical_worktree_path"].replace("\\", "/")))
        actual = os.path.normcase(os.path.normpath(repo.replace("\\", "/")))
        checks.append(_chk("A3", "canonical worktree path", declared == actual,
                           "declared path %s the resolved worktree"
                           % ("matches" if declared == actual else "does NOT match")))

    branch = _git_ok(repo, ["rev-parse", "--abbrev-ref", "HEAD"])
    if branch == "HEAD":
        checks.append(_chk("A4", "branch", False,
                           "the worktree is in a detached HEAD state"))
    else:
        checks.append(_chk("A4", "branch", branch == manifest["branch"],
                           "expected %s, observed %s" % (manifest["branch"], branch)))

    head = _git_ok(repo, ["rev-parse", "HEAD"])
    checks.append(_chk("A5", "HEAD", head == manifest["head"],
                       "expected %s, observed %s" % (manifest["head"], head)))

    if "git_common_dir_identity" in manifest:
        common = _git_ok(repo, ["rev-parse", "--git-common-dir"])
        common_abs = os.path.normcase(os.path.normpath(
            common if os.path.isabs(common) else os.path.join(repo, common)))
        want = os.path.normcase(os.path.normpath(
            manifest["git_common_dir_identity"].replace("\\", "/")))
        # Compare by trailing identity so no absolute machine path is printed.
        # A basename-only fallback would compare ".git" to ".git" and always
        # succeed, so the declared identity must match as a whole suffix.
        ok = common_abs.endswith(want)
        checks.append(_chk("A6", "git common directory", ok,
                           "common directory %s the declared identity"
                           % ("matches" if ok else "does NOT match")))

    # `supplied_path` is the raw --repo argument. Comparing the *resolved* top
    # level against itself would be tautological, so the check is whether the
    # caller pointed at a real worktree root or at some directory inside one.
    top = _git_ok(repo, ["rev-parse", "--show-toplevel"])
    given = os.path.normcase(os.path.normpath(
        os.path.abspath(supplied_path.replace("\\", "/"))))
    resolved = os.path.normcase(os.path.normpath(top.replace("\\", "/")))
    checks.append(_chk("A7", "supplied path is the worktree root", given == resolved,
                       "the supplied path is its own top level" if given == resolved
                       else "the supplied path lies inside another checkout root"))
    return checks


def gate_cleanliness(repo, manifest):
    checks = []
    if manifest.get("require_clean_index"):
        staged = [l for l in _git_ok(repo, ["diff", "--cached", "--name-only"]).splitlines()
                  if l.strip()]
        checks.append(_chk("B1", "index clean", not staged,
                           "staged paths: %d" % len(staged)))
    if manifest.get("require_clean_worktree"):
        # Porcelain omits ignored files, so ignored artifacts never count here.
        entries = [l for l in _git_ok(repo, ["status", "--porcelain", "-uall"]).splitlines()
                   if l.strip()]
        modified = [l for l in entries if not l.startswith("?? ")]
        untracked = [l for l in entries if l.startswith("?? ")]
        checks.append(_chk("B2", "worktree clean", not entries,
                           "tracked modifications: %d, visible untracked: %d "
                           "(ignored files excluded by design)"
                           % (len(modified), len(untracked))))

    git_dir = _git_ok(repo, ["rev-parse", "--git-dir"])
    git_dir = git_dir if os.path.isabs(git_dir) else os.path.join(repo, git_dir)
    found = [m for m in _INTERRUPTED_MARKERS if os.path.exists(os.path.join(git_dir, m))]
    checks.append(_chk("B3", "no interrupted git operation", not found,
                       "markers present: %s" % (", ".join(found) if found else "none")))
    return checks


def gate_tracked_blobs(repo, manifest):
    checks = []
    blobs = manifest.get("tracked_blobs") or {}
    for i, (path, oid) in enumerate(sorted(blobs.items()), 1):
        rc, out, _ = _git(repo, ["rev-parse", "HEAD:%s" % path])
        seen = out.strip() if rc == 0 else None
        checks.append(_chk("C%02d" % i, "tracked blob %s" % path, seen == oid,
                           "expected %s, observed %s" % (oid, seen or "absent")))
    if blobs:
        checks.append(_chk("C00", "tracked blobs compared by git blob id", True,
                           "%d file(s) compared by blob id, not raw bytes, so "
                           "core.autocrlf cannot cause a false failure" % len(blobs)))
    return checks


def gate_local_state(repo, manifest):
    checks = []
    files = manifest.get("local_ignored_files") or {}
    tracked = set(_git_ok(repo, ["ls-files"]).splitlines())
    tracked_folded = {t.lower() for t in tracked}

    for i, (path, spec) in enumerate(sorted(files.items()), 1):
        full = os.path.join(repo, path.replace("\\", "/"))
        prefix = "D%02d" % i
        if not os.path.isfile(full):
            checks.append(_chk(prefix + "a", "local file %s present" % path, False,
                               "expected at ${REPO}/%s, not found" % path))
            continue
        checks.append(_chk(prefix + "a", "local file %s present" % path, True, "present"))
        if "sha256" in spec:
            digest = _sha256_file(full)
            checks.append(_chk(prefix + "b", "local file %s hash" % path,
                               digest == spec["sha256"],
                               "expected %s, observed %s" % (spec["sha256"], digest)))
        if spec.get("must_be_json"):
            try:
                json.load(open(full, encoding="utf-8"))
                ok, why = True, "parses as JSON"
            except Exception:
                ok, why = False, "does not parse as JSON"
            checks.append(_chk(prefix + "c", "local file %s is JSON" % path, ok, why))
        if spec.get("must_be_ignored"):
            rc, out, _ = _git(repo, ["check-ignore", "--no-index", "-v", path])
            ignored = rc == 0 and bool(out.strip())
            checks.append(_chk(prefix + "d", "local file %s is ignored" % path,
                               ignored,
                               "git reports it as %signored" % ("" if ignored else "NOT ")))
        if spec.get("must_not_be_tracked"):
            is_tracked = path in tracked or path.lower() in tracked_folded
            checks.append(_chk(prefix + "e", "local file %s is not tracked" % path,
                               not is_tracked,
                               "tracked" if is_tracked else "not tracked"))

    ps = manifest.get("permission_state")
    if ps:
        full = os.path.join(repo, ps["path"].replace("\\", "/"))
        if not os.path.isfile(full):
            checks.append(_chk("E1", "permission file present", False,
                               "expected at ${REPO}/%s, not found" % ps["path"]))
        else:
            try:
                perms = json.load(open(full, encoding="utf-8"))["permissions"]
            except Exception:
                perms = None
            if perms is None:
                checks.append(_chk("E2", "permission file parses", False,
                                   "the permission file could not be parsed"))
            else:
                wanted = {k: ps[k] for k in ("allow", "ask", "deny") if k in ps}
                if wanted:
                    counts = {k: len(perms.get(k, [])) for k in wanted}
                    checks.append(_chk("E2", "permission counts", counts == wanted,
                                       "expected %s, observed %s"
                                       % (json.dumps(wanted, sort_keys=True),
                                          json.dumps(counts, sort_keys=True))))
                if ps.get("require_no_duplicates"):
                    dupes = {}
                    for key in ("allow", "ask", "deny"):
                        vals = perms.get(key, [])
                        if len(vals) != len(set(vals)):
                            dupes[key] = len(vals) - len(set(vals))
                    checks.append(_chk("E3", "permission entries unique", not dupes,
                                       "duplicate counts: %s"
                                       % (json.dumps(dupes, sort_keys=True) if dupes
                                          else "none")))
    return checks


def gate_casing(repo, manifest):
    rules = manifest.get("casing_rules")
    if not rules:
        return []
    checks = []
    tracked = _git_ok(repo, ["ls-files"]).splitlines()   # index paths, not the FS
    for i, prefix in enumerate(rules.get("required_prefixes", []), 1):
        n = sum(1 for p in tracked if p.startswith(prefix))
        checks.append(_chk("F%02d" % i, "tracked prefix %s present" % prefix, n > 0,
                           "%d tracked path(s)" % n))
    for i, prefix in enumerate(rules.get("forbidden_prefixes", []), 1):
        n = sum(1 for p in tracked if p.startswith(prefix))
        checks.append(_chk("Fx%02d" % i, "tracked prefix %s absent" % prefix, n == 0,
                           "%d tracked path(s)" % n))
    if rules.get("forbid_normalized_collisions"):
        folded = {}
        for p in tracked:
            folded.setdefault(p.lower(), set()).add(p)
        collisions = [v for v in folded.values() if len(v) > 1]
        checks.append(_chk("F00", "no case-normalized tracked collisions",
                           not collisions,
                           "%d collision(s)" % len(collisions)))
    return checks


def gate_submodules(repo, manifest):
    checks = []
    subs = manifest.get("submodules") or {}
    for i, (path, spec) in enumerate(sorted(subs.items()), 1):
        prefix = "G%02d" % i
        rc, out, _ = _git(repo, ["ls-files", "--stage", "-z", "--", path])
        entry = out.split("\0")[0] if rc == 0 and out else ""
        if not entry.startswith("160000"):
            checks.append(_chk(prefix + "a", "submodule %s in index" % path, False,
                               "no gitlink entry found"))
            continue
        seen = entry.split()[1]
        checks.append(_chk(prefix + "a", "submodule %s gitlink" % path,
                           seen == spec["gitlink"],
                           "expected %s, observed %s" % (spec["gitlink"], seen)))
        full = os.path.join(repo, path.replace("\\", "/"))
        populated = os.path.isdir(os.path.join(full, ".git")) or \
            os.path.isfile(os.path.join(full, ".git"))
        if "populated" in spec:
            checks.append(_chk(prefix + "b", "submodule %s population" % path,
                               populated == spec["populated"],
                               "declared %s, observed %s"
                               % ("populated" if spec["populated"] else "unpopulated",
                                  "populated" if populated else "unpopulated")))
        if populated and spec.get("populated"):
            # Read-only: no submodule command that could initialize or update.
            if "head" in spec:
                sub_head = _git_ok(full, ["rev-parse", "HEAD"])
                checks.append(_chk(prefix + "c", "submodule %s HEAD" % path,
                                   sub_head == spec["head"],
                                   "expected %s, observed %s" % (spec["head"], sub_head)))
            if spec.get("require_clean"):
                entries = [l for l in _git_ok(full, ["status", "--porcelain", "-uall"]).splitlines()
                           if l.strip()]
                checks.append(_chk(prefix + "d", "submodule %s clean" % path,
                                   not entries, "%d status entr(ies)" % len(entries)))
    return checks


def gate_forbidden(repo, manifest):
    fa = manifest.get("forbidden_artifacts")
    if not fa:
        return []
    patterns = fa.get("patterns", [])
    exceptions = set(p.replace("\\", "/") for p in fa.get("exceptions", []))
    # Consider tracked paths and every present file that git can see, including
    # ignored ones -- a forbidden artifact is forbidden whether ignored or not.
    tracked = set(_git_ok(repo, ["ls-files"]).splitlines())
    others = set(_git_ok(repo, ["ls-files", "--others"]).splitlines())
    candidates = sorted(tracked | others)

    hits = []
    for path in candidates:
        if path in exceptions:
            continue
        for pat in patterns:
            if _matches(path, pat):
                hits.append((path, pat))
                break
    # Cowork tooling residue anywhere in the worktree.
    residue = [p for p in candidates
               if any(fnmatch.fnmatch(os.path.basename(p), r) for r in _COWORK_RESIDUE)
               and p not in exceptions]
    checks = [_chk("H1", "no forbidden local artifacts", not hits,
                   "%d match(es) across %d declared pattern(s)"
                   % (len(hits), len(patterns)))]
    for i, (path, pat) in enumerate(hits[:20], 1):
        checks.append(_chk("H1.%02d" % i, "forbidden artifact %s" % path, False,
                           "matched declared pattern %s" % pat))
    checks.append(_chk("H2", "no Cowork lock/temp residue", not residue,
                       "%d residue file(s)" % len(residue)))
    for i, path in enumerate(residue[:10], 1):
        checks.append(_chk("H2.%02d" % i, "residue %s" % path, False, "present"))
    return checks


def gate_registry(repo, identity, manifest):
    """Read-only. Never registers, heartbeats, advances, or rewrites anything."""
    reg_spec = manifest.get("registry")
    if not reg_spec:
        return []
    # `~` is expanded here so a manifest can name the machine-local registry
    # without embedding a username or home directory in a shared document.
    path = os.path.expanduser(reg_spec["path"])
    checks = []
    lock = path + ".lock"
    if os.path.exists(lock):
        return [_chk("I0", "registry lock", False,
                     "a registry lock is present; another process may be writing",
                     warning=True)]
    if not os.path.isfile(path):
        return [_chk("I0", "registry present", False,
                     "no registry file at the declared location", stopped=True)]
    try:
        registry = sr.read_registry(path)
    except Exception as exc:
        return [_chk("I0", "registry readable", False,
                     ef.sanitize_text(str(exc)), stopped=True)]

    from datetime import datetime, timezone
    observed = datetime.now(timezone.utc)
    stale_seconds = reg_spec.get("stale_seconds", sr.DEFAULT_STALE_SECONDS)

    rec = None
    for s in registry["sessions"]:
        if s["session_id"] == reg_spec["session_id"]:
            rec = s
            break
    if rec is None:
        return [_chk("I1", "registry session present", False,
                     "no session with the declared id is registered")]

    state = sr.classify(rec, observed, stale_seconds)
    checks.append(_chk("I1", "registry session present", True,
                       "found, observed %s" % state))
    checks.append(_chk("I2", "registry session active", rec["status"] == "active",
                       "status %s" % rec["status"]))
    if state in ("stale", "future-heartbeat"):
        checks.append(_chk("I3", "registry session freshness", False,
                           "session observed %s; a person should confirm it is live"
                           % state, warning=True))
    checks.append(_chk("I4", "registry worktree identity",
                       rec["worktree_identity"] == identity,
                       "expected %s, observed %s" % (rec["worktree_identity"], identity)))
    declared_path = os.path.normcase(os.path.normpath(
        rec["canonical_worktree_path"].replace("\\", "/")))
    actual_path = os.path.normcase(os.path.normpath(repo.replace("\\", "/")))
    checks.append(_chk("I5", "registry canonical path",
                       declared_path == actual_path,
                       "registry path %s the resolved worktree"
                       % ("matches" if declared_path == actual_path else "does NOT match")))
    checks.append(_chk("I6", "registry branch", rec["branch"] == manifest["branch"],
                       "expected %s, observed %s" % (rec["branch"], manifest["branch"])))
    checks.append(_chk("I7", "registry expected commit",
                       rec["expected_commit"] == manifest["head"],
                       "expected %s, observed %s"
                       % (rec["expected_commit"], manifest["head"])))

    collisions = sr.find_collisions(rec, registry, observed, stale_seconds,
                                    ignore_self=True)
    blocking = [c for c in collisions if c[3] == "blocking"]
    approval = [c for c in collisions if c[3] == "approval"]
    checks.append(_chk("I8", "no conflicting live session",
                       not blocking and not approval,
                       "blocking=%d, approval-required=%d" % (len(blocking), len(approval)),
                       warning=bool(approval) and not blocking))
    for i, (category, other, detail, severity) in enumerate(
            sorted(collisions, key=lambda c: (c[0], c[1])), 1):
        checks.append(_chk("I8.%02d" % i, "collision: %s" % category, False,
                           "with %s -- %s" % (ef.sanitize_text(other), detail),
                           warning=(severity == "approval")))
    return checks


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def _reject_constant(name):
    raise ef.ValidationError("non-standard numeric value is not permitted")


def _read_manifest(path):
    try:
        with open(path, "rb") as fh:
            raw = fh.read(ef.MAX_INPUT_BYTES + 1)
    except OSError:
        raise ef.ValidationError("the manifest file could not be read")
    if len(raw) > ef.MAX_INPUT_BYTES:
        raise ef.SafetyLimitError("the manifest exceeds the maximum accepted size")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise ef.ValidationError("the manifest is not valid UTF-8")
    try:
        return json.loads(text, parse_constant=_reject_constant)
    except ef.ValidationError:
        raise
    except Exception:
        raise ef.ValidationError("the manifest is not valid JSON")


def _err(text):
    sys.stderr.buffer.write(text.encode("utf-8"))
    sys.stderr.buffer.flush()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="worktree_bootstrap_validator",
        description="Validate that a worktree is safely configured. Read-only; "
                    "never creates, repairs, or modifies anything.")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--repo", default=".")
    parser.add_argument("--format", choices=("markdown", "json"), required=True)
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return 0 if exc.code == 0 else 2

    try:
        manifest = _read_manifest(args.manifest)
        ef.enforce_limits(manifest)
        validate_manifest(manifest)
    except ef.SafetyLimitError as exc:
        _err("worktree_bootstrap_validator: safety limit: %s\n"
             % ef.sanitize_text(str(exc)))
        return 3
    except ef.ValidationError as exc:
        _err("worktree_bootstrap_validator: invalid manifest: %s\n"
             % ef.sanitize_text(str(exc)))
        return 2

    try:
        repo, identity = sg.resolve_repo(args.repo)
        checks = []
        checks.extend(gate_identity(repo, identity, manifest, args.repo))
        checks.extend(gate_cleanliness(repo, manifest))
        checks.extend(gate_tracked_blobs(repo, manifest))
        checks.extend(gate_local_state(repo, manifest))
        checks.extend(gate_casing(repo, manifest))
        checks.extend(gate_submodules(repo, manifest))
        checks.extend(gate_forbidden(repo, manifest))
        checks.extend(gate_registry(repo, identity, manifest))
    except (sg.StoppedError, StoppedError) as exc:
        checks = [_chk("A0", "worktree observation", False,
                       ef.sanitize_text(str(exc)), stopped=True)]

    doc = {"schema_version": ef.SCHEMA_VERSION,
           "phase": "worktree bootstrap validation",
           "scope": "read-only configuration check before an automated session",
           "checks": checks}
    if "notes" in manifest:
        doc["notes"] = manifest["notes"]

    try:
        norm = ef.normalize(doc)
        text = (ef.render_markdown(norm) if args.format == "markdown"
                else ef.render_json(norm))
    except (ef.ValidationError, ef.SafetyLimitError) as exc:
        _err("worktree_bootstrap_validator: %s\n" % ef.sanitize_text(str(exc)))
        return 2
    sys.stdout.buffer.write(text.encode("utf-8"))
    sys.stdout.buffer.flush()

    overall = norm["overall_status"]
    if overall == "stopped":
        return 4
    if overall == "failed":
        return 1
    if overall == "passed_with_warnings":
        return 5
    return 0


if __name__ == "__main__":
    sys.exit(main())
