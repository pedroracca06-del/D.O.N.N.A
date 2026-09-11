"""test_cowork_test_selector.py -- tests for the Cowork test selector.

Every repository, manifest, policy, and registry used here is synthetic and lives
under pytest's tmp_path. An autouse fixture proves the real ${HOME} session registry
stays byte-identical across the whole suite, and static tests prove the selector
imports no module and never invokes pytest.
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
SELECTOR = REPO_ROOT / "tools" / "cowork" / "test_selector.py"
POLICY = REPO_ROOT / "tools" / "cowork" / "test_selection_policy.json"
REAL_REGISTRY = Path.home() / ".claude" / "nova-session-registry.json"

sys.path.insert(0, str(SELECTOR.parent))
import test_selector as ts               # noqa: E402
sys.path.pop(0)

CANARY = "NOVA_3V_CANARY_9c41be07"
SECRET_VALUE = "sk-ant-api03-Zq7NOTREALvalue00000000"

OK, INVALID, LIMIT, STOPPED, FULL = 0, 2, 3, 4, 5


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
    """A small repository whose import graph is fully statically resolvable."""
    repo = tmp_path / name
    repo.mkdir(parents=True)
    git(repo, "init", "-q", "-b", "work")
    git(repo, "config", "user.email", "t@example.invalid")
    git(repo, "config", "user.name", "T")
    git(repo, "config", "core.autocrlf", "false")

    write(repo / ".gitignore", "data/*.json\n")
    write(repo / "pytest.ini", "[pytest]\ntestpaths = tests\n")
    write(repo / "core" / "__init__.py", "")
    write(repo / "core" / "base.py", "VALUE = 1\n")
    write(repo / "core" / "middle.py", "from core.base import VALUE\nDOUBLE = VALUE\n")
    write(repo / "engines" / "__init__.py", "")
    write(repo / "engines" / "top.py",
          "from core.middle import DOUBLE\n\n\ndef run():\n    return DOUBLE\n")
    write(repo / "ui" / "__init__.py", "")
    write(repo / "ui" / "panel.py", "PANEL = 'p'\n")

    write(repo / "tests" / "__init__.py", "")
    write(repo / "tests" / "conftest.py", "import pytest\n")
    write(repo / "tests" / "helpers.py", "def helper():\n    return 7\n")
    write(repo / "tests" / "test_top.py",
          "from engines.top import run\n\n\ndef test_run():\n    assert run() == 1\n")
    write(repo / "tests" / "test_base_direct.py",
          "from core.base import VALUE\n\n\ndef test_v():\n    assert VALUE == 1\n")
    write(repo / "tests" / "test_panel.py",
          "from ui.panel import PANEL\n\n\ndef test_p():\n    assert PANEL == 'p'\n")
    write(repo / "tests" / "test_with_helper.py",
          "from tests.helpers import helper\n\n\ndef test_h():\n    assert helper() == 7\n")
    write(repo / "tests" / "sub" / "conftest.py", "import pytest\n")
    write(repo / "tests" / "sub" / "test_nested.py",
          "def test_nested():\n    assert True\n")
    write(repo / "docs" / "guide.md", "# guide\n")

    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "init")
    return repo


def policy_doc():
    return json.loads(POLICY.read_text(encoding="utf-8"))


def demo_policy(**over):
    """A policy scoped to the synthetic repository's layout."""
    doc = policy_doc()
    doc["test_roots"] = ["tests"]
    doc["source_roots"] = ["core", "engines", "ui", "tools", "main.py"]
    doc["explicit_mappings"] = [
        {"id": "panel_data", "paths": ["ui/panel_data.json"],
         "tests": ["tests/test_panel.py"], "reason": "the panel reads this data"},
        {"id": "no_target", "paths": ["ui/orphan_data.json"], "tests": [],
         "reason": "declares no focused target on purpose"},
    ]
    doc["global_impact_paths"] = ["pytest.ini", ".gitignore", "requirements.txt"]
    doc["documentation_only_paths"] = ["docs/**", "*.md"]
    doc["exclusions"] = ["data/**", "**/__pycache__/**", "*.pyc"]
    doc.update(over)
    return doc


def write_policy(tmp_path, doc, name="policy.json"):
    p = tmp_path / name
    p.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    return p


def run(mode, repo=None, policy=None, inp=None, fmt="json", extra=()):
    cmd = [sys.executable, "-B", str(SELECTOR), mode, "--format", fmt]
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


def selected(out):
    """{test path -> mapping source}."""
    found = {}
    for c in checks(out):
        if c["id"].startswith("S") and c["id"][1:].isdigit() and c["id"] != "S0":
            found[c["label"]] = c["evidence"].split(" -- ")[0].strip()
    return found


def escalations(out):
    return {c["label"]: c["evidence"] for c in checks(out)
            if c["id"].startswith("E") and c["id"][1:].isdigit()}


def dynamic_inventory(out):
    """The Y-block: repository-relative paths reported as dynamic tests."""
    return [c["label"] for c in checks(out)
            if c["id"].startswith("Y") and c["id"][1:].isdigit()
            and c["id"] != "Y0"]


def dynamic_summary(out):
    for c in checks(out):
        if c["id"] == "Y0":
            return c["evidence"]
    return None


def dynamic_added(out):
    for c in checks(out):
        if c["id"] == "Y_ADD":
            return c["evidence"]
    return None


def documentation(out):
    return sorted(c["label"] for c in checks(out)
                  if c["id"].startswith("D") and c["id"][1:].isdigit())


def proposed(out):
    for c in checks(out):
        if c["id"] == "R2":
            return c["evidence"].split(" -- ")[0].strip()
    return None


def manifest(paths, **over):
    changes = []
    for entry in paths:
        if isinstance(entry, str):
            changes.append({"path": entry, "kind": "modify"})
        else:
            changes.append(dict(entry))
    doc = {"schema_version": 1, "changes": changes}
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


@pytest.fixture
def demo(tmp_path):
    return make_repo(tmp_path), write_policy(tmp_path, demo_policy())


# ------------------------------------------------------------- the contract

def test_shipped_policy_validates():
    rc, out, err = run("validate-policy")
    assert rc == OK, err
    assert json.loads(out)["overall_status"] in ("passed", "passed_with_warnings")


@pytest.mark.parametrize("key,bad", [
    ("focused_selection_is_advisory_only", False),
    ("full_regression_required", False),
    ("collection_parity_required", False),
    ("can_satisfy_a7_7", True),
    ("can_replace_collection_parity", True),
    ("can_replace_full_regression", True),
    ("claims_unselected_tests_pass", True),
    ("authorizes_staging_or_commit", True),
    ("unmappable_path_escalates_to_full_suite", False),
    ("selector_invokes_collection", True),
    ("selector_imports_modules", True),
    ("dynamic_test_safety_inclusion_enabled", False),
    ("source_side_dynamic_ambiguity_escalates", False),
    ("dynamic_tests_can_be_excluded", True),
    ("policy_can_downgrade_an_escalation", True),
])
def test_contract_values_are_fixed(tmp_path, key, bad):
    doc = policy_doc()
    doc["contract"][key] = bad
    rc, _out, err = run("validate-policy", policy=write_policy(tmp_path, doc))
    assert rc == INVALID and key in err


def test_policy_cannot_set_full_regression_false(tmp_path):
    doc = policy_doc()
    doc["contract"]["full_regression_required"] = False
    rc, _out, err = run("validate-policy", policy=write_policy(tmp_path, doc))
    assert rc == INVALID
    assert "advisory only" in err


def test_every_report_states_full_regression_and_parity_required(demo):
    repo, pol = demo
    for mode, extra, inp in (
            ("validate-policy", (), None),
            ("select-manifest", (), manifest(["core/base.py"])),
            ("select-worktree", (), None)):
        rc, out, err = run(mode, repo=repo, policy=pol, inp=inp, extra=extra)
        ids = {c["id"]: c["evidence"] for c in checks(out)}
        assert "true" in ids["K1"], mode
        assert "true" in ids["K2"], mode
        assert "never satisfies A7.7" in ids["K3"], mode
        assert "no claim is made" in ids["K4"], mode
        assert "authorizes nothing" in ids["K5"], mode


def test_notes_repeat_the_governing_rule(demo):
    repo, pol = demo
    rc, out, _err = run("select-manifest", repo=repo, policy=pol,
                        inp=manifest(["core/base.py"]))
    body = json.dumps(json.loads(out))
    assert "fast local feedback aid only" in body
    assert "remain mandatory before any commit" in body


# ------------------------------------------------------------------ modes

def test_supported_modes_are_exactly_six():
    assert ts.MODES == ("select-worktree", "select-staged", "select-commit",
                        "select-range", "select-manifest", "validate-policy")


@pytest.mark.parametrize("verb", ["run", "execute", "collect", "pytest", "apply",
                                  "approve", "commit"])
def test_execution_verbs_are_not_modes(verb, demo):
    repo, pol = demo
    rc, _out, _err = run(verb, repo=repo, policy=pol)
    assert rc == INVALID, verb


def test_help_exits_zero():
    p = subprocess.run([sys.executable, "-B", str(SELECTOR), "--help"],
                       capture_output=True)
    assert p.returncode == 0


def test_all_modes_require_a_repository(tmp_path):
    for mode in ("select-worktree", "select-staged", "select-commit",
                 "select-range", "select-manifest"):
        rc, _out, err = run(mode, inp=manifest(["core/base.py"]))
        assert rc == INVALID and "--repo" in err, mode


def test_select_worktree(demo):
    repo, pol = demo
    write(repo / "core" / "base.py", "VALUE = 2\n")
    rc, out, err = run("select-worktree", repo=repo, policy=pol)
    assert rc == OK, err + out
    assert "tests/test_base_direct.py" in selected(out)


def test_select_staged(demo):
    repo, pol = demo
    write(repo / "ui" / "panel.py", "PANEL = 'q'\n")
    git(repo, "add", "-A")
    rc, out, err = run("select-staged", repo=repo, policy=pol)
    assert rc == OK, err + out
    assert set(selected(out)) == {"tests/test_panel.py"}


def test_select_staged_ignores_unstaged(demo):
    repo, pol = demo
    write(repo / "ui" / "panel.py", "PANEL = 'q'\n")
    rc, out, _err = run("select-staged", repo=repo, policy=pol)
    assert rc == STOPPED


def test_select_commit(demo):
    repo, pol = demo
    write(repo / "ui" / "panel.py", "PANEL = 'q'\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "panel")
    rc, out, err = run("select-commit", repo=repo, policy=pol,
                       extra=["--commit", git(repo, "rev-parse", "HEAD")])
    assert rc == OK, err + out
    assert set(selected(out)) == {"tests/test_panel.py"}


def test_select_commit_rejects_a_bad_object_id(demo):
    repo, pol = demo
    rc, _out, err = run("select-commit", repo=repo, policy=pol,
                        extra=["--commit", "not-an-oid"])
    assert rc == INVALID


def test_select_range(demo):
    repo, pol = demo
    base = git(repo, "rev-parse", "HEAD")
    write(repo / "ui" / "panel.py", "PANEL = 'q'\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "one")
    head = git(repo, "rev-parse", "HEAD")
    rc, out, err = run("select-range", repo=repo, policy=pol,
                       extra=["--base", base, "--head", head])
    assert rc == OK, err + out
    assert set(selected(out)) == {"tests/test_panel.py"}


def test_select_range_requires_both_ends(demo):
    repo, pol = demo
    rc, _out, err = run("select-range", repo=repo, policy=pol,
                        extra=["--base", "HEAD"])
    assert rc == INVALID


def test_select_manifest(demo):
    repo, pol = demo
    rc, out, err = run("select-manifest", repo=repo, policy=pol,
                       inp=manifest(["ui/panel.py"]))
    assert rc == OK, err + out
    assert set(selected(out)) == {"tests/test_panel.py"}


# --------------------------------------------------------------- mapping

def test_changed_test_selects_itself(demo):
    repo, pol = demo
    rc, out, err = run("select-manifest", repo=repo, policy=pol,
                       inp=manifest(["tests/test_panel.py"]))
    assert rc == OK, err + out
    assert selected(out) == {"tests/test_panel.py": "self"}


def test_direct_import_mapping(demo):
    repo, pol = demo
    rc, out, err = run("select-manifest", repo=repo, policy=pol,
                       inp=manifest(["ui/panel.py"]))
    assert rc == OK, err + out
    assert selected(out)["tests/test_panel.py"] == "direct import"


def test_transitive_import_mapping(demo):
    """core/base.py -> core/middle.py -> engines/top.py -> tests/test_top.py."""
    repo, pol = demo
    rc, out, err = run("select-manifest", repo=repo, policy=pol,
                       inp=manifest(["core/base.py"]))
    assert rc == OK, err + out
    got = selected(out)
    assert got["tests/test_top.py"] == "transitive import"
    assert got["tests/test_base_direct.py"] == "direct import"


def test_relative_import_is_resolved(tmp_path):
    repo = make_repo(tmp_path)
    write(repo / "engines" / "sibling.py", "SIB = 1\n")
    write(repo / "engines" / "uses_relative.py", "from .sibling import SIB\nX = SIB\n")
    write(repo / "tests" / "test_relative.py",
          "from engines.uses_relative import X\n\n\ndef test_x():\n    assert X == 1\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "relative")
    pol = write_policy(tmp_path, demo_policy())
    rc, out, err = run("select-manifest", repo=repo, policy=pol,
                       inp=manifest(["engines/sibling.py"]))
    assert rc == OK, err + out
    assert "tests/test_relative.py" in selected(out)


def test_shared_test_helper_selects_dependents(demo):
    repo, pol = demo
    rc, out, err = run("select-manifest", repo=repo, policy=pol,
                       inp=manifest(["tests/helpers.py"]))
    assert rc == OK, err + out
    assert "tests/test_with_helper.py" in selected(out)


def test_conftest_selects_its_subtree(demo):
    repo, pol = demo
    rc, out, err = run("select-manifest", repo=repo, policy=pol,
                       inp=manifest(["tests/conftest.py"]))
    assert rc == OK, err + out
    got = selected(out)
    assert set(got) >= {"tests/test_top.py", "tests/test_panel.py",
                        "tests/sub/test_nested.py"}
    assert all(v == "conftest scope" for v in got.values())


def test_nested_conftest_selects_only_its_subtree(demo):
    repo, pol = demo
    rc, out, err = run("select-manifest", repo=repo, policy=pol,
                       inp=manifest(["tests/sub/conftest.py"]))
    assert rc == OK, err + out
    assert set(selected(out)) == {"tests/sub/test_nested.py"}


def test_explicit_policy_mapping(tmp_path):
    repo = make_repo(tmp_path)
    write(repo / "ui" / "panel_data.json", "{}\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "data")
    pol = write_policy(tmp_path, demo_policy())
    rc, out, err = run("select-manifest", repo=repo, policy=pol,
                       inp=manifest(["ui/panel_data.json"]))
    assert rc == OK, err + out
    assert selected(out) == {"tests/test_panel.py": "explicit policy"}


def test_explicit_mapping_with_no_target_escalates(tmp_path):
    repo = make_repo(tmp_path)
    write(repo / "ui" / "orphan_data.json", "{}\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "orphan")
    pol = write_policy(tmp_path, demo_policy())
    rc, out, _err = run("select-manifest", repo=repo, policy=pol,
                        inp=manifest(["ui/orphan_data.json"]))
    assert rc == FULL
    assert "ui/orphan_data.json" in escalations(out)


def test_a_direct_edge_is_never_downgraded_to_transitive(demo):
    """test_base_direct imports core.base directly and also reaches it via nothing."""
    repo, pol = demo
    rc, out, _err = run("select-manifest", repo=repo, policy=pol,
                        inp=manifest(["core/base.py"]))
    assert selected(out)["tests/test_base_direct.py"] == "direct import"


# ------------------------------------------------------------- escalation

@pytest.mark.parametrize("path", ["pytest.ini", ".gitignore"])
def test_global_impact_path_escalates(demo, path):
    repo, pol = demo
    rc, out, _err = run("select-manifest", repo=repo, policy=pol,
                        inp=manifest([path]))
    assert rc == FULL
    assert "global-impact" in escalations(out)[path]
    assert proposed(out) == "python -B -m pytest -q"


def test_unmapped_path_escalates(demo):
    repo, pol = demo
    rc, out, _err = run("select-manifest", repo=repo, policy=pol,
                        inp=manifest(["strange/thing.xyz"]))
    assert rc == FULL
    assert "not mapped by any rule" in escalations(out)["strange/thing.xyz"]


def test_source_with_no_importing_test_escalates(tmp_path):
    repo = make_repo(tmp_path)
    write(repo / "engines" / "lonely.py", "LONELY = 1\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "lonely")
    pol = write_policy(tmp_path, demo_policy())
    rc, out, _err = run("select-manifest", repo=repo, policy=pol,
                        inp=manifest(["engines/lonely.py"]))
    assert rc == FULL
    assert "no statically discovered test imports" in escalations(out)["engines/lonely.py"]


def test_syntax_error_escalates(tmp_path):
    repo = make_repo(tmp_path)
    write(repo / "engines" / "broken.py", "def oops(:\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "broken")
    pol = write_policy(tmp_path, demo_policy())
    rc, out, _err = run("select-manifest", repo=repo, policy=pol,
                        inp=manifest(["engines/broken.py"]))
    assert rc == FULL
    assert "could not be parsed" in escalations(out)["engines/broken.py"]


@pytest.mark.parametrize("body", [
    "import importlib\nm = importlib.import_module('core.base')\n\n\ndef test_d():\n    assert m\n",
    "def test_d():\n    mod = __import__('core.base')\n    assert mod\n",
    "src = 'X = 1'\nns = {}\nexec(compile(src, 'x', 'exec'), ns)\n\n\ndef test_e():\n    assert ns\n",
])
def test_dynamic_import_test_is_always_included(tmp_path, body):
    """A dynamic TEST is included conservatively; it no longer forces the full suite.

    This replaces the earlier all-or-nothing rule. The safety intent is unchanged --
    a test whose imports cannot be read is never dropped -- but one such file may no
    longer collapse every other change to a full-suite fallback.
    """
    repo = make_repo(tmp_path)
    write(repo / "tests" / "test_dynamic.py", body)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "dynamic")
    pol = write_policy(tmp_path, demo_policy())
    rc, out, err = run("select-manifest", repo=repo, policy=pol,
                       inp=manifest(["ui/panel.py"]))
    assert rc == OK, err + out
    assert selected(out)["tests/test_dynamic.py"] == "dynamic-test safety inclusion"
    assert selected(out)["tests/test_panel.py"] == "direct import"
    assert escalations(out) == {}
    assert dynamic_inventory(out) == ["tests/test_dynamic.py"]


def test_unsafe_wildcard_import_in_a_test_is_included_not_dropped(tmp_path):
    """A star import from an unresolvable module is unknowable, so the test joins
    every focused selection instead of forcing the whole repository to run."""
    repo = make_repo(tmp_path)
    write(repo / "tests" / "test_star.py",
          "from core.missing_module import *\n\n\ndef test_s():\n    assert True\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "star")
    pol = write_policy(tmp_path, demo_policy())
    rc, out, err = run("select-manifest", repo=repo, policy=pol,
                       inp=manifest(["ui/panel.py"]))
    assert rc == OK, err + out
    assert selected(out)["tests/test_star.py"] == "dynamic-test safety inclusion"


def test_unsafe_wildcard_import_in_changed_source_escalates(tmp_path):
    """The concession is test-side only: an unknowable SOURCE still escalates."""
    repo = make_repo(tmp_path)
    write(repo / "engines" / "star_src.py", "from core.missing_module import *\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "star source")
    pol = write_policy(tmp_path, demo_policy())
    rc, out, _err = run("select-manifest", repo=repo, policy=pol,
                        inp=manifest(["engines/star_src.py"]))
    assert rc == FULL
    assert "engines/star_src.py" in escalations(out)


def test_resolvable_wildcard_import_is_an_ordinary_edge(tmp_path):
    repo = make_repo(tmp_path)
    write(repo / "tests" / "test_star_ok.py",
          "from core.base import *\n\n\ndef test_s():\n    assert True\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "star ok")
    pol = write_policy(tmp_path, demo_policy())
    rc, out, err = run("select-manifest", repo=repo, policy=pol,
                       inp=manifest(["core/base.py"]))
    assert rc == OK, err + out
    assert "tests/test_star_ok.py" in selected(out)


def test_unresolved_internal_import_escalates(tmp_path):
    repo = make_repo(tmp_path)
    write(repo / "engines" / "bad_import.py", "from core.does_not_exist import Z\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "bad import")
    pol = write_policy(tmp_path, demo_policy())
    rc, out, _err = run("select-manifest", repo=repo, policy=pol,
                        inp=manifest(["engines/bad_import.py"]))
    assert rc == FULL


def test_external_import_is_not_an_escalation(demo):
    """`import json` must not look like an unresolved internal module."""
    repo, pol = demo
    rc, out, err = run("select-manifest", repo=repo, policy=pol,
                       inp=manifest(["ui/panel.py"]))
    assert rc == OK, err + out


def test_binary_change_escalates(demo):
    repo, pol = demo
    rc, out, _err = run("select-manifest", repo=repo, policy=pol,
                        inp=manifest([{"path": "ui/logo.png", "kind": "add",
                                       "binary": True}]))
    assert rc == FULL
    assert "binary" in escalations(out)["ui/logo.png"]


def test_ambiguous_basename_escalates(tmp_path):
    """Two tracked files with the same stem make a bare import unresolvable."""
    repo = make_repo(tmp_path)
    write(repo / "engines" / "shared.py", "A = 1\n")
    write(repo / "ui" / "shared.py", "B = 2\n")
    write(repo / "tests" / "test_ambig.py",
          "import shared\n\n\ndef test_a():\n    assert shared\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "ambiguous")
    pol = write_policy(tmp_path, demo_policy())
    rc, out, _err = run("select-manifest", repo=repo, policy=pol,
                        inp=manifest(["tests/test_ambig.py"]))
    # The changed test still selects itself, but its unresolved import escalates.
    assert rc == FULL


# ------------------------------------------------------- deletion / rename

def test_deletion_selects_the_prior_dependents(demo):
    repo, pol = demo
    rc, out, err = run("select-manifest", repo=repo, policy=pol,
                       inp=manifest([{"path": "ui/panel.py", "kind": "delete"}]))
    assert rc == OK, err + out
    assert "tests/test_panel.py" in selected(out)


def test_deletion_of_a_test_escalates(demo):
    repo, pol = demo
    git(repo, "rm", "-q", "--", "tests/test_panel.py")
    git(repo, "commit", "-q", "-m", "remove test")
    rc, out, _err = run("select-commit", repo=repo, policy=pol,
                        extra=["--commit", git(repo, "rev-parse", "HEAD")])
    assert rc == FULL
    assert "cannot select itself" in escalations(out)["tests/test_panel.py"]


def test_rename_evaluates_both_sides(demo):
    repo, pol = demo
    rc, out, err = run("select-manifest", repo=repo, policy=pol,
                       inp=manifest([{"path": "ui/renamed_panel.py", "kind": "rename",
                                      "source_path": "ui/panel.py"}]))
    assert rc == FULL
    # The old side maps to its dependents; the new side has no importer yet.
    assert "ui/renamed_panel.py" in escalations(out)


def test_rename_of_a_test_keeps_both_sides(demo):
    repo, pol = demo
    rc, out, err = run("select-manifest", repo=repo, policy=pol,
                       inp=manifest([{"path": "tests/test_panel_v2.py",
                                      "kind": "rename",
                                      "source_path": "tests/test_panel.py"}]))
    assert rc == OK, err + out
    assert set(selected(out)) == {"tests/test_panel_v2.py", "tests/test_panel.py"}


def test_case_only_rename_is_preserved(demo):
    repo, pol = demo
    rc, out, err = run("select-manifest", repo=repo, policy=pol,
                       inp=manifest([{"path": "tests/Test_Panel.py", "kind": "rename",
                                      "source_path": "tests/test_panel.py"}]))
    assert rc in (OK, FULL)
    body = json.dumps(json.loads(out))
    assert "tests/Test_Panel.py" in body and "tests/test_panel.py" in body


def test_git_detected_rename(demo):
    repo, pol = demo
    git(repo, "mv", "tests/test_panel.py", "tests/test_panel_renamed.py")
    git(repo, "add", "-A")
    rc, out, err = run("select-staged", repo=repo, policy=pol)
    assert rc == OK, err + out
    assert "tests/test_panel_renamed.py" in selected(out)


# ---------------------------------------------------------- documentation

def test_documentation_only_change_has_no_focused_target(demo):
    repo, pol = demo
    rc, out, err = run("select-manifest", repo=repo, policy=pol,
                       inp=manifest(["docs/guide.md"]))
    assert rc == OK, err + out
    assert selected(out) == {}
    assert documentation(out) == ["docs/guide.md"]
    result = [c for c in checks(out) if c["id"] == "R1"][0]
    assert "NO focused pytest target" in result["evidence"]
    assert "does not mean no testing is required" in result["evidence"]
    assert proposed(out) == "(none)"


def test_documentation_only_still_requires_full_regression(demo):
    repo, pol = demo
    rc, out, _err = run("select-manifest", repo=repo, policy=pol,
                        inp=manifest(["docs/guide.md"]))
    ids = {c["id"]: c["evidence"] for c in checks(out)}
    assert "true" in ids["K1"] and "true" in ids["K2"]


def test_no_focused_test_never_reads_as_no_testing_required(demo):
    repo, pol = demo
    rc, out, _err = run("select-manifest", repo=repo, policy=pol,
                        inp=manifest(["docs/guide.md"]))
    body = json.dumps(json.loads(out)).lower()
    assert "no testing required" not in body.replace(
        "this does not mean no testing is required.", "")


# --------------------------------------------------------- zero and stale

def test_zero_changes_is_stopped(demo):
    repo, pol = demo
    rc, out, _err = run("select-worktree", repo=repo, policy=pol)
    assert rc == STOPPED
    assert json.loads(out)["overall_status"] == "stopped"
    assert "no testing conclusion is implied" in out


def test_empty_manifest_change_list_is_stopped(demo):
    repo, pol = demo
    rc, out, _err = run("select-manifest", repo=repo, policy=pol, inp=manifest([]))
    assert rc == STOPPED


def test_non_repository_is_stopped(tmp_path):
    plain = tmp_path / "plain"
    plain.mkdir()
    pol = write_policy(tmp_path, demo_policy())
    rc, out, _err = run("select-worktree", repo=plain, policy=pol)
    assert rc == STOPPED


def test_expected_head_mismatch_is_stopped(demo):
    repo, pol = demo
    write(repo / "ui" / "panel.py", "PANEL = 'q'\n")
    rc, out, _err = run("select-worktree", repo=repo, policy=pol,
                        extra=["--expected-head", "f" * 40])
    assert rc == STOPPED


def test_expected_head_match_proceeds(demo):
    repo, pol = demo
    write(repo / "ui" / "panel.py", "PANEL = 'q'\n")
    rc, out, err = run("select-worktree", repo=repo, policy=pol,
                       extra=["--expected-head", git(repo, "rev-parse", "HEAD")])
    assert rc == OK, err + out


def test_expected_branch_mismatch_is_stopped(demo):
    repo, pol = demo
    write(repo / "ui" / "panel.py", "PANEL = 'q'\n")
    rc, out, _err = run("select-worktree", repo=repo, policy=pol,
                        extra=["--expected-branch", "elsewhere"])
    assert rc == STOPPED


def test_moved_head_during_observation_is_stopped(demo, monkeypatch):
    repo, pol = demo
    write(repo / "ui" / "panel.py", "PANEL = 'q'\n")
    seen = {"n": 0}
    real = ts.a7._git_ok

    def drifting(r, args):
        if args[:2] == ["rev-parse", "HEAD"]:
            seen["n"] += 1
            if seen["n"] > 1:
                return "f" * 40 + "\n"
        return real(r, args)

    monkeypatch.setattr(ts.a7, "_git_ok", drifting)
    out, code = _inprocess(["select-worktree", "--format", "json",
                            "--repo", str(repo), "--policy", str(pol)])
    assert code == STOPPED
    assert any("moved during observation" in c["evidence"] for c in out)


# ------------------------------------------------------------------ registry

def reg_session(repo, sid="boot-session", status="active", beat=None,
                head=None, identity=None):
    from datetime import datetime, timezone
    now = beat or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {"session_id": sid, "worktree_identity": identity or repo.name,
            "canonical_worktree_path": str(repo), "branch": "work",
            "task": "select", "read_scope": [], "write_scope": [],
            "protected_scope": [], "started_at": now, "heartbeat_at": now,
            "status": status, "owner": "tester",
            "expected_commit": head or git(repo, "rev-parse", "HEAD")}


def write_registry(tmp_path, sessions, name="registry.json"):
    p = tmp_path / name
    p.write_text(json.dumps({"schema_version": 1, "revision": 1,
                             "sessions": list(sessions)}, indent=2) + "\n",
                 encoding="utf-8")
    return p


def test_matching_registry_session_is_accepted(tmp_path, demo):
    repo, pol = demo
    reg = write_registry(tmp_path, [reg_session(repo)])
    write(repo / "ui" / "panel.py", "PANEL = 'q'\n")
    rc, out, err = run("select-worktree", repo=repo, policy=pol,
                       extra=["--registry", str(reg), "--session-id", "boot-session"])
    assert rc == OK, err + out


def test_registry_commit_mismatch_is_stopped(tmp_path, demo):
    repo, pol = demo
    reg = write_registry(tmp_path, [reg_session(repo, head="f" * 40)])
    write(repo / "ui" / "panel.py", "PANEL = 'q'\n")
    rc, out, _err = run("select-worktree", repo=repo, policy=pol,
                        extra=["--registry", str(reg),
                               "--session-id", "boot-session"])
    assert rc == STOPPED


def test_registry_is_never_mutated(tmp_path, demo):
    repo, pol = demo
    reg = write_registry(tmp_path, [reg_session(repo)])
    before = reg.read_bytes()
    write(repo / "ui" / "panel.py", "PANEL = 'q'\n")
    for _ in range(3):
        run("select-worktree", repo=repo, policy=pol,
            extra=["--registry", str(reg), "--session-id", "boot-session"])
    assert reg.read_bytes() == before


# --------------------------------------------------------------- the policy

def test_policy_unknown_field_rejected(tmp_path):
    doc = policy_doc()
    doc["surprise"] = 1
    rc, _out, err = run("validate-policy", policy=write_policy(tmp_path, doc))
    assert rc == INVALID and "unrecognized" in err


def test_policy_unsupported_schema_rejected(tmp_path):
    doc = policy_doc()
    doc["schema_version"] = 99
    rc, _out, err = run("validate-policy", policy=write_policy(tmp_path, doc))
    assert rc == INVALID


@pytest.mark.parametrize("flag", ["-x", "--tb=long", "-p", "no:cacheprovider",
                                  "--maxfail=1", "-k", "--collect-only"])
def test_policy_rejects_arbitrary_pytest_flags(tmp_path, flag):
    doc = policy_doc()
    doc["full_suite_arguments"] = ["python", "-B", "-m", "pytest", flag]
    rc, _out, err = run("validate-policy", policy=write_policy(tmp_path, doc))
    assert rc == INVALID and "allowed argument tokens" in err


def test_policy_rejects_an_environment_assignment_argument(tmp_path):
    """Refused as an environment assignment before the token check even runs."""
    doc = policy_doc()
    doc["full_suite_arguments"] = ["python", "-B", "-m", "pytest", "PYTHONPATH=."]
    rc, _out, err = run("validate-policy", policy=write_policy(tmp_path, doc))
    assert rc == INVALID
    assert "environment assignment" in err or "allowed argument tokens" in err


def test_policy_rejects_a_changed_interpreter(tmp_path):
    doc = policy_doc()
    doc["full_suite_arguments"] = ["bash", "-m", "pytest", "-q"]
    rc, _out, err = run("validate-policy", policy=write_policy(tmp_path, doc))
    assert rc == INVALID


@pytest.mark.parametrize("path", ["C:/Users/someone/tests", "../outside/**",
                                  "**", "*", "**/*"])
def test_policy_rejects_unsafe_paths(tmp_path, path):
    doc = policy_doc()
    doc["test_roots"] = [path]
    rc, _out, err = run("validate-policy", policy=write_policy(tmp_path, doc))
    assert rc == INVALID


@pytest.mark.parametrize("pattern", ["docs/**/{a,b}", "docs/[unclosed", "docs/***"])
def test_policy_rejects_unsafe_glob_syntax(tmp_path, pattern):
    doc = policy_doc()
    doc["documentation_only_paths"] = [pattern]
    rc, _out, err = run("validate-policy", policy=write_policy(tmp_path, doc))
    assert rc == INVALID and "unsafe glob" in err


def test_policy_rejects_case_duplicate_roots(tmp_path):
    doc = policy_doc()
    doc["source_roots"] = ["core", "CORE"]
    rc, _out, err = run("validate-policy", policy=write_policy(tmp_path, doc))
    assert rc == INVALID and "case-conflicting" in err


def test_policy_rejects_conflicting_explicit_mappings(tmp_path):
    doc = policy_doc()
    doc["explicit_mappings"] = [
        {"id": "a", "paths": ["ui/x.json"], "tests": ["tests/test_a.py"], "reason": "a"},
        {"id": "b", "paths": ["ui/x.json"], "tests": ["tests/test_b.py"], "reason": "b"},
    ]
    rc, _out, err = run("validate-policy", policy=write_policy(tmp_path, doc))
    assert rc == INVALID and "two rules" in err


def test_policy_rejects_a_mapped_test_outside_the_test_roots(tmp_path):
    doc = policy_doc()
    doc["explicit_mappings"] = [
        {"id": "a", "paths": ["ui/x.json"], "tests": ["elsewhere/test_a.py"],
         "reason": "a"}]
    rc, _out, err = run("validate-policy", policy=write_policy(tmp_path, doc))
    assert rc == INVALID and "outside every declared test root" in err


def test_policy_rejects_an_executable_field(tmp_path):
    doc = policy_doc()
    doc["description"] = "run $(whoami)"
    rc, _out, err = run("validate-policy", policy=write_policy(tmp_path, doc))
    assert rc == INVALID and "executable" in err


def test_policy_rejects_an_environment_assignment(tmp_path):
    doc = policy_doc()
    doc["description"] = "PYTHONPATH=/opt/lib"
    rc, _out, err = run("validate-policy", policy=write_policy(tmp_path, doc))
    assert rc == INVALID


def test_policy_rejects_a_machine_path(tmp_path):
    doc = policy_doc()
    doc["description"] = "for C:\\Repos\\NOVA"
    rc, _out, err = run("validate-policy", policy=write_policy(tmp_path, doc))
    assert rc == INVALID


def test_policy_rejects_a_credential(tmp_path):
    doc = policy_doc()
    doc["description"] = "token=%s" % SECRET_VALUE
    rc, _out, err = run("validate-policy", policy=write_policy(tmp_path, doc))
    assert rc == INVALID


@pytest.mark.parametrize("key", sorted(ts.LIMIT_MAXIMUMS))
def test_policy_cannot_raise_any_implementation_maximum(tmp_path, key):
    doc = policy_doc()
    doc["limits"][key] = ts.LIMIT_MAXIMUMS[key] + 1
    rc, _out, err = run("validate-policy", policy=write_policy(tmp_path, doc))
    assert rc == LIMIT and "implementation maximum" in err


@pytest.mark.parametrize("key", sorted(ts.LIMIT_MAXIMUMS))
def test_policy_may_lower_any_limit(tmp_path, key):
    doc = policy_doc()
    doc["limits"][key] = max(1, ts.LIMIT_MAXIMUMS[key] // 2)
    rc, _out, err = run("validate-policy", policy=write_policy(tmp_path, doc))
    assert rc == OK, err


def test_policy_collection_history_is_labelled_as_snapshots():
    hist = policy_doc()["collection_count_history"]
    counts = {s["count"] for s in hist["snapshots"]}
    assert counts == {926, 1722}
    assert "re-measured" in hist["note"] or "re-measure" in hist["note"]
    assert "never expected values" in hist["note"]


def test_policy_history_note_must_say_collection_is_remeasured(tmp_path):
    doc = policy_doc()
    doc["collection_count_history"]["note"] = "counts are fixed"
    rc, _out, err = run("validate-policy", policy=write_policy(tmp_path, doc))
    assert rc == INVALID


def test_no_expected_collection_constant_in_the_selector():
    src = SELECTOR.read_text(encoding="utf-8")
    for stale in ("926", "1722", "1709"):
        assert stale not in src, stale


def test_missing_policy_exits_two(tmp_path):
    rc, _out, err = run("validate-policy", policy=tmp_path / "absent.json")
    assert rc == INVALID and "could not be read" in err


def test_malformed_policy_exits_two(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("{nope", encoding="utf-8")
    rc, _out, err = run("validate-policy", policy=p)
    assert rc == INVALID


# --------------------------------------------------------------- manifests

@pytest.mark.parametrize("note", [
    "bash -c 'echo hi'",
    "$(rm -rf /)",
    "PYTHONPATH=/opt",
    "https://example.invalid/x",
    "api_key=abcdefghijkl",
    "-----BEGIN RSA PRIVATE KEY-----",
    "importlib.import_module('x')",
])
def test_manifest_rejects_unsafe_strings(demo, note):
    repo, pol = demo
    rc, _out, err = run("select-manifest", repo=repo, policy=pol,
                        inp=manifest(["ui/panel.py"], notes=[note]))
    assert rc == INVALID, note


def test_manifest_rejects_traversal(demo):
    repo, pol = demo
    rc, _out, err = run("select-manifest", repo=repo, policy=pol,
                        inp=manifest(["../outside.py"]))
    assert rc == INVALID and "traversal" in err


def test_manifest_rejects_an_absolute_path(demo):
    repo, pol = demo
    rc, _out, err = run("select-manifest", repo=repo, policy=pol,
                        inp=manifest(["C:/Windows/x.py"]))
    assert rc == INVALID


def test_manifest_rejects_unknown_fields(demo):
    repo, pol = demo
    doc = manifest(["ui/panel.py"])
    doc["command"] = ["pytest", "-x"]
    rc, _out, err = run("select-manifest", repo=repo, policy=pol, inp=doc)
    assert rc == INVALID and "unrecognized" in err


def test_manifest_rejects_unknown_change_fields(demo):
    repo, pol = demo
    rc, _out, err = run("select-manifest", repo=repo, policy=pol,
                        inp=manifest([{"path": "ui/panel.py", "kind": "modify",
                                       "pytest_args": "-x"}]))
    assert rc == INVALID and "unrecognized" in err


def test_manifest_rejects_a_bad_kind(demo):
    repo, pol = demo
    rc, _out, err = run("select-manifest", repo=repo, policy=pol,
                        inp=manifest([{"path": "ui/panel.py", "kind": "teleport"}]))
    assert rc == INVALID


def test_manifest_rejects_duplicates(demo):
    repo, pol = demo
    rc, _out, err = run("select-manifest", repo=repo, policy=pol,
                        inp=manifest(["ui/panel.py", "ui/panel.py"]))
    assert rc == INVALID and "duplicates" in err


def test_manifest_change_ceiling(tmp_path, demo):
    repo, _pol = demo
    doc = demo_policy()
    doc["limits"]["max_changes"] = 2
    pol = write_policy(tmp_path, doc, "small.json")
    rc, _out, err = run("select-manifest", repo=repo, policy=pol,
                        inp=manifest(["ui/a%d.py" % i for i in range(5)]))
    assert rc == LIMIT


def test_oversized_manifest_is_a_safety_limit(tmp_path, demo):
    repo, pol = demo
    big = tmp_path / "big.json"
    big.write_bytes(b'{"schema_version":1,"changes":[],"notes":["'
                    + b"x" * (ts.MAX_INPUT_BYTES + 16) + b'"]}')
    rc, _out, err = run("select-manifest", repo=repo, policy=pol,
                        extra=["--input", str(big)])
    assert rc == LIMIT


def test_empty_manifest_input_is_rejected(tmp_path, demo):
    repo, pol = demo
    empty = tmp_path / "empty.json"
    empty.write_text("", encoding="utf-8")
    rc, _out, err = run("select-manifest", repo=repo, policy=pol,
                        extra=["--input", str(empty)])
    assert rc == INVALID


# ------------------------------------------------ the closure property

def test_no_dependent_test_is_ever_omitted(demo):
    """The selection must contain every test that reaches a changed module."""
    repo, pol = demo
    for changed, expected in (
            ("core/base.py", {"tests/test_base_direct.py", "tests/test_top.py"}),
            ("core/middle.py", {"tests/test_top.py"}),
            ("engines/top.py", {"tests/test_top.py"}),
            ("ui/panel.py", {"tests/test_panel.py"}),
            ("tests/helpers.py", {"tests/test_with_helper.py"})):
        rc, out, err = run("select-manifest", repo=repo, policy=pol,
                           inp=manifest([changed]))
        assert rc == OK, (changed, err + out)
        assert expected <= set(selected(out)), changed
        assert [c for c in checks(out) if c["id"] == "P1"][0]["status"] == "pass"


def test_closure_property_check_is_reported(demo):
    repo, pol = demo
    rc, out, _err = run("select-manifest", repo=repo, policy=pol,
                        inp=manifest(["core/base.py"]))
    p1 = [c for c in checks(out) if c["id"] == "P1"][0]
    assert p1["status"] == "pass"
    assert "every statically discovered test" in p1["evidence"]


def test_closure_verifier_detects_an_omission():
    index = {"core/base.py": {"tests/test_a.py": "direct import",
                              "tests/test_b.py": "transitive import"}}
    missing = ts.verify_no_dependent_omitted({"tests/test_a.py"},
                                             {"core/base.py"}, index)
    assert missing == [("core/base.py", "tests/test_b.py")]
    assert ts.verify_no_dependent_omitted(
        {"tests/test_a.py", "tests/test_b.py"}, {"core/base.py"}, index) == []


# ------------------------------------------------------ proposed invocation

def test_proposed_invocation_is_a_structured_argument_array(demo):
    repo, pol = demo
    rc, out, err = run("select-manifest", repo=repo, policy=pol,
                       inp=manifest(["ui/panel.py"]))
    assert rc == OK, err
    text = proposed(out)
    assert text.startswith("python -B -m pytest ")
    assert text.endswith(" -q")
    for shell_char in ("&&", "||", ";", "|", ">", "<", "$(", "`"):
        assert shell_char not in text, shell_char


def test_proposed_invocation_targets_are_tracked_test_files(demo):
    repo, pol = demo
    rc, out, _err = run("select-manifest", repo=repo, policy=pol,
                        inp=manifest(["core/base.py"]))
    tokens = proposed(out).split()
    targets = [t for t in tokens if t.endswith(".py")]
    tracked = set(git(repo, "ls-files").splitlines())
    for t in targets:
        assert t in tracked, t


def test_full_suite_invocation_has_no_targets(demo):
    repo, pol = demo
    rc, out, _err = run("select-manifest", repo=repo, policy=pol,
                        inp=manifest(["pytest.ini"]))
    assert rc == FULL
    assert proposed(out) == "python -B -m pytest -q"


def test_proposed_invocation_is_labelled_as_never_executed(demo):
    repo, pol = demo
    rc, out, _err = run("select-manifest", repo=repo, policy=pol,
                        inp=manifest(["ui/panel.py"]))
    ev = [c for c in checks(out) if c["id"] == "R2"][0]["evidence"]
    assert "never executed by this tool" in ev


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
        code = ts.main(argv)
    finally:
        sys.stdout = real_stdout
    text = buf.getvalue().decode("utf-8")
    return (json.loads(text)["checks"] if text.strip() else []), code


def test_no_module_is_imported_and_no_marker_written(tmp_path):
    """A changed module with hostile top-level code is parsed, never imported."""
    repo = make_repo(tmp_path)
    marker = repo / "IMPORTED.txt"
    write(repo / "engines" / "hostile.py",
          "import pathlib\n"
          "pathlib.Path(__file__).parent.parent.joinpath('IMPORTED.txt')"
          ".write_text('executed')\n"
          "HOSTILE = 1\n")
    write(repo / "tests" / "test_hostile.py",
          "from engines.hostile import HOSTILE\n\n\n"
          "def test_h():\n    assert HOSTILE == 1\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "hostile")
    pol = write_policy(tmp_path, demo_policy())
    rc, out, err = run("select-manifest", repo=repo, policy=pol,
                       inp=manifest(["engines/hostile.py"]))
    assert rc == OK, err + out
    assert "tests/test_hostile.py" in selected(out)
    assert not marker.exists(), "the selector imported the module"


def test_pytest_is_never_invoked(tmp_path):
    """No .pytest_cache and no test side effect appears after a selection."""
    repo = make_repo(tmp_path)
    pol = write_policy(tmp_path, demo_policy())
    write(repo / "tests" / "test_sideeffect.py",
          "import pathlib\n"
          "pathlib.Path(__file__).parent.parent.joinpath('COLLECTED.txt')"
          ".write_text('collected')\n\n\n"
          "def test_s():\n    assert True\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "side effect")
    run("select-manifest", repo=repo, policy=pol, inp=manifest(["ui/panel.py"]))
    assert not (repo / "COLLECTED.txt").exists()
    assert not (repo / ".pytest_cache").exists()


def test_repository_is_byte_identical_afterwards(demo):
    repo, pol = demo
    write(repo / "ui" / "panel.py", "PANEL = 'q'\n")
    before = _tree_digest(repo)
    run("select-worktree", repo=repo, policy=pol)
    run("select-worktree", repo=repo, policy=pol)
    assert _tree_digest(repo) == before


def test_git_refs_index_config_and_fetch_head_unchanged(demo):
    repo, pol = demo
    write(repo / "ui" / "panel.py", "PANEL = 'q'\n")
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
    run("select-worktree", repo=repo, policy=pol)
    run("select-staged", repo=repo, policy=pol)
    run("select-commit", repo=repo, policy=pol,
        extra=["--commit", git(repo, "rev-parse", "HEAD")])
    assert _tree_digest(gitdir / "refs") == before["refs"]
    assert (gitdir / "HEAD").read_bytes() == before["head"]
    assert (gitdir / "index").read_bytes() == before["index"]
    assert (gitdir / "config").read_bytes() == before["config"]
    assert (gitdir / "FETCH_HEAD").exists() == before["fetch_head"]
    assert git(repo, "status", "--porcelain", "-uall") == before["status"]


def test_policy_and_input_files_are_byte_identical(tmp_path, demo):
    repo, pol = demo
    m = tmp_path / "m.json"
    m.write_text(json.dumps(manifest(["ui/panel.py"])), encoding="utf-8")
    before_m, before_p, before_shipped = m.read_bytes(), pol.read_bytes(), \
        POLICY.read_bytes()
    run("select-manifest", repo=repo, policy=pol, extra=["--input", str(m)])
    assert m.read_bytes() == before_m
    assert pol.read_bytes() == before_p
    assert POLICY.read_bytes() == before_shipped


def test_no_lock_or_temp_residue(demo):
    repo, pol = demo
    write(repo / "ui" / "panel.py", "PANEL = 'q'\n")
    run("select-worktree", repo=repo, policy=pol)
    for dirpath, _dirs, files in os.walk(repo):
        for name in files:
            low = name.lower()
            assert not low.endswith(".tmp"), name
            assert not low.startswith(".nova-"), name
            assert not low.endswith(".lock") or ".git" in dirpath, name


def test_output_is_deterministic(demo):
    repo, pol = demo
    write(repo / "core" / "base.py", "VALUE = 2\n")
    for mode, fmt in (("select-worktree", "json"), ("select-worktree", "markdown"),
                      ("validate-policy", "json"), ("validate-policy", "markdown")):
        first = run(mode, repo=repo, policy=pol, fmt=fmt)[1]
        second = run(mode, repo=repo, policy=pol, fmt=fmt)[1]
        assert first == second, (mode, fmt)


def test_no_canary_username_path_url_or_secret_in_output(tmp_path):
    repo = make_repo(tmp_path)
    pol = write_policy(tmp_path, demo_policy())
    write(repo / "ui" / "panel.py",
          "# %s\nAPI_KEY = '%s'\nPANEL = 'C:\\\\Users\\\\someone'\n"
          % (CANARY, SECRET_VALUE))
    rc, out, err = run("select-worktree", repo=repo, policy=pol)
    blob = out + err
    assert CANARY not in blob
    assert SECRET_VALUE not in blob
    assert str(tmp_path) not in blob
    assert "C:\\Users" not in blob and "C:/Users" not in blob
    assert "http://" not in blob and "https://" not in blob


def test_registry_contents_are_never_printed(tmp_path, demo):
    repo, pol = demo
    reg = write_registry(tmp_path, [reg_session(repo)])
    write(repo / "ui" / "panel.py", "PANEL = 'q'\n")
    rc, out, err = run("select-worktree", repo=repo, policy=pol,
                       extra=["--registry", str(reg), "--session-id", "boot-session"])
    blob = out + err
    assert str(repo) not in blob
    assert "canonical_worktree_path" not in blob


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
        if name not in ("_git", "_git_ok", "a7._git", "a7._git_ok",
                        "cc._git", "cc._git_ok"):
            continue
        for arg in node.args:
            if isinstance(arg, ast.List) and arg.elts:
                first = arg.elts[0]
                if isinstance(first, ast.Constant) and isinstance(first.value, str):
                    verbs.add(first.value)
    return verbs


def test_stdlib_only():
    mods = set()
    for node in ast.walk(ast.parse(SELECTOR.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            mods.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods.add(node.module.split(".")[0])
    third = [m for m in mods if m not in sys.stdlib_module_names
             and m not in ("__future__", "evidence_formatter", "staleness_guard",
                           "session_registry", "a7_battery", "change_classifier")]
    assert third == [], third


def test_no_eval_exec_or_dynamic_import():
    idents = _identifiers(SELECTOR)
    for banned in ("eval", "exec", "__import__", "importlib", "import_module",
                   "globals", "locals", "runpy"):
        assert banned not in idents, banned
    for node in ast.walk(ast.parse(SELECTOR.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id != "compile"


def test_selector_owns_no_subprocess():
    idents = _identifiers(SELECTOR)
    names = _dotted_names(SELECTOR)
    for banned in ("subprocess", "popen", "system", "spawn", "fork", "socket",
                   "urllib", "requests", "asyncio"):
        assert banned not in idents, banned
    for banned in ("os.system", "subprocess.run", "subprocess.Popen", "os.spawnv"):
        assert banned not in names, banned


def test_pytest_is_never_invoked_in_source():
    """`pytest` may appear only as a data token in an argument array."""
    tree = ast.parse(SELECTOR.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name.split(".")[0] != "pytest"
        elif isinstance(node, ast.ImportFrom) and node.module:
            assert node.module.split(".")[0] != "pytest"
    # `--collect-only` may appear in prose that states it is never used, but never
    # inside an argument array. Checked on list literals rather than on the text.
    for node in ast.walk(tree):
        if isinstance(node, ast.List):
            values = [e.value for e in node.elts
                      if isinstance(e, ast.Constant) and isinstance(e.value, str)]
            assert "--collect-only" not in values, values
            assert "pytest" not in values or set(values) <= \
                {"python", "-B", "-m", "pytest", "-q"}, values


def test_no_environment_value_reads():
    idents = _identifiers(SELECTOR)
    names = _dotted_names(SELECTOR)
    for banned in ("environ", "getenv", "expanduser", "expandvars", "getpass"):
        assert banned not in idents, banned
    for banned in ("os.environ", "os.getenv", "os.path.expanduser"):
        assert banned not in names, banned


def test_no_write_mode_open():
    import re as _re
    body = _executable_source(SELECTOR)
    for m in _re.finditer(r"open\(([^)]*)\)", body):
        assert not _re.search(r"['\"][wax]", m.group(1)), m.group(0)


def test_no_deletion_move_or_write_helper():
    idents = _identifiers(SELECTOR)
    names = _dotted_names(SELECTOR)
    for banned in ("remove", "unlink", "rmdir", "mkdir", "makedirs", "shutil",
                   "rmtree", "write_text", "write_bytes", "chmod", "symlink"):
        assert banned not in idents, banned
    for banned in ("os.remove", "os.unlink", "os.rename", "os.replace",
                   "os.mkdir", "os.makedirs", "shutil.rmtree"):
        assert banned not in names, banned


def test_no_mutating_git_verb_is_ever_requested():
    mutating = {"fetch", "pull", "push", "merge", "rebase", "checkout", "switch",
                "reset", "restore", "clean", "commit", "worktree", "submodule",
                "update-index", "gc", "add", "stash", "config", "mv", "rm"}
    asked = _git_verbs(SELECTOR)
    assert asked, "no git verb was found; the scan would be vacuous"
    assert not (asked & mutating), sorted(asked & mutating)


def test_every_git_verb_is_inside_the_a7_read_only_allowlist():
    sys.path.insert(0, str(SELECTOR.parent))
    try:
        import a7_battery as a7
    finally:
        sys.path.pop(0)
    asked = _git_verbs(SELECTOR)
    assert asked <= set(a7._A7_GIT_READ_ONLY), sorted(asked - set(a7._A7_GIT_READ_ONLY))


def test_no_session_registry_mutation():
    names = _dotted_names(SELECTOR)
    for banned in ("sr.write_registry_atomic", "sr._Lock", "sr.advance",
                   "sr.register", "sr.heartbeat", "sr.close"):
        assert banned not in names, banned
    assert "write_registry_atomic" not in _executable_source(SELECTOR)


def test_rendering_goes_through_the_evidence_formatter():
    names = _dotted_names(SELECTOR)
    assert {"ef.render_markdown", "ef.render_json", "ef.normalize"} <= names


def test_no_function_named_for_an_execution_or_approval():
    tree = ast.parse(SELECTOR.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            for verb in ("run_tests", "invoke", "execute", "collect", "approve",
                         "apply", "commit"):
                assert node.name != verb, node.name


def test_argument_token_allowlist_is_tiny_and_fixed():
    assert ts.ALLOWED_ARGUMENT_TOKENS == frozenset(
        {"python", "-B", "-m", "pytest", "-q"})


def test_mapping_source_vocabulary_is_complete():
    assert set(ts.MAPPING_SOURCES) == {
        "self", "direct import", "transitive import", "conftest scope",
        "explicit policy", "dynamic-test safety inclusion", "global fallback"}


def test_dynamic_safety_inclusion_is_the_weakest_real_mapping():
    """A genuine mapping always outranks the safety net in the reported source."""
    order = list(ts.MAPPING_SOURCES)
    assert order.index("dynamic-test safety inclusion") == len(order) - 2
    assert order[-1] == "global fallback"


# ------------------------------------------- dynamic-test safety inclusion

_NL = chr(10)          # newline, built without an escape so this file stays literal

DYNAMIC_BODIES = {
    "module": "import importlib" + _NL + "m = importlib.import_module('core.base')"
              + _NL + _NL + _NL + "def test_a():" + _NL + "    assert m" + _NL,
    "builtin": "def test_b():" + _NL + "    mod = __import__('core.base')" + _NL
               + "    assert mod" + _NL,
    "compiled": "src = 'X = 1'" + _NL + "ns = {}" + _NL
                + "exec(compile(src, 'x', 'exec'), ns)" + _NL + _NL + _NL
                + "def test_c():" + _NL + "    assert ns" + _NL,
    "built_name": "import importlib" + _NL + "part = 'ba' + 'se'" + _NL
                  + "m = importlib.import_module('core.' + part)" + _NL + _NL + _NL
                  + "def test_d():" + _NL + "    assert m" + _NL,
    "star": "from core.missing_module import *" + _NL + _NL + _NL
            + "def test_e():" + _NL + "    assert True" + _NL,
}


def make_dynamic_repo(tmp_path, names, name="nova-dyn"):
    """The demo repository plus one dynamic test per requested body kind."""
    repo = make_repo(tmp_path, name=name)
    for key in names:
        write(repo / "tests" / ("test_dyn_%s.py" % key), DYNAMIC_BODIES[key])
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "dynamic tests")
    return repo


def dynamic_reasons(out):
    return {c["label"]: c["evidence"] for c in checks(out)
            if c["id"].startswith("Y") and c["id"][1:].isdigit() and c["id"] != "Y0"}


def test_every_dynamic_shape_is_detected(tmp_path):
    """Each AST-detectable indirection lands in the inventory, none is executed."""
    repo = make_dynamic_repo(tmp_path, sorted(DYNAMIC_BODIES))
    pol = write_policy(tmp_path, demo_policy())
    rc, out, err = run("select-manifest", repo=repo, policy=pol,
                       inp=manifest(["ui/panel.py"]))
    assert rc == OK, err + out
    assert dynamic_inventory(out) == sorted(
        "tests/test_dyn_%s.py" % k for k in DYNAMIC_BODIES)


def test_multiple_dynamic_tests_are_included_deterministically(tmp_path):
    """All of them are selected, in one stable order, on every run."""
    repo = make_dynamic_repo(tmp_path, ["module", "builtin", "star"])
    pol = write_policy(tmp_path, demo_policy())
    runs = [run("select-manifest", repo=repo, policy=pol,
                inp=manifest(["core/base.py"])) for _ in range(3)]
    assert {r[0] for r in runs} == {OK}
    assert len({r[1] for r in runs}) == 1, "output was not byte-identical"
    got = selected(runs[0][1])
    for key in ("module", "builtin", "star"):
        assert got["tests/test_dyn_%s.py" % key] == "dynamic-test safety inclusion"
    assert dynamic_inventory(runs[0][1]) == ["tests/test_dyn_builtin.py",
                                             "tests/test_dyn_module.py",
                                             "tests/test_dyn_star.py"]


def test_a_dynamic_test_never_forces_every_selection_to_the_full_suite(tmp_path):
    """The Phase 3W correction itself: one dynamic test used to escalate everything."""
    repo = make_dynamic_repo(tmp_path, ["module"])
    pol = write_policy(tmp_path, demo_policy())
    for changed, expect in (("core/base.py", "tests/test_base_direct.py"),
                            ("ui/panel.py", "tests/test_panel.py"),
                            ("engines/top.py", "tests/test_top.py")):
        rc, out, err = run("select-manifest", repo=repo, policy=pol,
                           inp=manifest([changed]))
        assert rc == OK, (changed, err + out)
        assert expect in selected(out), changed
        assert "tests/test_dyn_module.py" in selected(out), changed


def test_ordinary_source_change_is_a_genuine_subset_plus_dynamic(tmp_path):
    """A focused selection must be smaller than the suite, not a disguised fallback."""
    repo = make_dynamic_repo(tmp_path, ["module"])
    pol = write_policy(tmp_path, demo_policy())
    rc, out, err = run("select-manifest", repo=repo, policy=pol,
                       inp=manifest(["ui/panel.py"]))
    assert rc == OK, err + out
    got = selected(out)
    all_tests = [p for p in git(repo, "ls-files").splitlines()
                 if p.startswith("tests/")
                 and p.rsplit("/", 1)[-1].startswith("test_")]
    assert len(got) < len(all_tests), (sorted(got), all_tests)
    assert got["tests/test_panel.py"] == "direct import"
    assert got["tests/test_dyn_module.py"] == "dynamic-test safety inclusion"
    assert "tests/test_top.py" not in got
    assert "tests/test_base_direct.py" not in got


def test_a_stronger_mapping_outranks_the_safety_label(tmp_path):
    """A dynamic test that genuinely imports the change reports the real mapping."""
    repo = make_repo(tmp_path)
    write(repo / "tests" / "test_dyn_panel.py",
          "import importlib" + _NL + "from ui.panel import PANEL" + _NL
          + "m = importlib.import_module('core.base')" + _NL + _NL + _NL
          + "def test_p():" + _NL + "    assert PANEL and m" + _NL)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "dynamic panel test")
    pol = write_policy(tmp_path, demo_policy())
    rc, out, err = run("select-manifest", repo=repo, policy=pol,
                       inp=manifest(["ui/panel.py"]))
    assert rc == OK, err + out
    assert selected(out)["tests/test_dyn_panel.py"] == "direct import"
    assert dynamic_inventory(out) == ["tests/test_dyn_panel.py"]
    assert "0 of 1 dynamic test" in dynamic_added(out)


# ------------------------------------------ source-side ambiguity escalates

def test_changed_dynamic_source_module_still_escalates(tmp_path):
    """A source whose own imports cannot be read hides dependency discovery."""
    repo = make_repo(tmp_path)
    write(repo / "engines" / "dyn_src.py",
          "import importlib" + _NL
          + "mod = importlib.import_module('core.' + 'base')" + _NL + "V = 1" + _NL)
    write(repo / "tests" / "test_dyn_src.py",
          "from engines.dyn_src import V" + _NL + _NL + _NL
          + "def test_v():" + _NL + "    assert V == 1" + _NL)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "dynamic source")
    pol = write_policy(tmp_path, demo_policy())
    rc, out, _err = run("select-manifest", repo=repo, policy=pol,
                        inp=manifest(["engines/dyn_src.py"]))
    assert rc == FULL
    assert "dependency discovery" in escalations(out)["engines/dyn_src.py"]
    assert proposed(out) == "python -B -m pytest -q"


def test_a_dynamic_source_is_not_rescued_by_the_test_side_inclusion(tmp_path):
    """The always-include set must never absorb a source-side unknown."""
    repo = make_repo(tmp_path)
    write(repo / "engines" / "dyn_src.py",
          "import importlib" + _NL + "mod = importlib.import_module('core.base')"
          + _NL + "V = 1" + _NL)
    write(repo / "tests" / "test_dyn_only.py",
          "import importlib" + _NL + "m = importlib.import_module('core.base')"
          + _NL + _NL + _NL + "def test_o():" + _NL + "    assert m" + _NL)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "both dynamic")
    pol = write_policy(tmp_path, demo_policy())
    rc, out, _err = run("select-manifest", repo=repo, policy=pol,
                        inp=manifest(["engines/dyn_src.py"]))
    assert rc == FULL
    assert selected(out) == {}


def test_search_path_mutation_alone_is_not_dynamic(tmp_path):
    """Mutating sys.path and then importing a RESOLVABLE sibling is knowable.

    Treating it as unknowable would mark most of the repository dynamic and destroy
    the usefulness this refinement exists for.
    """
    repo = make_repo(tmp_path)
    write(repo / "tests" / "test_pathmut.py",
          "import sys, os" + _NL
          + "sys.path.insert(0, os.path.dirname(__file__))" + _NL
          + "from core.base import VALUE" + _NL + _NL + _NL
          + "def test_m():" + _NL + "    assert VALUE == 1" + _NL)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "path mutation")
    pol = write_policy(tmp_path, demo_policy())
    rc, out, err = run("select-manifest", repo=repo, policy=pol,
                       inp=manifest(["ui/panel.py"]))
    assert rc == OK, err + out
    assert dynamic_inventory(out) == []
    assert "tests/test_pathmut.py" not in selected(out)


def test_search_path_mutation_with_an_unresolved_import_is_dynamic(tmp_path):
    """Mutation that leaves an internal import unresolvable IS unknowable."""
    repo = make_repo(tmp_path)
    write(repo / "tests" / "test_pathmut_bad.py",
          "import sys, os" + _NL
          + "sys.path.insert(0, os.path.dirname(__file__))" + _NL
          + "from core.nowhere import Z" + _NL + _NL + _NL
          + "def test_m():" + _NL + "    assert Z" + _NL)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "path mutation unresolved")
    pol = write_policy(tmp_path, demo_policy())
    rc, out, err = run("select-manifest", repo=repo, policy=pol,
                       inp=manifest(["ui/panel.py"]))
    assert rc == OK, err + out
    assert dynamic_inventory(out) == ["tests/test_pathmut_bad.py"]
    assert "search-path mutation" in dynamic_reasons(out)["tests/test_pathmut_bad.py"]


@pytest.mark.parametrize("path", ["pytest.ini", ".gitignore", "requirements.txt"])
def test_global_impact_still_selects_the_full_suite_with_dynamic_tests(tmp_path, path):
    repo = make_dynamic_repo(tmp_path, ["module"])
    pol = write_policy(tmp_path, demo_policy())
    rc, out, _err = run("select-manifest", repo=repo, policy=pol,
                        inp=manifest([path]))
    assert rc == FULL
    assert "global-impact" in escalations(out)[path]
    assert selected(out) == {}


def test_unresolved_internal_import_still_escalates_with_dynamic_tests(tmp_path):
    repo = make_dynamic_repo(tmp_path, ["module"])
    write(repo / "engines" / "bad2.py", "from core.does_not_exist import Z" + _NL)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "bad import")
    pol = write_policy(tmp_path, demo_policy())
    rc, out, _err = run("select-manifest", repo=repo, policy=pol,
                        inp=manifest(["engines/bad2.py"]))
    assert rc == FULL


def test_ambiguous_module_name_still_escalates_with_dynamic_tests(tmp_path):
    repo = make_dynamic_repo(tmp_path, ["module"])
    write(repo / "engines" / "shared.py", "A = 1" + _NL)
    write(repo / "ui" / "shared.py", "B = 2" + _NL)
    write(repo / "tests" / "test_ambig2.py",
          "import shared" + _NL + _NL + _NL + "def test_a():" + _NL
          + "    assert shared" + _NL)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "ambiguous")
    pol = write_policy(tmp_path, demo_policy())
    rc, out, _err = run("select-manifest", repo=repo, policy=pol,
                        inp=manifest(["tests/test_ambig2.py"]))
    assert rc == FULL


def test_unparseable_changed_source_still_escalates_with_dynamic_tests(tmp_path):
    repo = make_dynamic_repo(tmp_path, ["module"])
    write(repo / "engines" / "broken2.py", "def oops(:" + _NL)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "broken")
    pol = write_policy(tmp_path, demo_policy())
    rc, out, _err = run("select-manifest", repo=repo, policy=pol,
                        inp=manifest(["engines/broken2.py"]))
    assert rc == FULL
    assert "could not be parsed" in escalations(out)["engines/broken2.py"]


def test_an_unparseable_test_stops_the_inventory_and_escalates(tmp_path):
    """If one tracked test cannot be classified, the safety net is not complete."""
    repo = make_repo(tmp_path)
    write(repo / "tests" / "test_broken_test.py", "def test_x(:" + _NL)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "broken test")
    pol = write_policy(tmp_path, demo_policy())
    rc, out, _err = run("select-manifest", repo=repo, policy=pol,
                        inp=manifest(["ui/panel.py"]))
    assert rc == FULL
    reason = escalations(out)["tests/test_broken_test.py"]
    assert "dynamic-test inventory could not be completed" in reason
    assert "could not be classified" in dynamic_summary(out)


# ------------------------------------------- the inclusion cannot be turned off

def test_policy_may_not_exclude_a_test_file(tmp_path):
    doc = demo_policy()
    doc["exclusions"] = doc["exclusions"] + ["tests/test_dyn_module.py"]
    rc, _out, err = run("validate-policy", policy=write_policy(tmp_path, doc))
    assert rc == INVALID
    assert "may not name a test file" in err


def test_policy_may_not_exclude_a_test_pattern_under_a_test_root(tmp_path):
    doc = demo_policy()
    doc["exclusions"] = doc["exclusions"] + ["tests/test_*.py"]
    rc, _out, err = run("validate-policy", policy=write_policy(tmp_path, doc))
    assert rc == INVALID
    assert "may not name a test file" in err


def test_shipped_policy_excludes_no_test_file():
    for pattern in policy_doc()["exclusions"]:
        assert not pattern.startswith("tests/"), pattern


def test_a_manifest_cannot_remove_a_dynamic_test(tmp_path):
    """A manifest describes changes; it has no field that drops a selected test."""
    repo = make_dynamic_repo(tmp_path, ["module"])
    pol = write_policy(tmp_path, demo_policy())
    for doc in (manifest(["ui/panel.py"]),
                manifest(["ui/panel.py"], notes=["please skip the dynamic test"]),
                manifest(["ui/panel.py", "core/base.py"])):
        rc, out, err = run("select-manifest", repo=repo, policy=pol, inp=doc)
        assert rc == OK, err + out
        assert "tests/test_dyn_module.py" in selected(out)
    doc = manifest(["ui/panel.py"])
    doc["exclude_tests"] = ["tests/test_dyn_module.py"]
    rc, _out, err = run("select-manifest", repo=repo, policy=pol, inp=doc)
    assert rc == INVALID and "unrecognized" in err


def test_contract_locks_the_dynamic_rules_in_the_shipped_policy():
    contract = policy_doc()["contract"]
    assert contract["dynamic_test_safety_inclusion_enabled"] is True
    assert contract["source_side_dynamic_ambiguity_escalates"] is True
    assert contract["dynamic_tests_can_be_excluded"] is False
    assert contract["policy_can_downgrade_an_escalation"] is False


def test_flags_stay_true_on_a_dynamic_selection(tmp_path):
    repo = make_dynamic_repo(tmp_path, ["module", "star"])
    pol = write_policy(tmp_path, demo_policy())
    for doc in (manifest(["ui/panel.py"]), manifest(["docs/guide.md"]),
                manifest(["pytest.ini"])):
        rc, out, _err = run("select-manifest", repo=repo, policy=pol, inp=doc)
        ids = {c["id"]: c["evidence"] for c in checks(out)}
        assert "full_regression_required: true" in ids["K1"]
        assert "collection_parity_required: true" in ids["K2"]
        assert "still escalates" in ids["K7"]


def test_documentation_only_gets_no_focused_target_even_with_dynamic_tests(tmp_path):
    """A safety net is not a test plan for a change that has no focused target."""
    repo = make_dynamic_repo(tmp_path, ["module"])
    pol = write_policy(tmp_path, demo_policy())
    rc, out, err = run("select-manifest", repo=repo, policy=pol,
                       inp=manifest(["docs/guide.md"]))
    assert rc == OK, err + out
    assert selected(out) == {}
    assert proposed(out) == "(none)"
    assert documentation(out) == ["docs/guide.md"]
    assert dynamic_inventory(out) == ["tests/test_dyn_module.py"]
    body = json.dumps(json.loads(out))
    assert "NO focused pytest target" in body
    assert "does not mean no testing is required" in body


# --------------------------------------------------- safety of the inventory

def test_hostile_dynamic_test_is_never_executed(tmp_path):
    """Module-level code in a dynamic test must not run while it is inventoried."""
    repo = make_repo(tmp_path)
    marker = repo / "DYNAMIC_RAN.txt"
    write(repo / "tests" / "test_hostile_dyn.py",
          "import importlib, pathlib" + _NL
          + "pathlib.Path(__file__).parent.parent.joinpath('DYNAMIC_RAN.txt')"
          + ".write_text('executed')" + _NL
          + "m = importlib.import_module('core.base')" + _NL + _NL + _NL
          + "def test_h():" + _NL + "    assert m" + _NL)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "hostile dynamic")
    pol = write_policy(tmp_path, demo_policy())
    before = _tree_digest(repo)
    rc, out, err = run("select-manifest", repo=repo, policy=pol,
                       inp=manifest(["ui/panel.py"]))
    assert rc == OK, err + out
    assert dynamic_inventory(out) == ["tests/test_hostile_dyn.py"]
    assert not marker.exists(), "the selector executed a dynamic test"
    assert not (repo / ".pytest_cache").exists()
    assert _tree_digest(repo) == before


def test_dynamic_selection_writes_nothing_and_leaves_no_residue(tmp_path):
    repo = make_dynamic_repo(tmp_path, ["module", "builtin", "star"])
    pol = write_policy(tmp_path, demo_policy())
    pol_before = pol.read_bytes()
    before = _tree_digest(repo)
    run("select-manifest", repo=repo, policy=pol, inp=manifest(["core/base.py"]))
    run("select-worktree", repo=repo, policy=pol)
    assert _tree_digest(repo) == before
    assert pol.read_bytes() == pol_before
    for name in (".pytest_cache", "__pycache__", "COLLECTED.txt"):
        assert not (repo / name).exists(), name
    assert not list(tmp_path.glob("*.lock"))
    assert not list(tmp_path.glob("*.tmp"))


def test_dynamic_evidence_carries_no_machine_path_or_secret(tmp_path):
    repo = make_dynamic_repo(tmp_path, ["module"])
    pol = write_policy(tmp_path, demo_policy())
    rc, out, err = run("select-manifest", repo=repo, policy=pol,
                       inp=manifest(["core/base.py"]))
    blob = out + err
    assert str(tmp_path) not in blob
    assert "C:" + chr(92) + "Users" not in blob and "C:/Users" not in blob
    for path in dynamic_inventory(out):
        assert path.startswith("tests/") and ":" not in path


def test_dynamic_inventory_helpers_open_and_run_nothing():
    """The inventory reads an already-parsed graph; it opens and runs nothing."""
    assert hasattr(ts, "dynamic_test_inventory")
    tree = ast.parse(SELECTOR.read_text(encoding="utf-8"))
    seen = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in (
                "dynamic_test_inventory", "dynamic_inclusion_reason",
                "_mutates_search_path", "_dotted_target"):
            seen.add(node.name)
            for call in ast.walk(node):
                if isinstance(call, ast.Call) and isinstance(call.func, ast.Name):
                    assert call.func.id not in ("open", "compile", "eval", "exec",
                                                "__import__"), node.name
    assert seen == {"dynamic_test_inventory", "dynamic_inclusion_reason",
                    "_mutates_search_path", "_dotted_target"}


def test_dynamic_evidence_hardens_no_count_into_a_constant(tmp_path):
    repo = make_dynamic_repo(tmp_path, ["module"])
    pol = write_policy(tmp_path, demo_policy())
    rc, out, _err = run("select-manifest", repo=repo, policy=pol,
                        inp=manifest(["core/base.py"]))
    body = json.dumps(json.loads(out))
    assert "expected count" not in body
    assert "must collect" not in body
