"""The native builder locates optional packages without a fixed catalog."""

import sys
from pathlib import Path

import pytest

from nca import native


def test_builder_finds_kernels_in_an_independently_installed_package(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    package = tmp_path / "hypothetical_kernels"
    package.mkdir()
    (package / "__init__.py").write_text('"""Hypothetical plugin."""\n')
    first, second = package / "first.elisa", package / "second.elisa"
    first.write_text("// kernel fixture\n")
    second.write_text("// kernel fixture\n")
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setattr(sys, "argv", ["native", "--compiler", "/compiler", "--package",
                                      "hypothetical_kernels", "first"])
    calls = []

    def build(compiler: Path, sources: list[Path]) -> None:
        calls.append((compiler, sources))

    monkeypatch.setattr(native, "build", build)
    native.main()
    assert calls == [(Path("/compiler"), [first])]


def test_builder_rejects_a_missing_package(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["native", "--compiler", "/compiler", "--package",
                                      "hypothetical_missing_package"])
    with pytest.raises(SystemExit):
        native.main()


def test_build_requires_strict_floating_point_for_reference_equivalence(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []

    def run(command: list[str], *, check: bool, env: dict[str, str]) -> None:
        calls.append((command, check, env))

    monkeypatch.setattr(native.subprocess, "run", run)
    compiler, source = tmp_path / "compiler", tmp_path / "kernel.elisa"
    native.build(compiler, [source])
    assert len(calls) == 1
    command, check, environment = calls[0]
    assert command[0] == str(compiler) and command[-1] == str(source)
    assert "-fstrict-fp" in command
    assert check and environment["PYTHON_BIN"] == sys.executable
