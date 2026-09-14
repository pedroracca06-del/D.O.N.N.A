"""Static and import-boundary tests for the CM-1 package.

These prove, by reading the package source and by importing it in a fresh
isolated interpreter, that CM-1 stays what it claims to be: standard library
only, read-only, clock-free, environment-free, network-free, detached from every
live surface, and able to start exactly one kind of process — read-only
``git cat-file``.

Guarded flag names are loaded from ``tools/cowork/a7_policy.json`` rather than
written here.
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import intelligence.canonical_memory as package  # noqa: E402
from intelligence.canonical_memory import git_reader, schema  # noqa: E402

PACKAGE_DIR = Path(package.__file__).resolve().parent

EXPECTED_MODULES = [
    "__init__.py",
    "git_objects.py",
    "git_reader.py",
    "hashing.py",
    "ingest.py",
    "ingest_spec.py",
    "prime_precondition.py",
    "schema.py",
]

_BASE_IMPORT_ROOTS = frozenset(
    {"__future__", "dataclasses", "hashlib", "json", "re", "types", "typing", "unicodedata", "intelligence"}
)
_EXTRA_IMPORT_ROOTS = {
    "git_reader.py": frozenset({"subprocess", "pathlib"}),
    "prime_precondition.py": frozenset({"tempfile", "pathlib"}),
    "ingest.py": frozenset({"pathlib"}),
}
_ALLOWED_INTELLIGENCE_MODULES = {
    "prime_precondition.py": frozenset({"intelligence.current_knowledge"}),
}

_FORBIDDEN_CALL_NAMES = frozenset(
    {"open", "eval", "exec", "compile", "__import__", "input", "print", "breakpoint", "exit", "quit"}
)
_CLOCK_ATTRIBUTES = frozenset({"now", "utcnow", "today", "time", "time_ns", "monotonic", "perf_counter", "clock"})
_ENVIRONMENT_ATTRIBUTES = frozenset({"environ", "environb", "getenv", "getenvb", "putenv", "unsetenv"})
_PROCESS_ATTRIBUTES = frozenset(
    {"system", "popen", "Popen", "call", "check_call", "check_output", "getoutput", "getstatusoutput",
     "spawnl", "spawnv", "execv", "execve", "fork", "startfile"}
)
_NETWORK_ATTRIBUTES = frozenset({"urlopen", "connect", "create_connection", "socket", "request", "getaddrinfo"})
_WRITE_ATTRIBUTES = frozenset(
    {"write", "writelines", "write_text", "write_bytes", "mkdir", "makedirs", "touch", "unlink", "rmdir",
     "rmtree", "remove", "rename", "chmod", "symlink_to", "hardlink_to", "open", "truncate"}
)
_MUTATING_GIT_WORDS = frozenset(
    {"add", "am", "apply", "branch", "checkout", "cherry-pick", "clean", "clone", "commit", "config", "fetch",
     "gc", "hash-object", "init", "merge", "mv", "pull", "push", "rebase", "remote", "replace", "reset",
     "restore", "revert", "rm", "stash", "switch", "tag", "update-index", "update-ref", "worktree", "write-tree"}
)


def _sources() -> list[Path]:
    sources = sorted(PACKAGE_DIR.glob("*.py"))
    assert [path.name for path in sources] == EXPECTED_MODULES
    return sources


def _tree(path: Path) -> ast.AST:
    return ast.parse(path.read_text(encoding="utf-8"), filename=path.name)


def test_package_has_exactly_the_approved_modules():
    _sources()


def test_each_module_imports_only_its_declared_standard_library():
    for path in _sources():
        allowed = _BASE_IMPORT_ROOTS | _EXTRA_IMPORT_ROOTS.get(path.name, frozenset())
        extra_intelligence = _ALLOWED_INTELLIGENCE_MODULES.get(path.name, frozenset())
        for node in ast.walk(_tree(path)):
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                assert node.level == 0, f"{path.name} uses a relative import"
                modules = [node.module or ""]
            else:
                continue
            for module in modules:
                root = module.split(".")[0]
                assert root in allowed, f"{path.name} imports {module}"
                if root == "intelligence":
                    assert module.startswith("intelligence.canonical_memory") or module in extra_intelligence, (
                        f"{path.name} imports {module}"
                    )


def test_no_io_eval_or_printing_calls():
    for path in _sources():
        for node in ast.walk(_tree(path)):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id not in _FORBIDDEN_CALL_NAMES, f"{path.name} calls {node.func.id}()"


def _attributes(path: Path) -> set[str]:
    return {node.attr for node in ast.walk(_tree(path)) if isinstance(node, ast.Attribute)}


def test_no_clock_is_ever_read():
    for path in _sources():
        assert not (_attributes(path) & _CLOCK_ATTRIBUTES), path.name


def test_no_environment_is_read_or_assigned():
    for path in _sources():
        assert not (_attributes(path) & _ENVIRONMENT_ATTRIBUTES), path.name
        names = {node.id for node in ast.walk(_tree(path)) if isinstance(node, ast.Name)}
        assert not (names & _ENVIRONMENT_ATTRIBUTES), path.name
        for node in ast.walk(_tree(path)):
            if isinstance(node, ast.Call):
                assert "env" not in {kw.arg for kw in node.keywords}, f"{path.name} passes env="


def test_no_network_or_extra_process_primitives():
    for path in _sources():
        attrs = _attributes(path)
        assert not (attrs & _NETWORK_ATTRIBUTES), path.name
        assert not (attrs & _PROCESS_ATTRIBUTES), path.name


def test_writes_exist_only_in_the_temporary_prime_precondition():
    for path in _sources():
        attrs = _attributes(path) & _WRITE_ATTRIBUTES
        if path.name == "prime_precondition.py":
            assert attrs == {"write_bytes"}
            source = path.read_text(encoding="utf-8")
            assert "tempfile.TemporaryDirectory(" in source
            assert source.count("write_bytes(") == 1
        else:
            assert not attrs, f"{path.name} uses {sorted(attrs)}"


def test_shell_is_never_requested():
    for path in _sources():
        for node in ast.walk(_tree(path)):
            if isinstance(node, ast.Call):
                assert "shell" not in {kw.arg for kw in node.keywords}, path.name


def test_subprocess_appears_only_in_git_reader_and_only_as_run():
    for path in _sources():
        uses = {
            node.attr
            for node in ast.walk(_tree(path))
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "subprocess"
        }
        if path.name == "git_reader.py":
            assert uses == {"run", "TimeoutExpired"}
            runs = [
                node for node in ast.walk(_tree(path))
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "run"
            ]
            assert len(runs) == 1
            assert isinstance(runs[0].args[0], ast.Name) and runs[0].args[0].id == "argv"
        else:
            assert not uses, f"{path.name} touches subprocess"


def test_git_reader_constructs_no_mutating_git_command():
    constants = {
        node.value
        for node in ast.walk(_tree(PACKAGE_DIR / "git_reader.py"))
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    assert not (constants & _MUTATING_GIT_WORDS)
    argv = git_reader.build_cat_file_argv("r")
    assert argv[0] == "git" and argv[argv.index("-C") + 2] == "cat-file"
    assert not (set(argv) & _MUTATING_GIT_WORDS)


def test_package_source_never_names_a_guarded_flag():
    policy = json.loads((_REPO_ROOT / "tools" / "cowork" / "a7_policy.json").read_text(encoding="utf-8"))
    flags = policy["protected_flags"]
    assert len(flags) == 2
    for path in _sources():
        text = path.read_text(encoding="utf-8")
        for flag in flags:
            assert flag not in text, f"{path.name} names a guarded flag"


def test_boundary_pattern_still_catches_both_guarded_flags():
    from intelligence.canonical_memory import ingest

    policy = json.loads((_REPO_ROOT / "tools" / "cowork" / "a7_policy.json").read_text(encoding="utf-8"))
    for flag in policy["protected_flags"]:
        with pytest.raises(ingest.IngestError) as excinfo:
            ingest.check_boundary(f"set {flag} to a value", subject="flag")
        assert excinfo.value.code == "BOUNDARY_MATERIAL"


_LIVE_ROOTS = (
    "services", "core", "main", "monitor", "engines", "delivery", "ui", "health", "mcp",
    "anthropic", "openai", "httpx", "requests", "fastapi", "uvicorn", "dotenv", "yfinance", "bs4",
    "socket", "ssl", "sqlite3", "asyncio",
)
_LIVE_MODULES = ("urllib.request", "http.client", "intelligence.gateway", "intelligence.providers", "research")

_PROBE = """
import json, sys
sys.path.insert(0, sys.argv[1])
before = set(sys.modules)
import intelligence.canonical_memory
loaded = sorted(set(sys.modules) - before)
print(json.dumps(loaded))
"""


def test_import_in_a_fresh_isolated_interpreter_loads_no_live_or_network_module():
    proc = subprocess.run(
        [sys.executable, "-I", "-B", "-c", _PROBE, str(_REPO_ROOT)],
        capture_output=True,
        timeout=60,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr.decode("utf-8", "replace")
    loaded = json.loads(proc.stdout.decode("utf-8"))
    offenders = [
        name for name in loaded
        if name.split(".")[0] in _LIVE_ROOTS or any(name == m or name.startswith(m + ".") for m in _LIVE_MODULES)
    ]
    assert offenders == []
    assert "intelligence.current_knowledge" in loaded


def test_no_database_hydration_or_transition_surface_is_exported():
    exported = {name.lower() for name in package.__all__}
    for word in ("hydrate", "promote", "transition", "cutover", "database", "connect", "apply", "sync", "write"):
        assert not any(word in name for name in exported), word


def test_bootstrap_authority_is_git_only():
    assert package.AUTHORITIES == schema.AUTHORITIES == frozenset({"git"})


def test_package_declares_its_lack_of_authorization():
    notice = package.AUTHORIZATION_NOTICE.lower()
    assert "git-mirroring infrastructure only" in notice
    assert "git remains the only authority" in notice
    assert "nothing here grants runtime authority" in notice
    assert "authorizes autonomous or funded trading" in notice
    assert "execution remains disabled" in notice
    assert "does not, and must not be extended to" in (package.__doc__ or "")
    assert package.SCHEMA_VERSION == 1


def test_explicit_exports_resolve():
    assert len(package.__all__) == len(set(package.__all__))
    for name in package.__all__:
        assert hasattr(package, name), name
