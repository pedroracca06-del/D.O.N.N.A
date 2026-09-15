import ast
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1] / "intelligence" / "canonical_memory" / "hydration"


def test_exact_hydration_module_set():
    assert {p.name for p in PACKAGE.glob("*.py")} == {"__init__.py", "constants.py", "estimator.py", "hydrate.py", "projections.py", "relevance.py", "render.py", "schema.py"}


def test_no_prohibited_imports_or_calls():
    prohibited = {"os", "subprocess", "socket", "requests", "sqlite3", "time", "datetime", "random", "importlib", "pkgutil", "runpy", "builtins"}
    dynamic_names = {"__import__", "eval", "exec", "compile"}
    dynamic_attributes = {"import_module", "find_spec", "find_loader", "get_loader", "run_module", "run_path", "__import__"}
    for path in PACKAGE.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports = {node.names[0].name.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.Import)}
        imports |= {node.module.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module}
        assert not imports & prohibited
        called_names = {node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
        called_attributes = {node.func.attr for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)}
        assert not called_names & dynamic_names
        assert not called_attributes & dynamic_attributes
