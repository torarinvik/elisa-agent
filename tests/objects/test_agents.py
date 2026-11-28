"""Named agents: locks, the shared store and spawned instances."""

import json
import sys
from importlib import metadata
from pathlib import Path

import pytest

from nca import agents
from nca.abi import Contract, Manifest
from nca.objects import Primitive, Store

ENTRY = f"{__name__}:make"


def make() -> None:
    return None


def contribute_reader(store: Store) -> str:
    return store.put(Primitive(Manifest("reader", "1.0.0", Contract(("text.v1",), "word.v1"), 1.0),
                               ENTRY, size=1))


def contribute_counter(store: Store) -> str:
    return store.put(Primitive(Manifest("counter", "1.0.0", Contract(("word.v1",), "int.v1"), 1.0),
                               ENTRY, size=1))


@pytest.fixture
def root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("ELISA_AGENT_HOME", str(tmp_path / "home"))
    contributions(monkeypatch, "reader", "counter")
    return tmp_path / "home"


def contributions(monkeypatch: pytest.MonkeyPatch, *names: str) -> None:
    found = [metadata.EntryPoint(name, f"{__name__}:contribute_{name}", agents.GROUP)
             for name in names]
    monkeypatch.setattr(metadata, "entry_points", lambda group: found)


def test_home_follows_the_elisapkg_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("ELISA_AGENT_HOME", raising=False)
    monkeypatch.setenv("ELISAPKG_HOME", str(tmp_path))
    assert agents.home() == tmp_path / "agent"
    monkeypatch.delenv("ELISAPKG_HOME")
    assert agents.home() == Path.home() / ".elisapkg" / "agent"


def test_created_agent_locks_packages_and_shares_one_store(root: Path) -> None:
    assert agents.main(["create", "first"]) == 0
    assert agents.main(["create", "second"]) == 0
    lock = agents.Lock.read(root / "agents" / "first" / "agent.lock")
    assert [package.name for package in lock.packages] == ["counter", "reader"]
    stored = {f"sha256:{path.stem}" for path in (root / "store").glob("*.json")}
    assert stored == {package.ref for package in lock.packages}
    assert Store.open(root / "store")
    assert agents.main(["create", "first"]) == 1
    assert agents.main(["create", "Not/A/Name"]) == 1


def test_install_refuses_a_lock_the_environment_does_not_match(
        root: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    assert agents.main(["create", "source"]) == 0
    assert agents.main(["export", "source"]) == 0
    exported = root / "exported.lock"
    exported.write_text(capsys.readouterr().out.split("\n", 1)[1])
    assert agents.main(["install", str(exported), "--name", "copy"]) == 0

    contributions(monkeypatch, "reader")
    assert agents.main(["install", str(exported), "--name", "partial"]) == 1
    assert "package counter" in capsys.readouterr().err
    assert not (root / "agents" / "partial").exists()

    contributions(monkeypatch, "reader", "counter")
    changed = json.loads(exported.read_text())
    changed["packages"][0]["ref"] = "sha256:" + "0" * 64
    exported.write_text(json.dumps(changed))
    assert agents.main(["install", str(exported), "--name", "changed"]) == 1
    assert "the lock needs sha256:0000" in capsys.readouterr().err


def test_spawn_gives_each_instance_its_own_state(root: Path, tmp_path: Path) -> None:
    assert agents.main(["create", "worker"]) == 0
    report = "import os, pathlib; pathlib.Path(os.environ['ELISA_AGENT_STATE'], 'seen').write_text(os.environ['ELISA_AGENT_NAME'])"
    for _ in range(2):
        assert agents.main(["spawn", "worker", "--", sys.executable, "-c", report]) == 0
    instances = root / "agents" / "worker" / "instances"
    assert sorted(path.name for path in instances.iterdir()) == ["1", "2"]
    assert (instances / "2" / "seen").read_text() == "worker"
    assert agents.main(["spawn", "worker", "--", sys.executable, "-c", "raise SystemExit(3)"]) == 3
    assert agents.main(["spawn", "missing", "--", sys.executable]) == 1
    assert agents.main(["spawn", "worker"]) == 1
