"""Validation Module for trigger activation and basic payload observability checks."""

from __future__ import annotations

from .models import HTCircuit, HTGroundTruth, SelectedTestSet, TestVectorSet, ValidationResults
from .ports import SimulationPort


class HTValidator:
    def __init__(self, simulator: SimulationPort) -> None:
        self._simulator = simulator

    def validate(
        self,
        selected: SelectedTestSet,
        ht_circuit: HTCircuit,
        ground_truth: HTGroundTruth,
    ) -> ValidationResults:
        circuit = ht_circuit.circuit
        vectors = TestVectorSet(circuit.primary_inputs, selected.selected_test_vectors, source="selected_test_set")
        ht_results = self._simulator.simulate(circuit, vectors)
        activated_rows = [
            row for row in ht_results.net_values
            if all(row[net] == value for net, value in zip(ground_truth.trigger_nets, ground_truth.trigger_values))
        ]
        trigger_activated = bool(activated_rows)
        payload_activated = None
        if ground_truth.payload_location:
            payload_activated = any(
                ground_truth.payload_location in row for row in activated_rows
            ) and trigger_activated
        observed = None
        if ht_circuit.golden_circuit is not None and ground_truth.affected_output:
            golden_results = self._simulator.simulate(ht_circuit.golden_circuit, vectors)
            observed = any(
                ht_row[ground_truth.affected_output] != golden_row[ground_truth.affected_output]
                for ht_row, golden_row in zip(ht_results.net_values, golden_results.net_values)
            )
        return ValidationResults(
            trigger_activated=trigger_activated,
            trigger_activation_count=len(activated_rows),
            payload_activated=payload_activated,
            payload_observed_at_output=observed,
            detected=bool(trigger_activated and (observed is True if ground_truth.affected_output else True)),
        )
