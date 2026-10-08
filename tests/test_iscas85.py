import unittest
from pathlib import Path

from shield.activity import ActivityAnalyzer
from shield.circuit import BenchCircuitReader
from shield.graph import CircuitGraphBuilder
from shield.input_analysis import ReverseDFSInputAnalyzer
from shield.rarity import RareTargetSelector
from shield.simulation import LogicSimulator
from shield.test_vectors import LegacyShieldTestVectorGenerator


DATASETS = Path(__file__).parents[1] / "datasets"
EXPECTED_INPUTS = {
    "c880": 60,
    "c1355": 41,
    "c1908": 33,
    "c2670": 233,
    "c3540": 50,
    "c5315": 178,
    "c6288": 32,
    "c7552": 207,
}


class Iscas85Tests(unittest.TestCase):
    def test_benchmarks_parse_with_expected_input_counts(self):
        for name, input_count in EXPECTED_INPUTS.items():
            with self.subTest(circuit=name):
                circuit = BenchCircuitReader().read(DATASETS / f"{name}.bench")
                self.assertEqual(len(circuit.primary_inputs), input_count)
                self.assertEqual(len(circuit.topological_gate_order), len(circuit.gates))
                self.assertLessEqual(set(circuit.primary_outputs), set(circuit.nets))

    def test_c880_legacy_characterization_regression(self):
        circuit = BenchCircuitReader().read(DATASETS / "c880.bench")
        vectors = LegacyShieldTestVectorGenerator().generate(circuit, 1000, 42)
        simulation = LogicSimulator().simulate(circuit, vectors)
        activity = ActivityAnalyzer().analyze(simulation)
        targets = RareTargetSelector().select(activity, "switching_activity", 0.1)
        graph = CircuitGraphBuilder().build(circuit)
        selected = ReverseDFSInputAnalyzer(minimum_target_impact=2).analyze(graph, targets)
        self.assertEqual(len(targets.targets), 48)
        self.assertEqual(len(selected.inputs), 23)


if __name__ == "__main__":
    unittest.main()
