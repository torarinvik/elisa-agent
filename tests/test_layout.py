"""The core never depends on a domain, and domains never depend on each other."""

from __future__ import annotations

import ast
from pathlib import Path

from nca.abi import App, Contract, Term, parse_type
from nca.objects import Composite, Primitive, Store, constructors
from nca.packages import discover

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


CORE_CONSTRUCTORS = {"seq", "pair", "either", "unit"}


def textual(term: Term) -> set[str]:
    if not isinstance(term, App):
        return set()
    own = set() if term.name.startswith("sha256:") or term.name in CORE_CONSTRUCTORS else {term.name}
    return own.union(*(textual(a) for a in term.args))


def test_domain_packages_name_their_types_by_constructor_objects() -> None:
    store = Store()
    offending: dict[str, set[str]] = {}
    for name, ref in discover(store).items():
        for node in store.walk(ref):
            obj = store.get(node)
            if isinstance(obj, Primitive):
                label, contracts = obj.manifest.module_id, [obj.manifest.contract]
            elif isinstance(obj, Composite):
                label = obj.name
                contracts = [*(obj.exports or ()), *(Contract(i, o) for i, o in obj.requires)]
            else:
                continue
            names = set().union(*(textual(parse_type(t)) for c in contracts
                                  for t in (*c.inputs, c.output,
                                            *(u for i, o in c.slots for u in (*i, o)))))
            if names:
                offending[f"{name}: {label}"] = names
            # Installing the package brings every type it names.
            assert set(constructors(contracts)) <= set(store.walk(ref))
    assert offending == {}


def test_domains_share_truth_values_by_identical_constructors() -> None:
    from nca.domains.arithmetic import types as arithmetic
    from nca.domains.boolean import types as boolean

    assert arithmetic.BOOLEAN.ref == boolean.BOOLEAN.ref
