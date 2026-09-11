#!/usr/bin/env python
"""change_classifier.py -- read-only Cowork change classifier.

Answers one question: *what is the MINIMUM approval class an observed or proposed
repository change requires?*

It reports. It NEVER approves. There is no output value meaning "approved", and no
flag, policy field, or input can produce one. Concretely it never:
  * stages, commits, pushes, fetches, merges, rebases, deploys, or contacts a remote
  * creates, removes, or switches a branch or worktree
  * writes, moves, renames, or deletes any file
  * mutates the Session Registry
  * checks out a blob, or executes anything supplied as data

The four classes, least to most restrictive:

  FA_AR       fully automated / automated read-only; no approval
  AAM         automated with manual approval naming exact targets
  AM          always manual; Pedro performs or explicitly commands each time
  PROHIBITED  must not proceed under any approval

THE FLOOR. Any change to a repository path is at least AAM. A repository write is
never FA/AR merely because its content is documentation. FA/AR is reachable only by
a declared read-only operation that changes no path at all.

FAIL-SAFE. An unrecognized path, an unrecognized change kind, or any ambiguity
escalates to AM. Nothing is ever resolved downward by default, and a semantic finding
may raise a path's class but can never lower it.

SEMANTIC SCANNING IS DEFENCE IN DEPTH. It can raise a class; it cannot prove the
absence of dangerous behaviour. A file that trips no indicator has not been shown to
be safe -- it has only failed to match a known pattern. Detection patterns live here,
in fixed reviewable source; the policy declares only identifiers, classes, and
reasons, so the policy file stays pure data. Matched text is never printed.

Exit codes:
  0  classified FA/AR only
  5  AAM required
  6  AM required
  7  PROHIBITED
  2  invalid input, usage, or policy
  3  safety-limit rejection
  4  stopped: no change, or observation was stale or ambiguous
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
POLICY_FILENAME = "change_policy.json"

CLASS_ORDER = ("FA_AR", "AAM", "AM", "PROHIBITED")
CLASS_RANK = {name: i for i, name in enumerate(CLASS_ORDER)}

MODES = ("classify-worktree", "classify-staged", "classify-commit",
         "classify-range", "classify-manifest", "validate-policy")

EXIT_BY_CLASS = {"FA_AR": 0, "AAM": 5, "AM": 6, "PROHIBITED": 7}

# Implementation maximums. A policy may lower any of these; it can never raise one.
MAX_INPUT_BYTES = 1024 * 1024
MAX_CHANGES = 1000
MAX_DEPTH = 32
MAX_PATH_CHARS = 512
MAX_SCAN_BYTES = 512 * 1024
MAX_FINDINGS_PER_PATH = 32

LIMIT_MAXIMUMS = {
    "max_input_bytes": MAX_INPUT_BYTES,
    "max_changes": MAX_CHANGES,
    "max_depth": MAX_DEPTH,
    "max_path_chars": MAX_PATH_CHARS,
    "max_scan_bytes": MAX_SCAN_BYTES,
    "max_findings_per_path": MAX_FINDINGS_PER_PATH,
}

CHANGE_KINDS = ("add", "modify", "delete", "rename", "copy", "typechange",
                "gitlink", "unmerged", "unknown")

_STATUS_TO_KIND = {"A": "add", "M": "modify", "D": "delete", "R": "rename",
                   "C": "copy", "T": "typechange", "U": "unmerged"}

_OID_RE = re.compile(r"^[0-9a-f]{7,64}$")
_FULL_OID_RE = re.compile(r"^[0-9a-f]{40}$|^[0-9a-f]{64}$")
_HASH_RE = re.compile(r"^[0-9a-f]{40}$|^[0-9a-f]{64}$")
_REVISION_RE = re.compile(r"^[0-9a-f]{40}$|^[0-9a-f]{64}$")
_GITLINK_MODE = "160000"
# Git abbreviates object ids in --raw output unless --no-abbrev is given, and a
# missing side is reported as zeros at whatever width. Match any all-zero id.
_NULL_OID = re.compile(r"^0+$")

_MACHINE_PATH_RE = re.compile(
    r"([A-Za-z]:[\\/]|\\\\[A-Za-z0-9._-]+\\|/(?:home|Users)/[A-Za-z0-9._-]+|"
    r"/mnt/[a-z]/|%USERPROFILE%|\$HOME\b|~[/\\][A-Za-z])")

# Manifest content that would smuggle in execution, environment, or credentials.
_UNSAFE_INPUT_RE = re.compile(
    r"(?i)(\$\(|`|&&|\|\||;\s*\w+\s|(?<![.\w*])(sudo|curl|wget|bash|eval|exec|"
    r"powershell|cmd\.exe)\b|(?<![.\w*])sh\s+-c\b|<script|javascript:|"
    r"https?://\S*[?&](?:token|key|secret|password)=|ssh://|git@|"
    r"api[_-]?key\s*[:=]|secret\s*[:=]|token\s*[:=]|password\s*[:=]|"
    r"sk-ant-|ghp_|AKIA[0-9A-Z]{16}|-----BEGIN)")


# --------------------------------------------------------------------------
# Semantic indicators. Patterns live here, in fixed source; the policy declares
# only their identifiers, classes, and reasons. Matched text is NEVER printed.
# --------------------------------------------------------------------------

_RETIREMENT_FLAG_RE = re.compile(
    r"(?i)\b(NOVA_TRADING_SUBSYSTEM_ENABLED|NOVA_AUTO_EXECUTE)\b\s*"
    r"[:=]\s*[\"']?\s*(true|1|yes|on|enabled)\b")

_GUARD_BYPASS_RE = re.compile(
    r"(?i)("
    r"(disable|bypass|skip|remove|delete|neutralis|neutraliz|weaken|defeat|"
    r"circumvent|turn\s+off)[^.\n]{0,40}\b(guard|pretooluse|hook)\b"
    r"|\b(guard|hook)s?\b[^.\n]{0,40}\b(disabled|bypassed|skipped|removed|off)\b"
    r"|nova_guard_hook[^\n]{0,40}(disabled|bypass|skip|remove)"
    r"|--no-verify"
    r"|\bGUARD_(DISABLED|BYPASS|OFF|SKIP)\b"
    r"|\bexit\s*\(\s*0\s*\)\s*#\s*(bypass|skip|allow\s+everything)"
    r")")

_LLM_SYMBOL_RE = re.compile(
    r"(?i)\b(anthropic|claude|messages\.create|openai|chat\.completions|"
    r"grok|xai|llm_|completion\(|generate_text)\b")

_ORDER_SYMBOL_RE = re.compile(
    r"(?i)\b(submit_order|place_order|create_order|send_order|cancel_order|"
    r"close_position|MarketOrderRequest|LimitOrderRequest|OrderRequest|"
    r"trading_client\.|orders\.create|/v2/orders)\b")

_AUTONOMOUS_ORDER_RE = re.compile(
    r"(?i)("
    r"(auto|autonomous|automatic|unattended|without\s+approval|no\s+approval)"
    r"[^.\n]{0,40}\b(order|trade|execution|submit|cancel)\b"
    r"|\b(order|trade)s?\b[^.\n]{0,40}\b(auto[-_ ]?submit|auto[-_ ]?execute|"
    r"fire\s+automatically)\b"
    r"|\bAUTO_SUBMIT_ORDERS\b|\bAUTONOMOUS_TRADING\b"
    r")")

_CREDENTIAL_RE = re.compile(
    r"(?i)\b[a-z0-9_.-]*(api[_-]?key|secret|token|password|passphrase|cookie|"
    r"authorization|bearer|private[_-]?key|access[_-]?key|refresh[_-]?token|"
    r"client[_-]?secret)[a-z0-9_.-]*\s*[:=]\s*[\"']?[A-Za-z0-9/+_.-]{12,}")
_CREDENTIAL_FORMAT_RE = re.compile(
    r"(sk-ant-[A-Za-z0-9_-]{8,}|ghp_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|"
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----|xox[baprs]-[A-Za-z0-9-]{10,}|"
    r"eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.)")
# Names that read as placeholders or lookups rather than embedded values.
_CREDENTIAL_ALLOW_RE = re.compile(
    r"(?i)(os\.environ|getenv|<[a-z_]+>|\$\{|\.\.\.|example|placeholder|"
    r"redacted|xxx+|your[_-]|dummy|fake|sample|_RE\b|_PATTERN\b|re\.compile)")

_AUTO_PROMOTION_RE = re.compile(
    r"(?i)("
    r"(auto|automatic|automatically|unattended)[^.\n]{0,40}"
    r"\bpromot(e|es|ed|ion)\b"
    r"|\bpromot(e|es|ed)\b[^.\n]{0,40}\b(automatically|without\s+(review|approval))"
    r"|\bAUTO_PROMOTE\b|auto_promote\b|promote_to_approved\b"
    r")")

_RISK_LIMIT_RE = re.compile(
    r"(?i)\b(max_daily_loss|daily_loss_limit|max_drawdown|trailing_drawdown|"
    r"max_position_size|position_cap|max_concurrent_positions|risk_per_trade|"
    r"max_contracts|loss_limit|drawdown_limit|exposure_cap)\b")

_KILL_SWITCH_RE = re.compile(
    r"(?i)\b(kill_switch|killswitch|NOVA_TRADING_SUBSYSTEM_ENABLED|"
    r"NOVA_AUTO_EXECUTE|trading_enabled|execution_enabled|emergency_stop|"
    r"halt_trading|panic_stop)\b")

_BROKER_API_RE = re.compile(
    r"(?i)\b(alpaca|TradingClient|submit_order|cancel_order|close_position|"
    r"MarketOrderRequest|LimitOrderRequest|/v2/orders|broker_client|"
    r"place_order|order_request)\b")

_RESEARCH_PROMOTION_RE = re.compile(
    r"(?i)("
    r"\bpromot(e|es|ed|ing|ion)\b[^.\n]{0,40}\b(approved|authoritative|rules?|"
    r"specification|spec)\b"
    r"|\b(approved|authoritative)\b[^.\n]{0,30}\bspecification\b"
    r"|nova_knowledge_core/RULES/"
    r")")

_DEPLOY_INTENT_RE = re.compile(
    r"(?i)("
    r"\bgit\s+(push|merge|rebase|reset\s+--hard|filter-branch|filter-repo)\b"
    r"|\bpush\s+--force\b|--force-with-lease\b"
    r"|\bdeploy(ing|ment)?\s+to\s+(production|render|prod)\b"
    r"|\brelease\s+to\s+production\b"
    r"|\brewrit(e|ing)\s+history\b"
    r")")

_INDICATORS = (
    # (id, callable(text) -> bool)
    ("retirement_flag_activation", lambda t: bool(_RETIREMENT_FLAG_RE.search(t))),
    ("guard_bypass", lambda t: bool(_GUARD_BYPASS_RE.search(t))),
    ("llm_to_order_path",
     lambda t: bool(_LLM_SYMBOL_RE.search(t)) and bool(_ORDER_SYMBOL_RE.search(t))),
    ("autonomous_order_submission", lambda t: bool(_AUTONOMOUS_ORDER_RE.search(t))),
    ("credential_material", lambda t: _has_credential(t)),
    ("automatic_research_promotion", lambda t: bool(_AUTO_PROMOTION_RE.search(t))),
    ("risk_limit_change", lambda t: bool(_RISK_LIMIT_RE.search(t))),
    ("kill_switch_change", lambda t: bool(_KILL_SWITCH_RE.search(t))),
    ("broker_order_api", lambda t: bool(_BROKER_API_RE.search(t))),
    ("research_authority_promotion", lambda t: bool(_RESEARCH_PROMOTION_RE.search(t))),
    ("deployment_or_history_intent", lambda t: bool(_DEPLOY_INTENT_RE.search(t))),
)

INDICATOR_IDS = tuple(i for i, _fn in _INDICATORS)


def _has_credential(text):
    """A credential-shaped value, ignoring obvious placeholders and lookups."""
    for match in _CREDENTIAL_RE.finditer(text):
        line_start = text.rfind("\n", 0, match.start()) + 1
        line_end = text.find("\n", match.end())
        line = text[line_start:line_end if line_end != -1 else len(text)]
        if not _CREDENTIAL_ALLOW_RE.search(line):
            return True
    return bool(_CREDENTIAL_FORMAT_RE.search(text))


class PolicyError(Exception):
    """The policy file is missing or unusable -> exit 2."""


# --------------------------------------------------------------------------
# Class algebra
# --------------------------------------------------------------------------

def most_restrictive(*classes):
    """The highest class present. Never returns something lower than any input."""
    best = None
    for c in classes:
        if c is None:
            continue
        if c not in CLASS_RANK:
            c = "AM"                      # fail-safe: unknown escalates
        if best is None or CLASS_RANK[c] > CLASS_RANK[best]:
            best = c
    return best


def _bad(msg):
    raise ef.ValidationError(msg)


def _reject_constant(_name):
    raise ef.ValidationError("non-standard numeric value is not permitted")


# --------------------------------------------------------------------------
# Policy
# --------------------------------------------------------------------------

POLICY_REQUIRED = (
    "schema_version", "policy_name", "class_order", "class_labels", "fail_safe",
    "repository_write_floor", "change_kind_minimums",
    "deletion_never_below_modification", "binary", "submodule",
    "case_only_rename", "sensitive_areas", "path_rules", "declared_operations",
    "semantic_indicators", "semantic_scanning_note", "prohibited_indicator_ids",
    "ignored_files", "historical_presence", "limits",
)
POLICY_OPTIONAL = ("description",)

_POLICY_EXECUTABLE_RE = re.compile(
    r"(?i)(\$\(|`|&&|\|\||<script|javascript:|https?://|ssh://|git@|"
    r"(?<![.\w*])(sudo|curl|wget|bash|eval|exec)\b|(?<![.\w*])sh\s+-c\b)")

_TOO_BROAD = {"**", "*", "/**", "./**", ".", "./", "*/**", "**/*"}


def load_policy(path=None):
    p = path or os.path.join(os.path.dirname(os.path.abspath(__file__)), POLICY_FILENAME)
    try:
        raw = open(p, "rb").read()
    except OSError:
        raise PolicyError("the change policy file could not be read")
    if len(raw) > MAX_INPUT_BYTES:
        raise ef.SafetyLimitError("the policy file exceeds the maximum input size")
    try:
        policy = json.loads(raw.decode("utf-8"), parse_constant=_reject_constant)
    except ef.ValidationError:
        raise
    except Exception:
        raise PolicyError("the change policy file is not valid JSON")
    if not isinstance(policy, dict):
        raise PolicyError("the change policy must be a JSON object")
    if policy.get("schema_version") != SCHEMA_VERSION:
        raise PolicyError("unsupported change policy schema")
    return policy, hashlib.sha256(raw).hexdigest()


def _scan_policy(node, depth=0):
    if depth > MAX_DEPTH:
        raise ef.SafetyLimitError("the policy nests deeper than the maximum depth")
    if isinstance(node, dict):
        for k, v in node.items():
            _scan_policy(k, depth + 1)
            _scan_policy(v, depth + 1)
    elif isinstance(node, list):
        for v in node:
            _scan_policy(v, depth + 1)
    elif isinstance(node, str):
        if _POLICY_EXECUTABLE_RE.search(node):
            raise PolicyError("the policy contains an executable construct or URL")
        if _CREDENTIAL_FORMAT_RE.search(node):
            raise PolicyError("the policy contains a credential-shaped value")
        if _MACHINE_PATH_RE.search(node) or node.startswith("\\\\"):
            raise PolicyError("the policy contains a machine-specific path")


def _policy_path(value, what):
    if not isinstance(value, str) or not value.strip():
        raise PolicyError("%s must be a non-empty string" % what)
    norm = value.replace("\\", "/")
    if norm.startswith("/") or re.match(r"^[A-Za-z]:", norm):
        raise PolicyError("%s must be relative, not absolute" % what)
    if ".." in norm.split("/"):
        raise PolicyError("%s must not contain a parent-directory traversal" % what)
    if len(norm) > MAX_PATH_CHARS:
        raise ef.SafetyLimitError("%s exceeds the maximum path length" % what)
    if norm in _TOO_BROAD:
        raise PolicyError("%s is too broad to be a rule" % what)
    # An extension glob such as `*.md` is narrow -- it still carries literal
    # characters. Only a pattern whose every segment is pure wildcard, and which
    # can therefore match any path at all, is refused.
    segments = [s for s in norm.split("/") if s and s != "**"]
    if not segments or all(not re.sub(r"[*?\[\]!]", "", s) for s in segments):
        raise PolicyError("%s is too broad; it would match every path" % what)
    return norm


def validate_policy(policy):
    missing = [f for f in POLICY_REQUIRED if f not in policy]
    if missing:
        raise PolicyError("the policy is missing required field(s): %s"
                          % ", ".join(sorted(missing)))
    unknown = set(policy) - set(POLICY_REQUIRED) - set(POLICY_OPTIONAL)
    if unknown:
        raise PolicyError("the policy has unrecognized field(s): %s"
                          % ", ".join(sorted(unknown)))
    _scan_policy(policy)

    if policy["class_order"] != list(CLASS_ORDER):
        raise PolicyError("class_order must be exactly %s" % json.dumps(list(CLASS_ORDER)))
    for name in CLASS_ORDER:
        if name not in policy["class_labels"]:
            raise PolicyError("class_labels is missing %s" % name)

    fs = policy["fail_safe"]
    for key in ("unknown_path_class", "unknown_change_kind_class", "ambiguous_class"):
        if fs.get(key) != "AM":
            raise PolicyError("fail_safe %s must be \"AM\"" % key)

    if policy["repository_write_floor"].get("class") != "AAM":
        raise PolicyError("repository_write_floor class must be \"AAM\"; a repository "
                          "write is never FA/AR")
    if policy["deletion_never_below_modification"] is not True:
        raise PolicyError("deletion_never_below_modification must be true")
    if policy["binary"].get("minimum_class") != "AAM":
        raise PolicyError("binary minimum_class must be \"AAM\"")
    if policy["binary"].get("sensitive_area_class") != "AM":
        raise PolicyError("binary sensitive_area_class must be \"AM\"")
    if policy["submodule"].get("class") != "AM":
        raise PolicyError("submodule class must be \"AM\"")
    if policy["ignored_files"].get("enter_git_classification") is not False:
        raise PolicyError("ignored files must not enter git classification")
    if policy["historical_presence"].get("authorizes_new_changes") is not False:
        raise PolicyError("historical presence must not authorize new changes")

    kinds = policy["change_kind_minimums"]
    for kind in ("add", "modify", "delete", "rename", "typechange", "gitlink"):
        if kind not in kinds:
            raise PolicyError("change_kind_minimums is missing %s" % kind)
    for kind, cls in sorted(kinds.items()):
        if kind not in CHANGE_KINDS:
            raise PolicyError("change_kind_minimums names an unknown kind: %s" % kind)
        if cls not in CLASS_RANK:
            raise PolicyError("change_kind_minimums[%s] is not a class" % kind)

    if not isinstance(policy["sensitive_areas"], list) or not policy["sensitive_areas"]:
        raise PolicyError("sensitive_areas must be a non-empty list")
    for area in policy["sensitive_areas"]:
        _policy_path(area, "sensitive area")

    rules = policy["path_rules"]
    if not isinstance(rules, list) or not rules:
        raise PolicyError("path_rules must be a non-empty list")
    seen_ids, seen_patterns = set(), {}
    for rule in rules:
        if not isinstance(rule, dict):
            raise PolicyError("each path rule must be a mapping")
        extra = set(rule) - {"id", "class", "reason", "patterns", "exceptions"}
        if extra:
            raise PolicyError("path rule has unrecognized field(s): %s"
                              % ", ".join(sorted(extra)))
        rid = rule.get("id")
        if not isinstance(rid, str) or not rid.strip():
            raise PolicyError("each path rule needs an id")
        if rid in seen_ids:
            raise PolicyError("duplicate path rule id: %s" % rid)
        seen_ids.add(rid)
        if rule.get("class") not in CLASS_RANK:
            raise PolicyError("path rule %s has an unrecognized class" % rid)
        if not isinstance(rule.get("reason"), str) or not rule["reason"].strip():
            raise PolicyError("path rule %s needs a reason" % rid)
        pats = rule.get("patterns")
        if not isinstance(pats, list) or not pats:
            raise PolicyError("path rule %s needs at least one pattern" % rid)
        for pat in pats:
            norm = _policy_path(pat, "path rule pattern")
            folded = norm.lower()
            if folded in seen_patterns and seen_patterns[folded] != rid:
                raise PolicyError("pattern %r appears in two rules (%s and %s)"
                                  % (pat, seen_patterns[folded], rid))
            seen_patterns[folded] = rid
        for exc in rule.get("exceptions", []):
            _policy_path(exc, "path rule exception")

    ops = policy["declared_operations"]
    if not isinstance(ops, dict) or not ops:
        raise PolicyError("declared_operations must be a non-empty mapping")
    for name, spec in sorted(ops.items()):
        if not isinstance(spec, dict) or spec.get("class") not in CLASS_RANK:
            raise PolicyError("declared operation %s needs a recognized class" % name)
        if not isinstance(spec.get("reason"), str) or not spec["reason"].strip():
            raise PolicyError("declared operation %s needs a reason" % name)

    ind = policy["semantic_indicators"]
    if not isinstance(ind, dict):
        raise PolicyError("semantic_indicators must be a mapping")
    declared, implemented = set(ind), set(INDICATOR_IDS)
    if declared != implemented:
        raise PolicyError(
            "semantic indicator declarations and implementations disagree; "
            "declared-only: %s; implemented-only: %s"
            % (", ".join(sorted(declared - implemented)) or "none",
               ", ".join(sorted(implemented - declared)) or "none"))
    for name, spec in sorted(ind.items()):
        if not isinstance(spec, dict) or spec.get("class") not in CLASS_RANK:
            raise PolicyError("semantic indicator %s needs a recognized class" % name)
        if not isinstance(spec.get("reason"), str) or not spec["reason"].strip():
            raise PolicyError("semantic indicator %s needs a reason" % name)
    for name in policy["prohibited_indicator_ids"]:
        if name not in ind:
            raise PolicyError("prohibited_indicator_ids names an undeclared "
                              "indicator: %s" % name)
        if ind[name]["class"] != "PROHIBITED":
            raise PolicyError("indicator %s is listed as prohibited but declares "
                              "class %s" % (name, ind[name]["class"]))

    if "cannot prove" not in policy["semantic_scanning_note"].lower() \
            and "cannot prove" not in policy["semantic_scanning_note"]:
        raise PolicyError("semantic_scanning_note must state that scanning cannot "
                          "prove the absence of dangerous behaviour")

    limits = policy["limits"]
    if not isinstance(limits, dict):
        raise PolicyError("limits must be a mapping")
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
    return policy


# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------

def _norm(path):
    return path.replace("\\", "/").strip("/")


def _under(root, path):
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
        return fnmatch.fnmatch(p, tail) \
            or any(fnmatch.fnmatch(seg, tail) for seg in p.split("/"))
    return fnmatch.fnmatch(p, pat) or fnmatch.fnmatch(os.path.basename(p), pat)


def check_relative(path, what, limits):
    if not isinstance(path, str) or not path.strip():
        _bad("%s must be a non-empty string" % what)
    norm = path.replace("\\", "/")
    if norm.startswith("/") or re.match(r"^[A-Za-z]:", norm) or norm.startswith("\\\\"):
        _bad("%s must be repository-relative, not absolute" % what)
    if ".." in norm.split("/"):
        _bad("%s must not contain a parent-directory traversal" % what)
    if len(norm) > limits["max_path_chars"]:
        raise ef.SafetyLimitError("%s exceeds the maximum path length" % what)
    if _MACHINE_PATH_RE.search(norm):
        _bad("%s must not contain a machine-specific path" % what)
    return _norm(norm)


def in_sensitive_area(path, policy):
    return any(_under(area, path) for area in policy["sensitive_areas"])


def path_rule_for(path, policy):
    """The most restrictive matching rule. Order in the file never decides."""
    best = None
    for rule in policy["path_rules"]:
        if any(_matches(path, e) for e in rule.get("exceptions", [])):
            continue
        if any(_matches(path, pat) for pat in rule["patterns"]):
            if best is None or CLASS_RANK[rule["class"]] > CLASS_RANK[best["class"]]:
                best = rule
    return best


# --------------------------------------------------------------------------
# Git observation (every call through the A7 read-only allowlist)
# --------------------------------------------------------------------------

def _git(repo, args):
    return a7._git(repo, args)


def _git_ok(repo, args):
    return a7._git_ok(repo, args)


def resolve_oid(repo, value, what):
    if not isinstance(value, str) or not _OID_RE.match(value.strip()):
        _bad("%s must be a hexadecimal git object id" % what)
    rc, out, _err = _git(repo, ["rev-parse", "--verify", "%s^{commit}" % value.strip()])
    if rc != 0 or not _FULL_OID_RE.match(out.strip()):
        raise sg.StoppedError("%s could not be resolved to a commit" % what)
    return out.strip()


def _parse_raw_z(payload):
    """Parse `git diff --raw -z` records into change dictionaries."""
    fields = payload.split("\0")
    changes, i = [], 0
    while i < len(fields):
        head = fields[i]
        if not head:
            i += 1
            continue
        if not head.startswith(":"):
            raise sg.StoppedError("git produced an unrecognized diff record")
        parts = head[1:].split(" ")
        if len(parts) < 5:
            raise sg.StoppedError("git produced an incomplete diff record")
        old_mode, new_mode, old_oid, new_oid, status = parts[:5]
        letter = status[0].upper()
        kind = _STATUS_TO_KIND.get(letter, "unknown")
        i += 1
        if i >= len(fields):
            raise sg.StoppedError("git produced a diff record without a path")
        first = fields[i]
        i += 1
        source_path = None
        if letter in ("R", "C"):
            if i >= len(fields):
                raise sg.StoppedError("a rename record is missing its destination")
            source_path, path = first, fields[i]
            i += 1
        else:
            path = first
        if _GITLINK_MODE in (old_mode, new_mode):
            kind = "gitlink"
        changes.append({
            "path": _norm(path),
            "source_path": _norm(source_path) if source_path else None,
            "kind": kind,
            "old_mode": old_mode,
            "new_mode": new_mode,
            "old_oid": old_oid,
            "new_oid": new_oid,
            "origin": "git",
        })
    return changes


def observe_worktree(repo, limits):
    """Tracked worktree changes plus untracked files. Ignored files never appear."""
    raw = _git_ok(repo, ["diff", "--raw", "--no-abbrev", "-z", "--find-renames", "HEAD"])
    changes = _parse_raw_z(raw)
    others = _git_ok(repo, ["ls-files", "--others", "--exclude-standard", "-z"])
    for path in others.split("\0"):
        if path:
            changes.append({"path": _norm(path), "source_path": None, "kind": "add",
                            "old_mode": "000000", "new_mode": "100644",
                            "old_oid": "0" * 40, "new_oid": "0" * 40,
                            "origin": "worktree"})
    return _cap(changes, limits)


def observe_staged(repo, limits):
    raw = _git_ok(repo, ["diff", "--cached", "--raw", "--no-abbrev", "-z", "--find-renames"])
    return _cap(_parse_raw_z(raw), limits)


def observe_commit(repo, oid, limits):
    raw = _git_ok(repo, ["diff-tree", "--no-commit-id", "--raw", "--no-abbrev", "-z",
                         "-r", "--find-renames", oid])
    return _cap(_parse_raw_z(raw), limits)


def observe_range(repo, base, head, limits):
    raw = _git_ok(repo, ["diff", "--raw", "--no-abbrev", "-z", "--find-renames", base, head])
    return _cap(_parse_raw_z(raw), limits)


def _cap(changes, limits):
    if len(changes) > limits["max_changes"]:
        raise ef.SafetyLimitError("the change set holds more paths than the maximum")
    return sorted(changes, key=lambda c: (c["path"].lower(), c["kind"]))


def new_side_bytes(repo, change, limits):
    """(status, bytes) for the new side of a change. Scanned only, never checked out.

    status is one of:
      "scanned"         content was obtained and may be scanned
      "too-large"       content exceeds the scan ceiling; ambiguous, not clean
      "not-applicable"  a deletion or a gitlink has no new content to scan
      "unavailable"     content could not be obtained; ambiguous, not clean

    An UNSTAGED edit to a tracked file has no blob in the object database -- git
    reports an all-zero new object id -- so the working file is read instead.
    Without this fall-back the most ordinary case of all, editing a tracked file,
    would go unscanned and silently look clean.
    """
    if change["kind"] in ("delete", "gitlink"):
        return "not-applicable", None
    oid = change.get("new_oid") or ""
    if oid and not _NULL_OID.match(oid):
        rc, out, _err = _git(repo, ["cat-file", "-s", oid])
        if rc == 0 and out.strip().isdigit() \
                and int(out.strip()) > limits["max_scan_bytes"]:
            return "too-large", None
        rc, out, _err = _git(repo, ["cat-file", "blob", oid])
        if rc != 0:
            return "unavailable", None
        return "scanned", out.encode("utf-8", "surrogateescape")
    full = os.path.join(repo, change["path"].replace("/", os.sep))
    if os.path.islink(full):
        return "unavailable", None
    if not os.path.isfile(full):
        return "unavailable", None
    if os.path.getsize(full) > limits["max_scan_bytes"]:
        return "too-large", None
    with open(full, "rb") as fh:
        return "scanned", fh.read()


# --------------------------------------------------------------------------
# Semantic scanning
# --------------------------------------------------------------------------

def scan_text(text, policy, limits):
    """Indicator ids only. Matched text is never captured, stored, or printed."""
    found = []
    for name, test in _INDICATORS:
        try:
            if test(text):
                found.append(name)
        except Exception:
            # A pattern that cannot be evaluated is treated as ambiguous, not clean.
            found.append(name)
        if len(found) >= limits["max_findings_per_path"]:
            break
    return found


def is_binary(raw):
    if raw is None:
        return False
    return b"\x00" in raw[:8192]


# --------------------------------------------------------------------------
# Classification
# --------------------------------------------------------------------------

def classify_change(change, policy, limits, content=None, declared_findings=(),
                    content_status="not-applicable"):
    """Classify one path. Returns a result dict. Never lowers any contributing class."""
    reasons = []
    path = change["path"]

    floor = policy["repository_write_floor"]["class"]
    reasons.append(("repository write floor", floor,
                    policy["repository_write_floor"]["note"].split(".")[0]))
    cls = floor

    kind = change["kind"]
    if kind not in CHANGE_KINDS or kind == "unknown":
        kind_class = policy["fail_safe"]["unknown_change_kind_class"]
        reasons.append(("unrecognized change kind", kind_class,
                        "an unrecognized change kind escalates"))
    else:
        kind_class = policy["change_kind_minimums"].get(
            kind, policy["fail_safe"]["unknown_change_kind_class"])
        reasons.append(("change kind %s" % kind, kind_class,
                        "minimum for this kind of change"))
    cls = most_restrictive(cls, kind_class)

    # A deletion is never treated more leniently than a modification of the same path.
    if kind == "delete" and policy["deletion_never_below_modification"]:
        mod_class = policy["change_kind_minimums"].get("modify", "AAM")
        if CLASS_RANK[mod_class] > CLASS_RANK[kind_class]:
            reasons.append(("deletion floor", mod_class,
                            "a deletion is never below a modification"))
            cls = most_restrictive(cls, mod_class)

    # Both sides of a rename are classified; the destination never softens the source.
    targets = [path]
    if change.get("source_path"):
        targets.append(change["source_path"])
    for target in targets:
        rule = path_rule_for(target, policy)
        if rule is None:
            unknown_class = policy["fail_safe"]["unknown_path_class"]
            reasons.append(("unknown path %s" % target, unknown_class,
                            "no policy rule matches; unknown paths escalate"))
            cls = most_restrictive(cls, unknown_class)
        else:
            label = "path rule %s" % rule["id"]
            if target != path:
                label += " (rename source)"
            reasons.append((label, rule["class"], rule["reason"]))
            cls = most_restrictive(cls, rule["class"])

    if len(targets) == 2 and _norm(targets[0]).lower() == _norm(targets[1]).lower() \
            and _norm(targets[0]) != _norm(targets[1]):
        reasons.append(("case-only rename", policy["case_only_rename"]["class"],
                        policy["case_only_rename"]["note"].split(".")[0]))
        cls = most_restrictive(cls, policy["case_only_rename"]["class"])

    if kind == "gitlink" or _GITLINK_MODE in (change.get("old_mode"),
                                              change.get("new_mode")):
        reasons.append(("submodule gitlink", policy["submodule"]["class"],
                        policy["submodule"]["note"]))
        cls = most_restrictive(cls, policy["submodule"]["class"])

    binary = change.get("binary")
    if binary is None:
        binary = is_binary(content)
    if binary:
        bin_class = policy["binary"]["minimum_class"]
        why = "a binary cannot be read for intent"
        if in_sensitive_area(path, policy):
            bin_class = policy["binary"]["sensitive_area_class"]
            why = "an unreadable binary in a sensitive area is always manual"
        reasons.append(("binary content", bin_class, why))
        cls = most_restrictive(cls, bin_class)

    findings = list(declared_findings)
    if content is not None and not binary:
        text = content.decode("utf-8", "replace")
        findings.extend(f for f in scan_text(text, policy, limits) if f not in findings)
    elif content_status in ("too-large", "unavailable"):
        # Unscanned content is ambiguous, never clean.
        why = ("content too large to scan" if content_status == "too-large"
               else "content could not be obtained for scanning")
        reasons.append((why, policy["fail_safe"]["ambiguous_class"],
                        "unscanned content is ambiguous, not clean"))
        cls = most_restrictive(cls, policy["fail_safe"]["ambiguous_class"])

    for name in findings:
        spec = policy["semantic_indicators"].get(name)
        if spec is None:
            reasons.append(("unknown semantic finding %s" % name,
                            policy["fail_safe"]["ambiguous_class"],
                            "an unrecognized finding escalates"))
            cls = most_restrictive(cls, policy["fail_safe"]["ambiguous_class"])
            continue
        # Semantic findings may raise a class; most_restrictive can never lower one.
        reasons.append(("semantic indicator %s" % name, spec["class"], spec["reason"]))
        cls = most_restrictive(cls, spec["class"])

    return {
        "path": path,
        "source_path": change.get("source_path"),
        "kind": kind,
        "binary": bool(binary),
        "minimum_class": cls,
        "findings": sorted(findings),
        "reasons": reasons,
    }


# --------------------------------------------------------------------------
# Manifest mode
# --------------------------------------------------------------------------

MANIFEST_REQUIRED = ("schema_version",)
MANIFEST_OPTIONAL = ("declared_operation", "changes", "notes")
CHANGE_REQUIRED = ("path", "kind")
CHANGE_OPTIONAL = ("source_path", "old_hash", "new_hash", "binary",
                   "semantic_findings", "mode")


def _scan_manifest_strings(node, depth=0):
    if depth > MAX_DEPTH:
        raise ef.SafetyLimitError("the manifest nests deeper than the maximum depth")
    if isinstance(node, dict):
        for k, v in node.items():
            _scan_manifest_strings(k, depth + 1)
            _scan_manifest_strings(v, depth + 1)
    elif isinstance(node, list):
        for v in node:
            _scan_manifest_strings(v, depth + 1)
    elif isinstance(node, str):
        if _UNSAFE_INPUT_RE.search(node):
            _bad("the manifest contains a command, script, environment value, "
                 "credential, or sensitive URL and was rejected")


def validate_manifest(doc, policy, limits):
    if not isinstance(doc, dict):
        _bad("the manifest must be a JSON object")
    for f in MANIFEST_REQUIRED:
        if f not in doc:
            _bad("the manifest is missing required field: %s" % f)
    unknown = set(doc) - set(MANIFEST_REQUIRED) - set(MANIFEST_OPTIONAL)
    if unknown:
        _bad("the manifest has unrecognized field(s): %s" % ", ".join(sorted(unknown)))
    if doc["schema_version"] != SCHEMA_VERSION:
        _bad("unsupported manifest schema_version")
    _scan_manifest_strings(doc)

    op = doc.get("declared_operation")
    if op is not None:
        if not isinstance(op, str) or op not in policy["declared_operations"]:
            _bad("declared_operation is not a recognized operation")

    changes = doc.get("changes", [])
    if not isinstance(changes, list):
        _bad("changes must be a list")
    if len(changes) > limits["max_changes"]:
        raise ef.SafetyLimitError("the manifest holds more changes than the maximum")

    out, seen = [], {}
    for n, item in enumerate(changes, 1):
        if not isinstance(item, dict):
            _bad("change %d must be a mapping" % n)
        missing = [f for f in CHANGE_REQUIRED if f not in item]
        if missing:
            _bad("change %d is missing field(s): %s" % (n, ", ".join(sorted(missing))))
        extra = set(item) - set(CHANGE_REQUIRED) - set(CHANGE_OPTIONAL)
        if extra:
            _bad("change %d has unrecognized field(s): %s"
                 % (n, ", ".join(sorted(extra))))
        path = check_relative(item["path"], "change %d path" % n, limits)
        kind = item["kind"]
        if not isinstance(kind, str) or kind not in CHANGE_KINDS:
            _bad("change %d has an unrecognized kind" % n)
        source_path = None
        if "source_path" in item and item["source_path"] is not None:
            source_path = check_relative(item["source_path"],
                                         "change %d source_path" % n, limits)
        if kind in ("rename", "copy") and source_path is None:
            _bad("change %d is a %s and needs a source_path" % (n, kind))
        for key in ("old_hash", "new_hash"):
            if key in item and item[key] is not None:
                if not isinstance(item[key], str) or not _HASH_RE.match(item[key]):
                    _bad("change %d %s must be a full sha-1 or sha-256 digest"
                         % (n, key))
        if "binary" in item and not isinstance(item["binary"], bool):
            _bad("change %d binary must be a boolean" % n)
        findings = item.get("semantic_findings", [])
        if not isinstance(findings, list):
            _bad("change %d semantic_findings must be a list" % n)
        if len(findings) > limits["max_findings_per_path"]:
            raise ef.SafetyLimitError("change %d declares more findings than the maximum"
                                      % n)
        for f in findings:
            if not isinstance(f, str) or not re.match(r"^[a-z][a-z0-9_]{0,63}$", f):
                _bad("change %d declares a malformed semantic finding" % n)
        mode = item.get("mode")
        if mode is not None and (not isinstance(mode, str)
                                 or not re.match(r"^[0-7]{6}$", mode)):
            _bad("change %d mode must be a six-digit octal file mode" % n)
        key = (path.lower(), kind)
        if key in seen:
            _bad("change %d duplicates an earlier path and kind" % n)
        seen[key] = True
        out.append({"path": path, "source_path": source_path, "kind": kind,
                    "old_mode": mode or "100644", "new_mode": mode or "100644",
                    "old_oid": item.get("old_hash") or "0" * 40,
                    "new_oid": item.get("new_hash") or "0" * 40,
                    "binary": item.get("binary"),
                    "declared_findings": findings,
                    "origin": "manifest"})

    notes = doc.get("notes", [])
    if not isinstance(notes, list):
        _bad("notes must be a list")
    return op, sorted(out, key=lambda c: (c["path"].lower(), c["kind"])), notes


# --------------------------------------------------------------------------
# Baselines
# --------------------------------------------------------------------------

def _chk(cid, label, status, evidence):
    return {"id": cid, "label": label, "status": status, "evidence": evidence}


def baseline_checks(repo, identity, expected_head, expected_branch):
    """Freshness of the observation, via the Staleness Guard's own comparison."""
    checks, stopped = [], False
    head = _git_ok(repo, ["rev-parse", "HEAD"]).strip()
    branch = _git_ok(repo, ["rev-parse", "--abbrev-ref", "HEAD"]).strip()
    checks.append(_chk("B1", "worktree", "pass", "resolved as ${REPO} (%s)" % identity))
    if expected_branch:
        ok = branch == expected_branch
        checks.append(_chk("B2", "branch", "pass" if ok else "stopped",
                           "expected %s, observed %s" % (expected_branch, branch)))
        stopped = stopped or not ok
    if expected_head:
        base = {"schema_version": sg.SCHEMA_VERSION, "expected_branch": branch,
                "expected_head": expected_head}
        sg.validate_baseline(base)
        ok = head == expected_head
        checks.append(_chk("B3", "HEAD", "pass" if ok else "stopped",
                           "expected %s, observed %s" % (expected_head, head)))
        stopped = stopped or not ok
    return checks, stopped, head


def registry_checks(registry_path, session_id, identity, head):
    """Optional, read-only. Never locks, writes, or advances anything."""
    if not registry_path:
        return [], False
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
    checks = [_chk("N1", "registry session", "pass", "found, observed %s" % state)]
    stopped = False
    for cid, label, ok, ev in (
            ("N2", "registry session active", rec["status"] == "active",
             "status %s" % rec["status"]),
            ("N3", "registry session fresh", state == "live", "observed %s" % state),
            ("N4", "registry worktree", rec["worktree_identity"] == identity,
             "expected %s, observed %s" % (rec["worktree_identity"], identity)),
            ("N5", "registry expected commit", rec["expected_commit"] == head,
             "registry %s the observed HEAD"
             % ("matches" if rec["expected_commit"] == head else "does NOT match"))):
        checks.append(_chk(cid, label, "pass" if ok else "stopped", ev))
        stopped = stopped or not ok
    return checks, stopped


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------

_CLASS_STATUS = {"FA_AR": "pass", "AAM": "warning", "AM": "warning",
                 "PROHIBITED": "fail"}

_ESCALATION = {
    "FA_AR": "none; this is read-only",
    "AAM": "an approval from Pedro naming these exact targets",
    "AM": "Pedro performs this, or explicitly commands it each time",
    "PROHIBITED": "none exists; this must not proceed under any approval",
}


def result_checks(results, policy):
    checks = []
    for n, r in enumerate(results, 1):
        label = r["path"]
        if r["source_path"]:
            label = "%s -> %s" % (r["source_path"], r["path"])
        bits = ["%s: %s" % (why, cls) for why, cls, _reason in r["reasons"]]
        ev = "minimum %s; %s" % (r["minimum_class"], "; ".join(bits))
        if r["findings"]:
            ev += "; findings: %s" % ", ".join(r["findings"])
        checks.append(_chk("C%03d" % n, label,
                           _CLASS_STATUS[r["minimum_class"]], ev))
    return checks


def _emit(doc, fmt):
    norm = ef.normalize(doc)
    text = ef.render_markdown(norm) if fmt == "markdown" else ef.render_json(norm)
    sys.stdout.buffer.write(text.encode("utf-8"))
    sys.stdout.buffer.flush()
    return norm


def _err(text):
    sys.stderr.buffer.write(text.encode("utf-8"))
    sys.stderr.buffer.flush()


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
        _bad("no manifest was supplied")
    try:
        doc = json.loads(raw.decode("utf-8"), parse_constant=_reject_constant)
    except ef.ValidationError:
        raise
    except Exception:
        _bad("the manifest is not valid JSON")
    ef.enforce_limits(doc)
    return doc


def build_parser():
    parser = argparse.ArgumentParser(
        prog="change_classifier",
        description="Report the MINIMUM approval class a change requires. "
                    "Read-only: it never approves, stages, commits, or executes.")
    parser.add_argument("mode", choices=MODES)
    parser.add_argument("--format", choices=("markdown", "json"), required=True)
    parser.add_argument("--repo", default=None, help="path to a git worktree")
    parser.add_argument("--policy", default=None,
                        help="policy JSON (defaults to the sibling change_policy.json)")
    parser.add_argument("--input", default=None, help="manifest JSON; stdin if omitted")
    parser.add_argument("--commit", default=None, help="commit for classify-commit")
    parser.add_argument("--base", default=None, help="base for classify-range")
    parser.add_argument("--head", default=None, help="head for classify-range")
    parser.add_argument("--expected-head", default=None,
                        help="stop unless HEAD is exactly this object id")
    parser.add_argument("--expected-branch", default=None,
                        help="stop unless the branch is exactly this")
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
        _err("change_classifier: safety limit: %s\n" % ef.sanitize_text(str(exc)))
        return 3
    except (PolicyError, ef.ValidationError) as exc:
        _err("change_classifier: invalid policy: %s\n" % ef.sanitize_text(str(exc)))
        return 2

    mode = args.mode
    checks, notes, results = [], [], []
    overall = None
    stopped_reason = None
    declared_op = None

    try:
        if mode == "validate-policy":
            checks = [
                _chk("V1", "policy schema", "pass", "schema_version %d" % SCHEMA_VERSION),
                _chk("V2", "policy identity", "pass",
                     "%s, sha256 %s" % (policy["policy_name"], policy_hash)),
                _chk("V3", "class order", "pass", " < ".join(CLASS_ORDER)),
                _chk("V4", "repository write floor", "pass",
                     "every repository write is at least %s; a write is never FA/AR"
                     % policy["repository_write_floor"]["class"]),
                _chk("V5", "unknown path fallback", "pass",
                     policy["fail_safe"]["unknown_path_class"]),
                _chk("V6", "unknown change kind fallback", "pass",
                     policy["fail_safe"]["unknown_change_kind_class"]),
                _chk("V7", "deletion floor", "pass",
                     "a deletion is never below a modification"),
                _chk("V8", "binary handling", "pass",
                     "at least %s, and %s in a sensitive area"
                     % (policy["binary"]["minimum_class"],
                        policy["binary"]["sensitive_area_class"])),
                _chk("V9", "submodule handling", "pass", policy["submodule"]["class"]),
                _chk("V10", "path rules", "pass",
                     "%d rule(s): %s" % (len(policy["path_rules"]),
                                         ", ".join(r["id"] for r in policy["path_rules"]))),
                _chk("V11", "declared operations", "pass",
                     "%d operation(s)" % len(policy["declared_operations"])),
                _chk("V12", "semantic indicators", "pass",
                     "%d declared, %d implemented, identical sets"
                     % (len(policy["semantic_indicators"]), len(INDICATOR_IDS))),
                _chk("V13", "semantic scanning limits", "pass",
                     "defence in depth; it can raise a class and cannot prove the "
                     "absence of dangerous behaviour"),
                _chk("V14", "ignored files", "pass",
                     "never enter git classification; manifest only"),
                _chk("V15", "historical presence", "pass",
                     "being tracked already authorizes nothing"),
                _chk("V16", "approval", "pass",
                     "this tool reports a minimum required class and never approves"),
            ]
            for key in sorted(LIMIT_MAXIMUMS):
                checks.append(_chk("V17.%s" % key, "limit %s" % key, "pass",
                                   "policy %d, implementation maximum %d"
                                   % (limits[key], LIMIT_MAXIMUMS[key])))
            overall = "FA_AR"
        else:
            changes = []
            if mode == "classify-manifest":
                declared_op, changes, notes = validate_manifest(
                    _read_input(args.input, limits), policy, limits)
                repo = None
                for c in changes:
                    results.append(classify_change(
                        c, policy, limits, content=None,
                        declared_findings=c.get("declared_findings", ())))
            else:
                if not args.repo:
                    _bad("%s requires --repo" % mode)
                repo, identity = sg.resolve_repo(args.repo)
                bchecks, bstopped, head = baseline_checks(
                    repo, identity, args.expected_head, args.expected_branch)
                checks.extend(bchecks)
                rchecks, rstopped = registry_checks(
                    args.registry, args.session_id, identity, head)
                checks.extend(rchecks)
                if bstopped or rstopped:
                    raise sg.StoppedError("the observation baseline is not usable")

                if mode == "classify-worktree":
                    changes = observe_worktree(repo, limits)
                elif mode == "classify-staged":
                    changes = observe_staged(repo, limits)
                elif mode == "classify-commit":
                    if not args.commit:
                        _bad("classify-commit requires --commit")
                    changes = observe_commit(
                        repo, resolve_oid(repo, args.commit, "--commit"), limits)
                else:
                    if not args.base or not args.head:
                        _bad("classify-range requires --base and --head")
                    changes = observe_range(
                        repo, resolve_oid(repo, args.base, "--base"),
                        resolve_oid(repo, args.head, "--head"), limits)

                head_after = _git_ok(repo, ["rev-parse", "HEAD"]).strip()
                if head_after != head:
                    raise sg.StoppedError("HEAD moved during observation")

                for c in changes:
                    status, content = new_side_bytes(repo, c, limits)
                    results.append(classify_change(c, policy, limits, content=content,
                                                   content_status=status))

            if not changes:
                checks.append(_chk("C00", "change set", "stopped",
                                   "no change was observed; there is nothing to "
                                   "classify and nothing is approved"))
                stopped_reason = "no change observed"
            else:
                op_class = None
                if declared_op:
                    spec = policy["declared_operations"][declared_op]
                    op_class = spec["class"]
                    checks.append(_chk("O1", "declared operation", "pass",
                                       "%s: minimum %s -- %s"
                                       % (declared_op, op_class, spec["reason"])))
                overall = most_restrictive(op_class,
                                           *[r["minimum_class"] for r in results])
                counts = {c: 0 for c in CLASS_ORDER}
                for r in results:
                    counts[r["minimum_class"]] += 1
                checks.append(_chk("C0", "change set", "pass",
                                   "%d path(s); %s" % (len(results), "; ".join(
                                       "%s=%d" % (c, counts[c]) for c in CLASS_ORDER))))
                checks.extend(result_checks(results, policy))
                checks.append(_chk("R1", "minimum required class",
                                   _CLASS_STATUS[overall],
                                   "%s -- %s" % (overall, _ESCALATION[overall])))
                checks.append(_chk("R2", "authorization", "pass",
                                   "this is a minimum requirement, not an approval; "
                                   "nothing here authorizes the change"))
                notes.append(policy["semantic_scanning_note"])
    except ef.SafetyLimitError as exc:
        _err("change_classifier: safety limit: %s\n" % ef.sanitize_text(str(exc)))
        return 3
    except ef.ValidationError as exc:
        _err("change_classifier: invalid input: %s\n" % ef.sanitize_text(str(exc)))
        return 2
    except sg.StoppedError as exc:
        checks.append(_chk("Z0", "observation", "stopped", ef.sanitize_text(str(exc))))
        stopped_reason = ef.sanitize_text(str(exc))
        overall = None

    doc = {
        "schema_version": ef.SCHEMA_VERSION,
        "phase": "change classification",
        "scope": "read-only; reports the minimum approval class and never approves",
        "checks": checks,
    }
    if notes:
        doc["notes"] = notes
    try:
        _emit(doc, args.format)
    except (ef.ValidationError, ef.SafetyLimitError) as exc:
        _err("change_classifier: %s\n" % ef.sanitize_text(str(exc)))
        return 2

    if stopped_reason is not None or overall is None:
        return 4
    return EXIT_BY_CLASS[overall]


if __name__ == "__main__":
    sys.exit(main())
