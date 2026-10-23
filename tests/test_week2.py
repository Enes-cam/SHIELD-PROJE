import math
import unittest
from pathlib import Path

from shield.circuit import BenchCircuitReader
from shield.graph import CircuitGraphBuilder, distance, fanin_cone, fanout_cone, reachable_inputs
from shield.input_analysis import InputRanker, relevant_inputs, select_top_k
from shield.models import RareTarget, RareTargets
from shield.activity import ActivityAnalyzer
from shield.rarity import RareTargetSelector
from shield.simulation import LogicSimulator
from shield.test_vectors import LegacyShieldTestVectorGenerator
from shield.week2 import jaccard


C17 = Path(__file__).parents[1] / "datasets" / "c17.bench"


def c17_targets():
    return RareTargets((
        RareTarget("10", 0.01, "external"),
        RareTarget("19", 0.01, "external"),
    ), source="external")


class Task1JaccardTests(unittest.TestCase):
    def test_examples_and_empty_policy(self):
        self.assertAlmostEqual(jaccard({1, 2, 3, 4}, {2, 3, 4, 5}), 0.6)
        self.assertEqual(jaccard({1, 2}, {1, 2}), 1.0)
        self.assertEqual(jaccard({1}, {2}), 0.0)
        self.assertTrue(math.isnan(jaccard(set(), set())))

    def test_same_M_and_seed_produce_identical_rare_sets(self):
        circuit = BenchCircuitReader().read(C17)
        generator = LegacyShieldTestVectorGenerator()
        selector = RareTargetSelector()
        sets = []
        for _ in range(2):
            vectors = generator.generate(circuit, 100, 42)
            activity = ActivityAnalyzer().analyze(LogicSimulator().simulate(circuit, vectors))
            targets = selector.select(activity, "switching_activity", 0.5)
            sets.append({target.target_id for target in targets.targets})
        self.assertEqual(jaccard(sets[0], sets[1]), 1.0)


class Task2GraphTests(unittest.TestCase):
    def setUp(self):
        self.circuit = BenchCircuitReader().read(C17)
        self.graph = CircuitGraphBuilder().build(self.circuit)

    def test_teacher_c17_examples(self):
        self.assertEqual(reachable_inputs(self.graph, "10"), {"1", "3"})
        self.assertEqual(reachable_inputs(self.graph, "19"), {"3", "6", "7"})
        self.assertEqual(fanout_cone(self.graph, "2"), {"16", "22", "23"})
        self.assertEqual(distance(self.graph, "3", "19"), 2)

    def test_cone_duality_and_unreachable_distance(self):
        for source in self.graph.nodes:
            for target in self.graph.nodes:
                self.assertEqual(
                    source in fanin_cone(self.graph, target),
                    target in fanout_cone(self.graph, source),
                )
        self.assertIsNone(distance(self.graph, "2", "19"))


class Task3And4InputSelectionTests(unittest.TestCase):
    def setUp(self):
        circuit = BenchCircuitReader().read(C17)
        self.graph = CircuitGraphBuilder().build(circuit)
        self.targets = c17_targets()
        self.P_R = relevant_inputs(self.graph, self.targets)

    def test_relevant_inputs_and_scores(self):
        self.assertEqual(self.P_R, {"1", "3", "6", "7"})
        reach = InputRanker("reach_count").rank(self.graph, self.targets, self.P_R)
        self.assertEqual(reach, {"1": 0.5, "3": 1.0, "6": 0.5, "7": 0.5})
        weighted = InputRanker("dist_weighted").rank(self.graph, self.targets, self.P_R)
        self.assertAlmostEqual(weighted["3"], 1.0)
        self.assertAlmostEqual(weighted["1"], 2 / 3)
        self.assertAlmostEqual(weighted["7"], 2 / 3)
        self.assertAlmostEqual(weighted["6"], 1 / 3)

    def test_top_k_is_deterministic(self):
        scores = InputRanker("reach_count").rank(self.graph, self.targets, self.P_R)
        self.assertEqual(select_top_k(scores, 25), ("3",))
        self.assertEqual(select_top_k(scores, 50), ("3", "1"))
        self.assertEqual(select_top_k(scores, 100), ("3", "1", "6", "7"))
        self.assertEqual(select_top_k(scores, 50), select_top_k(scores, 50))

    def test_task4_c17_metrics_and_monotonicity(self):
        scores = InputRanker("reach_count").rank(self.graph, self.targets, self.P_R)
        selections = [select_top_k(scores, k) for k in (25, 50, 100)]
        tp = []
        dr = []
        for selected in selections:
            covered = {
                target.target_id
                for target in self.targets.targets
                if any(distance(self.graph, node, target.target_id) is not None for node in selected)
            }
            tp.append(len(covered) / len(self.targets.targets))
            dr.append(1 - len(selected) / len(self.graph.primary_input_nodes))
        self.assertEqual(dr[0], 0.8)
        self.assertEqual(tp[0], 1.0)
        self.assertEqual(tp[-1], 1.0)
        self.assertEqual(dr[-1], 1 - len(self.P_R) / len(self.graph.primary_input_nodes))
        self.assertEqual(tp, sorted(tp))
        self.assertEqual(dr, sorted(dr, reverse=True))


if __name__ == "__main__":
    unittest.main()
