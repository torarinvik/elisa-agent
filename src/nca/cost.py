"""Measured costs of experts.

Manifests declare the cost of one invocation in any unit the planner
compares consistently; floating-point operations are the unit used for
networks here.
"""

from __future__ import annotations

from dataclasses import replace

import torch
from torch import nn

from nca.abi import Module


def network_flops(network: nn.Module, shape: tuple[int, ...]) -> int:
    """Floating-point operations of one forward pass (multiply-adds count as two)."""
    total = 0

    def count(module: nn.Module, inputs: tuple[torch.Tensor, ...], output: torch.Tensor) -> None:
        nonlocal total
        if isinstance(module, nn.Conv2d):
            kh, kw = module.kernel_size
            total += 2 * output.numel() * module.in_channels // module.groups * kh * kw
        elif isinstance(module, nn.Linear):
            total += 2 * module.in_features * module.out_features

    hooks = [m.register_forward_hook(count) for m in network.modules()]
    with torch.no_grad():
        network(torch.zeros(1, *shape))
    for hook in hooks:
        hook.remove()
    return total


def costed(module: Module, cost: float, module_id: str | None = None) -> Module:
    """Declare ``cost`` (and optionally a new id) on ``module``'s manifest."""
    module.manifest = replace(module.manifest, cost=cost,
                              module_id=module_id or module.manifest.module_id)
    return module
