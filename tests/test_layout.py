"""The kernel has no built-in task packages or undeclared package imports."""

from __future__ import annotations

import ast
import re
import sys
import tomllib
from importlib import metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "src" / "nca"


def imported_modules(path: Path) -> set[str]:
    """Absolute imports, including literal dynamic imports, at any depth."""
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(), str(path))):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None and node.level == 0:
            names.add(node.module)
        elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
              and node.func.attr == "import_module" and node.args
              and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str)):
            names.add(node.args[0].value)
    return names


def test_core_and_its_tests_import_only_declared_dependencies() -> None:
    config = tomllib.loads((ROOT / "pyproject.toml").read_text())
    project = config["project"]
    requirements = [*project.get("dependencies", []),
                    *(r for group in project.get("optional-dependencies", {}).values() for r in group),
                    *(r for group in config.get("dependency-groups", {}).values() for r in group)]
    declared = {re.split(r"[<>=!~\[; ]", r, maxsplit=1)[0].lower().replace("-", "_")
                for r in requirements}
    owners = metadata.packages_distributions()
    allowed = set(sys.stdlib_module_names) | {"nca"} | declared
    test_modules = {p.stem for p in (ROOT / "tests").rglob("*.py")}
    offending = {}
    for path in [*PACKAGE.rglob("*.py"), *(ROOT / "tests").rglob("*.py")]:
        local = test_modules if path.is_relative_to(ROOT / "tests") else set()
        unexpected = []
        for module in imported_modules(path):
            name = module.split(".")[0]
            distributions = {d.lower().replace("-", "_") for d in owners.get(name, ())}
            if name not in allowed | local and not distributions & declared:
                unexpected.append(module)
        if unexpected:
            offending[str(path.relative_to(ROOT))] = sorted(unexpected)
    assert offending == {}


def test_core_contains_no_bundled_expert_packages_or_catalog() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    assert not (PACKAGE / "domains").exists()
    assert not (PACKAGE / "modules").exists()
    assert not project.get("entry-points", {}).get("nca.packages")
    assert not [entry for entry in metadata.distribution("nca").entry_points
                if entry.group == "nca.packages"]


def test_import_scanner_checks_nested_and_dynamic_imports(tmp_path: Path) -> None:
    source = tmp_path / "sample.py"
    source.write_text('def f():\n    import hypothetical_plugin\n'
                      '    from another_plugin import Expert\n'
                      '    importlib.import_module("dynamic_plugin.impl")\n')
    assert imported_modules(source) == {"hypothetical_plugin", "another_plugin", "dynamic_plugin.impl"}
