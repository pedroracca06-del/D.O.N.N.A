#!/usr/bin/env python
"""evidence_formatter.py -- deterministic, read-only Cowork evidence renderer.

Turns a validated JSON evidence document into either a Markdown report or a
normalized JSON document. It exists so that no claim about repository or test
state can be made without the command, the counts, and the failures behind it.

BOUNDARY (the whole point of this tool):
  * It NEVER executes anything. Command strings inside the document are data,
    rendered as text, and are never passed to a shell, subprocess, eval, or exec.
  * It NEVER writes a file. Output goes to stdout; errors go to stderr.
  * It NEVER touches the network.
  * It reads no environment variables and no clock. A timestamp appears in the
    output only if the caller supplied one in the input.
  * Standard library only.

DERIVED STATUS: the overall status is computed from the individual check
statuses. A caller-supplied "passed" claim is never trusted -- see
`derive_overall`. Zero checks can never yield `passed`.

PRIVACY: every string is sanitized before rendering. Values under
credential-shaped keys are replaced wholesale, recognizable credential formats
are replaced without echoing the match, and home-directory paths are rewritten
to ``${HOME}`` by pattern so no username reaches the output.

Exit codes:
  0  input valid and formatted (regardless of whether the checks passed)
  2  invalid CLI usage, or schema/content validation failure
  3  safety-limit rejection (size, depth, or collection count)
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from typing import Any

SCHEMA_VERSION = 1

# --------------------------------------------------------------------------
# Safety limits
# --------------------------------------------------------------------------

MAX_INPUT_BYTES = 1024 * 1024          # 1 MiB
MAX_DEPTH = 32
MAX_COLLECTION = 1000
MAX_STRING = 8192

VALID_STATUSES = ("pass", "fail", "stopped", "warning", "informational")

REQUIRED_TOP = ("schema_version", "phase", "scope", "checks")
OPTIONAL_TOP = ("tests", "changes", "repository_state", "permission_state", "notes")


class ValidationError(Exception):
    """Input is structurally or semantically invalid -> exit 2."""


class SafetyLimitError(Exception):
    """Input exceeded a documented safety bound -> exit 3."""


# --------------------------------------------------------------------------
# Sanitization
# --------------------------------------------------------------------------

REDACTED = "[REDACTED]"

# Keys whose VALUE is always replaced. Matched on the key only, so ordinary
# prose mentioning these words is untouched.
_CREDENTIAL_KEY_WORDS = (
    "token", "secret", "password", "passphrase", "api_key", "apikey",
    "cookie", "authorization", "bearer", "private_key", "access_key",
    "refresh_token", "client_secret",
)
# Key names that merely *describe* credential handling rather than carrying one.
_KEY_ALLOWLIST = re.compile(
    r"(?i)(_count|_scan|_check|_status|_result|_policy|_name|_label|_id|"
    r"izer|ization_check|scanner|redact)$"
)


def _is_credential_key(key: str) -> bool:
    k = key.lower()
    if _KEY_ALLOWLIST.search(k):
        return False
    return any(w in k for w in _CREDENTIAL_KEY_WORDS)


# Value patterns replaced without ever emitting the matched text.
_VALUE_PATTERNS = (
    # An auth header carries an optional scheme word AND the credential after
    # it. Matching only \S+ would stop at the space after "Bearer" and leave the
    # token itself in the output, so the scheme is consumed explicitly.
    re.compile(r"(?i)\b(?:proxy-)?authorization\s*:\s*(?:[A-Za-z][A-Za-z0-9-]*\s+)?\S+"),
    re.compile(r"(?i)\b(?:bearer|basic)\s+[A-Za-z0-9._~+/=-]{8,}"),
    re.compile(r"(?i)\bcookie\s*:\s*(?:[A-Za-z][A-Za-z0-9-]*\s+)?\S+"),
    re.compile(r"sk-ant-[A-Za-z0-9._-]{8,}"),
    re.compile(r"\bghp_[A-Za-z0-9]{16,}"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"-----BEGIN[^-]{0,64}-----"),
    # NAME=value where NAME looks credential-ish (env assignment in a command)
    re.compile(r"(?i)\b[A-Z0-9_]*(?:TOKEN|SECRET|PASSWORD|PASSPHRASE|APIKEY|"
               r"API_KEY|ACCESS_KEY|PRIVATE_KEY|CLIENT_SECRET)[A-Z0-9_]*\s*=\s*\S+"),
    # URL query secrets: ?token=... &api_key=... etc.
    re.compile(r"(?i)[?&](?:token|secret|api[_-]?key|password|access[_-]?key|"
               r"auth|sig|signature)=[^&\s\"']+"),
    # credentials embedded in a URL authority
    re.compile(r"(?i)\b[a-z][a-z0-9+.-]*://[^/\s:@]+:[^/\s@]+@"),
)

# Home-directory normalization, by PATTERN -- no environment read, so the
# username never has to be known (or exposed) to be removed.
_HOME_PATTERNS = (
    # Windows: C:\Users\<name>\...  or  C:/Users/<name>/...
    re.compile(r"(?i)\b[a-z]:[\\/]+users[\\/]+[^\\/\s\"']+"),
    # Git-Bash / MSYS: /c/Users/<name>/...
    re.compile(r"(?i)(?<![\w.])/[a-z]/users/[^/\s\"']+"),
    # POSIX: /home/<name>/...  and macOS /Users/<name>/...
    re.compile(r"(?<![\w.])/home/[^/\s\"']+"),
    re.compile(r"(?<![\w.])/Users/[^/\s\"']+"),
)


def sanitize_text(value: str) -> str:
    """Redact credential-shaped content and normalize home paths."""
    out = value
    for rx in _VALUE_PATTERNS:
        out = rx.sub(REDACTED, out)
    for rx in _HOME_PATTERNS:
        out = rx.sub("${HOME}", out)
    if len(out) > MAX_STRING:
        out = out[:MAX_STRING] + "...[truncated]"
    return out


def sanitize(node: Any, key: str | None = None) -> Any:
    """Recursively sanitize. Returns NEW structures; the input is not mutated."""
    if isinstance(node, dict):
        return {k: sanitize(v, k) for k, v in node.items()}
    if isinstance(node, list):
        return [sanitize(v, key) for v in node]
    if isinstance(node, str):
        if key is not None and _is_credential_key(key):
            return REDACTED
        return sanitize_text(node)
    return node


# --------------------------------------------------------------------------
# Structural limits
# --------------------------------------------------------------------------

def enforce_limits(node: Any, depth: int = 0) -> None:
    if depth > MAX_DEPTH:
        raise SafetyLimitError("input nesting exceeds the maximum depth of %d" % MAX_DEPTH)
    if isinstance(node, dict):
        if len(node) > MAX_COLLECTION:
            raise SafetyLimitError("a mapping exceeds the maximum of %d entries" % MAX_COLLECTION)
        for v in node.values():
            enforce_limits(v, depth + 1)
    elif isinstance(node, list):
        if len(node) > MAX_COLLECTION:
            raise SafetyLimitError("a list exceeds the maximum of %d items" % MAX_COLLECTION)
        for v in node:
            enforce_limits(v, depth + 1)
    elif isinstance(node, float):
        if math.isnan(node) or math.isinf(node):
            raise ValidationError("non-standard numeric value is not permitted")


# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------

def _require_mapping(value: Any, what: str) -> dict:
    if not isinstance(value, dict):
        raise ValidationError("%s must be a mapping" % what)
    return value


def validate(doc: Any) -> dict:
    if not isinstance(doc, dict):
        raise ValidationError("the evidence document must be a JSON object")

    for field in REQUIRED_TOP:
        if field not in doc:
            raise ValidationError("missing required field: %s" % field)

    if doc["schema_version"] != SCHEMA_VERSION:
        raise ValidationError(
            "unsupported schema_version (expected %d)" % SCHEMA_VERSION)

    for field in ("phase", "scope"):
        if not isinstance(doc[field], str) or not doc[field].strip():
            raise ValidationError("%s must be a non-empty string" % field)

    checks = doc["checks"]
    if not isinstance(checks, list):
        raise ValidationError("checks must be a list")

    seen: set[str] = set()
    for item in checks:
        c = _require_mapping(item, "each check")
        for field in ("id", "label", "status"):
            if field not in c:
                raise ValidationError("a check is missing required field: %s" % field)
            if not isinstance(c[field], str) or not c[field].strip():
                raise ValidationError("check field %s must be a non-empty string" % field)
        if c["status"] not in VALID_STATUSES:
            raise ValidationError(
                "invalid check status (expected one of: %s)" % ", ".join(VALID_STATUSES))
        if c["id"] in seen:
            raise ValidationError("duplicate check id")
        seen.add(c["id"])
        if "evidence" in c and not isinstance(c["evidence"], str):
            raise ValidationError("check evidence must be a string")

    if "tests" in doc:
        tests = doc["tests"]
        if not isinstance(tests, list):
            raise ValidationError("tests must be a list")
        for item in tests:
            t = _require_mapping(item, "each test entry")
            if "command" not in t or not isinstance(t["command"], str) or not t["command"].strip():
                raise ValidationError("each test entry needs a non-empty command string")
            for numeric in ("passed", "failed", "skipped", "errors", "exit_code"):
                if numeric in t and not isinstance(t[numeric], int):
                    raise ValidationError("test field %s must be an integer" % numeric)
                if numeric in t and isinstance(t[numeric], bool):
                    raise ValidationError("test field %s must be an integer" % numeric)
            if "duration_seconds" in t and not isinstance(t["duration_seconds"], (int, float)):
                raise ValidationError("duration_seconds must be a number")
            if "failures" in t and not isinstance(t["failures"], list):
                raise ValidationError("test failures must be a list")

    for field, kind in (("changes", dict), ("repository_state", dict),
                        ("permission_state", dict)):
        if field in doc and not isinstance(doc[field], kind):
            raise ValidationError("%s must be a mapping" % field)

    if "notes" in doc and not isinstance(doc["notes"], list):
        raise ValidationError("notes must be a list")

    unknown = set(doc) - set(REQUIRED_TOP) - set(OPTIONAL_TOP)
    if unknown:
        raise ValidationError("unrecognized top-level field(s): %s"
                              % ", ".join(sorted(unknown)))
    return doc


# --------------------------------------------------------------------------
# Derived status -- never trusts the caller
# --------------------------------------------------------------------------

def derive_overall(checks: list) -> str:
    """Compute overall status from check statuses only.

    Precedence: any fail -> failed; else any stopped -> stopped; else any
    warning -> passed_with_warnings; else passed. Zero checks -> stopped.
    """
    if not checks:
        return "stopped"
    statuses = {c["status"] for c in checks}
    if "fail" in statuses:
        return "failed"
    if "stopped" in statuses:
        return "stopped"
    if "warning" in statuses:
        return "passed_with_warnings"
    return "passed"


# --------------------------------------------------------------------------
# Normalization
# --------------------------------------------------------------------------

def normalize(doc: dict) -> dict:
    """Sanitized, deterministically ordered document with derived status."""
    clean = sanitize(doc)
    checks = sorted(clean["checks"], key=lambda c: c["id"])
    out: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "phase": clean["phase"],
        "scope": clean["scope"],
        "overall_status": derive_overall(checks),
        "check_counts": {s: sum(1 for c in checks if c["status"] == s)
                         for s in VALID_STATUSES},
        "checks": checks,
    }
    if "tests" in clean:
        out["tests"] = sorted(clean["tests"], key=lambda t: t["command"])
    for field in ("changes", "repository_state", "permission_state"):
        if field in clean:
            out[field] = clean[field]
    if "notes" in clean:
        out["notes"] = clean["notes"]
    if "timestamp" in clean.get("repository_state", {}):
        pass  # timestamps are passed through as supplied; none is generated
    return out


def render_json(norm: dict) -> str:
    return json.dumps(norm, indent=2, sort_keys=True, ensure_ascii=False,
                      allow_nan=False) + "\n"


# --------------------------------------------------------------------------
# Markdown rendering
# --------------------------------------------------------------------------

_STATUS_LABEL = {
    "passed": "PASSED",
    "passed_with_warnings": "PASSED WITH WARNINGS",
    "stopped": "STOPPED",
    "failed": "FAILED",
}


def _md_escape(text: str) -> str:
    return text.replace("|", "\\|").replace("\r", "").replace("\n", " ")


def _render_paths(title: str, values: Any, lines: list) -> None:
    lines.append("### %s" % title)
    lines.append("")
    if values is None or (isinstance(values, list) and not values):
        lines.append("- none")
    elif isinstance(values, list):
        for v in values:
            lines.append("- `%s`" % _md_escape(str(v)))
    else:
        lines.append("- %s" % _md_escape(str(values)))
    lines.append("")


def render_markdown(norm: dict) -> str:
    L: list = []
    overall = norm["overall_status"]
    L.append("# Evidence Report — %s" % _STATUS_LABEL.get(overall, overall.upper()))
    L.append("")
    L.append("**Overall status:** %s" % _STATUS_LABEL.get(overall, overall.upper()))
    L.append("")
    L.append("- **Phase:** %s" % _md_escape(norm["phase"]))
    L.append("- **Scope:** %s" % _md_escape(norm["scope"]))
    L.append("")

    counts = norm["check_counts"]
    L.append("## Check summary")
    L.append("")
    L.append("| Status | Count |")
    L.append("|---|---|")
    for s in VALID_STATUSES:
        L.append("| %s | %d |" % (s, counts[s]))
    L.append("| **total** | **%d** |" % len(norm["checks"]))
    L.append("")

    L.append("## Checks")
    L.append("")
    if not norm["checks"]:
        L.append("No checks were supplied, so no claim of success can be made.")
        L.append("")
    else:
        L.append("| ID | Status | Label | Evidence |")
        L.append("|---|---|---|---|")
        for c in norm["checks"]:
            L.append("| `%s` | %s | %s | %s |" % (
                _md_escape(c["id"]), c["status"], _md_escape(c["label"]),
                _md_escape(c.get("evidence", c.get("reason", "")))))
        L.append("")

    if "tests" in norm:
        L.append("## Tests")
        L.append("")
        if not norm["tests"]:
            L.append("- no test runs reported")
            L.append("")
        for t in norm["tests"]:
            L.append("**Command:** `%s`" % _md_escape(t["command"]))
            L.append("")
            fields = [(k, t[k]) for k in
                      ("passed", "failed", "skipped", "errors", "exit_code",
                       "duration_seconds") if k in t]
            if fields:
                L.append("| Field | Value |")
                L.append("|---|---|")
                for k, v in fields:
                    L.append("| %s | %s |" % (k, _md_escape(str(v))))
                L.append("")
            failures = t.get("failures") or []
            L.append("Failures: %s" % ("none" if not failures else ""))
            for f in failures:
                L.append("- `%s`" % _md_escape(str(f)))
            L.append("")

    if "changes" in norm:
        L.append("## Changes")
        L.append("")
        ch = norm["changes"]
        for title, key in (("Modified paths", "modified_paths"),
                           ("Staged paths", "staged_paths"),
                           ("Committed paths", "committed_paths"),
                           ("Pushed refs", "pushed_refs")):
            if key in ch:
                _render_paths(title, ch[key], L)

    if "repository_state" in norm:
        L.append("## Repository state")
        L.append("")
        L.append("| Field | Value |")
        L.append("|---|---|")
        for k in sorted(norm["repository_state"]):
            L.append("| %s | %s |" % (k, _md_escape(str(norm["repository_state"][k]))))
        L.append("")

    if "permission_state" in norm:
        L.append("## Permission state")
        L.append("")
        L.append("| Field | Value |")
        L.append("|---|---|")
        for k in sorted(norm["permission_state"]):
            L.append("| %s | %s |" % (k, _md_escape(str(norm["permission_state"][k]))))
        L.append("")

    if norm.get("notes"):
        L.append("## Notes")
        L.append("")
        for n in norm["notes"]:
            L.append("- %s" % _md_escape(str(n)))
        L.append("")

    while L and L[-1] == "":
        L.pop()
    return "\n".join(L) + "\n"


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def _read_input(path: str | None) -> str:
    if path is None:
        raw = sys.stdin.buffer.read()
    else:
        try:
            with open(path, "rb") as fh:
                raw = fh.read(MAX_INPUT_BYTES + 1)
        except OSError:
            raise ValidationError("input file could not be read")
    if len(raw) > MAX_INPUT_BYTES:
        raise SafetyLimitError(
            "input exceeds the maximum accepted size of %d bytes" % MAX_INPUT_BYTES)
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        raise ValidationError("input is not valid UTF-8")


def main(argv: list | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="evidence_formatter",
        description="Render a Cowork evidence document. Read-only; executes nothing.",
        add_help=True)
    parser.add_argument("--format", choices=("markdown", "json"), required=True,
                        help="output format (stdout only)")
    parser.add_argument("--input", default=None,
                        help="path to a UTF-8 JSON evidence document; stdin if omitted")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        # argparse exits 0 for --help; anything else is a usage error.
        return 0 if exc.code == 0 else 2

    try:
        text = _read_input(args.input)
        try:
            doc = json.loads(text, parse_constant=_reject_constant)
        except ValidationError:
            raise
        except Exception:
            # Deliberately does not echo the payload.
            raise ValidationError("input is not valid JSON")
        enforce_limits(doc)
        validate(doc)
        norm = normalize(doc)
        out = render_markdown(norm) if args.format == "markdown" else render_json(norm)
    except SafetyLimitError as exc:
        _write_err("evidence_formatter: safety limit: %s\n" % sanitize_text(str(exc)))
        return 3
    except ValidationError as exc:
        _write_err("evidence_formatter: invalid input: %s\n" % sanitize_text(str(exc)))
        return 2

    _write_out(out)
    return 0


def _write_out(text: str) -> None:
    """Emit UTF-8 bytes explicitly.

    Writing through sys.stdout would encode with the platform's locale codec
    (cp1252 on a redirected Windows pipe), so identical logical input would
    produce different bytes on different machines. Determinism requires the
    encoding to be fixed here rather than inherited from the environment.
    """
    sys.stdout.buffer.write(text.encode("utf-8"))
    sys.stdout.buffer.flush()


def _write_err(text: str) -> None:
    sys.stderr.buffer.write(text.encode("utf-8"))
    sys.stderr.buffer.flush()


def _reject_constant(name: str):
    raise ValidationError("non-standard numeric value is not permitted")


if __name__ == "__main__":
    sys.exit(main())
