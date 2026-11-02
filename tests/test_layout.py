"""The core never depends on a domain, and domains never depend on each other."""

from __future__ import annotations

import ast
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent.parent / "src" / "nca"
DOMAINS = PACKAGE / "domains"


def imported_modules(path: Path) -> set[str]:
    """Every absolute module a file imports, at any depth in the file."""
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(), str(path))):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None and node.level == 0:
            names.add(node.module)
            names.update(f"{node.module}.{alias.name}" for alias in node.names)
    return names


def domain_of(module: str) -> str | None:
    parts = module.split(".")
    return parts[2] if parts[:2] == ["nca", "domains"] and len(parts) > 2 else None


def test_core_imports_no_domain() -> None:
    offending = {
        str(path.relative_to(PACKAGE)): sorted(m for m in imported_modules(path)
                                               if m == "nca.domains" or domain_of(m))
        for path in PACKAGE.rglob("*.py") if DOMAINS not in path.parents}
    assert {path: modules for path, modules in offending.items() if modules} == {}


def test_domains_import_only_the_core_and_themselves() -> None:
    offending = {}
    for path in DOMAINS.rglob("*.py"):
        if path.parent == DOMAINS:
            continue
        own = path.relative_to(DOMAINS).parts[0]
        others = sorted(m for m in imported_modules(path) if domain_of(m) not in (None, own))
        if others:
            offending[str(path.relative_to(PACKAGE))] = others
    assert offending == {}
