"""test_cowork_worktree_bootstrap_validator.py -- tests for the bootstrap validator.

Every repository, worktree, registry, permission file, and submodule used here
is synthetic and lives under pytest's tmp_path. An autouse fixture proves the
real ${HOME} session registry stays byte-identical across the whole suite.
"""
from __future__ import annotations

import ast
import hashlib
import io
import json
import os
import subprocess
import sys
import tokenize
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = REPO_ROOT / "tools" / "cowork" / "worktree_bootstrap_validator.py"
FORMATTER = REPO_ROOT / "tools" / "cowork" / "evidence_formatter.py"
REAL_REGISTRY = Path.home() / ".claude" / "nova-session-registry.json"

CANARY = "NOVA_3R_CANARY_6b1e04ff"
T0 = "2026-09-02T10:00:00Z"


# ------------------------------------------------------------------ helpers

def git(repo, *args, check=True):
    p = subprocess.run(["git", "-C", str(repo)] + list(args),
                       capture_output=True, text=True)
    if check and p.returncode != 0:
        raise AssertionError("git %s failed: %s" % (args[0], p.stderr))
    return p.stdout.strip()


def make_repo(tmp_path, name="nova-demo"):
    repo = tmp_path / name
    repo.mkdir(parents=True)
    git(repo, "init", "-q", "-b", "work")
    git(repo, "config", "user.email", "t@example.invalid")
    git(repo, "config", "user.name", "T")
    (repo / ".gitignore").write_text(
        "data/*.json\n!data/keep_settings.json\ndata/_*.js\n"
        ".claude/settings.local.json\n", encoding="utf-8")
    (repo / "CLAUDE.md").write_text("# guide\n", encoding="utf-8")
    (repo / "app.py").write_text("x = 1\n", encoding="utf-8")
    (repo / "nova_knowledge_core").mkdir()
    (repo / "nova_knowledge_core" / "rules.md").write_text("r\n", encoding="utf-8")
    git(repo, "add", "--", ".gitignore", "CLAUDE.md", "app.py",
        "nova_knowledge_core/rules.md")
    git(repo, "commit", "-q", "-m", "init")
    return repo


def write_perms(repo, allow=3, ask=2, deny=1, dupes=False):
    d = repo / ".claude"
    d.mkdir(exist_ok=True)
    perms = {"allow": ["a%d" % i for i in range(allow)],
             "ask": ["k%d" % i for i in range(ask)],
             "deny": ["d%d" % i for i in range(deny)]}
    if dupes and perms["allow"]:
        perms["allow"][-1] = perms["allow"][0]
    p = d / "settings.local.json"
    p.write_text(json.dumps({"permissions": perms}, indent=2) + "\n", encoding="utf-8")
    return p


def sha256_file(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def manifest(repo, **over):
    m = {
        "schema_version": 1,
        "worktree_identity": repo.name,
        "branch": "work",
        "head": git(repo, "rev-parse", "HEAD"),
        "require_clean_index": True,
        "require_clean_worktree": True,
    }
    m.update(over)
    return m


def run(tmp_path, repo, man, fmt="json", raw=None, name="manifest.json"):
    mpath = tmp_path / name
    mpath.write_text(raw if raw is not None else json.dumps(man, indent=2),
                     encoding="utf-8")
    p = subprocess.run([sys.executable, "-B", str(VALIDATOR),
                        "--manifest", str(mpath), "--repo", str(repo),
                        "--format", fmt], capture_output=True)
    return (p.returncode, p.stdout.decode("utf-8", "replace"),
            p.stderr.decode("utf-8", "replace"))


def ids(out):
    return {c["id"]: c["status"] for c in json.loads(out)["checks"]}


def status_of(out):
    return json.loads(out)["overall_status"]


@pytest.fixture(autouse=True)
def _real_registry_untouched():
    before = (REAL_REGISTRY.exists(),
              REAL_REGISTRY.read_bytes() if REAL_REGISTRY.exists() else None)
    yield
    after = (REAL_REGISTRY.exists(),
             REAL_REGISTRY.read_bytes() if REAL_REGISTRY.exists() else None)
    assert before == after, "the real session registry was touched"


# ------------------------------------------------------------------ identity

def test_fully_valid_bootstrap(tmp_path):
    repo = make_repo(tmp_path)
    rc, out, err = run(tmp_path, repo, manifest(repo))
    assert rc == 0, err + out
    assert status_of(out) == "passed"


def test_wrong_worktree_identity(tmp_path):
    repo = make_repo(tmp_path)
    rc, out, _ = run(tmp_path, repo, manifest(repo, worktree_identity="other"))
    assert rc == 1 and ids(out)["A2"] == "fail"


def test_wrong_canonical_path(tmp_path):
    repo = make_repo(tmp_path)
    m = manifest(repo, canonical_worktree_path=str(tmp_path / "elsewhere"))
    rc, out, _ = run(tmp_path, repo, m)
    assert rc == 1 and ids(out)["A3"] == "fail"


def test_correct_canonical_path_passes(tmp_path):
    repo = make_repo(tmp_path)
    m = manifest(repo, canonical_worktree_path=str(repo))
    rc, out, err = run(tmp_path, repo, m)
    assert rc == 0, err + out
    assert ids(out)["A3"] == "pass"


def test_wrong_branch(tmp_path):
    repo = make_repo(tmp_path)
    rc, out, _ = run(tmp_path, repo, manifest(repo, branch="nope"))
    assert rc == 1 and ids(out)["A4"] == "fail"


def test_detached_head_fails(tmp_path):
    repo = make_repo(tmp_path)
    m = manifest(repo)
    git(repo, "checkout", "-q", "--detach")
    rc, out, _ = run(tmp_path, repo, m)
    assert rc == 1
    assert ids(out)["A4"] == "fail"
    assert "detached HEAD" in out


def test_moved_head_fails(tmp_path):
    repo = make_repo(tmp_path)
    m = manifest(repo)
    (repo / "app.py").write_text("y = 2\n", encoding="utf-8")
    git(repo, "add", "--", "app.py")
    git(repo, "commit", "-q", "-m", "moves head")
    rc, out, _ = run(tmp_path, repo, m)
    assert rc == 1 and ids(out)["A5"] == "fail"


def test_git_common_dir_matches_for_a_linked_worktree(tmp_path):
    repo = make_repo(tmp_path)
    linked = tmp_path / "linked"
    git(repo, "worktree", "add", "-q", "-b", "side", str(linked))
    try:
        m = manifest(linked, worktree_identity="linked", branch="side",
                     head=git(linked, "rev-parse", "HEAD"),
                     git_common_dir_identity=os.path.join(repo.name, ".git"))
        rc, out, err = run(tmp_path, linked, m)
        assert rc == 0, err + out
        assert ids(out)["A6"] == "pass"
    finally:
        git(repo, "worktree", "remove", "--force", str(linked))


def test_wrong_git_common_dir_fails(tmp_path):
    repo = make_repo(tmp_path)
    m = manifest(repo, git_common_dir_identity="some-other-repo/.git")
    rc, out, _ = run(tmp_path, repo, m)
    assert rc == 1 and ids(out)["A6"] == "fail"


def test_nested_path_resolves_to_its_top_level(tmp_path):
    """A subdirectory of a checkout is not its own worktree root."""
    repo = make_repo(tmp_path)
    sub = repo / "nova_knowledge_core"
    m = manifest(repo)
    rc, out, _ = run(tmp_path, sub, m)
    assert rc == 1 and ids(out)["A7"] == "fail"


def test_non_repository_is_stopped(tmp_path):
    plain = tmp_path / "plain"
    plain.mkdir()
    repo = make_repo(tmp_path)
    rc, out, _ = run(tmp_path, plain, manifest(repo))
    assert rc == 4 and status_of(out) == "stopped"


# --------------------------------------------------------------- cleanliness

def test_dirty_index_fails(tmp_path):
    repo = make_repo(tmp_path)
    (repo / "new.py").write_text("n\n", encoding="utf-8")
    git(repo, "add", "--", "new.py")
    rc, out, _ = run(tmp_path, repo, manifest(repo))
    assert rc == 1 and ids(out)["B1"] == "fail"


def test_tracked_modification_fails(tmp_path):
    repo = make_repo(tmp_path)
    (repo / "app.py").write_text("dirty\n", encoding="utf-8")
    rc, out, _ = run(tmp_path, repo, manifest(repo))
    assert rc == 1 and ids(out)["B2"] == "fail"


def test_visible_untracked_artifact_fails(tmp_path):
    repo = make_repo(tmp_path)
    (repo / "surprise.txt").write_text("s\n", encoding="utf-8")
    rc, out, _ = run(tmp_path, repo, manifest(repo))
    assert rc == 1 and ids(out)["B2"] == "fail"


def test_ignored_artifact_does_not_fail_cleanliness(tmp_path):
    repo = make_repo(tmp_path)
    (repo / "data").mkdir()
    (repo / "data" / "runtime.json").write_text("{}\n", encoding="utf-8")
    rc, out, err = run(tmp_path, repo, manifest(repo))
    assert rc == 0, err + out
    assert ids(out)["B2"] == "pass"


def test_interrupted_git_operation_marker_fails(tmp_path):
    repo = make_repo(tmp_path)
    (repo / ".git" / "MERGE_HEAD").write_text("0" * 40 + "\n", encoding="utf-8")
    rc, out, _ = run(tmp_path, repo, manifest(repo))
    assert rc == 1
    assert ids(out)["B3"] == "fail"
    assert "MERGE_HEAD" in out


def test_validation_creates_no_lock(tmp_path):
    repo = make_repo(tmp_path)
    run(tmp_path, repo, manifest(repo))
    assert not (repo / ".git" / "index.lock").exists()


# --------------------------------------------------------------- blob checks

def test_tracked_blob_match(tmp_path):
    repo = make_repo(tmp_path)
    blob = git(repo, "rev-parse", "HEAD:CLAUDE.md")
    rc, out, err = run(tmp_path, repo, manifest(repo, tracked_blobs={"CLAUDE.md": blob}))
    assert rc == 0, err + out
    assert ids(out)["C01"] == "pass"


def test_tracked_blob_mismatch(tmp_path):
    repo = make_repo(tmp_path)
    rc, out, _ = run(tmp_path, repo, manifest(repo, tracked_blobs={"CLAUDE.md": "0" * 40}))
    assert rc == 1 and ids(out)["C01"] == "fail"


def test_crlf_worktree_bytes_still_match_the_blob(tmp_path):
    """Raw file bytes differ under CRLF; the blob id does not."""
    repo = make_repo(tmp_path)
    blob = git(repo, "rev-parse", "HEAD:CLAUDE.md")
    raw_before = (repo / "CLAUDE.md").read_bytes()
    (repo / "CLAUDE.md").write_bytes(raw_before.replace(b"\n", b"\r\n"))
    assert (repo / "CLAUDE.md").read_bytes() != raw_before      # bytes changed
    git(repo, "config", "core.autocrlf", "true")
    rc, out, err = run(tmp_path, repo, manifest(
        repo, require_clean_worktree=False, tracked_blobs={"CLAUDE.md": blob}))
    assert ids(out)["C01"] == "pass", out


# ------------------------------------------------------------ local + perms

def test_missing_local_permission_file(tmp_path):
    repo = make_repo(tmp_path)
    m = manifest(repo, local_ignored_files={
        ".claude/settings.local.json": {"must_be_json": True}})
    rc, out, _ = run(tmp_path, repo, m)
    assert rc == 1 and ids(out)["D01a"] == "fail"


def test_permission_hash_mismatch(tmp_path):
    repo = make_repo(tmp_path)
    write_perms(repo)
    m = manifest(repo, local_ignored_files={
        ".claude/settings.local.json": {"sha256": "0" * 64}})
    rc, out, _ = run(tmp_path, repo, m)
    assert rc == 1 and ids(out)["D01b"] == "fail"


def test_permission_hash_match(tmp_path):
    repo = make_repo(tmp_path)
    p = write_perms(repo)
    m = manifest(repo, local_ignored_files={
        ".claude/settings.local.json": {
            "sha256": sha256_file(p), "must_be_json": True,
            "must_be_ignored": True, "must_not_be_tracked": True}})
    rc, out, err = run(tmp_path, repo, m)
    assert rc == 0, err + out
    for k in ("D01a", "D01b", "D01c", "D01d", "D01e"):
        assert ids(out)[k] == "pass", k


def test_permission_count_drift(tmp_path):
    repo = make_repo(tmp_path)
    write_perms(repo, allow=3, ask=2, deny=1)
    m = manifest(repo, permission_state={
        "path": ".claude/settings.local.json", "allow": 99, "ask": 2, "deny": 1})
    rc, out, _ = run(tmp_path, repo, m)
    assert rc == 1 and ids(out)["E2"] == "fail"


def test_duplicate_permission_entries_detected(tmp_path):
    repo = make_repo(tmp_path)
    write_perms(repo, allow=3, dupes=True)
    m = manifest(repo, permission_state={
        "path": ".claude/settings.local.json", "require_no_duplicates": True})
    rc, out, _ = run(tmp_path, repo, m)
    assert rc == 1 and ids(out)["E3"] == "fail"


def test_permission_file_not_ignored_detected(tmp_path):
    # A machine-level ignore file may already cover the real permission path in
    # every repository, so a synthetic local file proves the "declared as
    # ignored but is not" branch. The check itself is path-agnostic.
    repo = make_repo(tmp_path)
    (repo / "settings_local_stand_in.json").write_text("{}\n", encoding="utf-8")
    m = manifest(repo, require_clean_worktree=False, local_ignored_files={
        "settings_local_stand_in.json": {"must_be_ignored": True}})
    rc, out, _ = run(tmp_path, repo, m)
    assert rc == 1 and ids(out)["D01d"] == "fail"


def test_permission_file_ignored_passes(tmp_path):
    repo = make_repo(tmp_path)
    write_perms(repo)
    m = manifest(repo, require_clean_worktree=False, local_ignored_files={
        ".claude/settings.local.json": {"must_be_ignored": True,
                                        "must_not_be_tracked": True}})
    rc, out, _ = run(tmp_path, repo, m)
    assert rc == 0 and ids(out)["D01d"] == "pass" and ids(out)["D01e"] == "pass"


def test_permission_file_accidentally_tracked_detected(tmp_path):
    repo = make_repo(tmp_path)
    write_perms(repo)
    git(repo, "add", "-f", "--", ".claude/settings.local.json")
    git(repo, "commit", "-q", "-m", "oops tracked")
    m = manifest(repo, head=git(repo, "rev-parse", "HEAD"),
                 local_ignored_files={
                     ".claude/settings.local.json": {"must_not_be_tracked": True}})
    rc, out, _ = run(tmp_path, repo, m)
    assert rc == 1 and ids(out)["D01e"] == "fail"


def test_permission_values_are_never_printed(tmp_path):
    repo = make_repo(tmp_path)
    d = repo / ".claude"
    d.mkdir(exist_ok=True)
    (d / "settings.local.json").write_text(
        json.dumps({"permissions": {"allow": ["Bash(%s)" % CANARY],
                                    "ask": [], "deny": []}}), encoding="utf-8")
    m = manifest(repo, permission_state={
        "path": ".claude/settings.local.json", "allow": 1, "ask": 0, "deny": 0})
    rc, out, err = run(tmp_path, repo, m)
    assert CANARY not in out and CANARY not in err


# ------------------------------------------------------------------- casing

def test_lowercase_prefix_passes(tmp_path):
    repo = make_repo(tmp_path)
    m = manifest(repo, casing_rules={
        "required_prefixes": ["nova_knowledge_core/"],
        "forbidden_prefixes": ["NOVA_KNOWLEDGE_CORE/"],
        "forbid_normalized_collisions": True})
    rc, out, err = run(tmp_path, repo, m)
    assert rc == 0, err + out
    assert ids(out)["F01"] == "pass" and ids(out)["Fx01"] == "pass"


def test_uppercase_tracked_prefix_fails(tmp_path):
    repo = make_repo(tmp_path, name="upper")
    git(repo, "mv", "nova_knowledge_core", "TMP_KC")
    git(repo, "mv", "TMP_KC", "NOVA_KNOWLEDGE_CORE")
    git(repo, "commit", "-q", "-m", "uppercase")
    m = manifest(repo, head=git(repo, "rev-parse", "HEAD"), casing_rules={
        "required_prefixes": ["nova_knowledge_core/"],
        "forbidden_prefixes": ["NOVA_KNOWLEDGE_CORE/"]})
    rc, out, _ = run(tmp_path, repo, m)
    assert rc == 1
    assert ids(out)["F01"] == "fail" and ids(out)["Fx01"] == "fail"


def test_case_normalized_collision_fails(tmp_path):
    repo = make_repo(tmp_path, name="collide")
    # Two index entries differing only in case, created directly in the index.
    blob = git(repo, "rev-parse", "HEAD:app.py")
    git(repo, "update-index", "--add", "--cacheinfo", "100644,%s,APP.py" % blob)
    m = manifest(repo, require_clean_index=False, require_clean_worktree=False,
                 casing_rules={"forbid_normalized_collisions": True})
    rc, out, _ = run(tmp_path, repo, m)
    assert rc == 1 and ids(out)["F00"] == "fail"


def test_casing_uses_index_paths_not_filesystem(tmp_path):
    """The check reads git's index, so Windows case-insensitivity cannot mask it."""
    repo = make_repo(tmp_path)
    tracked = git(repo, "ls-files")
    assert "nova_knowledge_core/rules.md" in tracked
    m = manifest(repo, casing_rules={"forbidden_prefixes": ["NOVA_KNOWLEDGE_CORE/"]})
    rc, out, err = run(tmp_path, repo, m)
    assert rc == 0, err + out


# --------------------------------------------------------------- submodules

def _add_submodule(tmp_path, parent, name="sub"):
    child = make_repo(tmp_path, name=name + "-origin")
    subprocess.run(["git", "-C", str(parent), "-c", "protocol.file.allow=always",
                    "submodule", "add", "-q", str(child), name],
                   check=True, capture_output=True)
    git(parent, "commit", "-q", "-m", "add submodule")
    return child


def test_correct_populated_submodule(tmp_path):
    repo = make_repo(tmp_path)
    _add_submodule(tmp_path, repo)
    link = git(repo, "ls-files", "--stage", "--", "sub").split()[1]
    sub_head = git(repo / "sub", "rev-parse", "HEAD")
    m = manifest(repo, head=git(repo, "rev-parse", "HEAD"),
                 submodules={"sub": {"gitlink": link, "populated": True,
                                     "head": sub_head, "require_clean": True}})
    rc, out, err = run(tmp_path, repo, m)
    assert rc == 0, err + out
    for k in ("G01a", "G01b", "G01c", "G01d"):
        assert ids(out)[k] == "pass", k


def test_wrong_gitlink_fails(tmp_path):
    repo = make_repo(tmp_path)
    _add_submodule(tmp_path, repo)
    m = manifest(repo, head=git(repo, "rev-parse", "HEAD"),
                 submodules={"sub": {"gitlink": "0" * 40, "populated": True}})
    rc, out, _ = run(tmp_path, repo, m)
    assert rc == 1 and ids(out)["G01a"] == "fail"


def test_dirty_populated_submodule_fails(tmp_path):
    repo = make_repo(tmp_path)
    _add_submodule(tmp_path, repo)
    (repo / "sub" / "app.py").write_text("dirty\n", encoding="utf-8")
    link = git(repo, "ls-files", "--stage", "--", "sub").split()[1]
    m = manifest(repo, head=git(repo, "rev-parse", "HEAD"),
                 require_clean_worktree=False,
                 submodules={"sub": {"gitlink": link, "populated": True,
                                     "require_clean": True}})
    rc, out, _ = run(tmp_path, repo, m)
    assert rc == 1 and ids(out)["G01d"] == "fail"


def test_unpopulated_submodule_is_valid_when_declared(tmp_path):
    repo = make_repo(tmp_path)
    fake = "1" * 40
    git(repo, "update-index", "--add", "--cacheinfo", "160000,%s,mcp/tool" % fake)
    git(repo, "commit", "-q", "-m", "gitlink only")
    # Mirrors the real foundation worktree: the submodule directory exists but
    # was never checked out, which git reports as a clean worktree.
    (repo / "mcp" / "tool").mkdir(parents=True)
    m = manifest(repo, head=git(repo, "rev-parse", "HEAD"),
                 submodules={"mcp/tool": {"gitlink": fake, "populated": False}})
    rc, out, err = run(tmp_path, repo, m)
    assert rc == 0, err + out
    assert ids(out)["G01b"] == "pass"


def test_unexpected_population_state_fails(tmp_path):
    repo = make_repo(tmp_path)
    fake = "1" * 40
    git(repo, "update-index", "--add", "--cacheinfo", "160000,%s,mcp/tool" % fake)
    git(repo, "commit", "-q", "-m", "gitlink only")
    m = manifest(repo, head=git(repo, "rev-parse", "HEAD"),
                 submodules={"mcp/tool": {"gitlink": fake, "populated": True}})
    rc, out, _ = run(tmp_path, repo, m)
    assert rc == 1 and ids(out)["G01b"] == "fail"


def test_missing_gitlink_fails(tmp_path):
    repo = make_repo(tmp_path)
    m = manifest(repo, submodules={"absent/mod": {"gitlink": "2" * 40}})
    rc, out, _ = run(tmp_path, repo, m)
    assert rc == 1 and ids(out)["G01a"] == "fail"


# -------------------------------------------------------- forbidden artifacts

def test_forbidden_runtime_json_detected(tmp_path):
    repo = make_repo(tmp_path)
    (repo / "data").mkdir()
    (repo / "data" / "runtime.json").write_text("{}\n", encoding="utf-8")
    m = manifest(repo, forbidden_artifacts={"patterns": ["data/*.json"]})
    rc, out, _ = run(tmp_path, repo, m)
    assert rc == 1 and ids(out)["H1"] == "fail"


def test_tracked_settings_exception_allowed(tmp_path):
    repo = make_repo(tmp_path)
    (repo / "data").mkdir()
    (repo / "data" / "keep_settings.json").write_text("{}\n", encoding="utf-8")
    git(repo, "add", "--", "data/keep_settings.json")
    git(repo, "commit", "-q", "-m", "tracked settings")
    m = manifest(repo, head=git(repo, "rev-parse", "HEAD"),
                 forbidden_artifacts={"patterns": ["data/*.json"],
                                      "exceptions": ["data/keep_settings.json"]})
    rc, out, err = run(tmp_path, repo, m)
    assert rc == 0, err + out
    assert ids(out)["H1"] == "pass"


def test_scratch_artifact_detected(tmp_path):
    repo = make_repo(tmp_path)
    (repo / "data").mkdir()
    (repo / "data" / "_debug.js").write_text("x\n", encoding="utf-8")
    m = manifest(repo, forbidden_artifacts={"patterns": ["data/_*.js"]})
    rc, out, _ = run(tmp_path, repo, m)
    assert rc == 1 and ids(out)["H1"] == "fail"


def test_raw_transcript_detected(tmp_path):
    repo = make_repo(tmp_path)
    d = repo / "nova_knowledge_core" / "TRANSCRIPTS_RAW"
    d.mkdir(parents=True)
    (d / "t.txt").write_text("verbatim\n", encoding="utf-8")
    m = manifest(repo, require_clean_worktree=False, forbidden_artifacts={
        "patterns": ["nova_knowledge_core/TRANSCRIPTS_RAW/**"]})
    rc, out, _ = run(tmp_path, repo, m)
    assert rc == 1 and ids(out)["H1"] == "fail"


def test_cowork_lock_temp_residue_detected(tmp_path):
    repo = make_repo(tmp_path)
    (repo / ".nova-registry-abc.tmp").write_text("x\n", encoding="utf-8")
    m = manifest(repo, require_clean_worktree=False,
                 forbidden_artifacts={"patterns": ["data/*.json"]})
    rc, out, _ = run(tmp_path, repo, m)
    assert rc == 1 and ids(out)["H2"] == "fail"


def test_overbroad_forbidden_pattern_rejected(tmp_path):
    repo = make_repo(tmp_path)
    for bad in ("**", "*", "**/*"):
        rc, _, err = run(tmp_path, repo,
                         manifest(repo, forbidden_artifacts={"patterns": [bad]}))
        assert rc == 2 and "too broad" in err, bad


def test_ordinary_glob_pattern_is_accepted(tmp_path):
    """`data/*.json` is exact against an enumerated path list."""
    repo = make_repo(tmp_path)
    rc, out, err = run(tmp_path, repo,
                       manifest(repo, forbidden_artifacts={"patterns": ["data/*.json"]}))
    assert rc == 0, err + out


# ------------------------------------------------------------------ registry

def reg_session(repo, sid="boot-session", status="active", beat=T0,
                branch="work", head=None, identity=None, path=None,
                write=(), read=()):
    return {"session_id": sid, "worktree_identity": identity or repo.name,
            "canonical_worktree_path": path or str(repo), "branch": branch,
            "task": "bootstrap", "read_scope": list(read), "write_scope": list(write),
            "protected_scope": [], "started_at": beat, "heartbeat_at": beat,
            "status": status, "owner": "tester",
            "expected_commit": head or git(repo, "rev-parse", "HEAD")}


def write_registry(tmp_path, sessions, name="registry.json"):
    p = tmp_path / name
    p.write_text(json.dumps({"schema_version": 1, "revision": 1,
                             "sessions": list(sessions)}, indent=2) + "\n",
                 encoding="utf-8")
    return p


def test_matching_active_registry_session(tmp_path):
    repo = make_repo(tmp_path)
    reg = write_registry(tmp_path, [reg_session(repo)])
    m = manifest(repo, registry={"path": str(reg), "session_id": "boot-session",
                                 "stale_seconds": 10 ** 9})
    rc, out, err = run(tmp_path, repo, m)
    assert rc == 0, err + out
    for k in ("I1", "I2", "I4", "I5", "I6", "I7", "I8"):
        assert ids(out)[k] == "pass", k


def test_missing_registry_session(tmp_path):
    repo = make_repo(tmp_path)
    reg = write_registry(tmp_path, [reg_session(repo, sid="someone-else")])
    m = manifest(repo, registry={"path": str(reg), "session_id": "boot-session"})
    rc, out, _ = run(tmp_path, repo, m)
    assert rc == 1 and ids(out)["I1"] == "fail"


@pytest.mark.parametrize("status", ["paused", "closing", "closed"])
def test_non_active_registry_session(tmp_path, status):
    repo = make_repo(tmp_path)
    reg = write_registry(tmp_path, [reg_session(repo, status=status)])
    m = manifest(repo, registry={"path": str(reg), "session_id": "boot-session",
                                 "stale_seconds": 10 ** 9})
    rc, out, _ = run(tmp_path, repo, m)
    assert rc == 1 and ids(out)["I2"] == "fail"


def test_stale_registry_session_requires_approval(tmp_path):
    repo = make_repo(tmp_path)
    reg = write_registry(tmp_path, [reg_session(repo, beat="2020-01-01T00:00:00Z")])
    m = manifest(repo, registry={"path": str(reg), "session_id": "boot-session",
                                 "stale_seconds": 60})
    rc, out, _ = run(tmp_path, repo, m)
    assert rc == 5 and status_of(out) == "passed_with_warnings"
    assert ids(out)["I3"] == "warning"


def test_registry_branch_and_commit_mismatch(tmp_path):
    repo = make_repo(tmp_path)
    reg = write_registry(tmp_path, [reg_session(repo, branch="elsewhere",
                                                head="0" * 40)])
    m = manifest(repo, registry={"path": str(reg), "session_id": "boot-session",
                                 "stale_seconds": 10 ** 9})
    rc, out, _ = run(tmp_path, repo, m)
    assert rc == 1
    assert ids(out)["I6"] == "fail" and ids(out)["I7"] == "fail"


def test_registry_worktree_and_path_mismatch(tmp_path):
    repo = make_repo(tmp_path)
    reg = write_registry(tmp_path, [reg_session(repo, identity="other-wt",
                                                path=str(tmp_path / "nope"))])
    m = manifest(repo, registry={"path": str(reg), "session_id": "boot-session",
                                 "stale_seconds": 10 ** 9})
    rc, out, _ = run(tmp_path, repo, m)
    assert rc == 1
    assert ids(out)["I4"] == "fail" and ids(out)["I5"] == "fail"


def test_live_scope_collision_detected(tmp_path):
    repo = make_repo(tmp_path)
    mine = reg_session(repo, sid="boot-session", write=["app.py"])
    rival = reg_session(repo, sid="rival-session", write=["app.py"],
                        identity="other-wt", path=str(tmp_path / "other"),
                        branch="rival")
    reg = write_registry(tmp_path, [mine, rival])
    m = manifest(repo, registry={"path": str(reg), "session_id": "boot-session",
                                 "stale_seconds": 10 ** 9})
    rc, out, _ = run(tmp_path, repo, m)
    assert rc == 1 and ids(out)["I8"] == "fail"


def test_disjoint_registry_proposal_allowed(tmp_path):
    repo = make_repo(tmp_path)
    mine = reg_session(repo, sid="boot-session", write=["app.py"])
    other = reg_session(repo, sid="other-session", write=["docs/**"],
                        identity="other-wt", path=str(tmp_path / "other"),
                        branch="rival")
    reg = write_registry(tmp_path, [mine, other])
    m = manifest(repo, registry={"path": str(reg), "session_id": "boot-session",
                                 "stale_seconds": 10 ** 9})
    rc, out, err = run(tmp_path, repo, m)
    assert rc == 0, err + out
    assert ids(out)["I8"] == "pass"


def test_foreign_registry_lock_warns_without_mutation(tmp_path):
    repo = make_repo(tmp_path)
    reg = write_registry(tmp_path, [reg_session(repo)])
    lock = Path(str(reg) + ".lock")
    lock.write_text("99999", encoding="utf-8")
    before = reg.read_bytes()
    m = manifest(repo, registry={"path": str(reg), "session_id": "boot-session"})
    rc, out, _ = run(tmp_path, repo, m)
    assert rc == 5
    assert ids(out)["I0"] == "warning"
    assert reg.read_bytes() == before
    assert lock.read_text(encoding="utf-8") == "99999"
    lock.unlink()


def test_absent_registry_is_stopped(tmp_path):
    repo = make_repo(tmp_path)
    m = manifest(repo, registry={"path": str(tmp_path / "no-registry.json"),
                                 "session_id": "boot-session"})
    rc, out, _ = run(tmp_path, repo, m)
    assert rc == 4 and ids(out)["I0"] == "stopped"


def test_registry_path_expands_a_home_reference(tmp_path, monkeypatch):
    """A manifest may say `~/...` so it carries no username or home directory."""
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    repo = make_repo(tmp_path)
    reg = write_registry(tmp_path, [reg_session(repo)])
    target = home / ".claude" / "nova-session-registry.json"
    target.write_bytes(reg.read_bytes())
    m = manifest(repo, registry={"path": "~/.claude/nova-session-registry.json",
                                 "session_id": "boot-session",
                                 "stale_seconds": 10 ** 9})
    mpath = tmp_path / "home-manifest.json"
    mpath.write_text(json.dumps(m, indent=2), encoding="utf-8")
    env = dict(os.environ, HOME=str(home), USERPROFILE=str(home))
    p = subprocess.run([sys.executable, "-B", str(VALIDATOR),
                        "--manifest", str(mpath), "--repo", str(repo),
                        "--format", "json"], capture_output=True, env=env)
    out = p.stdout.decode("utf-8", "replace")
    assert p.returncode == 0, out + p.stderr.decode("utf-8", "replace")
    assert ids(out)["I1"] == "pass"
    assert target.read_bytes() == reg.read_bytes()


def test_registry_is_never_mutated_by_validation(tmp_path):
    repo = make_repo(tmp_path)
    reg = write_registry(tmp_path, [reg_session(repo)])
    before = reg.read_bytes()
    m = manifest(repo, registry={"path": str(reg), "session_id": "boot-session",
                                 "stale_seconds": 10 ** 9})
    run(tmp_path, repo, m)
    run(tmp_path, repo, m)
    assert reg.read_bytes() == before
    assert not Path(str(reg) + ".lock").exists()


# ------------------------------------------------------------------ manifest

def test_unknown_manifest_field_rejected(tmp_path):
    repo = make_repo(tmp_path)
    rc, _, err = run(tmp_path, repo, manifest(repo, extra_field="x"))
    assert rc == 2 and "unrecognized manifest field" in err


def test_command_like_manifest_value_rejected(tmp_path):
    repo = make_repo(tmp_path)
    for bad in ("run && rm -rf x", "$(whoami)", "https://example.invalid/x",
                "api_key=abc123", "bash -c ls"):
        rc, _, err = run(tmp_path, repo, manifest(repo, notes=[bad]))
        assert rc == 2, bad
        assert "rejected" in err


def test_malformed_manifest_rejected_without_payload_echo(tmp_path):
    repo = make_repo(tmp_path)
    bad = '{"schema_version": 1, "branch": "work", ' + CANARY
    rc, out, err = run(tmp_path, repo, None, raw=bad)
    assert rc == 2
    assert CANARY not in out and CANARY not in err


def test_unsupported_schema_rejected(tmp_path):
    repo = make_repo(tmp_path)
    rc, _, err = run(tmp_path, repo, manifest(repo, schema_version=9))
    assert rc == 2 and "unsupported schema_version" in err


def test_nan_rejected(tmp_path):
    repo = make_repo(tmp_path)
    raw = json.dumps(manifest(repo))[:-1] + ',"notes":[NaN]}'
    rc, _, err = run(tmp_path, repo, None, raw=raw)
    assert rc == 2


def test_traversal_and_absolute_paths_rejected(tmp_path):
    repo = make_repo(tmp_path)
    rc, _, err = run(tmp_path, repo,
                     manifest(repo, tracked_blobs={"../outside": "a" * 40}))
    assert rc == 2 and "traversal" in err
    rc, _, err = run(tmp_path, repo,
                     manifest(repo, tracked_blobs={"C:/Windows/x": "a" * 40}))
    assert rc == 2 and "repository-relative" in err


def test_invalid_object_id_and_hash_rejected(tmp_path):
    repo = make_repo(tmp_path)
    rc, _, err = run(tmp_path, repo, manifest(repo, head="abc"))
    assert rc == 2 and "object id" in err
    rc, _, err = run(tmp_path, repo, manifest(repo, local_ignored_files={
        ".claude/settings.local.json": {"sha256": "xyz"}}))
    assert rc == 2 and "64-char digest" in err


def test_case_conflicting_manifest_keys_rejected(tmp_path):
    repo = make_repo(tmp_path)
    rc, _, err = run(tmp_path, repo, manifest(repo, tracked_blobs={
        "App.py": "a" * 40, "app.py": "b" * 40}))
    assert rc == 2 and "case-conflicting" in err


def test_oversized_manifest_rejected(tmp_path):
    repo = make_repo(tmp_path)
    raw = json.dumps(manifest(repo))[:-1] + ',"notes":["' + "y" * (1024 * 1024) + '"]}'
    rc, _, err = run(tmp_path, repo, None, raw=raw)
    assert rc == 3


def test_excessive_collection_count_rejected(tmp_path):
    repo = make_repo(tmp_path)
    rc, _, err = run(tmp_path, repo, manifest(repo, notes=["n"] * 1500))
    assert rc == 3


def test_excessive_depth_rejected(tmp_path):
    repo = make_repo(tmp_path)
    nested = cur = {}
    for _ in range(60):
        cur["n"] = {}
        cur = cur["n"]
    rc, _, err = run(tmp_path, repo, manifest(repo, notes=[nested]))
    assert rc == 3


def test_no_test_command_field_is_accepted(tmp_path):
    """This validator confirms configuration, not test execution."""
    repo = make_repo(tmp_path)
    for field in ("required_test_suites", "tests", "command", "test_command"):
        rc, _, err = run(tmp_path, repo, manifest(repo, **{field: ["pytest -q"]}))
        assert rc == 2, field
        assert "unrecognized manifest field" in err


# ------------------------------------------------------------ determinism

def test_deterministic_markdown_and_json(tmp_path):
    repo = make_repo(tmp_path)
    m = manifest(repo, casing_rules={"required_prefixes": ["nova_knowledge_core/"]})
    for fmt in ("markdown", "json"):
        first = run(tmp_path, repo, m, fmt=fmt)[1]
        for _ in range(2):
            assert run(tmp_path, repo, m, fmt=fmt)[1] == first


def test_output_validates_through_the_formatter(tmp_path):
    repo = make_repo(tmp_path)
    rc, out, _ = run(tmp_path, repo, manifest(repo))
    parsed = json.loads(out)
    doc = {"schema_version": 1, "phase": parsed["phase"],
           "scope": parsed["scope"], "checks": parsed["checks"]}
    p = subprocess.run([sys.executable, "-B", str(FORMATTER), "--format", "json"],
                       input=json.dumps(doc).encode("utf-8"), capture_output=True)
    assert p.returncode == 0
    assert json.loads(p.stdout.decode("utf-8"))["overall_status"] == parsed["overall_status"]


def test_username_and_machine_path_absent_from_output(tmp_path):
    repo = make_repo(tmp_path)
    rc, out, err = run(tmp_path, repo, manifest(repo, canonical_worktree_path=str(repo)))
    user = Path.home().name
    assert user not in out and user not in err
    assert str(repo) not in out


def test_no_output_file_option():
    p = subprocess.run([sys.executable, "-B", str(VALIDATOR), "--help"],
                       capture_output=True, text=True)
    assert p.returncode == 0
    for flag in ("--output", "--outfile", "--write", "--fix", "--repair", "--create"):
        assert flag not in p.stdout, flag


# ----------------------------------------------------------- no mutation

def test_validation_mutates_nothing(tmp_path):
    repo = make_repo(tmp_path)
    _add_submodule(tmp_path, repo)
    link = git(repo, "ls-files", "--stage", "--", "sub").split()[1]
    reg = write_registry(tmp_path, [reg_session(repo,
                                                head=git(repo, "rev-parse", "HEAD"))])
    m = manifest(repo, head=git(repo, "rev-parse", "HEAD"),
                 submodules={"sub": {"gitlink": link, "populated": True}},
                 registry={"path": str(reg), "session_id": "boot-session",
                           "stale_seconds": 10 ** 9})
    fetch_head = repo / ".git" / "FETCH_HEAD"

    def snap():
        return (fetch_head.exists(), git(repo, "show-ref"),
                (repo / ".git" / "index").read_bytes(),
                (repo / ".git" / "config").read_bytes(),
                git(repo, "status", "--porcelain", "-uall"),
                git(repo / "sub", "rev-parse", "HEAD"),
                git(repo / "sub", "status", "--porcelain"),
                reg.read_bytes())

    before = snap()
    run(tmp_path, repo, m)
    run(tmp_path, repo, manifest(repo, head="0" * 40))     # a failing run too
    assert snap() == before


def test_no_input_content_is_executed(tmp_path):
    repo = make_repo(tmp_path)
    sentinel = tmp_path / "MUST_NOT_EXIST.txt"
    # A path-shaped value that would create a file if it were ever executed.
    m = manifest(repo, notes=["sentinel target %s" % sentinel.name])
    run(tmp_path, repo, m)
    assert not sentinel.exists()


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
    body = _executable_source(VALIDATOR)
    for forbidden in ("shell=True", "os.system", "popen", "eval(", "exec(",
                      "socket", "urllib", "requests", "httpx", "subprocess"):
        assert forbidden not in body, forbidden


def test_no_write_mode_file_open():
    body = _executable_source(VALIDATOR)
    import re as _re
    for m in _re.finditer(r"open\(([^)]*)\)", body):
        assert not _re.search(r"['\"][wax]", m.group(1)), m.group(0)


def test_no_mutating_git_verb_or_worktree_command():
    body = _executable_source(VALIDATOR)
    for verb in ("fetch", "pull", "push", "merge", "rebase", "checkout",
                 "switch", "reset", "restore", "clean", "commit", "worktree",
                 "submodule", "update-index", "gc", "maintenance"):
        assert '"%s"' % verb not in body, verb
        assert "'%s'" % verb not in body, verb


def test_no_deletion_helper():
    body = _executable_source(VALIDATOR)
    for banned in ("os.remove", "os.unlink", "shutil.rmtree", "rmdir", "unlink("):
        assert banned not in body, banned


def test_no_environment_value_reads():
    body = _executable_source(VALIDATOR)
    for banned in ("os.environ", "getenv"):
        assert banned not in body, banned


def test_stdlib_only():
    src = VALIDATOR.read_text(encoding="utf-8")
    mods = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Import):
            mods.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods.add(node.module.split(".")[0])
    third = [m for m in mods if m not in sys.stdlib_module_names
             and m not in ("__future__", "evidence_formatter", "staleness_guard",
                           "session_registry", "a7_battery")]
    assert third == [], third


def test_every_git_call_uses_an_existing_read_only_allowlist():
    body = _executable_source(VALIDATOR)
    assert "a7._git" in body or "a7_battery" in body
    sys.path.insert(0, str(VALIDATOR.parent))
    try:
        import a7_battery as a7
    finally:
        sys.path.pop(0)
    mutating = {"fetch", "pull", "push", "merge", "rebase", "checkout", "switch",
                "reset", "restore", "clean", "add", "commit", "worktree",
                "submodule", "config", "update-index"}
    assert not (a7._A7_GIT_READ_ONLY & mutating)


def test_reuses_formatter_and_existing_tools():
    body = _executable_source(VALIDATOR)
    for name in ("evidence_formatter", "staleness_guard", "session_registry",
                 "a7_battery"):
        assert name in body, name
    for reused in ("normalize", "render_json", "render_markdown", "resolve_repo",
                   "read_registry", "find_collisions", "classify"):
        assert reused in body, reused
