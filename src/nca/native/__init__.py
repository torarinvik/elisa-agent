"""Optional native kernels, written in Elisa and built as CPython extensions.

Each ``<name>.elisa`` here exports a Python module ``nca.native.<name>``.
Independently installed packages keep their own kernels beside their code. The
kernels are accelerators only: every one has a pure Python/NumPy reference
that gives the same results (within floating-point rounding) and that the
package uses whenever the kernel is not built. Build them with the Elisa
self-hosted compiler for the running interpreter:

    uv run python -m nca.native

which uses ``elisac-stage1`` from ``PATH`` (or ``--compiler``, or
``ELISA_STAGE1``). ``NCA_NATIVE=0`` disables the kernels at run time.
"""

from __future__ import annotations

import argparse
import importlib
import importlib.util
import os
import shutil
import subprocess
import sys
import sysconfig
from pathlib import Path
from types import ModuleType

def load(name: str, package: str = __name__) -> ModuleType | None:
    """The built kernel ``name`` of ``package``, or ``None`` if it is not built
    or disabled."""
    if os.environ.get("NCA_NATIVE", "1") == "0":
        return None
    try:
        return importlib.import_module(f"{package}.{name}")
    except ImportError:
        return None


def build(compiler: Path, sources: list[Path]) -> None:
    """Build strict-FP Elisa extensions beside their entry sources.

    Reference equivalence and conservative error accounting require ordinary
    division, including subnormal denominators, without reciprocal relaxation.
    """
    suffix = sysconfig.get_config_var("EXT_SUFFIX")
    environment = dict(os.environ, PYTHON_BIN=sys.executable)
    for source in sources:
        out = source.with_suffix(suffix)
        subprocess.run([str(compiler), "-fstrict-fp", "-emit", "pymodule-so", "-o", str(out), str(source)],
                       check=True, env=environment)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the native kernels.")
    parser.add_argument("--compiler", type=Path,
                        default=os.environ.get("ELISA_STAGE1") or shutil.which("elisac-stage1"),
                        help="the Elisa stage1 compiler (default: elisac-stage1 on PATH)")
    parser.add_argument("names", nargs="*",
                        help="kernels to build, by name or package path (default: all)")
    parser.add_argument("--package", action="append", dest="packages",
                        help="installed package whose kernels to build (repeatable; default: nca.native)")
    args = parser.parse_args()
    if args.compiler is None:
        parser.error("no compiler: install elisac-stage1, pass --compiler or set ELISA_STAGE1")
    sources: dict[Path, str] = {}
    for name in args.packages or [__name__]:
        try:
            spec = importlib.util.find_spec(name)
        except ModuleNotFoundError:
            spec = None
        if spec is None or spec.submodule_search_locations is None:
            parser.error(f"{name!r} is not an installed Python package")
        for location in spec.submodule_search_locations:
            root = Path(location)
            for source in root.rglob("*.elisa"):
                relative = ".".join(source.relative_to(root).with_suffix("").parts)
                sources[source] = f"{name}.{relative}"
    if args.names:
        sources = {s: name for s, name in sources.items()
                   if s.stem in args.names or name in args.names
                   or name.removeprefix("nca.") in args.names}
    build(args.compiler, sorted(sources))

