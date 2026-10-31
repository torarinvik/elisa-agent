"""Module registry: installation, replacement, and removal."""

from __future__ import annotations

from typing import Any, Protocol

from nca.abi import Manifest


class Module(Protocol):
    manifest: Manifest

    def invoke(self, *inputs: Any) -> Any: ...


class Registry:
    """Ordered set of installed modules, keyed by module id.

    Installation order is the planner's tie-break priority, so replacing a
    module keeps its position.
    """

    def __init__(self) -> None:
        self._modules: dict[str, Module] = {}

    def install(self, module: Module) -> None:
        module_id = module.manifest.module_id
        if module_id in self._modules:
            raise ValueError(f"module already installed: {module_id}")
        self._modules[module_id] = module

    def replace(self, module: Module) -> Module:
        module_id = module.manifest.module_id
        old = self._modules[module_id]
        if old.manifest.contract != module.manifest.contract:
            raise ValueError(f"contract mismatch replacing {module_id}")
        self._modules[module_id] = module
        return old

    def uninstall(self, module_id: str) -> Module:
        return self._modules.pop(module_id)

    def modules(self) -> list[Module]:
        return list(self._modules.values())
