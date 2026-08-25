#!/usr/bin/env python
"""
nova_guard_hook.py -- DISABLED CANDIDATE (Phase 2F). Not installed, not active.

PreToolUse hook protecting NOVA's retired trading subsystem from accidental
modification or re-enablement.

Contract (Claude Code 2.1.239, per official hooks documentation):
  stdin  : JSON object with session_id, cwd, hook_event_name, tool_name,
           tool_input, permission_mode, ...
  stdout : {"hookSpecificOutput": {"hookEventName": "PreToolUse",
            "permissionDecision": "allow"|"deny"|"ask",
            "permissionDecisionReason": "..."}}
  exit 0 : stdout JSON carries the decision; no output = no decision
  exit 2 : blocks whether or not JSON is printed. Claude Code STILL reads valid
           JSON on stdout, and the blocking message is the JSON reason when the
           JSON makes a blocking decision, otherwise the stderr text.

The deny path therefore prints the JSON decision, writes the same short reason
to stderr as a fallback, and exits 2. Both channels are supported, so the block
holds even if the JSON ever fails schema validation.

PRIVACY: this hook never emits command text, file contents, environment values,
or credentials. Block messages name only a protected relative path, a short
construct label, or a guarded flag name.

SCOPE: the project root comes from CLAUDE_PROJECT_DIR (set by Claude Code for
all hook processes) or, failing that, from walking up the hook's cwd. A root
only counts when it carries the NOVA marker directory, so the hook is inert in
unrelated projects even if installed at user scope. Any missing or malformed
project context fails OPEN (no decision), so a schema or environment problem
can never lock every tool call.

Standard library only. Windows-compatible.
"""
from __future__ import annotations

import json
import os
import posixpath
import re
import sys

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

# Directory that identifies the NOVA repository. Without it, the hook is inert.
MARKER_DIR = "nova_knowledge_core"

PROTECTED_RELATIVE = (
    "services/execution.py",
    "services/execution_bridge.py",
    "services/execution_request.py",
    "services/execution_reconcile.py",
    "core/config.py",
    "tests/conftest.py",
)

GUARDED_FLAGS = ("NOVA_TRADING_SUBSYSTEM_ENABLED", "NOVA_AUTO_EXECUTE")

TRUTHY = ("true", "1", "yes", "on", "enabled", "enable")

FILE_EDIT_TOOLS = ("Edit", "Write", "NotebookEdit", "MultiEdit")
SHELL_TOOLS = ("Bash", "PowerShell")

MAX_WALK_UP = 40

# --------------------------------------------------------------------------
# Path normalisation
# --------------------------------------------------------------------------

_DRIVE_POSIX = re.compile(r"^/([A-Za-z])/")
_QUOTES = "\"'`"


def _to_posix(path: str) -> str:
    """Normalise slash direction, quotes, and Git-Bash drive syntax."""
    p = path.strip().strip(_QUOTES).strip()
    p = p.replace("\\", "/")
    # /c/Users/... (Git Bash / MSYS) -> c:/Users/...
    m = _DRIVE_POSIX.match(p)
    if m and p[1:3] != ":/":
        p = m.group(1) + ":/" + p[3:]
    while "//" in p[2:]:
        p = p[:2] + p[2:].replace("//", "/")
    return p


def _is_absolute(p: str) -> bool:
    return bool(re.match(r"^[A-Za-z]:/", p)) or p.startswith("/")


def canonical(path: str, base: str) -> str:
    """Absolute, slash-normalised, case-folded path. Pure string arithmetic."""
    p = _to_posix(path)
    if not _is_absolute(p):
        p = posixpath.join(_to_posix(base), p)
    return posixpath.normpath(p).lower()


# --------------------------------------------------------------------------
# Project-root resolution (no hard-coded repository path)
# --------------------------------------------------------------------------

def _has_marker(root: str) -> bool:
    try:
        return os.path.isdir(posixpath.join(root, MARKER_DIR))
    except OSError:
        return False


def _env_root():
    """CLAUDE_PROJECT_DIR, if it is present, absolute, and a real directory."""
    raw = os.environ.get("CLAUDE_PROJECT_DIR") or ""
    if not isinstance(raw, str):
        return None
    raw = raw.strip().strip(_QUOTES).strip()
    if not raw:
        return None
    p = _to_posix(raw)
    if not _is_absolute(p):
        return None                      # malformed: relative or junk
    p = posixpath.normpath(p).lower()
    try:
        if not os.path.isdir(p):
            return None                  # malformed: points nowhere
    except OSError:
        return None
    return p


def _walk_up_root(cwd: str):
    """Nearest ancestor of cwd carrying the marker directory."""
    if not cwd:
        return None
    p = _to_posix(cwd)
    if not _is_absolute(p):
        return None
    p = posixpath.normpath(p).lower()
    for _ in range(MAX_WALK_UP):
        if _has_marker(p):
            return p
        parent = posixpath.dirname(p)
        if not parent or parent == p:
            return None
        p = parent
    return None


def resolve_root(cwd: str):
    """Project root, or None when project context is missing/unusable."""
    env = _env_root()
    if env and _has_marker(env):
        return env
    # CLAUDE_PROJECT_DIR absent, malformed, or not a NOVA checkout.
    return _walk_up_root(cwd)


def in_scope(cwd: str, root: str) -> bool:
    """True only inside the project root or one of its subdirectories.

    The trailing separator matters: it stops a sibling such as
    ``D.O.N.N.A-copy`` from matching the ``D.O.N.N.A`` prefix.
    """
    if not cwd or not root:
        return False
    c = canonical(cwd, root)
    return c == root or c.startswith(root + "/")


def protected_map(root: str) -> dict:
    return {canonical(posixpath.join(root, rel), root): rel for rel in PROTECTED_RELATIVE}


# --------------------------------------------------------------------------
# Shell command analysis
# --------------------------------------------------------------------------

# Path-shaped tokens: anything ending in a source extension we guard.
_PATH_TOKEN = re.compile(r"[A-Za-z0-9_.:/\\~$()-]*\.py\b", re.I)

# Mutating constructs, keyed by a short label used only for the block message.
_MUTATORS = (
    ("shell redirect",            re.compile(r"(?<![0-9<>])>>?(?!&)", re.I)),
    ("tee",                       re.compile(r"\btee\b", re.I)),
    ("sed in-place",              re.compile(r"\bsed\b[^|;&]*\s-[a-z]*i\b", re.I)),
    ("perl in-place",             re.compile(r"\bperl\b[^|;&]*\s-[a-z]*i\b", re.I)),
    ("patch",                     re.compile(r"\bpatch\b", re.I)),
    ("git apply",                 re.compile(r"\bgit\s+apply\b", re.I)),
    ("git restore",               re.compile(r"\bgit\s+restore\b", re.I)),
    ("git checkout of a path",    re.compile(r"\bgit\s+checkout\b[^|;&]*(--\s|\.py)", re.I)),
    ("git stash/reset of a path", re.compile(r"\bgit\s+(?:stash|reset)\b[^|;&]*\.py", re.I)),
    ("file removal",              re.compile(r"(^|[|;&(\s])(rm|del|unlink|shred)\b", re.I)),
    ("move/copy over target",     re.compile(r"(^|[|;&(\s])(mv|cp|move|copy|install)\b", re.I)),
    ("truncate/dd",               re.compile(r"\b(truncate|dd)\b", re.I)),
    ("python file write",         re.compile(
        r"\bopen\s*\([^)]*['\"][rwax][^'\"]*[wax+]|"
        r"\.write(?:_text|_bytes|lines)?\s*\(|"
        r"\bshutil\.(copy|move|copyfile|copy2)\b|"
        r"\bos\.(remove|unlink|rename|replace|truncate)\b|"
        r"\bpathlib\b[^|;&]*\bwrite", re.I)),
    ("node file write",           re.compile(
        r"\bfs(?:\.promises)?\.(write|append|truncate|unlink|rename|copy|rm)\w*\s*\(|"
        r"\.(writeFile|appendFile|truncate|unlink|rename|copyFile|rm|rmdir|mkdir)"
        r"(?:Sync)?\s*\(", re.I)),
    ("PowerShell content write",  re.compile(
        r"\b(Set-Content|Add-Content|Clear-Content|Out-File|Set-Item|"
        r"Remove-Item|Copy-Item|Move-Item|Rename-Item|New-Item)\b", re.I)),
    ("PowerShell redirect",       re.compile(r"\|\s*Out-File\b", re.I)),
)

# Constructs that are read-only even though they look adjacent to a mutator.
_READ_ONLY_HINTS = re.compile(
    r"\bsed\s+-n\b|\bgit\s+(diff|show|log|status|blame|grep)\b|"
    r"\bpytest\b|\bpython\s+-m\s+pytest\b|\bast\.parse\b|"
    r"\bpy_compile\b|\bdiff\b|\bgrep\b|\brg\b|\bcat\b|\bhead\b|\btail\b",
    re.I,
)


def mentioned_protected(command: str, cwd: str, protected: dict) -> list:
    """Protected relative paths this command names, in any path form."""
    hits = []
    cmd = command or ""
    for tok in _PATH_TOKEN.findall(cmd):
        rel = protected.get(canonical(tok, cwd))
        if rel and rel not in hits:
            hits.append(rel)
    # Also catch quoted paths the token regex splits (spaces in directories).
    for quoted in re.findall(r"[\"']([^\"']+\.py)[\"']", cmd, re.I):
        rel = protected.get(canonical(quoted, cwd))
        if rel and rel not in hits:
            hits.append(rel)
    return hits


def mutating_label(command: str):
    """Short label for the mutating construct present, else None."""
    cmd = command or ""
    for label, rx in _MUTATORS:
        if not rx.search(cmd):
            continue
        # A redirect to /dev/null or NUL is not a mutation of a real target.
        if label == "shell redirect" and re.search(r">>?\s*(/dev/null|NUL)\b", cmd, re.I):
            stripped = re.sub(r">>?\s*(/dev/null|NUL)\b", "", cmd, flags=re.I)
            if not re.search(r"(?<![0-9<>])>>?(?!&)", stripped):
                continue
        return label
    return None


_FLAG_ASSIGN = re.compile(
    r"(?:\$env:)?(" + "|".join(GUARDED_FLAGS) + r")\s*(?:=|\s-value\s+)\s*"
    r"[\"']?([A-Za-z0-9_]+)[\"']?",
    re.I,
)
_FLAG_SETX = re.compile(
    r"\b(?:setx|set)\s+(" + "|".join(GUARDED_FLAGS) + r")\s+[\"']?([A-Za-z0-9_]+)",
    re.I,
)


def guarded_flag_enabled(command: str):
    """Return the flag name if the command sets it to a truthy value, else None."""
    for rx in (_FLAG_ASSIGN, _FLAG_SETX):
        for name, value in rx.findall(command or ""):
            if value.strip().strip(_QUOTES).lower() in TRUTHY:
                return name.upper()
    return None


# --------------------------------------------------------------------------
# Decision
# --------------------------------------------------------------------------

def decide(payload: dict):
    """Return a short reason string to deny, or None to stay silent."""
    tool = payload.get("tool_name") or ""
    ti = payload.get("tool_input") or {}
    if not isinstance(ti, dict):
        return None
    cwd = payload.get("cwd") or ""
    if not isinstance(cwd, str):
        return None

    root = resolve_root(cwd)
    if not root or not in_scope(cwd, root):
        return None                       # fail open: no usable project context

    if tool in FILE_EDIT_TOOLS:
        protected = protected_map(root)
        candidates = []
        for key in ("file_path", "notebook_path", "path"):
            v = ti.get(key)
            if isinstance(v, str):
                candidates.append(v)
        edits = ti.get("edits")
        if isinstance(edits, list):
            for e in edits:
                if isinstance(e, dict) and isinstance(e.get("file_path"), str):
                    candidates.append(e["file_path"])
        for c in candidates:
            rel = protected.get(canonical(c, cwd))
            if rel:
                return ("%s is a guarded file of the retired NOVA trading subsystem "
                        "and must not be modified. Reading it is allowed. See "
                        "nova_knowledge_core/TRADING_SUBSYSTEM_RETIREMENT_AUDIT.md." % rel)
        return None

    if tool in SHELL_TOOLS:
        command = ti.get("command")
        if not isinstance(command, str):
            return None

        flag = guarded_flag_enabled(command)
        if flag:
            return ("This command sets %s to an enabling value. The NOVA trading "
                    "subsystem is retired and must stay disabled." % flag)

        hits = mentioned_protected(command, cwd, protected_map(root))
        if not hits:
            return None
        label = mutating_label(command)
        if not label:
            return None
        if _READ_ONLY_HINTS.search(command) and label in ("move/copy over target", "file removal"):
            return None
        return ("This command would modify %s (%s), a guarded file of the retired "
                "NOVA trading subsystem. Reading, grepping, diffing and running "
                "tests against it are allowed." % (hits[0], label))

    return None


def main() -> int:
    try:
        raw = sys.stdin.read()
    except Exception:
        return 0
    try:
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError
    except Exception:
        # Unparseable input: scope and tool cannot be established, so the hook
        # makes no decision and the normal permission flow applies.
        return 0

    try:
        reason = decide(payload)
    except Exception:
        return 0                          # never lock the session on a hook bug
    if reason is None:
        return 0

    out = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }
    sys.stdout.write(json.dumps(out))
    sys.stdout.flush()
    sys.stderr.write(reason)              # fallback channel; same short text
    sys.stderr.flush()
    return 2


if __name__ == "__main__":
    sys.exit(main())
