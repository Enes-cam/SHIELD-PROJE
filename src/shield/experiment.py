"""Experiment Module: orchestrates modules without exposing their internals."""

from __future__ import annotations

from pathlib import Path
from time import perf_counter

from .activity import ActivityAnalyzer
from .candidate_generation import RandomFullInputCandidateGenerator, RandomSelectedInputCandidateGenerator
from .circuit import BenchCircuitReader
from .coverage import CoverageAnalyzer
from .graph import CircuitGraphBuilder
from .input_analysis import ReverseDFSInputAnalyzer
from .models import ExperimentConfiguration, ExperimentResults, HTCircuit, ProblemDefinition
from .optimization import DiscretePSOOptimizer, GreedyCoverageOptimizer
from .rarity import RareTargetSelector
from .simulation import LogicSimulator
from .test_vectors import LegacyShieldTestVectorGenerator, RandomTestVectorGenerator
from .validation import HTValidator


class ExperimentRunner:
    def __init__(self) -> None:
        self.circuit_reader = BenchCircuitReader()
        self.vector_generator = RandomTestVectorGenerator()
        self.legacy_vector_generator = LegacyShieldTestVectorGenerator()
        self.simulator = LogicSimulator()
        self.activity_analyzer = ActivityAnalyzer()
        self.rare_selector = RareTargetSelector()
        self.graph_builder = CircuitGraphBuilder()
        self.coverage_analyzer = CoverageAnalyzer(self.simulator)
        self.validator = HTValidator(self.simulator)

    def run(
        self,
        config: ExperimentConfiguration,
    ) -> ExperimentResults:
        started = perf_counter()
        circuit = self.circuit_reader.read(Path(config.circuit))
        if config.test_vector_method == "shield_legacy_random":
            vectors = self.legacy_vector_generator.generate(circuit, config.sample_size, config.seed)
        elif config.test_vector_method == "random":
            vectors = self.vector_generator.generate(circuit, config.sample_size, config.seed)
        else:
            raise ValueError(f"unknown test_vector_method: {config.test_vector_method}")
        simulation = self.simulator.simulate(circuit, vectors)
        activity = self.activity_analyzer.analyze(simulation)
        targets = self.rare_selector.select(activity, config.rarity_method, config.threshold)
        if config.graph_method != "directed_net_graph":
            raise ValueError(f"unknown graph_method: {config.graph_method}")
        graph = self.graph_builder.build(circuit)
        if config.input_analysis_method != "reverse_dfs":
            raise ValueError(f"unknown input_analysis_method: {config.input_analysis_method}")
        input_analyzer = ReverseDFSInputAnalyzer(config.minimum_target_impact)
        selected_inputs = input_analyzer.analyze(graph, targets)
        candidate_generators = {
            "random_selected_inputs": RandomSelectedInputCandidateGenerator,
            "random_full_inputs": RandomFullInputCandidateGenerator,
        }
        if config.candidate_generation_method not in candidate_generators:
            raise ValueError(
                f"unknown candidate_generation_method: {config.candidate_generation_method}"
            )
        candidate_generator = candidate_generators[config.candidate_generation_method](
            config.candidate_count, config.seed
        )
        pool = candidate_generator.generate(circuit, selected_inputs)
        matrix = self.coverage_analyzer.analyze(circuit, pool, targets)
        problem = ProblemDefinition(
            config.problem_type,
            config.test_budget,
            constraints=config.optimization_parameters.get("constraints", {}),
        )
        if config.optimization_method == "greedy":
            optimizer = GreedyCoverageOptimizer()
        elif config.optimization_method == "pso":
            optimizer = DiscretePSOOptimizer(
                seed=config.seed,
                particles=int(config.optimization_parameters.get("particles", 40)),
                iterations=int(config.optimization_parameters.get("iterations", 100)),
            )
        else:
            raise ValueError(f"unknown optimization_method: {config.optimization_method}")
        selected_tests = optimizer.optimize(pool, matrix, problem)
        validation_result = None
        if config.validation_enabled:
            if not config.ht_circuit or config.ht_ground_truth is None:
                raise ValueError(
                    "validation_enabled requires ht_circuit and ht_ground_truth"
                )
            ht_ir = self.circuit_reader.read(config.ht_circuit)
            golden_ir = (
                self.circuit_reader.read(config.ht_golden_circuit)
                if config.ht_golden_circuit
                else None
            )
            validation_result = self.validator.validate(
                selected_tests,
                HTCircuit(ht_ir, golden_ir),
                config.ht_ground_truth,
            )
        return ExperimentResults(
            circuit_name=circuit.name,
            configuration=config,
            rare_target_count=len(targets.targets),
            selected_input_count=len(selected_inputs.inputs),
            candidate_count=len(pool.candidates),
            selected_test_count=selected_tests.test_set_size,
            coverage=selected_tests.coverage,
            runtime_seconds=perf_counter() - started,
            selected_test_ids=selected_tests.selected_test_ids,
            optimization_result={
                "method": config.optimization_method,
                "problem_type": config.problem_type,
                "objective_value": selected_tests.objective_value,
                "coverage": selected_tests.coverage,
                "selected_test_ids": selected_tests.selected_test_ids,
            },
            validation_result=validation_result,
        )
