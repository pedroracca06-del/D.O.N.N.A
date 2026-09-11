#!/usr/bin/env python
"""test_selector.py -- read-only changed-path test selector.

Answers one question: *given these changed paths, which tests are worth running
first for fast local feedback?*

THE GOVERNING RULE. A focused selection is a fast local feedback aid ONLY. It can
never:
  * satisfy A7.7 by itself
  * replace collection parity
  * replace the full regression suite required before a commit
  * claim that the unselected tests would pass
  * authorize staging, committing, pushing, merging, or deployment

Every report therefore carries `full_regression_required: true` and
`collection_parity_required: true`, unconditionally. No policy field, flag, or
input can set either to false, and validation refuses a policy that tries.

An unmappable or ambiguous changed path escalates to a full-suite-required result.
It never silently produces an empty or narrow selection. "No focused test" never
means "no testing required".

DYNAMIC TESTS ARE INCLUDED, NOT AN EXCUSE TO GIVE UP. A test file whose own import
behaviour cannot be known by reading is added to EVERY focused selection instead of
collapsing the whole repository to the full suite. That is the conservative reading:
the selection can only get broader, never narrower, and one such test file no longer
makes focused feedback impossible for every other change. The inclusion is a safety
net, not a mapping -- it is reported with its own mapping source so no one mistakes
it for proof that the test depends on the change.

The concession is strictly test-side. A CHANGED SOURCE file whose own imports cannot
be resolved still escalates, because there the unknown is dependency discovery
itself: tests that should have been selected may be invisible. A source-side
ambiguity is never converted into an always-include shortcut.

IT NEVER IMPORTS OR RUNS ANYTHING. It does not import an application or test
module, and it does not invoke pytest -- not even `--collect-only`, which imports
every test module and every conftest and would execute their module-level code.
Mapping is built by parsing tracked blobs with `ast` alone. The proposed
invocation is emitted as a structured argument array, as evidence, and is never
executed. The selector owns no subprocess: its only Git access is through the A7
battery's existing read-only allowlist.

Exit codes:
  0  a focused selection was produced with no ambiguity (a documentation-only
     result may exit 0 only while clearly reporting that there is no focused
     target and that full regression and collection parity are still required)
  2  invalid input, policy, or usage
  3  safety-limit rejection
  4  stopped: zero changed paths, or safe observation was impossible
  5  full-suite escalation required (ambiguity, an unmapped path, or a
     global-impact path)
"""
from __future__ import annotations

import argparse
import ast
import fnmatch
import hashlib
import json
import os
import posixpath
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import evidence_formatter as ef       # noqa: E402
import staleness_guard as sg          # noqa: E402
import session_registry as sr         # noqa: E402
import a7_battery as a7               # noqa: E402  (its read-only git allowlist)
import change_classifier as cc        # noqa: E402  (its changed-path observation)

sys.path.pop(0)

SCHEMA_VERSION = 1
POLICY_FILENAME = "test_selection_policy.json"

MODES = ("select-worktree", "select-staged", "select-commit", "select-range",
         "select-manifest", "validate-policy")

EXIT_OK = 0
EXIT_INVALID = 2
EXIT_LIMIT = 3
EXIT_STOPPED = 4
EXIT_FULL_SUITE = 5

# Implementation maximums. A policy may lower any of these; it can never raise one.
MAX_INPUT_BYTES = 1024 * 1024
MAX_CHANGES = 1000
MAX_FILES_SCANNED = 5000
MAX_FILE_BYTES = 512 * 1024
MAX_DEPTH = 32
MAX_PATH_CHARS = 512
MAX_SELECTED = 2000

LIMIT_MAXIMUMS = {
    "max_input_bytes": MAX_INPUT_BYTES,
    "max_changes": MAX_CHANGES,
    "max_files_scanned": MAX_FILES_SCANNED,
    "max_file_bytes": MAX_FILE_BYTES,
    "max_depth": MAX_DEPTH,
    "max_path_chars": MAX_PATH_CHARS,
    "max_selected": MAX_SELECTED,
}

# The only argument tokens a policy template may contain. Arbitrary pytest flags,
# plugin arguments, environment assignments, and shell fragments are refused.
ALLOWED_ARGUMENT_TOKENS = frozenset({"python", "-B", "-m", "pytest", "-q"})

# How a test came to be selected.
SOURCE_SELF = "self"
SOURCE_DIRECT = "direct import"
SOURCE_TRANSITIVE = "transitive import"
SOURCE_CONFTEST = "conftest scope"
SOURCE_POLICY = "explicit policy"
SOURCE_DYNAMIC = "dynamic-test safety inclusion"
SOURCE_GLOBAL = "global fallback"

# Ordered strongest-first. A test that has a real mapping keeps it; the safety
# inclusion is only ever the label of last resort before the global fallback.
MAPPING_SOURCES = (SOURCE_SELF, SOURCE_DIRECT, SOURCE_TRANSITIVE, SOURCE_CONFTEST,
                   SOURCE_POLICY, SOURCE_DYNAMIC, SOURCE_GLOBAL)

_MACHINE_PATH_RE = re.compile(
    r"([A-Za-z]:[\\/]|\\\\[A-Za-z0-9._-]+\\|/(?:home|Users)/[A-Za-z0-9._-]+|"
    r"/mnt/[a-z]/|%USERPROFILE%|\$HOME\b|~[/\\][A-Za-z])")

_UNSAFE_INPUT_RE = re.compile(
    r"(?i)(\$\(|`|&&|\|\||;\s*\w+\s|(?<![.\w*])(sudo|curl|wget|bash|eval|exec|"
    r"powershell|importlib|__import__)\b|(?<![.\w*])sh\s+-c\b|<script|javascript:|"
    r"https?://|ssh://|git@|api[_-]?key\s*[:=]|secret\s*[:=]|token\s*[:=]|"
    r"password\s*[:=]|sk-ant-|ghp_|AKIA[0-9A-Z]{16}|-----BEGIN|^[A-Z_]{3,}=)")

# Names that make a module's import set unknowable by static reading. Matched as
# AST identifiers and attribute names -- these are data strings here, never called.
_DYNAMIC_IMPORT_NAMES = ("__import__", "importlib", "import_module", "exec", "eval",
                         "load_module", "SourceFileLoader", "pkgutil", "runpy",
                         "spec_from_file_location", "module_from_spec",
                         "exec_module", "find_module")
# `compile` is deliberately absent: `re.compile` is not code loading, and matching
# it would mark most of the repository dynamic. The `exec(compile(...))` shape is
# already caught by `exec`.

# Mutating the interpreter search path only defeats static reading when it leaves an
# import that cannot be tied to a tracked file. The Cowork tools mutate the path and
# then import a sibling by bare name, which the tracked-basename fallback resolves
# exactly; treating that as unknowable would make almost every file dynamic and
# would destroy the very usefulness this selector exists for.
_PATH_MUTATION_METHODS = ("insert", "append", "extend", "remove", "pop", "clear")

# A credential-shaped value anywhere in the policy, which is data only.
_CREDENTIAL_RE = re.compile(
    r"(?i)(\b[a-z0-9_.-]*(api[_-]?key|secret|token|password|passphrase|bearer|"
    r"private[_-]?key|access[_-]?key)[a-z0-9_.-]*\s*[:=]\s*[\"']?[A-Za-z0-9/+_.-]{12,}"
    r"|sk-ant-[A-Za-z0-9_-]{8,}|ghp_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}"
    r"|-----BEGIN [A-Z ]*PRIVATE KEY-----)")


class PolicyError(Exception):
    """The policy file is missing or unusable -> exit 2."""


def _bad(msg):
    raise ef.ValidationError(msg)


def _reject_constant(_name):
    raise ef.ValidationError("non-standard numeric value is not permitted")


# --------------------------------------------------------------------------
# Policy
# --------------------------------------------------------------------------

POLICY_REQUIRED = (
    "schema_version", "policy_name", "contract", "collection_count_history",
    "test_roots", "source_roots", "test_file_patterns", "conftest_filename",
    "python_suffixes", "explicit_mappings", "global_impact_paths",
    "documentation_only_paths", "exclusions", "full_suite_arguments",
    "focused_arguments_prefix", "focused_arguments_suffix", "limits",
)
POLICY_OPTIONAL = ("description",)

# Contract fields whose values are fixed. A policy that disagrees is refused.
CONTRACT_FIXED = {
    "focused_selection_is_advisory_only": True,
    "full_regression_required": True,
    "collection_parity_required": True,
    "can_satisfy_a7_7": False,
    "can_replace_collection_parity": False,
    "can_replace_full_regression": False,
    "claims_unselected_tests_pass": False,
    "authorizes_staging_or_commit": False,
    "unmappable_path_escalates_to_full_suite": True,
    "selector_invokes_collection": False,
    "selector_imports_modules": False,
    "dynamic_test_safety_inclusion_enabled": True,
    "source_side_dynamic_ambiguity_escalates": True,
    "dynamic_tests_can_be_excluded": False,
    "policy_can_downgrade_an_escalation": False,
}

_POLICY_EXECUTABLE_RE = re.compile(
    r"(?i)(\$\(|`|&&|\|\||<script|javascript:|https?://|ssh://|git@|"
    r"(?<![.\w*])(sudo|curl|wget|bash|eval|exec)\b|(?<![.\w*])sh\s+-c\b)")

_TOO_BROAD = {"**", "*", "/**", "./**", ".", "./", "*/**", "**/*"}
_UNSAFE_GLOB_RE = re.compile(r"\*\*\*|\[[^\]]*$|\{|\}|\!\[")


def load_policy(path=None):
    p = path or os.path.join(os.path.dirname(os.path.abspath(__file__)), POLICY_FILENAME)
    try:
        raw = open(p, "rb").read()
    except OSError:
        raise PolicyError("the test selection policy file could not be read")
    if len(raw) > MAX_INPUT_BYTES:
        raise ef.SafetyLimitError("the policy file exceeds the maximum input size")
    try:
        policy = json.loads(raw.decode("utf-8"), parse_constant=_reject_constant)
    except ef.ValidationError:
        raise
    except Exception:
        raise PolicyError("the test selection policy file is not valid JSON")
    if not isinstance(policy, dict):
        raise PolicyError("the test selection policy must be a JSON object")
    if policy.get("schema_version") != SCHEMA_VERSION:
        raise PolicyError("unsupported test selection policy schema")
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
        if _CREDENTIAL_RE.search(node):
            raise PolicyError("the policy contains a credential-shaped value")
        if _MACHINE_PATH_RE.search(node) or node.startswith("\\\\"):
            raise PolicyError("the policy contains a machine-specific path")
        if re.match(r"^[A-Z_]{3,}=", node):
            raise PolicyError("the policy contains an environment assignment")


def _policy_path(value, what, allow_glob=True):
    if not isinstance(value, str) or not value.strip():
        raise PolicyError("%s must be a non-empty string" % what)
    norm = value.replace("\\", "/")
    if norm.startswith("/") or re.match(r"^[A-Za-z]:", norm):
        raise PolicyError("%s must be relative, not absolute" % what)
    if ".." in norm.split("/"):
        raise PolicyError("%s must not contain a parent-directory traversal" % what)
    if len(norm) > MAX_PATH_CHARS:
        raise ef.SafetyLimitError("%s exceeds the maximum path length" % what)
    if _UNSAFE_GLOB_RE.search(norm):
        raise PolicyError("%s uses unsafe glob syntax" % what)
    if not allow_glob and re.search(r"[*?\[]", norm):
        raise PolicyError("%s must be a literal path, not a pattern" % what)
    if norm in _TOO_BROAD:
        raise PolicyError("%s is too broad to be a rule" % what)
    segments = [s for s in norm.split("/") if s and s != "**"]
    if not segments or all(not re.sub(r"[*?\[\]!]", "", s) for s in segments):
        raise PolicyError("%s is too broad; it would match every path" % what)
    return norm.strip("/")


def _check_no_case_dupes(values, what):
    seen = {}
    for v in values:
        folded = v.lower()
        if folded in seen and seen[folded] != v:
            raise PolicyError("%s contains case-conflicting entries" % what)
        if folded in seen:
            raise PolicyError("%s contains duplicate entries" % what)
        seen[folded] = v


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
                "contract %s must be %s; a focused selection is advisory only and "
                "cannot replace collection parity or the full regression suite"
                % (key, json.dumps(want)))

    hist = policy["collection_count_history"]
    if not isinstance(hist, dict) or "snapshots" not in hist or "note" not in hist:
        raise PolicyError("collection_count_history needs a note and snapshots")
    if "re-measured" not in hist["note"] and "re-measure" not in hist["note"]:
        raise PolicyError("collection_count_history note must say collection is "
                          "re-measured, never taken as an expected value")
    for snap in hist["snapshots"]:
        if not isinstance(snap, dict) or "label" not in snap or "count" not in snap:
            raise PolicyError("each collection snapshot needs a label and a count")
        if not isinstance(snap["count"], int) or isinstance(snap["count"], bool):
            raise PolicyError("a collection snapshot count must be an integer")

    for field in ("test_roots", "source_roots", "documentation_only_paths",
                  "global_impact_paths", "exclusions"):
        values = policy[field]
        if not isinstance(values, list) or not values:
            raise PolicyError("%s must be a non-empty list" % field)
        norms = [_policy_path(v, "%s entry" % field) for v in values]
        _check_no_case_dupes(norms, field)

    # A policy must not be able to hide a test file from the dynamic inventory.
    # This refuses the literal form; the runtime inventory refuses the rest by
    # reporting any tracked test file it could not classify, which escalates.
    for pattern in policy["exclusions"]:
        norm = _norm(pattern)
        if is_test_file(norm, policy) or (
                any(_under(r, norm) for r in policy["test_roots"])
                and any(fnmatch.fnmatch(posixpath.basename(norm), pat)
                        for pat in policy["test_file_patterns"])):
            raise PolicyError(
                "exclusions may not name a test file (%s); a dynamic test can never "
                "be excluded from the safety inclusion by policy" % pattern)

    pats = policy["test_file_patterns"]
    if not isinstance(pats, list) or not pats:
        raise PolicyError("test_file_patterns must be a non-empty list")
    for pat in pats:
        if not isinstance(pat, str) or "/" in pat or not pat.strip():
            raise PolicyError("a test file pattern must be a bare filename pattern")
        if _UNSAFE_GLOB_RE.search(pat):
            raise PolicyError("a test file pattern uses unsafe glob syntax")

    if not isinstance(policy["conftest_filename"], str) \
            or policy["conftest_filename"] != "conftest.py":
        raise PolicyError("conftest_filename must be \"conftest.py\"")
    if policy["python_suffixes"] != [".py"]:
        raise PolicyError("python_suffixes must be exactly [\".py\"]")

    mappings = policy["explicit_mappings"]
    if not isinstance(mappings, list):
        raise PolicyError("explicit_mappings must be a list")
    seen_ids, seen_paths = set(), {}
    for m in mappings:
        if not isinstance(m, dict):
            raise PolicyError("each explicit mapping must be a mapping")
        extra = set(m) - {"id", "paths", "tests", "reason"}
        if extra:
            raise PolicyError("explicit mapping has unrecognized field(s): %s"
                              % ", ".join(sorted(extra)))
        mid = m.get("id")
        if not isinstance(mid, str) or not mid.strip():
            raise PolicyError("each explicit mapping needs an id")
        if mid in seen_ids:
            raise PolicyError("duplicate explicit mapping id: %s" % mid)
        seen_ids.add(mid)
        if not isinstance(m.get("reason"), str) or not m["reason"].strip():
            raise PolicyError("explicit mapping %s needs a reason" % mid)
        paths = m.get("paths")
        if not isinstance(paths, list) or not paths:
            raise PolicyError("explicit mapping %s needs at least one path" % mid)
        for p in paths:
            norm = _policy_path(p, "explicit mapping path", allow_glob=False)
            folded = norm.lower()
            if folded in seen_paths and seen_paths[folded] != mid:
                raise PolicyError("path %r is mapped by two rules (%s and %s)"
                                  % (p, seen_paths[folded], mid))
            seen_paths[folded] = mid
        tests = m.get("tests")
        if not isinstance(tests, list):
            raise PolicyError("explicit mapping %s needs a tests list" % mid)
        for t in tests:
            norm = _policy_path(t, "explicit mapping test", allow_glob=False)
            if not any(norm == r or norm.startswith(r + "/")
                       for r in policy["test_roots"]):
                raise PolicyError("explicit mapping %s names a test outside every "
                                  "declared test root" % mid)

    for field in ("full_suite_arguments", "focused_arguments_prefix",
                  "focused_arguments_suffix"):
        args = policy[field]
        if not isinstance(args, list):
            raise PolicyError("%s must be a list" % field)
        for token in args:
            if not isinstance(token, str):
                raise PolicyError("%s entries must be strings" % field)
            if token not in ALLOWED_ARGUMENT_TOKENS:
                raise PolicyError(
                    "%s contains %r, which is not one of the fixed allowed argument "
                    "tokens; arbitrary pytest flags, plugin arguments, environment "
                    "assignments, and shell fragments are refused" % (field, token))
    if policy["full_suite_arguments"][:4] != ["python", "-B", "-m", "pytest"]:
        raise PolicyError("full_suite_arguments must begin with python -B -m pytest")
    if policy["focused_arguments_prefix"] != ["python", "-B", "-m", "pytest"]:
        raise PolicyError("focused_arguments_prefix must be python -B -m pytest")

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
    return fnmatch.fnmatch(p, pat) or fnmatch.fnmatch(posixpath.basename(p), pat)


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


def is_test_file(path, policy):
    name = posixpath.basename(_norm(path))
    if not any(_under(r, path) for r in policy["test_roots"]):
        return False
    if name == policy["conftest_filename"]:
        return False
    return any(fnmatch.fnmatch(name, pat) for pat in policy["test_file_patterns"])


def is_conftest(path, policy):
    return posixpath.basename(_norm(path)) == policy["conftest_filename"]


def is_excluded(path, policy):
    return any(_matches(path, pat) for pat in policy["exclusions"])


def is_documentation_only(path, policy):
    return any(_matches(path, pat) for pat in policy["documentation_only_paths"])


def is_global_impact(path, policy):
    return any(_matches(path, pat) for pat in policy["global_impact_paths"])


def is_python(path, policy):
    return any(_norm(path).endswith(s) for s in policy["python_suffixes"])


def internal_top_levels(policy, tracked):
    """Top-level names that look like this repository's own packages or modules."""
    names = set()
    for root in list(policy["source_roots"]) + list(policy["test_roots"]):
        head = _norm(root).split("/")[0]
        if head and not re.search(r"[*?\[]", head):
            names.add(head[:-3] if head.endswith(".py") else head)
    for path in tracked:
        parts = _norm(path).split("/")
        if len(parts) == 1 and parts[0].endswith(".py"):
            names.add(parts[0][:-3])
        elif len(parts) > 1:
            names.add(parts[0])
    return names


# --------------------------------------------------------------------------
# Static import graph. Nothing is imported; only blobs are parsed.
# --------------------------------------------------------------------------

class Graph:
    __slots__ = ("imports", "unresolved", "dynamic", "unparseable", "files",
                 "internal", "path_mutation", "absent")

    def __init__(self):
        self.imports = {}        # path -> set(path)
        self.unresolved = {}     # path -> set(module name)
        self.dynamic = set()     # paths whose import set cannot be known statically
        self.unparseable = set()
        self.files = set()
        self.internal = set()
        self.path_mutation = set()   # paths that mutate the interpreter search path
        self.absent = set()          # tracked paths with no blob at the pinned HEAD


def _module_candidates(module, tracked_set, basenames=None):
    """Repository paths a dotted module name could refer to.

    Package-path resolution first. Then, for a single-segment name, a tracked
    basename lookup -- because the Cowork tools are imported by bare module name
    after a `sys.path` insertion, which package paths cannot express. A basename
    matching more than one tracked file is AMBIGUOUS and is reported as such
    rather than guessed at; the caller escalates.

    A false positive here can only make a selection BROADER, never narrower, so
    the fallback cannot cause a dependent test to be omitted.
    """
    base = module.replace(".", "/")
    for candidate in (base + ".py", base + "/__init__.py"):
        if candidate in tracked_set:
            return candidate
    if basenames is not None and "." not in module:
        hits = basenames.get(module)
        if hits and len(hits) == 1:
            return hits[0]
        if hits and len(hits) > 1:
            return _AMBIGUOUS
    return None


class _Ambiguous:
    """Sentinel: a module name matches several tracked files."""

    def __repr__(self):
        return "<ambiguous>"


_AMBIGUOUS = _Ambiguous()


def build_basename_index(tracked_set):
    index = {}
    for path in sorted(tracked_set):
        if path.endswith(".py"):
            stem = posixpath.basename(path)[:-3]
            index.setdefault(stem, []).append(path)
    return index


def _resolve_relative(path, level, module):
    """PEP 328 relative import -> a dotted package path, or None if it escapes."""
    parts = _norm(path).split("/")
    pkg = parts[:-1]                      # the containing directory
    if level > 1:
        if len(pkg) < level - 1:
            return None
        pkg = pkg[:len(pkg) - (level - 1)]
    base = "/".join(pkg)
    if module:
        base = (base + "/" if base else "") + module.replace(".", "/")
    return base.strip("/")


def _dotted_target(node):
    """`sys.path` for an Attribute chain, or None. Reads the AST only."""
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        return ".".join(reversed(parts))
    return None


def _mutates_search_path(node):
    """True if this AST node rebinds or mutates `sys.path`."""
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
            and node.func.attr in _PATH_MUTATION_METHODS:
        return _dotted_target(node.func.value) == "sys.path"
    if isinstance(node, (ast.Assign, ast.AugAssign)):
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        for target in targets:
            base = target.value if isinstance(target, ast.Subscript) else target
            if _dotted_target(base) == "sys.path":
                return True
    return False


def parse_module(path, text, tracked_set, internal, graph, basenames):
    """Record one file's static import edges. Never imports, never executes."""
    graph.files.add(path)
    edges, unresolved = set(), set()
    try:
        tree = ast.parse(text)
    except SyntaxError:
        graph.unparseable.add(path)
        graph.imports[path] = edges
        graph.unresolved[path] = unresolved
        return

    for node in ast.walk(tree):
        if _mutates_search_path(node):
            graph.path_mutation.add(path)
        # A dynamic import makes this file's import set unknowable by reading.
        if isinstance(node, ast.Name) and node.id in _DYNAMIC_IMPORT_NAMES:
            graph.dynamic.add(path)
        elif isinstance(node, ast.Attribute) and node.attr in _DYNAMIC_IMPORT_NAMES:
            graph.dynamic.add(path)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in _DYNAMIC_IMPORT_NAMES:
                    graph.dynamic.add(path)
                _add_edge(alias.name, tracked_set, internal, edges, unresolved,
                          basenames)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = _resolve_relative(path, node.level, node.module or "")
                if base is None:
                    unresolved.add("." * node.level + (node.module or ""))
                    continue
                target = _module_candidates(base.replace("/", "."), tracked_set,
                                            basenames)
                if target is _AMBIGUOUS:
                    unresolved.add(base.replace("/", "."))
                elif target:
                    edges.add(target)
                else:
                    # `from . import name` -- try each imported name as a submodule.
                    hit = False
                    for alias in node.names:
                        if alias.name == "*":
                            continue
                        sub = _module_candidates(
                            (base + "/" + alias.name).replace("/", "."), tracked_set,
                            basenames)
                        if sub is _AMBIGUOUS:
                            unresolved.add(alias.name)
                            hit = True
                        elif sub:
                            edges.add(sub)
                            hit = True
                    if not hit:
                        unresolved.add("." * node.level + (node.module or ""))
            else:
                name = node.module or ""
                if name.split(".")[0] in _DYNAMIC_IMPORT_NAMES:
                    graph.dynamic.add(path)
                resolved = _add_edge(name, tracked_set, internal, edges,
                                     unresolved, basenames)
                if resolved is None and any(a.name == "*" for a in node.names):
                    # A star import from a module we cannot resolve: what it brings
                    # in is unknowable, so this file is treated as dynamic.
                    graph.dynamic.add(path)
                elif resolved is None:
                    for alias in node.names:
                        sub = _module_candidates(
                            "%s.%s" % (name, alias.name) if name else alias.name,
                            tracked_set, basenames)
                        if sub is _AMBIGUOUS:
                            unresolved.add(alias.name)
                        elif sub:
                            edges.add(sub)

    # A search-path mutation is only unknowable when it actually leaves an import
    # this reader could not tie to a tracked file.
    if path in graph.path_mutation and unresolved:
        graph.dynamic.add(path)

    graph.imports[path] = edges
    graph.unresolved[path] = unresolved


def _add_edge(module, tracked_set, internal, edges, unresolved, basenames=None):
    if not module:
        return None
    target = _module_candidates(module, tracked_set, basenames)
    if target is _AMBIGUOUS:
        unresolved.add(module)
        return None
    if target:
        edges.add(target)
        return target
    # Only a name that LOOKS internal but cannot be found is a problem. An
    # external package (json, pytest, fastapi) is simply not a repository edge.
    if module.split(".")[0] in internal:
        unresolved.add(module)
    return None


def tracked_files(repo):
    """Tracked repository-relative paths, through the A7 read-only allowlist."""
    out = a7._git_ok(repo, ["ls-files", "-z"])
    return sorted(_norm(p) for p in out.split("\0") if p)


def build_graph(repo, policy, limits, read_blob):
    """Parse every tracked Python file at the pinned baseline."""
    graph = Graph()
    tracked_set = set(tracked_files(repo))
    graph.internal = internal_top_levels(policy, tracked_set)
    basenames = build_basename_index(tracked_set)

    scanned = 0
    for path in sorted(tracked_set):
        if not is_python(path, policy) or is_excluded(path, policy):
            continue
        scanned += 1
        if scanned > limits["max_files_scanned"]:
            raise ef.SafetyLimitError("the repository holds more Python files than "
                                      "the scan maximum")
        raw = read_blob(path, limits)
        if raw is None:
            # Tracked but with no blob at the pinned HEAD: a staged addition or
            # rename destination. It is unreadable here, but it is not a file whose
            # content defeated the parser, and the two are not the same finding.
            graph.absent.add(path)
            graph.unparseable.add(path)
            graph.files.add(path)
            graph.imports[path] = set()
            graph.unresolved[path] = set()
            continue
        parse_module(path, raw.decode("utf-8", "replace"), tracked_set,
                     graph.internal, graph, basenames)
    return graph, tracked_set


def dependency_closure(graph, start, limits):
    """Every repository file `start` reaches through imports, transitively."""
    seen, stack, depth_guard = set(), [start], 0
    while stack:
        current = stack.pop()
        for target in graph.imports.get(current, ()):
            if target not in seen:
                seen.add(target)
                stack.append(target)
        depth_guard += 1
        if depth_guard > limits["max_files_scanned"] * 4:
            raise ef.SafetyLimitError("the import graph traversal exceeded its bound")
    return seen


def build_reverse_index(graph, policy, limits):
    """{source path -> {test path: 'direct import' | 'transitive import'}}."""
    index = {}
    for path in sorted(graph.files):
        if not is_test_file(path, policy):
            continue
        direct = graph.imports.get(path, set())
        for target in dependency_closure(graph, path, limits):
            kind = SOURCE_DIRECT if target in direct else SOURCE_TRANSITIVE
            slot = index.setdefault(target, {})
            # A direct edge is never downgraded to transitive.
            if slot.get(path) != SOURCE_DIRECT:
                slot[path] = kind
    return index


# --------------------------------------------------------------------------
# Selection
# --------------------------------------------------------------------------

class Selection:
    def __init__(self):
        self.selected = {}        # test path -> (mapping source, reason)
        self.escalations = []     # (path, reason)
        self.unmapped = []        # (path, reason)
        self.documentation = []   # paths
        self.observed = []        # change dicts

    def add(self, test_path, source, reason):
        current = self.selected.get(test_path)
        if current is None or MAPPING_SOURCES.index(source) < MAPPING_SOURCES.index(current[0]):
            self.selected[test_path] = (source, reason)

    def escalate(self, path, reason):
        self.escalations.append((path, reason))


def conftest_subtree_tests(conftest_path, graph, policy):
    directory = posixpath.dirname(_norm(conftest_path))
    return sorted(p for p in graph.files
                  if is_test_file(p, policy)
                  and (not directory or _under(directory, p)))


def select_for_path(path, kind, graph, index, policy, selection, tracked_set):
    """Classify one changed path into a selection, an escalation, or a doc note."""
    path = _norm(path)

    if is_excluded(path, policy):
        return

    if is_global_impact(path, policy):
        selection.escalate(path, "a global-impact path requires the full suite")
        return

    for mapping in policy["explicit_mappings"]:
        if path in [_norm(p) for p in mapping["paths"]]:
            if not mapping["tests"]:
                selection.escalate(
                    path, "explicit policy mapping %s declares no focused target: %s"
                    % (mapping["id"], mapping["reason"]))
                return
            for t in mapping["tests"]:
                selection.add(_norm(t), SOURCE_POLICY,
                              "explicit policy mapping %s: %s"
                              % (mapping["id"], mapping["reason"]))
            return

    if is_conftest(path, policy):
        subtree = conftest_subtree_tests(path, graph, policy)
        if not subtree:
            selection.escalate(path, "a conftest with no discoverable subtree tests")
            return
        for t in subtree:
            selection.add(t, SOURCE_CONFTEST,
                          "changed conftest at %s covers this subtree" % path)
        return

    if is_test_file(path, policy):
        if path in tracked_set or kind != "delete":
            selection.add(path, SOURCE_SELF, "the changed test selects itself")
        else:
            selection.escalate(path, "a deleted test file cannot select itself")
        return

    if is_python(path, policy):
        if path in graph.unparseable:
            selection.escalate(path, "the changed Python file could not be parsed")
            return
        if path not in tracked_set and kind not in ("delete", "rename"):
            selection.escalate(path, "an untracked Python file has no baseline "
                                     "import graph")
            return
        dependents = index.get(path)
        if not dependents:
            selection.escalate(
                path, "no statically discovered test imports this module")
            return
        for test_path, source in sorted(dependents.items()):
            selection.add(test_path, source,
                          "%s reaches %s by %s" % (test_path, path, source))
        return

    if is_documentation_only(path, policy):
        selection.documentation.append(path)
        return

    selection.escalate(path, "the path is not mapped by any rule")


def dynamic_test_inventory(graph, policy, tracked_set, changed_paths=()):
    """The deterministic always-include set, plus any gap that blocks completing it.

    Returns `(dynamic_tests, incomplete)`.

    `dynamic_tests` is a sorted list of tracked TEST files whose own import
    behaviour cannot be known by reading them: `import_module`, `__import__`, a
    compile-and-run construct, a loader or finder call, a dynamically constructed
    module name, an unresolvable star import, or a search-path mutation that leaves
    an import unresolved. Every finding comes from the AST of a tracked blob. No
    file here is imported, executed, or opened for its side effects, and hostile
    module-level code in one of them is never run by this tool.

    `incomplete` lists `(path, reason)` for every tracked test file whose dynamic
    status could NOT be determined -- excluded from the scan, never parsed, or
    unparseable. If it is non-empty the inventory cannot be completed and the
    caller escalates to the full suite rather than shipping a partial safety net.

    One case is deliberately not a gap: a tracked test file with no blob at the
    pinned HEAD that is itself one of the observed changes. It is a staged addition
    or a rename destination, so there is nothing at the baseline to classify, and it
    is already selected on its own account. A baseline-absent test file that is NOT
    among the observed changes is still a gap.
    """
    changed = {_norm(p) for p in changed_paths}
    dynamic_tests, incomplete = [], []
    for path in sorted(tracked_set):
        if not is_test_file(path, policy):
            continue
        if is_excluded(path, policy):
            incomplete.append((path, "a tracked test file is excluded from the "
                                     "static scan, so its dynamic status is unknown"))
        elif path not in graph.files:
            incomplete.append((path, "a tracked test file was never parsed at the "
                                     "baseline, so its dynamic status is unknown"))
        elif path in graph.absent:
            if path not in changed:
                incomplete.append(
                    (path, "a tracked test file has no content at the pinned HEAD "
                           "and is not among the observed changes, so its dynamic "
                           "status is unknown"))
        elif path in graph.unparseable:
            incomplete.append((path, "a tracked test file could not be parsed, so "
                                     "its dynamic status is unknown"))
        elif path in graph.dynamic:
            dynamic_tests.append(path)
    return dynamic_tests, incomplete


def dynamic_inclusion_reason(path, graph):
    """Why one dynamic test joins every focused selection. Evidence, not a mapping."""
    why = "unresolved star import or dynamic import indirection"
    if path in graph.path_mutation and graph.unresolved.get(path):
        why = "search-path mutation leaving %d unresolved import name(s)" \
              % len(graph.unresolved[path])
    return ("its import set cannot be known by static reading (%s), so it is "
            "included conservatively rather than allowing it to force every "
            "selection to the full suite; this is a safety net, not evidence that "
            "the test depends on the change" % why)


def verify_no_dependent_omitted(selected, changed_python, index):
    """Independent recomputation of the closure property.

    For every changed Python module, every statically discovered test that imports
    it -- directly or transitively -- must be in the selection. This is recomputed
    from the reverse index rather than from the selection loop, so a bug in the
    loop cannot hide behind itself.
    """
    missing = []
    for path in sorted(changed_python):
        for test_path in sorted(index.get(path, {})):
            if test_path not in selected:
                missing.append((path, test_path))
    return missing


# --------------------------------------------------------------------------
# Manifest mode
# --------------------------------------------------------------------------

MANIFEST_REQUIRED = ("schema_version",)
MANIFEST_OPTIONAL = ("changes", "notes")
CHANGE_REQUIRED = ("path", "kind")
CHANGE_OPTIONAL = ("source_path", "binary")


def _scan_manifest(node, depth=0):
    if depth > MAX_DEPTH:
        raise ef.SafetyLimitError("the manifest nests deeper than the maximum depth")
    if isinstance(node, dict):
        for k, v in node.items():
            _scan_manifest(k, depth + 1)
            _scan_manifest(v, depth + 1)
    elif isinstance(node, list):
        for v in node:
            _scan_manifest(v, depth + 1)
    elif isinstance(node, str):
        if _UNSAFE_INPUT_RE.search(node):
            _bad("the manifest contains a command, flag, environment value, "
                 "credential, or URL and was rejected")


def validate_manifest(doc, limits):
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
    _scan_manifest(doc)

    changes = doc.get("changes", [])
    if not isinstance(changes, list):
        _bad("changes must be a list")
    if len(changes) > limits["max_changes"]:
        raise ef.SafetyLimitError("the manifest holds more changes than the maximum")

    out, seen = [], set()
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
        if not isinstance(kind, str) or kind not in cc.CHANGE_KINDS:
            _bad("change %d has an unrecognized kind" % n)
        source_path = None
        if item.get("source_path") is not None:
            source_path = check_relative(item["source_path"],
                                         "change %d source_path" % n, limits)
        if kind in ("rename", "copy") and source_path is None:
            _bad("change %d is a %s and needs a source_path" % (n, kind))
        if "binary" in item and not isinstance(item["binary"], bool):
            _bad("change %d binary must be a boolean" % n)
        key = (path.lower(), kind)
        if key in seen:
            _bad("change %d duplicates an earlier path and kind" % n)
        seen.add(key)
        out.append({"path": path, "source_path": source_path, "kind": kind,
                    "binary": item.get("binary", False), "origin": "manifest",
                    "old_mode": "100644", "new_mode": "100644",
                    "old_oid": "0" * 40, "new_oid": "0" * 40})

    notes = doc.get("notes", [])
    if not isinstance(notes, list):
        _bad("notes must be a list")
    return sorted(out, key=lambda c: (c["path"].lower(), c["kind"])), notes


# --------------------------------------------------------------------------
# Checks and rendering
# --------------------------------------------------------------------------

def _chk(cid, label, status, evidence):
    return {"id": cid, "label": label, "status": status, "evidence": evidence}


def baseline_checks(repo, identity, expected_head, expected_branch):
    checks, stopped = [], False
    head = a7._git_ok(repo, ["rev-parse", "HEAD"]).strip()
    branch = a7._git_ok(repo, ["rev-parse", "--abbrev-ref", "HEAD"]).strip()
    checks.append(_chk("B1", "worktree", "pass", "resolved as ${REPO} (%s)" % identity))
    checks.append(_chk("B2", "baseline branch", "pass", branch))
    checks.append(_chk("B3", "baseline HEAD", "pass", head))
    if expected_branch:
        ok = branch == expected_branch
        checks.append(_chk("B4", "expected branch", "pass" if ok else "stopped",
                           "expected %s, observed %s" % (expected_branch, branch)))
        stopped = stopped or not ok
    if expected_head:
        base = {"schema_version": sg.SCHEMA_VERSION, "expected_branch": branch,
                "expected_head": expected_head}
        sg.validate_baseline(base)
        ok = head == expected_head
        checks.append(_chk("B5", "expected HEAD", "pass" if ok else "stopped",
                           "expected %s, observed %s" % (expected_head, head)))
        stopped = stopped or not ok
    return checks, stopped, head, branch


def registry_checks(registry_path, session_id, identity, head):
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
        prog="test_selector",
        description="Propose a focused test selection from changed paths. Read-only: "
                    "it imports nothing, runs nothing, and never replaces the full "
                    "regression suite or collection parity.")
    parser.add_argument("mode", choices=MODES)
    parser.add_argument("--format", choices=("markdown", "json"), required=True)
    parser.add_argument("--repo", default=None, help="path to a git worktree")
    parser.add_argument("--policy", default=None,
                        help="policy JSON (defaults to the sibling "
                             "test_selection_policy.json)")
    parser.add_argument("--input", default=None, help="manifest JSON; stdin if omitted")
    parser.add_argument("--commit", default=None, help="commit for select-commit")
    parser.add_argument("--base", default=None, help="base for select-range")
    parser.add_argument("--head", default=None, help="head for select-range")
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
        return 0 if exc.code == 0 else EXIT_INVALID

    try:
        policy, policy_hash = load_policy(args.policy)
        validate_policy(policy)
        limits = policy["limits"]
    except ef.SafetyLimitError as exc:
        _err("test_selector: safety limit: %s\n" % ef.sanitize_text(str(exc)))
        return EXIT_LIMIT
    except (PolicyError, ef.ValidationError) as exc:
        _err("test_selector: invalid policy: %s\n" % ef.sanitize_text(str(exc)))
        return EXIT_INVALID

    mode = args.mode
    checks, notes = [], []
    exit_code = EXIT_OK

    # These two are constants of the contract, printed on every single report.
    contract_checks = [
        _chk("K1", "full_regression_required", "warning",
             "full_regression_required: true -- always; a focused selection never "
             "replaces the complete regression suite required before a commit"),
        _chk("K2", "collection_parity_required", "warning",
             "collection_parity_required: true -- always; collection must be "
             "re-measured against the current pinned HEAD and compared as exact "
             "node-ID sets"),
        _chk("K3", "A7.7", "warning", "a focused selection is optional preliminary "
             "evidence and never satisfies A7.7 by itself"),
        _chk("K4", "unselected tests", "pass", "no claim is made that unselected "
             "tests would pass; they were simply not chosen for fast feedback"),
        _chk("K5", "authorization", "pass", "this selection authorizes nothing -- "
             "not staging, committing, pushing, merging, or deployment"),
        _chk("K6", "execution", "pass", "no module was imported and pytest was not "
             "invoked, including --collect-only"),
        _chk("K7", "dynamic tests", "pass", "a test file with dynamic imports is "
             "included conservatively and can never be excluded by policy or "
             "manifest; a CHANGED SOURCE file with unresolved dynamic imports "
             "still escalates to the full suite"),
    ]

    try:
        if mode == "validate-policy":
            checks = [
                _chk("V1", "policy schema", "pass", "schema_version %d" % SCHEMA_VERSION),
                _chk("V2", "policy identity", "pass",
                     "%s, sha256 %s" % (policy["policy_name"], policy_hash)),
                _chk("V3", "test roots", "pass", ", ".join(policy["test_roots"])),
                _chk("V4", "source roots", "pass", "%d root(s)" % len(policy["source_roots"])),
                _chk("V5", "explicit mappings", "pass",
                     "%d mapping(s): %s" % (len(policy["explicit_mappings"]),
                                            ", ".join(m["id"] for m in
                                                      policy["explicit_mappings"]))),
                _chk("V6", "global-impact paths", "pass",
                     "%d path(s) force the full suite" % len(policy["global_impact_paths"])),
                _chk("V7", "documentation-only paths", "pass",
                     "%d pattern(s)" % len(policy["documentation_only_paths"])),
                _chk("V8", "argument template", "pass",
                     "fixed tokens only: %s" % " ".join(policy["full_suite_arguments"])),
                _chk("V9", "collection counts", "pass",
                     "historical snapshots only (%s); collection is always "
                     "re-measured and is never invoked by this tool"
                     % ", ".join("%s=%d" % (s["label"], s["count"])
                                 for s in policy["collection_count_history"]["snapshots"])),
            ]
            for key in sorted(CONTRACT_FIXED):
                checks.append(_chk("V10.%s" % key, "contract %s" % key, "pass",
                                   json.dumps(CONTRACT_FIXED[key])))
            for key in sorted(LIMIT_MAXIMUMS):
                checks.append(_chk("V11.%s" % key, "limit %s" % key, "pass",
                                   "policy %d, implementation maximum %d"
                                   % (limits[key], LIMIT_MAXIMUMS[key])))
            checks.extend(contract_checks)
        else:
            changes, repo, tracked_set = [], None, set()
            if mode == "select-manifest":
                if not args.repo:
                    _bad("select-manifest requires --repo to resolve the baseline "
                         "import graph")
                changes, extra_notes = validate_manifest(
                    _read_input(args.input, limits), limits)
                notes.extend(extra_notes)
            if not args.repo:
                _bad("%s requires --repo" % mode)
            repo, identity = sg.resolve_repo(args.repo)
            bchecks, bstopped, head, branch = baseline_checks(
                repo, identity, args.expected_head, args.expected_branch)
            checks.extend(bchecks)
            rchecks, rstopped = registry_checks(
                args.registry, args.session_id, identity, head)
            checks.extend(rchecks)
            if bstopped or rstopped:
                raise sg.StoppedError("the observation baseline is not usable")

            if mode == "select-worktree":
                changes = cc.observe_worktree(repo, limits)
            elif mode == "select-staged":
                changes = cc.observe_staged(repo, limits)
            elif mode == "select-commit":
                if not args.commit:
                    _bad("select-commit requires --commit")
                changes = cc.observe_commit(
                    repo, cc.resolve_oid(repo, args.commit, "--commit"), limits)
            elif mode == "select-range":
                if not args.base or not args.head:
                    _bad("select-range requires --base and --head")
                changes = cc.observe_range(
                    repo, cc.resolve_oid(repo, args.base, "--base"),
                    cc.resolve_oid(repo, args.head, "--head"), limits)

            if len(changes) > limits["max_changes"]:
                raise ef.SafetyLimitError("more changed paths than the maximum")

            def read_blob(path, lim):
                oid = a7._git(repo, ["rev-parse", "HEAD:%s" % path])
                if oid[0] != 0 or not oid[1].strip():
                    return None
                size = a7._git(repo, ["cat-file", "-s", oid[1].strip()])
                if size[0] == 0 and size[1].strip().isdigit() \
                        and int(size[1].strip()) > lim["max_file_bytes"]:
                    return None
                blob = a7._git(repo, ["cat-file", "blob", oid[1].strip()])
                if blob[0] != 0:
                    return None
                return blob[1].encode("utf-8", "surrogateescape")

            graph, tracked_set = build_graph(repo, policy, limits, read_blob)
            index = build_reverse_index(graph, policy, limits)

            head_after = a7._git_ok(repo, ["rev-parse", "HEAD"]).strip()
            if head_after != head:
                raise sg.StoppedError("HEAD moved during observation")

            if not changes:
                checks.append(_chk("C00", "changed paths", "stopped",
                                   "no changed path was observed; there is nothing "
                                   "to select and no testing conclusion is implied"))
                checks.extend(contract_checks)
                raise _Stop(EXIT_STOPPED)

            selection = Selection()
            selection.observed = changes
            changed_python = set()

            # A test file whose imports cannot be read is included in every focused
            # selection instead of collapsing the repository to the full suite. The
            # inventory must be complete for that promise to hold; if any tracked
            # test file could not be classified, escalate instead.
            observed_paths = set()
            for change in changes:
                observed_paths.add(_norm(change["path"]))
                if change.get("source_path"):
                    observed_paths.add(_norm(change["source_path"]))
            dynamic_tests, inventory_gaps = dynamic_test_inventory(
                graph, policy, tracked_set, observed_paths)
            for gap_path, gap_reason in inventory_gaps:
                selection.escalate(
                    gap_path, "the dynamic-test inventory could not be completed: %s"
                    % gap_reason)

            for change in changes:
                if change.get("binary"):
                    selection.escalate(change["path"],
                                       "a binary change cannot be mapped statically")
                    continue
                targets = [(change["path"], change["kind"])]
                if change.get("source_path"):
                    targets.append((change["source_path"], change["kind"]))
                for path, kind in targets:
                    if is_python(path, policy) and not is_excluded(path, policy):
                        changed_python.add(_norm(path))
                        # Source-side ambiguity is NOT covered by the test-side
                        # safety inclusion. If a changed non-test module's own
                        # imports cannot be read, dependency discovery from it is
                        # unknowable and tests that should be selected may be
                        # invisible, so it still escalates.
                        norm = _norm(path)
                        if norm in graph.dynamic and not is_test_file(norm, policy):
                            selection.escalate(
                                path, "the changed source file uses unresolved "
                                      "dynamic imports, so dependency discovery "
                                      "from it cannot be proven complete")
                    select_for_path(path, kind, graph, index, policy, selection,
                                    tracked_set)
                unresolved_here = graph.unresolved.get(_norm(change["path"]), set())
                if unresolved_here:
                    selection.escalate(
                        change["path"],
                        "%d import(s) look internal but resolve to no tracked file"
                        % len(unresolved_here))

            checks.append(_chk("C0", "changed paths", "pass",
                               "%d observed" % len(changes)))
            for n, change in enumerate(sorted(changes,
                                              key=lambda c: c["path"].lower()), 1):
                label = change["path"]
                if change.get("source_path"):
                    label = "%s -> %s" % (change["source_path"], change["path"])
                checks.append(_chk("C%03d" % n, label, "informational",
                                   "kind %s" % change["kind"]))

            missing = verify_no_dependent_omitted(
                set(selection.selected), changed_python, index)
            checks.append(_chk("P1", "closure property",
                               "pass" if not missing else "fail",
                               "every statically discovered test importing a changed "
                               "module is selected"
                               if not missing else
                               "%d dependent test(s) were omitted" % len(missing)))

            full_suite = bool(selection.escalations) or bool(missing)

            # The dynamic-test inventory is evidence on every report, whatever the
            # outcome: how many were detected, exactly which, and why each is added.
            checks.append(_chk(
                "Y0", "dynamic test inventory",
                "pass" if not inventory_gaps else "warning",
                "%d tracked test file(s) use dynamic imports and are included "
                "conservatively in every focused selection; %d tracked test file(s) "
                "could not be classified"
                % (len(dynamic_tests), len(inventory_gaps))))
            for n, dyn_path in enumerate(dynamic_tests, 1):
                checks.append(_chk("Y%03d" % n, ef.sanitize_text(dyn_path),
                                   "informational",
                                   "%s -- %s" % (SOURCE_DYNAMIC,
                                                 dynamic_inclusion_reason(dyn_path,
                                                                          graph))))

            # Conservative inclusion applies to a real focused selection. A
            # documentation-only change still reports NO focused target, so nobody
            # reads a safety net as a test plan for a change that has none.
            ordinary_selected = len(selection.selected)
            if selection.selected and not full_suite:
                for dyn_path in dynamic_tests:
                    selection.add(dyn_path, SOURCE_DYNAMIC,
                                  dynamic_inclusion_reason(dyn_path, graph))
                added = [t for t in dynamic_tests
                         if selection.selected[t][0] == SOURCE_DYNAMIC]
                checks.append(_chk(
                    "Y_ADD", "dynamic safety inclusion", "pass",
                    "%d of %d dynamic test(s) added to a focused selection of %d "
                    "ordinarily mapped test file(s); the remainder were already "
                    "selected by a stronger mapping"
                    % (len(added), len(dynamic_tests), ordinary_selected)))
                checks.append(_chk("S0", "focused selection", "pass",
                                   "%d test file(s)" % len(selection.selected)))
                for n, (test_path, (source, reason)) in enumerate(
                        sorted(selection.selected.items()), 1):
                    checks.append(_chk("S%03d" % n, test_path, "pass",
                                       "%s -- %s" % (source, reason)))
            for n, (path, reason) in enumerate(sorted(selection.escalations), 1):
                checks.append(_chk("E%03d" % n, path, "warning", reason))
            for n, path in enumerate(sorted(selection.documentation), 1):
                checks.append(_chk("D%03d" % n, path, "informational",
                                   "documentation-only; no focused pytest target"))

            if full_suite:
                exit_code = EXIT_FULL_SUITE
                proposed = list(policy["full_suite_arguments"])
                checks.append(_chk("R1", "result", "warning",
                                   "full suite required: %d escalation(s)"
                                   % len(selection.escalations)))
            elif selection.selected:
                targets = sorted(selection.selected)
                if len(targets) > limits["max_selected"]:
                    raise ef.SafetyLimitError("more selected tests than the maximum")
                for t in targets:
                    if not is_test_file(t, policy):
                        raise sg.StoppedError(
                            "a selected target is not a test file by path shape")
                # A rename destination, or a newly added test, is not tracked at
                # the baseline yet. That is expected, not a failure -- the file
                # exists once the change lands. It is reported, not hidden.
                new_targets = [t for t in targets if t not in graph.files]
                if new_targets:
                    checks.append(_chk(
                        "T0", "targets absent from the baseline", "informational",
                        "%d target(s) do not exist at the pinned HEAD and will only "
                        "exist once the change lands: %s"
                        % (len(new_targets), ", ".join(new_targets))))
                proposed = (list(policy["focused_arguments_prefix"]) + targets
                            + list(policy["focused_arguments_suffix"]))
                checks.append(_chk("R1", "result", "pass",
                                   "focused selection of %d test file(s)"
                                   % len(targets)))
            else:
                proposed = []
                checks.append(_chk("R1", "result", "pass",
                                   "documentation-only change: there is NO focused "
                                   "pytest target. This does not mean no testing is "
                                   "required."))

            checks.append(_chk("R2", "proposed invocation", "informational",
                               (" ".join(proposed) if proposed else "(none)")
                               + " -- structured argument array, evidence only, "
                                 "never executed by this tool"))
            checks.append(_chk("R3", "policy", "pass",
                               "%s, sha256 %s" % (policy["policy_name"], policy_hash)))
            checks.extend(contract_checks)
            notes.append("A focused selection is a fast local feedback aid only. "
                         "The complete regression suite and collection-parity "
                         "evidence remain mandatory before any commit.")
    except _Stop as stop:
        exit_code = stop.code
    except ef.SafetyLimitError as exc:
        _err("test_selector: safety limit: %s\n" % ef.sanitize_text(str(exc)))
        return EXIT_LIMIT
    except ef.ValidationError as exc:
        _err("test_selector: invalid input: %s\n" % ef.sanitize_text(str(exc)))
        return EXIT_INVALID
    except sg.StoppedError as exc:
        checks.append(_chk("Z0", "observation", "stopped", ef.sanitize_text(str(exc))))
        checks.extend(contract_checks)
        exit_code = EXIT_STOPPED

    doc = {
        "schema_version": ef.SCHEMA_VERSION,
        "phase": "test selection",
        "scope": "read-only; a focused selection is advisory and never replaces "
                 "full regression or collection parity",
        "checks": checks,
    }
    if notes:
        doc["notes"] = notes
    try:
        _emit(doc, args.format)
    except (ef.ValidationError, ef.SafetyLimitError) as exc:
        _err("test_selector: %s\n" % ef.sanitize_text(str(exc)))
        return EXIT_INVALID
    return exit_code


class _Stop(Exception):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


if __name__ == "__main__":
    sys.exit(main())
