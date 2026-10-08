"""Input Analysis Module. SHIELD reverse DFS is the baseline strategy."""

from __future__ import annotations

from collections import Counter

from .models import CircuitGraph, RareTargets, SelectedInput, SelectedInputs


class ReverseDFSInputAnalyzer:
    method = "reverse_dfs"

    def __init__(self, minimum_target_impact: int = 1) -> None:
        if minimum_target_impact < 1:
            raise ValueError("minimum_target_impact must be at least 1")
        self._minimum_target_impact = minimum_target_impact

    def analyze(
        self,
        graph: CircuitGraph,
        rare_targets: RareTargets,
    ) -> SelectedInputs:
        primary_inputs = set(graph.primary_input_nodes)
        impact_counts: Counter[str] = Counter()
        for target in rare_targets.targets:
            if target.target_id not in graph.predecessors:
                continue
            reached_inputs: set[str] = set()
            visited: set[str] = set()
            stack = [target.target_id]
            while stack:
                node = stack.pop()
                if node in visited:
                    continue
                visited.add(node)
                if node in primary_inputs:
                    reached_inputs.add(node)
                    continue
                stack.extend(graph.predecessors.get(node, ()))
            impact_counts.update(reached_inputs)

        total_targets = max(len(rare_targets.targets), 1)
        order = {node: index for index, node in enumerate(graph.primary_input_nodes)}
        selected = [
            SelectedInput(node, count / total_targets, count)
            for node, count in impact_counts.items()
            if count >= self._minimum_target_impact
        ]
        selected.sort(key=lambda item: (-item.impacted_target_count, order[item.input_id]))
        return SelectedInputs(tuple(selected), self.method)
