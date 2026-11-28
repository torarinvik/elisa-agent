"""Named agents kept in a per-user home, and the ``elisa-agent`` command.

An agent is a lock: the core version and, for each expert package it was
created with, the distribution that contributed it, that distribution's
version and the reference of the object it put into the store. Objects are
content-addressed, so every agent shares one store and equal experts are kept
once. The home is ``$ELISA_AGENT_HOME``, else ``$ELISAPKG_HOME/agent``, else
``~/.elisapkg/agent``::

    store/                   every agent's objects, one file per digest
    blobs/sha256/DIGEST      large files such as weights, one per digest
    agents/NAME/agent.lock   what the agent consists of
    agents/NAME/instances/   one directory of state per spawned instance

Weights too large to ship inside a distribution are blobs: raw files kept
beside the store under their SHA-256. An expert names the digest in its
stored object, so the object's reference changes whenever the weights do, and
asks ``blob`` for the file when it loads.

A lock is checked against the running environment before an agent is
installed from it or spawned: each package must be contributed at the locked
version and give the locked reference. Nothing is fetched here; installing
the packages a lock names is the environment's job.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path
from typing import Any

from nca.objects import Store
from nca.packages import GROUP, discover

LOCK_VERSION = 1
CORE = "nca"
_NAME = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}")
_DIGEST = re.compile(r"[0-9a-f]{64}")


@dataclass(frozen=True)
class Package:
    """One expert package as an agent holds it."""

    name: str
    distribution: str | None
    version: str | None
    ref: str


@dataclass(frozen=True)
class Lock:
    core: str
    packages: tuple[Package, ...]

    def data(self) -> dict[str, Any]:
        return {"elisa-agent-lock": LOCK_VERSION, "core": {"name": CORE, "version": self.core},
                "packages": [vars(package) for package in self.packages]}

    @classmethod
    def read(cls, path: Path) -> Lock:
        data = json.loads(path.read_text())
        if not isinstance(data, dict) or data.get("elisa-agent-lock") != LOCK_VERSION:
            raise ValueError(f"{path} is not an elisa-agent lock of version {LOCK_VERSION}")
        packages = tuple(Package(str(entry["name"]), entry["distribution"], entry["version"],
                                 str(entry["ref"])) for entry in data["packages"])
        return cls(str(data["core"]["version"]), packages)


def home() -> Path:
    """The agent home of the current user."""
    if configured := os.environ.get("ELISA_AGENT_HOME"):
        return Path(configured)
    if elisapkg := os.environ.get("ELISAPKG_HOME"):
        return Path(elisapkg) / "agent"
    return Path.home() / ".elisapkg" / "agent"


def _blob_path(sha256: str) -> Path:
    digest = sha256.removeprefix("sha256:")
    if not _DIGEST.fullmatch(digest):
        raise ValueError(f"{sha256!r} is not a SHA-256 digest of 64 lowercase hexadecimal digits")
    return home() / "blobs" / "sha256" / digest


def blob(sha256: str) -> Path:
    """The local file of the admitted blob with digest ``sha256``.

    The digest was verified when the blob was admitted and is not recomputed
    here, so loading a large file does not read it twice.
    """
    path = _blob_path(sha256)
    if not path.is_file():
        raise LookupError(f"blob sha256:{path.name} is not in {path.parent}; "
                          "admit the file with nca.agents.admit_blob")
    return path


def admit_blob(source: Path) -> str:
    """Copy the file ``source`` into the blob directory and return its
    digest as ``sha256:…``. Admitting equal contents again changes nothing."""
    hashing = hashlib.sha256()
    with source.open("rb") as stream:
        while chunk := stream.read(1 << 20):
            hashing.update(chunk)
    path = _blob_path(hashing.hexdigest())
    if not path.is_file():
        _private(path.parent)
        staged = path.with_name(f".{path.name}.{os.getpid()}")
        try:
            shutil.copyfile(source, staged)
            copied = hashlib.sha256()
            with staged.open("rb") as stream:
                while chunk := stream.read(1 << 20):
                    copied.update(chunk)
            if copied.digest() != hashing.digest():
                raise OSError(f"{source} changed while it was admitted")
            staged.chmod(0o400)
            staged.replace(path)
        finally:
            staged.unlink(missing_ok=True)
    return f"sha256:{path.name}"


def core_version() -> str:
    return metadata.version(CORE)


def installed(store: Store) -> tuple[Package, ...]:
    """Every expert package this environment contributes, put into ``store``."""
    references = dict(discover(store).items())
    found = []
    for entry in sorted(metadata.entry_points(group=GROUP), key=lambda entry: entry.name):
        distribution = entry.dist
        found.append(Package(entry.name, None if distribution is None else distribution.name,
                             None if distribution is None else distribution.version,
                             references[entry.name]))
    return tuple(found)


def differences(lock: Lock, current: Sequence[Package], core: str) -> list[str]:
    """Why the environment cannot run ``lock``; empty when it can.

    Packages the environment has beyond the lock are not differences: the
    agent uses only what its lock names.
    """
    found = [] if lock.core == core else [f"core {CORE} is {core}, the lock needs {lock.core}"]
    present = {package.name: package for package in current}
    for wanted in lock.packages:
        have = present.get(wanted.name)
        if have is None:
            found.append(f"package {wanted.name} ({wanted.distribution} {wanted.version}) "
                         "is not installed")
        elif (have.distribution, have.version) != (wanted.distribution, wanted.version):
            found.append(f"package {wanted.name} is {have.distribution} {have.version}, "
                         f"the lock needs {wanted.distribution} {wanted.version}")
        elif have.ref != wanted.ref:
            found.append(f"package {wanted.name} gives {have.ref}, the lock needs {wanted.ref}")
    return found


def _agent(root: Path, name: str) -> Path:
    if not _NAME.fullmatch(name):
        raise ValueError(f"{name!r} is not an agent name: use 1 to 64 lowercase letters, "
                         "digits, '.', '_' or '-', starting with a letter or digit")
    return root / "agents" / name


def _private(directory: Path) -> Path:
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    return directory


def _check(lock: Lock, root: Path) -> None:
    """Refuse a lock this environment cannot run, and keep its objects."""
    store = Store()
    found = differences(lock, installed(store), core_version())
    if found:
        raise ValueError("this environment does not match the lock:\n  " + "\n  ".join(found))
    store.save(_private(root / "store"))


def _register(root: Path, name: str, lock: Lock) -> Path:
    directory = _agent(root, name)
    if (directory / "agent.lock").exists():
        raise ValueError(f"agent {name} already exists")
    _private(directory)
    path = directory / "agent.lock"
    path.write_text(json.dumps(lock.data(), indent=2) + "\n")
    return path


def create(root: Path, name: str) -> Lock:
    """Make agent ``name`` from every package this environment contributes."""
    _agent(root, name)
    store = Store()
    lock = Lock(core_version(), installed(store))
    store.save(_private(root / "store"))
    _register(root, name, lock)
    return lock


def install(root: Path, lock_path: Path, name: str) -> Lock:
    """Register agent ``name`` from a lock made elsewhere."""
    _agent(root, name)
    lock = Lock.read(lock_path)
    _check(lock, root)
    _register(root, name, lock)
    return lock


def spawn(root: Path, name: str, command: Sequence[str]) -> int:
    """Run ``command`` as a new instance of agent ``name``.

    The instance gets a fresh state directory. The command is the host
    program; it finds its agent through ``ELISA_AGENT_NAME``,
    ``ELISA_AGENT_LOCK``, ``ELISA_AGENT_STORE`` and ``ELISA_AGENT_STATE``.
    """
    directory = _agent(root, name)
    lock_path = directory / "agent.lock"
    if not lock_path.exists():
        raise ValueError(f"agent {name} does not exist")
    _check(Lock.read(lock_path), root)
    instances = _private(directory / "instances")
    number = 1 + max((int(path.name) for path in instances.iterdir() if path.name.isdigit()),
                     default=0)
    state = instances / str(number)
    state.mkdir(mode=0o700)
    environment = dict(os.environ, ELISA_AGENT_NAME=name, ELISA_AGENT_LOCK=str(lock_path),
                       ELISA_AGENT_STORE=str(root / "store"), ELISA_AGENT_STATE=str(state))
    return subprocess.run(list(command), env=environment, check=False).returncode


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="elisa-agent", description="Manage named agents.")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("packages", help="list the expert packages this environment contributes")
    commands.add_parser("list", help="list the agents in the agent home")
    creating = commands.add_parser("create", help="make an agent from the installed packages")
    creating.add_argument("name")
    exporting = commands.add_parser("export", help="print an agent's lock")
    exporting.add_argument("name")
    installing = commands.add_parser("install", help="register an agent from a lock file")
    installing.add_argument("lock", type=Path)
    installing.add_argument("--name", required=True)
    spawning = commands.add_parser("spawn", help="run a host program as a new instance")
    spawning.add_argument("name")
    spawning.add_argument("host", nargs=argparse.REMAINDER, metavar="-- COMMAND ...")
    return parser


def _run(arguments: argparse.Namespace, root: Path) -> int:
    if arguments.command == "packages":
        for package in installed(Store()):
            print(f"{package.name}  {package.distribution} {package.version}  {package.ref}")
    elif arguments.command == "list":
        agents = root / "agents"
        for lock_path in sorted(agents.glob("*/agent.lock")) if agents.is_dir() else []:
            print(f"{lock_path.parent.name}  {len(Lock.read(lock_path).packages)} packages")
    elif arguments.command == "create":
        lock = create(root, arguments.name)
        print(f"created agent {arguments.name} with {len(lock.packages)} packages")
    elif arguments.command == "export":
        sys.stdout.write((_agent(root, arguments.name) / "agent.lock").read_text())
    elif arguments.command == "install":
        lock = install(root, arguments.lock, arguments.name)
        print(f"installed agent {arguments.name} with {len(lock.packages)} packages")
    else:
        host = arguments.host[1:] if arguments.host[:1] == ["--"] else arguments.host
        if not host:
            raise ValueError("spawn needs a host program: elisa-agent spawn NAME -- COMMAND ...")
        return spawn(root, arguments.name, host)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        return _run(arguments, home())
    except (OSError, RuntimeError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
