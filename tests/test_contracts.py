import inspect
import ast
import unittest
from pathlib import Path

from shield.activity import ActivityAnalyzer
from shield.candidate_generation import RandomSelectedInputCandidateGenerator
from shield.circuit import BenchCircuitReader
from shield.coverage import CoverageAnalyzer
from shield.graph import CircuitGraphBuilder
from shield.input_analysis import ReverseDFSInputAnalyzer
from shield.experiment import ExperimentRunner
from shield.optimization import GreedyCoverageOptimizer
from shield.rarity import RareTargetSelector
from shield.simulation import LogicSimulator
from shield.test_vectors import RandomTestVectorGenerator
from shield.validation import HTValidator


def public_parameters(callable_object):
    return tuple(
        name for name in inspect.signature(callable_object).parameters
        if name != "self"
    )


class ModuleContractTests(unittest.TestCase):
    def test_teacher_defined_operation_inputs_are_exact(self):
        expected = {
            BenchCircuitReader.read: ("path",),
            RandomTestVectorGenerator.generate: ("circuit", "sample_size", "seed"),
            LogicSimulator.simulate: ("circuit", "vectors"),
            ActivityAnalyzer.analyze: ("results",),
            RareTargetSelector.select: ("activity", "method", "threshold"),
            CircuitGraphBuilder.build: ("circuit",),
            ReverseDFSInputAnalyzer.analyze: ("graph", "rare_targets"),
            RandomSelectedInputCandidateGenerator.generate: ("circuit", "selected_inputs"),
            CoverageAnalyzer.analyze: ("circuit", "pool", "targets"),
            GreedyCoverageOptimizer.optimize: ("pool", "matrix", "problem"),
            HTValidator.validate: ("selected", "ht_circuit", "ground_truth"),
            ExperimentRunner.run: ("config",),
        }
        for operation, parameters in expected.items():
            with self.subTest(operation=operation.__qualname__):
                self.assertEqual(public_parameters(operation), parameters)

    def test_algorithm_modules_do_not_import_each_other(self):
        source_root = Path(__file__).parents[1] / "src" / "shield"
        modules = (
            "circuit.py", "test_vectors.py", "simulation.py", "activity.py",
            "rarity.py", "graph.py", "input_analysis.py",
            "candidate_generation.py", "coverage.py", "optimization.py",
            "validation.py",
        )
        allowed_shared_modules = {"models", "ports"}
        for filename in modules:
            tree = ast.parse((source_root / filename).read_text(encoding="utf-8"))
            internal_imports = {
                node.module.lstrip(".").split(".", 1)[0]
                for node in ast.walk(tree)
                if isinstance(node, ast.ImportFrom) and node.level > 0 and node.module
            }
            with self.subTest(module=filename):
                self.assertLessEqual(internal_imports, allowed_shared_modules)


if __name__ == "__main__":
    unittest.main()
