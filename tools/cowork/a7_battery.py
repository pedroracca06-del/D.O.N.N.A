#!/usr/bin/env python
"""a7_battery.py -- reusable read-only A7 safety battery.

Seven fixed gates run against a candidate change set described by a manifest.
Nothing is executed from the manifest; nothing is written; no test is run.

  A1  Scope integrity          observed changed paths == manifest expectation
  A2  Secret / credential scan added text and new text files
  A3  Machine-specific paths   user profiles, temp/scratch, absolute checkouts
  A4  Protected boundary       retirement, kill switches, hooks, settings,
                               permissions, risk, strategy, broker paths
  A5  Runtime / generated /    runtime JSON, logs, caches, bytecode,
      copyright                credential files, raw third-party transcripts
  A6  Baseline staleness       reuses the Staleness Guard's observations
  A7  Evidence / test parity   validates SUPPLIED test evidence; runs nothing

Worktree-session collision detection is deliberately NOT here; it belongs to the
Session Registry phase.

BOUNDARY:
  * Only a fixed allowlist of read-only Git subcommands ever runs, each as an
    argument array. ``shell=True`` is never used. No fetch, pull, push, merge,
    rebase, checkout, switch, reset, restore, clean, add, commit, tag/branch
    mutation, submodule update, config write, maintenance, or gc.
  * Test commands inside the manifest are DATA. The battery verifies supplied
    evidence and never executes a suite.
  * Writes no file. Output goes to stdout; errors go to stderr.
  * Standard library only; the Evidence Formatter and Staleness Guard are reused
    rather than reimplemented.

POLICY: ``a7_policy.json`` is the fixed minimum. A manifest may add stricter
protections through ``stricter_protected_paths``; it can never remove or weaken
a policy minimum, and there is no "disable this gate" option.

Exit codes:
  0  all seven gates pass, no approval-required warning
  1  one or more gates fail
  2  invalid CLI, manifest, or policy
  3  safety-limit rejection
  4  a required observation stopped or was unavailable
  5  gates pass but approval-required warnings exist
"""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import evidence_formatter as ef      # noqa: E402
import staleness_guard as sg         # noqa: E402

sys.path.pop(0)

SCHEMA_VERSION = 1
POLICY_FILENAME = "a7_policy.json"

MANIFEST_REQUIRED = ("schema_version", "phase", "change_scope",
                     "expected_paths", "baseline", "required_test_suites")
MANIFEST_OPTIONAL = ("declared_protected_changes", "stricter_protected_paths",
                     "expected_submodule_gitlinks", "notes")
VALID_SCOPES = ("staged", "worktree", "commit")

_OID_RE = re.compile(r"^[0-9a-f]{40}$|^[0-9a-f]{64}$")

# The battery needs two read-only subcommands the Staleness Guard does not
# (`diff-tree` for a commit candidate, `cat-file` to read blob text), so it
# declares its own allowlist rather than weakening the guard's. Every entry is
# read-only; the mutating-verb exclusion is asserted by test.
_A7_GIT_READ_ONLY = frozenset({
    "rev-parse", "status", "diff", "diff-tree", "show", "ls-files",
    "ls-tree", "cat-file", "check-ignore", "show-ref", "remote",
})


def _git(repo, args, timeout=sg.GIT_TIMEOUT_SECONDS):
    """Run one allowlisted read-only Git command. Never uses a shell."""
    if not args or args[0] not in _A7_GIT_READ_ONLY:
        raise sg.StoppedError("refused a git subcommand outside the A7 read-only allowlist")
    # Argument array only; a shell is never involved.
    cmd = ["git", "--no-optional-locks", "-C", repo] + args
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise sg.StoppedError("a git command exceeded its timeout")
    except OSError:
        raise sg.StoppedError("git could not be executed")
    return (proc.returncode,
            proc.stdout.decode("utf-8", "surrogateescape"),
            ef.sanitize_text(proc.stderr.decode("utf-8", "replace").strip()))


def _git_ok(repo, args):
    rc, out, err = _git(repo, args)
    if rc != 0:
        raise sg.StoppedError("git %s failed: %s" % (args[0], err[:120]))
    return out

# ---- A2 detection ---------------------------------------------------------

_SECRET_KEY_RE = re.compile(
    r"(?i)\b[A-Za-z0-9_.-]*(api[_-]?key|secret|token|password|passphrase|"
    r"cookie|authorization|bearer|private[_-]?key|access[_-]?key|"
    r"refresh[_-]?token|client[_-]?secret)[A-Za-z0-9_.-]*\s*[:=]\s*\S+")
_SECRET_KEY_ALLOW_RE = re.compile(
    r"(?i)(tokeniz|secret[ _-]?scan|credential[ _-]?check|_count|_status|"
    r"_policy|_name|_label|redact|\bREDACTED\b)")
_SECRET_FORMATS = (
    ("anthropic-key", re.compile(r"sk-ant-[A-Za-z0-9._-]{8,}")),
    ("github-token", re.compile(r"\bghp_[A-Za-z0-9]{16,}")),
    ("aws-access-key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("private-key-block", re.compile(r"-----BEGIN[^-]{0,64}PRIVATE KEY-----")),
    ("authorization-header", re.compile(
        r"(?i)\b(?:proxy-)?authorization\s*:\s*(?:[A-Za-z][A-Za-z0-9-]*\s+)?\S+")),
    ("bearer-token", re.compile(r"(?i)\b(?:bearer|basic)\s+[A-Za-z0-9._~+/=-]{12,}")),
    ("url-embedded-credentials", re.compile(
        r"(?i)\b[a-z][a-z0-9+.-]*://[^/\s:@]+:[^/\s@]+@")),
    ("url-query-secret", re.compile(
        r"(?i)[?&](?:token|secret|api[_-]?key|password|access[_-]?key|sig)=[^&\s\"']+")),
)

# ---- A3 detection ---------------------------------------------------------

_MACHINE_PATTERNS = (
    ("windows-user-profile", re.compile(r"(?i)\b[a-z]:[\\/]+users[\\/]+[^\\/\s\"']+")),
    ("gitbash-user-path", re.compile(r"(?i)(?<![\w.])/[a-z]/users/[^/\s\"']+")),
    ("posix-home", re.compile(r"(?<![\w.])/home/[^/\s\"']+")),
    ("macos-home", re.compile(r"(?<![\w.])/Users/[^/\s\"']+")),
    ("temp-scratch", re.compile(
        r"(?i)(\b[a-z]:[\\/]+(?:temp|tmp)\b|(?<![\w.])/tmp/|AppData[\\/]+Local[\\/]+Temp)")),
    ("absolute-drive-path", re.compile(r"(?i)\b[a-z]:[\\/]+(?!users\b)[^\s\"']{2,}")),
)


class PolicyError(Exception):
    """The policy file is missing or unusable -> exit 2."""


# --------------------------------------------------------------------------
# Policy
# --------------------------------------------------------------------------

def load_policy(path=None):
    p = path or os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             POLICY_FILENAME)
    try:
        raw = open(p, "rb").read()
    except OSError:
        raise PolicyError("the A7 policy file could not be read")
    try:
        policy = json.loads(raw.decode("utf-8"), parse_constant=_reject_constant)
    except ef.ValidationError:
        raise
    except Exception:
        raise PolicyError("the A7 policy file is not valid JSON")
    if not isinstance(policy, dict) or policy.get("schema_version") != SCHEMA_VERSION:
        raise PolicyError("unsupported A7 policy schema")
    return policy, hashlib.sha256(raw).hexdigest()


def _reject_constant(name):
    raise ef.ValidationError("non-standard numeric value is not permitted")


def _protected_rules(policy):
    """[(category, classification, pattern)] over every protected category."""
    out = []
    for name, spec in policy["protected_path_categories"].items():
        cls = spec.get("classification", "AAM")
        for pat in list(spec.get("paths", [])) + list(spec.get("patterns", [])):
            out.append((name, cls, pat))
    rt = policy["raw_transcript_prohibition"]
    for pat in rt["patterns"]:
        out.append(("raw_transcripts", rt["classification"], pat))
    return out


def _matches(path, pattern):
    p = path.replace("\\", "/")
    pat = pattern.replace("\\", "/")
    if pat.endswith("/**"):
        base = pat[:-3]
        return p == base or p.startswith(base + "/")
    return fnmatch.fnmatch(p, pat) or fnmatch.fnmatch(os.path.basename(p), pat)


# --------------------------------------------------------------------------
# Manifest
# --------------------------------------------------------------------------

def validate_manifest(doc, policy):
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

    if not isinstance(doc["phase"], str) or not doc["phase"].strip():
        sg._bad("phase must be a non-empty string")

    scope = doc["change_scope"]
    if not isinstance(scope, dict):
        sg._bad("change_scope must be a mapping")
    extra = set(scope) - {"kind", "commit"}
    if extra:
        sg._bad("unrecognized change_scope field(s): %s" % ", ".join(sorted(extra)))
    if scope.get("kind") not in VALID_SCOPES:
        sg._bad("change_scope kind must be one of: %s" % ", ".join(VALID_SCOPES))
    if scope["kind"] == "commit":
        if "commit" not in scope:
            sg._bad("commit scope requires an explicit commit id")
        if not _OID_RE.match(str(scope["commit"])):
            sg._bad("commit scope requires a full commit id, not an abbreviation")
    elif "commit" in scope:
        sg._bad("commit is only valid for the commit scope")

    paths = doc["expected_paths"]
    if not isinstance(paths, list):
        sg._bad("expected_paths must be a list")
    # Exact duplicates are always invalid. Case-conflicting entries are NOT
    # rejected here: a case-only rename legitimately produces two paths that
    # differ only in case (kept.txt -> KEPT.TXT). Gate A1 decides, because only
    # there is the observed change set available to tell a rename pair from an
    # accidental collision.
    exact = set()
    for item in paths:
        sg._check_rel_path(item, "expected_paths entry")
        norm = item.replace("\\", "/")
        if norm in exact:
            sg._bad("expected_paths contains duplicate entries")
        exact.add(norm)

    if not isinstance(doc["baseline"], dict):
        sg._bad("baseline must be a mapping")
    sg.validate_baseline(doc["baseline"])

    suites = doc["required_test_suites"]
    if not isinstance(suites, list) or not suites:
        sg._bad("required_test_suites must be a non-empty list")
    for s in suites:
        if not isinstance(s, dict):
            sg._bad("each required_test_suites entry must be a mapping")
        allowed = {"name", "command", "expected_passed", "expected_failed",
                   "expected_skipped", "expected_errors", "expected_collected",
                   "observed_passed", "observed_failed", "observed_skipped",
                   "observed_errors", "observed_collected", "observed_failures"}
        bad = set(s) - allowed
        if bad:
            sg._bad("unrecognized test-suite field(s): %s" % ", ".join(sorted(bad)))
        for req in ("name", "command"):
            if req not in s or not isinstance(s[req], str) or not s[req].strip():
                sg._bad("each test suite needs a non-empty %s" % req)
        for k, v in s.items():
            if k.startswith(("expected_", "observed_")) and k != "observed_failures":
                if not isinstance(v, int) or isinstance(v, bool):
                    sg._bad("test-suite %s must be an integer" % k)
        if "observed_failures" in s and not isinstance(s["observed_failures"], list):
            sg._bad("observed_failures must be a list")

    if "declared_protected_changes" in doc:
        dp = doc["declared_protected_changes"]
        if not isinstance(dp, list):
            sg._bad("declared_protected_changes must be a list")
        for item in dp:
            sg._check_rel_path(item, "declared_protected_changes entry")

    if "stricter_protected_paths" in doc:
        sp = doc["stricter_protected_paths"]
        if not isinstance(sp, list):
            sg._bad("stricter_protected_paths must be a list")
        for item in sp:
            if not isinstance(item, str) or not item.strip():
                sg._bad("stricter_protected_paths entries must be non-empty strings")
            if item.startswith("!") or item.startswith("-"):
                sg._bad("stricter_protected_paths cannot express a negation; "
                        "policy minimums may not be weakened")

    if "expected_submodule_gitlinks" in doc:
        subs = doc["expected_submodule_gitlinks"]
        if not isinstance(subs, dict):
            sg._bad("expected_submodule_gitlinks must be a mapping")
        sg._check_no_dupe_keys(subs, "expected_submodule_gitlinks")
        for path, oid in subs.items():
            sg._check_rel_path(path, "expected_submodule_gitlinks path")
            sg._check_oid(oid, "expected_submodule_gitlinks[%s]" % path)

    if "notes" in doc and not isinstance(doc["notes"], list):
        sg._bad("notes must be a list")
    return doc


# --------------------------------------------------------------------------
# Observation of the candidate change set
# --------------------------------------------------------------------------

def _nul_fields(text):
    parts = text.split("\0")
    if parts and parts[-1] == "":
        parts.pop()
    return parts


def observe_changes(repo, scope):
    """Return {path: {'kind': ..., 'status': ...}} using machine-readable,
    NUL-delimited git output only. Never parses human-formatted status."""
    kind = scope["kind"]
    found = {}

    def add(path, group, status):
        path = path.replace("\\", "/")
        found.setdefault(path, {"kind": group, "status": status})

    if kind == "commit":
        out = _git_ok(repo, ["diff-tree", "--no-commit-id", "--name-status",
                               "-r", "-M", "-z", scope["commit"]])
        fields = _nul_fields(out)
        i = 0
        while i < len(fields):
            st = fields[i]
            if st and st[0] in ("R", "C") and i + 2 < len(fields):
                add(fields[i + 1], "committed", st + " (source)")
                add(fields[i + 2], "committed", st + " (destination)")
                i += 3
            elif i + 1 < len(fields):
                add(fields[i + 1], "committed", st)
                i += 2
            else:
                break
        return found

    if kind in ("staged", "worktree"):
        out = _git_ok(repo, ["diff", "--cached", "--name-status", "-M", "-z"])
        fields = _nul_fields(out)
        i = 0
        while i < len(fields):
            st = fields[i]
            if st and st[0] in ("R", "C") and i + 2 < len(fields):
                add(fields[i + 1], "staged", st + " (source)")
                add(fields[i + 2], "staged", st + " (destination)")
                i += 3
            elif i + 1 < len(fields):
                add(fields[i + 1], "staged", st)
                i += 2
            else:
                break

    if kind == "worktree":
        out = _git_ok(repo, ["diff", "--name-status", "-M", "-z"])
        fields = _nul_fields(out)
        i = 0
        while i < len(fields):
            st = fields[i]
            if st and st[0] in ("R", "C") and i + 2 < len(fields):
                add(fields[i + 1], "unstaged", st + " (source)")
                add(fields[i + 2], "unstaged", st + " (destination)")
                i += 3
            elif i + 1 < len(fields):
                add(fields[i + 1], "unstaged", st)
                i += 2
            else:
                break
        out = _git_ok(repo, ["ls-files", "--others", "--exclude-standard", "-z"])
        for path in _nul_fields(out):
            add(path, "untracked", "??")

    # Classify submodule gitlinks separately.
    for path in list(found):
        rc, mode_out, _ = _git(repo, ["ls-files", "--stage", "-z", "--", path])
        if rc == 0 and mode_out.startswith("160000"):
            found[path]["kind"] = "submodule"
    return found


def _blob_text(repo, scope, path):
    """Return (text, is_binary). Never decodes a binary blob as text."""
    if scope["kind"] == "commit":
        ref = "%s:%s" % (scope["commit"], path)
    elif scope["kind"] == "staged":
        ref = ":%s" % path
    else:
        ref = None

    if ref is not None:
        rc, out, _ = _git(repo, ["cat-file", "-p", ref])
        if rc != 0:
            return None, False
        data = out.encode("utf-8", "surrogateescape")
    else:
        full = os.path.join(repo, path)
        if not os.path.isfile(full):
            return None, False
        try:
            data = open(full, "rb").read()
        except OSError:
            return None, False
    if b"\0" in data[:8192]:
        return None, True
    try:
        return data.decode("utf-8"), False
    except UnicodeDecodeError:
        return None, True


# --------------------------------------------------------------------------
# Gates
# --------------------------------------------------------------------------

def _finding_hash(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def gate_a1(observed, manifest):
    expected = [p.replace("\\", "/") for p in manifest["expected_paths"]]
    obs = sorted(observed)
    exp = sorted(expected)
    missing = [p for p in exp if p not in observed]
    extra = [p for p in obs if p not in expected]
    checks = []
    if not exp and obs:
        checks.append(sg._chk("A1.0", "A1 scope: change set required", False,
                              "manifest declared zero paths but %d changed" % len(obs)))
    checks.append(sg._chk(
        "A1.1", "A1 scope integrity", not missing and not extra,
        "expected %d, observed %d, missing %d, extra %d"
        % (len(exp), len(obs), len(missing), len(extra))))
    if missing:
        checks.append(sg._chk("A1.2", "A1 missing declared paths", False,
                              "; ".join(sorted(missing)[:10])))
    if extra:
        checks.append(sg._chk("A1.3", "A1 undeclared paths present", False,
                              "; ".join(sorted(extra)[:10])))
    # Case-conflicting declarations are legitimate only when both sides are
    # genuinely present in the observed change set -- i.e. a case-only rename.
    folded = {}
    for p in expected:
        folded.setdefault(p.lower(), []).append(p)
    bogus = [v for v in folded.values()
             if len(v) > 1 and not all(p in observed for p in v)]
    if bogus:
        checks.append(sg._chk(
            "A1.5", "A1 case-conflicting declarations", False,
            "; ".join("/".join(sorted(v)) for v in bogus[:5])))

    groups = {}
    for path, meta in observed.items():
        groups.setdefault(meta["kind"], []).append(path)
    checks.append(sg._chk(
        "A1.4", "A1 change-set composition", True,
        ", ".join("%s=%d" % (k, len(v)) for k, v in sorted(groups.items())) or "empty"))
    return checks


def gate_a2(repo, scope, observed):
    findings = []
    binaries = 0
    for path in sorted(observed):
        if observed[path]["kind"] == "submodule":
            continue
        text, is_binary = _blob_text(repo, scope, path)
        if is_binary:
            binaries += 1
            continue
        if text is None:
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            if _SECRET_KEY_RE.search(line) and not _SECRET_KEY_ALLOW_RE.search(line):
                findings.append((path, lineno, "credential-key",
                                 _finding_hash(line)))
            for name, rx in _SECRET_FORMATS:
                if rx.search(line):
                    findings.append((path, lineno, name, _finding_hash(line)))
    checks = [sg._chk("A2.1", "A2 secret and credential scan", not findings,
                      "findings: %d, binary files classified: %d" % (len(findings), binaries))]
    for i, (path, lineno, cat, fh) in enumerate(findings[:20]):
        checks.append(sg._chk("A2.%02d" % (i + 2), "A2 finding in %s" % path, False,
                              "line %d, category %s, finding %s" % (lineno, cat, fh)))
    return checks


def gate_a3(repo, scope, observed, policy):
    placeholders = policy["portable_placeholders"]
    findings = []
    for path in sorted(observed):
        if observed[path]["kind"] == "submodule":
            continue
        text, is_binary = _blob_text(repo, scope, path)
        if is_binary or text is None:
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            stripped = line
            for ph in placeholders:
                stripped = stripped.replace(ph, "")
            for name, rx in _MACHINE_PATTERNS:
                if rx.search(stripped):
                    findings.append((path, lineno, name))
                    break
    checks = [sg._chk("A3.1", "A3 machine-specific path scan", not findings,
                      "findings: %d" % len(findings))]
    for i, (path, lineno, name) in enumerate(findings[:20]):
        checks.append(sg._chk("A3.%02d" % (i + 2), "A3 finding in %s" % path, False,
                              "line %d, category %s" % (lineno, name)))
    return checks


def gate_a4(repo, scope, observed, manifest, policy):
    rules = _protected_rules(policy)
    stricter = manifest.get("stricter_protected_paths", [])
    declared = {p.replace("\\", "/") for p in manifest.get("declared_protected_changes", [])}

    hits = []
    for path in sorted(observed):
        for category, cls, pat in rules:
            if _matches(path, pat):
                hits.append((path, category, cls))
                break
        else:
            for pat in stricter:
                if _matches(path, pat):
                    hits.append((path, "manifest-stricter", "AAM"))
                    break

    checks = []
    undeclared = [h for h in hits if h[0] not in declared]
    declared_hits = [h for h in hits if h[0] in declared]

    checks.append(sg._chk("A4.1", "A4 protected-boundary classification", True,
                          "protected paths touched: %d (declared %d, undeclared %d)"
                          % (len(hits), len(declared_hits), len(undeclared))))
    for i, (path, category, cls) in enumerate(undeclared[:20]):
        checks.append(sg._chk("A4.%02d" % (i + 2),
                              "A4 undeclared protected change: %s" % path, False,
                              "category %s requires %s and was not declared" % (category, cls)))
    # Declared protected changes never pass silently.
    for i, (path, category, cls) in enumerate(declared_hits[:20]):
        checks.append({"id": "A4.D%02d" % (i + 1),
                       "label": "A4 declared protected change: %s" % path,
                       "status": "warning",
                       "evidence": "category %s requires %s approval" % (category, cls)})

    # Activation flags appearing in added content.
    flag_hits = []
    for path in sorted(observed):
        if observed[path]["kind"] == "submodule":
            continue
        text, is_binary = _blob_text(repo, scope, path)
        if is_binary or text is None:
            continue
        for flag in policy["protected_flags"]:
            for lineno, line in enumerate(text.splitlines(), 1):
                if re.search(re.escape(flag) + r"\s*[:=]\s*['\"]?(true|1|yes|on|enabled)\b",
                             line, re.I):
                    flag_hits.append((path, lineno, flag))
    for i, (path, lineno, flag) in enumerate(flag_hits[:10]):
        checks.append(sg._chk("A4.F%02d" % (i + 1),
                              "A4 activation flag enabled in %s" % path, False,
                              "line %d sets %s to an enabling value" % (lineno, flag)))
    if not flag_hits:
        checks.append(sg._chk("A4.F00", "A4 activation flags not enabled", True,
                              "no guarded flag set to an enabling value"))
    return checks


def gate_a5(observed, policy):
    runtime = policy["runtime_generated_patterns"]
    creds = policy["credential_file_patterns"]
    transcripts = policy["raw_transcript_prohibition"]["patterns"]
    exceptions = set(policy["tracked_data_exceptions"])

    bad = []
    submodules = []
    for path in sorted(observed):
        if observed[path]["kind"] == "submodule":
            submodules.append(path)
            continue
        if path in exceptions:
            continue
        for pat in transcripts:
            if _matches(path, pat):
                bad.append((path, "raw-third-party-transcript"))
                break
        else:
            for pat in creds:
                if _matches(path, pat):
                    bad.append((path, "credential-file"))
                    break
            else:
                for pat in runtime:
                    if _matches(path, pat):
                        bad.append((path, "runtime-or-generated"))
                        break
    checks = [sg._chk("A5.1", "A5 runtime/generated/copyright scan", not bad,
                      "prohibited entries: %d, submodule gitlinks classified: %d"
                      % (len(bad), len(submodules)))]
    for i, (path, why) in enumerate(bad[:20]):
        checks.append(sg._chk("A5.%02d" % (i + 2), "A5 prohibited entry: %s" % path,
                              False, why))
    return checks


def gate_a6(repo, identity, manifest):
    """Reuses the Staleness Guard. Never fetches."""
    base = manifest["baseline"]
    required = ("expected_branch", "expected_head")
    missing = [f for f in required if f not in base]
    if missing:
        return [sg._chk("A6.0", "A6 baseline completeness", False,
                        "baseline missing: %s" % ", ".join(missing))]
    checks = sg.observe(repo, identity, base, None)
    out = []
    for c in checks:
        out.append({"id": "A6." + c["id"], "label": "A6 " + c["label"],
                    "status": c["status"], "evidence": c["evidence"]})
    return out


_PROSE_PASS_RE = re.compile(r"(?i)\b(all (tests )?pass(ed|ing)?|everything pass(ed|es)?|"
                            r"tests are green|no failures)\b")


def gate_a7(manifest):
    checks = []
    suites = manifest["required_test_suites"]
    for i, s in enumerate(suites, 1):
        name = s["name"]
        prefix = "A7.%d" % i
        have_obs = any(k.startswith("observed_") and k != "observed_failures" for k in s)
        if not have_obs:
            checks.append(sg._chk("%s.0" % prefix, "A7 evidence present for %s" % name,
                                  False, "no observed counts supplied; a suite cannot "
                                         "be reported without measurement", stopped=True))
            continue
        if _PROSE_PASS_RE.search(s["command"]):
            checks.append(sg._chk("%s.P" % prefix, "A7 prose-only claim for %s" % name,
                                  False, "the command field contains an unsupported "
                                         "success claim rather than a command"))
        mismatches = []
        for field in ("passed", "failed", "skipped", "errors", "collected"):
            e, o = "expected_" + field, "observed_" + field
            if e in s and o in s and s[e] != s[o]:
                mismatches.append("%s expected %d observed %d" % (field, s[e], s[o]))
            elif e in s and o not in s:
                mismatches.append("%s expected but not observed" % field)
        # The command is recorded verbatim as DATA so the claim carries its
        # evidence. It is never executed.
        recorded = "command: %s" % s["command"]
        checks.append(sg._chk("%s.1" % prefix, "A7 test parity for %s" % name,
                              not mismatches,
                              (recorded + "; " + "; ".join(mismatches)) if mismatches
                              else (recorded + "; counts match")))
        if s.get("observed_failed", 0) > s.get("expected_failed", 0):
            checks.append(sg._chk("%s.2" % prefix, "A7 new failures in %s" % name, False,
                                  "%d observed failures against %d expected"
                                  % (s.get("observed_failed", 0), s.get("expected_failed", 0))))
        if "expected_failed" in s and s["expected_failed"] > 0 and \
                "observed_failures" in s and \
                len(s["observed_failures"]) != s["observed_failed"]:
            checks.append(sg._chk("%s.3" % prefix, "A7 failure list completeness for %s" % name,
                                  False, "named failures do not match the observed count"))
    return checks


# --------------------------------------------------------------------------
# Assembly
# --------------------------------------------------------------------------

def run_battery(repo, identity, manifest, policy, policy_hash):
    checks = []
    scope = manifest["change_scope"]
    observed = observe_changes(repo, scope)
    checks.append(sg._chk("A0.1", "A7 policy loaded", True,
                          "policy %s sha256 %s" % (policy["policy_name"], policy_hash)))
    checks.extend(gate_a1(observed, manifest))
    checks.extend(gate_a2(repo, scope, observed))
    checks.extend(gate_a3(repo, scope, observed, policy))
    checks.extend(gate_a4(repo, scope, observed, manifest, policy))
    checks.extend(gate_a5(observed, policy))
    checks.extend(gate_a6(repo, identity, manifest))
    checks.extend(gate_a7(manifest))
    return checks


def _read_manifest(path):
    if path is None:
        raw = sys.stdin.buffer.read()
    else:
        try:
            with open(path, "rb") as fh:
                raw = fh.read(ef.MAX_INPUT_BYTES + 1)
        except OSError:
            raise ef.ValidationError("manifest file could not be read")
    if len(raw) > ef.MAX_INPUT_BYTES:
        raise ef.SafetyLimitError(
            "manifest exceeds the maximum accepted size of %d bytes" % ef.MAX_INPUT_BYTES)
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise ef.ValidationError("manifest is not valid UTF-8")
    try:
        return json.loads(text, parse_constant=_reject_constant)
    except ef.ValidationError:
        raise
    except Exception:
        raise ef.ValidationError("manifest is not valid JSON")


def _err(text):
    sys.stderr.buffer.write(text.encode("utf-8"))
    sys.stderr.buffer.flush()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="a7_battery",
        description="Run the seven read-only A7 safety gates. Executes nothing.")
    parser.add_argument("--repo", default=".")
    parser.add_argument("--format", choices=("markdown", "json"), required=True)
    parser.add_argument("--input", default=None,
                        help="manifest JSON file; stdin if omitted")
    parser.add_argument("--policy", default=None,
                        help="path to a policy file; the bundled minimum by default")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return 0 if exc.code == 0 else 2

    try:
        policy, policy_hash = load_policy(args.policy)
        manifest = _read_manifest(args.input)
        ef.enforce_limits(manifest)
        validate_manifest(manifest, policy)
    except ef.SafetyLimitError as exc:
        _err("a7_battery: safety limit: %s\n" % ef.sanitize_text(str(exc)))
        return 3
    except (ef.ValidationError, PolicyError) as exc:
        _err("a7_battery: invalid input: %s\n" % ef.sanitize_text(str(exc)))
        return 2

    try:
        repo, identity = sg.resolve_repo(args.repo)
        checks = run_battery(repo, identity, manifest, policy, policy_hash)
    except sg.StoppedError as exc:
        checks = [sg._chk("A0.0", "A7 observation", False,
                          ef.sanitize_text(str(exc)), stopped=True)]

    doc = {
        "schema_version": ef.SCHEMA_VERSION,
        "phase": manifest["phase"],
        "scope": "A7 battery over a %s candidate" % manifest["change_scope"]["kind"],
        "checks": checks,
    }
    if "notes" in manifest:
        doc["notes"] = manifest["notes"]

    try:
        norm = ef.normalize(doc)
        text = ef.render_markdown(norm) if args.format == "markdown" else ef.render_json(norm)
    except (ef.ValidationError, ef.SafetyLimitError) as exc:
        _err("a7_battery: %s\n" % ef.sanitize_text(str(exc)))
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
