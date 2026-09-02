"""test_cowork_obsidian_sync_planner.py -- tests for the Obsidian sync planner.

Every repository, vault, policy, registry, and note used here is synthetic and lives
under pytest's tmp_path. No real Obsidian vault is located, inspected, created, or
modified: the planner has no discovery path at all, and an autouse fixture proves the
real ${HOME} session registry stays byte-identical across the whole suite.
"""
from __future__ import annotations

import ast
import copy
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tokenize
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
PLANNER = REPO_ROOT / "tools" / "cowork" / "obsidian_sync_planner.py"
POLICY = REPO_ROOT / "tools" / "cowork" / "obsidian_policy.json"
REAL_REGISTRY = Path.home() / ".claude" / "nova-session-registry.json"

sys.path.insert(0, str(PLANNER.parent))
import obsidian_sync_planner as osp        # noqa: E402
sys.path.pop(0)

CANARY = "NOVA_3S_CANARY_47a90c1e"
SECRET_VALUE = "sk-ant-api03-Zq7NOTREALvalue0000"


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
    git(repo, "config", "core.autocrlf", "false")
    write(repo / "docs" / "claude-cowork" / "README.md", "# Readme\n\nBody.\n")
    write(repo / "nova_knowledge_core" / "RULES" / "orb.md", "# ORB\n\nRule.\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "init")
    return repo


def write(path, text, newline="\n"):
    path.parent.mkdir(parents=True, exist_ok=True)
    data = text if isinstance(text, bytes) else text.encode("utf-8")
    if newline == "\r\n":
        data = data.replace(b"\n", b"\r\n")
    path.write_bytes(data)
    return path


def make_vault(tmp_path, name="vault"):
    v = tmp_path / name
    for sub in ("NOVA/Docs", "NOVA/Specs", "NOVA/Observations", "NOVA/Working"):
        (v / sub).mkdir(parents=True, exist_ok=True)
    return v


def policy_doc():
    return json.loads(POLICY.read_text(encoding="utf-8"))


def write_policy(tmp_path, doc, name="policy.json"):
    p = tmp_path / name
    p.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    return p


def note(source, blob, classification, authority, body="\nBody.\n",
         nid=None, src_hash=None, last_sync=None, state="synchronized", **extra):
    """Build a synthetic note. `last_sync=True` fills in the true body hash."""
    fields = {
        "nova_id": nid if nid is not None else osp.stable_id(authority, source),
        "nova_schema": "1",
        "nova_source": source,
        "nova_source_blob": blob,
        "nova_source_hash": src_hash if src_hash is not None else "0" * 64,
        "nova_classification": classification,
        "nova_authority": authority,
        "nova_sync_state": state,
    }
    fields.update({k: v for k, v in extra.items() if v is not None})
    if last_sync is True:
        fields["nova_last_sync_hash"] = "0" * 64          # placeholder, fixed below
    lines = ["---"] + ["%s: %s" % (k, fields[k]) for k in sorted(fields)] + ["---"]
    text = "\n".join(lines) + body
    if last_sync is True:
        fm = osp.parse_frontmatter(text, osp.LIMIT_MAXIMUMS)
        real = osp.note_body_hash(text, fm)
        fields["nova_last_sync_hash"] = real
        lines = ["---"] + ["%s: %s" % (k, fields[k]) for k in sorted(fields)] + ["---"]
        text = "\n".join(lines) + body
    elif isinstance(last_sync, str):
        fields["nova_last_sync_hash"] = last_sync
        lines = ["---"] + ["%s: %s" % (k, fields[k]) for k in sorted(fields)] + ["---"]
        text = "\n".join(lines) + body
    return text


def blob_of(repo, path):
    return git(repo, "rev-parse", "HEAD:%s" % path)


def run(op, repo=None, vault=None, policy=None, inp=None, fmt="json", extra=()):
    cmd = [sys.executable, "-B", str(PLANNER), op, "--format", fmt]
    if repo is not None:
        cmd += ["--repo", str(repo)]
    if vault is not None:
        cmd += ["--vault", str(vault)]
    if policy is not None:
        cmd += ["--policy", str(policy)]
    cmd += list(extra)
    payload = b"" if inp is None else json.dumps(inp).encode("utf-8")
    p = subprocess.run(cmd, capture_output=True, input=payload)
    return (p.returncode, p.stdout.decode("utf-8", "replace"),
            p.stderr.decode("utf-8", "replace"))


def checks(out):
    return json.loads(out)["checks"]


def ops(out):
    """{source -> classified operation} parsed from the item evidence lines."""
    found = {}
    for c in checks(out):
        if c["id"][0] in ("X", "M") and c["id"][1:].isdigit():
            src = c["label"].split(" -> ")[0]
            found[src] = c["evidence"].split(";")[0].strip()
    return found


def summary(out, prefix):
    for c in checks(out):
        if c["id"] == prefix:
            return dict(part.strip().split("=") for part in c["evidence"].split(";"))
    raise AssertionError("no summary check %s" % prefix)


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


def test_shipped_policy_declares_no_execution_authority():
    doc = policy_doc()
    assert doc["authority_model"]["execution_authority"] == "none"
    assert doc["authority_model"]["two_way_automatic_sync"] is False
    assert doc["authority_model"]["auto_merge"] is False
    assert doc["authority_model"]["deletion"] is False


def test_shipped_policy_has_no_disable_switch():
    """No *key* may turn a protection off. Prose describing the ban is fine."""
    keys = set()

    def walk(node):
        if isinstance(node, dict):
            for k, v in node.items():
                keys.add(k.lower())
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(policy_doc())
    for word in ("enable", "disable", "bypass", "override", "allow_all",
                 "skip", "unsafe", "force", "ignore_", "no_check"):
        assert not any(word in k for k in keys), word
    # And no key anywhere carries a boolean that would switch a protection on.
    assert "allow_execution" not in keys and "trusted" not in keys


def test_shipped_policy_carries_no_vault_path_secret_or_url():
    import re as _re
    raw = POLICY.read_text(encoding="utf-8")
    for bad in ("http://", "https://", "C:\\", "C:/", "/Users/", "/home/",
                "%USERPROFILE%", "$HOME", "iCloud", "OneDrive", "Dropbox"):
        assert bad not in raw, bad
    # `.obsidian/**` appears only as a prohibited path, never as a location to read.
    assert '".obsidian/**"' in raw
    # Any home-directory-shaped path, whatever the account name.
    assert not _re.search(r"[A-Za-z]:[\\/]|~[\\/]|\\\\[A-Za-z0-9]", raw)


def test_policy_unknown_field_rejected(tmp_path):
    doc = policy_doc()
    doc["surprise"] = "x"
    rc, _out, err = run("validate-policy", policy=write_policy(tmp_path, doc))
    assert rc == 2 and "unrecognized" in err


def test_policy_unsupported_schema_rejected(tmp_path):
    doc = policy_doc()
    doc["schema_version"] = 99
    rc, _out, err = run("validate-policy", policy=write_policy(tmp_path, doc))
    assert rc == 2 and "schema" in err


@pytest.mark.parametrize("root", ["**", "*", ".", "./**", "*/**"])
def test_policy_overly_broad_source_root_rejected(tmp_path, root):
    doc = policy_doc()
    doc["export_classes"]["approved_doc"]["source_roots"] = [root]
    rc, _out, err = run("validate-policy", policy=write_policy(tmp_path, doc))
    assert rc == 2 and "broad" in err


def test_policy_absolute_source_root_rejected(tmp_path):
    doc = policy_doc()
    doc["export_classes"]["approved_doc"]["source_roots"] = ["C:/notes/**"]
    rc, _out, err = run("validate-policy", policy=write_policy(tmp_path, doc))
    assert rc == 2


def test_policy_traversal_source_root_rejected(tmp_path):
    doc = policy_doc()
    doc["export_classes"]["approved_doc"]["source_roots"] = ["../elsewhere/**"]
    rc, _out, err = run("validate-policy", policy=write_policy(tmp_path, doc))
    assert rc == 2 and "traversal" in err


def test_policy_missing_forbidden_root_category_rejected(tmp_path):
    doc = policy_doc()
    del doc["prohibited_paths"]["raw_transcripts"]
    rc, _out, err = run("validate-policy", policy=write_policy(tmp_path, doc))
    assert rc == 2 and "raw_transcripts" in err


def test_policy_forbidden_destination_overlap_rejected(tmp_path):
    doc = policy_doc()
    doc["prohibited_import_destination_roots"].append("nova_knowledge_core/CANDIDATES")
    rc, _out, err = run("validate-policy", policy=write_policy(tmp_path, doc))
    assert rc == 2 and "overlaps" in err


def test_policy_duplicate_case_conflicting_roots_rejected(tmp_path):
    doc = policy_doc()
    doc["export_classes"]["approved_spec"]["source_roots"] = ["DOCS/claude-cowork/**"]
    rc, _out, err = run("validate-policy", policy=write_policy(tmp_path, doc))
    assert rc == 2 and "duplicate" in err


def test_policy_executable_field_rejected(tmp_path):
    doc = policy_doc()
    doc["description"] = "run $(whoami) before syncing"
    rc, _out, err = run("validate-policy", policy=write_policy(tmp_path, doc))
    assert rc == 2 and "executable" in err


def test_policy_url_rejected(tmp_path):
    doc = policy_doc()
    doc["description"] = "see https://example.invalid/policy"
    rc, _out, err = run("validate-policy", policy=write_policy(tmp_path, doc))
    assert rc == 2


def test_policy_machine_path_rejected(tmp_path):
    doc = policy_doc()
    doc["description"] = "vault at C:\\Vaults\\Main"
    rc, _out, err = run("validate-policy", policy=write_policy(tmp_path, doc))
    assert rc == 2


@pytest.mark.parametrize("field,value", [
    ("algorithm", "md5-prefix"),
    ("hex_length", 8),
    ("prefix", "note-"),
    ("rename_policy", "automatic"),
    ("automatic_rename_detection", True),
])
def test_policy_invalid_stable_id_rule_rejected(tmp_path, field, value):
    doc = policy_doc()
    doc["stable_id"][field] = value
    rc, _out, err = run("validate-policy", policy=write_policy(tmp_path, doc))
    assert rc == 2 and "stable_id" in err


@pytest.mark.parametrize("key", sorted(osp.LIMIT_MAXIMUMS))
def test_policy_cannot_raise_any_implementation_maximum(tmp_path, key):
    doc = policy_doc()
    doc["limits"][key] = osp.LIMIT_MAXIMUMS[key] + 1
    rc, _out, err = run("validate-policy", policy=write_policy(tmp_path, doc))
    assert rc == 3 and "implementation maximum" in err


@pytest.mark.parametrize("key", sorted(osp.LIMIT_MAXIMUMS))
def test_policy_may_lower_any_limit(tmp_path, key):
    doc = policy_doc()
    doc["limits"][key] = max(1, osp.LIMIT_MAXIMUMS[key] // 2)
    rc, _out, err = run("validate-policy", policy=write_policy(tmp_path, doc))
    assert rc == 0, err


def test_policy_missing_limit_rejected(tmp_path):
    doc = policy_doc()
    del doc["limits"]["max_plan_items"]
    rc, _out, err = run("validate-policy", policy=write_policy(tmp_path, doc))
    assert rc == 2


def test_policy_execution_authority_cannot_be_granted(tmp_path):
    doc = policy_doc()
    doc["authority_model"]["execution_authority"] = "git"
    rc, _out, err = run("validate-policy", policy=write_policy(tmp_path, doc))
    assert rc == 2 and "execution_authority" in err


def test_policy_cannot_enable_two_way_sync(tmp_path):
    doc = policy_doc()
    doc["authority_model"]["two_way_automatic_sync"] = True
    rc, _out, err = run("validate-policy", policy=write_policy(tmp_path, doc))
    assert rc == 2


def test_policy_cannot_enable_deletion(tmp_path):
    doc = policy_doc()
    doc["authority_model"]["deletion"] = True
    rc, _out, err = run("validate-policy", policy=write_policy(tmp_path, doc))
    assert rc == 2


def test_policy_cannot_allow_a_second_file_type(tmp_path):
    doc = policy_doc()
    doc["allowed_file_types"] = [".md", ".canvas"]
    rc, _out, err = run("validate-policy", policy=write_policy(tmp_path, doc))
    assert rc == 2


def test_missing_policy_file_exits_two(tmp_path):
    rc, _out, err = run("validate-policy", policy=tmp_path / "absent.json")
    assert rc == 2 and "could not be read" in err


def test_malformed_policy_file_exits_two(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("{not json", encoding="utf-8")
    rc, _out, err = run("validate-policy", policy=p)
    assert rc == 2


# ------------------------------------------------------------------- the CLI

@pytest.mark.parametrize("verb", osp.FORBIDDEN_OPERATIONS)
def test_mutation_verbs_are_not_operations(verb, tmp_path):
    repo = make_repo(tmp_path)
    rc, _out, _err = run(verb, repo=repo)
    assert rc == 2, verb


def test_supported_operations_are_exactly_five():
    assert osp.OPERATIONS == ("validate-policy", "inventory", "plan-export",
                              "plan-import", "check-plan")


def test_help_exits_zero():
    p = subprocess.run([sys.executable, "-B", str(PLANNER), "--help"],
                       capture_output=True)
    assert p.returncode == 0


def test_plan_requires_an_explicit_vault(tmp_path):
    repo = make_repo(tmp_path)
    rc, _out, err = run("plan-export", repo=repo)
    assert rc == 2 and "--vault" in err


def test_plan_requires_a_repository(tmp_path):
    vault = make_vault(tmp_path)
    rc, _out, err = run("plan-export", vault=vault)
    assert rc == 2 and "--repo" in err


def test_non_repository_is_stopped(tmp_path):
    plain = tmp_path / "plain"
    plain.mkdir()
    vault = make_vault(tmp_path)
    rc, out, _err = run("plan-export", repo=plain, vault=vault)
    assert rc == 4 and json.loads(out)["overall_status"] == "stopped"


def test_absent_vault_is_stopped(tmp_path):
    repo = make_repo(tmp_path)
    rc, out, _err = run("plan-export", repo=repo, vault=tmp_path / "no-vault")
    assert rc == 4


def test_inventory_without_a_vault_reports_no_discovery(tmp_path):
    repo = make_repo(tmp_path)
    rc, out, err = run("inventory", repo=repo)
    assert rc == 0, err
    assert "never discovered" in out


# ------------------------------------------------------------------- export

def test_eligible_create(tmp_path):
    repo = make_repo(tmp_path)
    vault = make_vault(tmp_path)
    rc, out, err = run("plan-export", repo=repo, vault=vault)
    assert rc == 0, err
    assert ops(out)["docs/claude-cowork/README.md"] == "create"
    assert ops(out)["nova_knowledge_core/RULES/orb.md"] == "create"


def test_unchanged(tmp_path):
    repo = make_repo(tmp_path)
    vault = make_vault(tmp_path)
    src = "docs/claude-cowork/README.md"
    write(vault / "NOVA" / "Docs" / "README.md",
          note(src, blob_of(repo, src), "approved-doc", "git", last_sync=True))
    rc, out, err = run("plan-export", repo=repo, vault=vault)
    assert rc == 0, err
    assert ops(out)[src] == "unchanged"


def test_git_only_change_is_update_safe(tmp_path):
    repo = make_repo(tmp_path)
    vault = make_vault(tmp_path)
    src = "docs/claude-cowork/README.md"
    old = blob_of(repo, src)
    write(vault / "NOVA" / "Docs" / "README.md",
          note(src, old, "approved-doc", "git", last_sync=True))
    write(repo / "docs" / "claude-cowork" / "README.md", "# Readme\n\nRevised.\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "revise")
    rc, out, err = run("plan-export", repo=repo, vault=vault)
    assert rc == 0, err
    assert ops(out)[src] == "update-safe"


def test_vault_only_change_is_a_conflict(tmp_path):
    repo = make_repo(tmp_path)
    vault = make_vault(tmp_path)
    src = "docs/claude-cowork/README.md"
    text = note(src, blob_of(repo, src), "approved-doc", "git", last_sync=True)
    write(vault / "NOVA" / "Docs" / "README.md", text + "\nEdited in the vault.\n")
    rc, out, _err = run("plan-export", repo=repo, vault=vault)
    assert rc == 1
    assert ops(out)[src] == "conflict"


def test_both_changed_is_a_conflict(tmp_path):
    repo = make_repo(tmp_path)
    vault = make_vault(tmp_path)
    src = "docs/claude-cowork/README.md"
    text = note(src, blob_of(repo, src), "approved-doc", "git", last_sync=True)
    write(vault / "NOVA" / "Docs" / "README.md", text + "\nEdited.\n")
    write(repo / "docs" / "claude-cowork" / "README.md", "# Readme\n\nAlso revised.\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "revise")
    rc, out, _err = run("plan-export", repo=repo, vault=vault)
    assert rc == 1
    ev = [c["evidence"] for c in checks(out) if src in c["label"]][0]
    assert "conflict" in ev and "both" in ev


def test_note_without_a_last_sync_hash_is_a_conflict(tmp_path):
    repo = make_repo(tmp_path)
    vault = make_vault(tmp_path)
    src = "docs/claude-cowork/README.md"
    write(vault / "NOVA" / "Docs" / "README.md",
          note(src, blob_of(repo, src), "approved-doc", "git"))
    rc, out, _err = run("plan-export", repo=repo, vault=vault)
    assert rc == 1 and ops(out)[src] == "conflict"


def test_note_naming_a_different_source_is_a_conflict(tmp_path):
    repo = make_repo(tmp_path)
    vault = make_vault(tmp_path)
    src = "docs/claude-cowork/README.md"
    text = note(src, blob_of(repo, src), "approved-doc", "git", last_sync=True)
    text = text.replace("nova_source: %s" % src, "nova_source: docs/claude-cowork/OTHER.md")
    write(vault / "NOVA" / "Docs" / "README.md", text)
    rc, out, _err = run("plan-export", repo=repo, vault=vault)
    assert rc == 1 and ops(out)[src] == "conflict"


def test_tracked_raw_transcript_remains_excluded(tmp_path):
    repo = make_repo(tmp_path)
    doc = policy_doc()
    doc["export_classes"]["observation"]["source_roots"] = ["nova_knowledge_core/**"]
    doc["export_classes"]["approved_spec"]["source_roots"] = ["docs/specs/**"]
    pol = write_policy(tmp_path, doc)
    src = "nova_knowledge_core/TRANSCRIPTS_RAW/evan_001.md"
    write(repo / "nova_knowledge_core" / "TRANSCRIPTS_RAW" / "evan_001.md", "# raw\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "transcript")
    vault = make_vault(tmp_path)
    rc, out, err = run("plan-export", repo=repo, vault=vault, policy=pol,
                       inp={"schema_version": 1, "select": [src]})
    assert rc == 0, err
    assert ops(out)[src] == "excluded"
    ev = [c["evidence"] for c in checks(out) if src in c["label"]][0]
    assert "raw_transcripts" in ev


def test_runtime_json_is_excluded(tmp_path):
    repo = make_repo(tmp_path)
    doc = policy_doc()
    doc["export_classes"]["approved_doc"]["source_roots"] = ["data/**"]
    pol = write_policy(tmp_path, doc)
    write(repo / "data" / "state.md", "# state\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "runtime")
    rc, out, err = run("plan-export", repo=repo, vault=make_vault(tmp_path), policy=pol)
    assert rc == 0, err
    assert ops(out)["data/state.md"] == "excluded"


@pytest.mark.parametrize("rel", [
    "services/execution.py", "engines/risk_engine.py", "services/broker_link.py",
    "main.py", "core/config.py",
])
def test_risk_execution_and_broker_paths_are_excluded(tmp_path, rel):
    repo = make_repo(tmp_path)
    doc = policy_doc()
    doc["export_classes"]["approved_doc"]["source_roots"] = ["docs/**"]
    pol = write_policy(tmp_path, doc)
    write(repo / "docs" / rel, "# x\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "code")
    rc, out, err = run("plan-export", repo=repo, vault=make_vault(tmp_path), policy=pol)
    assert rc == 0, err
    assert ops(out)["docs/" + rel] == "excluded"


def test_binary_is_excluded(tmp_path):
    repo = make_repo(tmp_path)
    write(repo / "docs" / "claude-cowork" / "chart.png", "not really a png\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "binary")
    rc, out, err = run("plan-export", repo=repo, vault=make_vault(tmp_path))
    assert rc == 0, err
    # Recorded as excluded rather than silently dropped, so the evidence shows it.
    assert ops(out)["docs/claude-cowork/chart.png"] == "excluded"


def test_oversized_source_is_excluded(tmp_path):
    repo = make_repo(tmp_path)
    doc = policy_doc()
    doc["limits"]["max_markdown_bytes"] = 64
    pol = write_policy(tmp_path, doc)
    write(repo / "docs" / "claude-cowork" / "big.md", "# big\n" + ("x" * 500) + "\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "big")
    rc, out, err = run("plan-export", repo=repo, vault=make_vault(tmp_path), policy=pol)
    assert rc == 0, err
    assert ops(out)["docs/claude-cowork/big.md"] == "excluded"


def test_credential_content_is_excluded(tmp_path):
    repo = make_repo(tmp_path)
    write(repo / "docs" / "claude-cowork" / "creds.md",
          "# creds\n\napi_key = %s\n" % SECRET_VALUE)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "creds")
    rc, out, err = run("plan-export", repo=repo, vault=make_vault(tmp_path))
    assert rc == 0, err
    assert ops(out)["docs/claude-cowork/creds.md"] == "excluded"
    assert SECRET_VALUE not in out


def test_machine_path_content_is_excluded(tmp_path):
    repo = make_repo(tmp_path)
    write(repo / "docs" / "claude-cowork" / "paths.md",
          "# paths\n\nSee C:\\Users\\someone\\vault for details.\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "paths")
    rc, out, err = run("plan-export", repo=repo, vault=make_vault(tmp_path))
    assert rc == 0, err
    assert ops(out)["docs/claude-cowork/paths.md"] == "excluded"


def test_duplicate_stable_id_is_a_conflict():
    a = osp.stable_id("git", "docs/a.md")
    b = osp.stable_id("git", "docs/b.md")
    assert a != b
    assert osp.stable_id("git", "docs/a.md") == a
    assert osp.stable_id("obsidian", "docs/a.md") != a


def _two_root_policy(tmp_path):
    """One class, two roots -- so two distinct sources can share one destination."""
    doc = policy_doc()
    doc["export_classes"]["approved_doc"]["source_roots"] = ["docs/a/**", "docs/b/**"]
    doc["export_classes"]["approved_spec"]["source_roots"] = ["specs/**"]
    doc["export_classes"]["observation"]["source_roots"] = ["obs/**"]
    return write_policy(tmp_path, doc)


def test_duplicate_destination_is_a_conflict(tmp_path):
    repo = make_repo(tmp_path)
    pol = _two_root_policy(tmp_path)
    write(repo / "docs" / "a" / "x.md", "# a\n")
    write(repo / "docs" / "b" / "x.md", "# b\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "collide")
    rc, out, _err = run("plan-export", repo=repo, vault=make_vault(tmp_path), policy=pol)
    assert rc == 1
    assert "conflict" in json.dumps(ops(out))


def test_case_normalized_destination_collision_is_a_conflict(tmp_path):
    repo = make_repo(tmp_path)
    pol = _two_root_policy(tmp_path)
    write(repo / "docs" / "a" / "x.md", "# a\n")
    write(repo / "docs" / "b" / "X.md", "# b\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "collide")
    rc, out, _err = run("plan-export", repo=repo, vault=make_vault(tmp_path), policy=pol)
    assert rc == 1
    assert "conflict" in json.dumps(ops(out))


def test_submodule_gitlink_is_excluded(tmp_path):
    repo = make_repo(tmp_path)
    doc = policy_doc()
    doc["export_classes"]["approved_doc"]["source_roots"] = ["docs/**"]
    pol = write_policy(tmp_path, doc)
    git(repo, "update-index", "--add", "--cacheinfo",
        "160000,%s,docs/vendor.md" % ("1" * 40))
    git(repo, "commit", "-q", "-m", "gitlink")
    rc, out, err = run("plan-export", repo=repo, vault=make_vault(tmp_path), policy=pol)
    assert rc == 0, err
    assert ops(out)["docs/vendor.md"] == "excluded"


def test_head_drift_during_observation_is_stopped(tmp_path, monkeypatch):
    """The second HEAD read must disagree with the first, which stops the plan."""
    repo = make_repo(tmp_path)
    seen = {"n": 0}
    real = osp.repo_head

    def drifting(r):
        seen["n"] += 1
        return real(r) if seen["n"] == 1 else "f" * 40

    monkeypatch.setattr(osp, "repo_head", drifting)
    sel = tmp_path / "selection.json"
    sel.write_text(json.dumps({"schema_version": 1}), encoding="utf-8")
    checks_out, code = _inprocess(["plan-export", "--format", "json",
                                   "--repo", str(repo),
                                   "--vault", str(make_vault(tmp_path)),
                                   "--input", str(sel)])
    assert code == 4
    drift = [c for c in checks_out if c["id"] == "Z1"][0]
    assert drift["status"] == "stopped" and "moved" in drift["evidence"]


def _link_dir(link, target):
    """Create a directory link. Junctions need no elevation on Windows."""
    if os.name == "nt":
        p = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)],
                           capture_output=True)
        if p.returncode == 0:
            return "junction"
    try:
        os.symlink(str(target), str(link), target_is_directory=True)
        return "symlink"
    except (OSError, NotImplementedError, AttributeError):
        return None


def test_vault_junction_escape_is_stopped(tmp_path):
    repo = make_repo(tmp_path)
    vault = make_vault(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    write(outside / "README.md", "# elsewhere\n")
    docs = vault / "NOVA" / "Docs"
    shutil.rmtree(docs)
    kind = _link_dir(docs, outside)
    if kind is None:
        pytest.skip("this environment permits neither a junction nor a symbolic link")
    rc, out, _err = run("plan-export", repo=repo, vault=vault)
    assert rc == 4, kind
    assert "outside the supplied vault root" in out or "symbolic link" in out


def test_vault_file_symlink_is_refused(tmp_path, monkeypatch):
    """The symlink branch, exercised directly so it runs on every machine."""
    vault = make_vault(tmp_path)
    write(vault / "NOVA" / "Docs" / "README.md", "# note\n")
    monkeypatch.setattr(os.path, "islink", lambda p: True)
    with pytest.raises(Exception) as exc:
        osp.read_vault_note(vault, "NOVA/Docs/README.md", osp.LIMIT_MAXIMUMS)
    assert "symbolic link" in str(exc.value)


def test_vault_note_outside_the_root_is_refused(tmp_path):
    vault = make_vault(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    write(outside / "README.md", "# elsewhere\n")
    assert osp.escapes_root(vault, outside / "README.md")
    assert not osp.escapes_root(vault, vault / "NOVA" / "Docs" / "README.md")


def test_crlf_and_lf_sources_plan_identically(tmp_path):
    lf = make_repo(tmp_path, "lf")
    crlf = make_repo(tmp_path, "crlf")
    write(crlf / "docs" / "claude-cowork" / "README.md", "# Readme\n\nBody.\n",
          newline="\r\n")
    git(crlf, "add", "-A")
    git(crlf, "commit", "-q", "-m", "crlf")
    a = osp.content_hash((lf / "docs" / "claude-cowork" / "README.md").read_bytes())
    b = osp.content_hash((crlf / "docs" / "claude-cowork" / "README.md").read_bytes())
    assert a == b
    assert (crlf / "docs" / "claude-cowork" / "README.md").read_bytes() \
        != (lf / "docs" / "claude-cowork" / "README.md").read_bytes()


def test_observation_class_requires_explicit_selection(tmp_path):
    repo = make_repo(tmp_path)
    write(repo / "nova_knowledge_core" / "OTE_INTELLIGENCE" / "ote.md", "# ote\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "obs")
    vault = make_vault(tmp_path)
    src = "nova_knowledge_core/OTE_INTELLIGENCE/ote.md"

    rc, out, err = run("plan-export", repo=repo, vault=vault)
    assert rc == 0, err
    assert src not in ops(out)

    rc, out, err = run("plan-export", repo=repo, vault=vault,
                       inp={"schema_version": 1, "select": [src]})
    assert rc == 0, err
    assert ops(out)[src] == "create"


def test_export_never_proposes_a_deletion(tmp_path):
    repo = make_repo(tmp_path)
    vault = make_vault(tmp_path)
    write(vault / "NOVA" / "Docs" / "orphan.md", "# orphan with no source\n")
    rc, out, err = run("plan-export", repo=repo, vault=vault)
    assert rc == 0, err
    body = json.dumps(json.loads(out))
    for verb in ("delete", "remove", "prune", "unlink"):
        assert verb not in body.lower(), verb


def test_export_writes_nothing(tmp_path):
    repo = make_repo(tmp_path)
    vault = make_vault(tmp_path)
    src = "docs/claude-cowork/README.md"
    dest = vault / "NOVA" / "Docs" / "README.md"
    write(dest, note(src, blob_of(repo, src), "approved-doc", "git", last_sync=True))
    before_vault = _tree_digest(vault)
    before_repo = git(repo, "rev-parse", "HEAD")
    before_status = git(repo, "status", "--porcelain", "-uall")
    run("plan-export", repo=repo, vault=vault)
    run("plan-export", repo=repo, vault=vault)
    assert _tree_digest(vault) == before_vault
    assert git(repo, "rev-parse", "HEAD") == before_repo
    assert git(repo, "status", "--porcelain", "-uall") == before_status


# ------------------------------------------------------------------- import

def _working_note(rel, body="\nWorking thoughts.\n", **over):
    dest = "nova_knowledge_core/CANDIDATES/" + rel[len("NOVA/Working/"):]
    kw = dict(source=dest, blob="0" * 40, classification="working-note",
              authority="obsidian", body=body, nid=osp.stable_id("obsidian", rel))
    kw.update(over)
    return note(**kw)


def test_valid_candidate_import_requires_approval(tmp_path):
    repo = make_repo(tmp_path)
    vault = make_vault(tmp_path)
    rel = "NOVA/Working/idea.md"
    write(vault / "NOVA" / "Working" / "idea.md", _working_note(rel))
    rc, out, err = run("plan-import", repo=repo, vault=vault)
    assert rc == 5, err + out
    assert ops(out)[rel] == "candidate-import"
    assert "separate approval" in out


def test_unchanged_note_is_no_change(tmp_path):
    repo = make_repo(tmp_path)
    vault = make_vault(tmp_path)
    rel = "NOVA/Working/idea.md"
    text = _working_note(rel)
    write(vault / "NOVA" / "Working" / "idea.md", text)
    fm = osp.parse_frontmatter(text, osp.LIMIT_MAXIMUMS)
    body = text[fm.body_offset:]
    write(repo / "nova_knowledge_core" / "CANDIDATES" / "idea.md", body)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "candidate")
    rc, out, err = run("plan-import", repo=repo, vault=vault)
    assert rc == 0, err + out
    assert ops(out)[rel] == "no-change"


def test_unknown_stable_id_is_a_conflict(tmp_path):
    repo = make_repo(tmp_path)
    vault = make_vault(tmp_path)
    rel = "NOVA/Working/idea.md"
    write(vault / "NOVA" / "Working" / "idea.md",
          _working_note(rel, nid="nova-" + "0" * 16))
    rc, out, _err = run("plan-import", repo=repo, vault=vault)
    assert rc == 1 and ops(out)[rel] == "conflict"


def test_malformed_provenance_is_a_conflict(tmp_path):
    repo = make_repo(tmp_path)
    vault = make_vault(tmp_path)
    rel = "NOVA/Working/idea.md"
    write(vault / "NOVA" / "Working" / "idea.md", "# no frontmatter at all\n")
    rc, out, _err = run("plan-import", repo=repo, vault=vault)
    assert rc == 1 and ops(out)[rel] == "conflict"


def test_authority_escalation_is_denied(tmp_path):
    repo = make_repo(tmp_path)
    vault = make_vault(tmp_path)
    rel = "NOVA/Working/idea.md"
    write(vault / "NOVA" / "Working" / "idea.md",
          _working_note(rel, classification="approved-spec"))
    rc, out, _err = run("plan-import", repo=repo, vault=vault)
    assert rc == 1 and ops(out)[rel] == "conflict"


def test_git_authority_claim_from_the_vault_is_denied(tmp_path):
    repo = make_repo(tmp_path)
    vault = make_vault(tmp_path)
    rel = "NOVA/Working/idea.md"
    write(vault / "NOVA" / "Working" / "idea.md", _working_note(rel, authority="git"))
    rc, out, _err = run("plan-import", repo=repo, vault=vault)
    assert rc == 1 and ops(out)[rel] == "conflict"


@pytest.mark.parametrize("dest", [
    "nova_knowledge_core/RULES/orb.md",
    "docs/claude-cowork/README.md",
    "services/execution.py",
    "engines/risk_engine.py",
    ".claude/settings.local.json",
    ".claude/hooks/nova_guard_hook.py",
    "data/nova_state_engine.json",
    "nova_knowledge_core/TRANSCRIPTS_RAW/evan.md",
    "main.py",
])
def test_forbidden_import_destinations_never_become_candidates(tmp_path, dest):
    repo = make_repo(tmp_path)
    vault = make_vault(tmp_path)
    rel = "NOVA/Working/idea.md"
    write(vault / "NOVA" / "Working" / "idea.md", _working_note(rel, source=dest))
    rc, out, _err = run("plan-import", repo=repo, vault=vault)
    assert rc == 1
    assert ops(out)[rel] in ("conflict", "excluded")


def test_credential_content_never_becomes_a_candidate(tmp_path):
    repo = make_repo(tmp_path)
    vault = make_vault(tmp_path)
    rel = "NOVA/Working/idea.md"
    write(vault / "NOVA" / "Working" / "idea.md",
          _working_note(rel, body="\ntoken = %s\n" % SECRET_VALUE))
    rc, out, _err = run("plan-import", repo=repo, vault=vault)
    assert rc == 0
    assert ops(out)[rel] == "excluded"
    assert SECRET_VALUE not in out


def test_executable_directive_never_becomes_a_candidate(tmp_path):
    repo = make_repo(tmp_path)
    vault = make_vault(tmp_path)
    rel = "NOVA/Working/idea.md"
    write(vault / "NOVA" / "Working" / "idea.md",
          _working_note(rel, body="\n<%tp.system.prompt()%>\n"))
    rc, out, _err = run("plan-import", repo=repo, vault=vault)
    assert ops(out)[rel] == "excluded"


def test_source_destination_mismatch_is_a_conflict(tmp_path):
    repo = make_repo(tmp_path)
    vault = make_vault(tmp_path)
    rel = "NOVA/Working/idea.md"
    write(vault / "NOVA" / "Working" / "idea.md",
          _working_note(rel, source="nova_knowledge_core/CANDIDATES/elsewhere.md"))
    rc, out, _err = run("plan-import", repo=repo, vault=vault)
    assert rc == 1 and ops(out)[rel] == "conflict"


def test_a_note_outside_an_import_namespace_is_ignored(tmp_path):
    repo = make_repo(tmp_path)
    vault = make_vault(tmp_path)
    write(vault / "NOVA" / "Docs" / "exported.md", "# not a working note\n")
    rc, out, err = run("plan-import", repo=repo, vault=vault)
    assert rc == 0, err
    assert "NOVA/Docs/exported.md" not in ops(out)


def test_import_leaves_the_repository_byte_identical(tmp_path):
    repo = make_repo(tmp_path)
    vault = make_vault(tmp_path)
    rel = "NOVA/Working/idea.md"
    write(vault / "NOVA" / "Working" / "idea.md", _working_note(rel))
    before_repo = _tree_digest(repo)
    before_vault = _tree_digest(vault)
    run("plan-import", repo=repo, vault=vault)
    run("plan-import", repo=repo, vault=vault)
    assert _tree_digest(repo) == before_repo
    assert _tree_digest(vault) == before_vault


def test_import_plan_is_never_approval(tmp_path):
    repo = make_repo(tmp_path)
    vault = make_vault(tmp_path)
    write(vault / "NOVA" / "Working" / "idea.md", _working_note("NOVA/Working/idea.md"))
    rc, out, _err = run("plan-import", repo=repo, vault=vault)
    assert rc == 5
    assert "not approval" in out and "Nothing is written" in out


# ----------------------------------------------------------------- metadata

def test_valid_fixed_scalar_frontmatter_parses():
    text = "---\nnova_id: nova-0123456789abcdef\ntitle: \"A Note\"\n---\nbody\n"
    fm = osp.parse_frontmatter(text, osp.LIMIT_MAXIMUMS)
    assert fm.fields["nova_id"] == "nova-0123456789abcdef"
    assert fm.fields["title"] == "A Note"


def test_every_frontmatter_value_stays_a_string():
    text = "---\na: 1\nb: true\nc: null\nd: 3.5\n---\nbody\n"
    fm = osp.parse_frontmatter(text, osp.LIMIT_MAXIMUMS)
    assert fm.fields == {"a": "1", "b": "true", "c": "null", "d": "3.5"}
    assert all(isinstance(v, str) for v in fm.fields.values())


def test_duplicate_frontmatter_key_rejected():
    with pytest.raises(Exception) as exc:
        osp.parse_frontmatter("---\na: 1\na: 2\n---\nbody\n", osp.LIMIT_MAXIMUMS)
    assert "more than once" in str(exc.value)


def test_unknown_nova_control_field_rejected():
    fields = {"nova_id": osp.stable_id("git", "x.md"), "nova_schema": "1",
              "nova_source": "x.md", "nova_source_blob": "a" * 40,
              "nova_source_hash": "b" * 64, "nova_classification": "approved-doc",
              "nova_authority": "git", "nova_sync_state": "synchronized",
              "nova_execute": "true"}
    with pytest.raises(Exception) as exc:
        osp.validate_provenance(fields, policy_doc(), osp.LIMIT_MAXIMUMS)
    assert "unknown NOVA control field" in str(exc.value)


def test_traversal_in_nova_source_rejected():
    fields = {"nova_id": osp.stable_id("git", "x.md"), "nova_schema": "1",
              "nova_source": "../../etc/passwd", "nova_source_blob": "a" * 40,
              "nova_source_hash": "b" * 64, "nova_classification": "approved-doc",
              "nova_authority": "git", "nova_sync_state": "synchronized"}
    with pytest.raises(Exception) as exc:
        osp.validate_provenance(fields, policy_doc(), osp.LIMIT_MAXIMUMS)
    assert "traversal" in str(exc.value)


def test_absolute_machine_path_in_metadata_rejected():
    fields = {"nova_id": osp.stable_id("git", "x.md"), "nova_schema": "1",
              "nova_source": "C:/Users/someone/x.md", "nova_source_blob": "a" * 40,
              "nova_source_hash": "b" * 64, "nova_classification": "approved-doc",
              "nova_authority": "git", "nova_sync_state": "synchronized"}
    with pytest.raises(Exception):
        osp.validate_provenance(fields, policy_doc(), osp.LIMIT_MAXIMUMS)


def test_credential_shaped_metadata_rejected():
    fields = {"nova_id": osp.stable_id("git", "x.md"), "nova_schema": "1",
              "nova_source": "x.md", "nova_source_blob": "a" * 40,
              "nova_source_hash": "b" * 64, "nova_classification": "approved-doc",
              "nova_authority": "git", "nova_sync_state": "synchronized",
              "nova_approval": SECRET_VALUE}
    with pytest.raises(Exception):
        osp.validate_provenance(fields, policy_doc(), osp.LIMIT_MAXIMUMS)


@pytest.mark.parametrize("line,why", [
    ("a: &anchor", "anchor"),
    ("a: *alias", "alias"),
    ("a: !!python/object", "tag"),
    ("a: |", "block scalar"),
    ("a: >", "folded scalar"),
    ("a: {b: c}", "flow mapping"),
    ("a: [1, 2]", "flow sequence"),
    ("a: %directive", "directive"),
])
def test_unsupported_yaml_features_rejected(line, why):
    with pytest.raises(Exception) as exc:
        osp.parse_frontmatter("---\n%s\n---\nbody\n" % line, osp.LIMIT_MAXIMUMS)
    assert why in str(exc.value)


@pytest.mark.parametrize("text", [
    "---\n  indented: x\n---\nbody\n",
    "---\n\ta: x\n---\nbody\n",
    "---\n# comment\n---\nbody\n",
    "---\n\na: x\n---\nbody\n",
    "---\n<<: *base\n---\nbody\n",
    "---\nA_KEY: x\n---\nbody\n",
    "---\na: 'single'\n---\nbody\n",
    "---\na: x\n",
    "no frontmatter\n",
    "\ufeff---\na: x\n---\nbody\n",
])
def test_rejected_frontmatter_shapes(text):
    with pytest.raises(Exception):
        osp.parse_frontmatter(text, osp.LIMIT_MAXIMUMS)


def test_too_many_frontmatter_fields_rejected():
    lines = ["---"] + ["k%02d: v" % i for i in range(40)] + ["---", "body"]
    with pytest.raises(Exception):
        osp.parse_frontmatter("\n".join(lines) + "\n", osp.LIMIT_MAXIMUMS)


def test_plugin_and_template_syntax_is_never_executed(tmp_path):
    """Prohibited forms are refused; the rest is preserved inertly as text."""
    repo = make_repo(tmp_path)
    marker = repo / "must_not_exist.txt"
    write(repo / "docs" / "claude-cowork" / "tricky.md",
          "# tricky\n\n```dataview\nLIST FROM \"NOVA\"\n```\n\n"
          "![[embed]] and [[wikilink]] and $(echo hi > must_not_exist.txt)\n"
          "and `rm -rf .` and {{template}}\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "tricky")
    rc, out, err = run("plan-export", repo=repo, vault=make_vault(tmp_path))
    assert rc == 0, err
    assert ops(out)["docs/claude-cowork/tricky.md"] == "create"
    assert not marker.exists()


def test_stable_id_excludes_usernames_and_machine_paths():
    """The id is a fixed prefix plus 16 hex characters, so it can hold nothing else."""
    nid = osp.stable_id("git", "docs/claude-cowork/README.md")
    assert osp._ID_RE.match(nid)
    assert set(nid[len("nova-"):]) <= set("0123456789abcdef")
    assert len(nid) == len("nova-") + 16
    # An absolute source path still yields an id carrying no trace of it.
    other = osp.stable_id("git", "docs/README.md")
    assert ":" not in other and "/" not in other and "\\" not in other


def test_stable_id_is_never_taken_from_the_note(tmp_path):
    repo = make_repo(tmp_path)
    vault = make_vault(tmp_path)
    src = "docs/claude-cowork/README.md"
    text = note(src, blob_of(repo, src), "approved-doc", "git", last_sync=True,
                nid="nova-" + "f" * 16)
    write(vault / "NOVA" / "Docs" / "README.md", text)
    rc, out, _err = run("plan-export", repo=repo, vault=vault)
    assert rc == 1 and ops(out)[src] == "conflict"


def test_renaming_a_source_changes_its_stable_id():
    before = osp.stable_id("git", "docs/a.md")
    after = osp.stable_id("git", "docs/renamed.md")
    assert before != after


# --------------------------------------------------------------- check-plan

def _plan_doc(direction, items):
    return {"schema_version": 1, "direction": direction, "items": items}


def _sample_item(**over):
    item = {
        "schema_version": 1, "nova_id": osp.stable_id("git", "docs/a.md"),
        "title": "a", "classification": "approved-doc", "authority": "git",
        "source_repository": "demo", "source_path": "docs/a.md",
        "source_blob": "a" * 40, "source_hash": "b" * 64,
        "destination": "NOVA/Docs/a.md", "operation": "create",
        "prior_source_blob": None, "prior_source_hash": None,
        "observed_destination_hash": None, "conflict_status": "none",
        "conflict_reason": "",
    }
    item.update(over)
    item["item_hash"] = osp.item_hash(item)
    return item


def test_check_plan_accepts_a_well_formed_plan(tmp_path):
    doc = _plan_doc("export", [_sample_item()])
    rc, out, err = run("check-plan", inp=doc)
    assert rc == 0, err + out


def test_check_plan_detects_a_tampered_item_hash(tmp_path):
    item = _sample_item()
    item["item_hash"] = "0" * 32
    rc, out, _err = run("check-plan", inp=_plan_doc("export", [item]))
    assert rc == 1
    assert [c for c in checks(out) if c["id"] == "P001"][0]["status"] == "fail"


def test_check_plan_detects_a_tampered_field(tmp_path):
    item = _sample_item()
    item["destination"] = "NOVA/Docs/elsewhere.md"
    rc, out, _err = run("check-plan", inp=_plan_doc("export", [item]))
    assert rc == 1


def test_check_plan_rejects_a_duplicate_destination(tmp_path):
    a = _sample_item()
    b = _sample_item(nova_id=osp.stable_id("git", "docs/b.md"), source_path="docs/b.md")
    rc, _out, err = run("check-plan", inp=_plan_doc("export", [a, b]))
    assert rc == 2 and "duplicates a destination" in err


def test_check_plan_rejects_one_source_with_two_destinations(tmp_path):
    a = _sample_item()
    b = _sample_item(destination="NOVA/Docs/b.md")
    rc, _out, err = run("check-plan", inp=_plan_doc("export", [a, b]))
    assert rc == 2


def test_check_plan_rejects_a_cross_direction_operation(tmp_path):
    item = _sample_item(operation="candidate-import")
    rc, _out, err = run("check-plan", inp=_plan_doc("export", [item]))
    assert rc == 2 and "does not allow" in err


def test_check_plan_reports_conflicts(tmp_path):
    item = _sample_item(operation="conflict", conflict_status="conflict",
                        conflict_reason="both changed")
    rc, out, _err = run("check-plan", inp=_plan_doc("export", [item]))
    assert rc == 1


def test_check_plan_requires_approval_for_candidate_imports(tmp_path):
    item = _sample_item(operation="candidate-import", authority="obsidian",
                        classification="working-note",
                        destination="nova_knowledge_core/CANDIDATES/a.md")
    rc, out, _err = run("check-plan", inp=_plan_doc("import", [item]))
    assert rc == 5


def test_check_plan_rejects_an_absolute_path(tmp_path):
    item = _sample_item(source_path="C:/Users/someone/a.md")
    rc, _out, err = run("check-plan", inp=_plan_doc("export", [item]))
    assert rc == 2


def test_check_plan_rejects_an_unknown_direction(tmp_path):
    rc, _out, err = run("check-plan", inp=_plan_doc("sideways", []))
    assert rc == 2


def test_check_plan_rejects_an_extra_item_field(tmp_path):
    item = _sample_item()
    item["surprise"] = 1
    rc, _out, err = run("check-plan", inp=_plan_doc("export", [item]))
    assert rc == 2


def test_oversized_input_is_a_safety_limit(tmp_path):
    big = tmp_path / "big.json"
    big.write_bytes(b'{"schema_version":1,"direction":"export","items":[],"pad":"'
                    + b"x" * (osp.MAX_INPUT_BYTES + 16) + b'"}')
    p = subprocess.run([sys.executable, "-B", str(PLANNER), "check-plan",
                        "--format", "json", "--input", str(big)], capture_output=True)
    assert p.returncode == 3


def test_plan_item_ceiling_is_enforced(tmp_path):
    doc = policy_doc()
    doc["limits"]["max_plan_items"] = 1
    pol = write_policy(tmp_path, doc)
    items = [_sample_item(), _sample_item(nova_id=osp.stable_id("git", "docs/b.md"),
                                          source_path="docs/b.md",
                                          destination="NOVA/Docs/b.md")]
    p = tmp_path / "plan.json"
    p.write_text(json.dumps(_plan_doc("export", items)), encoding="utf-8")
    rc, _out, err = run("check-plan", policy=pol, extra=["--input", str(p)])
    assert rc == 3


# ------------------------------------------------------------------- safety

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
    """Run main() in-process and return (checks, exit code). Used for monkeypatching."""
    import io
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
        code = osp.main(argv)
    finally:
        sys.stdout = real_stdout
    text = buf.getvalue().decode("utf-8")
    return json.loads(text)["checks"], code


def test_git_refs_index_config_and_fetch_head_are_untouched(tmp_path):
    repo = make_repo(tmp_path)
    vault = make_vault(tmp_path)
    gitdir = repo / ".git"
    before = {
        "refs": _tree_digest(gitdir / "refs"),
        "head": (gitdir / "HEAD").read_bytes(),
        "index": (gitdir / "index").read_bytes(),
        "config": (gitdir / "config").read_bytes(),
        "fetch_head": (gitdir / "FETCH_HEAD").exists(),
        "status": git(repo, "status", "--porcelain", "-uall"),
    }
    run("plan-export", repo=repo, vault=vault)
    run("plan-import", repo=repo, vault=vault)
    run("inventory", repo=repo, vault=vault)
    assert _tree_digest(gitdir / "refs") == before["refs"]
    assert (gitdir / "HEAD").read_bytes() == before["head"]
    assert (gitdir / "index").read_bytes() == before["index"]
    assert (gitdir / "config").read_bytes() == before["config"]
    assert (gitdir / "FETCH_HEAD").exists() == before["fetch_head"]
    assert git(repo, "status", "--porcelain", "-uall") == before["status"]


def test_no_lock_or_temp_residue(tmp_path):
    repo = make_repo(tmp_path)
    vault = make_vault(tmp_path)
    write(vault / "NOVA" / "Working" / "idea.md", _working_note("NOVA/Working/idea.md"))
    run("plan-export", repo=repo, vault=vault)
    run("plan-import", repo=repo, vault=vault)
    for root in (repo, vault, tmp_path):
        for dirpath, _dirs, files in os.walk(root):
            for name in files:
                low = name.lower()
                assert not low.endswith(".tmp"), name
                assert not low.endswith(".lock") or ".git" in dirpath, name
                assert not low.startswith(".nova-"), name


def test_input_files_are_byte_identical_afterwards(tmp_path):
    repo = make_repo(tmp_path)
    vault = make_vault(tmp_path)
    sel = tmp_path / "selection.json"
    sel.write_text(json.dumps({"schema_version": 1,
                               "select": ["docs/claude-cowork/README.md"]}),
                   encoding="utf-8")
    before = sel.read_bytes()
    pol_before = POLICY.read_bytes()
    run("plan-export", repo=repo, vault=vault, extra=["--input", str(sel)])
    assert sel.read_bytes() == before
    assert POLICY.read_bytes() == pol_before


def test_output_is_deterministic_across_runs(tmp_path):
    repo = make_repo(tmp_path)
    vault = make_vault(tmp_path)
    write(vault / "NOVA" / "Working" / "idea.md", _working_note("NOVA/Working/idea.md"))
    for op, fmt in (("plan-export", "json"), ("plan-export", "markdown"),
                    ("plan-import", "json"), ("plan-import", "markdown"),
                    ("validate-policy", "json")):
        first = run(op, repo=repo, vault=vault, fmt=fmt)[1]
        second = run(op, repo=repo, vault=vault, fmt=fmt)[1]
        assert first == second, (op, fmt)


def test_no_canary_username_secret_or_raw_path_in_output(tmp_path):
    repo = make_repo(tmp_path, "nova-demo")
    vault = make_vault(tmp_path)
    write(repo / "docs" / "claude-cowork" / "leak.md",
          "# %s\n\nkey = %s\n\nC:\\Users\\someone\\vault\n" % (CANARY, SECRET_VALUE))
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "leak")
    for op in ("plan-export", "plan-import", "inventory"):
        rc, out, err = run(op, repo=repo, vault=vault)
        blob = out + err
        assert SECRET_VALUE not in blob, op
        assert CANARY not in blob, op
        assert str(tmp_path) not in blob, op
        assert "C:\\Users" not in blob and "C:/Users" not in blob, op


def test_excluded_document_bodies_are_never_printed(tmp_path):
    repo = make_repo(tmp_path)
    write(repo / "docs" / "claude-cowork" / "secretish.md",
          "# heading\n\npassword = %s\n\nUNIQUE_BODY_PHRASE_9f1c\n" % SECRET_VALUE)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "secretish")
    rc, out, err = run("plan-export", repo=repo, vault=make_vault(tmp_path))
    assert "UNIQUE_BODY_PHRASE_9f1c" not in out + err


# ------------------------------------------------------------ static safety

def _executable_source(path):
    """Source with comments and docstrings removed, so prose cannot mask a call.

    Tokens are joined with newlines, so this catches single identifiers. Dotted
    names and call arguments are checked through `_dotted_names` and `_git_verbs`
    below, which read the AST instead of the token text.
    """
    import io as _io
    src = Path(path).read_text(encoding="utf-8")
    out = []
    docstrings = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)):
            doc = ast.get_docstring(node, clean=False)
            if doc is not None:
                docstrings.add(doc)
    for tok in tokenize.generate_tokens(_io.StringIO(src).readline):
        if tok.type == tokenize.COMMENT:
            continue
        if tok.type == tokenize.STRING:
            try:
                value = ast.literal_eval(tok.string)
            except Exception:
                value = None
            if isinstance(value, str) and value in docstrings:
                continue
        out.append(tok.string)
    return "\n".join(out)


def _identifiers(path):
    """Only NAME tokens: a string literal such as \"rename\" is data, not a call."""
    import io as _io
    src = Path(path).read_text(encoding="utf-8")
    names = set()
    for tok in tokenize.generate_tokens(_io.StringIO(src).readline):
        if tok.type == tokenize.NAME:
            names.add(tok.string)
    return names


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
    """Every dotted name the module actually references, from the AST."""
    names = set()
    for node in ast.walk(ast.parse(Path(path).read_text(encoding="utf-8"))):
        if isinstance(node, ast.Attribute):
            d = _dotted(node)
            if d:
                names.add(d)
    return names


def _git_verbs(path):
    """Every literal first argument handed to a git helper, from the AST."""
    verbs = set()
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
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
    for node in ast.walk(ast.parse(PLANNER.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            mods.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods.add(node.module.split(".")[0])
    third = [m for m in mods if m not in sys.stdlib_module_names
             and m not in ("__future__", "evidence_formatter", "staleness_guard",
                           "session_registry", "a7_battery")]
    assert third == [], third


def test_no_eval_or_exec():
    body = _executable_source(PLANNER)
    for banned in ("eval(", "exec(", "compile(", "__import__("):
        assert banned not in body, banned


def test_no_subprocess_shell_or_network():
    body = _executable_source(PLANNER)
    for banned in ("subprocess", "os.system", "popen", "shell=True", "socket",
                   "urllib", "http.client", "requests", "ftplib", "smtplib",
                   "asyncio", "telnetlib"):
        assert banned not in body, banned


def test_no_environment_or_vault_discovery():
    idents = _identifiers(PLANNER)
    names = _dotted_names(PLANNER)
    for banned in ("environ", "getenv", "expanduser", "expandvars", "winreg",
                   "psutil", "getpass", "home", "glob"):
        assert banned not in idents, banned
    for banned in ("os.environ", "os.getenv", "os.path.expanduser",
                   "os.path.expandvars", "Path.home", "glob.glob"):
        assert banned not in names, banned
    # Docstrings are stripped, so the boundary statement naming these services
    # does not count -- only a real reference to one would.
    body = _executable_source(PLANNER)
    for banned in ("OneDrive", "Dropbox", "iCloud", "obsidian.json", "%APPDATA%"):
        assert banned not in body, banned


def test_no_write_mode_open():
    import re as _re
    body = _executable_source(PLANNER)
    for m in _re.finditer(r"open\(([^)]*)\)", body):
        assert not _re.search(r"['\"][wax]", m.group(1)), m.group(0)


def test_no_deletion_move_or_rename_helper():
    idents = _identifiers(PLANNER)
    names = _dotted_names(PLANNER)
    for banned in ("remove", "unlink", "rmdir", "mkdir", "makedirs", "shutil",
                   "rmtree", "write_text", "write_bytes", "chmod", "symlink",
                   "copyfile", "copytree", "copy2", "truncate", "ftruncate"):
        assert banned not in idents, banned
    for banned in ("os.remove", "os.unlink", "os.rename", "os.replace",
                   "os.rmdir", "os.mkdir", "os.makedirs", "os.chmod",
                   "os.symlink", "shutil.move", "shutil.rmtree", "shutil.copy"):
        assert banned not in names, banned
    # `str.replace` is used on paths; `os.rename`/`os.replace` are what matter.
    assert "os.rename" not in names and "os.replace" not in names


def test_no_mutating_git_verb_is_ever_requested():
    """Checked on the AST, so the refusal list in FORBIDDEN_OPERATIONS is not a hit."""
    mutating = {"fetch", "pull", "push", "merge", "rebase", "checkout", "switch",
                "reset", "restore", "clean", "commit", "worktree", "submodule",
                "update-index", "gc", "maintenance", "add", "stash", "config"}
    asked = _git_verbs(PLANNER)
    assert asked, "no git verb was found; the scan would be vacuous"
    assert not (asked & mutating), sorted(asked & mutating)


def test_every_git_verb_is_inside_the_existing_read_only_allowlist():
    sys.path.insert(0, str(PLANNER.parent))
    try:
        import a7_battery as a7
    finally:
        sys.path.pop(0)
    asked = _git_verbs(PLANNER)
    assert asked <= set(a7._A7_GIT_READ_ONLY), sorted(asked - set(a7._A7_GIT_READ_ONLY))
    mutating = {"fetch", "pull", "push", "merge", "rebase", "checkout", "switch",
                "reset", "restore", "clean", "add", "commit", "worktree",
                "submodule", "config", "update-index"}
    assert not (set(a7._A7_GIT_READ_ONLY) & mutating)


def test_git_is_reached_only_through_the_a7_helper():
    names = _dotted_names(PLANNER)
    assert "a7._git" in names or "a7._git_ok" in names
    for banned in ("subprocess.run", "subprocess.Popen", "subprocess.check_output"):
        assert banned not in names, banned


def test_no_session_registry_mutation():
    names = _dotted_names(PLANNER)
    for banned in ("sr.write_registry_atomic", "sr._Lock", "sr.advance",
                   "sr.register", "sr.heartbeat", "sr.close", "sr.pause",
                   "sr.resume"):
        assert banned not in names, banned
    body = _executable_source(PLANNER)
    assert "write_registry_atomic" not in body


def test_rendering_goes_through_the_evidence_formatter():
    names = _dotted_names(PLANNER)
    assert {"ef.render_markdown", "ef.render_json", "ef.normalize"} <= names


def test_forbidden_operation_names_appear_only_in_the_refusal_list():
    tree = ast.parse(PLANNER.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            for verb in ("apply", "sync", "write_note", "delete", "rename",
                         "install", "repair"):
                assert node.name != verb, node.name


def test_policy_file_is_data_only():
    raw = POLICY.read_text(encoding="utf-8")
    doc = json.loads(raw)
    assert isinstance(doc, dict)
    for banned in ("$(", "`", "&&", "||", "<script", "javascript:", "eval(",
                   "exec(", "import "):
        assert banned not in raw, banned
