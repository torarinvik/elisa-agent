"""Test the core and every package checkout under a directory in one environment.

Discovers packages by their ``pyproject.toml``, names none of them, and installs
all of them editable into a throwaway environment, so entry points and package
metadata resolve as they would for a user. Exits nonzero if any suite fails.
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

CORE = Path(__file__).resolve().parent.parent


def install(python: Path, checkouts: list[Path]) -> None:
    arguments = [item for checkout in checkouts for item in ("-e", str(checkout))]
    subprocess.run(["uv", "pip", "install", "--quiet", "--python", str(python), "pytest", *arguments],
                   check=True)


def suite(python: Path, checkout: Path, seconds: float) -> tuple[bool, str]:
    environment = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    try:
        result = subprocess.run([str(python), "-m", "pytest", "-q", "-p", "no:cacheprovider"], cwd=checkout,
                                env=environment, capture_output=True, text=True, timeout=seconds, check=False)
    except subprocess.TimeoutExpired:
        return False, f"timed out after {seconds:g} s"
    lines = result.stdout.strip().splitlines()
    failures = [line for line in lines if line.startswith(("FAILED", "ERROR"))]
    return result.returncode == 0, "\n    ".join([lines[-1] if lines else "no output", *failures])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packages", type=Path, required=True, help="directory holding package checkouts")
    parser.add_argument("--seconds", type=float, default=280, help="time limit per suite")
    args = parser.parse_args()
    checkouts = sorted(path.parent for path in args.packages.resolve().glob("*/pyproject.toml"))
    if shutil.which("uv") is None or not checkouts:
        parser.error("requires uv and at least one package checkout")
    with tempfile.TemporaryDirectory(prefix="nca-check-") as directory:
        environment = Path(directory) / "environment"
        subprocess.run(["uv", "venv", "--quiet", "--python", f"{sys.version_info.major}.{sys.version_info.minor}",
                        str(environment)], check=True)
        python = environment / "bin" / "python"
        install(python, [CORE, *checkouts])
        passed = True
        for checkout in [CORE, *checkouts]:
            good, summary = suite(python, checkout, args.seconds)
            passed &= good
            print(f"{'ok  ' if good else 'FAIL'} {checkout.name}: {summary}", flush=True)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
