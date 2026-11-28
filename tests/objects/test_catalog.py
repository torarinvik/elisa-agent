"""Packages from an index: record choice, validation and verified blobs."""

import hashlib
import io
import json
import subprocess
from importlib import metadata
from pathlib import Path
from typing import Any

import pytest

from nca import agents, catalog

WEIGHTS = b"weights" * 5000
COMMIT = "a" * 40


def record(version: str = "1.2.0", **changes: Any) -> dict[str, Any]:
    blob = {"name": "small/model.bin", "sha256": hashlib.sha256(WEIGHTS).hexdigest(),
            "bytes": len(WEIGHTS), "sources": [{"url": "https://example.invalid/model.bin"}],
            "license": "CC-BY-4.0", "attribution": "Somebody 2025", "optional": False}
    extra = dict(blob, name="large.bin", optional=True, sources=[
        {"huggingface": "someone/model", "revision": "b" * 40, "file": "large.bin"}])
    return {"elisa-package": 1, "name": "reader", "version": version, "summary": "Reads.",
            "code": {"git": "https://example.invalid/reader", "commit": COMMIT, "license": "MIT"},
            "requires": {"core": ">=0.1.0", "python": ">=3.11"}, "contributes": ["reader"],
            "blobs": [blob, extra], **changes}


def publish(index: Path, *records: dict[str, Any]) -> None:
    for entry in records:
        path = index / "packages" / entry["name"] / f"{entry['version']}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(entry))
    for command in (["init", "--quiet"], ["add", "-A"],
                    ["-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit",
                     "--quiet", "--allow-empty", "-m", "publish"]):
        subprocess.run(["git", "-C", str(index), *command], check=True)


@pytest.fixture
def root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    index = tmp_path / "index-origin"
    index.mkdir()
    publish(index, record("1.2.0"), record("1.10.0"))
    monkeypatch.setenv("ELISA_AGENT_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("ELISA_AGENT_INDEX", str(index))
    monkeypatch.setattr(catalog, "_install_code", lambda git, commit: None)
    monkeypatch.setattr(catalog, "_open", lambda url: io.BytesIO(WEIGHTS))
    monkeypatch.setattr(metadata, "entry_points",
                        lambda group: [metadata.EntryPoint("reader", "x:y", group)])
    return tmp_path / "home"


def test_add_takes_the_highest_version_and_only_required_blobs(
        root: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert agents.main(["add", "reader"]) == 0
    shown = capsys.readouterr().out
    assert "added reader 1.10.0 at aaaaaaaaaaaa" in shown
    assert "small/model.bin: CC-BY-4.0; Somebody 2025" in shown
    kept = agents.blob(hashlib.sha256(WEIGHTS).hexdigest())
    assert kept.read_bytes() == WEIGHTS and len(list(kept.parent.iterdir())) == 1
    assert json.loads((root / "added" / "reader.json").read_text())["version"] == "1.10.0"
    assert agents.main(["add", "reader@1.2.0", "--with", "large.bin"]) == 0
    assert agents.main(["add", "reader@9.9.9"]) == 1
    assert agents.main(["add", "reader", "--with", "missing.bin"]) == 1
    assert agents.main(["add", "absent"]) == 1


def test_a_blob_that_does_not_match_its_record_is_never_admitted(
        root: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    for served in (WEIGHTS[:-1], WEIGHTS + b"x", WEIGHTS[:-1] + b"X"):
        monkeypatch.setattr(catalog, "_open", lambda url, served=served: io.BytesIO(served))
        assert agents.main(["add", "reader"]) == 1
        assert "do not match the record" in capsys.readouterr().err
        assert not list((root / "blobs" / "sha256").iterdir())
    assert not (root / "added").exists()


def test_the_index_copy_follows_new_versions_but_not_another_index(
        root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert agents.main(["add", "reader"]) == 0
    publish(tmp_path / "index-origin", record("2.0.0"))
    assert catalog.add(root, "reader")["version"] == "2.0.0"
    other = tmp_path / "other-index"
    other.mkdir()
    publish(other, record("3.0.0"))
    monkeypatch.setenv("ELISA_AGENT_INDEX", str(other))
    assert agents.main(["add", "reader"]) == 1


@pytest.mark.parametrize("changes, problem", [
    ({"code": {"git": "https://example.invalid/r", "commit": "main"}}, "commit of 40"),
    ({"code": {"git": "http://example.invalid/r", "commit": COMMIT}}, "https"),
    ({"code": {"git": "/somewhere/local", "commit": COMMIT}}, "https"),
    ({"requires": {"core": "==0.1.0"}}, "requires.core"),
    ({"blobs": [{"name": "../escape", "sha256": "0" * 64, "bytes": 1, "sources": [],
                 "optional": True}]}, "blob name"),
    ({"blobs": [{"name": "w.bin", "sha256": "0" * 64, "bytes": 1, "sources": [],
                 "optional": False}]}, "has no source"),
    ({"blobs": [{"name": "w.bin", "sha256": "0" * 64, "bytes": 1, "optional": False,
                 "sources": [{"url": "http://example.invalid/w.bin"}]}]}, "not an https"),
    ({"blobs": [{"name": "w.bin", "sha256": "0" * 64, "bytes": 1, "optional": False,
                 "sources": [{"huggingface": "a/b", "revision": "main", "file": "w"}]}]},
     "exact revision"),
])
def test_records_that_could_not_be_installed_exactly_are_refused(
        changes: dict[str, Any], problem: str) -> None:
    with pytest.raises(ValueError, match=problem):
        catalog.validate(record(**changes), local=False)


def test_a_local_index_may_name_code_by_local_path() -> None:
    local = record(code={"git": "/somewhere/local", "commit": COMMIT})
    catalog.validate(local, local=True)
    assert catalog.source_url(record()["blobs"][1]["sources"][0]) == (
        "https://huggingface.co/someone/model/resolve/" + "b" * 40 + "/large.bin")
