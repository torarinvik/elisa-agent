"""Optional native kernels, written in Elisa and built as CPython extensions.

Each ``<name>.elisa`` here exports a Python module ``nca.native.<name>``;
a domain keeps its own kernels beside its code in the same way, so
``nca/domains/<domain>/<name>.elisa`` exports ``nca.domains.<domain>.<name>``. The
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
import os
import shutil
import subprocess
import sys
import sysconfig
from pathlib import Path
from types import ModuleType

HERE = Path(__file__).parent
PACKAGE = HERE.parent


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
    """Build each Elisa source into an extension module beside it."""
    suffix = sysconfig.get_config_var("EXT_SUFFIX")
    environment = dict(os.environ, PYTHON_BIN=sys.executable)
    for source in sources:
        out = source.with_suffix(suffix)
        subprocess.run([str(compiler), "-emit", "pymodule-so", "-o", str(out), str(source)],
                       check=True, env=environment)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the native kernels.")
    parser.add_argument("--compiler", type=Path,
                        default=os.environ.get("ELISA_STAGE1") or shutil.which("elisac-stage1"),
                        help="the Elisa stage1 compiler (default: elisac-stage1 on PATH)")
    parser.add_argument("names", nargs="*",
                        help="kernels to build, by name or package path (default: all)")
    args = parser.parse_args()
    if args.compiler is None:
        parser.error("no compiler: install elisac-stage1, pass --compiler or set ELISA_STAGE1")
    sources = sorted(PACKAGE.rglob("*.elisa"))
    if args.names:
        sources = [s for s in sources
                   if s.stem in args.names
                   or ".".join(s.relative_to(PACKAGE).with_suffix("").parts) in args.names]
    build(args.compiler, sources)

