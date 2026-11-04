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


def test_native_integer_record_selection_matches_exhaustive_reference() -> None:
    from array import array
    from itertools import product

    kernel = native.load("records")
    if kernel is None:
        pytest.skip("native record selector unavailable or disabled")
    for length in range(7):
        for values in product((-2, 0, 2), repeat=length):
            packed = array("q", values)
            for width in range(1, 4):
                for column in range(width):
                    for needle in (-2, 0, 2):
                        expected = ([] if length % width else [
                            row for row in range(length // width)
                            if values[row * width + column] == needle])
                        assert kernel.select_equal(packed, width, column, needle) == expected
    extreme = array("q", [-(2 ** 63), 2 ** 63 - 1, -(2 ** 63)])
    assert kernel.select_equal(extreme, 1, 0, -(2 ** 63)) == [0, 2]
    for width, column in ((0, 0), (-1, 0), (1, -1), (1, 1), (3, 0)):
        assert kernel.select_equal(array("q", [1, 2]), width, column, 1) == []


def test_assignment_kernel_preserves_all_small_stable_orders() -> None:
    from itertools import product

    kernel = native.load("assignment")
    if kernel is None:
        pytest.skip("native assignment kernel unavailable or disabled")
    for arity in range(1, 6):
        for size in range(1, 6):
            choices = list(product(range(arity), repeat=size))
            expected = sorted(range(len(choices)), key=lambda i: (
                max(choices[i].count(j) for j in range(arity)), choices[i]))
            assert kernel.order(arity, size, 4096) == expected
    assert kernel.order(0, 3, 4096) == []
    assert kernel.order(2, 13, 4096) == []


def test_assignment_kernel_matches_every_cacheable_shape() -> None:
    from itertools import product

    kernel = native.load("assignment")
    if kernel is None:
        pytest.skip("native assignment kernel unavailable or disabled")
    for arity in range(2, 65):
        size = 1
        while arity ** size * arity <= 4096:
            choices = list(product(range(arity), repeat=size))
            expected = sorted(range(len(choices)), key=lambda i: (
                max(choices[i].count(j) for j in range(arity)), choices[i]))
            assert kernel.order(arity, size, 4096) == expected
            size += 1
