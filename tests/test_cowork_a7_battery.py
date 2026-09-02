"""test_cowork_a7_battery.py -- tests for the reusable A7 safety battery.

Synthetic Git repositories under pytest's tmp_path only. No network, no
external service, no mutation of the NOVA repository.
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
BATTERY = REPO_ROOT / "tools" / "cowork" / "a7_battery.py"
POLICY = REPO_ROOT / "tools" / "cowork" / "a7_policy.json"
FORMATTER = REPO_ROOT / "tools" / "cowork" / "evidence_formatter.py"

CANARY = "NOVA_3M_CANARY_71c0e4bd93af"


# ------------------------------------------------------------------ helpers

def git(repo, *args, check=True):
    p = subprocess.run(["git", "-C", str(repo)] + list(args),
                       capture_output=True, text=True)
    if check and p.returncode != 0:
        raise AssertionError("git %s failed: %s" % (args[0], p.stderr))
    return p.stdout.strip()


def make_repo(tmp_path, name="work"):
    repo = tmp_path / name
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    git(repo, "config", "user.email", "t@example.invalid")
    git(repo, "config", "user.name", "T")
    (repo / ".gitignore").write_text("*.log\nignored/\n", encoding="utf-8")
    (repo / "kept.txt").write_text("hello\n", encoding="utf-8")
    git(repo, "add", "--", ".gitignore", "kept.txt")
    git(repo, "commit", "-q", "-m", "initial")
    return repo


def manifest_for(repo, paths, scope="staged", commit=None, **extra):
    m = {
        "schema_version": 1,
        "phase": "test",
        "change_scope": {"kind": scope},
        "expected_paths": list(paths),
        "baseline": {
            "schema_version": 1,
            "expected_branch": git(repo, "rev-parse", "--abbrev-ref", "HEAD"),
            "expected_head": git(repo, "rev-parse", "HEAD"),
        },
        "required_test_suites": [
            {"name": "unit", "command": "python -B -m pytest tests -q",
             "expected_passed": 5, "observed_passed": 5,
             "expected_failed": 0, "observed_failed": 0},
        ],
    }
    if commit:
        m["change_scope"]["commit"] = commit
    m.update(extra)
    return m


def run(repo, manifest, fmt="json", raw=None, input_file=None, policy=None):
    cmd = [sys.executable, "-B", str(BATTERY), "--repo", str(repo), "--format", fmt]
    if policy is not None:
        cmd += ["--policy", str(policy)]
    data = b""
    if input_file is not None:
        cmd += ["--input", str(input_file)]
    else:
        text = raw if raw is not None else json.dumps(manifest)
        data = text.encode("utf-8") if isinstance(text, str) else text
    p = subprocess.run(cmd, input=data, capture_output=True)
    return (p.returncode,
            p.stdout.decode("utf-8", "replace"),
            p.stderr.decode("utf-8", "replace"))


def ids(out):
    return {c["id"]: c["status"] for c in json.loads(out)["checks"]}


def failed_ids(out, prefix):
    return [i for i, s in ids(out).items() if i.startswith(prefix) and s == "fail"]


# ------------------------------------------------------------------ A1 scope

def test_a1_exact_match_passes(tmp_path):
    repo = make_repo(tmp_path)
    (repo / "new.py").write_text("x = 1\n", encoding="utf-8")
    git(repo, "add", "--", "new.py")
    rc, out, err = run(repo, manifest_for(repo, ["new.py"]))
    assert rc == 0, err + out
    assert ids(out)["A1.1"] == "pass"


def test_a1_extra_path_fails(tmp_path):
    repo = make_repo(tmp_path)
    for n in ("declared.py", "surprise.py"):
        (repo / n).write_text("x = 1\n", encoding="utf-8")
        git(repo, "add", "--", n)
    rc, out, _ = run(repo, manifest_for(repo, ["declared.py"]))
    assert rc == 1
    assert ids(out)["A1.1"] == "fail"
    assert ids(out)["A1.3"] == "fail"


def test_a1_missing_path_fails(tmp_path):
    repo = make_repo(tmp_path)
    (repo / "one.py").write_text("x = 1\n", encoding="utf-8")
    git(repo, "add", "--", "one.py")
    rc, out, _ = run(repo, manifest_for(repo, ["one.py", "two.py"]))
    assert rc == 1
    assert ids(out)["A1.2"] == "fail"


def test_a1_duplicate_path_rejected(tmp_path):
    repo = make_repo(tmp_path)
    rc, _, err = run(repo, manifest_for(repo, ["a.py", "a.py"]))
    assert rc == 2 and "duplicate" in err


def test_a1_bogus_case_conflict_fails_the_gate(tmp_path):
    """Two entries differing only by case, with no matching rename in the
    observed change set, are a collision and must fail A1.

    They are NOT rejected at validation time, because a genuine case-only
    rename produces exactly that shape -- see the case-only-rename test.
    """
    repo = make_repo(tmp_path)
    (repo / "x.py").write_text("x = 1\n", encoding="utf-8")
    git(repo, "add", "--", "x.py")
    rc, out, _ = run(repo, manifest_for(repo, ["A/x.py", "a/x.py"]))
    assert rc == 1
    assert ids(out)["A1.5"] == "fail"


def test_a1_zero_paths_cannot_pass_when_changes_exist(tmp_path):
    repo = make_repo(tmp_path)
    (repo / "sneak.py").write_text("x = 1\n", encoding="utf-8")
    git(repo, "add", "--", "sneak.py")
    rc, out, _ = run(repo, manifest_for(repo, []))
    assert rc == 1
    assert ids(out)["A1.0"] == "fail"


def test_a1_staged_and_unstaged_are_distinguished(tmp_path):
    repo = make_repo(tmp_path)
    (repo / "staged.py").write_text("x = 1\n", encoding="utf-8")
    git(repo, "add", "--", "staged.py")
    (repo / "kept.txt").write_text("modified\n", encoding="utf-8")
    rc, out, _ = run(repo, manifest_for(repo, ["staged.py", "kept.txt"],
                                        scope="worktree"))
    comp = [c for c in json.loads(out)["checks"] if c["id"] == "A1.4"][0]
    assert "staged=1" in comp["evidence"]
    assert "unstaged=1" in comp["evidence"]


def test_a1_untracked_visible_file_counted_in_worktree_scope(tmp_path):
    repo = make_repo(tmp_path)
    (repo / "loose.py").write_text("x = 1\n", encoding="utf-8")
    rc, out, _ = run(repo, manifest_for(repo, ["loose.py"], scope="worktree"))
    assert rc == 0
    comp = [c for c in json.loads(out)["checks"] if c["id"] == "A1.4"][0]
    assert "untracked=1" in comp["evidence"]


def test_a1_commit_scope(tmp_path):
    repo = make_repo(tmp_path)
    (repo / "c.py").write_text("x = 1\n", encoding="utf-8")
    git(repo, "add", "--", "c.py")
    git(repo, "commit", "-q", "-m", "adds c")
    head = git(repo, "rev-parse", "HEAD")
    m = manifest_for(repo, ["c.py"], scope="commit", commit=head)
    rc, out, err = run(repo, m)
    assert rc == 0, err + out
    assert ids(out)["A1.1"] == "pass"


def test_a1_abbreviated_commit_rejected(tmp_path):
    repo = make_repo(tmp_path)
    short = git(repo, "rev-parse", "--short", "HEAD")
    m = manifest_for(repo, ["x"], scope="commit", commit=short)
    rc, _, err = run(repo, m)
    assert rc == 2 and "full commit id" in err


def test_a1_rename_reports_both_sides(tmp_path):
    repo = make_repo(tmp_path)
    git(repo, "mv", "kept.txt", "renamed.txt")
    rc, out, _ = run(repo, manifest_for(repo, ["kept.txt", "renamed.txt"]))
    assert rc == 0, out
    assert ids(out)["A1.1"] == "pass"


def test_a1_case_only_rename_reports_both_sides(tmp_path):
    repo = make_repo(tmp_path)
    git(repo, "mv", "kept.txt", "TMP_KEPT")
    git(repo, "mv", "TMP_KEPT", "KEPT.TXT")
    rc, out, _ = run(repo, manifest_for(repo, ["kept.txt", "KEPT.TXT"]))
    assert ids(out)["A1.1"] == "pass", out


def test_a1_submodule_gitlink_classified(tmp_path):
    repo = make_repo(tmp_path)
    git(repo, "update-index", "--add", "--cacheinfo", "160000,%s,sub/mod" % ("1" * 40))
    rc, out, _ = run(repo, manifest_for(repo, ["sub/mod"]))
    comp = [c for c in json.loads(out)["checks"] if c["id"] == "A1.4"][0]
    assert "submodule=1" in comp["evidence"]


def test_a1_filename_with_space(tmp_path):
    repo = make_repo(tmp_path)
    (repo / "has space.py").write_text("x = 1\n", encoding="utf-8")
    git(repo, "add", "--", "has space.py")
    rc, out, _ = run(repo, manifest_for(repo, ["has space.py"]))
    assert rc == 0, out
    assert ids(out)["A1.1"] == "pass"


def test_a1_empty_file_handled(tmp_path):
    repo = make_repo(tmp_path)
    (repo / "empty.txt").write_text("", encoding="utf-8")
    git(repo, "add", "--", "empty.txt")
    rc, out, _ = run(repo, manifest_for(repo, ["empty.txt"]))
    assert rc == 0, out


def test_a1_deletion_handled(tmp_path):
    repo = make_repo(tmp_path)
    git(repo, "rm", "-q", "--", "kept.txt")
    rc, out, _ = run(repo, manifest_for(repo, ["kept.txt"]))
    assert rc == 0, out
    assert ids(out)["A1.1"] == "pass"


# ----------------------------------------------------------------- A2 secrets

def test_a2_clean_text_passes(tmp_path):
    repo = make_repo(tmp_path)
    (repo / "ok.py").write_text("def f():\n    return 42\n", encoding="utf-8")
    git(repo, "add", "--", "ok.py")
    rc, out, _ = run(repo, manifest_for(repo, ["ok.py"]))
    assert rc == 0
    assert ids(out)["A2.1"] == "pass"


def test_a2_credential_key_value_fails_without_leaking(tmp_path):
    repo = make_repo(tmp_path)
    (repo / "bad.py").write_text('API_KEY = "%s"\n' % CANARY, encoding="utf-8")
    git(repo, "add", "--", "bad.py")
    rc, out, err = run(repo, manifest_for(repo, ["bad.py"]))
    assert rc == 1
    assert ids(out)["A2.1"] == "fail"
    assert CANARY not in out and CANARY not in err


def test_a2_authorization_header_fails_without_leaking(tmp_path):
    repo = make_repo(tmp_path)
    (repo / "h.txt").write_text("Authorization: Bearer %s\n" % CANARY, encoding="utf-8")
    git(repo, "add", "--", "h.txt")
    rc, out, err = run(repo, manifest_for(repo, ["h.txt"]))
    assert rc == 1
    assert CANARY not in out and CANARY not in err


def test_a2_token_formats_detected(tmp_path):
    repo = make_repo(tmp_path)
    body = "\n".join(["sk-ant-" + "a" * 30, "ghp_" + "b" * 20, "AKIA" + "C" * 16])
    (repo / "t.txt").write_text(body + "\n", encoding="utf-8")
    git(repo, "add", "--", "t.txt")
    rc, out, _ = run(repo, manifest_for(repo, ["t.txt"]))
    assert rc == 1
    for leak in ("sk-ant-aaa", "ghp_bbb", "AKIACCC"):
        assert leak not in out


def test_a2_only_sanitized_metadata_reported(tmp_path):
    repo = make_repo(tmp_path)
    (repo / "bad.py").write_text('token = "%s"\n' % CANARY, encoding="utf-8")
    git(repo, "add", "--", "bad.py")
    rc, out, _ = run(repo, manifest_for(repo, ["bad.py"]))
    finding = [c for c in json.loads(out)["checks"] if c["id"].startswith("A2.0")]
    assert finding
    ev = finding[0]["evidence"]
    assert "line 1" in ev and "category" in ev and "finding" in ev
    assert CANARY not in ev


def test_a2_binary_is_classified_not_decoded(tmp_path):
    repo = make_repo(tmp_path)
    (repo / "blob.bin").write_bytes(bytes([0, 1, 2, 3, 255]) + CANARY.encode())
    git(repo, "add", "--", "blob.bin")
    rc, out, err = run(repo, manifest_for(repo, ["blob.bin"]))
    assert rc == 0, out
    assert "binary files classified: 1" in out
    assert CANARY not in out and CANARY not in err


def test_a2_prose_false_positives_not_flagged(tmp_path):
    repo = make_repo(tmp_path)
    (repo / "doc.md").write_text(
        "the tokenizer ran\na secret scan found nothing\ncredential check passed\n",
        encoding="utf-8")
    git(repo, "add", "--", "doc.md")
    rc, out, _ = run(repo, manifest_for(repo, ["doc.md"]))
    assert rc == 0, out
    assert ids(out)["A2.1"] == "pass"


# ------------------------------------------------------------ A3 machine paths

def test_a3_windows_profile_fails_without_username(tmp_path):
    repo = make_repo(tmp_path)
    (repo / "p.py").write_text('P = r"C:\\Users\\someperson\\x"\n', encoding="utf-8")
    git(repo, "add", "--", "p.py")
    rc, out, err = run(repo, manifest_for(repo, ["p.py"]))
    assert rc == 1
    assert ids(out)["A3.1"] == "fail"
    assert "someperson" not in out and "someperson" not in err


def test_a3_gitbash_profile_fails(tmp_path):
    repo = make_repo(tmp_path)
    (repo / "p.py").write_text('P = "/c/Users/someperson/x"\n', encoding="utf-8")
    git(repo, "add", "--", "p.py")
    rc, out, _ = run(repo, manifest_for(repo, ["p.py"]))
    assert rc == 1 and "someperson" not in out


def test_a3_temp_scratch_fails(tmp_path):
    repo = make_repo(tmp_path)
    (repo / "p.py").write_text('P = "/tmp/scratch/out.txt"\n', encoding="utf-8")
    git(repo, "add", "--", "p.py")
    rc, out, _ = run(repo, manifest_for(repo, ["p.py"]))
    assert rc == 1
    assert ids(out)["A3.1"] == "fail"


def test_a3_portable_placeholders_allowed(tmp_path):
    repo = make_repo(tmp_path)
    (repo / "p.py").write_text(
        'A = "${HOME}/x"\nB = "${REPO}/y"\nC = "${CLAUDE_PROJECT_DIR}/z"\n',
        encoding="utf-8")
    git(repo, "add", "--", "p.py")
    rc, out, _ = run(repo, manifest_for(repo, ["p.py"]))
    assert rc == 0, out
    assert ids(out)["A3.1"] == "pass"


def test_a3_real_username_never_emitted(tmp_path):
    repo = make_repo(tmp_path)
    user = Path.home().name
    (repo / "p.py").write_text('P = r"%s"\n' % str(Path.home() / "x"), encoding="utf-8")
    git(repo, "add", "--", "p.py")
    rc, out, err = run(repo, manifest_for(repo, ["p.py"]))
    assert user not in out and user not in err


# --------------------------------------------------------------- A4 protected

def test_a4_undeclared_protected_file_fails(tmp_path):
    repo = make_repo(tmp_path)
    (repo / "core").mkdir()
    (repo / "core" / "config.py").write_text("X = 1\n", encoding="utf-8")
    git(repo, "add", "--", "core/config.py")
    rc, out, _ = run(repo, manifest_for(repo, ["core/config.py"]))
    assert rc == 1
    assert any(s == "fail" for i, s in ids(out).items() if i.startswith("A4.0"))


def test_a4_declared_protected_change_yields_exit_5(tmp_path):
    repo = make_repo(tmp_path)
    (repo / "core").mkdir()
    (repo / "core" / "config.py").write_text("X = 1\n", encoding="utf-8")
    git(repo, "add", "--", "core/config.py")
    m = manifest_for(repo, ["core/config.py"],
                     declared_protected_changes=["core/config.py"])
    rc, out, _ = run(repo, m)
    assert rc == 5, out
    parsed = json.loads(out)
    assert parsed["overall_status"] == "passed_with_warnings"
    assert any(c["status"] == "warning" and c["id"].startswith("A4.D")
               for c in parsed["checks"])


def test_a4_declared_protected_never_passes_silently(tmp_path):
    repo = make_repo(tmp_path)
    (repo / ".claude").mkdir()
    (repo / ".claude" / "settings.json").write_text("{}\n", encoding="utf-8")
    git(repo, "add", "--", ".claude/settings.json")
    m = manifest_for(repo, [".claude/settings.json"],
                     declared_protected_changes=[".claude/settings.json"])
    rc, out, _ = run(repo, m)
    assert rc == 5
    warn = [c for c in json.loads(out)["checks"] if c["id"].startswith("A4.D")]
    assert warn and ("AAM" in warn[0]["evidence"] or "AM" in warn[0]["evidence"])


def test_a4_activation_flag_enabled_fails(tmp_path):
    repo = make_repo(tmp_path)
    (repo / "cfg.sh").write_text("NOVA_AUTO_EXECUTE=true\n", encoding="utf-8")
    git(repo, "add", "--", "cfg.sh")
    rc, out, _ = run(repo, manifest_for(repo, ["cfg.sh"]))
    assert rc == 1
    assert any(s == "fail" for i, s in ids(out).items() if i.startswith("A4.F"))


def test_a4_activation_flag_false_is_not_flagged(tmp_path):
    repo = make_repo(tmp_path)
    (repo / "cfg.sh").write_text("NOVA_AUTO_EXECUTE=false\n", encoding="utf-8")
    git(repo, "add", "--", "cfg.sh")
    rc, out, _ = run(repo, manifest_for(repo, ["cfg.sh"]))
    assert rc == 0, out
    assert ids(out)["A4.F00"] == "pass"


def test_a4_hook_change_detected(tmp_path):
    repo = make_repo(tmp_path)
    (repo / ".claude" / "hooks").mkdir(parents=True)
    (repo / ".claude" / "hooks" / "h.py").write_text("x = 1\n", encoding="utf-8")
    git(repo, "add", "--", ".claude/hooks/h.py")
    rc, out, _ = run(repo, manifest_for(repo, [".claude/hooks/h.py"]))
    assert rc == 1


def test_a4_permission_file_change_detected(tmp_path):
    repo = make_repo(tmp_path)
    (repo / ".claude").mkdir()
    (repo / ".claude" / "settings.local.json").write_text("{}\n", encoding="utf-8")
    git(repo, "add", "-f", "--", ".claude/settings.local.json")
    rc, out, _ = run(repo, manifest_for(repo, [".claude/settings.local.json"]))
    assert rc == 1


def test_a4_risk_and_strategy_and_broker_paths_classified(tmp_path):
    for rel in ("engines/risk_engine.py",
                "nova_knowledge_core/RULES/x.json",
                "services/execution_bridge.py"):
        tmp = tmp_path / rel.replace("/", "_")
        tmp.mkdir()
        repo = make_repo(tmp, name="r")
        target = repo / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("x = 1\n", encoding="utf-8")
        git(repo, "add", "--", rel)
        rc, out, _ = run(repo, manifest_for(repo, [rel]))
        assert rc == 1, rel


def test_a4_manifest_cannot_weaken_fixed_policy(tmp_path):
    repo = make_repo(tmp_path)
    (repo / "core").mkdir()
    (repo / "core" / "config.py").write_text("X = 1\n", encoding="utf-8")
    git(repo, "add", "--", "core/config.py")
    # A negation-style entry is rejected outright.
    m = manifest_for(repo, ["core/config.py"],
                     stricter_protected_paths=["!core/config.py"])
    rc, _, err = run(repo, m)
    assert rc == 2 and "may not be weakened" in err


def test_a4_stricter_manifest_paths_are_honoured(tmp_path):
    repo = make_repo(tmp_path)
    (repo / "extra.py").write_text("x = 1\n", encoding="utf-8")
    git(repo, "add", "--", "extra.py")
    m = manifest_for(repo, ["extra.py"], stricter_protected_paths=["extra.py"])
    rc, out, _ = run(repo, m)
    assert rc == 1          # undeclared, and now protected by the manifest


# ----------------------------------------------------------- A5 runtime/data

def test_a5_runtime_json_fails(tmp_path):
    repo = make_repo(tmp_path)
    (repo / "data").mkdir()
    (repo / "data" / "donna_liquidity.json").write_text("{}\n", encoding="utf-8")
    git(repo, "add", "-f", "--", "data/donna_liquidity.json")
    rc, out, _ = run(repo, manifest_for(repo, ["data/donna_liquidity.json"]))
    assert rc == 1
    assert ids(out)["A5.1"] == "fail"


def test_a5_donna_settings_is_the_tracked_exception(tmp_path):
    repo = make_repo(tmp_path)
    (repo / "data").mkdir()
    (repo / "data" / "donna_settings.json").write_text("{}\n", encoding="utf-8")
    git(repo, "add", "-f", "--", "data/donna_settings.json")
    rc, out, _ = run(repo, manifest_for(repo, ["data/donna_settings.json"]))
    assert rc == 0, out
    assert ids(out)["A5.1"] == "pass"


def test_a5_raw_transcript_fails(tmp_path):
    repo = make_repo(tmp_path)
    d = repo / "nova_knowledge_core" / "TRANSCRIPTS_RAW"
    d.mkdir(parents=True)
    (d / "t.txt").write_text("verbatim\n", encoding="utf-8")
    git(repo, "add", "--", "nova_knowledge_core/TRANSCRIPTS_RAW/t.txt")
    rc, out, _ = run(repo, manifest_for(repo,
                                        ["nova_knowledge_core/TRANSCRIPTS_RAW/t.txt"]))
    assert rc == 1
    assert ids(out)["A5.1"] == "fail"


def test_a5_log_cache_and_pyc_fail(tmp_path):
    for rel in ("app.log", "__pycache__/m.pyc", ".pytest_cache/v/x"):
        sub = tmp_path / rel.replace("/", "_").replace(".", "_")
        sub.mkdir()
        repo = make_repo(sub, name="r")
        target = repo / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("x\n", encoding="utf-8")
        git(repo, "add", "-f", "--", rel)
        rc, out, _ = run(repo, manifest_for(repo, [rel]))
        assert rc == 1, rel


def test_a5_original_summary_allowed(tmp_path):
    repo = make_repo(tmp_path)
    d = repo / "nova_knowledge_core"
    d.mkdir()
    (d / "SUMMARY.md").write_text("# original analysis\n", encoding="utf-8")
    git(repo, "add", "--", "nova_knowledge_core/SUMMARY.md")
    rc, out, _ = run(repo, manifest_for(repo, ["nova_knowledge_core/SUMMARY.md"]))
    assert rc == 0, out


def test_a5_force_added_ignored_artifact_is_caught(tmp_path):
    repo = make_repo(tmp_path)
    (repo / "noise.log").write_text("x\n", encoding="utf-8")
    git(repo, "add", "-f", "--", "noise.log")     # ignored, but force-staged
    rc, out, _ = run(repo, manifest_for(repo, ["noise.log"]))
    assert rc == 1
    assert ids(out)["A5.1"] == "fail"


def test_a5_credential_file_fails(tmp_path):
    repo = make_repo(tmp_path)
    (repo / ".env").write_text("X=1\n", encoding="utf-8")
    git(repo, "add", "-f", "--", ".env")
    rc, out, _ = run(repo, manifest_for(repo, [".env"]))
    assert rc == 1


# ------------------------------------------------------------- A6 staleness

def test_a6_fresh_baseline_passes(tmp_path):
    repo = make_repo(tmp_path)
    (repo / "x.py").write_text("x = 1\n", encoding="utf-8")
    git(repo, "add", "--", "x.py")
    rc, out, _ = run(repo, manifest_for(repo, ["x.py"]))
    assert rc == 0
    assert ids(out)["A6.A03"] == "pass"


def test_a6_head_drift_fails(tmp_path):
    repo = make_repo(tmp_path)
    m = manifest_for(repo, ["x.py"])
    m["baseline"]["expected_head"] = "0" * 40
    (repo / "x.py").write_text("x = 1\n", encoding="utf-8")
    git(repo, "add", "--", "x.py")
    rc, out, _ = run(repo, m)
    assert rc == 1
    assert ids(out)["A6.A03"] == "fail"


def test_a6_branch_drift_fails(tmp_path):
    repo = make_repo(tmp_path)
    m = manifest_for(repo, ["x.py"])
    m["baseline"]["expected_branch"] = "someotherbranch"
    (repo / "x.py").write_text("x = 1\n", encoding="utf-8")
    git(repo, "add", "--", "x.py")
    rc, out, _ = run(repo, m)
    assert rc == 1
    assert ids(out)["A6.A02"] == "fail"


def test_a6_permission_drift_fails(tmp_path):
    repo = make_repo(tmp_path)
    (repo / "perm.json").write_text(
        json.dumps({"permissions": {"allow": ["a"], "ask": [], "deny": []}}),
        encoding="utf-8")
    (repo / "x.py").write_text("x = 1\n", encoding="utf-8")
    git(repo, "add", "--", "x.py")
    m = manifest_for(repo, ["x.py"])
    m["baseline"]["expected_permission_state"] = {
        "path": "perm.json", "allow": 99, "ask": 0, "deny": 0}
    rc, out, _ = run(repo, m)
    assert rc == 1
    assert ids(out)["A6.E02"] == "fail"


def test_a6_ref_drift_fails(tmp_path):
    repo = make_repo(tmp_path)
    (repo / "x.py").write_text("x = 1\n", encoding="utf-8")
    git(repo, "add", "--", "x.py")
    m = manifest_for(repo, ["x.py"])
    m["baseline"]["expected_local_refs"] = {"refs/heads/main": "0" * 40}
    rc, out, _ = run(repo, m)
    assert rc == 1
    assert ids(out)["A6.B01"] == "fail"


def test_a6_stopped_observation_stops_the_battery(tmp_path):
    repo = make_repo(tmp_path)
    plain = tmp_path / "notarepo"
    plain.mkdir()
    rc, out, _ = run(plain, manifest_for(repo, ["x.py"]))
    assert rc == 4
    assert json.loads(out)["overall_status"] == "stopped"


def test_a6_never_fetches_and_leaves_state_identical(tmp_path):
    repo = make_repo(tmp_path)
    (repo / "x.py").write_text("x = 1\n", encoding="utf-8")
    git(repo, "add", "--", "x.py")
    fetch_head = repo / ".git" / "FETCH_HEAD"
    before = (fetch_head.exists(), git(repo, "show-ref"),
              (repo / ".git" / "index").read_bytes(),
              (repo / ".git" / "config").read_bytes(),
              git(repo, "status", "--porcelain", "-uall"))
    run(repo, manifest_for(repo, ["x.py"]))
    after = (fetch_head.exists(), git(repo, "show-ref"),
             (repo / ".git" / "index").read_bytes(),
             (repo / ".git" / "config").read_bytes(),
             git(repo, "status", "--porcelain", "-uall"))
    assert before == after


# --------------------------------------------------------- A7 test evidence

def test_a7_exact_parity_passes(tmp_path):
    repo = make_repo(tmp_path)
    (repo / "x.py").write_text("x = 1\n", encoding="utf-8")
    git(repo, "add", "--", "x.py")
    rc, out, _ = run(repo, manifest_for(repo, ["x.py"]))
    assert rc == 0
    assert ids(out)["A7.1.1"] == "pass"


def test_a7_new_failure_fails(tmp_path):
    repo = make_repo(tmp_path)
    (repo / "x.py").write_text("x = 1\n", encoding="utf-8")
    git(repo, "add", "--", "x.py")
    m = manifest_for(repo, ["x.py"])
    m["required_test_suites"][0].update(expected_failed=0, observed_failed=3)
    rc, out, _ = run(repo, m)
    assert rc == 1
    assert ids(out)["A7.1.2"] == "fail"


def test_a7_collection_count_change_fails(tmp_path):
    repo = make_repo(tmp_path)
    (repo / "x.py").write_text("x = 1\n", encoding="utf-8")
    git(repo, "add", "--", "x.py")
    m = manifest_for(repo, ["x.py"])
    m["required_test_suites"][0].update(expected_collected=926, observed_collected=900)
    rc, out, _ = run(repo, m)
    assert rc == 1
    assert ids(out)["A7.1.1"] == "fail"


def test_a7_missing_evidence_stops(tmp_path):
    repo = make_repo(tmp_path)
    (repo / "x.py").write_text("x = 1\n", encoding="utf-8")
    git(repo, "add", "--", "x.py")
    m = manifest_for(repo, ["x.py"])
    m["required_test_suites"] = [{"name": "unit", "command": "pytest -q"}]
    rc, out, _ = run(repo, m)
    assert rc == 4
    assert ids(out)["A7.1.0"] == "stopped"


def test_a7_missing_suite_list_rejected(tmp_path):
    repo = make_repo(tmp_path)
    m = manifest_for(repo, ["x.py"])
    m["required_test_suites"] = []
    rc, _, err = run(repo, m)
    assert rc == 2 and "non-empty list" in err


def test_a7_weakened_expectation_detected(tmp_path):
    repo = make_repo(tmp_path)
    (repo / "x.py").write_text("x = 1\n", encoding="utf-8")
    git(repo, "add", "--", "x.py")
    m = manifest_for(repo, ["x.py"])
    # expected_passed present but never observed -> cannot be claimed
    m["required_test_suites"][0] = {"name": "unit", "command": "pytest -q",
                                    "expected_passed": 900, "observed_failed": 0}
    rc, out, _ = run(repo, m)
    assert rc == 1
    assert ids(out)["A7.1.1"] == "fail"


def test_a7_prose_only_pass_rejected(tmp_path):
    repo = make_repo(tmp_path)
    (repo / "x.py").write_text("x = 1\n", encoding="utf-8")
    git(repo, "add", "--", "x.py")
    m = manifest_for(repo, ["x.py"])
    m["required_test_suites"][0]["command"] = "all tests passed"
    rc, out, _ = run(repo, m)
    assert rc == 1
    assert ids(out)["A7.1.P"] == "fail"


def test_a7_failure_list_must_match_count(tmp_path):
    repo = make_repo(tmp_path)
    (repo / "x.py").write_text("x = 1\n", encoding="utf-8")
    git(repo, "add", "--", "x.py")
    m = manifest_for(repo, ["x.py"])
    m["required_test_suites"][0].update(expected_failed=2, observed_failed=2,
                                        observed_failures=["only::one"])
    rc, out, _ = run(repo, m)
    assert rc == 1
    assert ids(out)["A7.1.3"] == "fail"


def test_a7_test_command_is_data_and_never_executed(tmp_path):
    repo = make_repo(tmp_path)
    sentinel = tmp_path / "MUST_NOT_EXIST.txt"
    (repo / "x.py").write_text("x = 1\n", encoding="utf-8")
    git(repo, "add", "--", "x.py")
    m = manifest_for(repo, ["x.py"])
    m["required_test_suites"][0]["command"] = (
        "python -c \"open(r'%s','w').write('x')\"" % sentinel)
    rc, out, _ = run(repo, m)
    assert not sentinel.exists()
    assert "MUST_NOT_EXIST" in out


# ------------------------------------------------------------- manifest input

def test_unknown_manifest_field_rejected(tmp_path):
    repo = make_repo(tmp_path)
    m = manifest_for(repo, ["x.py"])
    m["run_command"] = "git push --force"
    rc, _, err = run(repo, m)
    assert rc == 2 and "unrecognized manifest field" in err


def test_absolute_expected_path_rejected(tmp_path):
    repo = make_repo(tmp_path)
    rc, _, err = run(repo, manifest_for(repo, ["C:/Windows/x"]))
    assert rc == 2 and "repository-relative" in err


def test_traversal_expected_path_rejected(tmp_path):
    repo = make_repo(tmp_path)
    rc, _, err = run(repo, manifest_for(repo, ["../outside"]))
    assert rc == 2 and "traversal" in err


def test_unsupported_scope_rejected(tmp_path):
    repo = make_repo(tmp_path)
    m = manifest_for(repo, ["x.py"])
    m["change_scope"] = {"kind": "everything"}
    rc, _, err = run(repo, m)
    assert rc == 2 and "change_scope kind" in err


def test_unsupported_schema_rejected(tmp_path):
    repo = make_repo(tmp_path)
    m = manifest_for(repo, ["x.py"])
    m["schema_version"] = 99
    rc, _, err = run(repo, m)
    assert rc == 2 and "unsupported schema_version" in err


def test_malformed_manifest_rejected_without_payload_echo(tmp_path):
    repo = make_repo(tmp_path)
    bad = '{"schema_version": 1, "phase": "p", ' + CANARY
    rc, out, err = run(repo, None, raw=bad)
    assert rc == 2
    assert CANARY not in err and CANARY not in out
    assert bad not in err


def test_oversized_manifest_rejected(tmp_path):
    repo = make_repo(tmp_path)
    payload = json.dumps(manifest_for(repo, ["x.py"]))
    payload = payload[:-1] + ',"notes":["' + "y" * (1024 * 1024) + '"]}'
    rc, _, err = run(repo, None, raw=payload)
    assert rc == 3 and "maximum accepted size" in err


def test_excessive_collection_count_rejected(tmp_path):
    repo = make_repo(tmp_path)
    rc, _, err = run(repo, manifest_for(repo, ["x.py"], notes=["n"] * 1500))
    assert rc == 3


def test_file_input_leaves_manifest_untouched(tmp_path):
    repo = make_repo(tmp_path)
    (repo / "x.py").write_text("x = 1\n", encoding="utf-8")
    git(repo, "add", "--", "x.py")
    f = tmp_path / "manifest.json"
    f.write_text(json.dumps(manifest_for(repo, ["x.py"]), indent=2), encoding="utf-8")
    before = f.read_bytes()
    rc, out, err = run(repo, None, input_file=f)
    assert rc == 0, err + out
    assert f.read_bytes() == before


# ---------------------------------------------------------------- policy

def test_policy_is_data_not_executable():
    """Pure JSON data. `__pycache__` is a legitimate glob, so the check looks
    for executable constructs rather than a bare double underscore."""
    text = POLICY.read_text(encoding="utf-8")
    policy = json.loads(text)
    assert isinstance(policy, dict)
    for banned in ("import ", "eval(", "exec(", "lambda", "__import__",
                   "subprocess", "os.system", "#!"):
        assert banned not in text, banned


def test_policy_contains_no_machine_path_or_secret():
    text = POLICY.read_text(encoding="utf-8")
    import re as _re
    assert not _re.search(r"(?i)[a-z]:[\\/]+users|/home/|/c/Users|AppData", text)
    assert not _re.search(r"(?i)sk-ant-|ghp_|AKIA[0-9A-Z]{16}|-----BEGIN", text)


def test_policy_has_no_disable_option():
    text = POLICY.read_text(encoding="utf-8").lower()
    for banned in ("disable", "skip_gate", "ignore_gate", "bypass"):
        assert banned not in text, banned


def test_policy_hash_is_reported_and_stable(tmp_path):
    repo = make_repo(tmp_path)
    (repo / "x.py").write_text("x = 1\n", encoding="utf-8")
    git(repo, "add", "--", "x.py")
    outs = []
    for _ in range(2):
        rc, out, _ = run(repo, manifest_for(repo, ["x.py"]))
        line = [c for c in json.loads(out)["checks"] if c["id"] == "A0.1"][0]
        outs.append(line["evidence"])
    assert outs[0] == outs[1]
    import hashlib
    assert hashlib.sha256(POLICY.read_bytes()).hexdigest() in outs[0]


# ----------------------------------------------------------- cross-cutting

def test_deterministic_markdown_and_json(tmp_path):
    repo = make_repo(tmp_path)
    (repo / "x.py").write_text("x = 1\n", encoding="utf-8")
    git(repo, "add", "--", "x.py")
    m = manifest_for(repo, ["x.py"])
    for fmt in ("markdown", "json"):
        first = run(repo, m, fmt=fmt)[1]
        for _ in range(2):
            assert run(repo, m, fmt=fmt)[1] == first


def test_output_shows_overall_and_each_gate(tmp_path):
    repo = make_repo(tmp_path)
    (repo / "x.py").write_text("x = 1\n", encoding="utf-8")
    git(repo, "add", "--", "x.py")
    rc, out, _ = run(repo, manifest_for(repo, ["x.py"]), fmt="markdown")
    assert "Overall status" in out
    for gate in ("A1", "A2", "A3", "A4", "A5", "A6", "A7"):
        assert gate in out, gate


def test_no_output_file_option():
    p = subprocess.run([sys.executable, "-B", str(BATTERY), "--help"],
                       capture_output=True, text=True)
    assert p.returncode == 0
    for flag in ("--output", "--outfile", "--write"):
        assert flag not in p.stdout


def test_repository_byte_identical_before_and_after(tmp_path):
    repo = make_repo(tmp_path)
    (repo / "x.py").write_text("x = 1\n", encoding="utf-8")
    git(repo, "add", "--", "x.py")
    def snapshot():
        return (git(repo, "status", "--porcelain", "-uall"),
                git(repo, "show-ref"),
                (repo / ".git" / "index").read_bytes(),
                (repo / ".git" / "config").read_bytes())
    before = snapshot()
    run(repo, manifest_for(repo, ["x.py"]))
    run(repo, manifest_for(repo, ["wrong.py"]))     # a failing run too
    assert snapshot() == before


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


def test_no_shell_true_or_eval_or_network():
    body = _executable_source(BATTERY)
    for forbidden in ("shell=True", "os.system", "popen", "eval(", "exec(",
                      "socket", "urllib", "requests", "httpx"):
        assert forbidden not in body, forbidden


def test_git_allowlist_contains_no_mutating_verb():
    sys.path.insert(0, str(BATTERY.parent))
    try:
        import a7_battery as a7
    finally:
        sys.path.pop(0)
    mutating = {"fetch", "pull", "push", "merge", "rebase", "checkout",
                "switch", "reset", "restore", "clean", "add", "commit",
                "tag", "branch", "submodule", "config", "maintenance", "gc",
                "ls-remote"}
    assert not (a7._A7_GIT_READ_ONLY & mutating)


def test_git_helper_refuses_subcommand_outside_allowlist(tmp_path):
    repo = make_repo(tmp_path)
    sys.path.insert(0, str(BATTERY.parent))
    try:
        import a7_battery as a7
        import staleness_guard as sg
    finally:
        sys.path.pop(0)
    with pytest.raises(sg.StoppedError):
        a7._git(str(repo), ["push", "origin", "main"])


def test_stdlib_only():
    src = BATTERY.read_text(encoding="utf-8")
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
    body = _executable_source(BATTERY)
    assert "evidence_formatter" in body and "staleness_guard" in body
    for reused in ("normalize", "render_json", "render_markdown", "sanitize_text",
                   "enforce_limits", "resolve_repo", "observe", "validate_baseline"):
        assert reused in body, reused


def test_no_policy_weakening_path():
    body = _executable_source(BATTERY)
    for banned in ("disable_gate", "skip_gate", "allow_override", "bypass"):
        assert banned not in body, banned
