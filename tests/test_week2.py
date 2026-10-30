import contextlib
import io
import json
import math
import unittest
from pathlib import Path

from shield.circuit import BenchCircuitReader
from shield.experiment import evaluate_input_selection
from shield.graph import CircuitGraphBuilder, distance, fanin_cone, fanout_cone, reachable_inputs
from shield.input_analysis import InputRanker, ReverseDFSInputAnalyzer, relevant_inputs, select_top_k, selected_inputs_from_scores
from shield.models import RareTarget, RareTargets
from shield.activity import ActivityAnalyzer
from shield.rarity import RareTargetSelector, jaccard
from shield.simulation import LogicSimulator
from shield.test_vectors import LegacyShieldTestVectorGenerator


C17 = Path(__file__).parents[1] / "datasets" / "c17.bench"
DATASETS = C17.parent


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

    def test_baseline_rare_counts_match_original_shield(self):
        # Week 2 Task 1: değerler özgün PSO_DFS.Parser rare_net çıktısından alındı.
        from DFS_bench import myfunc as original_shield_reverse_dfs
        expected = {"c1908": 104, "c2670": 78, "c3540": 257,
                    "c5315": 46, "c6288": 67, "c7552": 150}
        baseline = json.loads((DATASETS.parent / "config" / "week2.json").read_text())["baseline"]
        for name, original_count in expected.items():
            with self.subTest(circuit=name):
                circuit = BenchCircuitReader().read(DATASETS / f"{name}.bench")
                vectors = LegacyShieldTestVectorGenerator().generate(circuit, baseline["M"], baseline["seed"])
                activity = ActivityAnalyzer().analyze(LogicSimulator().simulate(circuit, vectors))
                targets = RareTargetSelector().select(activity, baseline["rarity_method"], baseline["threshold"])
                self.assertEqual(len(targets.targets), original_count)
                # Week 2 Task 3: rank skorunda kalan input'ları özgün DFS_bench ile karşılaştır.
                with contextlib.redirect_stdout(io.StringIO()):
                    original_indices = original_shield_reverse_dfs(
                        [int(target.target_id) for target in targets.targets],
                        str(DATASETS / f"{name}.bench"),
                    )
                original_ids = {circuit.primary_inputs[index] for index in original_indices}
                graph = CircuitGraphBuilder().build(circuit)
                scores = InputRanker("shield_dfs").rank(graph, targets, relevant_inputs(graph, targets))
                self.assertEqual({node for node, score in scores.items() if score > 0}, original_ids)


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
        # Week 2 Task 3: özgün SHIELD yalnızca birden çok hedefe ulaşan input'u tutar.
        shield = InputRanker("shield_dfs").rank(self.graph, self.targets, self.P_R)
        self.assertEqual({node for node, score in shield.items() if score > 0}, {"3"})
        self.assertEqual(set(ReverseDFSInputAnalyzer(2).analyze(self.graph, self.targets).input_ids), {"3"})
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
        selected = selected_inputs_from_scores(scores, select_top_k(scores, 25), "reach_count", self.graph, self.targets)
        self.assertEqual(selected.input_ids, ("3",))
        self.assertEqual(selected.inputs[0].importance_score, 1.0)

    def test_task4_c17_metrics_and_monotonicity(self):
        scores = InputRanker("reach_count").rank(self.graph, self.targets, self.P_R)
        metrics = [
            evaluate_input_selection("c17", self.graph, self.targets, "reach_count", k, scores, 0.0)[0]
            for k in (25, 50, 100)
        ]
        tp = [item.TP_k for item in metrics]
        dr = [item.DR_k for item in metrics]
        self.assertEqual(dr[0], 0.8)
        self.assertEqual(tp[0], 1.0)
        self.assertEqual(tp[-1], 1.0)
        self.assertEqual(dr[-1], 1 - len(self.P_R) / len(self.graph.primary_input_nodes))
        self.assertEqual(tp, sorted(tp))
        self.assertEqual(dr, sorted(dr, reverse=True))


if __name__ == "__main__":
    unittest.main()
