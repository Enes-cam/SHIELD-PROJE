"""Rare Target Module with replaceable rarity strategies."""

from __future__ import annotations

import math

from .models import ActivityInfo, RareTarget, RareTargets


# Week 2 Task 1: Farklı çalıştırmalardaki rare-target kümeleri Jaccard ile karşılaştırılır.
def jaccard(a: set[str], b: set[str]) -> float:
    """Return set similarity; two empty sets are undefined for this experiment."""
    union = a | b
    return math.nan if not union else len(a & b) / len(union)


class RareTargetSelector:
    METHODS = {"switching_activity", "transition_probability", "signal_probability"}

    def select(
        self,
        activity: ActivityInfo,
        method: str,
        threshold: float,
    ) -> RareTargets:
        if method not in self.METHODS:
            raise ValueError(f"unknown rarity method {method!r}; choose from {sorted(self.METHODS)}")
        selected = []
        for node in activity.target_eligible_nodes:
            if node not in activity.nodes:
                continue
            item = activity.nodes[node]
            score = {
                "switching_activity": item.switching_activity,
                "transition_probability": item.transition_probability,
                "signal_probability": item.rare_signal_probability,
            }[method]
            if score < threshold:
                target_value = item.rare_value if method == "signal_probability" else 1
                selected.append(RareTarget(node, score, method, target_value))
        selected.sort(key=lambda target: (target.rarity_score, target.target_id))
        return RareTargets(tuple(selected))


def prepared_rare_targets(targets: list[tuple[str, float, int]], method: str = "external") -> RareTargets:
    return RareTargets(tuple(RareTarget(node, score, method, value) for node, score, value in targets), source="external")
