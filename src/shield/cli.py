"""Command-line entry point for reproducible experiments."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .experiment import ExperimentRunner
from .models import ExperimentConfiguration, HTGroundTruth


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the modular SHIELD baseline")
    parser.add_argument("circuit", type=Path)
    parser.add_argument("--sample-size", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--test-vector-method", choices=["shield_legacy_random", "random"], default="shield_legacy_random")
    parser.add_argument("--rarity-method", choices=["switching_activity", "transition_probability", "signal_probability"], default="switching_activity")
    parser.add_argument("--threshold", type=float, default=0.1)
    parser.add_argument("--minimum-target-impact", type=int, default=2)
    parser.add_argument("--candidate-count", type=int, default=100)
    parser.add_argument("--candidate-generation-method", choices=["random_selected_inputs", "random_full_inputs"], default="random_selected_inputs")
    parser.add_argument("--optimization-method", choices=["greedy", "pso"], default="greedy")
    parser.add_argument("--pso-particles", type=int, default=40)
    parser.add_argument("--pso-iterations", type=int, default=100)
    parser.add_argument("--problem-type", choices=["minimum_test_set", "maximum_coverage_fixed_budget"], default="minimum_test_set")
    parser.add_argument("--test-budget", type=int)
    parser.add_argument("--ht-circuit", type=Path)
    parser.add_argument("--ht-golden-circuit", type=Path)
    parser.add_argument("--trigger-nets", help="Comma-separated trigger net names")
    parser.add_argument("--trigger-values", help="Comma-separated trigger values")
    parser.add_argument("--payload-location")
    parser.add_argument("--payload-type")
    parser.add_argument("--affected-output")
    parser.add_argument("--output", type=Path)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    ground_truth = None
    if args.ht_circuit:
        if not args.trigger_nets or not args.trigger_values:
            raise SystemExit("--ht-circuit requires --trigger-nets and --trigger-values")
        trigger_nets = tuple(item.strip() for item in args.trigger_nets.split(",") if item.strip())
        trigger_values = tuple(int(item.strip()) for item in args.trigger_values.split(","))
        if len(trigger_nets) != len(trigger_values) or any(value not in (0, 1) for value in trigger_values):
            raise SystemExit("trigger nets and binary values must have equal lengths")
        ground_truth = HTGroundTruth(
            trigger_nets=trigger_nets,
            trigger_values=trigger_values,
            payload_location=args.payload_location,
            payload_type=args.payload_type,
            affected_output=args.affected_output,
        )
    config = ExperimentConfiguration(
        circuit=str(args.circuit),
        sample_size=args.sample_size,
        seed=args.seed,
        test_vector_method=args.test_vector_method,
        rarity_method=args.rarity_method,
        threshold=args.threshold,
        minimum_target_impact=args.minimum_target_impact,
        candidate_generation_method=args.candidate_generation_method,
        candidate_count=args.candidate_count,
        optimization_method=args.optimization_method,
        problem_type=args.problem_type,
        test_budget=args.test_budget,
        validation_enabled=bool(args.ht_circuit),
        ht_circuit=str(args.ht_circuit) if args.ht_circuit else None,
        ht_golden_circuit=str(args.ht_golden_circuit) if args.ht_golden_circuit else None,
        ht_ground_truth=ground_truth,
        optimization_parameters={
            "particles": args.pso_particles,
            "iterations": args.pso_iterations,
        },
    )
    result = ExperimentRunner().run(config)
    payload = json.dumps(result.to_dict(), indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
    print(payload)


if __name__ == "__main__":
    main()
