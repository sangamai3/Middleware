"""
DAGParser — topological sort for flow step graphs.

Uses Kahn's algorithm.  Raises FlowValidationError on:
  - cycles
  - disconnected graphs (steps with no path to root)
  - unknown depends_on references
"""

from __future__ import annotations

from collections import defaultdict, deque

from ..connectors.base.errors import FlowValidationError
from ..models.flow import StepConfig


class DAGParser:
    def __init__(self, steps: list[StepConfig]) -> None:
        self._steps = {s.id: s for s in steps}

    def validate(self) -> None:
        """Raise FlowValidationError if the graph has issues."""
        self._check_unknown_deps()
        self._check_cycles()

    def topological_order(self) -> list[str]:
        """Return step IDs in a valid execution order (Kahn's algorithm)."""
        self._check_unknown_deps()

        in_degree: dict[str, int] = {sid: 0 for sid in self._steps}
        successors: dict[str, list[str]] = defaultdict(list)

        for sid, step in self._steps.items():
            for dep in step.depends_on:
                in_degree[sid] += 1
                successors[dep].append(sid)

        queue: deque[str] = deque(
            sid for sid, deg in in_degree.items() if deg == 0
        )
        order: list[str] = []

        while queue:
            node = queue.popleft()
            order.append(node)
            for succ in successors[node]:
                in_degree[succ] -= 1
                if in_degree[succ] == 0:
                    queue.append(succ)

        if len(order) != len(self._steps):
            cycle_members = [sid for sid, deg in in_degree.items() if deg > 0]
            raise FlowValidationError(
                f"Cycle detected in flow graph. Nodes in cycle: {cycle_members}"
            )

        return order

    def _check_unknown_deps(self) -> None:
        for sid, step in self._steps.items():
            for dep in step.depends_on:
                if dep not in self._steps:
                    raise FlowValidationError(
                        f"Step '{sid}' depends on unknown step '{dep}'"
                    )

    def _check_cycles(self) -> None:
        self.topological_order()

    def parallel_layers(self) -> list[list[str]]:
        """
        Return steps grouped into layers that can execute concurrently.

        All steps in a layer have no inter-dependencies; each layer depends
        only on steps in earlier layers.
        """
        order = self.topological_order()
        step_layer: dict[str, int] = {}

        for sid in order:
            deps = self._steps[sid].depends_on
            layer = max((step_layer[dep] for dep in deps), default=-1) + 1
            step_layer[sid] = layer

        max_layer = max(step_layer.values(), default=0)
        layers: list[list[str]] = [[] for _ in range(max_layer + 1)]
        for sid, layer in step_layer.items():
            layers[layer].append(sid)
        return layers
