#!/usr/bin/env python
"""codex_relay.py -- deterministic local transport between Claude and Codex.

It moves exactly two things: one validated Claude phase report, and one
structured Codex verdict answering it. It is a mailbox, not an agent.

WHAT IT IS NOT. It does not invoke Codex. It does not call a model. It owns no
subprocess of its own, opens no socket, and reads no environment beyond the paths
it is explicitly handed. It never writes a repository file, never runs Git as a
mutation, and never registers, advances, pauses, resumes, or closes a Session
Registry record. Git and the registry are READ, through the existing read-only
observers, and only to prove that an envelope still describes reality.

A VERDICT IS AN OPINION. `PASS` means one thing: a second reader found no
objection. It is never authorization to modify, commit, push, merge, deploy,
trade, alter risk, or enable execution. Work classified AAM or AM still needs
Pedro's named approval, exactly as before. Nothing in a response is executed, and
no instruction found inside report text, notes, findings, or a summary is ever
followed -- those are DATA.

LOGICAL IDENTITY, NOT MACHINE PATHS. An envelope names a `repository_identity`
and a `worktree_identity`. It never carries an absolute path, because envelopes
also reject machine paths and a tool may not exempt itself from its own rule. The
real local path is supplied to the relay at the command line and verified against
Git and the Session Registry there.

CODEX NEVER WRITES THE MAILBOX. A future runner will point Codex's
`-o/--output-last-message` at a private temporary file. `ingest-response` reads
that file, validates it, and only then records a relay-authored response envelope
through the locked atomic update. Codex's bytes never land in `relay.json`.

ARCHIVE HONESTY. The archive is append-only *by this tool*: it never overwrites,
renames, or deletes an entry, and it stops on a name collision. The hash chain
detects ordinary corruption, truncation, reordering, or partial rewriting. It is
NOT tamper-proof: anyone who can rewrite the mailbox and the whole archive
together can produce a consistent forgery. Treat it as an integrity check, not a
security boundary.

Exit codes:
  0  the operation succeeded
  2  invalid CLI, policy, schema, or envelope
  3  safety-limit rejection
  4  stopped: mailbox, repository, or registry state unusable, or lock contention
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import posixpath
import re
import sys
import time
import uuid
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import evidence_formatter as ef       # noqa: E402
import staleness_guard as sg          # noqa: E402
import session_registry as sr         # noqa: E402
import a7_battery as a7               # noqa: E402  (its read-only git allowlist)

sys.path.pop(0)

SCHEMA_VERSION = 1
POLICY_FILENAME = "relay_policy.json"
VERDICT_SCHEMA_FILENAME = "relay_verdict_schema.json"

MAILBOX_FILENAME = "relay.json"
LOCK_SUFFIX = ".lock"
ARCHIVE_DIRNAME = "archive"

EXIT_OK = 0
EXIT_INVALID = 2
EXIT_LIMIT = 3
EXIT_STOPPED = 4

OPERATIONS = ("validate-policy", "validate-request", "validate-response",
              "cancel-request", "record-rejection",
              "submit", "ingest-response", "inspect", "verify-chain")

# A verb that would imply doing something rather than carrying a message. Refused
# before argparse so the failure names the reason instead of printing usage.
FORBIDDEN_VERBS = frozenset({
    "run", "exec", "review", "retry", "approve", "authorize", "apply", "edit",
    "stage", "commit", "push", "merge", "deploy", "trade", "sync", "watch",
    "daemon", "force", "override", "repair", "delete", "prune", "clear",
    "reset", "resume",
})

ZERO_HASH = "0" * 64

# Implementation maximums. A policy may lower any of these; it can never raise one.
MAX_ENVELOPE_BYTES = 262144
MAX_DEPTH = 32
MAX_FINDINGS = 100
MAX_PATHS = 250
MAX_STRING_CHARS = 8192
MAX_NOTES = 50
MAX_MESSAGES = 500
LOCK_TIMEOUT_SECONDS = 5
LOCK_POLL_SECONDS = 0.05

LIMIT_MAXIMUMS = {
    "max_envelope_bytes": MAX_ENVELOPE_BYTES,
    "max_depth": MAX_DEPTH,
    "max_findings": MAX_FINDINGS,
    "max_paths": MAX_PATHS,
    "max_string_chars": MAX_STRING_CHARS,
    "max_notes": MAX_NOTES,
    "max_messages": MAX_MESSAGES,
    "lock_timeout_seconds": LOCK_TIMEOUT_SECONDS,
}

REQUEST_FIELDS = (
    "schema_version", "message_id", "sequence", "previous_message_sha256",
    "created_at", "sender", "recipient", "phase", "repository_identity",
    "worktree_identity", "branch", "head", "registry_revision",
    "registry_expected_commit", "scope", "change_class", "evidence",
    "evidence_digest", "state",
)

RESPONSE_FIELDS = (
    "schema_version", "message_id", "sequence", "previous_message_sha256",
    "created_at", "sender", "recipient", "phase", "repository_identity",
    "worktree_identity", "branch", "head", "registry_revision",
    "registry_expected_commit", "request_message_id", "response",
)

# A request that can never execute again -- its bound registry revision has been
# overtaken, say -- would otherwise sit pending forever and block the mailbox for
# every future review. This TERMINAL message retires exactly one such request by
# APPENDING to the chain. It deletes nothing, rewrites nothing, and is emphatically
# not a model response: it carries no verdict, consumes no review attempt, and
# approves nothing. It records why the request went stale rather than hiding it.
CANCELLATION_TYPE = "request_cancelled"
CANCELLATION_FIELDS = (
    "schema_version", "message_id", "sequence", "previous_message_sha256",
    "created_at", "sender", "recipient", "message_type", "cancelled_request_id",
    "cancelled_sequence", "phase", "head", "registry_revision", "reason",
    "cancelled_by",
)

# The other way a request finishes without a verdict: the child DID run and DID
# answer, but the answer failed validation and was never recorded. Leaving that
# request pending would block the mailbox and hide the fact that the one attempt
# was spent. This terminal states both plainly. It is not a verdict and not an
# approval, and it never permits a retry -- a new attempt needs a NEW request.
REJECTION_TYPE = "response_rejected"
REJECTION_FIELDS = (
    "schema_version", "message_id", "sequence", "previous_message_sha256",
    "created_at", "sender", "recipient", "message_type", "cancelled_request_id",
    "cancelled_sequence", "phase", "head", "registry_revision",
    "rejection_reason", "attempt_consumed", "recorded_by",
)

VERDICT_FIELDS = ("schema_version", "request_message_id", "phase", "head",
                  "verdict", "summary", "findings", "non_authorization")
FINDING_FIELDS = ("finding_id", "severity", "category", "message", "evidence")

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
_OID_RE = re.compile(r"^[0-9a-f]{40}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_PHASE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_IDENTITY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_BRANCH_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,127}$")
_TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_CATEGORY_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")

# A path that identifies this machine or this user rather than the repository.
_MACHINE_PATH_RE = re.compile(
    r"([A-Za-z]:[\\/]|\\\\[A-Za-z0-9._-]+\\|/(?:home|Users)/[A-Za-z0-9._-]+|"
    r"/mnt/[a-z]/|/cygdrive/[a-z]/|%USERPROFILE%|%HOMEPATH%|\$HOME\b|"
    r"~[/\\][A-Za-z])")

# A credential-shaped value anywhere in an envelope. Matched, never printed.
_CREDENTIAL_RE = re.compile(
    r"(?i)(\b[a-z0-9_.-]*(api[_-]?key|secret|token|password|passphrase|bearer|"
    r"authorization|auth|cookie|credential|private[_-]?key|access[_-]?key|"
    r"client[_-]?secret|refresh[_-]?token)"
    r"[a-z0-9_.-]*\s*[:=]\s*[\"']?[A-Za-z0-9/+_.-]{12,}"
    r"|\bbearer\s+[A-Za-z0-9._-]{16,}"
    r"|sk-ant-[A-Za-z0-9_-]{8,}|gh[pos]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}"
    r"|xox[baprs]-[A-Za-z0-9-]{10,}|-----BEGIN [A-Z ]*PRIVATE KEY-----)")

# A construct that would only be there to be executed by something downstream.
_EXECUTABLE_RE = re.compile(
    r"(?i)(\$\(|`|&&|\|\||;\s*(rm|del|curl|wget|git|python|node)\b|"
    r"(?<![.\w*])(sudo|curl|wget|bash|eval|exec|powershell|pwsh|cmd\.exe|"
    r"invoke-expression|iex|start-process|importlib|__import__|os\.system|"
    r"subprocess)\b|(?<![.\w*])sh\s+-c\b|<script|javascript:|"
    r"^[A-Z_]{3,}=|\bset-content\b|\bout-file\b)")

# A code audit has to be able to SAY `subprocess`, `intelligence/gateway.py`, or
# `ProviderError` without that counting as smuggling. The generic rule above
# cannot distinguish naming a symbol from invoking one, so typed audit fields get
# this narrower rule instead: a bare identifier is data, an INVOCATION is not.
# Everything genuinely executable is still refused -- shells, chaining, scripts,
# encoded payloads, tool invocations, and imperative "run this" instructions.
_AUDIT_EXECUTABLE_RULES = (
    ("command substitution", re.compile(r"\$\(")),
    ("command chaining", re.compile(r"&&|\|\||;\s*\w+\s")),
    ("pipe into interpreter",
     re.compile(r"(?i)\|\s*(?:bash|sh|zsh|python|node|pwsh|powershell)\b")),
    ("shell or tool invocation", re.compile(
        r"(?i)(?<![.\w])(sudo|curl|wget|nc|netcat|chmod|chown|iex|"
        r"invoke-expression|start-process|cmd\.exe|powershell|pwsh)\b")),
    ("interpreter with flags",
     re.compile(r"(?i)(?<![.\w])(?:sh|bash|python|node)\s+-\w")),
    ("markup or scheme payload",
     re.compile(r"(?i)<script|javascript:|data:text/html")),
    # A NAMED symbol is data; an INVOCATION is not. `subprocess` passes,
    # `subprocess.run(` does not.
    ("code invocation", re.compile(
        r"(?:os\.system|subprocess\.(?:run|Popen|call|check_output)|eval|exec|"
        r"__import__|importlib\.import_module|compile)\s*\(")),
    ("imperative instruction", re.compile(
        r"(?i)\b(?:run|execute|apply|paste)\s+(?:the\s+|these\s+|this\s+)?"
        r"(?:following|commands?|scripts?|patch|diff|snippet)\b")),
    ("patch or diff payload",
     re.compile(r"(?m)^\s*(?:diff --git|@@ -|\+\+\+ b/|--- a/)")),
    ("encoded blob", re.compile(r"[A-Za-z0-9+/]{80,}={0,2}")),
)


def audit_executable_reason(text):
    """Name of the first rule a typed audit value violates, or None."""
    for name, rx in _AUDIT_EXECUTABLE_RULES:
        if rx.search(text):
            return name
    return None

# The typed, inert fields a code audit may use. Anything outside this set inside
# an audit block is rejected, so the shape cannot be used to smuggle new keys.
AUDIT_FINDING_FIELDS = (
    "finding_id", "severity", "category", "repository_path", "line_start",
    "line_end", "symbol", "observed_behavior", "technical_risk",
    "evidence_description", "recommended_correction", "test_gap",
    "acceptance_criteria",
)
AUDIT_BLOCK_FIELDS = ("schema_version", "architecture_summary", "findings")
AUDIT_SCHEMA_VERSION = 1
# Fields that may carry inert code references; the rest stay under the generic
# rule. `symbol` and `repository_path` are additionally shape-checked.
AUDIT_CODE_FIELDS = frozenset({
    "repository_path", "symbol", "observed_behavior", "technical_risk",
    "evidence_description", "recommended_correction", "test_gap",
    "acceptance_criteria", "architecture_summary",
})
_SYMBOL_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]{0,127}$")

# A key that would smuggle an action into a document that is supposed to be data.
# Deliberately absent: `path` and `allow`. They are legitimate structural names
# here -- `diff_numstat[].path` and `permission_state.allow` -- and banning them
# would reject every well-formed envelope. Path VALUES are separately validated
# as repository-relative, and `allow` only ever holds a count.
_COMMAND_KEY_RE = re.compile(
    r"(?i)^(command|cmd|args?|argv|shell|exec|execute|entrypoint|script|run|"
    r"env|environment|cwd|binary|program|action|approve|approval|"
    r"authorize|authorization|grant|permission|permissions|enable|"
    r"disable|hook|hooks|subprocess|system|eval|apply|patch|diff_apply|"
    r"trade|order|orders|broker|risk_override|kill_switch)$")

# Intent that no envelope may carry, whatever wrapper it arrives in.
_PROHIBITED_INTENT_RE = re.compile(
    r"(?i)(nova_trading_subsystem_enabled\s*[:=]\s*(true|1|yes|on|enabled)"
    r"|nova_auto_execute\s*[:=]\s*(true|1|yes|on|enabled)"
    r"|\benable\s+(?:live\s+)?(?:trading|execution|the\s+broker)\b"
    r"|\bsubmit\s+(?:a\s+|the\s+)?(?:broker\s+)?order\b"
    r"|\b(?:override|bypass|disable)\s+(?:the\s+)?(?:risk|kill[- ]switch|guard)\b"
    r"|\bthis\s+(?:verdict|pass)\s+(?:is|grants|constitutes)\s+"
    r"(?:approval|authorization|permission)\b)")


class PolicyError(Exception):
    """The policy or verdict schema is missing or unusable -> exit 2."""


def _bad(msg):
    raise ef.ValidationError(msg)


def _reject_constant(_name):
    # NaN / Infinity / -Infinity are never valid in an envelope.
    raise ef.ValidationError("a non-standard numeric value is not permitted")


# --------------------------------------------------------------------------
# Canonical serialization -- one byte sequence per document, on every machine
# --------------------------------------------------------------------------

def canonical_bytes(obj):
    """Deterministic UTF-8 encoding: sorted keys, no padding, no NaN."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def sha256_of(obj):
    return hashlib.sha256(canonical_bytes(obj)).hexdigest()


def evidence_digest_of(evidence):
    """The digest an envelope must carry. Always recomputed, never trusted."""
    return sha256_of(evidence)


# --------------------------------------------------------------------------
# Policy and verdict schema
# --------------------------------------------------------------------------

POLICY_REQUIRED = ("schema_version", "policy_name", "contract", "limits",
                   "enums", "evidence_fields", "operations",
                   "forbidden_operation_words", "planned_reviewer",
                   "non_authorization_sentence")
POLICY_OPTIONAL = ("description",)

CONTRACT_FIXED = {
    "pass_is_not_authorization": True,
    "aam_am_require_named_approval": True,
    "relay_invokes_codex": False,
    "relay_invokes_any_model": False,
    "relay_mutates_repository": False,
    "relay_mutates_session_registry": False,
    "relay_executes_envelope_content": False,
    "envelope_content_is_untrusted_data": True,
    "codex_writes_authoritative_mailbox": False,
    "envelope_carries_machine_paths": False,
    "envelope_may_authorize_trading": False,
    "envelope_may_enable_retired_flags": False,
    "automatic_retry_enabled": False,
    "automatic_resubmission_after_revise": False,
    "archive_is_append_only_by_this_tool": True,
    # Deliberately False. A hash chain finds ordinary corruption; it does not
    # defeat an attacker who can rewrite the mailbox and the archive together.
    "archive_is_cryptographically_tamper_proof": False,
}

ENUMS_FIXED = {
    "sender": ["claude", "codex"],
    "recipient": ["claude", "codex"],
    "request_state": ["pending"],
    "response_verdict": ["PASS", "REVISE", "STOP", "ESCALATE"],
    "finding_severity": ["critical", "high", "medium", "low", "informational"],
    "change_class": ["FA", "AR", "AAM", "AM"],
    "hash_algorithm": ["sha256"],
}

EVIDENCE_FIELDS = ("changed_paths", "collection_digest", "diff_numstat",
                   "notes", "permission_state", "policy_hashes",
                   "repository_state", "test_results")

NON_AUTHORIZATION_SENTENCE = (
    "This verdict grants no permission to modify, commit, push, merge, deploy, "
    "trade, alter risk, or enable execution.")


def _sibling(name):
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), name)


def _load_json_file(path, what):
    try:
        raw = open(path, "rb").read()
    except OSError:
        raise PolicyError("the %s file could not be read" % what)
    if len(raw) > MAX_ENVELOPE_BYTES:
        raise ef.SafetyLimitError("the %s file exceeds the maximum size" % what)
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise PolicyError("the %s file is not valid UTF-8" % what)
    try:
        doc = json.loads(text, parse_constant=_reject_constant)
    except ef.ValidationError:
        raise
    except Exception:
        raise PolicyError("the %s file is not valid JSON" % what)
    return doc, hashlib.sha256(raw).hexdigest()


def load_policy(path=None):
    doc, digest = _load_json_file(path or _sibling(POLICY_FILENAME), "relay policy")
    if not isinstance(doc, dict):
        raise PolicyError("the relay policy must be a JSON object")
    if doc.get("schema_version") != SCHEMA_VERSION:
        raise PolicyError("unsupported relay policy schema")
    return doc, digest


def load_verdict_schema(path=None):
    doc, digest = _load_json_file(path or _sibling(VERDICT_SCHEMA_FILENAME),
                                  "verdict schema")
    if not isinstance(doc, dict):
        raise PolicyError("the verdict schema must be a JSON object")
    return doc, digest


def _scan_policy_text(node, depth=0):
    if depth > MAX_DEPTH:
        raise ef.SafetyLimitError("the policy nests deeper than the maximum depth")
    if isinstance(node, dict):
        for k, v in node.items():
            _scan_policy_text(k, depth + 1)
            _scan_policy_text(v, depth + 1)
    elif isinstance(node, list):
        for v in node:
            _scan_policy_text(v, depth + 1)
    elif isinstance(node, str):
        if _CREDENTIAL_RE.search(node):
            raise PolicyError("the policy contains a credential-shaped value")
        if _MACHINE_PATH_RE.search(node):
            raise PolicyError("the policy contains a machine-specific path")


def validate_policy(policy):
    missing = [f for f in POLICY_REQUIRED if f not in policy]
    if missing:
        raise PolicyError("the policy is missing required field(s): %s"
                          % ", ".join(sorted(missing)))
    unknown = set(policy) - set(POLICY_REQUIRED) - set(POLICY_OPTIONAL)
    if unknown:
        raise PolicyError("the policy has unrecognized field(s): %s"
                          % ", ".join(sorted(unknown)))
    _scan_policy_text(policy)

    contract = policy["contract"]
    if not isinstance(contract, dict):
        raise PolicyError("contract must be a mapping")
    unknown = set(contract) - set(CONTRACT_FIXED)
    if unknown:
        raise PolicyError("contract has unrecognized field(s): %s"
                          % ", ".join(sorted(unknown)))
    for key, want in sorted(CONTRACT_FIXED.items()):
        if key not in contract:
            raise PolicyError("contract is missing %s" % key)
        if contract[key] is not want:
            raise PolicyError(
                "contract %s must be %s; the relay carries messages and grants "
                "no authority, and no policy field may weaken that"
                % (key, json.dumps(want)))

    enums = policy["enums"]
    if not isinstance(enums, dict) or set(enums) != set(ENUMS_FIXED):
        raise PolicyError("enums must define exactly the fixed enumerations")
    for key, want in sorted(ENUMS_FIXED.items()):
        if enums[key] != want:
            raise PolicyError("enum %s is fixed and may not be changed" % key)

    limits = policy["limits"]
    if not isinstance(limits, dict):
        raise PolicyError("limits must be a mapping")
    if "reviews_per_phase_head" not in limits:
        raise PolicyError("limits is missing reviews_per_phase_head")
    if limits["reviews_per_phase_head"] != 1:
        raise PolicyError("reviews_per_phase_head is fixed at 1; the relay caps "
                          "normal operation at one review per completed phase")
    for key, ceiling in sorted(LIMIT_MAXIMUMS.items()):
        if key not in limits:
            raise PolicyError("limits is missing %s" % key)
        value = limits[key]
        if not isinstance(value, int) or isinstance(value, bool) or value < 1:
            raise PolicyError("limits %s must be a positive integer" % key)
        if value > ceiling:
            raise ef.SafetyLimitError(
                "limits %s (%d) exceeds the implementation maximum (%d); a policy "
                "may lower a limit but never raise one" % (key, value, ceiling))
    extra = set(limits) - set(LIMIT_MAXIMUMS) - {"reviews_per_phase_head"}
    if extra:
        raise PolicyError("limits has unrecognized field(s): %s"
                          % ", ".join(sorted(extra)))

    if list(policy["evidence_fields"]) != sorted(EVIDENCE_FIELDS):
        raise PolicyError("evidence_fields is fixed and may not be changed")
    if list(policy["operations"]) != list(OPERATIONS):
        raise PolicyError("operations is fixed; the relay exposes no other "
                          "operation and no alias")
    forbidden = policy["forbidden_operation_words"]
    if not isinstance(forbidden, list) or not forbidden:
        raise PolicyError("forbidden_operation_words must be a non-empty list")
    if not set(forbidden) <= FORBIDDEN_VERBS:
        raise PolicyError("forbidden_operation_words names a word the "
                          "implementation does not refuse")
    if policy["non_authorization_sentence"] != NON_AUTHORIZATION_SENTENCE:
        raise PolicyError("non_authorization_sentence is fixed")

    reviewer = policy["planned_reviewer"]
    if not isinstance(reviewer, dict):
        raise PolicyError("planned_reviewer must be a mapping")
    if reviewer.get("sandbox_mode") != "read-only":
        raise PolicyError("planned_reviewer sandbox_mode is fixed at read-only")
    if reviewer.get("approval_policy") != "never":
        raise PolicyError("planned_reviewer approval_policy is fixed at never")
    if reviewer.get("stronger_model_requires_named_approval") is not True:
        raise PolicyError("a stronger model always requires Pedro's named approval")
    return policy


def validate_verdict_schema(schema):
    """The schema is data we ship; confirm the parts the validator relies on."""
    if schema.get("type") != "object":
        raise PolicyError("the verdict schema must describe an object")
    if schema.get("additionalProperties") is not False:
        raise PolicyError("the verdict schema must set additionalProperties false")
    if sorted(schema.get("required", [])) not in (
            sorted(VERDICT_FIELDS), sorted(tuple(VERDICT_FIELDS) + ("audit",))):
        raise PolicyError("the verdict schema must require exactly the verdict "
                          "fields, plus the audit block when it is defined")
    props = schema.get("properties")
    # `audit` is the one optional property: required stays exactly the verdict
    # fields, so a verdict without an audit block is still conforming, while a
    # typed audit verdict is no longer non-conforming.
    if not isinstance(props, dict)             or set(props) not in (set(VERDICT_FIELDS),
                                  set(VERDICT_FIELDS) | {"audit"}):
        raise PolicyError("the verdict schema must define exactly the verdict "
                          "fields, plus at most the optional audit block")
    audit = props.get("audit")
    if audit is not None:
        if audit.get("additionalProperties") is not False:
            raise PolicyError("the audit block must set additionalProperties false")
        if sorted(audit.get("required", [])) != sorted(AUDIT_BLOCK_FIELDS):
            raise PolicyError("the audit block must require exactly its fields")
        entry = audit.get("properties", {}).get("findings", {}).get("items", {})
        if entry.get("additionalProperties") is not False:
            raise PolicyError("an audit finding must set additionalProperties false")
        if sorted(entry.get("required", [])) != sorted(AUDIT_FINDING_FIELDS):
            raise PolicyError("an audit finding must require exactly its fields")
        for key in sorted(set(audit.get("properties", {}))
                          | set(entry.get("properties", {}))):
            if _COMMAND_KEY_RE.match(key):
                raise PolicyError("the audit block defines an action-bearing field")
    if props["verdict"].get("enum") != list(ENUMS_FIXED["response_verdict"]):
        raise PolicyError("the verdict schema enum is fixed")
    if props["non_authorization"].get("const") != NON_AUTHORIZATION_SENTENCE:
        raise PolicyError("the verdict schema non_authorization sentence is fixed")
    item = props["findings"].get("items", {})
    if item.get("additionalProperties") is not False:
        raise PolicyError("a finding must set additionalProperties false")
    if sorted(item.get("required", [])) != sorted(FINDING_FIELDS):
        raise PolicyError("a finding must require exactly the finding fields")
    for key in sorted(set(props) | set(item.get("properties", {}))):
        if _COMMAND_KEY_RE.match(key):
            raise PolicyError("the verdict schema defines an action-bearing field")
    return schema


# --------------------------------------------------------------------------
# Shared field validation
# --------------------------------------------------------------------------

def _limits(policy):
    return policy["limits"]


def _walk(node, limits, depth=0, key=None):
    """Depth, size, and content scan applied to every envelope, uniformly."""
    if depth > limits["max_depth"]:
        raise ef.SafetyLimitError("the document nests deeper than the maximum depth")
    if isinstance(node, dict):
        seen = set()
        for k, v in node.items():
            if not isinstance(k, str):
                _bad("every field name must be a string")
            folded = k.lower()
            if folded in seen:
                _bad("a case-conflicting field name was supplied")
            seen.add(folded)
            if _COMMAND_KEY_RE.match(k):
                _bad("a command-, action-, or authorization-bearing field is not "
                     "permitted anywhere in an envelope")
            _walk(k, limits, depth + 1)
            _walk(v, limits, depth + 1, key=k)
    elif isinstance(node, list):
        if len(node) > limits["max_paths"]:
            raise ef.SafetyLimitError("a list exceeds the maximum element count")
        for v in node:
            _walk(v, limits, depth + 1, key=key)
    elif isinstance(node, str):
        if len(node) > limits["max_string_chars"]:
            raise ef.SafetyLimitError("a string exceeds the maximum length")
        if _CREDENTIAL_RE.search(node):
            # The matched value is never echoed.
            _bad("a credential-shaped value was found and the envelope was rejected")
        if _MACHINE_PATH_RE.search(node):
            _bad("a machine-specific path or username is not permitted in an "
                 "envelope; use the logical repository and worktree identity")
        if _EXECUTABLE_RE.search(node):
            _bad("an executable construct or command was found in a field that "
                 "may only carry inert data")
        # The fixed non-authorization sentence names the very acts it forbids
        # ("... or enable execution"). Remove it before scanning for intent, or
        # every correct verdict would be rejected by its own disclaimer. The
        # sentence is separately checked for exact equality, so removing it here
        # cannot let an altered version through.
        if _PROHIBITED_INTENT_RE.search(node.replace(NON_AUTHORIZATION_SENTENCE, " ")):
            _bad("the envelope expresses prohibited intent (trading, broker "
                 "activity, risk or guard override, or a claim that a verdict "
                 "grants authorization); this is a failure, not a warning")
    elif isinstance(node, float):
        if node != node or node in (float("inf"), float("-inf")):
            _bad("a non-standard numeric value is not permitted")
    elif node is None or isinstance(node, (int, bool)):
        return
    else:
        _bad("an unsupported value type was supplied")


def _require(doc, fields, what):
    if not isinstance(doc, dict):
        _bad("the %s must be a JSON object" % what)
    missing = [f for f in fields if f not in doc]
    if missing:
        _bad("the %s is missing required field(s): %s"
             % (what, ", ".join(sorted(missing))))
    unknown = set(doc) - set(fields)
    if unknown:
        _bad("the %s has unrecognized field(s): %s"
             % (what, ", ".join(sorted(unknown))))


def _str_field(doc, name, pattern, what):
    value = doc[name]
    if not isinstance(value, str) or not pattern.match(value):
        _bad("%s %s is malformed" % (what, name))
    return value


def _rel_path(value, what, limits):
    if not isinstance(value, str) or not value.strip():
        _bad("%s must be a non-empty string" % what)
    norm = value.replace("\\", "/")
    if norm.startswith("/") or re.match(r"^[A-Za-z]:", norm):
        _bad("%s must be repository-relative, not absolute" % what)
    if ".." in norm.split("/"):
        _bad("%s must not contain a parent-directory traversal" % what)
    if len(norm) > limits["max_string_chars"]:
        raise ef.SafetyLimitError("%s exceeds the maximum length" % what)
    if _MACHINE_PATH_RE.search(norm):
        _bad("%s must not contain a machine-specific path" % what)
    return posixpath.normpath(norm).strip("/")


def _path_list(values, what, limits):
    if not isinstance(values, list):
        _bad("%s must be a list" % what)
    if len(values) > limits["max_paths"]:
        raise ef.SafetyLimitError("%s exceeds the maximum path count" % what)
    out, seen = [], {}
    for v in values:
        norm = _rel_path(v, "%s entry" % what, limits)
        folded = norm.lower()
        if folded in seen:
            _bad("%s contains a duplicate or case-conflicting path" % what)
        seen[folded] = norm
        out.append(norm)
    return out


# --------------------------------------------------------------------------
# Evidence
# --------------------------------------------------------------------------

def validate_evidence(evidence, policy):
    limits = _limits(policy)
    if not isinstance(evidence, dict):
        _bad("evidence must be a JSON object")
    unknown = set(evidence) - set(EVIDENCE_FIELDS)
    if unknown:
        _bad("evidence has unrecognized field(s): %s; only the fixed evidence "
             "fields are supported" % ", ".join(sorted(unknown)))
    if not evidence:
        _bad("evidence must not be empty")

    if "changed_paths" in evidence:
        _path_list(evidence["changed_paths"], "changed_paths", limits)
    if "diff_numstat" in evidence:
        rows = evidence["diff_numstat"]
        if not isinstance(rows, list):
            _bad("diff_numstat must be a list")
        if len(rows) > limits["max_paths"]:
            raise ef.SafetyLimitError("diff_numstat exceeds the maximum row count")
        for row in rows:
            _require(row, ("path", "insertions", "deletions"), "diff_numstat row")
            _rel_path(row["path"], "diff_numstat path", limits)
            for k in ("insertions", "deletions"):
                if not isinstance(row[k], int) or isinstance(row[k], bool) \
                        or row[k] < 0:
                    _bad("diff_numstat %s must be a non-negative integer" % k)
    if "test_results" in evidence:
        rows = evidence["test_results"]
        if not isinstance(rows, list) or not rows:
            _bad("test_results must be a non-empty list")
        if len(rows) > limits["max_paths"]:
            raise ef.SafetyLimitError("test_results exceeds the maximum row count")
        for row in rows:
            _require(row, ("suite", "passed", "failed", "skipped"),
                     "test_results row")
            if not isinstance(row["suite"], str) or not row["suite"].strip():
                _bad("a test_results suite must be a non-empty string")
            for k in ("passed", "failed", "skipped"):
                if not isinstance(row[k], int) or isinstance(row[k], bool) \
                        or row[k] < 0:
                    _bad("test_results %s must be a non-negative integer" % k)
    if "collection_digest" in evidence:
        _require(evidence["collection_digest"], ("node_count", "sha256"),
                 "collection_digest")
        cd = evidence["collection_digest"]
        if not isinstance(cd["node_count"], int) or isinstance(cd["node_count"], bool) \
                or cd["node_count"] < 0:
            _bad("collection_digest node_count must be a non-negative integer")
        if not _SHA256_RE.match(str(cd["sha256"])):
            _bad("collection_digest sha256 must be a 64-character lowercase digest")
    if "policy_hashes" in evidence:
        hashes = evidence["policy_hashes"]
        if not isinstance(hashes, dict) or not hashes:
            _bad("policy_hashes must be a non-empty mapping")
        if len(hashes) > limits["max_paths"]:
            raise ef.SafetyLimitError("policy_hashes exceeds the maximum count")
        for name, value in hashes.items():
            _rel_path(name, "policy_hashes key", limits)
            if not isinstance(value, str) or not _SHA256_RE.match(value):
                _bad("every policy hash must be a 64-character lowercase digest")
    if "repository_state" in evidence:
        _require(evidence["repository_state"], ("clean", "untracked_count"),
                 "repository_state")
        rs = evidence["repository_state"]
        if not isinstance(rs["clean"], bool):
            _bad("repository_state clean must be a boolean")
        if not isinstance(rs["untracked_count"], int) \
                or isinstance(rs["untracked_count"], bool) \
                or rs["untracked_count"] < 0:
            _bad("repository_state untracked_count must be a non-negative integer")
    if "permission_state" in evidence:
        _require(evidence["permission_state"], ("allow", "ask", "deny"),
                 "permission_state")
        for k in ("allow", "ask", "deny"):
            v = evidence["permission_state"][k]
            if not isinstance(v, int) or isinstance(v, bool) or v < 0:
                _bad("permission_state %s must be a non-negative integer" % k)
    if "notes" in evidence:
        notes = evidence["notes"]
        if not isinstance(notes, list):
            _bad("notes must be a list")
        if len(notes) > limits["max_notes"]:
            raise ef.SafetyLimitError("notes exceeds the maximum count")
        for n in notes:
            if not isinstance(n, str) or not n.strip():
                _bad("every note must be a non-empty string")
    return evidence


# --------------------------------------------------------------------------
# Request envelope
# --------------------------------------------------------------------------

def is_cancellation(msg):
    """True for a terminal cancellation message, whatever else it carries."""
    return isinstance(msg, dict) and msg.get("message_type") == CANCELLATION_TYPE


def is_rejection(msg):
    """True for a terminal rejection: a response was produced and refused."""
    return isinstance(msg, dict) and msg.get("message_type") == REJECTION_TYPE


def is_terminal(msg):
    """Either terminal kind. Both retire exactly one request, append-only."""
    return is_cancellation(msg) or is_rejection(msg)


def is_review_request(msg):
    """True for an actual Claude review request, never for a terminal."""
    return (isinstance(msg, dict) and msg.get("sender") == "claude"
            and not is_terminal(msg))


def cancelled_request_ids(mailbox_doc):
    """Every request id retired by a terminal already in the chain.

    Named for the first terminal kind it covered; it now covers both, because
    anything downstream only needs to know a request is finished, not how.
    """
    return {m.get("cancelled_request_id") for m in mailbox_doc["messages"]
            if is_terminal(m)}


def validate_cancellation(doc, policy):
    """Field-by-field check of a terminal cancellation envelope."""
    limits = _limits(policy)
    _require(doc, CANCELLATION_FIELDS, "cancellation envelope")
    _walk(doc, limits)

    if doc["schema_version"] != SCHEMA_VERSION:
        _bad("unsupported cancellation schema_version")
    _str_field(doc, "message_id", _UUID_RE, "cancellation")
    _str_field(doc, "cancelled_request_id", _UUID_RE, "cancellation")
    _str_field(doc, "previous_message_sha256", _SHA256_RE, "cancellation")
    _str_field(doc, "created_at", _TIMESTAMP_RE, "cancellation")
    _str_field(doc, "phase", _PHASE_RE, "cancellation")
    _str_field(doc, "head", _OID_RE, "cancellation")
    for name in ("sequence", "cancelled_sequence"):
        if not isinstance(doc[name], int) or isinstance(doc[name], bool)                 or doc[name] < 1:
            _bad("cancellation %s must be a positive integer" % name)
    if not isinstance(doc["registry_revision"], int)             or isinstance(doc["registry_revision"], bool)             or doc["registry_revision"] < 0:
        _bad("cancellation registry_revision must be a non-negative integer")
    if doc["sender"] != "claude":
        _bad("a cancellation envelope must be sent by claude")
    if doc["recipient"] != "codex":
        _bad("a cancellation envelope must be addressed to codex")
    if doc["message_type"] != CANCELLATION_TYPE:
        _bad("message_type must be %r" % CANCELLATION_TYPE)
    for name in ("reason", "cancelled_by"):
        if not isinstance(doc[name], str) or not doc[name].strip():
            _bad("cancellation %s must be a non-empty string" % name)
    if len(canonical_bytes(doc)) > limits["max_envelope_bytes"]:
        raise ef.SafetyLimitError("the cancellation envelope exceeds the maximum size")


def validate_rejection(doc, policy):
    """Field-by-field check of a terminal response-rejection envelope."""
    limits = _limits(policy)
    _require(doc, REJECTION_FIELDS, "rejection envelope")
    _walk(doc, limits)

    if doc["schema_version"] != SCHEMA_VERSION:
        _bad("unsupported rejection schema_version")
    _str_field(doc, "message_id", _UUID_RE, "rejection")
    _str_field(doc, "cancelled_request_id", _UUID_RE, "rejection")
    _str_field(doc, "previous_message_sha256", _SHA256_RE, "rejection")
    _str_field(doc, "created_at", _TIMESTAMP_RE, "rejection")
    _str_field(doc, "phase", _PHASE_RE, "rejection")
    _str_field(doc, "head", _OID_RE, "rejection")
    for name in ("sequence", "cancelled_sequence"):
        if not isinstance(doc[name], int) or isinstance(doc[name], bool) \
                or doc[name] < 1:
            _bad("rejection %s must be a positive integer" % name)
    if not isinstance(doc["registry_revision"], int) \
            or isinstance(doc["registry_revision"], bool) \
            or doc["registry_revision"] < 0:
        _bad("rejection registry_revision must be a non-negative integer")
    if doc["sender"] != "claude":
        _bad("a rejection envelope must be sent by claude")
    if doc["recipient"] != "codex":
        _bad("a rejection envelope must be addressed to codex")
    if doc["message_type"] != REJECTION_TYPE:
        _bad("message_type must be %r" % REJECTION_TYPE)
    # The attempt is always spent: the child ran to produce the refused answer.
    # Recording anything else would misstate what happened.
    if doc["attempt_consumed"] is not True:
        _bad("a rejection always records attempt_consumed true; the child ran")
    for name in ("rejection_reason", "recorded_by"):
        if not isinstance(doc[name], str) or not doc[name].strip():
            _bad("rejection %s must be a non-empty string" % name)
    if len(canonical_bytes(doc)) > limits["max_envelope_bytes"]:
        raise ef.SafetyLimitError("the rejection envelope exceeds the maximum size")
    return doc
    return doc


def validate_request(doc, policy):
    limits = _limits(policy)
    _require(doc, REQUEST_FIELDS, "request envelope")
    _walk(doc, limits)

    if doc["schema_version"] != SCHEMA_VERSION:
        _bad("unsupported request schema_version")
    _str_field(doc, "message_id", _UUID_RE, "request")
    if not isinstance(doc["sequence"], int) or isinstance(doc["sequence"], bool) \
            or doc["sequence"] < 1:
        _bad("request sequence must be a positive integer")
    _str_field(doc, "previous_message_sha256", _SHA256_RE, "request")
    _str_field(doc, "created_at", _TIMESTAMP_RE, "request")
    if doc["sender"] != "claude":
        _bad("a request envelope must be sent by claude")
    if doc["recipient"] != "codex":
        _bad("a request envelope must be addressed to codex")
    _str_field(doc, "phase", _PHASE_RE, "request")
    _str_field(doc, "repository_identity", _IDENTITY_RE, "request")
    _str_field(doc, "worktree_identity", _IDENTITY_RE, "request")
    _str_field(doc, "branch", _BRANCH_RE, "request")
    _str_field(doc, "head", _OID_RE, "request")
    _str_field(doc, "registry_expected_commit", _OID_RE, "request")
    if not isinstance(doc["registry_revision"], int) \
            or isinstance(doc["registry_revision"], bool) \
            or doc["registry_revision"] < 0:
        _bad("request registry_revision must be a non-negative integer")
    if doc["change_class"] not in ENUMS_FIXED["change_class"]:
        _bad("request change_class is not one of the fixed classes")
    if doc["state"] != "pending":
        _bad("a request envelope must be in the pending state")
    _path_list(doc["scope"], "scope", limits)

    validate_evidence(doc["evidence"], policy)
    _str_field(doc, "evidence_digest", _SHA256_RE, "request")
    recomputed = evidence_digest_of(doc["evidence"])
    if recomputed != doc["evidence_digest"]:
        _bad("evidence_digest does not match the evidence; the digest is always "
             "recomputed and a supplied value is never trusted")

    size = len(canonical_bytes(doc))
    if size > limits["max_envelope_bytes"]:
        raise ef.SafetyLimitError("the request envelope exceeds the maximum size")
    return doc


def validate_audit(block, policy):
    """Typed, inert code-audit block. Names of things are data; running is not.

    Every value here is still scanned for credentials and machine paths. What
    differs from the generic rule is only the executable test: a code audit must
    be able to say `subprocess`, `intelligence/gateway.py`, or `ProviderError`
    without that counting as smuggling, while shells, chaining, scripts, patches,
    encoded payloads, tool invocations, and "run this" instructions stay refused.
    """
    limits = _limits(policy)
    _require(block, AUDIT_BLOCK_FIELDS, "audit block")
    if block["schema_version"] != AUDIT_SCHEMA_VERSION:
        _bad("unsupported audit schema_version")

    def _inert(value, where):
        if not isinstance(value, str) or not value.strip():
            _bad("audit %s must be a non-empty string" % where)
        if len(value) > 4096:
            raise ef.SafetyLimitError("audit %s exceeds the maximum length" % where)
        if _CREDENTIAL_RE.search(value):
            _bad("a credential-shaped value was found in audit %s" % where)
        if _MACHINE_PATH_RE.search(value):
            _bad("a machine-specific path or username is not permitted in "
                 "audit %s" % where)
        reason = audit_executable_reason(value)
        if reason:
            _bad("audit %s carries %s; an audit describes code, it never ships "
                 "something to run" % (where, reason))

    _inert(block["architecture_summary"], "architecture_summary")
    findings = block["findings"]
    if not isinstance(findings, list):
        _bad("audit findings must be a list")
    if len(findings) > limits["max_findings"]:
        raise ef.SafetyLimitError("audit findings exceeds the maximum count")
    seen = set()
    for f in findings:
        _require(f, AUDIT_FINDING_FIELDS, "audit finding")
        _str_field(f, "finding_id", _PHASE_RE, "audit finding")
        if f["finding_id"] in seen:
            _bad("a duplicate audit finding_id was supplied")
        seen.add(f["finding_id"])
        if f["severity"] not in ENUMS_FIXED["finding_severity"]:
            _bad("audit finding severity is not one of the fixed severities")
        _str_field(f, "category", _CATEGORY_RE, "audit finding")
        _rel_path(f["repository_path"], "audit repository_path", limits)
        if not _SYMBOL_RE.match(str(f["symbol"])):
            _bad("audit symbol must be a plain identifier or dotted name")
        for k in ("line_start", "line_end"):
            if not isinstance(f[k], int) or isinstance(f[k], bool) or f[k] < 0:
                _bad("audit %s must be a non-negative integer" % k)
        if f["line_end"] < f["line_start"]:
            _bad("audit line_end must not precede line_start")
        for k in ("observed_behavior", "technical_risk", "evidence_description",
                  "recommended_correction", "test_gap", "acceptance_criteria"):
            _inert(f[k], k)
    return block


def validate_verdict(doc, policy, schema):
    """Check a Codex final response field by field against the shipped schema."""
    limits = _limits(policy)
    # Strict structured output cannot omit a property, so "no audit" arrives as
    # an explicit null rather than a missing key. Both mean the same thing here.
    audit = doc.get("audit")
    fields = VERDICT_FIELDS + (("audit",) if "audit" in doc else ())
    _require(doc, fields, "verdict document")
    # The audit block carries typed inert code references and is validated by its
    # own stricter-shaped rules; everything else stays under the generic scan.
    _walk({k: v for k, v in doc.items() if k != "audit"}, limits)
    if audit is not None:
        validate_audit(audit, policy)

    if doc["schema_version"] != SCHEMA_VERSION:
        _bad("unsupported verdict schema_version")
    _str_field(doc, "request_message_id", _UUID_RE, "verdict")
    _str_field(doc, "phase", _PHASE_RE, "verdict")
    _str_field(doc, "head", _OID_RE, "verdict")
    if doc["verdict"] not in ENUMS_FIXED["response_verdict"]:
        _bad("verdict must be one of PASS, REVISE, STOP, or ESCALATE")
    if not isinstance(doc["summary"], str) or not doc["summary"].strip():
        _bad("verdict summary must be a non-empty string")
    if len(doc["summary"]) > 4096:
        raise ef.SafetyLimitError("verdict summary exceeds the maximum length")

    if doc["non_authorization"] != NON_AUTHORIZATION_SENTENCE:
        _bad("non_authorization must be exactly the fixed sentence; a verdict "
             "that alters or omits it is rejected, never accepted with a warning")

    findings = doc["findings"]
    if not isinstance(findings, list):
        _bad("findings must be a list")
    if len(findings) > limits["max_findings"]:
        raise ef.SafetyLimitError("findings exceeds the maximum count")
    seen = set()
    for f in findings:
        _require(f, FINDING_FIELDS, "finding")
        _str_field(f, "finding_id", _PHASE_RE, "finding")
        if f["finding_id"] in seen:
            _bad("a duplicate finding_id was supplied")
        seen.add(f["finding_id"])
        if f["severity"] not in ENUMS_FIXED["finding_severity"]:
            _bad("finding severity is not one of the fixed severities")
        _str_field(f, "category", _CATEGORY_RE, "finding")
        for k in ("message", "evidence"):
            if not isinstance(f[k], str) or not f[k].strip():
                _bad("finding %s must be a non-empty string" % k)
            if len(f[k]) > 4096:
                raise ef.SafetyLimitError("finding %s exceeds the maximum length" % k)

    size = len(canonical_bytes(doc))
    if size > limits["max_envelope_bytes"]:
        raise ef.SafetyLimitError("the verdict document exceeds the maximum size")
    return doc


# --------------------------------------------------------------------------
# Mailbox
# --------------------------------------------------------------------------

EMPTY_MAILBOX = {"schema_version": SCHEMA_VERSION, "revision": 0, "messages": []}


def mailbox_paths(root):
    root = os.path.abspath(root)
    return (root,
            os.path.join(root, MAILBOX_FILENAME),
            os.path.join(root, MAILBOX_FILENAME + LOCK_SUFFIX),
            os.path.join(root, ARCHIVE_DIRNAME))


def read_mailbox(path):
    if not os.path.isfile(path):
        return dict(EMPTY_MAILBOX, messages=[])
    try:
        raw = open(path, "rb").read()
    except OSError:
        raise sg.StoppedError("the mailbox could not be read")
    if len(raw) > MAX_ENVELOPE_BYTES * 4:
        raise ef.SafetyLimitError("the mailbox exceeds the maximum size")
    try:
        doc = json.loads(raw.decode("utf-8"), parse_constant=_reject_constant)
    except ef.ValidationError:
        raise
    except Exception:
        raise sg.StoppedError("the mailbox is not valid JSON")
    if not isinstance(doc, dict) or doc.get("schema_version") != SCHEMA_VERSION:
        raise sg.StoppedError("the mailbox has an unsupported schema")
    if not isinstance(doc.get("messages"), list):
        raise sg.StoppedError("the mailbox is malformed")
    if not isinstance(doc.get("revision"), int) or isinstance(doc["revision"], bool):
        raise sg.StoppedError("the mailbox revision is malformed")
    if len(doc["messages"]) > MAX_MESSAGES:
        raise ef.SafetyLimitError("the mailbox holds more messages than the maximum")
    return doc


class _Lock:
    """A sibling lock. Never steals, never removes a lock it did not create."""

    def __init__(self, path, timeout):
        self.path = path
        self.timeout = timeout
        self.fd = None

    def __enter__(self):
        deadline = time.monotonic() + self.timeout
        while True:
            try:
                self.fd = os.open(self.path,
                                  os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                return self
            except FileExistsError:
                if time.monotonic() >= deadline:
                    raise sg.StoppedError(
                        "another process holds the mailbox lock; stopping rather "
                        "than stealing it")
                time.sleep(LOCK_POLL_SECONDS)
            except OSError:
                raise sg.StoppedError("the mailbox lock could not be created")

    def __exit__(self, *exc):
        if self.fd is not None:
            try:
                os.close(self.fd)
            except OSError:
                pass
            try:
                os.unlink(self.path)
            except OSError:
                pass
            self.fd = None
        return False


def _atomic_write(path, payload):
    """Same-directory temp file -> flush -> fsync -> os.replace."""
    directory = os.path.dirname(path)
    tmp = os.path.join(directory, ".%s.%d.tmp"
                       % (os.path.basename(path), os.getpid()))
    fd = os.open(tmp, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(payload)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
        tmp = None
    finally:
        if tmp is not None and os.path.exists(tmp):
            try:
                os.unlink(tmp)          # only ever this process's own temp file
            except OSError:
                pass


def _archive(archive_dir, revision, payload):
    """Append-only by this tool: never overwrite, rename, or delete an entry."""
    name = os.path.join(archive_dir, "relay-%06d.json" % revision)
    if os.path.exists(name):
        raise sg.StoppedError(
            "an archive entry for this revision already exists; stopping rather "
            "than overwriting history")
    fd = os.open(name, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "wb") as fh:
        fh.write(payload)
        fh.flush()
        os.fsync(fh.fileno())


def chain_hash(messages):
    """The hash the next message must carry."""
    if not messages:
        return ZERO_HASH
    return sha256_of(messages[-1])


def verify_chain(mailbox):
    """Sequence and previous-hash integrity. Detects corruption, not forgery."""
    problems = []
    previous = ZERO_HASH
    expected_seq = 1
    seen_ids = set()
    seen_reviews = set()
    seen_cancelled = set()
    # Only ids of actual review requests. A cancellation must name one of THESE,
    # never a response or another cancellation, so `seen_ids` is deliberately not
    # reused here: it holds every message id and would accept the wrong target.
    seen_request_ids = set()
    for n, msg in enumerate(mailbox["messages"], 1):
        if not isinstance(msg, dict):
            problems.append((n, "message %d is not an object" % n))
            break
        if msg.get("sequence") != expected_seq:
            problems.append((n, "message %d has sequence %r, expected %d"
                             % (n, msg.get("sequence"), expected_seq)))
        if msg.get("previous_message_sha256") != previous:
            problems.append((n, "message %d breaks the hash chain" % n))
        mid = msg.get("message_id")
        if mid in seen_ids:
            problems.append((n, "message %d repeats a message_id" % n))
        seen_ids.add(mid)
        if is_terminal(msg):
            target = msg.get("cancelled_request_id")
            if target not in seen_request_ids:
                problems.append((n, "message %d terminates something that is not "
                                    "an earlier review request" % n))
            if target in seen_cancelled:
                problems.append((n, "message %d terminates an already-terminated "
                                    "request" % n))
            seen_cancelled.add(target)
        elif msg.get("sender") == "claude":
            seen_request_ids.add(mid)
            key = (msg.get("phase"), msg.get("head"))
            if key in seen_reviews:
                problems.append((n, "message %d replays a (phase, head) review" % n))
            seen_reviews.add(key)
        previous = sha256_of(msg)
        expected_seq += 1
    return problems


# --------------------------------------------------------------------------
# Repository and registry observation (read-only, through existing observers)
# --------------------------------------------------------------------------

def observe_repository(repo_path):
    repo, identity = sg.resolve_repo(repo_path)
    head = a7._git_ok(repo, ["rev-parse", "HEAD"]).strip()
    branch = a7._git_ok(repo, ["rev-parse", "--abbrev-ref", "HEAD"]).strip()
    porcelain = a7._git_ok(repo, ["status", "--porcelain"])
    entries = [ln for ln in porcelain.splitlines() if ln.strip()]
    return {"repo": repo, "identity": identity, "head": head, "branch": branch,
            "dirty_entries": len(entries)}


def observe_registry(registry_path, session_id):
    if os.path.exists(registry_path + ".lock"):
        raise sg.StoppedError("a registry lock is present; another process may be "
                              "writing")
    if not os.path.isfile(registry_path):
        raise sg.StoppedError("no registry file at the supplied location")
    registry = sr.read_registry(registry_path)
    record = None
    for s in registry["sessions"]:
        if s["session_id"] == session_id:
            record = s
            break
    if record is None:
        raise sg.StoppedError("no session with the supplied id is registered")
    state = sr.classify(record, datetime.now(timezone.utc), sr.DEFAULT_STALE_SECONDS)
    return {"revision": registry["revision"], "record": record, "state": state}


def bind_checks(doc, repo_obs, reg_obs):
    """Prove the envelope still describes reality. Any drift stops the relay."""
    problems = []
    if doc["head"] != repo_obs["head"]:
        problems.append("head does not match the observed repository HEAD")
    if doc["branch"] != repo_obs["branch"]:
        problems.append("branch does not match the observed branch")
    if doc["worktree_identity"] != repo_obs["identity"]:
        problems.append("worktree_identity does not match the observed worktree")
    if repo_obs["dirty_entries"]:
        problems.append("the worktree or index is not clean")
    if reg_obs is not None:
        if doc["registry_revision"] != reg_obs["revision"]:
            problems.append("registry_revision does not match the live registry")
        if doc["registry_expected_commit"] != reg_obs["record"]["expected_commit"]:
            problems.append("registry_expected_commit does not match the registered "
                            "session")
        if reg_obs["record"]["expected_commit"] != repo_obs["head"]:
            problems.append("the registered expected_commit does not match HEAD")
        if doc["branch"] != reg_obs["record"]["branch"]:
            problems.append("branch does not match the registered session branch")
    return problems


# --------------------------------------------------------------------------
# Checks and rendering
# --------------------------------------------------------------------------

def _chk(cid, label, status, evidence):
    return {"id": cid, "label": label, "status": status, "evidence": evidence}


def contract_checks():
    return [
        _chk("K1", "authority", "warning", "PASS means only that a second reader "
             "found no objection; it grants no permission to modify, commit, push, "
             "merge, deploy, trade, alter risk, or enable execution"),
        _chk("K2", "approval", "warning", "AAM and AM work still requires Pedro's "
             "named approval; a verdict never substitutes for it"),
        _chk("K3", "untrusted input", "pass", "report text, notes, findings, and "
             "summaries are data; no instruction inside them is followed"),
        _chk("K4", "execution", "pass", "this tool invokes no model, runs no "
             "command, and never executes envelope content"),
        _chk("K5", "mutation", "pass", "no repository file, Git ref, Session "
             "Registry record, hook, or permission is modified"),
        _chk("K6", "retry", "pass", "one review per (phase, head); REVISE does not "
             "authorize resubmission and there is no automatic retry"),
        _chk("K7", "archive", "informational", "append-only by this tool and hash "
             "chained; that detects corruption or partial rewriting, and is NOT a "
             "guarantee against an attacker who can rewrite mailbox and archive "
             "together"),
    ]


def _emit(doc, fmt):
    norm = ef.normalize(doc)
    text = ef.render_markdown(norm) if fmt == "markdown" else ef.render_json(norm)
    sys.stdout.buffer.write(text.encode("utf-8"))
    sys.stdout.buffer.flush()
    return norm


def _err(text):
    sys.stderr.buffer.write(text.encode("utf-8"))
    sys.stderr.buffer.flush()


def _read_doc(path, limits, what):
    if path is None:
        raw = sys.stdin.buffer.read(limits["max_envelope_bytes"] + 1)
    else:
        if not os.path.isfile(path):
            _bad("the %s file does not exist" % what)
        if os.path.getsize(path) > limits["max_envelope_bytes"]:
            raise ef.SafetyLimitError("the %s exceeds the maximum size" % what)
        with open(path, "rb") as fh:
            raw = fh.read(limits["max_envelope_bytes"] + 1)
    if len(raw) > limits["max_envelope_bytes"]:
        raise ef.SafetyLimitError("the %s exceeds the maximum size" % what)
    if not raw.strip():
        _bad("no %s was supplied" % what)
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        _bad("the %s is not valid UTF-8" % what)
    try:
        return json.loads(text, parse_constant=_reject_constant)
    except ef.ValidationError:
        raise
    except Exception:
        _bad("the %s is not valid JSON" % what)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def build_parser():
    parser = argparse.ArgumentParser(
        prog="codex_relay",
        description="Carry one validated report and one structured verdict between "
                    "Claude and Codex. It invokes nothing, approves nothing, and "
                    "modifies no repository or registry state.")
    parser.add_argument("operation", choices=OPERATIONS)
    parser.add_argument("--format", choices=("markdown", "json"), required=True)
    parser.add_argument("--mailbox", default=None,
                        help="mailbox directory; required for stateful operations")
    parser.add_argument("--policy", default=None)
    parser.add_argument("--verdict-schema", default=None)
    parser.add_argument("--input", default=None,
                        help="request envelope JSON; stdin if omitted")
    parser.add_argument("--response", default=None,
                        help="private temporary verdict file produced elsewhere")
    parser.add_argument("--repo", default=None, help="path to a git worktree")
    parser.add_argument("--registry", default=None,
                        help="machine-local session registry, read-only")
    parser.add_argument("--session-id", default=None)
    parser.add_argument("--request-id", default=None,
                        help="cancel-request: the pending request to retire")
    parser.add_argument("--reason", default=None,
                        help="cancel-request: why the request became unusable")
    parser.add_argument("--rejection-reason", default=None,
                        help="record-rejection: sanitized reason the response "
                             "was refused")
    parser.add_argument("--recorded-by", default=None,
                        help="record-rejection: the actor recording the terminal")
    parser.add_argument("--cancelled-by", default=None,
                        help="cancel-request: the person authorizing the retirement")
    parser.add_argument("--expect-mailbox-revision", type=int, default=None,
                        help="cancel-request: refuse unless the mailbox is still "
                             "at this revision (compare-and-swap guard)")
    return parser


class _Stop(Exception):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _require_mailbox(args):
    if not args.mailbox:
        _bad("%s requires --mailbox" % args.operation)
    root, mailbox, lock, archive = mailbox_paths(args.mailbox)
    if not os.path.isdir(root):
        raise sg.StoppedError("the mailbox directory does not exist; it is created "
                              "by a separate approved step, never by this tool")
    if os.path.islink(root) or os.path.islink(mailbox):
        raise sg.StoppedError("the mailbox path is a link; stopping")
    return root, mailbox, lock, archive


def _record(args, policy, message, checks):
    """Lock, re-read, archive, atomically replace. Failure leaves prior bytes."""
    root, mailbox_path, lock_path, archive_dir = _require_mailbox(args)
    limits = _limits(policy)
    before = read_mailbox(mailbox_path)
    with _Lock(lock_path, limits["lock_timeout_seconds"]):
        # Re-read under the lock: another writer may have moved the mailbox on.
        current = read_mailbox(mailbox_path)
        if current["revision"] != before["revision"]:
            raise sg.StoppedError("the mailbox changed while the lock was being "
                                  "acquired; stopping rather than overwriting")
        problems = verify_chain(current)
        if problems:
            raise sg.StoppedError("the mailbox chain is broken: %s"
                                  % problems[0][1])
        if message["sequence"] != len(current["messages"]) + 1:
            raise sg.StoppedError("the message sequence does not continue the "
                                  "mailbox")
        if message["previous_message_sha256"] != chain_hash(current["messages"]):
            raise sg.StoppedError("the message does not chain to the mailbox tip")
        if len(current["messages"]) + 1 > limits["max_messages"]:
            raise ef.SafetyLimitError("the mailbox is full")

        updated = {"schema_version": SCHEMA_VERSION,
                   "revision": current["revision"] + 1,
                   "messages": list(current["messages"]) + [message]}
        payload = canonical_bytes(updated) + b"\n"
        if len(payload) > MAX_ENVELOPE_BYTES * 4:
            raise ef.SafetyLimitError("the updated mailbox exceeds the maximum size")
        if not os.path.isdir(archive_dir):
            os.mkdir(archive_dir, 0o700)
        _archive(archive_dir, updated["revision"], payload)
        _atomic_write(mailbox_path, payload)

    checks.append(_chk("M1", "mailbox revision", "pass",
                       "%d -> %d" % (current["revision"], updated["revision"])))
    checks.append(_chk("M2", "messages", "pass",
                       "%d recorded" % len(updated["messages"])))
    checks.append(_chk("M3", "archive", "pass",
                       "relay-%06d.json written; no entry was overwritten, "
                       "renamed, or deleted" % updated["revision"]))
    checks.append(_chk("M4", "residue", "pass",
                       "lock released and the temporary file removed"))
    return updated


def _new_message_id():
    return str(uuid.uuid4())


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0].lower() in FORBIDDEN_VERBS:
        _err("codex_relay: %r is not an operation. This tool carries messages; it "
             "never runs, reviews, approves, applies, commits, pushes, merges, "
             "deploys, retries, or resets anything.\n" % argv[0])
        return EXIT_INVALID

    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return 0 if exc.code == 0 else EXIT_INVALID

    try:
        policy, policy_hash = load_policy(args.policy)
        validate_policy(policy)
        schema, schema_hash = load_verdict_schema(args.verdict_schema)
        validate_verdict_schema(schema)
        limits = _limits(policy)
    except ef.SafetyLimitError as exc:
        _err("codex_relay: safety limit: %s\n" % ef.sanitize_text(str(exc)))
        return EXIT_LIMIT
    except (PolicyError, ef.ValidationError) as exc:
        _err("codex_relay: invalid policy: %s\n" % ef.sanitize_text(str(exc)))
        return EXIT_INVALID

    op = args.operation
    checks, notes = [], []
    exit_code = EXIT_OK

    try:
        checks.append(_chk("P1", "policy", "pass",
                           "%s, sha256 %s" % (policy["policy_name"], policy_hash)))
        checks.append(_chk("P2", "verdict schema", "pass", "sha256 %s" % schema_hash))

        if op == "validate-policy":
            for key in sorted(CONTRACT_FIXED):
                checks.append(_chk("C.%s" % key, "contract %s" % key, "pass",
                                   json.dumps(CONTRACT_FIXED[key])))
            for key in sorted(LIMIT_MAXIMUMS):
                checks.append(_chk("L.%s" % key, "limit %s" % key, "pass",
                                   "policy %d, implementation maximum %d"
                                   % (limits[key], LIMIT_MAXIMUMS[key])))
            checks.append(_chk("O1", "operations", "pass", ", ".join(OPERATIONS)))
            checks.append(_chk("O2", "refused verbs", "pass",
                               "%d action words exit 2" % len(FORBIDDEN_VERBS)))

        elif op in ("validate-request", "submit"):
            doc = _read_doc(args.input, limits, "request envelope")
            validate_request(doc, policy)
            checks.append(_chk("Q1", "request envelope", "pass",
                               "phase %s, sequence %d, change class %s"
                               % (doc["phase"], doc["sequence"],
                                  doc["change_class"])))
            checks.append(_chk("Q2", "evidence digest", "pass",
                               "recomputed and matched: %s" % doc["evidence_digest"]))
            checks.append(_chk("Q3", "scope", "pass",
                               "%d repository-relative path(s)" % len(doc["scope"])))

            repo_obs = reg_obs = None
            if args.repo:
                repo_obs = observe_repository(args.repo)
                checks.append(_chk("R1", "repository", "pass",
                                   "branch %s, HEAD %s, %d uncommitted entr(ies)"
                                   % (repo_obs["branch"], repo_obs["head"],
                                      repo_obs["dirty_entries"])))
            if args.registry:
                if not args.session_id:
                    _bad("--registry requires --session-id")
                reg_obs = observe_registry(args.registry, args.session_id)
                checks.append(_chk("R2", "registry", "pass",
                                   "revision %d, session observed %s"
                                   % (reg_obs["revision"], reg_obs["state"])))
            if repo_obs is not None:
                problems = bind_checks(doc, repo_obs, reg_obs)
                for n, p in enumerate(problems, 1):
                    checks.append(_chk("R%02d" % (10 + n), "binding", "stopped", p))
                if problems:
                    raise sg.StoppedError("the envelope no longer describes the "
                                          "observed repository or registry state")
                checks.append(_chk("R9", "binding", "pass",
                                   "head, branch, worktree identity, registry "
                                   "revision, and expected commit all match"))
            elif op == "submit":
                _bad("submit requires --repo so the envelope can be bound to the "
                     "observed repository")

            if op == "submit":
                current = read_mailbox(_require_mailbox(args)[1])
                for msg in current["messages"]:
                    if msg.get("message_id") == doc["message_id"]:
                        _bad("this message_id is already recorded")
                    if msg.get("sender") == "claude" \
                            and msg.get("phase") == doc["phase"] \
                            and msg.get("head") == doc["head"]:
                        _bad("a review for this (phase, head) is already recorded; "
                             "the cap is one review per completed phase and a "
                             "REVISE verdict does not authorize resubmission")
                _record(args, policy, doc, checks)

        elif op in ("validate-response", "ingest-response"):
            verdict = _read_doc(args.response, limits, "verdict document")
            validate_verdict(verdict, policy, schema)
            checks.append(_chk("V1", "verdict document", "pass",
                               "%s, %d finding(s)"
                               % (verdict["verdict"], len(verdict["findings"]))))
            checks.append(_chk("V2", "non-authorization", "pass",
                               "the fixed sentence is present and exact"))
            checks.append(_chk("V3", "handling", "informational",
                               "recorded as data; no part of it is executed or "
                               "followed as an instruction"))

            request = None
            if args.mailbox:
                current = read_mailbox(_require_mailbox(args)[1])
                for msg in current["messages"]:
                    if msg.get("message_id") == verdict["request_message_id"]:
                        request = msg
                        break
                if request is None:
                    _bad("no recorded request matches request_message_id")
                if request.get("sender") != "claude":
                    _bad("request_message_id does not name a Claude request")
                if request.get("phase") != verdict["phase"]:
                    _bad("the verdict phase does not match the request")
                if request.get("head") != verdict["head"]:
                    _bad("the verdict head does not match the request")
                for msg in current["messages"]:
                    if msg.get("sender") == "codex" \
                            and msg.get("request_message_id") \
                            == verdict["request_message_id"]:
                        _bad("a response for this request is already recorded")
                checks.append(_chk("V4", "request binding", "pass",
                                   "matches request %s at phase %s"
                                   % (request["message_id"], request["phase"])))

            if op == "ingest-response":
                if request is None:
                    _bad("ingest-response requires --mailbox and a recorded request")
                repo_obs = None
                if args.repo:
                    repo_obs = observe_repository(args.repo)
                    if repo_obs["head"] != verdict["head"]:
                        raise sg.StoppedError("HEAD moved since the request; the "
                                              "verdict no longer describes this tree")
                    if repo_obs["dirty_entries"]:
                        raise sg.StoppedError("the worktree or index is not clean")
                # The relay authors the envelope; Codex's bytes never become one.
                message = {
                    "schema_version": SCHEMA_VERSION,
                    "message_id": _new_message_id(),
                    "sequence": len(current["messages"]) + 1,
                    "previous_message_sha256": chain_hash(current["messages"]),
                    "created_at": datetime.now(timezone.utc)
                                          .strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "sender": "codex",
                    "recipient": "claude",
                    "phase": request["phase"],
                    "repository_identity": request["repository_identity"],
                    "worktree_identity": request["worktree_identity"],
                    "branch": request["branch"],
                    "head": request["head"],
                    "registry_revision": request["registry_revision"],
                    "registry_expected_commit": request["registry_expected_commit"],
                    "request_message_id": request["message_id"],
                    "response": verdict,
                }
                _require(message, RESPONSE_FIELDS, "response envelope")
                _record(args, policy, message, checks)

        elif op == "cancel-request":
            for name, value in (("--request-id", args.request_id),
                                ("--reason", args.reason),
                                ("--cancelled-by", args.cancelled_by)):
                if not value:
                    _bad("cancel-request requires %s" % name)

            current = read_mailbox(_require_mailbox(args)[1])
            problems = verify_chain(current)
            if problems:
                raise sg.StoppedError("the mailbox chain is broken: %s"
                                      % problems[0][1])
            checks.append(_chk("X1", "chain", "pass",
                               "%d message(s) verified before cancelling"
                               % len(current["messages"])))

            # Compare-and-swap: a racing writer must fail closed, not overwrite.
            if args.expect_mailbox_revision is not None and                     current["revision"] != args.expect_mailbox_revision:
                raise sg.StoppedError("the mailbox is at revision %d, not the "
                                      "expected %d; refusing rather than racing"
                                      % (current["revision"],
                                         args.expect_mailbox_revision))
            checks.append(_chk("X2", "revision guard", "pass",
                               "mailbox revision %d" % current["revision"]))

            target = None
            for msg in current["messages"]:
                if msg.get("message_id") == args.request_id:
                    target = msg
                    break
            if target is None:
                _bad("no recorded message has that id")
            if not is_review_request(target):
                _bad("that id does not name a Claude review request")
            for msg in current["messages"]:
                if msg.get("sender") == "codex" and                         msg.get("request_message_id") == args.request_id:
                    _bad("a response for that request is already recorded; a "
                         "completed exchange is never cancelled")
            if args.request_id in cancelled_request_ids(current):
                _bad("that request is already cancelled")

            answered = {m.get("request_message_id") for m in current["messages"]
                        if m.get("sender") == "codex"}
            retired = cancelled_request_ids(current)
            pending = [m for m in current["messages"] if is_review_request(m)
                       and m.get("message_id") not in answered
                       and m.get("message_id") not in retired]
            if len(pending) != 1:
                raise sg.StoppedError(
                    "the mailbox holds %d pending request(s); cancellation "
                    "requires exactly one so no ambiguity is left behind"
                    % len(pending))
            if pending[0]["message_id"] != args.request_id:
                _bad("the supplied request id is not the pending request")
            checks.append(_chk("X3", "target", "pass",
                               "request %s, sequence %s, phase %s, bound to "
                               "registry revision %s"
                               % (target["message_id"], target["sequence"],
                                  target["phase"], target["registry_revision"])))

            message = {
                "schema_version": SCHEMA_VERSION,
                "message_id": _new_message_id(),
                "sequence": len(current["messages"]) + 1,
                "previous_message_sha256": chain_hash(current["messages"]),
                "created_at": datetime.now(timezone.utc)
                                      .strftime("%Y-%m-%dT%H:%M:%SZ"),
                "sender": "claude",
                "recipient": "codex",
                "message_type": CANCELLATION_TYPE,
                "cancelled_request_id": target["message_id"],
                "cancelled_sequence": target["sequence"],
                "phase": target["phase"],
                "head": target["head"],
                "registry_revision": target["registry_revision"],
                "reason": args.reason,
                "cancelled_by": args.cancelled_by,
            }
            validate_cancellation(message, policy)
            checks.append(_chk("X4", "cancellation", "warning",
                               "terminal only: no verdict, no review attempt "
                               "consumed, and nothing approved"))
            _record(args, policy, message, checks)

        elif op == "record-rejection":
            for name, value in (("--request-id", args.request_id),
                                ("--rejection-reason", args.rejection_reason),
                                ("--recorded-by", args.recorded_by)):
                if not value:
                    _bad("record-rejection requires %s" % name)

            current = read_mailbox(_require_mailbox(args)[1])
            problems = verify_chain(current)
            if problems:
                raise sg.StoppedError("the mailbox chain is broken: %s"
                                      % problems[0][1])
            checks.append(_chk("X1", "chain", "pass",
                               "%d message(s) verified before recording"
                               % len(current["messages"])))

            if args.expect_mailbox_revision is not None and \
                    current["revision"] != args.expect_mailbox_revision:
                raise sg.StoppedError("the mailbox is at revision %d, not the "
                                      "expected %d; refusing rather than racing"
                                      % (current["revision"],
                                         args.expect_mailbox_revision))
            checks.append(_chk("X2", "revision guard", "pass",
                               "mailbox revision %d" % current["revision"]))

            target = None
            for msg in current["messages"]:
                if msg.get("message_id") == args.request_id:
                    target = msg
                    break
            if target is None:
                _bad("no recorded message has that id")
            if not is_review_request(target):
                _bad("that id does not name a Claude review request")
            for msg in current["messages"]:
                if msg.get("sender") == "codex" and \
                        msg.get("request_message_id") == args.request_id:
                    _bad("a response for that request is already recorded")
            if args.request_id in cancelled_request_ids(current):
                _bad("that request is already terminated")

            answered = {m.get("request_message_id") for m in current["messages"]
                        if m.get("sender") == "codex"}
            retired = cancelled_request_ids(current)
            pending = [m for m in current["messages"] if is_review_request(m)
                       and m.get("message_id") not in answered
                       and m.get("message_id") not in retired]
            if len(pending) != 1:
                raise sg.StoppedError(
                    "the mailbox holds %d pending request(s); recording a "
                    "rejection requires exactly one so no ambiguity is left"
                    % len(pending))
            if pending[0]["message_id"] != args.request_id:
                _bad("the supplied request id is not the pending request")
            checks.append(_chk("X3", "target", "pass",
                               "request %s, sequence %s, phase %s"
                               % (target["message_id"], target["sequence"],
                                  target["phase"])))

            message = {
                "schema_version": SCHEMA_VERSION,
                "message_id": _new_message_id(),
                "sequence": len(current["messages"]) + 1,
                "previous_message_sha256": chain_hash(current["messages"]),
                "created_at": datetime.now(timezone.utc)
                                      .strftime("%Y-%m-%dT%H:%M:%SZ"),
                "sender": "claude",
                "recipient": "codex",
                "message_type": REJECTION_TYPE,
                "cancelled_request_id": target["message_id"],
                "cancelled_sequence": target["sequence"],
                "phase": target["phase"],
                "head": target["head"],
                "registry_revision": target["registry_revision"],
                "rejection_reason": args.rejection_reason,
                "attempt_consumed": True,
                "recorded_by": args.recorded_by,
            }
            validate_rejection(message, policy)
            checks.append(_chk("X4", "rejection", "warning",
                               "the child ran and answered; the answer failed "
                               "validation and was never recorded, so the one "
                               "attempt is spent and a retry needs a NEW request"))
            _record(args, policy, message, checks)

        elif op == "inspect":
            current = read_mailbox(_require_mailbox(args)[1])
            checks.append(_chk("I1", "mailbox", "pass",
                               "revision %d, %d message(s)"
                               % (current["revision"], len(current["messages"]))))
            for n, msg in enumerate(current["messages"], 1):
                if is_rejection(msg):
                    detail = ("REJECTED response for request %s, phase %s"
                              % (msg.get("cancelled_request_id"),
                                 msg.get("phase")))
                elif is_cancellation(msg):
                    detail = ("CANCELLED request %s, phase %s"
                              % (msg.get("cancelled_request_id"),
                                 msg.get("phase")))
                elif msg.get("sender") == "claude":
                    detail = "request, phase %s, change class %s" \
                             % (msg.get("phase"), msg.get("change_class"))
                else:
                    detail = "response, verdict %s" \
                             % (msg.get("response", {}) or {}).get("verdict")
                checks.append(_chk("I%03d" % n, "message %d" % n, "informational",
                                   "%s, sequence %s" % (detail, msg.get("sequence"))))

        elif op == "verify-chain":
            current = read_mailbox(_require_mailbox(args)[1])
            problems = verify_chain(current)
            checks.append(_chk("H1", "chain", "pass" if not problems else "fail",
                               "%d message(s) verified" % len(current["messages"])
                               if not problems
                               else "%d problem(s) found" % len(problems)))
            for n, (_idx, text) in enumerate(problems, 1):
                checks.append(_chk("H%03d" % (n + 1), "problem", "fail", text))
            checks.append(_chk("H0", "limitation", "informational",
                               "a hash chain detects corruption, truncation, "
                               "reordering, or partial rewriting; it cannot defeat "
                               "a rewrite of the mailbox and archive together"))
            if problems:
                exit_code = EXIT_STOPPED

        checks.extend(contract_checks())
        notes.append("A verdict is an opinion. PASS means only that a second reader "
                     "found no objection; every AAM and AM action still requires "
                     "Pedro's named approval.")

    except _Stop as stop:
        exit_code = stop.code
    except ef.SafetyLimitError as exc:
        _err("codex_relay: safety limit: %s\n" % ef.sanitize_text(str(exc)))
        return EXIT_LIMIT
    except ef.ValidationError as exc:
        _err("codex_relay: invalid input: %s\n" % ef.sanitize_text(str(exc)))
        return EXIT_INVALID
    except sg.StoppedError as exc:
        checks.append(_chk("Z0", "stopped", "stopped", ef.sanitize_text(str(exc))))
        checks.extend(contract_checks())
        exit_code = EXIT_STOPPED
    except OSError as exc:
        checks.append(_chk("Z1", "stopped", "stopped",
                           ef.sanitize_text("a filesystem operation failed: %s"
                                            % exc.__class__.__name__)))
        checks.extend(contract_checks())
        exit_code = EXIT_STOPPED

    doc = {
        "schema_version": ef.SCHEMA_VERSION,
        "phase": "codex relay",
        "scope": "local transport; a verdict is an opinion and never authorization",
        "checks": checks,
    }
    if notes:
        doc["notes"] = notes
    try:
        _emit(doc, args.format)
    except (ef.ValidationError, ef.SafetyLimitError) as exc:
        _err("codex_relay: %s\n" % ef.sanitize_text(str(exc)))
        return EXIT_INVALID
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
