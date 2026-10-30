"""Input Analysis Module with replaceable input-ranking strategies."""

from __future__ import annotations

from collections import Counter
from math import ceil
from typing import Callable

from .graph import distance, reachable_inputs
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


# Week 2 Task 3: En az bir rare target'a ulaşabilen primary input'lar tutulur.
def relevant_inputs(graph: CircuitGraph, rare_targets: RareTargets) -> set[str]:
    """P_R: union of primary inputs that can reach at least one rare target."""
    result: set[str] = set()
    for target in rare_targets.targets:
        result.update(reachable_inputs(graph, target.target_id))
    return result


def _normalize(raw: dict[str, float], candidates: set[str]) -> dict[str, float]:
    maximum = max((raw.get(node, 0.0) for node in candidates), default=0.0)
    if maximum == 0:
        return {node: 0.0 for node in candidates}
    return {node: raw.get(node, 0.0) / maximum for node in candidates}


def _shield_dfs_scores(
    graph: CircuitGraph, rare_targets: RareTargets, candidates: set[str]
) -> dict[str, float]:
    # Week 2 Task 3: Özgün SHIELD'in count > 1 filtresi korunur.
    legacy = ReverseDFSInputAnalyzer(minimum_target_impact=2).analyze(graph, rare_targets)
    counts = {item.input_id: item.impacted_target_count for item in legacy.inputs}
    return _normalize(counts, candidates)


def _reach_count_scores(
    graph: CircuitGraph, rare_targets: RareTargets, candidates: set[str]
) -> dict[str, float]:
    target_count = len(rare_targets.targets)
    if target_count == 0:
        return {node: 0.0 for node in candidates}
    counts = Counter(
        node
        for target in rare_targets.targets
        for node in reachable_inputs(graph, target.target_id)
    )
    return {node: counts[node] / target_count for node in candidates}


def _dist_weighted_scores(
    graph: CircuitGraph, rare_targets: RareTargets, candidates: set[str]
) -> dict[str, float]:
    raw: dict[str, float] = {}
    for node in candidates:
        score = 0.0
        for target in rare_targets.targets:
            path_length = distance(graph, node, target.target_id)
            if path_length is not None and path_length > 0:
                score += 1.0 / path_length
        raw[node] = score
    return _normalize(raw, candidates)


RankingStrategy = Callable[[CircuitGraph, RareTargets, set[str]], dict[str, float]]
# Week 2 Task 3: SHIELD reverse DFS baseline olarak korunur ve iki yöntemle karşılaştırılır.
RANKING_STRATEGIES: dict[str, RankingStrategy] = {
    "shield_dfs": _shield_dfs_scores,
    "reach_count": _reach_count_scores,
    "dist_weighted": _dist_weighted_scores,
}


class InputRanker:
    """Configured ranker with the teacher-defined three-input operation."""

    def __init__(self, method: str) -> None:
        if method not in RANKING_STRATEGIES:
            raise ValueError(f"unknown input ranking method: {method}")
        self.method = method

    def rank(
        self,
        graph: CircuitGraph,
        rare_targets: RareTargets,
        P_R: set[str],
    ) -> dict[str, float]:
        """Score only inputs in P_R using the configured strategy."""
        primary_inputs = set(graph.primary_input_nodes)
        if not P_R <= primary_inputs:
            raise ValueError("P_R must contain only primary inputs")
        return RANKING_STRATEGIES[self.method](graph, rare_targets, set(P_R))


def select_top_k(scores: dict[str, float], k: int) -> tuple[str, ...]:
    """Choose ceil(k% of P_R), breaking equal-score ties by input id."""
    if not 0 <= k <= 100:
        raise ValueError("k must be between 0 and 100")
    count = ceil(k / 100 * len(scores))
    ordered = sorted(scores, key=lambda node: (-scores[node], _input_sort_key(node)))
    return tuple(ordered[:count])


def _input_sort_key(node: str) -> tuple[int, int | str]:
    try:
        return (0, int(node))
    except ValueError:
        return (1, node)


def selected_inputs_from_scores(
    scores: dict[str, float], selected_ids: tuple[str, ...], method: str,
    graph: CircuitGraph, rare_targets: RareTargets,
) -> SelectedInputs:
    """Convert Task 3 scores into the shared SelectedInputs contract."""
    targets_by_input = Counter(
        node
        for target in rare_targets.targets
        for node in reachable_inputs(graph, target.target_id)
    )
    return SelectedInputs(
        tuple(SelectedInput(node, scores[node], targets_by_input[node]) for node in selected_ids),
        method,
    )
