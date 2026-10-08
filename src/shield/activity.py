"""Activity Analysis Module."""

from __future__ import annotations

from .models import ActivityInfo, NodeActivity, SimulationResults


class ActivityAnalyzer:
    def analyze(self, results: SimulationResults) -> ActivityInfo:
        if not results.net_values:
            return ActivityInfo({}, results.target_eligible_nodes)
        node_order = tuple(results.net_values[0].keys())
        activity = {}
        for node in node_order:
            values = [row[node] for row in results.net_values]
            transitions_01 = sum(a == 0 and b == 1 for a, b in zip(values, values[1:]))
            transitions_10 = sum(a == 1 and b == 0 for a, b in zip(values, values[1:]))
            activity[node] = NodeActivity(
                zero_count=values.count(0),
                one_count=values.count(1),
                transition_0_to_1=transitions_01,
                transition_1_to_0=transitions_10,
                sample_count=len(values),
            )
        return ActivityInfo(activity, results.target_eligible_nodes)
