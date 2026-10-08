import unittest
from pathlib import Path

from shield.circuit import BenchCircuitReader
from shield.experiment import ExperimentRunner
from shield.models import (
    Candidate, CandidatePool, CoverageMatrix, HTCircuit, HTGroundTruth,
    ExperimentConfiguration, ProblemDefinition, SelectedTestSet,
)
from shield.optimization import DiscretePSOOptimizer, GreedyCoverageOptimizer
from shield.simulation import LogicSimulator
from shield.validation import HTValidator


FIXTURES = Path(__file__).parent / "fixtures"


class OptimizationAndValidationTests(unittest.TestCase):
    def setUp(self):
        self.pool = CandidatePool(
            ("A", "B"),
            (
                Candidate("T1", (0, 0)),
                Candidate("T2", (0, 1)),
                Candidate("T3", (1, 0)),
                Candidate("T4", (1, 1)),
            ),
            "test",
        )
        self.matrix = CoverageMatrix(
            ("N1", "N2", "N3"),
            {
                "T1": (1, 0, 0),
                "T2": (0, 1, 0),
                "T3": (0, 0, 1),
                "T4": (1, 1, 1),
            },
        )

    def test_greedy_supports_both_problem_types_and_constraints(self):
        optimizer = GreedyCoverageOptimizer()
        minimum = optimizer.optimize(
            self.pool, self.matrix, ProblemDefinition("minimum_test_set")
        )
        self.assertEqual(minimum.selected_test_ids, ("T4",))
        fixed = optimizer.optimize(
            self.pool,
            self.matrix,
            ProblemDefinition(
                "maximum_coverage_fixed_budget", 2,
                constraints={"forbidden_candidate_ids": ("T4",)},
            ),
        )
        self.assertEqual(fixed.test_set_size, 2)
        self.assertAlmostEqual(fixed.coverage, 2 / 3)

    def test_pso_uses_candidate_pool_and_coverage_contract(self):
        result = DiscretePSOOptimizer(seed=42, particles=20, iterations=30).optimize(
            self.pool,
            self.matrix,
            ProblemDefinition("minimum_test_set", constraints={"max_test_set_size": 3}),
        )
        self.assertEqual(result.coverage, 1.0)
        self.assertEqual(result.test_set_size, 1)

    def test_validation_checks_trigger_and_output_observability(self):
        reader = BenchCircuitReader()
        golden = reader.read(FIXTURES / "golden_ht.bench")
        trojan = reader.read(FIXTURES / "trojan_ht.bench")
        selected = SelectedTestSet(("T1",), ((1, 1),), 1, 1.0, 1.0)
        truth = HTGroundTruth(
            trigger_nets=("TRIGGER",),
            trigger_values=(1,),
            payload_location="TRIGGER",
            payload_type="XOR output corruption",
            affected_output="Z",
        )
        result = HTValidator(LogicSimulator()).validate(
            selected, HTCircuit(trojan, golden), truth
        )
        self.assertTrue(result.trigger_activated)
        self.assertTrue(result.payload_activated)
        self.assertTrue(result.payload_observed_at_output)
        self.assertTrue(result.detected)

    def test_experiment_runs_configured_validation_pipeline(self):
        truth = HTGroundTruth(
            trigger_nets=("TRIGGER",), trigger_values=(1,),
            payload_location="TRIGGER", affected_output="Z",
        )
        config = ExperimentConfiguration(
            circuit=str(FIXTURES / "golden_ht.bench"),
            sample_size=20,
            seed=42,
            threshold=1.1,
            minimum_target_impact=1,
            candidate_generation_method="random_full_inputs",
            candidate_count=4,
            optimization_method="greedy",
            validation_enabled=True,
            ht_circuit=str(FIXTURES / "trojan_ht.bench"),
            ht_golden_circuit=str(FIXTURES / "golden_ht.bench"),
            ht_ground_truth=truth,
        )
        result = ExperimentRunner().run(config)
        self.assertIsNotNone(result.validation_result)
        self.assertTrue(result.validation_result.trigger_activated)
        self.assertTrue(result.validation_result.payload_observed_at_output)
        self.assertEqual(result.optimization_result["method"], "greedy")


if __name__ == "__main__":
    unittest.main()
