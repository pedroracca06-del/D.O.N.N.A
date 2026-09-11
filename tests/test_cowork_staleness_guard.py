"""test_cowork_staleness_guard.py -- tests for the Cowork Staleness Guard.

Every case builds a synthetic Git repository under pytest's tmp_path (OS temp,
outside this repository). Remote-truth cases use a local bare repository; no
external service is ever contacted. Nothing in the NOVA repository is read or
written by these tests except the tool source itself.
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
GUARD = REPO_ROOT / "tools" / "cowork" / "staleness_guard.py"
FORMATTER = REPO_ROOT / "tools" / "cowork" / "evidence_formatter.py"

CANARY = "NOVA_3L_CANARY_5b8e21fa07c9"


# ------------------------------------------------------------------ helpers

def git(repo, *args, check=True):
    p = subprocess.run(["git", "-C", str(repo)] + list(args),
                       capture_output=True, text=True)
    if check and p.returncode != 0:
        raise AssertionError("git %s failed: %s" % (args[0], p.stderr))
    return p.stdout.strip()


def make_repo(tmp_path, name="work"):
    """A synthetic repository with one commit, an ignored file, and a config."""
    repo = tmp_path / name
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    git(repo, "config", "user.email", "test@example.invalid")
    git(repo, "config", "user.name", "Test")
    (repo / ".gitignore").write_text("ignored/\n*.log\n", encoding="utf-8")
    (repo / "kept.txt").write_text("hello\n", encoding="utf-8")
    (repo / "perm.json").write_text(
        json.dumps({"permissions": {"allow": ["a", "b"], "ask": ["c"],
                                    "deny": []}}, indent=2) + "\n",
        encoding="utf-8")
    git(repo, "add", "--", ".gitignore", "kept.txt", "perm.json")
    git(repo, "commit", "-q", "-m", "initial")
    return repo


def baseline_for(repo, **extra):
    b = {
        "schema_version": 1,
        "expected_branch": git(repo, "rev-parse", "--abbrev-ref", "HEAD"),
        "expected_head": git(repo, "rev-parse", "HEAD"),
    }
    b.update(extra)
    return b


def run(repo, baseline, fmt="json", remote=None, as_file=None, raw=None):
    cmd = [sys.executable, "-B", str(GUARD), "--repo", str(repo), "--format", fmt]
    if remote is not None:
        cmd += ["--check-remote", remote]
    data = b""
    if as_file is not None:
        cmd += ["--input", str(as_file)]
    else:
        text = raw if raw is not None else json.dumps(baseline)
        data = text.encode("utf-8") if isinstance(text, str) else text
    p = subprocess.run(cmd, input=data, capture_output=True)
    return (p.returncode,
            p.stdout.decode("utf-8", "replace"),
            p.stderr.decode("utf-8", "replace"))


def statuses(out):
    return {c["id"]: c["status"] for c in json.loads(out)["checks"]}


def sha256_file(path):
    import hashlib
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# --------------------------------------------------------------- fresh cases

def test_matching_branch_and_head_is_fresh(tmp_path):
    repo = make_repo(tmp_path)
    rc, out, err = run(repo, baseline_for(repo))
    assert rc == 0, err
    assert json.loads(out)["overall_status"] == "passed"


def test_clean_index_and_worktree_pass(tmp_path):
    repo = make_repo(tmp_path)
    b = baseline_for(repo, require_clean_index=True, require_clean_worktree=True)
    rc, out, _ = run(repo, b)
    assert rc == 0
    st = statuses(out)
    assert st["C01"] == "pass" and st["C02"] == "pass"


def test_matching_tracked_blob_passes(tmp_path):
    repo = make_repo(tmp_path)
    blob = git(repo, "rev-parse", "HEAD:kept.txt")
    rc, out, _ = run(repo, baseline_for(repo, expected_tracked_blobs={"kept.txt": blob}))
    assert rc == 0
    assert statuses(out)["D01"] == "pass"


def test_matching_permission_hash_and_counts_pass(tmp_path):
    repo = make_repo(tmp_path)
    b = baseline_for(repo, expected_permission_state={
        "path": "perm.json", "sha256": sha256_file(repo / "perm.json"),
        "allow": 2, "ask": 1, "deny": 0})
    rc, out, _ = run(repo, b)
    assert rc == 0
    st = statuses(out)
    assert st["E01"] == "pass" and st["E02"] == "pass"


def test_matching_local_ref_passes(tmp_path):
    repo = make_repo(tmp_path)
    head = git(repo, "rev-parse", "HEAD")
    rc, out, _ = run(repo, baseline_for(repo, expected_local_refs={"refs/heads/main": head}))
    assert rc == 0
    assert statuses(out)["B01"] == "pass"


def test_matching_gitlink_fixture_passes(tmp_path):
    """A synthetic gitlink entry, without needing a real submodule checkout."""
    repo = make_repo(tmp_path)
    fake_oid = "1" * 40
    git(repo, "update-index", "--add", "--cacheinfo",
        "160000,%s,sub/mod" % fake_oid)
    git(repo, "commit", "-q", "-m", "add gitlink")
    b = baseline_for(repo, expected_submodule_gitlinks={"sub/mod": fake_oid})
    rc, out, _ = run(repo, b)
    assert rc == 0
    assert statuses(out)["F01"] == "pass"


def test_matching_worktree_identity_passes(tmp_path):
    repo = make_repo(tmp_path, name="myworktree")
    rc, out, _ = run(repo, baseline_for(repo, expected_worktree_identity="myworktree"))
    assert rc == 0
    assert statuses(out)["G01"] == "pass"


def test_deterministic_markdown_and_json(tmp_path):
    repo = make_repo(tmp_path)
    b = baseline_for(repo, require_clean_index=True)
    for fmt in ("markdown", "json"):
        first = run(repo, b, fmt=fmt)[1]
        for _ in range(2):
            assert run(repo, b, fmt=fmt)[1] == first


# --------------------------------------------------------------- stale cases

def test_head_moved_is_stale(tmp_path):
    repo = make_repo(tmp_path)
    b = baseline_for(repo)
    (repo / "kept.txt").write_text("changed\n", encoding="utf-8")
    git(repo, "add", "--", "kept.txt")
    git(repo, "commit", "-q", "-m", "second")
    rc, out, _ = run(repo, b)
    assert rc == 1
    assert json.loads(out)["overall_status"] == "failed"
    assert statuses(out)["A03"] == "fail"


def test_branch_changed_is_stale(tmp_path):
    repo = make_repo(tmp_path)
    b = baseline_for(repo)
    git(repo, "checkout", "-q", "-b", "other")
    rc, out, _ = run(repo, b)
    assert rc == 1
    assert statuses(out)["A02"] == "fail"


def test_local_ref_moved_is_stale(tmp_path):
    repo = make_repo(tmp_path)
    old = git(repo, "rev-parse", "HEAD")
    b = baseline_for(repo, expected_local_refs={"refs/heads/main": old})
    (repo / "kept.txt").write_text("x\n", encoding="utf-8")
    git(repo, "add", "--", "kept.txt")
    git(repo, "commit", "-q", "-m", "moves main")
    b["expected_head"] = git(repo, "rev-parse", "HEAD")   # isolate the ref check
    rc, out, _ = run(repo, b)
    assert rc == 1
    assert statuses(out)["B01"] == "fail"


def test_staged_file_is_stale(tmp_path):
    repo = make_repo(tmp_path)
    b = baseline_for(repo, require_clean_index=True)
    (repo / "new.txt").write_text("n\n", encoding="utf-8")
    git(repo, "add", "--", "new.txt")
    rc, out, _ = run(repo, b)
    assert rc == 1
    assert statuses(out)["C01"] == "fail"


def test_tracked_modification_is_stale(tmp_path):
    repo = make_repo(tmp_path)
    b = baseline_for(repo, require_clean_worktree=True)
    (repo / "kept.txt").write_text("dirty\n", encoding="utf-8")
    rc, out, _ = run(repo, b)
    assert rc == 1
    assert statuses(out)["C02"] == "fail"


def test_visible_untracked_file_is_stale(tmp_path):
    repo = make_repo(tmp_path)
    b = baseline_for(repo, require_clean_worktree=True)
    (repo / "surprise.txt").write_text("s\n", encoding="utf-8")
    rc, out, _ = run(repo, b)
    assert rc == 1
    assert statuses(out)["C02"] == "fail"


def test_ignored_file_does_not_trigger_drift(tmp_path):
    repo = make_repo(tmp_path)
    b = baseline_for(repo, require_clean_index=True, require_clean_worktree=True)
    (repo / "debug.log").write_text("noise\n", encoding="utf-8")
    (repo / "ignored").mkdir()
    (repo / "ignored" / "x.txt").write_text("noise\n", encoding="utf-8")
    rc, out, _ = run(repo, b)
    assert rc == 0, out
    assert statuses(out)["C02"] == "pass"


def test_tracked_blob_mismatch_is_stale(tmp_path):
    repo = make_repo(tmp_path)
    b = baseline_for(repo, expected_tracked_blobs={"kept.txt": "0" * 40})
    rc, out, _ = run(repo, b)
    assert rc == 1
    assert statuses(out)["D01"] == "fail"


def test_permission_hash_drift_is_stale(tmp_path):
    repo = make_repo(tmp_path)
    b = baseline_for(repo, expected_permission_state={
        "path": "perm.json", "sha256": "0" * 64})
    rc, out, _ = run(repo, b)
    assert rc == 1
    assert statuses(out)["E01"] == "fail"


def test_permission_count_drift_is_stale(tmp_path):
    repo = make_repo(tmp_path)
    b = baseline_for(repo, expected_permission_state={
        "path": "perm.json", "allow": 99, "ask": 1, "deny": 0})
    rc, out, _ = run(repo, b)
    assert rc == 1
    assert statuses(out)["E02"] == "fail"


def test_missing_permission_file_is_stale(tmp_path):
    repo = make_repo(tmp_path)
    b = baseline_for(repo, expected_permission_state={"path": "absent.json"})
    rc, out, _ = run(repo, b)
    assert rc == 1
    assert statuses(out)["E01"] == "fail"


def test_gitlink_mismatch_is_stale(tmp_path):
    repo = make_repo(tmp_path)
    b = baseline_for(repo, expected_submodule_gitlinks={"sub/mod": "2" * 40})
    rc, out, _ = run(repo, b)
    assert rc == 1
    assert statuses(out)["F01"] == "fail"


def test_wrong_worktree_identity_is_stale(tmp_path):
    repo = make_repo(tmp_path, name="actual")
    b = baseline_for(repo, expected_worktree_identity="expected-other")
    rc, out, _ = run(repo, b)
    assert rc == 1
    assert statuses(out)["G01"] == "fail"


def test_one_stale_check_forces_exit_1_and_failed(tmp_path):
    repo = make_repo(tmp_path)
    b = baseline_for(repo, require_clean_index=True,
                     expected_tracked_blobs={"kept.txt": "0" * 40})
    rc, out, _ = run(repo, b)
    assert rc == 1
    parsed = json.loads(out)
    assert parsed["overall_status"] == "failed"
    assert parsed["check_counts"]["pass"] >= 1        # others still passed


# ------------------------------------------------------- stopped / invalid

def test_nonexistent_repository_is_stopped(tmp_path):
    rc, out, _ = run(tmp_path / "nope", baseline_for(make_repo(tmp_path)))
    assert rc == 4
    assert json.loads(out)["overall_status"] == "stopped"


def test_non_repository_directory_is_stopped(tmp_path):
    plain = tmp_path / "plain"
    plain.mkdir()
    repo = make_repo(tmp_path)
    rc, out, _ = run(plain, baseline_for(repo))
    assert rc == 4
    assert json.loads(out)["overall_status"] == "stopped"


def test_malformed_json_rejected_without_payload_echo(tmp_path):
    repo = make_repo(tmp_path)
    bad = '{"schema_version": 1, "expected_branch": "main", ' + CANARY
    rc, out, err = run(repo, None, raw=bad)
    assert rc == 2
    assert "not valid JSON" in err
    assert CANARY not in err and CANARY not in out
    assert bad not in err


def test_unsupported_schema_rejected(tmp_path):
    repo = make_repo(tmp_path)
    b = baseline_for(repo)
    b["schema_version"] = 99
    rc, _, err = run(repo, b)
    assert rc == 2 and "unsupported schema_version" in err


def test_unknown_field_rejected(tmp_path):
    repo = make_repo(tmp_path)
    b = baseline_for(repo)
    b["run_command"] = "rm -rf /"
    rc, _, err = run(repo, b)
    assert rc == 2 and "unrecognized baseline field" in err


def test_absolute_baseline_path_rejected(tmp_path):
    repo = make_repo(tmp_path)
    b = baseline_for(repo, expected_tracked_blobs={"C:/Windows/x": "0" * 40})
    rc, _, err = run(repo, b)
    assert rc == 2 and "repository-relative" in err


def test_traversal_path_rejected(tmp_path):
    repo = make_repo(tmp_path)
    b = baseline_for(repo, expected_tracked_blobs={"../outside.txt": "0" * 40})
    rc, _, err = run(repo, b)
    assert rc == 2 and "traversal" in err


def test_invalid_object_id_rejected(tmp_path):
    repo = make_repo(tmp_path)
    b = baseline_for(repo)
    b["expected_head"] = "not-an-oid"
    rc, _, err = run(repo, b)
    assert rc == 2 and "object id" in err


def test_duplicate_case_normalized_keys_rejected(tmp_path):
    repo = make_repo(tmp_path)
    b = baseline_for(repo, expected_tracked_blobs={"A/x.txt": "0" * 40,
                                                   "a/x.txt": "1" * 40})
    rc, _, err = run(repo, b)
    assert rc == 2 and "duplicate keys" in err


def test_oversized_baseline_rejected(tmp_path):
    repo = make_repo(tmp_path)
    payload = json.dumps(baseline_for(repo))
    payload = payload[:-1] + ',"notes":["' + "y" * (1024 * 1024) + '"]}'
    rc, _, err = run(repo, None, raw=payload)
    assert rc == 3 and "maximum accepted size" in err


def test_excessive_depth_rejected(tmp_path):
    repo = make_repo(tmp_path)
    nested = cur = {}
    for _ in range(60):
        cur["n"] = {}
        cur = cur["n"]
    b = baseline_for(repo, notes=[nested])
    rc, _, err = run(repo, b)
    assert rc == 3 and "depth" in err


def test_excessive_collection_count_rejected(tmp_path):
    repo = make_repo(tmp_path)
    b = baseline_for(repo, notes=["n"] * 1500)
    rc, _, err = run(repo, b)
    assert rc == 3 and "maximum of" in err


def test_nan_rejected(tmp_path):
    repo = make_repo(tmp_path)
    raw = json.dumps(baseline_for(repo))[:-1] + ',"notes":[NaN]}'
    rc, _, err = run(repo, None, raw=raw)
    assert rc == 2 and "non-standard numeric" in err


# ------------------------------------------------------------ remote truth

def make_bare_remote(tmp_path, source):
    bare = tmp_path / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(bare)],
                   check=True, capture_output=True)
    git(source, "remote", "add", "origin", str(bare))
    git(source, "push", "-q", "origin", "main")
    return bare


def test_remote_ref_match_passes(tmp_path):
    repo = make_repo(tmp_path)
    make_bare_remote(tmp_path, repo)
    head = git(repo, "rev-parse", "HEAD")
    b = baseline_for(repo, expected_remote_refs={"refs/heads/main": head})
    rc, out, err = run(repo, b, remote="origin")
    assert rc == 0, err + out
    assert statuses(out)["R01"] == "pass"


def test_remote_advance_without_fetch_is_detected(tmp_path):
    repo = make_repo(tmp_path)
    bare = make_bare_remote(tmp_path, repo)
    old_head = git(repo, "rev-parse", "HEAD")
    b = baseline_for(repo, expected_remote_refs={"refs/heads/main": old_head})

    # A second clone advances the remote behind this repository's back.
    other = tmp_path / "other"
    subprocess.run(["git", "clone", "-q", str(bare), str(other)],
                   check=True, capture_output=True)
    git(other, "config", "user.email", "t@example.invalid")
    git(other, "config", "user.name", "T")
    (other / "kept.txt").write_text("remote change\n", encoding="utf-8")
    git(other, "add", "--", "kept.txt")
    git(other, "commit", "-q", "-m", "remote advance")
    git(other, "push", "-q", "origin", "main")

    fetch_head = repo / ".git" / "FETCH_HEAD"
    before_exists = fetch_head.exists()
    before_refs = git(repo, "show-ref")

    rc, out, _ = run(repo, b, remote="origin")
    assert rc == 1
    assert statuses(out)["R01"] == "fail"
    # No fetch happened.
    assert fetch_head.exists() == before_exists
    assert git(repo, "show-ref") == before_refs


def test_remote_observation_does_not_change_local_state(tmp_path):
    repo = make_repo(tmp_path)
    make_bare_remote(tmp_path, repo)
    b = baseline_for(repo, require_clean_index=True, require_clean_worktree=True)
    before = (git(repo, "show-ref"),
              git(repo, "status", "--porcelain", "-uall"),
              git(repo, "rev-parse", "HEAD"),
              (repo / ".git" / "config").read_bytes())
    run(repo, b, remote="origin")
    after = (git(repo, "show-ref"),
             git(repo, "status", "--porcelain", "-uall"),
             git(repo, "rev-parse", "HEAD"),
             (repo / ".git" / "config").read_bytes())
    assert before == after


def test_tags_are_not_inspected(tmp_path):
    repo = make_repo(tmp_path)
    make_bare_remote(tmp_path, repo)
    git(repo, "tag", "v1")
    git(repo, "push", "-q", "origin", "v1")
    head = git(repo, "rev-parse", "HEAD")
    b = baseline_for(repo, expected_remote_refs={"refs/heads/main": head})
    rc, out, _ = run(repo, b, remote="origin")
    assert rc == 0
    assert "refs/tags" not in out


def test_url_passed_to_check_remote_is_rejected(tmp_path):
    repo = make_repo(tmp_path)
    bare = make_bare_remote(tmp_path, repo)
    b = baseline_for(repo)
    rc, out, _ = run(repo, b, remote="https://example.invalid/x.git")
    assert rc == 1
    assert statuses(out)["R00"] == "fail"
    assert "example.invalid" not in out


def test_unknown_remote_is_rejected(tmp_path):
    repo = make_repo(tmp_path)
    b = baseline_for(repo)
    rc, out, _ = run(repo, b, remote="nosuchremote")
    assert rc == 1
    assert statuses(out)["R00"] == "fail"


def test_unreachable_remote_is_stopped_with_exit_4(tmp_path):
    repo = make_repo(tmp_path)
    missing = tmp_path / "gone.git"
    git(repo, "remote", "add", "origin", str(missing))
    b = baseline_for(repo)
    rc, out, _ = run(repo, b, remote="origin")
    assert rc == 4
    assert json.loads(out)["overall_status"] == "stopped"
    assert str(missing) not in out


def test_remote_url_never_leaks(tmp_path):
    repo = make_repo(tmp_path)
    secret_dir = tmp_path / ("remote_" + CANARY + ".git")
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(secret_dir)],
                   check=True, capture_output=True)
    git(repo, "remote", "add", "origin", str(secret_dir))
    git(repo, "push", "-q", "origin", "main")
    head = git(repo, "rev-parse", "HEAD")
    b = baseline_for(repo, expected_remote_refs={"refs/heads/main": head})
    rc, out, err = run(repo, b, remote="origin")
    assert CANARY not in out and CANARY not in err


# ---------------------------------------------------------------- security

def test_command_like_baseline_strings_are_rejected(tmp_path):
    repo = make_repo(tmp_path)
    for field in ("command", "git_args", "hook", "env", "script"):
        b = baseline_for(repo)
        b[field] = "git push --force"
        rc, _, err = run(repo, b)
        assert rc == 2, field
        assert "unrecognized baseline field" in err


def test_canary_never_appears_in_output(tmp_path):
    repo = make_repo(tmp_path)
    b = baseline_for(repo, notes=["token=" + CANARY,
                                  "Authorization: Bearer " + CANARY])
    for fmt in ("markdown", "json"):
        rc, out, err = run(repo, b, fmt=fmt)
        assert CANARY not in out, fmt
        assert CANARY not in err, fmt


def test_machine_username_absent_from_output(tmp_path):
    repo = make_repo(tmp_path)
    user = Path.home().name
    rc, out, err = run(repo, baseline_for(repo))
    assert rc == 0
    assert user not in out and user not in err


def test_repository_root_is_normalized(tmp_path):
    repo = make_repo(tmp_path)
    rc, out, _ = run(repo, baseline_for(repo))
    assert "${REPO}" in out
    assert str(repo) not in out


def test_no_repository_file_written_and_baseline_untouched(tmp_path):
    repo = make_repo(tmp_path)
    bfile = tmp_path / "baseline.json"
    bfile.write_text(json.dumps(baseline_for(repo), indent=2), encoding="utf-8")
    before_bytes = bfile.read_bytes()
    before_tree = sorted(p.name for p in repo.iterdir())
    rc, out, err = run(repo, None, as_file=bfile)
    assert rc == 0, err
    assert bfile.read_bytes() == before_bytes
    assert sorted(p.name for p in repo.iterdir()) == before_tree


def test_index_and_status_byte_identical_after_fresh_and_stale(tmp_path):
    repo = make_repo(tmp_path)
    b = baseline_for(repo, require_clean_index=True)
    idx = repo / ".git" / "index"
    before = (idx.read_bytes(), git(repo, "status", "--porcelain", "-uall"),
              git(repo, "show-ref"))
    run(repo, b)                                   # fresh
    stale = baseline_for(repo, expected_head="0" * 40)
    run(repo, stale)                               # stale
    after = (idx.read_bytes(), git(repo, "status", "--porcelain", "-uall"),
             git(repo, "show-ref"))
    assert before == after


# ----------------------------------------------------------- static review

def _executable_source(path):
    """Source with comments and docstrings stripped."""
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


def test_never_uses_shell_true():
    body = _executable_source(GUARD)
    assert "shell=True" not in body
    assert "os.system" not in body
    assert "popen" not in body.lower()


def test_no_eval_exec_or_network_library():
    body = _executable_source(GUARD)
    for forbidden in ("eval(", "exec(", "socket", "urllib", "requests", "httpx"):
        assert forbidden not in body, forbidden


def test_no_mutating_git_subcommand_in_executable_source():
    body = _executable_source(GUARD)
    for verb in ("fetch", "pull", "push", "merge", "rebase", "checkout",
                 "switch", "reset", "restore", "clean", "commit",
                 "maintenance", "gc"):
        assert '"%s"' % verb not in body, verb
        assert "'%s'" % verb not in body, verb


def test_git_allowlist_is_read_only():
    sys.path.insert(0, str(GUARD.parent))
    try:
        import staleness_guard as sg
    finally:
        sys.path.pop(0)
    mutating = {"fetch", "pull", "push", "merge", "rebase", "checkout",
                "switch", "reset", "restore", "clean", "add", "commit",
                "tag", "branch", "submodule", "config", "maintenance", "gc"}
    assert not (sg._GIT_READ_ONLY & mutating)
    # `merge-base` is read-only despite the name; `merge` itself is not present.
    assert "merge-base" in sg._GIT_READ_ONLY
    assert "merge" not in sg._GIT_READ_ONLY


# ------------------------------------------- narrowly admitted merge-base

def _sg():
    sys.path.insert(0, str(GUARD.parent))
    try:
        import staleness_guard as sg
        return sg
    finally:
        sys.path.pop(0)


def test_is_ancestor_true_for_a_real_ancestor(tmp_path):
    repo = make_repo(tmp_path)
    first = git(repo, "rev-parse", "HEAD")
    (repo / "kept.txt").write_text("2\n", encoding="utf-8")
    git(repo, "add", "--", "kept.txt")
    git(repo, "commit", "-q", "-m", "second")
    second = git(repo, "rev-parse", "HEAD")
    assert _sg().is_ancestor(str(repo), first, second) is True


def test_is_ancestor_false_for_unrelated_history(tmp_path):
    repo = make_repo(tmp_path)
    first = git(repo, "rev-parse", "HEAD")
    git(repo, "checkout", "-q", "--orphan", "fresh")
    (repo / "b.txt").write_text("x\n", encoding="utf-8")
    git(repo, "add", "--", "b.txt")
    git(repo, "commit", "-q", "-m", "orphan")
    other = git(repo, "rev-parse", "HEAD")
    assert _sg().is_ancestor(str(repo), first, other) is False


def test_is_ancestor_false_in_the_reverse_direction(tmp_path):
    repo = make_repo(tmp_path)
    first = git(repo, "rev-parse", "HEAD")
    (repo / "kept.txt").write_text("2\n", encoding="utf-8")
    git(repo, "add", "--", "kept.txt")
    git(repo, "commit", "-q", "-m", "second")
    second = git(repo, "rev-parse", "HEAD")
    assert _sg().is_ancestor(str(repo), second, first) is False


def test_is_ancestor_rejects_abbreviated_or_ref_arguments(tmp_path):
    repo = make_repo(tmp_path)
    head = git(repo, "rev-parse", "HEAD")
    sg = _sg()
    for bad in (head[:8], "HEAD", "main", "", "not-an-oid"):
        with pytest.raises(sg.StoppedError):
            sg.is_ancestor(str(repo), bad, head)
        with pytest.raises(sg.StoppedError):
            sg.is_ancestor(str(repo), head, bad)


def test_only_the_is_ancestor_form_of_merge_base_is_permitted(tmp_path):
    """Every other merge-base shape is refused inside _git, not at the caller."""
    repo = make_repo(tmp_path)
    head = git(repo, "rev-parse", "HEAD")
    sg = _sg()
    for args in (
            ["merge-base", head, head],                       # plain merge-base
            ["merge-base", "--all", head, head],
            ["merge-base", "--fork-point", "main"],
            ["merge-base", "--octopus", head, head],
            ["merge-base", "--is-ancestor", head],            # too few
            ["merge-base", "--is-ancestor", head, head, head],  # too many
            ["merge-base", "--is-ancestor", "HEAD", head],    # ref, not an oid
            ["merge-base", "--is-ancestor", head[:8], head],  # abbreviation
    ):
        with pytest.raises(sg.StoppedError):
            sg._git(str(repo), args)


def test_merge_base_addition_does_not_mutate_the_repository(tmp_path):
    repo = make_repo(tmp_path)
    first = git(repo, "rev-parse", "HEAD")
    (repo / "kept.txt").write_text("2\n", encoding="utf-8")
    git(repo, "add", "--", "kept.txt")
    git(repo, "commit", "-q", "-m", "second")
    second = git(repo, "rev-parse", "HEAD")
    fetch_head = repo / ".git" / "FETCH_HEAD"
    before = (fetch_head.exists(), git(repo, "show-ref"),
              (repo / ".git" / "index").read_bytes(),
              (repo / ".git" / "config").read_bytes(),
              git(repo, "status", "--porcelain", "-uall"))
    _sg().is_ancestor(str(repo), first, second)
    after = (fetch_head.exists(), git(repo, "show-ref"),
             (repo / ".git" / "index").read_bytes(),
             (repo / ".git" / "config").read_bytes(),
             git(repo, "status", "--porcelain", "-uall"))
    assert before == after


def test_existing_observer_behaviour_is_unchanged_by_the_addition(tmp_path):
    """The pre-existing commands still work exactly as before."""
    repo = make_repo(tmp_path)
    b = baseline_for(repo, require_clean_index=True, require_clean_worktree=True)
    rc, out, err = run(repo, b)
    assert rc == 0, err + out
    assert json.loads(out)["overall_status"] == "passed"


def test_git_helper_refuses_a_subcommand_outside_the_allowlist(tmp_path):
    repo = make_repo(tmp_path)
    sys.path.insert(0, str(GUARD.parent))
    try:
        import staleness_guard as sg
    finally:
        sys.path.pop(0)
    with pytest.raises(sg.StoppedError):
        sg._git(str(repo), ["fetch", "origin"])


def test_stdlib_only():
    src = GUARD.read_text(encoding="utf-8")
    mods = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Import):
            mods.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods.add(node.module.split(".")[0])
    third = [m for m in mods
             if m not in sys.stdlib_module_names
             and m not in ("__future__", "evidence_formatter")]
    assert third == [], third


def test_no_clock_dependency():
    body = _executable_source(GUARD)
    for forbidden in ("datetime", "time.time", "now(", "utcnow"):
        assert forbidden not in body, forbidden


def test_reuses_the_formatter_rather_than_duplicating_it():
    body = _executable_source(GUARD)
    assert "evidence_formatter" in body
    for reused in ("normalize", "render_json", "render_markdown",
                   "sanitize_text", "enforce_limits"):
        assert reused in body, reused


# -------------------------------------------------------------- integration

def test_emitted_document_validates_through_the_formatter(tmp_path):
    repo = make_repo(tmp_path)
    rc, out, _ = run(repo, baseline_for(repo, require_clean_index=True))
    assert rc == 0
    parsed = json.loads(out)
    # Feed the rendered checks back through the formatter as a fresh document.
    doc = {"schema_version": 1, "phase": parsed["phase"],
           "scope": parsed["scope"], "checks": parsed["checks"]}
    p = subprocess.run([sys.executable, "-B", str(FORMATTER), "--format", "json"],
                       input=json.dumps(doc).encode("utf-8"), capture_output=True)
    assert p.returncode == 0
    assert json.loads(p.stdout.decode("utf-8"))["overall_status"] == "passed"


def test_formatter_planted_failure_behaviour_still_intact():
    doc = {"schema_version": 1, "phase": "p", "scope": "s",
           "checks": [{"id": "A", "label": "x", "status": "fail"}],
           "notes": ["everything passed"]}
    p = subprocess.run([sys.executable, "-B", str(FORMATTER), "--format", "json"],
                       input=json.dumps(doc).encode("utf-8"), capture_output=True)
    assert json.loads(p.stdout.decode("utf-8"))["overall_status"] == "failed"


def test_repeated_identical_observation_is_byte_identical(tmp_path):
    repo = make_repo(tmp_path)
    b = baseline_for(repo, require_clean_index=True, require_clean_worktree=True)
    outs = {run(repo, b, fmt="json")[1] for _ in range(3)}
    assert len(outs) == 1


def test_no_output_file_option():
    p = subprocess.run([sys.executable, "-B", str(GUARD), "--help"],
                       capture_output=True, text=True)
    assert p.returncode == 0
    for flag in ("--output", "--outfile", "--write"):
        assert flag not in p.stdout
