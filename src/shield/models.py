"""Shared, format-independent data contracts used between SHIELD modules."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping, Sequence


Bit = int
TestVector = tuple[Bit, ...]


@dataclass(frozen=True)
class Gate:
    gate_id: str
    gate_type: str
    input_nets: tuple[str, ...]
    output_net: str


@dataclass(frozen=True)
class CircuitIR:
    name: str
    primary_inputs: tuple[str, ...]
    primary_outputs: tuple[str, ...]
    gates: tuple[Gate, ...]
    nets: tuple[str, ...]
    connections: tuple[tuple[str, str], ...]
    topological_gate_order: tuple[str, ...]

    @property
    def gate_by_id(self) -> dict[str, Gate]:
        return {gate.gate_id: gate for gate in self.gates}


@dataclass(frozen=True)
class TestVectorSet:
    primary_input_order: tuple[str, ...]
    test_vectors: tuple[TestVector, ...]
    source: str = "generated"
    seed: int | None = None


@dataclass(frozen=True)
class SimulationResults:
    primary_input_order: tuple[str, ...]
    test_vectors: tuple[TestVector, ...]
    net_values: tuple[Mapping[str, Bit], ...]
    target_eligible_nodes: tuple[str, ...]


@dataclass(frozen=True)
class NodeActivity:
    zero_count: int
    one_count: int
    transition_0_to_1: int
    transition_1_to_0: int
    sample_count: int

    @property
    def switching_activity(self) -> float:
        return (self.transition_0_to_1 + self.transition_1_to_0) / max(self.sample_count, 1)

    @property
    def transition_probability(self) -> float:
        return (self.transition_0_to_1 + self.transition_1_to_0) / max(self.sample_count - 1, 1)

    @property
    def rare_signal_probability(self) -> float:
        return min(self.zero_count, self.one_count) / max(self.sample_count, 1)

    @property
    def rare_value(self) -> Bit:
        return 0 if self.zero_count < self.one_count else 1


@dataclass(frozen=True)
class ActivityInfo:
    nodes: Mapping[str, NodeActivity]
    target_eligible_nodes: tuple[str, ...]


@dataclass(frozen=True)
class RareTarget:
    target_id: str
    rarity_score: float
    rarity_method: str
    target_value: Bit = 1


@dataclass(frozen=True)
class RareTargets:
    targets: tuple[RareTarget, ...]
    source: str = "computed"


@dataclass(frozen=True)
class CircuitGraph:
    nodes: tuple[str, ...]
    directed_edges: tuple[tuple[str, str], ...]
    primary_input_nodes: tuple[str, ...]
    primary_output_nodes: tuple[str, ...]
    predecessors: Mapping[str, tuple[str, ...]]
    successors: Mapping[str, tuple[str, ...]]


@dataclass(frozen=True)
class SelectedInput:
    input_id: str
    importance_score: float
    impacted_target_count: int


@dataclass(frozen=True)
class SelectedInputs:
    inputs: tuple[SelectedInput, ...]
    method: str

    @property
    def input_ids(self) -> tuple[str, ...]:
        return tuple(item.input_id for item in self.inputs)


@dataclass(frozen=True)
class Candidate:
    candidate_id: str
    test_vector: TestVector


@dataclass(frozen=True)
class CandidatePool:
    primary_input_order: tuple[str, ...]
    candidates: tuple[Candidate, ...]
    method: str


@dataclass(frozen=True)
class CoverageMatrix:
    target_order: tuple[str, ...]
    coverage_by_candidate: Mapping[str, tuple[Bit, ...]]

    def covered_targets(self, candidate_id: str) -> set[str]:
        row = self.coverage_by_candidate[candidate_id]
        return {target for target, covered in zip(self.target_order, row) if covered}


@dataclass(frozen=True)
class ProblemDefinition:
    problem_type: str = "minimum_test_set"
    test_budget: int | None = None
    objective: str = "maximize_coverage"
    constraints: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SelectedTestSet:
    selected_test_ids: tuple[str, ...]
    selected_test_vectors: tuple[TestVector, ...]
    test_set_size: int
    coverage: float
    objective_value: float


@dataclass(frozen=True)
class HTGroundTruth:
    trigger_nets: tuple[str, ...]
    trigger_values: tuple[Bit, ...]
    payload_location: str | None = None
    payload_type: str | None = None
    affected_output: str | None = None


@dataclass(frozen=True)
class HTCircuit:
    circuit: CircuitIR
    golden_circuit: CircuitIR | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ValidationResults:
    trigger_activated: bool
    trigger_activation_count: int
    payload_activated: bool | None
    payload_observed_at_output: bool | None
    detected: bool


@dataclass(frozen=True)
class ExperimentConfiguration:
    circuit: str
    sample_size: int = 1000
    seed: int = 42
    test_vector_method: str = "shield_legacy_random"
    rarity_method: str = "switching_activity"
    threshold: float = 0.1
    graph_method: str = "directed_net_graph"
    input_analysis_method: str = "reverse_dfs"
    minimum_target_impact: int = 2
    candidate_generation_method: str = "random_selected_inputs"
    candidate_count: int = 100
    optimization_method: str = "greedy"
    problem_type: str = "minimum_test_set"
    test_budget: int | None = None
    validation_enabled: bool = False
    ht_circuit: str | None = None
    ht_golden_circuit: str | None = None
    ht_ground_truth: HTGroundTruth | None = None
    optimization_parameters: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ExperimentResults:
    circuit_name: str
    configuration: ExperimentConfiguration
    rare_target_count: int
    selected_input_count: int
    candidate_count: int
    selected_test_count: int
    coverage: float
    runtime_seconds: float
    selected_test_ids: tuple[str, ...]
    optimization_result: Mapping[str, Any]
    validation_result: ValidationResults | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
