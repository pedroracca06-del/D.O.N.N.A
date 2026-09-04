#!/usr/bin/env python
"""session_registry.py -- machine-local Cowork session collision registry.

Lets one session discover that another is already working on the same worktree,
branch, or file scope before it starts an audit or a staging plan. It is
coordination metadata and nothing else.

Designed real location (NOT created by this tool):

    ${HOME}/.claude/nova-session-registry.json

BOUNDARY:
  * Lives outside every repository and worktree.
  * Holds coordination metadata only -- no credentials, tokens, environment
    values, broker data, prompts, source content, or trading instructions.
  * Executes nothing. Edits no repository. Runs no command from input.
  * Never blocks a human: it reports, and a person decides.
  * NEVER deletes a record. `close` marks history; there is deliberately no
    prune, delete, clear, force, override, repair, or patch operation.
  * `advance` moves an active session's `expected_commit` forward after an
    intentional local commit. The destination is ALWAYS the verified repository
    HEAD -- it can never be supplied -- and the recorded commit must be an
    ancestor of it, so a rewind, amend, or rebase is refused rather than
    absorbed. Advancing records where a session now sits; it approves nothing
    and never pushes, merges, or deploys.
  * Optional worktree verification reuses the Staleness Guard's read-only
    observations. It never fetches.
  * Standard library only.

INITIALIZATION: if the registry file does not exist, `list` and `check` report
that safely; every mutating operation stops. The tool never creates the file or
its parent directory -- real initialization is a separate approved step.

Exit codes:
  0  successful read, or a safe mutation
  1  live collision, or a rejected state transition
  2  invalid CLI, schema, or record
  3  safety-limit rejection
  4  stopped: registry unavailable, corrupt, or locked; or worktree observation failed
  5  stale or ambiguous collision requiring Pedro's decision
"""
from __future__ import annotations

import argparse
import errno
import json
import os
import re
import sys
import tempfile
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import evidence_formatter as ef      # noqa: E402
import staleness_guard as sg         # noqa: E402

sys.path.pop(0)

SCHEMA_VERSION = 1
DEFAULT_STALE_SECONDS = 30 * 60          # 30 minutes
LOCK_TIMEOUT_SECONDS = 5
LOCK_POLL_SECONDS = 0.05

MAX_SESSIONS = 200
MAX_SCOPE_ENTRIES = 200
MAX_FIELD_CHARS = 512

SESSION_FIELDS = (
    "session_id", "worktree_identity", "canonical_worktree_path", "branch",
    "task", "read_scope", "write_scope", "protected_scope", "started_at",
    "heartbeat_at", "status", "owner", "expected_commit",
)
SCOPE_FIELDS = ("read_scope", "write_scope", "protected_scope")
VALID_STATUS = ("active", "paused", "closing", "closed")
NON_COLLIDING_STATUS = ("closed",)

_SESSION_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,63}$")
_IDENTITY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_BRANCH_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,127}$")
_OID_RE = re.compile(r"^[0-9a-f]{40}$|^[0-9a-f]{64}$")
_RFC3339_UTC_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$")

# Credential-shaped content must never enter the registry.
_SECRETISH_RE = re.compile(
    r"(?i)(api[_-]?key|secret|token|password|passphrase|cookie|authorization|"
    r"bearer|private[_-]?key|access[_-]?key|client[_-]?secret|sk-ant-|ghp_|"
    r"AKIA[0-9A-Z]{16})")


class StoppedError(Exception):
    """Registry unavailable, corrupt, or locked -> exit 4."""


class TransitionError(Exception):
    """A state transition was rejected -> exit 1."""


# --------------------------------------------------------------------------
# Time
# --------------------------------------------------------------------------

def parse_utc(value: str) -> datetime:
    if not isinstance(value, str) or not _RFC3339_UTC_RE.match(value):
        sg._bad("timestamps must be RFC3339 UTC, e.g. 2026-09-02T10:00:00Z")
    return datetime.strptime(value.split(".")[0].rstrip("Z"),
                             "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)


def format_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# --------------------------------------------------------------------------
# Scope algebra
# --------------------------------------------------------------------------

_WILDCARD_RE = re.compile(r"[*?\[]")


def normalize_scope(pattern: str) -> str:
    """Case-folded, slash-normalized. Windows path equivalence is why the fold
    happens here rather than at comparison time."""
    return pattern.replace("\\", "/").strip().rstrip("/").lower()


def scope_is_ambiguous(pattern: str) -> bool:
    """A pattern whose intersection with another cannot be decided exactly.

    Arbitrary glob intersection is not decidable in general. Anything beyond a
    single trailing `/**` or `/*` is treated as ambiguous and escalated rather
    than silently assumed disjoint.
    """
    p = normalize_scope(pattern)
    if not _WILDCARD_RE.search(p):
        return False
    if p.endswith("/**") or p.endswith("/*"):
        return bool(_WILDCARD_RE.search(p[: p.rfind("/")]))
    return True


def _prefix_of(pattern: str) -> str:
    p = normalize_scope(pattern)
    for suffix in ("/**", "/*"):
        if p.endswith(suffix):
            return p[: -len(suffix)]
    return p


def scopes_overlap(a: str, b: str):
    """(overlaps, ambiguous). Conservative: parent/child counts as overlap."""
    if scope_is_ambiguous(a) or scope_is_ambiguous(b):
        return True, True
    pa, pb = _prefix_of(a), _prefix_of(b)
    if pa == pb:
        return True, False
    if pa.startswith(pb + "/") or pb.startswith(pa + "/"):
        return True, False
    return False, False


def any_overlap(list_a, list_b):
    hits, ambiguous = [], False
    for a in list_a or []:
        for b in list_b or []:
            over, amb = scopes_overlap(a, b)
            if over:
                hits.append((a, b))
                ambiguous = ambiguous or amb
    return hits, ambiguous


# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------

def _check_scope_list(values, field):
    if not isinstance(values, list):
        sg._bad("%s must be a list" % field)
    if len(values) > MAX_SCOPE_ENTRIES:
        raise ef.SafetyLimitError(
            "%s exceeds the maximum of %d entries" % (field, MAX_SCOPE_ENTRIES))
    seen = {}
    for item in values:
        if not isinstance(item, str) or not item.strip():
            sg._bad("%s entries must be non-empty strings" % field)
        if len(item) > MAX_FIELD_CHARS:
            raise ef.SafetyLimitError("%s entry exceeds %d characters"
                                      % (field, MAX_FIELD_CHARS))
        norm = item.replace("\\", "/")
        if norm.startswith("/") or re.match(r"^[A-Za-z]:", norm):
            sg._bad("%s entries must be repository-relative, not absolute" % field)
        if ".." in norm.split("/"):
            sg._bad("%s entries must not contain a parent-directory traversal" % field)
        folded = normalize_scope(item)
        if folded in seen:
            sg._bad("%s contains duplicate or case-conflicting entries" % field)
        seen[folded] = item


def validate_session(rec, what="session"):
    if not isinstance(rec, dict):
        sg._bad("%s must be a mapping" % what)
    missing = [f for f in SESSION_FIELDS if f not in rec]
    if missing:
        sg._bad("%s missing required field(s): %s" % (what, ", ".join(missing)))
    extra = set(rec) - set(SESSION_FIELDS)
    if extra:
        sg._bad("%s has unrecognized field(s): %s" % (what, ", ".join(sorted(extra))))

    if not _SESSION_ID_RE.match(str(rec["session_id"])):
        sg._bad("session_id must be 3-64 chars of [A-Za-z0-9._-] starting alphanumeric")
    if not _IDENTITY_RE.match(str(rec["worktree_identity"])):
        sg._bad("worktree_identity is not a valid stable name")
    if not _BRANCH_RE.match(str(rec["branch"])):
        sg._bad("branch is not a valid ref name")
    if not _OID_RE.match(str(rec["expected_commit"])):
        sg._bad("expected_commit must be a full git object id")
    if rec["status"] not in VALID_STATUS:
        sg._bad("status must be one of: %s" % ", ".join(VALID_STATUS))

    for field in ("canonical_worktree_path", "task", "owner"):
        value = rec[field]
        if not isinstance(value, str) or not value.strip():
            sg._bad("%s must be a non-empty string" % field)
        if len(value) > MAX_FIELD_CHARS:
            raise ef.SafetyLimitError("%s exceeds %d characters" % (field, MAX_FIELD_CHARS))

    started = parse_utc(rec["started_at"])
    beat = parse_utc(rec["heartbeat_at"])
    if beat < started:
        sg._bad("heartbeat_at precedes started_at")

    for field in SCOPE_FIELDS:
        _check_scope_list(rec[field], field)

    blob = json.dumps(rec, sort_keys=True)
    if _SECRETISH_RE.search(blob):
        sg._bad("the session record contains credential-shaped content and was rejected")
    return rec


def validate_registry(doc):
    if not isinstance(doc, dict):
        sg._bad("the registry must be a JSON object")
    extra = set(doc) - {"schema_version", "revision", "sessions"}
    if extra:
        sg._bad("registry has unrecognized field(s): %s" % ", ".join(sorted(extra)))
    for field in ("schema_version", "revision", "sessions"):
        if field not in doc:
            sg._bad("registry missing required field: %s" % field)
    if doc["schema_version"] != SCHEMA_VERSION:
        sg._bad("unsupported registry schema_version (expected %d)" % SCHEMA_VERSION)
    rev = doc["revision"]
    if not isinstance(rev, int) or isinstance(rev, bool) or rev < 0:
        sg._bad("revision must be a nonnegative integer")
    sessions = doc["sessions"]
    if not isinstance(sessions, list):
        sg._bad("sessions must be a list")
    if len(sessions) > MAX_SESSIONS:
        raise ef.SafetyLimitError("registry exceeds the maximum of %d sessions" % MAX_SESSIONS)
    seen = set()
    for rec in sessions:
        validate_session(rec, "registry session")
        if rec["session_id"] in seen:
            sg._bad("registry contains duplicate session_id")
        seen.add(rec["session_id"])
    return doc


# --------------------------------------------------------------------------
# Registry file access
# --------------------------------------------------------------------------

def _reject_constant(name):
    raise ef.ValidationError("non-standard numeric value is not permitted")


def registry_exists(path):
    return os.path.isfile(path)


def read_registry(path):
    if not registry_exists(path):
        raise StoppedError("the registry file does not exist")
    try:
        raw = open(path, "rb").read(ef.MAX_INPUT_BYTES + 1)
    except OSError:
        raise StoppedError("the registry file could not be read")
    if len(raw) > ef.MAX_INPUT_BYTES:
        raise ef.SafetyLimitError("the registry exceeds the maximum accepted size")
    try:
        doc = json.loads(raw.decode("utf-8"), parse_constant=_reject_constant)
    except ef.ValidationError:
        raise
    except Exception:
        raise StoppedError("the registry file is not valid JSON")
    ef.enforce_limits(doc)
    return validate_registry(doc)


class _Lock:
    """Atomic sibling lock.

    Uses O_CREAT|O_EXCL, which is atomic on Windows as well as POSIX -- no
    advisory locking, no platform-specific fallback. A lock this process did not
    create is never broken or removed automatically.
    """

    def __init__(self, registry_path, timeout=LOCK_TIMEOUT_SECONDS):
        self.path = registry_path + ".lock"
        self.timeout = timeout
        self.fd = None

    def __enter__(self):
        deadline = time.monotonic() + self.timeout
        while True:
            try:
                self.fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                os.write(self.fd, str(os.getpid()).encode("ascii"))
                return self
            except OSError as exc:
                if exc.errno != errno.EEXIST:
                    raise StoppedError("the registry lock could not be created")
                if time.monotonic() >= deadline:
                    raise StoppedError(
                        "the registry is locked by another process; "
                        "the lock is left in place for a person to inspect")
                time.sleep(LOCK_POLL_SECONDS)

    def __exit__(self, *exc):
        # Remove only the lock this process created.
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


def write_registry_atomic(path, doc):
    """Complete temp sibling -> flush -> fsync -> atomic replace.

    The original file is untouched unless the replacement fully succeeds.
    """
    validate_registry(doc)
    payload = (json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=False,
                          allow_nan=False) + "\n").encode("utf-8")
    directory = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(prefix=".nova-registry-", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(payload)
            fh.flush()
            try:
                os.fsync(fh.fileno())
            except OSError:
                pass
        try:
            os.chmod(tmp, 0o600)
        except OSError:
            pass
        os.replace(tmp, path)
        tmp = None
    finally:
        if tmp is not None and os.path.exists(tmp):
            try:
                os.unlink(tmp)        # never leave a partial file behind
            except OSError:
                pass


# --------------------------------------------------------------------------
# Classification and collisions
# --------------------------------------------------------------------------

def classify(rec, observed_at, stale_seconds):
    """live | stale | closing | closed | future-heartbeat."""
    if rec["status"] == "closed":
        return "closed"
    beat = parse_utc(rec["heartbeat_at"])
    delta = (observed_at - beat).total_seconds()
    if delta < -1:
        return "future-heartbeat"
    if rec["status"] == "closing":
        return "closing"
    if delta > stale_seconds:
        return "stale"
    return "live"


def find_collisions(proposal, registry, observed_at, stale_seconds,
                    ignore_self=False):
    """[(category, other_session_id, detail, severity)] with severity
    'blocking' (live) or 'approval' (stale/ambiguous).

    `ignore_self` is used by `resume`, where the proposal *is* an already
    registered record: without it the session would collide with itself and be
    reported as a duplicate id.
    """
    out = []
    p_write = proposal["write_scope"]
    p_read = proposal["read_scope"]
    p_prot = proposal["protected_scope"]

    for other in sorted(registry["sessions"], key=lambda r: r["session_id"]):
        if other["session_id"] == proposal["session_id"]:
            if not ignore_self:
                out.append(("duplicate-session-id", other["session_id"],
                            "a record with this session_id already exists", "blocking"))
            continue
        state = classify(other, observed_at, stale_seconds)
        if state == "closed":
            continue
        severity = "blocking" if state in ("live", "closing") else "approval"

        same_worktree = (normalize_scope(other["canonical_worktree_path"])
                         == normalize_scope(proposal["canonical_worktree_path"]))
        either_writes = bool(p_write) or bool(other["write_scope"])

        # ---- the read-only review handoff -------------------------------
        #
        # A writer that has EXPLICITLY paused, and whose heartbeat still proves
        # it alive, holds its write scope in reserve rather than in use. A
        # proposal that writes NOTHING may therefore be registered beside it --
        # that is the whole point of pausing for a review, and it is a
        # lifecycle-state fact, not an approval or an override.
        #
        # Deliberately narrow. This does nothing at all when:
        #   * the proposal has any write scope of its own (a writer never
        #     coexists with a writer, paused or otherwise);
        #   * the other session is active or closing (a working writer still
        #     blocks, exactly as before);
        #   * the other session is stale, ambiguous, or has a future heartbeat
        #     (`state` is then not "live", so nothing is discounted and the
        #     existing approval-severity path still stops the operation).
        #
        # Only the three write-derived collisions below are discounted. The
        # duplicate-id, expected-commit-mismatch, and every protected-scope
        # check remain exactly as they were.
        dormant_writer = (other["status"] == "paused" and state == "live"
                          and not p_write)

        if same_worktree and either_writes and not dormant_writer:
            out.append(("same-worktree-with-write", other["session_id"],
                        "another %s session holds this worktree" % state, severity))
        if (other["branch"] == proposal["branch"] and not same_worktree
                and either_writes and not dormant_writer):
            out.append(("same-branch-different-worktree", other["session_id"],
                        "branch is held by a %s session in another worktree" % state,
                        severity))
        if same_worktree and other["expected_commit"] != proposal["expected_commit"]:
            out.append(("expected-commit-mismatch", other["session_id"],
                        "same worktree recorded against a different baseline", severity))

        pairs = [("write-write-overlap", p_write, other["write_scope"]),
                 ("write-read-overlap", p_write, other["read_scope"]),
                 ("read-write-overlap", p_read, other["write_scope"]),
                 ("write-protected-overlap", p_write, other["protected_scope"]),
                 ("protected-write-overlap", p_prot, other["write_scope"])]
        if dormant_writer:
            # Only the reserved write scope is discounted, and only against a
            # plain read. A protected-scope claim still collides with it.
            pairs = [t for t in pairs if t[0] != "read-write-overlap"]

        for label, mine, theirs in pairs:
            hits, ambiguous = any_overlap(mine, theirs)
            if hits:
                sev = "approval" if (ambiguous or severity == "approval") else "blocking"
                detail = "%d overlapping pattern(s)%s" % (
                    len(hits), "; pattern intersection is ambiguous" if ambiguous else "")
                out.append((label, other["session_id"], detail, sev))
    return out


# --------------------------------------------------------------------------
# Evidence
# --------------------------------------------------------------------------

def _chk(cid, label, ok, evidence, stopped=False, warning=False):
    if stopped:
        status = "stopped"
    elif warning:
        status = "warning"
    else:
        status = "pass" if ok else "fail"
    return {"id": cid, "label": label, "status": status, "evidence": evidence}


def _sanitize_id(value):
    return ef.sanitize_text(str(value))


def build_checks(operation, proposal, registry, observed_at, stale_seconds,
                 rev_before, rev_after, collisions, extra=None):
    checks = [
        _chk("S01", "operation", True, operation),
        _chk("S02", "registry revision", True,
             "before %s, after %s" % (rev_before, rev_after)),
        _chk("S03", "observation time", True, format_utc(observed_at)),
        _chk("S04", "stale threshold", True, "%d seconds" % stale_seconds),
    ]
    if proposal is not None:
        checks.append(_chk("S05", "session", True,
                           "id %s, worktree %s, branch %s, status %s"
                           % (_sanitize_id(proposal["session_id"]),
                              _sanitize_id(proposal["worktree_identity"]),
                              _sanitize_id(proposal["branch"]),
                              proposal["status"])))
    if registry is not None:
        counts = {}
        for rec in registry["sessions"]:
            counts[classify(rec, observed_at, stale_seconds)] = \
                counts.get(classify(rec, observed_at, stale_seconds), 0) + 1
        checks.append(_chk("S06", "registry population", True,
                           ", ".join("%s=%d" % kv for kv in sorted(counts.items()))
                           or "no sessions"))
        future = [r for r in registry["sessions"]
                  if classify(r, observed_at, stale_seconds) == "future-heartbeat"]
        if future:
            checks.append(_chk("S07", "clock moved backward", False,
                               "%d record(s) carry a heartbeat later than the "
                               "observation time" % len(future), warning=True))

    blocking = [c for c in collisions if c[3] == "blocking"]
    approval = [c for c in collisions if c[3] == "approval"]
    checks.append(_chk("C00", "collision scan",
                       not blocking and not approval,
                       "blocking=%d, approval-required=%d" % (len(blocking), len(approval)),
                       warning=bool(approval) and not blocking))
    for i, (category, other, detail, severity) in enumerate(
            sorted(collisions, key=lambda c: (c[0], c[1])), 1):
        checks.append(_chk("C%02d" % i, "collision: %s" % category,
                           False, "with %s -- %s" % (_sanitize_id(other), detail),
                           warning=(severity == "approval")))
    for c in (extra or []):
        checks.append(c)
    return checks


# --------------------------------------------------------------------------
# Worktree verification (read-only, never fetches)
# --------------------------------------------------------------------------

def verify_worktree(repo_path, proposal):
    checks = []
    repo, identity = sg.resolve_repo(repo_path)
    base = {
        "schema_version": 1,
        "expected_branch": proposal["branch"],
        "expected_head": proposal["expected_commit"],
        "expected_worktree_identity": proposal["worktree_identity"],
    }
    for c in sg.observe(repo, identity, base, None):
        checks.append({"id": "W." + c["id"], "label": "worktree " + c["label"],
                       "status": c["status"], "evidence": c["evidence"]})
    return checks


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def _read_json_input(path):
    if path is None:
        raw = sys.stdin.buffer.read()
    else:
        try:
            with open(path, "rb") as fh:
                raw = fh.read(ef.MAX_INPUT_BYTES + 1)
        except OSError:
            raise ef.ValidationError("the session file could not be read")
    if len(raw) > ef.MAX_INPUT_BYTES:
        raise ef.SafetyLimitError("input exceeds the maximum accepted size")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise ef.ValidationError("input is not valid UTF-8")
    try:
        return json.loads(text, parse_constant=_reject_constant)
    except ef.ValidationError:
        raise
    except Exception:
        raise ef.ValidationError("input is not valid JSON")


def _err(text):
    sys.stderr.buffer.write(text.encode("utf-8"))
    sys.stderr.buffer.flush()


def _emit(checks, fmt, notes=None):
    doc = {"schema_version": ef.SCHEMA_VERSION, "phase": "session registry",
           "scope": "concurrent session coordination", "checks": checks}
    if notes:
        doc["notes"] = notes
    norm = ef.normalize(doc)
    text = ef.render_markdown(norm) if fmt == "markdown" else ef.render_json(norm)
    sys.stdout.buffer.write(text.encode("utf-8"))
    sys.stdout.buffer.flush()
    return norm


def _find(registry, session_id):
    for rec in registry["sessions"]:
        if rec["session_id"] == session_id:
            return rec
    return None


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="session_registry",
        description="Machine-local session collision registry. Never deletes a record.")
    parser.add_argument("operation",
                        choices=("list", "check", "register", "heartbeat",
                                 "pause", "resume", "close", "advance"))
    parser.add_argument("--registry", required=True,
                        help="path to the machine-local registry JSON file")
    parser.add_argument("--format", choices=("markdown", "json"), required=True)
    parser.add_argument("--input", default=None,
                        help="session JSON file; stdin if omitted")
    parser.add_argument("--session-id", default=None,
                        help="target session for heartbeat/pause/resume/close")
    parser.add_argument("--repo", default=None,
                        help="verify this worktree for check/register/resume")
    parser.add_argument("--observed-at", default=None,
                        help="RFC3339 UTC observation time (defaults to now)")
    parser.add_argument("--stale-seconds", type=int, default=DEFAULT_STALE_SECONDS)
    parser.add_argument("--previous-commit", default=None,
                        help="for advance: the commit currently recorded on the "
                             "session; the destination is always the verified "
                             "repository HEAD and can never be supplied")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return 0 if exc.code == 0 else 2

    op = args.operation
    try:
        observed_at = (parse_utc(args.observed_at) if args.observed_at
                       else datetime.now(timezone.utc))
        if args.stale_seconds < 0:
            sg._bad("--stale-seconds must be nonnegative")
    except ef.ValidationError as exc:
        _err("session_registry: invalid input: %s\n" % ef.sanitize_text(str(exc)))
        return 2

    # ---- uninitialized registry ------------------------------------------
    if not registry_exists(args.registry):
        if op in ("list", "check"):
            checks = [_chk("S01", "operation", True, op),
                      _chk("S00", "registry initialized", True,
                           "no registry file present; nothing is registered. "
                           "Creating it is a separate approved step.")]
            _emit(checks, args.format)
            return 0
        _err("session_registry: stopped: the registry does not exist; "
             "initialization is a separate approved step\n")
        return 4

    try:
        registry = read_registry(args.registry)
    except ef.SafetyLimitError as exc:
        _err("session_registry: safety limit: %s\n" % ef.sanitize_text(str(exc)))
        return 3
    except (StoppedError, ef.ValidationError) as exc:
        _err("session_registry: stopped: %s\n" % ef.sanitize_text(str(exc)))
        return 4

    rev_before = registry["revision"]

    # ---- read-only operations --------------------------------------------
    if op == "list":
        checks = build_checks(op, None, registry, observed_at,
                              args.stale_seconds, rev_before, rev_before, [])
        for i, rec in enumerate(sorted(registry["sessions"],
                                       key=lambda r: r["session_id"]), 1):
            state = classify(rec, observed_at, args.stale_seconds)
            checks.append(_chk(
                "L%02d" % i, "session %s" % _sanitize_id(rec["session_id"]),
                True,
                "worktree %s, branch %s, status %s, observed %s"
                % (_sanitize_id(rec["worktree_identity"]),
                   _sanitize_id(rec["branch"]), rec["status"], state),
                warning=(state in ("stale", "future-heartbeat"))))
        norm = _emit(checks, args.format)
        return 5 if norm["overall_status"] == "passed_with_warnings" else 0

    # ---- operations needing a proposal or target -------------------------
    try:
        if op in ("check", "register"):
            proposal = validate_session(_read_json_input(args.input), "proposed session")
        else:
            if not args.session_id:
                sg._bad("%s requires --session-id" % op)
            target = _find(registry, args.session_id)
            if target is None:
                sg._bad("no session with that id is registered")
            proposal = target
        if op == "advance":
            if not args.repo:
                sg._bad("advance requires --repo so the destination HEAD can be verified")
            if not args.previous_commit:
                sg._bad("advance requires --previous-commit")
            if not _OID_RE.match(str(args.previous_commit)):
                sg._bad("--previous-commit must be a full git object id")
        elif args.previous_commit:
            sg._bad("--previous-commit is only valid for advance")
    except ef.SafetyLimitError as exc:
        _err("session_registry: safety limit: %s\n" % ef.sanitize_text(str(exc)))
        return 3
    except ef.ValidationError as exc:
        _err("session_registry: invalid input: %s\n" % ef.sanitize_text(str(exc)))
        return 2

    extra = []
    if args.repo and op in ("check", "register", "resume"):
        try:
            extra = verify_worktree(args.repo, proposal)
        except sg.StoppedError as exc:
            _emit([_chk("W00", "worktree verification", False,
                        ef.sanitize_text(str(exc)), stopped=True)], args.format)
            return 4

    # ---- collisions -------------------------------------------------------
    if op in ("check", "register", "resume"):
        collisions = find_collisions(proposal, registry, observed_at,
                                     args.stale_seconds, ignore_self=(op == "resume"))
    else:
        collisions = []

    if op == "check":
        checks = build_checks(op, proposal, registry, observed_at,
                              args.stale_seconds, rev_before, rev_before,
                              collisions, extra)
        norm = _emit(checks, args.format)
        return {"failed": 1, "stopped": 4,
                "passed_with_warnings": 5}.get(norm["overall_status"], 0)

    # ---- mutating operations ---------------------------------------------
    try:
        with _Lock(args.registry):
            current = read_registry(args.registry)
            if current["revision"] != rev_before:
                raise TransitionError(
                    "the registry changed while this operation was preparing; "
                    "re-read and retry")
            rev_after = current["revision"] + 1
            now_stamp = format_utc(observed_at)

            if op == "register":
                if _find(current, proposal["session_id"]) is not None:
                    raise TransitionError("a session with this id is already registered")
                live = [c for c in collisions if c[3] == "blocking"]
                approval_needed = [c for c in collisions if c[3] == "approval"]
                bad_worktree = [c for c in extra if c["status"] in ("fail", "stopped")]
                if live or bad_worktree:
                    checks = build_checks(op, proposal, current, observed_at,
                                          args.stale_seconds, rev_before, rev_before,
                                          collisions, extra)
                    checks.append(_chk("R00", "registration", False,
                                       "refused: %d blocking collision(s), "
                                       "%d worktree mismatch(es)"
                                       % (len(live), len(bad_worktree))))
                    _emit(checks, args.format)
                    return 1
                if approval_needed:
                    checks = build_checks(op, proposal, current, observed_at,
                                          args.stale_seconds, rev_before, rev_before,
                                          collisions, extra)
                    checks.append(_chk("R00", "registration", False,
                                       "not performed: overlapping stale or ambiguous "
                                       "session(s) require Pedro's decision",
                                       warning=True))
                    _emit(checks, args.format)
                    return 5
                record = dict(proposal)
                record["status"] = "active"
                record["heartbeat_at"] = now_stamp
                current["sessions"].append(record)

            elif op == "heartbeat":
                rec = _find(current, args.session_id)
                if rec["status"] not in ("active", "paused"):
                    raise TransitionError("only an active or paused session may heartbeat")
                before = {k: v for k, v in rec.items() if k != "heartbeat_at"}
                rec["heartbeat_at"] = now_stamp
                after = {k: v for k, v in rec.items() if k != "heartbeat_at"}
                if before != after:
                    raise TransitionError("heartbeat must change only heartbeat_at")

            elif op == "pause":
                rec = _find(current, args.session_id)
                if rec["status"] != "active":
                    raise TransitionError("only an active session may be paused")
                rec["status"] = "paused"

            elif op == "resume":
                rec = _find(current, args.session_id)
                if rec["status"] != "paused":
                    raise TransitionError("only a paused session may be resumed")
                live = [c for c in collisions if c[3] == "blocking"]
                approval_needed = [c for c in collisions if c[3] == "approval"]
                bad_worktree = [c for c in extra if c["status"] in ("fail", "stopped")]
                if live or bad_worktree:
                    checks = build_checks(op, proposal, current, observed_at,
                                          args.stale_seconds, rev_before, rev_before,
                                          collisions, extra)
                    checks.append(_chk("R00", "resume", False,
                                       "refused: %d blocking collision(s), "
                                       "%d worktree mismatch(es)"
                                       % (len(live), len(bad_worktree))))
                    _emit(checks, args.format)
                    return 1
                if approval_needed:
                    checks = build_checks(op, proposal, current, observed_at,
                                          args.stale_seconds, rev_before, rev_before,
                                          collisions, extra)
                    checks.append(_chk("R00", "resume", False,
                                       "not performed: overlapping stale or ambiguous "
                                       "session(s) require Pedro's decision",
                                       warning=True))
                    _emit(checks, args.format)
                    return 5
                rec["status"] = "active"
                rec["heartbeat_at"] = now_stamp

            elif op == "advance":
                rec = _find(current, args.session_id)
                if rec["status"] != "active":
                    raise TransitionError(
                        "only an active session may advance its expected commit")
                if rec["expected_commit"] != args.previous_commit:
                    raise TransitionError(
                        "the supplied previous commit does not match the "
                        "commit recorded on this session")
                repo, identity = sg.resolve_repo(args.repo)
                if identity != rec["worktree_identity"]:
                    raise TransitionError(
                        "the supplied repository is a different worktree "
                        "than the one recorded on this session")
                branch = sg._git_ok(repo, ["rev-parse", "--abbrev-ref", "HEAD"])
                if branch == "HEAD":
                    raise TransitionError(
                        "the repository is in a detached HEAD state")
                if branch != rec["branch"]:
                    raise TransitionError(
                        "the repository is on a different branch than the one "
                        "recorded on this session")
                head = sg._git_ok(repo, ["rev-parse", "HEAD"])
                if not _OID_RE.match(head):
                    raise TransitionError("the repository HEAD is not a full object id")
                if head == args.previous_commit:
                    raise TransitionError(
                        "HEAD has not moved; there is nothing to advance to")
                # Forward-only: the recorded commit must be an ancestor of HEAD,
                # so a rewind, an amend, or a rebase cannot be absorbed silently.
                if not sg.is_ancestor(repo, args.previous_commit, head):
                    raise TransitionError(
                        "the recorded commit is not an ancestor of HEAD; "
                        "advancement is forward-only")
                before_fields = {k: v for k, v in rec.items()
                                 if k not in ("expected_commit", "heartbeat_at")}
                rec["expected_commit"] = head          # destination is HEAD, never supplied
                rec["heartbeat_at"] = now_stamp
                after_fields = {k: v for k, v in rec.items()
                                if k not in ("expected_commit", "heartbeat_at")}
                if before_fields != after_fields:
                    raise TransitionError(
                        "advance must change only expected_commit and heartbeat_at")

            elif op == "close":
                rec = _find(current, args.session_id)
                if rec["status"] == "closed":
                    raise TransitionError("the session is already closed")
                rec["status"] = "closed"      # retained, never deleted

            current["revision"] = rev_after
            write_registry_atomic(args.registry, current)
    except TransitionError as exc:
        checks = build_checks(op, proposal, registry, observed_at,
                              args.stale_seconds, rev_before, rev_before,
                              collisions, extra)
        checks.append(_chk("T00", "state transition", False,
                           ef.sanitize_text(str(exc))))
        _emit(checks, args.format)
        return 1
    except ef.SafetyLimitError as exc:
        _err("session_registry: safety limit: %s\n" % ef.sanitize_text(str(exc)))
        return 3
    except StoppedError as exc:
        _emit([_chk("S00", "registry access", False,
                    ef.sanitize_text(str(exc)), stopped=True)], args.format)
        return 4
    except ef.ValidationError as exc:
        _err("session_registry: invalid input: %s\n" % ef.sanitize_text(str(exc)))
        return 2

    final = read_registry(args.registry)
    checks = build_checks(op, proposal, final, observed_at, args.stale_seconds,
                          rev_before, final["revision"], collisions, extra)
    checks.append(_chk("R00", op, True, "completed; no record was deleted"))
    norm = _emit(checks, args.format)
    return 5 if norm["overall_status"] == "passed_with_warnings" else 0


if __name__ == "__main__":
    sys.exit(main())
