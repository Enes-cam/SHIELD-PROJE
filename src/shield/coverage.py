"""Coverage Module."""

from __future__ import annotations

from .models import CandidatePool, CircuitIR, CoverageMatrix, RareTargets, TestVectorSet
from .ports import SimulationPort


class CoverageAnalyzer:
    def __init__(self, simulator: SimulationPort) -> None:
        self._simulator = simulator

    def analyze(self, circuit: CircuitIR, pool: CandidatePool, targets: RareTargets) -> CoverageMatrix:
        vectors = TestVectorSet(pool.primary_input_order, tuple(c.test_vector for c in pool.candidates), source=pool.method)
        results = self._simulator.simulate(circuit, vectors)
        target_order = tuple(target.target_id for target in targets.targets)
        desired_values = {target.target_id: target.target_value for target in targets.targets}
        rows = {}
        for candidate, net_values in zip(pool.candidates, results.net_values):
            rows[candidate.candidate_id] = tuple(
                int(net_values[target_id] == desired_values[target_id]) for target_id in target_order
            )
        return CoverageMatrix(target_order, rows)
