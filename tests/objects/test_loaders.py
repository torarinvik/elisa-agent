import json
import random
import re
import shutil
import subprocess
from collections.abc import Iterator
from importlib import metadata
from pathlib import Path

import pytest

from nca.objects import loaders

SRC = Path(__file__).resolve().parents[2] / "src" / "nca"


@pytest.fixture
def fresh() -> Iterator[None]:
    loaders.refresh()
    yield
    loaders.refresh()


def test_legacy_import_paths_alias_the_stable_factories() -> None:
    registered = {name: next(iter(places)) for name, places in loaders.registered().items()}
    stable = {place: name for name, place in registered.items() if "@" in name}
    legacy = {name: place for name, place in registered.items() if ":" in name}
    assert legacy, "earlier artifacts' entries must stay registered"
    for name, place in legacy.items():
        assert place in stable, f"{name} aliases no stable identifier"
        assert loaders.resolve(name) is loaders.resolve(stable[place])


def test_core_primitives_store_registered_identifiers_not_import_paths() -> None:
    entry = re.compile(r'Primitive\([^,]+,\s*f?"([^"]*)"')
    found = [match for path in SRC.rglob("*.py") for match in entry.findall(path.read_text())]
    assert found
    for text in found:
        assert ":" not in text and text.endswith("@1"), text


def test_conflicting_registrations_refuse_only_their_identifier(
        monkeypatch: pytest.MonkeyPatch, fresh: None) -> None:
    points = (metadata.EntryPoint("vendor/model@1", "first:load", loaders.GROUP),
              metadata.EntryPoint("vendor/model@1", "second:load", loaders.GROUP),
              metadata.EntryPoint("vendor/other@1", "nca.objects.loaders:refresh",
                                  loaders.GROUP))

    def entry_points(group: str) -> tuple[metadata.EntryPoint, ...]:
        return points if group == loaders.GROUP else ()

    monkeypatch.setattr(metadata, "entry_points", entry_points)
    with pytest.raises(ValueError, match="registered at"):
        loaders.resolve("vendor/model@1")
    assert loaders.resolve("vendor/other@1") is loaders.refresh


def test_duplicate_identical_registrations_are_one(monkeypatch: pytest.MonkeyPatch,
                                                   fresh: None) -> None:
    point = metadata.EntryPoint("vendor/model@1", "nca.objects.loaders:refresh", loaders.GROUP)

    def entry_points(group: str) -> tuple[metadata.EntryPoint, ...]:
        return (point, point) if group == loaders.GROUP else ()

    monkeypatch.setattr(metadata, "entry_points", entry_points)
    assert loaders.resolve("vendor/model@1") is loaders.refresh


def test_unregistered_identifiers_fail_and_import_paths_still_load() -> None:
    with pytest.raises(LookupError, match="not registered"):
        loaders.resolve("vendor/missing@1")
    assert loaders.resolve("nca.objects.loaders:refresh") is loaders.refresh


def test_resolution_matches_the_lean_model_on_generated_registries() -> None:
    """``NCA.resolveLoader``: order-free, per-identifier, conflict-refusing."""
    lake = shutil.which("lake")
    if lake is None:
        pytest.skip("Lean differential checks require the development toolchain")
    rng = random.Random(4127)
    names, places = ["a@1", "b@1", "m:f", "c@2"], ["x:load", "y:load", "z:load"]
    fixtures, expected = [], []
    for _ in range(256):
        pairs = [(rng.choice(names), rng.choice(places)) for _ in range(rng.randrange(7))]
        probes = names + ["absent@1"]
        fixtures.append({"registrations": pairs, "probes": probes})
        expected.append([loaders.location(pairs, name) for name in probes])
    lean = Path(__file__).resolve().parents[2] / "lean"
    subprocess.run([lake, "build", "NCA.Execution.Loaders"], cwd=lean,
                   capture_output=True, text=True, check=True, timeout=120)
    result = subprocess.run(
        [lake, "env", "lean", "--run", "NCA/Execution/LoaderReplay.lean"],
        cwd=lean, input=json.dumps(fixtures), capture_output=True, text=True,
        check=True, timeout=120,
    )
    assert json.loads(result.stdout) == expected
