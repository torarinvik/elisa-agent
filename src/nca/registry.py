"""Module registry: installation, replacement, and removal."""

from __future__ import annotations

from nca.abi import Module
from nca.index import ProducerIndex


class Registry:
    """Ordered set of installed modules, keyed by module id.

    Installation order is the planner's tie-break priority, so replacing a
    module keeps its position. ``index`` is the planner's index of the
    installed modules, kept up to date: installation appends to it and keeps
    every cached planning result (THEORY §12, Theorem 12.18); uninstalling
    rebuilds it.
    """

    def __init__(self) -> None:
        self._modules: dict[str, Module] = {}
        self.index = ProducerIndex()

    def install(self, module: Module) -> None:
        module_id = module.manifest.module_id
        if module_id in self._modules:
            raise ValueError(f"module already installed: {module_id}")
        self._modules[module_id] = module
        self.index.append(module)

    def replace(self, module: Module) -> Module:
        module_id = module.manifest.module_id
        old = self._modules[module_id]
        if old.manifest.contract != module.manifest.contract:
            raise ValueError(f"contract mismatch replacing {module_id}")
        self.index.replace(list(self._modules).index(module_id), module)
        self._modules[module_id] = module
        return old

    def uninstall(self, module_id: str) -> Module:
        module = self._modules.pop(module_id)
        self.index = ProducerIndex(list(self._modules.values()))
        return module

    def modules(self) -> list[Module]:
        return list(self._modules.values())
