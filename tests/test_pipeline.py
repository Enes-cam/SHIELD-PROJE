import unittest
from pathlib import Path

from shield.activity import ActivityAnalyzer
from shield.candidate_generation import RandomSelectedInputCandidateGenerator
from shield.circuit import BenchCircuitReader
from shield.coverage import CoverageAnalyzer
from shield.experiment import ExperimentRunner
from shield.graph import CircuitGraphBuilder
from shield.input_analysis import ReverseDFSInputAnalyzer
from shield.models import ExperimentConfiguration, RareTarget, RareTargets, TestVectorSet
from shield.simulation import LogicSimulator
from shield.test_vectors import LegacyShieldTestVectorGenerator, RandomTestVectorGenerator


FIXTURE = Path(__file__).parent / "fixtures" / "tiny.bench"


class PipelineTests(unittest.TestCase):
    def test_circuit_reader_creates_format_independent_ir(self):
        circuit = BenchCircuitReader().read(FIXTURE)
        self.assertEqual(circuit.primary_inputs, ("A", "B", "C"))
        self.assertEqual(circuit.primary_outputs, ("Z",))
        self.assertEqual(circuit.connections, (("A", "N1"), ("B", "N1"), ("B", "N2"), ("C", "N2"), ("N1", "Z"), ("N2", "Z")))
        self.assertEqual(circuit.topological_gate_order, ("N1", "N2", "Z"))
        self.assertEqual(circuit.gate_by_id["N1"].gate_type, "AND")

    def test_logic_simulation_accepts_prepared_vectors(self):
        circuit = BenchCircuitReader().read(FIXTURE)
        vectors = TestVectorSet(circuit.primary_inputs, ((0, 0, 0), (1, 1, 0)), source="test")
        results = LogicSimulator().simulate(circuit, vectors)
        self.assertEqual(results.net_values[0]["Z"], 0)
        self.assertEqual(results.net_values[1]["Z"], 1)

    def test_activity_counts_levels_and_transitions(self):
        circuit = BenchCircuitReader().read(FIXTURE)
        vectors = TestVectorSet(circuit.primary_inputs, ((0, 0, 0), (1, 1, 0), (1, 1, 0)), source="test")
        results = LogicSimulator().simulate(circuit, vectors)
        activity = ActivityAnalyzer().analyze(results)
        self.assertEqual(activity.nodes["N1"].zero_count, 1)
        self.assertEqual(activity.nodes["N1"].one_count, 2)
        self.assertEqual(activity.nodes["N1"].transition_0_to_1, 1)
        self.assertEqual(activity.nodes["N1"].transition_1_to_0, 0)

    def test_reverse_dfs_baseline_returns_influencing_inputs(self):
        circuit = BenchCircuitReader().read(FIXTURE)
        graph = CircuitGraphBuilder().build(circuit)
        targets = RareTargets((RareTarget("N1", 0.01, "external", 1),), source="external")
        selected = ReverseDFSInputAnalyzer().analyze(graph, targets)
        self.assertEqual(selected.input_ids, ("A", "B"))

    def test_prepared_targets_bypass_rarity_stage_components(self):
        circuit = BenchCircuitReader().read(FIXTURE)
        targets = RareTargets((RareTarget("Z", 0.01, "external", 1),), source="external")
        graph = CircuitGraphBuilder().build(circuit)
        selected = ReverseDFSInputAnalyzer().analyze(graph, targets)
        pool = RandomSelectedInputCandidateGenerator(8, seed=42).generate(circuit, selected)
        matrix = CoverageAnalyzer(LogicSimulator()).analyze(circuit, pool, targets)
        self.assertEqual(matrix.target_order, ("Z",))
        self.assertTrue(any(row == (1,) for row in matrix.coverage_by_candidate.values()))

    def test_random_vectors_are_reproducible(self):
        circuit = BenchCircuitReader().read(FIXTURE)
        generator = RandomTestVectorGenerator()
        self.assertEqual(generator.generate(circuit, 10, 42), generator.generate(circuit, 10, 42))

    def test_legacy_vector_generator_is_reproducible(self):
        circuit = BenchCircuitReader().read(FIXTURE)
        generator = LegacyShieldTestVectorGenerator()
        self.assertEqual(generator.generate(circuit, 10, 42), generator.generate(circuit, 10, 42))

    def test_end_to_end_experiment_is_reproducible_except_runtime(self):
        config = ExperimentConfiguration(
            circuit=str(FIXTURE), sample_size=100, seed=42, threshold=0.4,
            minimum_target_impact=1, candidate_count=8,
        )
        first = ExperimentRunner().run(config)
        second = ExperimentRunner().run(config)
        self.assertEqual(first.circuit_name, second.circuit_name)
        self.assertEqual(first.rare_target_count, second.rare_target_count)
        self.assertEqual(first.selected_test_ids, second.selected_test_ids)
        self.assertEqual(first.coverage, second.coverage)


if __name__ == "__main__":
    unittest.main()
