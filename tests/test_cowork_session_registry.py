"""test_cowork_session_registry.py -- tests for the Cowork Session Registry.

Every registry written by these tests lives in pytest's tmp_path (OS temp),
never under the user profile. A guard test asserts the real
``${HOME}/.claude/nova-session-registry.json`` is neither created nor modified.
Synthetic Git repositories are used for worktree verification; no network.
"""
from __future__ import annotations

import ast
import io
import json
import os
import subprocess
import sys
import tokenize
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_TOOL = REPO_ROOT / "tools" / "cowork" / "session_registry.py"
FORMATTER = REPO_ROOT / "tools" / "cowork" / "evidence_formatter.py"

REAL_REGISTRY = Path.home() / ".claude" / "nova-session-registry.json"
CANARY = "NOVA_3O_CANARY_2f7ad91c"
T0 = "2026-09-02T10:00:00Z"


# ------------------------------------------------------------------ helpers

def session(sid="sess-a", wt="nova-dev", branch="feature/ui", write=(), read=(),
            prot=(), commit="a" * 40, started=None, beat=T0, status="active",
            path=None, task="demo", owner="tester"):
    # A record whose heartbeat precedes its start is invalid by design, so a
    # test that backdates the heartbeat backdates the start with it unless it
    # explicitly says otherwise.
    started = started or beat
    return {
        "session_id": sid,
        "worktree_identity": wt,
        "canonical_worktree_path": path or ("/synthetic/%s" % wt),
        "branch": branch,
        "task": task,
        "read_scope": list(read),
        "write_scope": list(write),
        "protected_scope": list(prot),
        "started_at": started,
        "heartbeat_at": beat,
        "status": status,
        "owner": owner,
        "expected_commit": commit,
    }


def init_registry(tmp_path, sessions=(), revision=0, name="registry.json"):
    """Test helper -- production CLI never creates a registry."""
    p = tmp_path / name
    p.write_text(json.dumps({"schema_version": 1, "revision": revision,
                             "sessions": list(sessions)}, indent=2) + "\n",
                 encoding="utf-8")
    return p


def run(op, registry, payload=None, sid=None, at=T0, fmt="json", raw=None,
        repo=None, stale=None, input_file=None):
    cmd = [sys.executable, "-B", str(REGISTRY_TOOL), op,
           "--registry", str(registry), "--format", fmt]
    if at is not None:
        cmd += ["--observed-at", at]
    if sid:
        cmd += ["--session-id", sid]
    if repo:
        cmd += ["--repo", str(repo)]
    if stale is not None:
        cmd += ["--stale-seconds", str(stale)]
    data = b""
    if input_file is not None:
        cmd += ["--input", str(input_file)]
    elif raw is not None:
        data = raw.encode("utf-8") if isinstance(raw, str) else raw
    elif payload is not None:
        data = json.dumps(payload).encode("utf-8")
    p = subprocess.run(cmd, input=data, capture_output=True)
    return (p.returncode,
            p.stdout.decode("utf-8", "replace"),
            p.stderr.decode("utf-8", "replace"))


def status_of(out):
    return json.loads(out)["overall_status"]


def categories(out):
    return {c["label"].split(": ", 1)[1]
            for c in json.loads(out)["checks"]
            if c["label"].startswith("collision: ")}


def load(reg):
    return json.loads(Path(reg).read_text(encoding="utf-8"))


def git(repo, *args, check=True):
    p = subprocess.run(["git", "-C", str(repo)] + list(args),
                       capture_output=True, text=True)
    if check and p.returncode != 0:
        raise AssertionError("git %s failed: %s" % (args[0], p.stderr))
    return p.stdout.strip()


def make_repo(tmp_path, name="wt"):
    repo = tmp_path / name
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    git(repo, "config", "user.email", "t@example.invalid")
    git(repo, "config", "user.name", "T")
    (repo / "a.txt").write_text("x\n", encoding="utf-8")
    git(repo, "add", "--", "a.txt")
    git(repo, "commit", "-q", "-m", "init")
    return repo


# --------------------------------------------------------------- real registry

@pytest.fixture(autouse=True)
def _real_registry_untouched():
    """The real ${HOME} registry must never be created or modified."""
    before = (REAL_REGISTRY.exists(),
              REAL_REGISTRY.read_bytes() if REAL_REGISTRY.exists() else None)
    yield
    after = (REAL_REGISTRY.exists(),
             REAL_REGISTRY.read_bytes() if REAL_REGISTRY.exists() else None)
    assert before == after, "the real session registry was touched"


def test_real_registry_is_absent_and_stays_absent(tmp_path):
    assert not REAL_REGISTRY.exists()
    reg = init_registry(tmp_path)
    run("register", reg, payload=session())
    assert not REAL_REGISTRY.exists()


# ------------------------------------------------------------------- schema

def test_valid_registry_and_session_accepted(tmp_path):
    reg = init_registry(tmp_path)
    rc, out, err = run("register", reg, payload=session())
    assert rc == 0, err + out
    assert status_of(out) == "passed"


def test_unknown_session_field_rejected(tmp_path):
    reg = init_registry(tmp_path)
    s = session()
    s["run_command"] = "rm -rf /"
    rc, _, err = run("register", reg, payload=s)
    assert rc == 2 and "unrecognized field" in err


def test_missing_session_field_rejected(tmp_path):
    reg = init_registry(tmp_path)
    s = session()
    del s["owner"]
    rc, _, err = run("register", reg, payload=s)
    assert rc == 2 and "missing required field" in err


def test_duplicate_session_id_in_registry_rejected(tmp_path):
    dup = [session(sid="same"), session(sid="same", wt="other")]
    reg = init_registry(tmp_path, dup)
    rc, _, err = run("list", reg)
    assert rc == 4 and "duplicate session_id" in err


def test_invalid_timestamp_rejected(tmp_path):
    reg = init_registry(tmp_path)
    rc, _, err = run("register", reg, payload=session(beat="2026-09-02 10:00"))
    assert rc == 2 and "RFC3339 UTC" in err


def test_heartbeat_before_start_rejected(tmp_path):
    reg = init_registry(tmp_path)
    rc, _, err = run("register", reg,
                     payload=session(started=T0, beat="2026-09-01T10:00:00Z"))
    assert rc == 2 and "precedes started_at" in err


def test_invalid_status_rejected(tmp_path):
    reg = init_registry(tmp_path)
    rc, _, err = run("register", reg, payload=session(status="running"))
    assert rc == 2 and "status must be one of" in err


def test_invalid_commit_rejected(tmp_path):
    reg = init_registry(tmp_path)
    rc, _, err = run("register", reg, payload=session(commit="abc123"))
    assert rc == 2 and "object id" in err


def test_invalid_session_id_rejected(tmp_path):
    reg = init_registry(tmp_path)
    rc, _, err = run("register", reg, payload=session(sid="a b/c"))
    assert rc == 2 and "session_id" in err


def test_absolute_scope_rejected(tmp_path):
    reg = init_registry(tmp_path)
    rc, _, err = run("register", reg, payload=session(write=["C:/Windows/x"]))
    assert rc == 2 and "repository-relative" in err


def test_traversal_scope_rejected(tmp_path):
    reg = init_registry(tmp_path)
    rc, _, err = run("register", reg, payload=session(write=["../outside"]))
    assert rc == 2 and "traversal" in err


def test_case_conflicting_scopes_rejected(tmp_path):
    reg = init_registry(tmp_path)
    rc, _, err = run("register", reg, payload=session(write=["UI/**", "ui/**"]))
    assert rc == 2 and "case-conflicting" in err


def test_excessive_scope_count_rejected(tmp_path):
    reg = init_registry(tmp_path)
    rc, _, err = run("register", reg,
                     payload=session(write=["p%d/**" % i for i in range(300)]))
    assert rc == 3 and "maximum" in err


def test_oversized_input_rejected(tmp_path):
    reg = init_registry(tmp_path)
    payload = json.dumps(session())
    payload = payload[:-1] + ',"task":"' + "y" * (1024 * 1024) + '"}'
    rc, _, err = run("register", reg, raw=payload)
    assert rc == 3


def test_nan_rejected(tmp_path):
    reg = init_registry(tmp_path)
    raw = json.dumps(session())[:-1] + ',"extra":NaN}'
    rc, _, err = run("register", reg, raw=raw)
    assert rc == 2


def test_corrupt_registry_is_stopped_and_preserved(tmp_path):
    reg = tmp_path / "registry.json"
    reg.write_text("{ this is not json", encoding="utf-8")
    before = reg.read_bytes()
    rc, _, err = run("list", reg)
    assert rc == 4 and "not valid JSON" in err
    assert reg.read_bytes() == before


def test_unknown_registry_field_rejected(tmp_path):
    reg = tmp_path / "registry.json"
    reg.write_text(json.dumps({"schema_version": 1, "revision": 0,
                               "sessions": [], "extra": 1}), encoding="utf-8")
    rc, _, err = run("list", reg)
    assert rc == 4 and "unrecognized field" in err


# ----------------------------------------------------------------- read-only

def test_list_empty_initialized_registry(tmp_path):
    reg = init_registry(tmp_path)
    rc, out, _ = run("list", reg)
    assert rc == 0 and status_of(out) == "passed"


def test_list_shows_active_paused_stale_closed(tmp_path):
    old = "2026-09-02T08:00:00Z"          # 2h before T0 -> stale at 30min
    reg = init_registry(tmp_path, [
        session(sid="s-active", wt="w1"),
        session(sid="s-paused", wt="w2", status="paused"),
        session(sid="s-stale", wt="w3", beat=old),
        session(sid="s-closed", wt="w4", status="closed"),
    ])
    rc, out, _ = run("list", reg)
    assert rc == 5                        # a stale record is approval-worthy
    text = out
    for sid in ("s-active", "s-paused", "s-stale", "s-closed"):
        assert sid in text
    assert "observed stale" in text
    assert "observed closed" in text


def test_uninitialized_list_and_check_report_safely(tmp_path):
    missing = tmp_path / "nope.json"
    for op in ("list", "check"):
        rc, out, _ = run(op, missing, payload=session())
        assert rc == 0
        assert "no registry file present" in out


def test_uninitialized_mutations_stop(tmp_path):
    missing = tmp_path / "nope.json"
    for op, sid in (("register", None), ("heartbeat", "x"), ("pause", "x"),
                    ("resume", "x"), ("close", "x")):
        rc, _, err = run(op, missing, payload=session(), sid=sid)
        assert rc == 4, op
        assert "separate approved step" in err
    assert not missing.exists()
    assert not (tmp_path / "nope.json.lock").exists()


def test_tool_never_creates_parent_directory(tmp_path):
    nested = tmp_path / "does" / "not" / "exist" / "registry.json"
    rc, _, err = run("register", nested, payload=session())
    assert rc == 4
    assert not (tmp_path / "does").exists()


def test_check_safe_proposal(tmp_path):
    reg = init_registry(tmp_path, [session(sid="other", wt="w1", write=["docs/**"])])
    rc, out, _ = run("check", reg, payload=session(sid="new", wt="w2",
                                                   branch="b2", write=["ui/**"]))
    assert rc == 0 and status_of(out) == "passed"
    assert load(reg)["revision"] == 0          # check never mutates


def test_deterministic_output_at_fixed_observation_time(tmp_path):
    reg = init_registry(tmp_path, [session(sid="sess-a", wt="w1", write=["ui/**"]),
                                   session(sid="sess-b", wt="w2", write=["docs/**"])])
    for fmt in ("json", "markdown"):
        first = run("list", reg, fmt=fmt)[1]
        for _ in range(2):
            assert run("list", reg, fmt=fmt)[1] == first


# ---------------------------------------------------------------- collisions

def test_same_worktree_with_write_collides(tmp_path):
    reg = init_registry(tmp_path, [session(sid="sess-a", wt="w1", write=["ui/**"])])
    rc, out, _ = run("check", reg, payload=session(sid="sess-b", wt="w1",
                                                   branch="other", write=["docs/**"]))
    assert rc == 1
    assert "same-worktree-with-write" in categories(out)


def test_same_branch_different_worktree_collides(tmp_path):
    reg = init_registry(tmp_path, [session(sid="sess-a", wt="w1", branch="shared",
                                           write=["ui/**"])])
    rc, out, _ = run("check", reg, payload=session(sid="sess-b", wt="w2",
                                                   branch="shared", write=["docs/**"]))
    assert rc == 1
    assert "same-branch-different-worktree" in categories(out)


def test_write_write_overlap_collides(tmp_path):
    reg = init_registry(tmp_path, [session(sid="sess-a", wt="w1", branch="b1",
                                           write=["ui/**"])])
    rc, out, _ = run("check", reg, payload=session(sid="sess-b", wt="w2", branch="b2",
                                                   write=["ui/pages/**"]))
    assert rc == 1
    assert "write-write-overlap" in categories(out)


def test_write_read_overlap_collides(tmp_path):
    reg = init_registry(tmp_path, [session(sid="sess-a", wt="w1", branch="b1",
                                           read=["ui/**"])])
    rc, out, _ = run("check", reg, payload=session(sid="sess-b", wt="w2", branch="b2",
                                                   write=["ui/**"]))
    assert rc == 1
    assert "write-read-overlap" in categories(out)


def test_write_protected_overlap_collides(tmp_path):
    reg = init_registry(tmp_path, [session(sid="sess-a", wt="w1", branch="b1",
                                           prot=["core/**"])])
    rc, out, _ = run("check", reg, payload=session(sid="sess-b", wt="w2", branch="b2",
                                                   write=["core/config.py"]))
    assert rc == 1
    assert "write-protected-overlap" in categories(out)


def test_parent_child_overlap_collides(tmp_path):
    reg = init_registry(tmp_path, [session(sid="sess-a", wt="w1", branch="b1",
                                           write=["ui"])])
    rc, out, _ = run("check", reg, payload=session(sid="sess-b", wt="w2", branch="b2",
                                                   write=["ui/pages/journal.py"]))
    assert rc == 1
    assert "write-write-overlap" in categories(out)


def test_windows_case_equivalent_scopes_collide(tmp_path):
    reg = init_registry(tmp_path, [session(sid="sess-a", wt="w1", branch="b1",
                                           write=["UI/Pages/**"])])
    rc, out, _ = run("check", reg, payload=session(sid="sess-b", wt="w2", branch="b2",
                                                   write=["ui/pages/**"]))
    assert rc == 1
    assert "write-write-overlap" in categories(out)


def test_ambiguous_wildcard_is_conservatively_escalated(tmp_path):
    reg = init_registry(tmp_path, [session(sid="sess-a", wt="w1", branch="b1",
                                           write=["ui/*/pages/**"])])
    rc, out, _ = run("check", reg, payload=session(sid="sess-b", wt="w2", branch="b2",
                                                   write=["docs/**"]))
    assert rc == 5                          # approval, not a silent pass
    assert status_of(out) == "passed_with_warnings"


def test_expected_commit_mismatch_collides(tmp_path):
    reg = init_registry(tmp_path, [session(sid="sess-a", wt="w1", commit="a" * 40)])
    rc, out, _ = run("check", reg, payload=session(sid="sess-b", wt="w1",
                                                   commit="b" * 40))
    assert rc == 1
    assert "expected-commit-mismatch" in categories(out)


def test_duplicate_session_id_collides(tmp_path):
    reg = init_registry(tmp_path, [session(sid="same", wt="w1")])
    rc, out, _ = run("check", reg, payload=session(sid="same", wt="w2"))
    assert rc == 1
    assert "duplicate-session-id" in categories(out)


def test_two_read_only_sessions_coexist(tmp_path):
    reg = init_registry(tmp_path, [session(sid="sess-a", wt="w1", branch="b1",
                                           read=["docs/**"])])
    rc, out, _ = run("check", reg, payload=session(sid="sess-b", wt="w2", branch="b2",
                                                   read=["docs/**"]))
    assert rc == 0 and status_of(out) == "passed"


def test_disjoint_scopes_coexist(tmp_path):
    reg = init_registry(tmp_path, [session(sid="dev", wt="w1", branch="b1",
                                           write=["ui/**"])])
    rc, out, _ = run("check", reg, payload=session(sid="ind", wt="w2", branch="b2",
                                                   write=["indicators/**"]))
    assert rc == 0 and status_of(out) == "passed"


def test_closed_record_does_not_collide(tmp_path):
    reg = init_registry(tmp_path, [session(sid="old", wt="w1", write=["ui/**"],
                                           status="closed")])
    rc, out, _ = run("check", reg, payload=session(sid="new", wt="w1",
                                                   write=["ui/**"]))
    assert rc == 0 and status_of(out) == "passed"


def test_stale_collision_is_approval_not_blocking(tmp_path):
    old = "2026-09-02T08:00:00Z"
    reg = init_registry(tmp_path, [session(sid="sess-a", wt="w1", branch="b1",
                                           write=["ui/**"], beat=old)])
    rc, out, _ = run("check", reg, payload=session(sid="sess-b", wt="w2", branch="b2",
                                                   write=["ui/**"]))
    assert rc == 5
    assert status_of(out) == "passed_with_warnings"


def test_stale_threshold_is_configurable(tmp_path):
    old = "2026-09-02T09:50:00Z"           # 10 minutes before T0
    reg = init_registry(tmp_path, [session(sid="sess-a", wt="w1", branch="b1",
                                           write=["ui/**"], beat=old)])
    prop = session(sid="sess-b", wt="w2", branch="b2", write=["ui/**"])
    assert run("check", reg, payload=prop, stale=3600)[0] == 1     # still live
    assert run("check", reg, payload=prop, stale=60)[0] == 5       # now stale


def test_backward_clock_is_reported(tmp_path):
    future = "2026-09-02T12:00:00Z"
    reg = init_registry(tmp_path, [session(sid="sess-a", wt="w1", beat=future,
                                           started=T0)])
    rc, out, _ = run("list", reg)
    assert rc == 5
    assert "clock moved backward" in out


# --------------------------------------------------------------- transitions

def test_register_safe_increments_revision(tmp_path):
    reg = init_registry(tmp_path)
    rc, out, err = run("register", reg, payload=session())
    assert rc == 0, err
    doc = load(reg)
    assert doc["revision"] == 1 and len(doc["sessions"]) == 1


def test_duplicate_register_rejected(tmp_path):
    reg = init_registry(tmp_path, [session(sid="sess-a", wt="w1")])
    rc, out, _ = run("register", reg, payload=session(sid="sess-a", wt="w2"))
    assert rc == 1
    assert load(reg)["revision"] == 0


def test_register_refused_on_blocking_collision(tmp_path):
    reg = init_registry(tmp_path, [session(sid="sess-a", wt="w1", branch="b1",
                                           write=["ui/**"])])
    rc, out, _ = run("register", reg, payload=session(sid="sess-b", wt="w2",
                                                      branch="b2", write=["ui/**"]))
    assert rc == 1
    assert load(reg)["revision"] == 0
    assert len(load(reg)["sessions"]) == 1


def test_register_on_stale_collision_requires_approval_and_does_not_write(tmp_path):
    old = "2026-09-02T08:00:00Z"
    reg = init_registry(tmp_path, [session(sid="sess-a", wt="w1", branch="b1",
                                           write=["ui/**"], beat=old)])
    rc, out, _ = run("register", reg, payload=session(sid="sess-b", wt="w2",
                                                      branch="b2", write=["ui/**"]))
    assert rc == 5
    assert load(reg)["revision"] == 0
    assert len(load(reg)["sessions"]) == 1


def test_heartbeat_changes_only_heartbeat_field(tmp_path):
    reg = init_registry(tmp_path, [session(sid="sess-a", wt="w1",
                                           beat="2026-09-02T09:00:00Z")])
    before = load(reg)["sessions"][0]
    rc, out, err = run("heartbeat", reg, sid="sess-a")
    assert rc == 0, err
    after = load(reg)["sessions"][0]
    assert after["heartbeat_at"] == T0
    assert {k: v for k, v in before.items() if k != "heartbeat_at"} == \
           {k: v for k, v in after.items() if k != "heartbeat_at"}
    assert load(reg)["revision"] == 1


def test_pause_then_resume(tmp_path):
    reg = init_registry(tmp_path, [session(sid="sess-a", wt="w1")])
    assert run("pause", reg, sid="sess-a")[0] == 0
    assert load(reg)["sessions"][0]["status"] == "paused"
    assert run("resume", reg, sid="sess-a")[0] == 0
    assert load(reg)["sessions"][0]["status"] == "active"
    assert load(reg)["revision"] == 2


def test_resume_rejected_on_collision(tmp_path):
    reg = init_registry(tmp_path, [
        session(sid="sess-a", wt="w1", branch="b1", write=["ui/**"], status="paused"),
        session(sid="sess-b", wt="w2", branch="b2", write=["ui/**"]),
    ])
    rc, out, _ = run("resume", reg, sid="sess-a")
    assert rc == 1
    assert load(reg)["sessions"][0]["status"] == "paused"
    assert load(reg)["revision"] == 0


def test_close_retains_the_record(tmp_path):
    reg = init_registry(tmp_path, [session(sid="sess-a", wt="w1")])
    rc, out, _ = run("close", reg, sid="sess-a")
    assert rc == 0
    doc = load(reg)
    assert len(doc["sessions"]) == 1              # retained, never deleted
    assert doc["sessions"][0]["status"] == "closed"


def test_invalid_transitions_rejected(tmp_path):
    reg = init_registry(tmp_path, [session(sid="sess-a", wt="w1", status="closed")])
    for op in ("heartbeat", "pause", "resume", "close"):
        rc, out, _ = run(op, reg, sid="sess-a")
        assert rc == 1, op
    assert load(reg)["revision"] == 0


def test_unknown_session_id_rejected(tmp_path):
    reg = init_registry(tmp_path, [session(sid="sess-a", wt="w1")])
    rc, _, err = run("close", reg, sid="ghost")
    assert rc == 2 and "no session with that id" in err


def test_revision_is_monotonic_across_operations(tmp_path):
    reg = init_registry(tmp_path)
    run("register", reg, payload=session(sid="sess-a", wt="w1"))
    seen = [load(reg)["revision"]]
    for op in ("heartbeat", "pause", "resume", "close"):
        run(op, reg, sid="sess-a")
        seen.append(load(reg)["revision"])
    assert seen == sorted(seen) and len(set(seen)) == len(seen)


def test_no_prune_or_delete_operation_exists():
    """The operation list must not offer a destructive verb.

    The check targets the choices themselves, not arbitrary words: the tool's
    own description legitimately contains "Never deletes a record."
    """
    for banned in ("prune", "delete", "clear", "force", "override", "repair", "patch"):
        p = subprocess.run([sys.executable, "-B", str(REGISTRY_TOOL), banned,
                            "--registry", "x", "--format", "json"],
                           capture_output=True, text=True)
        assert p.returncode == 2, banned          # rejected as an invalid choice

    help_text = subprocess.run(
        [sys.executable, "-B", str(REGISTRY_TOOL), "--help"],
        capture_output=True, text=True).stdout
    # The usage line has several brace groups (--format has one too); pick the
    # one that lists the positional operations.
    import re as _re
    # argparse prints the group twice (usage line and positional section).
    groups = {g for g in _re.findall(r"\{([^}]*)\}", help_text) if "list" in g}
    assert len(groups) == 1, groups
    offered = sorted(o.strip() for o in groups.pop().split(","))
    assert offered == ["check", "close", "heartbeat", "list", "pause",
                       "register", "resume"]


# ---------------------------------------------------------------- atomicity

def test_lock_contention_stops(tmp_path):
    reg = init_registry(tmp_path)
    lock = Path(str(reg) + ".lock")
    lock.write_text("99999", encoding="utf-8")     # a foreign lock
    before = reg.read_bytes()
    rc, out, err = run("register", reg, payload=session())
    assert rc == 4
    assert "locked" in (out + err)
    assert lock.exists()                            # never broken automatically
    assert reg.read_bytes() == before
    lock.unlink()


def test_foreign_lock_is_not_removed(tmp_path):
    reg = init_registry(tmp_path)
    lock = Path(str(reg) + ".lock")
    lock.write_text("12345", encoding="utf-8")
    run("register", reg, payload=session())
    assert lock.read_text(encoding="utf-8") == "12345"
    lock.unlink()


def test_successful_mutation_removes_its_own_lock(tmp_path):
    reg = init_registry(tmp_path)
    assert run("register", reg, payload=session())[0] == 0
    assert not Path(str(reg) + ".lock").exists()


def test_no_temp_residue_after_success_or_failure(tmp_path):
    reg = init_registry(tmp_path, [session(sid="sess-a", wt="w1", write=["ui/**"])])
    run("register", reg, payload=session(sid="sess-b", wt="w2", branch="b2",
                                         write=["ui/**"]))        # refused
    run("register", reg, payload=session(sid="c", wt="w3", branch="b3",
                                         write=["docs/**"]))      # accepted
    leftovers = [p.name for p in tmp_path.iterdir()
                 if p.name.startswith(".nova-registry-") or p.name.endswith(".tmp")]
    assert leftovers == []


def test_registry_is_never_partial_json(tmp_path):
    reg = init_registry(tmp_path)
    for i in range(5):
        run("register", reg, payload=session(sid="sess-%d" % i, wt="w%d" % i,
                                             branch="b%d" % i,
                                             write=["area%d/**" % i]))
        json.loads(reg.read_text(encoding="utf-8"))    # must always parse
    assert len(load(reg)["sessions"]) == 5


def test_revision_race_is_detected(tmp_path):
    """A stale in-flight revision must not silently overwrite a newer registry."""
    sys.path.insert(0, str(REGISTRY_TOOL.parent))
    try:
        import session_registry as sr
    finally:
        sys.path.pop(0)
    reg = init_registry(tmp_path, [session(sid="sess-a", wt="w1")], revision=7)
    doc = sr.read_registry(str(reg))
    assert doc["revision"] == 7
    # Someone else advances the registry underneath us.
    init_registry(tmp_path, [session(sid="sess-a", wt="w1")], revision=8)
    reread = sr.read_registry(str(reg))
    assert reread["revision"] == 8 != doc["revision"]


def test_original_preserved_when_validation_fails_mid_write(tmp_path, monkeypatch):
    sys.path.insert(0, str(REGISTRY_TOOL.parent))
    try:
        import session_registry as sr
    finally:
        sys.path.pop(0)
    reg = init_registry(tmp_path, [session(sid="sess-a", wt="w1")], revision=3)
    before = Path(reg).read_bytes()
    bad = {"schema_version": 1, "revision": 4,
           "sessions": [session(sid="sess-a"), session(sid="sess-a")]}     # duplicate id
    with pytest.raises(Exception):
        sr.write_registry_atomic(str(reg), bad)
    assert Path(reg).read_bytes() == before


def test_original_preserved_when_replace_fails(tmp_path, monkeypatch):
    sys.path.insert(0, str(REGISTRY_TOOL.parent))
    try:
        import session_registry as sr
    finally:
        sys.path.pop(0)
    reg = init_registry(tmp_path, [session(sid="sess-a", wt="w1")], revision=3)
    before = Path(reg).read_bytes()

    def boom(src, dst):
        raise OSError("simulated replace failure")

    monkeypatch.setattr(sr.os, "replace", boom)
    good = {"schema_version": 1, "revision": 4, "sessions": [session(sid="sess-b")]}
    with pytest.raises(OSError):
        sr.write_registry_atomic(str(reg), good)
    assert Path(reg).read_bytes() == before
    leftovers = [p.name for p in tmp_path.iterdir()
                 if p.name.startswith(".nova-registry-")]
    assert leftovers == []


# ----------------------------------------------------------------- worktree

def test_worktree_verification_matches(tmp_path):
    repo = make_repo(tmp_path)
    head = git(repo, "rev-parse", "HEAD")
    reg = init_registry(tmp_path)
    s = session(sid="sess-a", wt=repo.name, branch="main", commit=head)
    rc, out, err = run("check", reg, payload=s, repo=repo)
    assert rc == 0, err + out


def test_worktree_wrong_branch_blocks(tmp_path):
    repo = make_repo(tmp_path)
    head = git(repo, "rev-parse", "HEAD")
    reg = init_registry(tmp_path)
    s = session(sid="sess-a", wt=repo.name, branch="other", commit=head)
    rc, out, _ = run("register", reg, payload=s, repo=repo)
    assert rc == 1
    assert load(reg)["revision"] == 0


def test_worktree_moved_head_blocks_registration(tmp_path):
    repo = make_repo(tmp_path)
    reg = init_registry(tmp_path)
    s = session(sid="sess-a", wt=repo.name, branch="main", commit="0" * 40)
    rc, out, _ = run("register", reg, payload=s, repo=repo)
    assert rc == 1
    assert load(reg)["revision"] == 0


def test_worktree_wrong_identity_blocks(tmp_path):
    repo = make_repo(tmp_path)
    head = git(repo, "rev-parse", "HEAD")
    reg = init_registry(tmp_path)
    s = session(sid="sess-a", wt="not-this-worktree", branch="main", commit=head)
    rc, out, _ = run("register", reg, payload=s, repo=repo)
    assert rc == 1


def test_worktree_observation_does_not_mutate_the_repository(tmp_path):
    repo = make_repo(tmp_path)
    head = git(repo, "rev-parse", "HEAD")
    reg = init_registry(tmp_path)
    fetch_head = repo / ".git" / "FETCH_HEAD"
    before = (fetch_head.exists(), git(repo, "show-ref"),
              (repo / ".git" / "index").read_bytes(),
              (repo / ".git" / "config").read_bytes(),
              git(repo, "status", "--porcelain", "-uall"))
    run("check", reg, payload=session(sid="sess-a", wt=repo.name, branch="main",
                                      commit=head), repo=repo)
    after = (fetch_head.exists(), git(repo, "show-ref"),
             (repo / ".git" / "index").read_bytes(),
             (repo / ".git" / "config").read_bytes(),
             git(repo, "status", "--porcelain", "-uall"))
    assert before == after


def test_missing_repo_is_stopped(tmp_path):
    reg = init_registry(tmp_path)
    rc, out, _ = run("check", reg, payload=session(), repo=tmp_path / "nope")
    assert rc == 4
    assert status_of(out) == "stopped"


# ----------------------------------------------------------------- security

def test_credential_shaped_record_is_rejected(tmp_path):
    reg = init_registry(tmp_path)
    rc, out, err = run("register", reg,
                       payload=session(task="api_key=%s" % CANARY))
    assert rc == 2
    assert CANARY not in out and CANARY not in err
    assert load(reg)["revision"] == 0


def test_canary_never_appears_in_output(tmp_path):
    reg = init_registry(tmp_path)
    rc, out, err = run("register", reg, raw='{"bad": "%s"' % CANARY)
    assert CANARY not in out and CANARY not in err


def test_username_and_machine_path_absent_from_output(tmp_path):
    reg = init_registry(tmp_path, [session(sid="sess-a", wt="w1",
                                           path=str(Path.home() / "repo"))])
    rc, out, err = run("list", reg)
    user = Path.home().name
    assert user not in out and user not in err


def test_registry_contents_are_not_dumped_wholesale(tmp_path):
    reg = init_registry(tmp_path, [session(sid="sess-a", wt="w1", owner="secret-owner-x",
                                           task="a very distinctive task string")])
    rc, out, _ = run("list", reg)
    assert "a very distinctive task string" not in out
    assert "secret-owner-x" not in out


def test_output_shows_required_fields(tmp_path):
    reg = init_registry(tmp_path, [session(sid="sess-a", wt="w1", branch="b1",
                                           write=["ui/**"])])
    rc, out, _ = run("check", reg, payload=session(sid="sess-b", wt="w1",
                                                   write=["ui/**"]), fmt="markdown")
    for token in ("operation", "registry revision", "collision", "session"):
        assert token in out.lower()


def test_no_output_file_option():
    p = subprocess.run([sys.executable, "-B", str(REGISTRY_TOOL), "--help"],
                       capture_output=True, text=True)
    assert p.returncode == 0
    for flag in ("--output", "--outfile", "--write"):
        assert flag not in p.stdout


# -------------------------------------------------------------- integration

def test_output_validates_through_the_formatter(tmp_path):
    reg = init_registry(tmp_path, [session(sid="sess-a", wt="w1")])
    rc, out, _ = run("list", reg)
    parsed = json.loads(out)
    doc = {"schema_version": 1, "phase": parsed["phase"],
           "scope": parsed["scope"], "checks": parsed["checks"]}
    p = subprocess.run([sys.executable, "-B", str(FORMATTER), "--format", "json"],
                       input=json.dumps(doc).encode("utf-8"), capture_output=True)
    assert p.returncode == 0
    assert json.loads(p.stdout.decode("utf-8"))["overall_status"] == parsed["overall_status"]


def test_repeated_fixed_time_observations_are_identical(tmp_path):
    reg = init_registry(tmp_path, [session(sid="sess-a", wt="w1", write=["ui/**"])])
    prop = session(sid="sess-b", wt="w2", branch="b2", write=["ui/**"])
    outs = {run("check", reg, payload=prop)[1] for _ in range(3)}
    assert len(outs) == 1


# ---------------------------------------------------------------- static

def _executable_source(path):
    src = Path(path).read_text(encoding="utf-8")
    tree = ast.parse(src)
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)):
            ds = ast.get_docstring(node, clean=False)
            if ds:
                docstrings.add(ds)
    kept = []
    for tok in tokenize.generate_tokens(io.StringIO(src).readline):
        if tok.type == tokenize.COMMENT:
            continue
        if tok.type == tokenize.STRING:
            try:
                value = ast.literal_eval(tok.string)
            except Exception:
                value = None
            if isinstance(value, str) and value in docstrings:
                continue
        kept.append(tok.string)
    return "\n".join(kept)


def test_no_eval_exec_shell_or_network():
    body = _executable_source(REGISTRY_TOOL)
    for forbidden in ("shell=True", "os.system", "popen", "eval(", "exec(",
                      "socket", "urllib", "requests", "httpx"):
        assert forbidden not in body, forbidden


def test_no_subprocess_use_of_its_own():
    """Git access happens only through the Staleness Guard's read-only observer."""
    body = _executable_source(REGISTRY_TOOL)
    assert "subprocess" not in body


def test_no_delete_or_prune_helper_in_source():
    body = _executable_source(REGISTRY_TOOL)
    for banned in ("def prune", "def delete", "def clear_", "def force_",
                   "def repair", "sessions.remove", "sessions.pop", "del "):
        assert banned not in body, banned


def test_stdlib_only():
    src = REGISTRY_TOOL.read_text(encoding="utf-8")
    mods = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Import):
            mods.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods.add(node.module.split(".")[0])
    third = [m for m in mods if m not in sys.stdlib_module_names
             and m not in ("__future__", "evidence_formatter", "staleness_guard")]
    assert third == [], third


def test_reuses_formatter_and_staleness_guard():
    body = _executable_source(REGISTRY_TOOL)
    assert "evidence_formatter" in body and "staleness_guard" in body
    for reused in ("normalize", "render_json", "render_markdown", "sanitize_text",
                   "enforce_limits", "resolve_repo", "observe"):
        assert reused in body, reused


def test_no_environment_value_exposure():
    body = _executable_source(REGISTRY_TOOL)
    for banned in ("os.environ", "getenv"):
        assert banned not in body, banned
