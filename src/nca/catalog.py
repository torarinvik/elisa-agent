"""Expert packages installed from an index of pinned records.

The index is a git repository holding one immutable record per published
package version, ``packages/NAME/VERSION.json``. A record names the code by a
git location and an exact commit, and each weight or data file by its
SHA-256 and byte count with the places it can be fetched from. Commits and
digests are the identity; locations only say where to fetch.

``add`` updates a local copy of the index in the agent home, installs the
code at the pinned commit into the running environment and admits every
required blob, refusing bytes that do not match the record. It refuses a
package that is installed editable, so a working checkout is never replaced
by its published version. The index location is ``$ELISA_AGENT_INDEX``, else the public index. A local index may
name code by local path, for development; a remote one must name ``https``
locations.

The index itself is not yet signed: a published version cannot be altered
without changing its commit or digests, but whoever controls the index can
publish a new version. The local copy only ever moves forward.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Sequence
from importlib import metadata
from pathlib import Path
from typing import Any, BinaryIO

from nca import agents
from nca.packages import GROUP

RECORD_VERSION = 1
PUBLIC_INDEX = "https://github.com/torarinvik/elisa-agent-index"
_NAME = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}")
_VERSION = re.compile(r"[0-9]+(\.[0-9]+){0,3}")
_COMMIT = re.compile(r"[0-9a-f]{40}")
_DIGEST = re.compile(r"[0-9a-f]{64}")
_HUGGINGFACE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*")
_FILE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*(/[A-Za-z0-9][A-Za-z0-9._-]*)*")


def index_location() -> str:
    return os.environ.get("ELISA_AGENT_INDEX") or PUBLIC_INDEX


def _numbers(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def _git(*arguments: str) -> str:
    done = subprocess.run(["git", *arguments], capture_output=True, text=True, check=False)
    if done.returncode != 0:
        raise RuntimeError(f"git {arguments[0]} failed: {done.stderr.strip()}")
    return done.stdout.strip()


def refresh(root: Path, location: str) -> Path:
    """Bring the local copy of the index at ``location`` up to date.

    The copy only fast-forwards, so an index whose history was rewritten is
    refused instead of followed.
    """
    copy = root / "index"
    if not (copy / ".git").is_dir():
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        _git("clone", "--quiet", location, str(copy))
    elif _git("-C", str(copy), "remote", "get-url", "origin") != location:
        raise ValueError(f"the index copy in {copy} follows another location; remove it to "
                         f"follow {location}")
    else:
        _git("-C", str(copy), "pull", "--quiet", "--ff-only")
    return copy


def source_url(source: Any) -> str:
    """The ``https`` address a blob source names."""
    if isinstance(source, dict) and isinstance(source.get("url"), str):
        url = source["url"]
    elif (isinstance(source, dict) and all(isinstance(source.get(key), str)
                                           for key in ("huggingface", "revision", "file"))
          and _HUGGINGFACE.fullmatch(source["huggingface"])
          and _COMMIT.fullmatch(source["revision"]) and _FILE.fullmatch(source["file"])):
        url = (f"https://huggingface.co/{source['huggingface']}/resolve/"
               f"{source['revision']}/{source['file']}")
    else:
        raise ValueError(f"blob source {source!r} is neither a url nor a huggingface "
                         "repository with an exact revision and file")
    if not url.startswith("https://"):
        raise ValueError(f"blob source {url} is not an https address")
    return url


def validate(record: Any, *, local: bool) -> None:
    """Refuse a record ``add`` could not install exactly as written."""
    def need(condition: bool, problem: str) -> None:
        if not condition:
            raise ValueError(f"package record: {problem}")

    need(isinstance(record, dict) and record.get("elisa-package") == RECORD_VERSION,
         f"not an elisa-package record of version {RECORD_VERSION}")
    need(isinstance(record.get("name"), str) and bool(_NAME.fullmatch(record["name"])),
         "name is missing or malformed")
    need(isinstance(record.get("version"), str) and bool(_VERSION.fullmatch(record["version"])),
         "version is not dotted numbers")
    code = record.get("code")
    need(isinstance(code, dict) and isinstance(code.get("git"), str)
         and isinstance(code.get("commit"), str) and bool(_COMMIT.fullmatch(code["commit"])),
         "code needs a git location and a commit of 40 hexadecimal digits")
    need(code["git"].startswith("https://") or (local and Path(code["git"]).is_absolute()),
         "code.git must be an https address")
    contributes = record.get("contributes")
    need(isinstance(contributes, list) and all(isinstance(name, str) for name in contributes),
         "contributes must list entry-point names")
    core = record.get("requires", {}).get("core", ">=0")
    need(isinstance(core, str) and core.startswith(">=")
         and bool(_VERSION.fullmatch(core[2:])), "requires.core must be >=VERSION")
    blobs = record.get("blobs")
    need(isinstance(blobs, list), "blobs must be a list")
    for blob in blobs:
        need(isinstance(blob, dict) and isinstance(blob.get("name"), str)
             and bool(_FILE.fullmatch(blob["name"])), "a blob name is missing or malformed")
        need(isinstance(blob.get("sha256"), str) and bool(_DIGEST.fullmatch(blob["sha256"]))
             and type(blob.get("bytes")) is int and blob["bytes"] > 0
             and isinstance(blob.get("sources"), list)
             and isinstance(blob.get("optional"), bool),
             f"blob {blob['name']} needs sha256, bytes, sources and optional")
        need(blob["optional"] or bool(blob["sources"]),
             f"required blob {blob['name']} has no source")
        for source in blob["sources"]:
            source_url(source)
    names = [blob["name"] for blob in blobs]
    need(len(set(names)) == len(names), "two blobs share a name")


def find(index: Path, name: str, version: str | None, *, local: bool) -> dict[str, Any]:
    """The record of ``name`` at ``version``, or at its highest version."""
    if not _NAME.fullmatch(name) or (version is not None and not _VERSION.fullmatch(version)):
        raise ValueError(f"{name}@{version} is not a package name and version")
    published = {path.stem: path for path in (index / "packages" / name).glob("*.json")
                 if _VERSION.fullmatch(path.stem)}
    if not published:
        raise ValueError(f"the index has no package {name}")
    chosen = version if version is not None else max(published, key=_numbers)
    if chosen not in published:
        raise ValueError(f"the index has no {name} {chosen}; it has "
                         + ", ".join(sorted(published, key=_numbers)))
    record = json.loads(published[chosen].read_text())
    validate(record, local=local)
    if (record["name"], record["version"]) != (name, chosen):
        raise ValueError(f"{published[chosen]} describes {record['name']} {record['version']}")
    return record


def _open(url: str) -> BinaryIO:
    """Open ``url``, following redirects and waiting out a busy server.

    Archives answer a burst of requests with 429 or a 5xx status and say how
    long to wait; three more attempts are made, each after at most a minute.
    """
    request = urllib.request.Request(url, headers={"User-Agent": "elisa-agent"})
    for attempt in range(4):
        try:
            return urllib.request.urlopen(request, timeout=60)  # noqa: S310 - https only
        except urllib.error.HTTPError as error:
            if attempt == 3 or error.code not in (429, 500, 502, 503, 504):
                raise
            stated = error.headers.get("Retry-After", "")
            time.sleep(min(int(stated), 60) if stated.isdecimal() else 2 ** (attempt + 1))
    raise AssertionError("unreachable")


def _editable(distribution: str) -> bool:
    """Whether ``distribution`` is installed from a working checkout."""
    try:
        direct = metadata.distribution(distribution).read_text("direct_url.json")
    except metadata.PackageNotFoundError:
        return False
    return bool(direct) and json.loads(direct).get("dir_info", {}).get("editable") is True


def fetch_blob(blob: dict[str, Any]) -> str:
    """Admit the blob a record describes, downloading it when it is absent.

    Each source is tried in turn. Bytes are hashed as they arrive and a file
    of another length or digest is discarded, never admitted.
    """
    path = agents.home() / "blobs" / "sha256" / blob["sha256"]
    if path.is_file():
        return f"sha256:{blob['sha256']}"
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    staged = path.with_name(f".{path.name}.{os.getpid()}")
    problems = []
    for source in blob["sources"]:
        url = source_url(source)
        try:
            hashing, received = hashlib.sha256(), 0
            with _open(url) as stream, staged.open("wb") as out:
                while received <= blob["bytes"] and (chunk := stream.read(1 << 20)):
                    hashing.update(chunk)
                    received += len(chunk)
                    out.write(chunk)
            if received != blob["bytes"] or hashing.hexdigest() != blob["sha256"]:
                raise ValueError(f"{received} bytes with sha256 {hashing.hexdigest()} "
                                 "do not match the record")
            staged.chmod(0o400)
            staged.replace(path)
            return f"sha256:{blob['sha256']}"
        except (OSError, ValueError) as error:
            problems.append(f"{url}: {error}")
        finally:
            staged.unlink(missing_ok=True)
    raise RuntimeError(f"blob {blob['name']} could not be fetched:\n  " + "\n  ".join(problems))


def _install_code(git: str, commit: str) -> None:
    """Install the distribution at ``commit`` into the running environment."""
    requirement = f"git+{git if '://' in git else Path(git).as_uri()}@{commit}"
    installer = (["uv", "pip", "install", "--python", sys.executable] if shutil.which("uv")
                 else [sys.executable, "-m", "pip", "install"])
    done = subprocess.run([*installer, requirement], check=False)
    if done.returncode != 0:
        raise RuntimeError(f"installing {requirement} failed")


def add(root: Path, name: str, version: str | None = None,
        wanted: Sequence[str] = ()) -> dict[str, Any]:
    """Install package ``name`` from the index with its required blobs and
    the optional blobs named in ``wanted``. Returns its record."""
    location = index_location()
    local = "://" not in location
    record = find(refresh(root, location), name, version, local=local)
    core = agents.core_version()
    if _numbers(core) < _numbers(record.get("requires", {}).get("core", ">=0")[2:]):
        raise ValueError(f"{name} {record['version']} needs core {record['requires']['core']}, "
                         f"this is {core}")
    optional = {blob["name"] for blob in record["blobs"] if blob["optional"]}
    if unknown := sorted(set(wanted) - optional):
        raise ValueError(f"{name} {record['version']} has no optional blob named "
                         + ", ".join(unknown))
    if _editable(name):
        raise ValueError(f"{name} is installed here from a working checkout (editable); adding "
                         "the published version would replace that work. Use another "
                         "environment, or uninstall it first")
    _install_code(record["code"]["git"], record["code"]["commit"])
    importlib.invalidate_caches()
    contributed = {entry.name for entry in metadata.entry_points(group=GROUP)}
    if missing := sorted(set(record["contributes"]) - contributed):
        raise RuntimeError(f"{name} was installed but does not contribute " + ", ".join(missing))
    for blob in record["blobs"]:
        if not blob["optional"] or blob["name"] in wanted:
            fetch_blob(blob)
    added = root / "added"
    added.mkdir(mode=0o700, parents=True, exist_ok=True)
    (added / f"{name}.json").write_text(json.dumps(record, indent=2) + "\n")
    return record


def notices(record: dict[str, Any]) -> list[str]:
    """What the licences of a record's parts oblige a user to be told."""
    lines = [f"code: {record['code'].get('license') or 'no licence stated'}"]
    for blob in record["blobs"]:
        lines.append(f"{blob['name']}: {blob.get('license') or 'no licence stated'}"
                     + (f"; {blob['attribution']}" if blob.get("attribution") else ""))
    return lines
