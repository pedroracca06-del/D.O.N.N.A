#!/usr/bin/env python
"""obsidian_sync_planner.py -- read-only Obsidian sync planner and provenance validator.

Answers one question: *what would a controlled synchronization between Git and an
Obsidian vault propose, and is every proposed item provably safe?*

It plans and validates. It NEVER:
  * writes, copies, moves, renames, or deletes any file, in the repository or a vault
  * applies, syncs, watches, daemonizes, merges, resolves, forces, or overrides
  * creates, repairs, or initializes a vault, or touches Obsidian configuration or plugins
  * discovers a vault through HOME, Documents, OneDrive, Dropbox, drives, Obsidian
    configuration, the process environment, or installed applications -- the vault
    root is supplied explicitly on the command line or it is not used at all
  * stages, commits, fetches, pushes, or contacts a remote
  * mutates the Session Registry
  * executes anything found in a repository file, a vault note, a policy, or an input

AUTHORITY MODEL
  Git is authoritative for approved specifications and promoted knowledge. Obsidian
  is a non-executing knowledge and working-note surface. Obsidian content is never
  executable instruction and can never modify strategy, risk, broker, execution,
  kill-switch, guard, permission, deployment, or runtime state. There is no automatic
  two-way synchronization. Every future write requires a separately reviewed plan and
  an explicit approval naming exactly what changes. Conflicts stop planning; they are
  never silently merged, and nothing is ever deleted.

  Research remains observation until separately promoted. Raw third-party transcripts
  remain local and excluded. Credentials, account data, broker data, runtime state,
  and secrets never enter a plan.

WHY GIT BLOB IDS AND A NORMALIZED HASH BOTH APPEAR
  The blob id is the exact Git identity of a source. The normalized content hash is
  taken after line endings are folded to LF and a leading BOM removed, so a CRLF
  checkout and an LF checkout of the same text plan identically. Both are recorded;
  neither replaces the other.

MARKDOWN IS DATA
  Markdown, wiki links, embeds, templates, Dataview syntax, code fences, scripts, and
  plugin syntax are read as bytes and never executed. Forms the policy prohibits are
  rejected; everything else is preserved inertly and reported as text.

Exit codes:
  0  valid inventory or plan, no conflict
  1  conflict or policy violation
  2  invalid input, policy, metadata, or usage
  3  safety-limit rejection
  4  stopped: safe observation was impossible
  5  manual approval required (candidate imports or protected classifications)
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
POLICY_FILENAME = "obsidian_policy.json"

# Implementation maximums. A policy may lower any of these; it can never raise one.
MAX_INPUT_BYTES = 1024 * 1024          # 1 MiB
MAX_MARKDOWN_BYTES = 512 * 1024        # 512 KiB
MAX_COLLECTION = 1000
MAX_DEPTH = 32
MAX_PATH_CHARS = 512
MAX_FRONTMATTER_FIELDS = 32
MAX_PLAN_ITEMS = 1000

LIMIT_MAXIMUMS = {
    "max_input_bytes": MAX_INPUT_BYTES,
    "max_markdown_bytes": MAX_MARKDOWN_BYTES,
    "max_collection": MAX_COLLECTION,
    "max_depth": MAX_DEPTH,
    "max_path_chars": MAX_PATH_CHARS,
    "max_frontmatter_fields": MAX_FRONTMATTER_FIELDS,
    "max_plan_items": MAX_PLAN_ITEMS,
}

OPERATIONS = ("validate-policy", "inventory", "plan-export", "plan-import", "check-plan")

# Verbs that must never become operations. Driving the parser with one exits 2.
FORBIDDEN_OPERATIONS = (
    "apply", "sync", "watch", "daemon", "write", "copy", "move", "delete",
    "rename", "install", "initialize-vault", "create-vault", "init", "repair",
    "force", "override", "merge", "resolve", "plugin", "plugins",
)

EXPORT_RESULTS = ("create", "unchanged", "update-safe", "conflict", "excluded", "stopped")
IMPORT_RESULTS = ("no-change", "candidate-import", "conflict", "excluded", "stopped")

_ID_RE = re.compile(r"^nova-[0-9a-f]{16}$")
_KEY_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_OID_RE = re.compile(r"^[0-9a-f]{40}$|^[0-9a-f]{64}$")

# YAML constructs the fixed-scalar subset refuses outright.
_YAML_UNSUPPORTED = {
    "&": "anchor", "*": "alias", "!": "tag", "|": "block scalar",
    ">": "folded scalar", "{": "flow mapping", "[": "flow sequence",
    "?": "explicit key", "@": "reserved indicator", "`": "reserved indicator",
    "%": "directive",
}

_CREDENTIAL_RE = re.compile(
    r"(?i)\b[a-z0-9_.-]*(api[_-]?key|secret|token|password|passphrase|cookie|"
    r"authorization|bearer|private[_-]?key|access[_-]?key|refresh[_-]?token|"
    r"client[_-]?secret)[a-z0-9_.-]*\s*[:=]\s*\S")
_CREDENTIAL_FORMAT_RE = re.compile(
    r"(sk-ant-[A-Za-z0-9_-]{8,}|ghp_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|"
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----|xox[baprs]-[A-Za-z0-9-]{10,})")
_MACHINE_PATH_RE = re.compile(
    r"([A-Za-z]:[\\/]|\\\\[A-Za-z0-9._-]+\\|/(?:home|Users)/[A-Za-z0-9._-]+|"
    r"/mnt/[a-z]/|%USERPROFILE%|\$HOME\b|~[/\\][A-Za-z])")
_EXECUTABLE_DIRECTIVE_RE = re.compile(
    r"(?i)(<%[^%]|<script\b|javascript:|```\s*dataviewjs\b|```\s*js\s+engine\b|"
    r"```\s*templater\b|<%tp\.|\bexecute\s*=\s*true\b|\brun_on_open\b)")
_ACCOUNT_RE = re.compile(
    r"(?i)\b(account[_ -]?(number|id)|broker[_ -]?account|order[_ -]?id)\s*[:=]\s*\S")


class PolicyError(Exception):
    """The policy file is missing or unusable -> exit 2."""


class ApprovalRequired(Exception):
    """A candidate import or protected classification needs a person -> exit 5."""


# --------------------------------------------------------------------------
# Policy
# --------------------------------------------------------------------------

POLICY_REQUIRED = (
    "schema_version", "policy_name", "authority_model", "allowed_file_types",
    "export_classes", "import_classes", "candidate_destination_roots",
    "prohibited_import_destination_roots", "prohibited_paths",
    "prohibited_entry_kinds", "prohibited_content_classes",
    "required_provenance_fields", "stable_id", "valid_classifications",
    "valid_authorities", "limits",
)
POLICY_OPTIONAL = ("description", "optional_provenance_fields")

# A source root broad enough to sweep the repository is refused outright.
_TOO_BROAD_ROOTS = {"**", "*", "/**", "./**", ".", "./", "*/**"}

_REQUIRED_PROHIBITED_CATEGORIES = (
    "claude_control", "runtime_state", "raw_transcripts",
    "backups_and_quarantine", "environment_and_credentials",
    "broker_account_and_runtime", "execution_risk_strategy_and_kill_switch",
    "generated_and_temporary", "binaries_and_attachments",
    "scripts_notebooks_and_executables",
)


def _bad(msg):
    raise ef.ValidationError(msg)


def _policy_bad(msg):
    raise PolicyError(msg)


def _reject_constant(name):
    raise ef.ValidationError("non-standard numeric value is not permitted")


def load_policy(path=None):
    p = path or os.path.join(os.path.dirname(os.path.abspath(__file__)), POLICY_FILENAME)
    try:
        raw = open(p, "rb").read()
    except OSError:
        raise PolicyError("the Obsidian policy file could not be read")
    if len(raw) > MAX_INPUT_BYTES:
        raise ef.SafetyLimitError("the policy file exceeds the maximum input size")
    try:
        policy = json.loads(raw.decode("utf-8"), parse_constant=_reject_constant)
    except ef.ValidationError:
        raise
    except Exception:
        raise PolicyError("the Obsidian policy file is not valid JSON")
    if not isinstance(policy, dict):
        raise PolicyError("the Obsidian policy must be a JSON object")
    if policy.get("schema_version") != SCHEMA_VERSION:
        raise PolicyError("unsupported Obsidian policy schema")
    return policy, hashlib.sha256(raw).hexdigest()


def _check_policy_path(value, what):
    if not isinstance(value, str) or not value.strip():
        _policy_bad("%s must be a non-empty string" % what)
    norm = value.replace("\\", "/")
    if norm.startswith("/") or re.match(r"^[A-Za-z]:", norm) or norm.startswith("\\\\"):
        _policy_bad("%s must be relative, not an absolute or machine-specific path" % what)
    if ".." in norm.split("/"):
        _policy_bad("%s must not contain a parent-directory traversal" % what)
    if len(norm) > MAX_PATH_CHARS:
        raise ef.SafetyLimitError("%s exceeds the maximum path length" % what)
    if _MACHINE_PATH_RE.search(norm) or "~" in norm:
        _policy_bad("%s must not contain a machine-specific path" % what)
    return norm


def _check_no_case_dupes(values, what):
    seen = {}
    for v in values:
        folded = v.replace("\\", "/").lower().rstrip("/")
        if folded in seen:
            _policy_bad("%s contains duplicate or case-conflicting entries" % what)
        seen[folded] = v


def validate_policy(policy):
    """Structural validation. Raises PolicyError / ValidationError / SafetyLimitError."""
    missing = [f for f in POLICY_REQUIRED if f not in policy]
    if missing:
        _policy_bad("the policy is missing required field(s): %s" % ", ".join(sorted(missing)))
    unknown = set(policy) - set(POLICY_REQUIRED) - set(POLICY_OPTIONAL)
    if unknown:
        _policy_bad("the policy has unrecognized field(s): %s" % ", ".join(sorted(unknown)))

    # No executable construct anywhere in the policy, at any depth.
    _scan_policy_values(policy)

    am = policy["authority_model"]
    if not isinstance(am, dict):
        _policy_bad("authority_model must be a mapping")
    if am.get("execution_authority") != "none":
        _policy_bad("authority_model execution_authority must be \"none\"")
    for flag, want in (("two_way_automatic_sync", False), ("auto_merge", False),
                       ("deletion", False), ("every_write_requires_named_approval", True)):
        if am.get(flag) is not want:
            _policy_bad("authority_model %s must be %s" % (flag, json.dumps(want)))

    types = policy["allowed_file_types"]
    if types != [".md"]:
        _policy_bad("allowed_file_types must be exactly [\".md\"]")

    if not isinstance(policy["export_classes"], dict) or not policy["export_classes"]:
        _policy_bad("export_classes must be a non-empty mapping")
    if not isinstance(policy["import_classes"], dict) or not policy["import_classes"]:
        _policy_bad("import_classes must be a non-empty mapping")

    valid_status = policy["valid_classifications"]
    if not isinstance(valid_status, list) or not valid_status:
        _policy_bad("valid_classifications must be a non-empty list")
    if policy["valid_authorities"] != ["git", "obsidian"]:
        _policy_bad("valid_authorities must be exactly [\"git\", \"obsidian\"]")

    roots, namespaces = [], []
    for name, spec in sorted(policy["export_classes"].items()):
        if not isinstance(spec, dict):
            _policy_bad("export class %s must be a mapping" % name)
        extra = set(spec) - {"status", "authority", "requires_explicit_selection",
                             "source_roots", "vault_namespace"}
        if extra:
            _policy_bad("export class %s has unrecognized field(s): %s"
                        % (name, ", ".join(sorted(extra))))
        if spec.get("authority") != "git":
            _policy_bad("export class %s must have authority \"git\"" % name)
        if spec.get("status") not in valid_status:
            _policy_bad("export class %s has an unrecognized status" % name)
        if not isinstance(spec.get("requires_explicit_selection"), bool):
            _policy_bad("export class %s requires_explicit_selection must be a boolean" % name)
        srcs = spec.get("source_roots")
        if not isinstance(srcs, list) or not srcs:
            _policy_bad("export class %s must declare at least one source root" % name)
        for root in srcs:
            norm = _check_policy_path(root, "export source root")
            if norm.rstrip("/*") in ("", ".") or norm in _TOO_BROAD_ROOTS:
                _policy_bad("export source root %r is too broad" % root)
            segments = [s for s in norm.split("/") if s and s != "**"]
            if not segments or all(re.search(r"[*?\[]", s) for s in segments):
                _policy_bad("export source root %r is too broad; at least one "
                            "path segment must be literal" % root)
            roots.append(norm)
        ns = _check_policy_path(spec.get("vault_namespace"), "vault namespace")
        namespaces.append(ns)
    _check_no_case_dupes(roots, "export source roots")
    _check_no_case_dupes(namespaces, "vault namespaces")

    dest_roots = []
    for name, spec in sorted(policy["import_classes"].items()):
        if not isinstance(spec, dict):
            _policy_bad("import class %s must be a mapping" % name)
        extra = set(spec) - {"status", "authority", "vault_namespaces",
                             "candidate_destination_root"}
        if extra:
            _policy_bad("import class %s has unrecognized field(s): %s"
                        % (name, ", ".join(sorted(extra))))
        if spec.get("authority") != "obsidian":
            _policy_bad("import class %s must have authority \"obsidian\"" % name)
        if spec.get("status") not in valid_status:
            _policy_bad("import class %s has an unrecognized status" % name)
        nss = spec.get("vault_namespaces")
        if not isinstance(nss, list) or not nss:
            _policy_bad("import class %s must declare at least one vault namespace" % name)
        for ns in nss:
            _check_policy_path(ns, "import vault namespace")
        dest = _check_policy_path(spec.get("candidate_destination_root"),
                                  "candidate destination root")
        dest_roots.append(dest)

    declared = [_check_policy_path(d, "candidate destination root")
                for d in policy["candidate_destination_roots"]]
    if not declared:
        _policy_bad("at least one candidate destination root is required")
    _check_no_case_dupes(declared, "candidate destination roots")
    for d in dest_roots:
        if d not in declared:
            _policy_bad("import candidate destination %r is not a declared "
                        "candidate destination root" % d)

    forbidden_dests = policy["prohibited_import_destination_roots"]
    if not isinstance(forbidden_dests, list) or not forbidden_dests:
        _policy_bad("prohibited_import_destination_roots must be a non-empty list")
    for d in forbidden_dests:
        nd = _check_policy_path(d, "prohibited import destination root")
        for good in declared:
            if _under(good, nd) or _under(nd, good):
                _policy_bad("candidate destination %r overlaps prohibited "
                            "destination %r" % (good, nd))

    prohibited = policy["prohibited_paths"]
    if not isinstance(prohibited, dict):
        _policy_bad("prohibited_paths must be a mapping")
    for cat in _REQUIRED_PROHIBITED_CATEGORIES:
        if cat not in prohibited or not prohibited[cat]:
            _policy_bad("prohibited_paths is missing the required category %s" % cat)
    for cat, pats in sorted(prohibited.items()):
        if not isinstance(pats, list):
            _policy_bad("prohibited_paths[%s] must be a list" % cat)
        for pat in pats:
            _check_policy_path(pat, "prohibited path pattern")

    if not isinstance(policy["prohibited_entry_kinds"], list):
        _policy_bad("prohibited_entry_kinds must be a list")
    for kind in ("symlink", "junction", "submodule", "directory"):
        if kind not in policy["prohibited_entry_kinds"]:
            _policy_bad("prohibited_entry_kinds must include %s" % kind)

    if not isinstance(policy["prohibited_content_classes"], dict) \
            or not policy["prohibited_content_classes"]:
        _policy_bad("prohibited_content_classes must be a non-empty mapping")

    req = policy["required_provenance_fields"]
    if not isinstance(req, list):
        _policy_bad("required_provenance_fields must be a list")
    for field in ("nova_id", "nova_schema", "nova_source", "nova_source_blob",
                  "nova_source_hash", "nova_classification", "nova_authority",
                  "nova_sync_state"):
        if field not in req:
            _policy_bad("required_provenance_fields must include %s" % field)

    sid = policy["stable_id"]
    if not isinstance(sid, dict):
        _policy_bad("stable_id must be a mapping")
    if sid.get("algorithm") != "sha256-prefix":
        _policy_bad("stable_id algorithm must be \"sha256-prefix\"")
    if sid.get("hex_length") != 16:
        _policy_bad("stable_id hex_length must be 16")
    if sid.get("prefix") != "nova-":
        _policy_bad("stable_id prefix must be \"nova-\"")
    if sid.get("rename_policy") != "explicit-migration-only":
        _policy_bad("stable_id rename_policy must be \"explicit-migration-only\"")
    if sid.get("automatic_rename_detection") is not False:
        _policy_bad("stable_id automatic_rename_detection must be false")

    limits = policy["limits"]
    if not isinstance(limits, dict):
        _policy_bad("limits must be a mapping")
    for key, ceiling in sorted(LIMIT_MAXIMUMS.items()):
        if key not in limits:
            _policy_bad("limits is missing %s" % key)
        value = limits[key]
        if not isinstance(value, int) or isinstance(value, bool) or value < 1:
            _policy_bad("limits %s must be a positive integer" % key)
        if value > ceiling:
            raise ef.SafetyLimitError(
                "limits %s (%d) exceeds the implementation maximum (%d); a policy "
                "may lower a limit but never raise one" % (key, value, ceiling))
    return policy


# The command words carry a negative lookbehind for `.` and `*` so a prohibition
# pattern naming an extension (`*.bash`, `*.sh`) is data, while a real command
# (`bash -c`, `curl ...`) still matches.
_EXECUTABLE_POLICY_RE = re.compile(
    r"(?i)(\$\(|`|&&|\|\||<script|javascript:|https?://|ssh://|git@|"
    r"(?<![.\w*])(sudo|curl|wget|bash|eval|exec)\b|(?<![.\w*])sh\s+-c\b)")


def _scan_policy_values(node, depth=0):
    if depth > MAX_DEPTH:
        raise ef.SafetyLimitError("the policy nests deeper than the maximum depth")
    if isinstance(node, dict):
        for k, v in node.items():
            _scan_policy_values(k, depth + 1)
            _scan_policy_values(v, depth + 1)
    elif isinstance(node, list):
        for v in node:
            _scan_policy_values(v, depth + 1)
    elif isinstance(node, str):
        if _EXECUTABLE_POLICY_RE.search(node) or _CREDENTIAL_FORMAT_RE.search(node):
            _policy_bad("the policy contains an executable construct, URL, or "
                        "credential-shaped value")
        if _MACHINE_PATH_RE.search(node) or node.startswith("\\\\"):
            _policy_bad("the policy contains a machine-specific path")


# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------

def _norm(path):
    return path.replace("\\", "/").strip("/")


def _under(root, path):
    """True when `path` is `root` or lies beneath it. Both repository-relative."""
    r, p = _norm(root), _norm(path)
    return p == r or p.startswith(r + "/")


def _matches(path, pattern):
    p, pat = _norm(path), pattern.replace("\\", "/")
    if pat.endswith("/**"):
        return _under(pat[:-3], p)
    if pat.startswith("**/"):
        tail = pat[3:]
        if tail.endswith("/**"):
            base = tail[:-3]
            parts = p.split("/")
            return any(parts[i] == base for i in range(len(parts) - 1))
        return fnmatch.fnmatch(p, pat) or fnmatch.fnmatch(p, tail) \
            or any(fnmatch.fnmatch(seg, tail) for seg in p.split("/"))
    return fnmatch.fnmatch(p, pat) or fnmatch.fnmatch(os.path.basename(p), pat)


def prohibited_reason(path, policy):
    """Return the prohibiting category, or None."""
    for cat in sorted(policy["prohibited_paths"]):
        for pat in policy["prohibited_paths"][cat]:
            if _matches(path, pat):
                return cat
    return None


def check_relative(path, what, limits):
    if not isinstance(path, str) or not path.strip():
        _bad("%s must be a non-empty string" % what)
    norm = path.replace("\\", "/")
    if norm.startswith("/") or re.match(r"^[A-Za-z]:", norm) or norm.startswith("\\\\"):
        _bad("%s must be relative, not absolute" % what)
    if ".." in norm.split("/"):
        _bad("%s must not contain a parent-directory traversal" % what)
    if len(norm) > limits["max_path_chars"]:
        raise ef.SafetyLimitError("%s exceeds the maximum path length" % what)
    if _MACHINE_PATH_RE.search(norm):
        _bad("%s must not contain a machine-specific path" % what)
    return _norm(norm)


def escapes_root(root_real, candidate_abs):
    """True when the candidate resolves outside the explicit root (symlink/junction)."""
    real = os.path.realpath(candidate_abs)
    root = os.path.realpath(root_real)
    try:
        common = os.path.commonpath([os.path.normcase(real), os.path.normcase(root)])
    except ValueError:
        return True
    return common != os.path.normcase(root)


# --------------------------------------------------------------------------
# Fixed-scalar frontmatter (a deliberately tiny subset; not YAML)
# --------------------------------------------------------------------------

class Frontmatter:
    __slots__ = ("fields", "body_offset")

    def __init__(self, fields, body_offset):
        self.fields = fields
        self.body_offset = body_offset


def parse_frontmatter(text, limits):
    """Parse the fixed scalar subset. Every value is a string; nothing is coerced.

    Supported: a document opening with a `---` line, then `key: value` lines, then a
    closing `---` line. Keys are lowercase identifiers. Values are plain scalars, or
    a double-quoted scalar containing no escape sequence. Nothing else is supported --
    no lists, no nesting, no comments, no blank lines, no anchors, aliases, tags,
    block or folded scalars, flow collections, directives, merge keys, multiple
    documents, or implicit type coercion. Unsupported input is rejected, never guessed.
    """
    if text.startswith("﻿"):
        _bad("frontmatter must not begin with a byte-order mark")
    lines = text.split("\n")
    if not lines or lines[0].rstrip("\r") != "---":
        _bad("the note does not begin with a frontmatter block")
    fields, order = {}, []
    idx = 1
    while True:
        if idx >= len(lines):
            _bad("the frontmatter block is not terminated")
        raw = lines[idx].rstrip("\r")
        if raw == "---":
            idx += 1
            break
        if raw.strip() == "":
            _bad("the frontmatter contains a blank line, which is not supported")
        if "\t" in raw:
            _bad("the frontmatter contains a tab, which is not supported")
        if raw != raw.lstrip(" "):
            _bad("the frontmatter contains indentation, so nesting is not supported")
        if raw.lstrip().startswith("#"):
            _bad("the frontmatter contains a comment, which is not supported")
        if raw.startswith("<<"):
            _bad("the frontmatter contains a merge key, which is not supported")
        if ":" not in raw:
            _bad("the frontmatter line %r is not a key/value pair" % raw[:40])
        key, _, value = raw.partition(":")
        key = key.strip()
        if not _KEY_RE.match(key):
            _bad("the frontmatter key %r is not a lowercase identifier" % key[:40])
        if key in fields:
            _bad("the frontmatter defines %s more than once" % key)
        value = value.strip()
        if value == "":
            _bad("the frontmatter key %s has an empty value" % key)
        first = value[0]
        if first in _YAML_UNSUPPORTED:
            _bad("the frontmatter uses an unsupported YAML %s"
                 % _YAML_UNSUPPORTED[first])
        if first == '"':
            if len(value) < 2 or value[-1] != '"' or "\\" in value:
                _bad("the frontmatter value for %s is not a plain quoted scalar" % key)
            value = value[1:-1]
            if '"' in value:
                _bad("the frontmatter value for %s is not a plain quoted scalar" % key)
        elif "'" == first:
            _bad("the frontmatter uses single quotes, which are not supported")
        fields[key] = value
        order.append(key)
        if len(order) > limits["max_frontmatter_fields"]:
            raise ef.SafetyLimitError("the frontmatter declares more fields than "
                                      "the maximum")
        idx += 1
    body_offset = len("\n".join(lines[:idx])) + (1 if idx < len(lines) else 0)
    return Frontmatter(fields, body_offset)


def validate_provenance(fields, policy, limits, expect_authority=None):
    """Validate NOVA control metadata. Every vault value is untrusted."""
    required = policy["required_provenance_fields"]
    optional = policy.get("optional_provenance_fields", [])
    known = set(required) | set(optional)

    for key, value in sorted(fields.items()):
        if not key.startswith("nova_"):
            continue
        if key not in known:
            _bad("unknown NOVA control field %s" % key)
        if _CREDENTIAL_RE.search("%s: %s" % (key, value)) \
                or _CREDENTIAL_FORMAT_RE.search(value):
            _bad("the NOVA control field %s holds a credential-shaped value" % key)
        if _MACHINE_PATH_RE.search(value):
            _bad("the NOVA control field %s holds a machine-specific path" % key)
        if _EXECUTABLE_DIRECTIVE_RE.search(value):
            _bad("the NOVA control field %s holds an executable directive" % key)

    missing = [f for f in required if f not in fields]
    if missing:
        _bad("missing required provenance field(s): %s" % ", ".join(sorted(missing)))

    if fields["nova_schema"] != str(SCHEMA_VERSION):
        _bad("nova_schema must be %d" % SCHEMA_VERSION)
    if not _ID_RE.match(fields["nova_id"]):
        _bad("nova_id is malformed")
    if fields["nova_authority"] not in policy["valid_authorities"]:
        _bad("nova_authority is not a recognized authority")
    if expect_authority and fields["nova_authority"] != expect_authority:
        _bad("nova_authority claims %s where %s is required"
             % (fields["nova_authority"], expect_authority))
    if fields["nova_classification"] not in policy["valid_classifications"]:
        _bad("nova_classification is not a recognized classification")
    if not _OID_RE.match(fields["nova_source_blob"]):
        _bad("nova_source_blob is not a full git object id")
    if not _SHA256_RE.match(fields["nova_source_hash"]):
        _bad("nova_source_hash is not a sha-256 digest")
    if "nova_last_sync_hash" in fields and not _SHA256_RE.match(fields["nova_last_sync_hash"]):
        _bad("nova_last_sync_hash is not a sha-256 digest")
    if fields["nova_sync_state"] not in ("synchronized", "local-only", "pending"):
        _bad("nova_sync_state is not a recognized state")
    check_relative(fields["nova_source"], "nova_source", limits)
    return fields


# --------------------------------------------------------------------------
# Identity and hashing
# --------------------------------------------------------------------------

def stable_id(authority, source_path):
    """nova-<first 16 hex of sha256(authority + NUL + normalized source path)>.

    Deterministic and documented. It contains no username and no machine path. It is
    stable for the same source identity, and it changes when the source path changes,
    which is why a rename requires an explicit migration rather than automatic rename
    detection. A note claiming an id is never trusted: the id is always recomputed.
    """
    payload = ("%s\x00%s" % (authority, _norm(source_path))).encode("utf-8")
    return "nova-" + hashlib.sha256(payload).hexdigest()[:16]


def normalize_bytes(raw):
    """Fold CRLF/CR to LF and drop a leading BOM, so the hash is logically stable."""
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    return raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def content_hash(raw):
    return hashlib.sha256(normalize_bytes(raw)).hexdigest()


def decode_markdown(raw, what):
    try:
        return normalize_bytes(raw).decode("utf-8")
    except UnicodeDecodeError:
        _bad("%s is not valid UTF-8; the encoding is unsupported" % what)


def note_body_hash(text, fm):
    """Hash the note body only.

    A note can never carry the hash of its own complete file -- that is circular --
    so provenance records the body. On export the body *is* the source content, so
    at the moment of synchronization the body hash equals the source hash, and any
    later divergence is exactly an independent vault edit.
    """
    return hashlib.sha256(text[fm.body_offset:].encode("utf-8")).hexdigest()


def item_hash(item):
    """Deterministic identity of a plan item, over its stable fields only."""
    payload = {k: v for k, v in item.items() if k != "item_hash"}
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:32]


# --------------------------------------------------------------------------
# Content prohibitions
# --------------------------------------------------------------------------

def content_violations(text, policy):
    """Ordered list of prohibited content classes present. Never returns the text."""
    found = []
    if _CREDENTIAL_RE.search(text) or _CREDENTIAL_FORMAT_RE.search(text):
        found.append("credential_shaped")
    if _MACHINE_PATH_RE.search(text):
        found.append("machine_specific_path")
    if _ACCOUNT_RE.search(text):
        found.append("broker_or_account_identifier")
    if _EXECUTABLE_DIRECTIVE_RE.search(text):
        found.append("executable_directive")
    declared = policy["prohibited_content_classes"]
    return [f for f in found if f in declared]


# --------------------------------------------------------------------------
# Repository observation (all Git through the A7 read-only allowlist)
# --------------------------------------------------------------------------

def _git_ok(repo, args):
    return a7._git_ok(repo, args)


def repo_head(repo):
    return _git_ok(repo, ["rev-parse", "HEAD"]).strip()


def tracked_files(repo):
    out = _git_ok(repo, ["ls-files", "-z"])
    return sorted(p for p in out.split("\0") if p)


def blob_id(repo, path):
    rc, out, _err = a7._git(repo, ["rev-parse", "HEAD:%s" % path])
    if rc != 0 or not out.strip():
        return None
    return out.strip()


def blob_bytes(repo, oid):
    text = _git_ok(repo, ["cat-file", "blob", oid])
    return text.encode("utf-8", "surrogateescape")


def gitlink_paths(repo):
    out = _git_ok(repo, ["ls-files", "-s", "-z"])
    links = set()
    for entry in out.split("\0"):
        if entry.startswith("160000"):
            parts = entry.split("\t", 1)
            if len(parts) == 2:
                links.add(_norm(parts[1]))
    return links


# --------------------------------------------------------------------------
# Vault observation (explicit root only -- never discovered)
# --------------------------------------------------------------------------

def vault_notes(vault_root, limits):
    """Sorted vault-relative Markdown paths under the explicitly supplied root."""
    root = os.path.abspath(vault_root)
    if not os.path.isdir(root):
        raise sg.StoppedError("the supplied vault path does not exist")
    found = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in (".obsidian", ".trash", ".git"))
        for name in sorted(filenames):
            if not name.lower().endswith(".md"):
                continue
            full = os.path.join(dirpath, name)
            rel = _norm(os.path.relpath(full, root))
            found.append(rel)
            if len(found) > limits["max_collection"]:
                raise ef.SafetyLimitError("the vault holds more notes than the maximum")
    return sorted(found)


def read_vault_note(vault_root, rel, limits):
    """Read one note. Refuses a symlink, junction, or anything escaping the root."""
    root = os.path.abspath(vault_root)
    full = os.path.join(root, rel.replace("/", os.sep))
    if os.path.islink(full):
        raise sg.StoppedError("a vault entry is a symbolic link, which is refused")
    if escapes_root(root, full):
        raise sg.StoppedError("a vault entry resolves outside the supplied vault root")
    if not os.path.isfile(full):
        return None
    size = os.path.getsize(full)
    if size > limits["max_markdown_bytes"]:
        raise ef.SafetyLimitError("a vault note exceeds the maximum Markdown size")
    with open(full, "rb") as fh:
        return fh.read()


# --------------------------------------------------------------------------
# Checks
# --------------------------------------------------------------------------

def _chk(cid, label, status, evidence):
    return {"id": cid, "label": label, "status": status, "evidence": evidence}


_RESULT_STATUS = {
    "create": "pass", "unchanged": "pass", "update-safe": "pass",
    "no-change": "pass", "excluded": "informational",
    "candidate-import": "warning", "conflict": "fail", "stopped": "stopped",
}


# --------------------------------------------------------------------------
# Baselines
# --------------------------------------------------------------------------

def registry_checks(registry_path, session_id, repo, identity, head):
    """Read-only Session Registry freshness. Never writes, never locks."""
    checks = []
    if not registry_path:
        return checks, False
    if os.path.exists(registry_path + ".lock"):
        return [_chk("N1", "registry lock", "stopped",
                     "a registry lock is present; another process may be writing")], True
    if not os.path.isfile(registry_path):
        return [_chk("N1", "registry present", "stopped",
                     "no registry file at the supplied location")], True
    try:
        registry = sr.read_registry(registry_path)
    except Exception as exc:
        return [_chk("N1", "registry readable", "stopped",
                     ef.sanitize_text(str(exc)))], True
    rec = None
    for s in registry["sessions"]:
        if s["session_id"] == session_id:
            rec = s
            break
    if rec is None:
        return [_chk("N1", "registry session", "stopped",
                     "no session with the supplied id is registered")], True
    from datetime import datetime, timezone
    state = sr.classify(rec, datetime.now(timezone.utc), sr.DEFAULT_STALE_SECONDS)
    stopped = False
    checks.append(_chk("N1", "registry session", "pass",
                       "found, observed %s" % state))
    for cid, label, ok, ev in (
            ("N2", "registry session active", rec["status"] == "active",
             "status %s" % rec["status"]),
            ("N3", "registry session fresh", state == "live",
             "observed %s" % state),
            ("N4", "registry worktree", rec["worktree_identity"] == identity,
             "expected %s, observed %s" % (rec["worktree_identity"], identity)),
            ("N5", "registry expected commit", rec["expected_commit"] == head,
             "registry %s the observed HEAD"
             % ("matches" if rec["expected_commit"] == head else "does NOT match"))):
        checks.append(_chk(cid, label, "pass" if ok else "stopped", ev))
        stopped = stopped or not ok
    return checks, stopped


# --------------------------------------------------------------------------
# Export planning
# --------------------------------------------------------------------------

def _export_class_for(path, policy):
    for name, spec in sorted(policy["export_classes"].items()):
        for root in spec["source_roots"]:
            if _matches(path, root):
                return name, spec, _norm(root.rstrip("*").rstrip("/"))
    return None, None, None


def _destination(spec, root_prefix, path):
    tail = _norm(path)
    if root_prefix and _under(root_prefix, tail):
        tail = tail[len(_norm(root_prefix)):].lstrip("/")
    return "%s/%s" % (_norm(spec["vault_namespace"]), tail)


def plan_export(repo, identity, vault_root, policy, limits, selection, head):
    """Classify every eligible Git source into exactly one export result."""
    items, notes = [], []
    selected = set(_norm(p) for p in (selection or []))
    tracked = tracked_files(repo)
    links = gitlink_paths(repo)
    if len(tracked) > limits["max_collection"] * 10:
        notes.append("the repository holds more tracked files than are shown; only "
                     "policy-eligible sources are considered")

    seen_ids, seen_dests = {}, {}
    for path in tracked:
        norm = _norm(path)
        cls_name, spec, root_prefix = _export_class_for(norm, policy)
        if cls_name is None:
            continue
        if spec["requires_explicit_selection"] and norm not in selected:
            continue
        if selected and norm not in selected:
            continue

        result, reason = None, ""
        if norm in links:
            result, reason = "excluded", "the source is a submodule gitlink"
        elif not norm.lower().endswith(".md"):
            result, reason = "excluded", "the source is not Markdown"
        else:
            cat = prohibited_reason(norm, policy)
            if cat:
                result, reason = "excluded", "prohibited path class: %s" % cat

        oid = blob_id(repo, norm) if result is None else None
        if result is None and oid is None:
            result, reason = "stopped", "the source blob could not be resolved"

        raw = None
        if result is None:
            raw = blob_bytes(repo, oid)
            if len(raw) > limits["max_markdown_bytes"]:
                result, reason = "excluded", "the source exceeds the maximum Markdown size"

        text = None
        if result is None:
            try:
                text = decode_markdown(raw, "the source")
            except ef.ValidationError as exc:
                result, reason = "excluded", ef.sanitize_text(str(exc))

        if result is None:
            bad = content_violations(text, policy)
            if bad:
                result, reason = "excluded", "prohibited content class: %s" % bad[0]

        nid = stable_id("git", norm)
        dest = _destination(spec, root_prefix, norm)
        try:
            check_relative(dest, "vault destination", limits)
        except ef.ValidationError as exc:
            result, reason = "stopped", ef.sanitize_text(str(exc))

        src_hash = content_hash(raw) if raw is not None else None
        observed_hash, prior_blob, prior_hash = None, None, None

        if result is None:
            if nid in seen_ids and seen_ids[nid] != norm:
                result, reason = "conflict", "the stable id is already used by another source"
            elif dest.lower() in seen_dests and seen_dests[dest.lower()] != norm:
                result, reason = "conflict", "another source already plans this destination"

        if result is None:
            try:
                existing = read_vault_note(vault_root, dest, limits)
            except sg.StoppedError as exc:
                existing, result, reason = None, "stopped", ef.sanitize_text(str(exc))
            if result is None:
                if existing is None:
                    result, reason = "create", "no note exists at the destination"
                else:
                    try:
                        vtext = decode_markdown(existing, "the destination note")
                        fm = parse_frontmatter(vtext, limits)
                        validate_provenance(fm.fields, policy, limits)
                    except (ef.ValidationError, ef.SafetyLimitError) as exc:
                        result = "conflict"
                        reason = "the destination note's provenance is unusable: %s" \
                                 % ef.sanitize_text(str(exc))
                    else:
                        observed_hash = note_body_hash(vtext, fm)
                        prior_blob = fm.fields["nova_source_blob"]
                        prior_hash = fm.fields.get("nova_last_sync_hash")
                        if fm.fields["nova_id"] != nid:
                            result, reason = "conflict", \
                                "the destination note carries a different stable id"
                        elif _norm(fm.fields["nova_source"]) != norm:
                            result, reason = "conflict", \
                                "the destination note names a different source"
                        elif prior_hash is None:
                            # Without a recorded body hash an independent vault edit
                            # cannot be excluded, so nothing may be called safe.
                            result, reason = "conflict", \
                                "the note records no last-synchronized body hash, so " \
                                "an independent vault edit cannot be ruled out"
                        else:
                            vault_changed = observed_hash != prior_hash
                            git_changed = oid != prior_blob
                            if vault_changed and git_changed:
                                result, reason = "conflict", \
                                    "both the source and the note changed since the " \
                                    "last synchronization"
                            elif vault_changed:
                                result, reason = "conflict", \
                                    "the note changed independently of the source"
                            elif git_changed:
                                result, reason = "update-safe", \
                                    "the source changed and the note matches the last " \
                                    "synchronized content"
                            else:
                                result, reason = "unchanged", \
                                    "the source and the note both match the last " \
                                    "synchronization"

        seen_ids.setdefault(nid, norm)
        seen_dests.setdefault(dest.lower(), norm)

        item = {
            "schema_version": SCHEMA_VERSION,
            "nova_id": nid,
            "title": os.path.basename(norm)[:-3] if norm.lower().endswith(".md") else os.path.basename(norm),
            "classification": spec["status"],
            "authority": "git",
            "source_repository": identity,
            "source_path": norm,
            "source_blob": oid,
            "source_hash": src_hash,
            "destination": dest,
            "operation": result,
            "prior_source_blob": prior_blob,
            "prior_source_hash": prior_hash,
            "observed_destination_hash": observed_hash,
            "conflict_status": "conflict" if result == "conflict" else "none",
            "conflict_reason": reason if result in ("conflict", "stopped", "excluded") else "",
        }
        item["item_hash"] = item_hash(item)
        items.append(item)
        if len(items) > limits["max_plan_items"]:
            raise ef.SafetyLimitError("the export plan holds more items than the maximum")

    items.sort(key=lambda i: (i["destination"].lower(), i["nova_id"]))
    return items, notes


# --------------------------------------------------------------------------
# Import planning (strictly more restrictive than export)
# --------------------------------------------------------------------------

def _import_class_for(rel, policy):
    for name, spec in sorted(policy["import_classes"].items()):
        for ns in spec["vault_namespaces"]:
            if _under(ns, rel):
                return name, spec, _norm(ns)
    return None, None, None


def plan_import(repo, identity, vault_root, policy, limits, selection, head):
    """Classify every vault note into exactly one import result. Writes nothing."""
    items, notes = [], []
    selected = set(_norm(p) for p in (selection or []))
    tracked = set(tracked_files(repo))
    approval_needed = False

    for rel in vault_notes(vault_root, limits):
        cls_name, spec, ns = _import_class_for(rel, policy)
        if cls_name is None:
            continue
        if selected and rel not in selected:
            continue

        result, reason = None, ""
        nid = None
        source_path = None
        dest = None
        observed_hash = None
        prior_hash = None

        try:
            raw = read_vault_note(vault_root, rel, limits)
        except sg.StoppedError as exc:
            raw, result, reason = None, "stopped", ef.sanitize_text(str(exc))
        except ef.SafetyLimitError as exc:
            raw, result, reason = None, "excluded", ef.sanitize_text(str(exc))

        text = None
        if result is None:
            try:
                text = decode_markdown(raw, "the note")
            except ef.ValidationError as exc:
                result, reason = "excluded", ef.sanitize_text(str(exc))

        fields = None
        if result is None:
            try:
                fm = parse_frontmatter(text, limits)
                fields = validate_provenance(fm.fields, policy, limits,
                                             expect_authority="obsidian")
                observed_hash = note_body_hash(text, fm)
            except (ef.ValidationError, ef.SafetyLimitError) as exc:
                result, reason = "conflict", \
                    "provenance is missing, malformed, or contradictory: %s" \
                    % ef.sanitize_text(str(exc))

        if result is None:
            if fields["nova_classification"] != spec["status"]:
                result, reason = "conflict", \
                    "the note claims a classification its namespace does not permit"
            elif fields["nova_classification"] in ("approved-spec", "approved-doc"):
                result, reason = "conflict", "authority escalation: an approved " \
                    "classification cannot originate in the vault"

        if result is None:
            nid = stable_id("obsidian", rel)
            if fields["nova_id"] != nid:
                result, reason = "conflict", \
                    "the note's stable id does not match its vault identity; a rename " \
                    "requires an explicit migration"

        if result is None:
            try:
                source_path = check_relative(fields["nova_source"], "nova_source", limits)
            except (ef.ValidationError, ef.SafetyLimitError) as exc:
                result, reason = "conflict", ef.sanitize_text(str(exc))

        if result is None:
            dest = "%s/%s" % (_norm(spec["candidate_destination_root"]),
                              rel[len(ns):].lstrip("/"))
            if _norm(source_path) != _norm(dest):
                result, reason = "conflict", \
                    "the note's declared source does not match its authorized destination"

        if result is None:
            if not any(_under(root, dest) for root in policy["candidate_destination_roots"]):
                result, reason = "excluded", \
                    "the destination is not an authorized candidate path"
            else:
                for bad_root in policy["prohibited_import_destination_roots"]:
                    if _under(bad_root, dest):
                        result, reason = "excluded", \
                            "the destination lies under a prohibited root"
                        break

        if result is None:
            cat = prohibited_reason(dest, policy)
            if cat is None:
                cat = prohibited_reason(rel, policy)
            if cat:
                result, reason = "excluded", "prohibited path class: %s" % cat

        if result is None:
            bad = content_violations(text, policy)
            if bad:
                result, reason = "excluded", "prohibited content class: %s" % bad[0]

        if result is None:
            prior_hash = fields.get("nova_last_sync_hash")
            if dest in tracked:
                existing_oid = blob_id(repo, dest)
                existing = blob_bytes(repo, existing_oid) if existing_oid else None
                repo_hash = content_hash(existing) if existing is not None else None
                if repo_hash == observed_hash:
                    result, reason = "no-change", \
                        "the repository candidate already matches the note"
                elif prior_hash and repo_hash and prior_hash != repo_hash:
                    result, reason = "conflict", \
                        "the repository candidate changed independently of the note"
                else:
                    result, reason = "candidate-import", \
                        "a person must review and approve this candidate"
            else:
                result, reason = "candidate-import", \
                    "a person must review and approve this new candidate"

        if result == "candidate-import":
            approval_needed = True

        item = {
            "schema_version": SCHEMA_VERSION,
            "nova_id": nid or stable_id("obsidian", rel),
            "title": os.path.basename(rel)[:-3] if rel.lower().endswith(".md") else os.path.basename(rel),
            "classification": spec["status"],
            "authority": "obsidian",
            "source_repository": identity,
            "source_path": rel,
            "source_blob": None,
            "source_hash": observed_hash,
            "destination": dest or "",
            "operation": result,
            "prior_source_blob": None,
            "prior_source_hash": prior_hash,
            "observed_destination_hash": observed_hash,
            "conflict_status": "conflict" if result == "conflict" else "none",
            "conflict_reason": reason if result != "no-change" else "",
        }
        item["item_hash"] = item_hash(item)
        items.append(item)
        if len(items) > limits["max_plan_items"]:
            raise ef.SafetyLimitError("the import plan holds more items than the maximum")

    items.sort(key=lambda i: (i["source_path"].lower(), i["nova_id"]))
    notes.append("An import plan is not approval. Nothing is written to the "
                 "repository; every candidate needs Pedro's separate approval.")
    return items, notes, approval_needed


# --------------------------------------------------------------------------
# check-plan
# --------------------------------------------------------------------------

PLAN_ITEM_FIELDS = (
    "schema_version", "nova_id", "title", "classification", "authority",
    "source_repository", "source_path", "source_blob", "source_hash",
    "destination", "operation", "prior_source_blob", "prior_source_hash",
    "observed_destination_hash", "conflict_status", "conflict_reason", "item_hash",
)


def check_plan(doc, policy, limits):
    """Re-validate an emitted plan structurally and recompute every item hash."""
    checks = []
    if not isinstance(doc, dict):
        _bad("the plan must be a JSON object")
    if doc.get("schema_version") != SCHEMA_VERSION:
        _bad("unsupported plan schema_version")
    direction = doc.get("direction")
    if direction not in ("export", "import"):
        _bad("the plan must declare direction \"export\" or \"import\"")
    items = doc.get("items")
    if not isinstance(items, list):
        _bad("the plan must carry an items list")
    if len(items) > limits["max_plan_items"]:
        raise ef.SafetyLimitError("the plan holds more items than the maximum")
    allowed = EXPORT_RESULTS if direction == "export" else IMPORT_RESULTS

    checks.append(_chk("P1", "plan direction", "pass", direction))
    checks.append(_chk("P2", "plan items", "pass", "%d item(s)" % len(items)))

    ids, dests, sources = {}, {}, {}
    conflicts = approval = 0
    for n, item in enumerate(items, 1):
        pre = "P%03d" % n
        if not isinstance(item, dict):
            _bad("plan item %d must be a mapping" % n)
        missing = [f for f in PLAN_ITEM_FIELDS if f not in item]
        if missing:
            _bad("plan item %d is missing field(s): %s" % (n, ", ".join(sorted(missing))))
        extra = set(item) - set(PLAN_ITEM_FIELDS)
        if extra:
            _bad("plan item %d has unrecognized field(s): %s"
                 % (n, ", ".join(sorted(extra))))
        if item["operation"] not in allowed:
            _bad("plan item %d has an operation this direction does not allow" % n)
        if not _ID_RE.match(item["nova_id"]):
            _bad("plan item %d has a malformed nova_id" % n)
        if item["authority"] not in policy["valid_authorities"]:
            _bad("plan item %d claims an unrecognized authority" % n)
        if item["classification"] not in policy["valid_classifications"]:
            _bad("plan item %d claims an unrecognized classification" % n)
        check_relative(item["source_path"], "plan item %d source_path" % n, limits)
        if item["destination"]:
            check_relative(item["destination"], "plan item %d destination" % n, limits)

        recomputed = item_hash(item)
        ok = recomputed == item["item_hash"]
        checks.append(_chk(pre, "item %s hash" % item["nova_id"],
                           "pass" if ok else "fail",
                           "recomputed hash %s the recorded one"
                           % ("matches" if ok else "does NOT match")))

        if item["nova_id"] in ids and ids[item["nova_id"]] != item["source_path"]:
            _bad("plan item %d reuses a stable id for a different source" % n)
        ids[item["nova_id"]] = item["source_path"]
        if item["destination"]:
            key = item["destination"].lower()
            if key in dests and dests[key] != item["source_path"]:
                _bad("plan item %d duplicates a destination" % n)
            dests[key] = item["source_path"]
        src = item["source_path"].lower()
        if src in sources and item["destination"] and sources[src] != item["destination"]:
            _bad("plan item %d maps one source to two destinations" % n)
        sources[src] = item["destination"]

        if item["operation"] == "conflict":
            conflicts += 1
        if item["operation"] == "candidate-import":
            approval += 1

    checks.append(_chk("P8", "conflicts", "fail" if conflicts else "pass",
                       "%d conflicting item(s)" % conflicts))
    checks.append(_chk("P9", "candidate imports",
                       "warning" if approval else "pass",
                       "%d item(s) awaiting approval" % approval))
    return checks, conflicts, approval


# --------------------------------------------------------------------------
# Rendering and CLI
# --------------------------------------------------------------------------

def summarize(items, results):
    counts = {r: 0 for r in results}
    for item in items:
        counts[item["operation"]] = counts.get(item["operation"], 0) + 1
    return counts


def item_checks(items, prefix):
    checks = []
    for n, item in enumerate(items, 1):
        result = item["operation"]
        label = "%s -> %s" % (item["source_path"], item["destination"] or "(none)")
        ev = "%s; id %s; item hash %s" % (result, item["nova_id"], item["item_hash"])
        if item["conflict_reason"]:
            ev += "; %s" % item["conflict_reason"]
        checks.append(_chk("%s%03d" % (prefix, n), label,
                           _RESULT_STATUS.get(result, "fail"), ev))
    return checks


def _read_input(path, limits):
    if path is None:
        raw = sys.stdin.buffer.read(limits["max_input_bytes"] + 1)
    else:
        if not os.path.isfile(path):
            _bad("the input file does not exist")
        if os.path.getsize(path) > limits["max_input_bytes"]:
            raise ef.SafetyLimitError("the input exceeds the maximum size")
        with open(path, "rb") as fh:
            raw = fh.read(limits["max_input_bytes"] + 1)
    if len(raw) > limits["max_input_bytes"]:
        raise ef.SafetyLimitError("the input exceeds the maximum size")
    if not raw.strip():
        return {}
    try:
        doc = json.loads(raw.decode("utf-8"), parse_constant=_reject_constant)
    except ef.ValidationError:
        raise
    except Exception:
        _bad("the input is not valid JSON")
    ef.enforce_limits(doc)
    return doc


def _selection(doc, limits):
    if not doc:
        return None
    if not isinstance(doc, dict):
        _bad("the input must be a JSON object")
    if doc.get("schema_version") not in (None, SCHEMA_VERSION):
        _bad("unsupported input schema_version")
    sel = doc.get("select")
    if sel is None:
        return None
    if not isinstance(sel, list):
        _bad("select must be a list of relative paths")
    if len(sel) > limits["max_collection"]:
        raise ef.SafetyLimitError("the selection holds more entries than the maximum")
    return [check_relative(p, "selection entry", limits) for p in sel]


def _emit(doc, fmt):
    norm = ef.normalize(doc)
    text = ef.render_markdown(norm) if fmt == "markdown" else ef.render_json(norm)
    sys.stdout.buffer.write(text.encode("utf-8"))
    sys.stdout.buffer.flush()
    return norm


def _err(text):
    sys.stderr.buffer.write(text.encode("utf-8"))
    sys.stderr.buffer.flush()


def build_parser():
    parser = argparse.ArgumentParser(
        prog="obsidian_sync_planner",
        description="Plan and validate controlled Obsidian synchronization. "
                    "Read-only: it never writes, applies, syncs, merges, or deletes.")
    parser.add_argument("operation", choices=OPERATIONS)
    parser.add_argument("--format", choices=("markdown", "json"), required=True)
    parser.add_argument("--repo", default=None, help="path to a git worktree")
    parser.add_argument("--vault", default=None,
                        help="explicit Obsidian vault root; never discovered")
    parser.add_argument("--policy", default=None, help="policy JSON (defaults to the "
                                                       "sibling obsidian_policy.json)")
    parser.add_argument("--input", default=None,
                        help="selection or plan JSON; stdin if omitted")
    parser.add_argument("--registry", default=None,
                        help="machine-local session registry, read-only")
    parser.add_argument("--session-id", default=None)
    return parser


def main(argv=None):
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return 0 if exc.code == 0 else 2

    try:
        policy, policy_hash = load_policy(args.policy)
        validate_policy(policy)
        limits = policy["limits"]
    except ef.SafetyLimitError as exc:
        _err("obsidian_sync_planner: safety limit: %s\n" % ef.sanitize_text(str(exc)))
        return 3
    except (PolicyError, ef.ValidationError) as exc:
        _err("obsidian_sync_planner: invalid policy: %s\n" % ef.sanitize_text(str(exc)))
        return 2

    op = args.operation
    checks, notes = [], []
    exit_code = 0

    try:
        if op == "validate-policy":
            checks = [
                _chk("V1", "policy schema", "pass", "schema_version %d" % SCHEMA_VERSION),
                _chk("V2", "policy identity", "pass",
                     "%s, sha256 %s" % (policy["policy_name"], policy_hash)),
                _chk("V3", "execution authority", "pass",
                     "declared \"none\"; Obsidian content is never executable instruction"),
                _chk("V4", "two-way automatic sync", "pass", "disabled"),
                _chk("V5", "auto-merge", "pass", "disabled"),
                _chk("V6", "deletion", "pass", "never proposed or performed"),
                _chk("V7", "allowed file types", "pass", "Markdown only"),
                _chk("V8", "export classes", "pass",
                     "%d class(es): %s" % (len(policy["export_classes"]),
                                           ", ".join(sorted(policy["export_classes"])))),
                _chk("V9", "import classes", "pass",
                     "%d class(es): %s" % (len(policy["import_classes"]),
                                           ", ".join(sorted(policy["import_classes"])))),
                _chk("V10", "prohibited path categories", "pass",
                     "%d categories" % len(policy["prohibited_paths"])),
                _chk("V11", "prohibited content classes", "pass",
                     ", ".join(sorted(policy["prohibited_content_classes"]))),
                _chk("V12", "stable id rule", "pass",
                     "sha256-prefix over authority and source path; renames require "
                     "explicit migration; no automatic rename detection"),
            ]
            for key in sorted(LIMIT_MAXIMUMS):
                checks.append(_chk("V13.%s" % key, "limit %s" % key, "pass",
                                   "policy %d, implementation maximum %d"
                                   % (limits[key], LIMIT_MAXIMUMS[key])))
        elif op == "check-plan":
            doc = _read_input(args.input, limits)
            checks, conflicts, approval = check_plan(doc, policy, limits)
            if conflicts:
                exit_code = 1
            elif approval:
                exit_code = 5
        else:
            if not args.repo:
                _bad("%s requires --repo" % op)
            repo, identity = sg.resolve_repo(args.repo)
            head_before = repo_head(repo)
            reg_checks, reg_stopped = registry_checks(
                args.registry, args.session_id, repo, identity, head_before)
            checks.extend(reg_checks)
            if reg_stopped:
                raise sg.StoppedError("the session registry baseline is not usable")

            if op == "inventory":
                tracked = tracked_files(repo)
                for name, spec in sorted(policy["export_classes"].items()):
                    eligible = [p for p in tracked
                                if any(_matches(p, r) for r in spec["source_roots"])
                                and p.lower().endswith(".md")
                                and not prohibited_reason(p, policy)]
                    checks.append(_chk("Q.%s" % name, "export class %s" % name, "pass",
                                       "%d eligible source(s)%s" % (
                                           len(eligible),
                                           "; explicit selection required"
                                           if spec["requires_explicit_selection"] else "")))
                if args.vault:
                    for name, spec in sorted(policy["import_classes"].items()):
                        rels = [r for r in vault_notes(args.vault, limits)
                                if any(_under(ns, r) for ns in spec["vault_namespaces"])]
                        checks.append(_chk("Q.%s" % name, "import class %s" % name,
                                           "pass", "%d vault note(s)" % len(rels)))
                else:
                    notes.append("No vault root was supplied, so no vault namespace was "
                                 "inventoried. A vault is never discovered.")
            else:
                if not args.vault:
                    _bad("%s requires an explicit --vault root" % op)
                # The vault root is never discovered, and it is never created.
                if not os.path.isdir(args.vault):
                    raise sg.StoppedError("the supplied vault path does not exist")
                selection = _selection(_read_input(args.input, limits), limits)
                if op == "plan-export":
                    items, extra = plan_export(repo, identity, args.vault, policy,
                                               limits, selection, head_before)
                    notes.extend(extra)
                    counts = summarize(items, EXPORT_RESULTS)
                    checks.append(_chk("X0", "export plan", "pass", "; ".join(
                        "%s=%d" % (k, counts[k]) for k in EXPORT_RESULTS)))
                    checks.extend(item_checks(items, "X"))
                    if counts["conflict"]:
                        exit_code = 1
                    if counts["stopped"]:
                        exit_code = 4
                else:
                    items, extra, approval = plan_import(repo, identity, args.vault,
                                                         policy, limits, selection,
                                                         head_before)
                    notes.extend(extra)
                    counts = summarize(items, IMPORT_RESULTS)
                    checks.append(_chk("M0", "import plan", "pass", "; ".join(
                        "%s=%d" % (k, counts[k]) for k in IMPORT_RESULTS)))
                    checks.extend(item_checks(items, "M"))
                    if counts["conflict"]:
                        exit_code = 1
                    elif approval:
                        exit_code = 5
                    if counts["stopped"]:
                        exit_code = 4

            head_after = repo_head(repo)
            drifted = head_after != head_before
            checks.append(_chk("Z1", "repository baseline stable during observation",
                               "stopped" if drifted else "pass",
                               "HEAD moved during observation" if drifted
                               else "HEAD unchanged throughout"))
            if drifted:
                exit_code = 4
    except ef.SafetyLimitError as exc:
        _err("obsidian_sync_planner: safety limit: %s\n" % ef.sanitize_text(str(exc)))
        return 3
    except ef.ValidationError as exc:
        _err("obsidian_sync_planner: invalid input: %s\n" % ef.sanitize_text(str(exc)))
        return 2
    except sg.StoppedError as exc:
        checks.append(_chk("Z0", "observation", "stopped", ef.sanitize_text(str(exc))))
        exit_code = 4

    doc = {
        "schema_version": ef.SCHEMA_VERSION,
        "phase": "obsidian sync planning",
        "scope": "read-only plan and provenance validation; nothing is written",
        "checks": checks,
    }
    if notes:
        doc["notes"] = notes
    try:
        norm = _emit(doc, args.format)
    except (ef.ValidationError, ef.SafetyLimitError) as exc:
        _err("obsidian_sync_planner: %s\n" % ef.sanitize_text(str(exc)))
        return 2

    if exit_code:
        return exit_code
    overall = norm["overall_status"]
    if overall == "stopped":
        return 4
    if overall == "failed":
        return 1
    if overall == "warning":
        return 5
    return 0


if __name__ == "__main__":
    sys.exit(main())
