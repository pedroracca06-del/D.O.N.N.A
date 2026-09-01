#!/usr/bin/env python
"""
nova_guard_hook.py -- NOVA retirement guard for Claude Code PreToolUse operations.

PreToolUse hook protecting NOVA's retired trading subsystem from accidental
modification or re-enablement.

Rewritten from the ee91955 baseline to fix the Phase 2I findings. The core change
is structural: instead of running mutation regexes against the whole command
string, the command is split into subcommands, `cd`-style directory changes are
tracked across them, and each subcommand is examined for the *destination* it
would write to. A protected path that appears only as a read source, a copy
source, or quoted documentation text is no longer a block.

Contract (Claude Code 2.1.239, per official hooks documentation):
  stdin  : JSON with session_id, cwd, hook_event_name, tool_name, tool_input, ...
  stdout : {"hookSpecificOutput": {"hookEventName": "PreToolUse",
            "permissionDecision": "deny", "permissionDecisionReason": "..."}}
  exit 0 : stdout JSON carries the decision; no output = no decision
  exit 2 : blocks regardless of JSON; Claude Code still reads valid stdout JSON,
           and the blocking message is the JSON reason when present, else stderr.

PROTECTION TIERS
  Tier 1 -- retirement implementation files. No modification by any tool or shell
            command. Reads, greps, diffs, tests, and copy-*from* are allowed.
  Tier 2 -- main.py and monitor.py. Actively developed, so ordinary edits are
            allowed. Blocked only when the edit touches kill-switch text, when the
            whole file would be replaced (Write), or when a shell command would
            mutate the file (a shell command cannot say which lines it changes).

PRIVACY: never emits command text, file contents, environment values, or
credentials. Block messages name only a protected relative path, a short
construct label, or a guarded flag name.

SCOPE: project root from CLAUDE_PROJECT_DIR, else by walking up the hook's cwd.
A root counts only if it carries the NOVA marker directory, so the hook is inert
in unrelated projects. Missing or malformed context fails OPEN.

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

MARKER_DIR = "nova_knowledge_core"

# Tier 1: no modification, by any means.
TIER1_PROTECTED = (
    "services/execution.py",
    "services/execution_bridge.py",
    "services/execution_request.py",
    "services/execution_reconcile.py",
    "core/config.py",
    "tests/conftest.py",
)

# Tier 2: kill-switch protection only; ordinary development is allowed.
TIER2_KILLSWITCH = (
    "main.py",
    "monitor.py",
)

GUARDED_FLAGS = ("NOVA_TRADING_SUBSYSTEM_ENABLED", "NOVA_AUTO_EXECUTE")

# Text whose presence in an Edit's old_string/new_string means the edit is
# touching retirement-guard logic in a Tier 2 file.
GUARD_EXPRESSIONS = GUARDED_FLAGS + (
    "TRADING_SUBSYSTEM_DISABLED",
    "trading_subsystem_enabled",
    "_EXECUTION_AVAILABLE",
)

TRUTHY = ("true", "1", "yes", "on", "enabled", "enable")

FILE_EDIT_TOOLS = ("Edit", "Write", "NotebookEdit", "MultiEdit")
SHELL_TOOLS = ("Bash", "PowerShell")

MAX_WALK_UP = 40

_QUOTES = "\"'`"

# --------------------------------------------------------------------------
# Path normalisation
# --------------------------------------------------------------------------

_DRIVE_POSIX = re.compile(r"^/([A-Za-z])/")


def _to_posix(path: str) -> str:
    """Normalise slash direction, quotes, and Git-Bash drive syntax."""
    p = path.strip().strip(_QUOTES).strip()
    p = p.replace("\\", "/")
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
# Project-root resolution
# --------------------------------------------------------------------------

def _has_marker(root: str) -> bool:
    try:
        return os.path.isdir(posixpath.join(root, MARKER_DIR))
    except OSError:
        return False


def _env_root():
    raw = os.environ.get("CLAUDE_PROJECT_DIR") or ""
    if not isinstance(raw, str):
        return None
    raw = raw.strip().strip(_QUOTES).strip()
    if not raw:
        return None
    p = _to_posix(raw)
    if not _is_absolute(p):
        return None
    p = posixpath.normpath(p).lower()
    try:
        if not os.path.isdir(p):
            return None
    except OSError:
        return None
    return p


def _walk_up_root(cwd: str):
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
    env = _env_root()
    if env and _has_marker(env):
        return env
    return _walk_up_root(cwd)


def in_scope(cwd: str, root: str) -> bool:
    """Inside the root or a subdirectory. The trailing separator stops a sibling
    such as ``D.O.N.N.A-copy`` from matching the ``D.O.N.N.A`` prefix."""
    if not cwd or not root:
        return False
    c = canonical(cwd, root)
    return c == root or c.startswith(root + "/")


def _tier_maps(root: str):
    t1 = {canonical(posixpath.join(root, r), root): r for r in TIER1_PROTECTED}
    t2 = {canonical(posixpath.join(root, r), root): r for r in TIER2_KILLSWITCH}
    return t1, t2


# --------------------------------------------------------------------------
# Quote-aware scanning primitives
# --------------------------------------------------------------------------

def _mask_quoted(s: str) -> str:
    """Same-length copy with quoted regions replaced by NULs.

    Indices in the result line up with the original, so a regex can be run on the
    mask to find matches that are *outside* any quoted string, then the text read
    back from the original at the same offsets.
    """
    out = []
    quote = None
    for ch in s:
        if quote:
            out.append("\x00")
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
            out.append("\x00")
        else:
            out.append(ch)
    return "".join(out)


def _read_token(s: str, i: int):
    """Read one shell token from s starting at i. Returns (text, next_index)."""
    n = len(s)
    while i < n and s[i] in " \t":
        i += 1
    if i >= n:
        return "", i
    if s[i] in "\"'":
        q = s[i]
        j = s.find(q, i + 1)
        if j == -1:
            return s[i + 1:], n
        return s[i + 1:j], j + 1
    j = i
    while j < n and s[j] not in " \t\n;|&<>":
        j += 1
    return s[i:j], j


_SEPARATOR = re.compile(r"&&|\|\||;|\n|\|")


def split_subcommands(cmd: str):
    """Split on unquoted && || ; | and newline. Returns a list of raw strings."""
    mask = _mask_quoted(cmd)
    parts, last = [], 0
    for m in _SEPARATOR.finditer(mask):
        # do not split a 2>&1 style redirect
        if m.group(0) == "|" and m.start() > 0 and mask[m.start() - 1] == ">":
            continue
        parts.append(cmd[last:m.start()])
        last = m.end()
    parts.append(cmd[last:])
    return [p.strip() for p in parts if p.strip()]


def tokens_of(sub: str):
    """Tokenise a subcommand, dropping redirect operators and their targets."""
    toks, i, n = [], 0, len(sub)
    while i < n:
        while i < n and sub[i] in " \t":
            i += 1
        if i >= n:
            break
        if sub[i] in "<>" or (sub[i].isdigit() and i + 1 < n and sub[i + 1] == ">"):
            while i < n and (sub[i] in "<>&" or sub[i].isdigit()):
                i += 1
            _, i = _read_token(sub, i)          # consume the redirect target
            continue
        t, i = _read_token(sub, i)
        if t:
            toks.append(t)
    return toks


_REDIR = re.compile(r"(?<![0-9<>])(\d?>>?)(?!&)")


def redirect_targets(sub: str):
    """Destinations of > and >> in this subcommand (quoted targets included)."""
    mask = _mask_quoted(sub)
    out = []
    for m in _REDIR.finditer(mask):
        tgt, _ = _read_token(sub, m.end())
        tgt = tgt.strip().strip(_QUOTES)
        if tgt and not tgt.startswith("&"):
            out.append(tgt)
    return out


# --------------------------------------------------------------------------
# Directory tracking
# --------------------------------------------------------------------------

_CD_VERBS = ("cd", "chdir", "pushd", "push-location", "set-location", "sl")


def cd_target(toks):
    """If this subcommand changes directory, return its literal argument."""
    if not toks:
        return None
    if toks[0].lower() not in _CD_VERBS:
        return None
    for t in toks[1:]:
        if t.startswith("-") and t.lower() not in ("-path",):
            continue
        if t.lower() == "-path":
            continue
        return t
    return None


# --------------------------------------------------------------------------
# Mutation destinations
# --------------------------------------------------------------------------

# Verbs where every path argument is a destination.
_MUTATE_ANY = {
    "sed", "perl", "patch", "tee", "rm", "del", "unlink", "shred", "truncate",
    "dd", "shred", "set-content", "add-content", "clear-content", "out-file",
    "set-item", "remove-item", "rename-item", "new-item", "sc",
}
# Verbs where only the LAST path argument is the destination (source survives).
_COPY_VERBS = {"cp", "copy", "install", "copy-item", "cpi"}
# Verbs that also destroy their source, so BOTH ends matter.
_MOVE_VERBS = {"mv", "move", "move-item", "rename-item", "mi", "ren"}
_MUTATE_LAST = _COPY_VERBS | _MOVE_VERBS

# Verbs that only mutate with an in-place flag.
_INPLACE_ONLY = {"sed", "perl"}
_INPLACE_FLAG = re.compile(r"^-[a-z]*i[a-z]*$", re.I)

_GIT_MUTATE = re.compile(r"^(apply|restore|checkout|stash|reset|clean|mv|rm)$", re.I)

# Concrete file-writing APIs. Each yields a literal destination path.
_CODE_DESTS = (
    re.compile(r"\bopen\s*\(\s*['\"]([^'\"]+)['\"]\s*,\s*['\"][^'\"]*[wax+]", re.I),
    re.compile(r"\bPath\s*\(\s*['\"]([^'\"]+)['\"]\s*\)\s*\.\s*write_(?:text|bytes)", re.I),
    re.compile(r"\bos\.(?:remove|unlink|truncate)\s*\(\s*['\"]([^'\"]+)['\"]", re.I),
    re.compile(r"\bos\.(?:rename|replace)\s*\(\s*['\"][^'\"]+['\"]\s*,\s*['\"]([^'\"]+)['\"]", re.I),
    re.compile(r"\bshutil\.(?:copy|copy2|copyfile|move)\s*\(\s*['\"][^'\"]+['\"]\s*,\s*['\"]([^'\"]+)['\"]", re.I),
    re.compile(r"\.(?:writeFile|appendFile)(?:Sync)?\s*\(\s*['\"]([^'\"]+)['\"]", re.I),
    re.compile(r"\.(?:rm|unlink|truncate)(?:Sync)?\s*\(\s*['\"]([^'\"]+)['\"]", re.I),
    re.compile(r"\.(?:rename|copyFile)(?:Sync)?\s*\(\s*['\"][^'\"]+['\"]\s*,\s*['\"]([^'\"]+)['\"]", re.I),
)


def _path_args(toks):
    """Argument tokens that could name a file."""
    return [t for t in toks[1:] if t and not t.startswith("-")]


def destinations(sub: str, toks):
    """(destination_path, short_label) pairs this subcommand would write to."""
    out = []
    for tgt in redirect_targets(sub):
        out.append((tgt, "shell redirect"))
    if not toks:
        return out

    verb = toks[0].lower()
    verb = verb.rsplit("/", 1)[-1]

    if verb == "git":
        rest = [t for t in toks[1:] if not t.startswith("-")]
        if rest and _GIT_MUTATE.match(rest[0]):
            for p in rest[1:]:
                out.append((p, "git " + rest[0].lower()))
    elif verb in _MUTATE_LAST:
        args = _path_args(toks)
        # PowerShell -Destination wins when present
        dest = None
        for i, t in enumerate(toks):
            if t.lower() in ("-destination", "-dest") and i + 1 < len(toks):
                dest = toks[i + 1]
        if dest is None and len(args) >= 2:
            dest = args[-1]
        elif dest is None and len(args) == 1:
            dest = args[0]
        if dest is not None:
            out.append((dest, verb + " destination"))
        if verb in _MOVE_VERBS:
            # a move/rename removes the source too
            for p_ in args[:-1] if len(args) >= 2 else []:
                out.append((p_, verb + " source (removed)"))
    elif verb in _MUTATE_ANY:
        if verb in _INPLACE_ONLY and not any(_INPLACE_FLAG.match(t) for t in toks[1:]):
            pass                                  # sed -n / perl -e: read-only
        else:
            for p in _path_args(toks):
                out.append((p, verb + " target"))

    for rx in _CODE_DESTS:
        for m in rx.finditer(sub):
            out.append((m.group(1), "file write"))

    return out


# --------------------------------------------------------------------------
# Guarded flag assignment
# --------------------------------------------------------------------------

_FLAG_ALT = "|".join(GUARDED_FLAGS)

# Explicit API forms. These name the variable inside quotes by design, so they
# are matched on the raw text rather than the quote-masked text.
_FLAG_API = (
    re.compile(r"\[(?:System\.)?Environment\]::SetEnvironmentVariable\(\s*['\"](" +
               _FLAG_ALT + r")['\"]\s*,\s*['\"]?([^'\",)]*)", re.I),
    re.compile(r"Set-Item\s+(?:-Path\s+)?Env:\\?(" + _FLAG_ALT +
               r")\b[^;|]*?-Value\s+['\"]?([^\s'\";]+)", re.I),
    re.compile(r"\$env:(" + _FLAG_ALT + r")\s*=\s*['\"]?([^\s'\";]+)", re.I),
    re.compile(r"os\.environ(?:\.setdefault\(|\[)\s*['\"](" + _FLAG_ALT +
               r")['\"]\s*[\],]\s*=?\s*['\"]?([^'\"),]*)", re.I),
    re.compile(r"process\.env\.(" + _FLAG_ALT + r")\s*=\s*['\"]?([^\s'\";]+)", re.I),
    re.compile(r"\bsetx\s+['\"]?(" + _FLAG_ALT + r")['\"]?\s+['\"]?([^\s'\"]+)", re.I),
)

# Bare shell assignment. Matched on the MASKED text so that a mention inside a
# quoted string -- documentation, a test fixture, an echo -- does not count.
_FLAG_BARE = re.compile(r"(?:^|[\s;&|])(?:export\s+|env\s+|set\s+)?(" + _FLAG_ALT + r")=")


def _truthy(v: str) -> bool:
    return v.strip().strip(_QUOTES).strip().lower() in TRUTHY


def guarded_flag_enabled(cmd: str):
    """Flag name if the command sets a guarded flag to an enabling value."""
    for rx in _FLAG_API:
        for name, val in rx.findall(cmd):
            if _truthy(val):
                return name.upper()
    mask = _mask_quoted(cmd)
    for m in _FLAG_BARE.finditer(mask):
        val, _ = _read_token(cmd, m.end(1) + 1)
        if _truthy(val):
            return m.group(1).upper()
    return None


# --------------------------------------------------------------------------
# Decision
# --------------------------------------------------------------------------

def _t1_reason(rel, label):
    return ("This command would modify %s (%s), a guarded file of the retired NOVA "
            "trading subsystem. Reading, grepping, diffing, copying *from* it and "
            "running tests against it are allowed." % (rel, label))


def _t2_shell_reason(rel, label):
    return ("This command would modify %s (%s) from the shell. %s carries the NOVA "
            "retirement kill switch, and a shell command cannot show which lines it "
            "changes -- use Edit for ordinary changes to this file." % (rel, label, rel))


def decide_shell(command: str, cwd: str, t1: dict, t2: dict):
    flag = guarded_flag_enabled(command)
    if flag:
        return ("This command sets %s to an enabling value. The NOVA trading "
                "subsystem is retired and must stay disabled." % flag)

    here = cwd
    for sub in split_subcommands(command):
        toks = tokens_of(sub)
        for raw, label in destinations(sub, toks):
            key = canonical(raw, here)
            if key in t1:
                return _t1_reason(t1[key], label)
            if key in t2:
                return _t2_shell_reason(t2[key], label)
        tgt = cd_target(toks)
        if tgt:
            here = canonical(tgt, here)
    return None


def decide_edit(tool: str, ti: dict, cwd: str, t1: dict, t2: dict):
    targets = []
    for key in ("file_path", "notebook_path", "path"):
        v = ti.get(key)
        if isinstance(v, str):
            targets.append((v, ti))
    edits = ti.get("edits")
    if isinstance(edits, list):
        for e in edits:
            if isinstance(e, dict) and isinstance(e.get("file_path"), str):
                targets.append((e["file_path"], e))

    for raw, payload in targets:
        key = canonical(raw, cwd)
        if key in t1:
            return ("%s is a guarded file of the retired NOVA trading subsystem and "
                    "must not be modified. Reading it is allowed. See "
                    "nova_knowledge_core/TRADING_SUBSYSTEM_RETIREMENT_AUDIT.md."
                    % t1[key])
        if key in t2:
            rel = t2[key]
            if tool in ("Write", "NotebookEdit"):
                return ("%s would be replaced wholesale. It carries the NOVA "
                        "retirement kill switch, so full-file replacement is blocked "
                        "-- use Edit for targeted changes." % rel)
            blob = ""
            for f in ("old_string", "new_string", "new_source", "content"):
                v = payload.get(f)
                if isinstance(v, str):
                    blob += v + "\n"
                v2 = ti.get(f)
                if isinstance(v2, str) and v2 not in blob:
                    blob += v2 + "\n"
            for expr in GUARD_EXPRESSIONS:
                if expr in blob:
                    return ("This edit touches retirement kill-switch text (%s) in %s. "
                            "The trading subsystem is retired; unrelated edits to this "
                            "file are allowed." % (expr, rel))
    return None


def decide(payload: dict):
    tool = payload.get("tool_name") or ""
    ti = payload.get("tool_input") or {}
    if not isinstance(ti, dict):
        return None
    cwd = payload.get("cwd") or ""
    if not isinstance(cwd, str):
        return None

    root = resolve_root(cwd)
    if not root or not in_scope(cwd, root):
        return None                     # fail open: no usable project context

    t1, t2 = _tier_maps(root)
    base = canonical(cwd, root)

    if tool in FILE_EDIT_TOOLS:
        return decide_edit(tool, ti, base, t1, t2)
    if tool in SHELL_TOOLS:
        command = ti.get("command")
        if not isinstance(command, str):
            return None
        return decide_shell(command, base, t1, t2)
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
        return 0

    try:
        reason = decide(payload)
    except Exception:
        return 0                        # never lock the session on a hook bug
    if reason is None:
        return 0

    sys.stdout.write(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }))
    sys.stdout.flush()
    sys.stderr.write(reason)
    sys.stderr.flush()
    return 2


if __name__ == "__main__":
    sys.exit(main())
