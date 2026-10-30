#!/usr/bin/env python3
"""Run the rare-target stability experiment requested in Week 2 Task 1."""

from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import asdict
from itertools import combinations
from pathlib import Path
from statistics import mean, pstdev
from time import perf_counter
from typing import Any, Iterable

from shield.activity import ActivityAnalyzer
from shield.circuit import BenchCircuitReader
from shield.models import ActivityInfo, NodeActivity, SimulationResults
from shield.rarity import RareTargetSelector, jaccard
from shield.simulation import LogicSimulator
from shield.test_vectors import LegacyShieldTestVectorGenerator, RandomTestVectorGenerator


def load_config(path: str | Path) -> dict[str, Any]:
    config_path = Path(path)
    data = json.loads(config_path.read_text(encoding="utf-8"))
    required = {"circuits", "dataset_dir", "output_dir", "baseline", "task1"}
    missing = required - data.keys()
    if missing:
        raise ValueError(f"rarity stability config is missing: {sorted(missing)}")
    return data


def _thresholds(start: float, stop: float, step: float) -> tuple[float, ...]:
    count = int(round((stop - start) / step))
    return tuple(round(start + index * step, 10) for index in range(count + 1))


def _activity_to_json(activity: ActivityInfo, runtime_s: float) -> dict[str, Any]:
    return {
        "target_eligible_nodes": list(activity.target_eligible_nodes),
        "nodes": {node: asdict(item) for node, item in activity.nodes.items()},
        "runtime_s": runtime_s,
    }


def _activity_from_json(payload: dict[str, Any]) -> tuple[ActivityInfo, float]:
    nodes = {node: NodeActivity(**values) for node, values in payload["nodes"].items()}
    return ActivityInfo(nodes, tuple(payload["target_eligible_nodes"])), float(payload["runtime_s"])


def _write_csv(path: Path, fieldnames: list[str], rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _circuit_path(config: dict[str, Any], circuit: str) -> Path:
    return Path(config["dataset_dir"]) / f"{circuit}.bench"


# Week 2 Task 1: Her (M, seed) bir kez simulate edilir; ActivityInfo eşiklerde tekrar kullanılır.
class RarityStabilityExperiment:
    def __init__(self) -> None:
        self.reader = BenchCircuitReader()
        self.legacy_generator = LegacyShieldTestVectorGenerator()
        self.random_generator = RandomTestVectorGenerator()
        self.simulator = LogicSimulator()
        self.activity_analyzer = ActivityAnalyzer()
        self.selector = RareTargetSelector()

    def run(self, config: dict[str, Any]) -> tuple[Path, Path]:
        output = Path(config["output_dir"]) / "task1"
        cache_dir = output / "activity_cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        settings = config["task1"]
        thresholds = _thresholds(
            settings["threshold_start"], settings["threshold_stop"], settings["threshold_step"]
        )
        rare_rows: list[dict[str, Any]] = []
        sets: dict[tuple[str, int, int, str, float], set[str]] = {}
        runtimes: dict[tuple[str, int, int], float] = {}

        for circuit_name in config["circuits"]:
            circuit = self.reader.read(_circuit_path(config, circuit_name))
            for sample_size in settings["sample_sizes"]:
                for seed in settings["seeds"]:
                    cache_path = cache_dir / f"{circuit_name}_M{sample_size}_seed{seed}.json"
                    if cache_path.exists():
                        activity, runtime_s = _activity_from_json(
                            json.loads(cache_path.read_text(encoding="utf-8"))
                        )
                    else:
                        started = perf_counter()
                        method = config["baseline"]["test_vector_method"]
                        generator = (
                            self.legacy_generator
                            if method == "shield_legacy_random"
                            else self.random_generator
                        )
                        vectors = generator.generate(circuit, sample_size, seed)
                        activity = self.activity_analyzer.analyze(
                            self.simulator.simulate(circuit, vectors)
                        )
                        runtime_s = perf_counter() - started
                        cache_path.write_text(
                            json.dumps(_activity_to_json(activity, runtime_s), indent=2) + "\n",
                            encoding="utf-8",
                        )
                    runtimes[(circuit_name, sample_size, seed)] = runtime_s
                    for method in settings["rarity_methods"]:
                        for threshold in thresholds:
                            targets = self.selector.select(activity, method, threshold)
                            target_ids = {target.target_id for target in targets.targets}
                            sets[(circuit_name, sample_size, seed, method, threshold)] = target_ids
                            rare_rows.append({
                                "circuit": circuit_name,
                                "M": sample_size,
                                "seed": seed,
                                "method": method,
                                "threshold": threshold,
                                "rare_count": len(target_ids),
                                "rare_net_ids": " ".join(sorted(target_ids, key=_node_sort_key)),
                            })

        rare_path = output / "rare_sets.csv"
        _write_csv(
            rare_path,
            ["circuit", "M", "seed", "method", "threshold", "rare_count", "rare_net_ids"],
            rare_rows,
        )
        stability_rows: list[dict[str, Any]] = []
        for circuit_name in config["circuits"]:
            for sample_size in settings["sample_sizes"]:
                for method in settings["rarity_methods"]:
                    for threshold in thresholds:
                        seed_sets = [
                            sets[(circuit_name, sample_size, seed, method, threshold)]
                            for seed in settings["seeds"]
                        ]
                        similarities = [jaccard(a, b) for a, b in combinations(seed_sets, 2)]
                        valid = [value for value in similarities if not math.isnan(value)]
                        counts = [len(value) for value in seed_sets]
                        stability_rows.append({
                            "circuit": circuit_name,
                            "M": sample_size,
                            "method": method,
                            "threshold": threshold,
                            "mean_jaccard": mean(valid) if valid else math.nan,
                            "std_jaccard": pstdev(valid) if valid else math.nan,
                            "min_jaccard": min(valid) if valid else math.nan,
                            "mean_rare_count": mean(counts),
                            "mean_runtime_s": mean(
                                runtimes[(circuit_name, sample_size, seed)]
                                for seed in settings["seeds"]
                            ),
                        })

        stability_path = output / "stability.csv"
        _write_csv(
            stability_path,
            [
                "circuit", "M", "method", "threshold", "mean_jaccard",
                "std_jaccard", "min_jaccard", "mean_rare_count", "mean_runtime_s",
            ],
            stability_rows,
        )
        self._plot(config, stability_rows, output)
        if "c1908" in config["circuits"]:
            self._write_debug(config, sets, output)
        return rare_path, stability_path

    @staticmethod
    def _plot(config: dict[str, Any], rows: list[dict[str, Any]], output: Path) -> None:
        try:
            import matplotlib.pyplot as plt
        except ImportError as exc:
            raise RuntimeError("Task 1 plots require matplotlib") from exc
        chosen = set(config["task1"]["plot_thresholds"])
        for circuit in config["circuits"]:
            figure, axis = plt.subplots(figsize=(8, 5))
            for threshold in sorted(chosen):
                points = [
                    row for row in rows
                    if row["circuit"] == circuit and math.isclose(row["threshold"], threshold)
                ]
                axis.plot(
                    [row["M"] for row in points],
                    [row["mean_jaccard"] for row in points],
                    marker="o",
                    label=f"t={threshold:g}",
                )
            axis.set_xscale("log")
            axis.set_xlabel("M (test vector count, log scale)")
            axis.set_ylabel("Mean Jaccard")
            axis.set_title(f"{circuit}: rarity stability")
            axis.grid(True, alpha=0.3)
            axis.legend()
            figure.tight_layout()
            figure.savefig(output / f"{circuit}_stability.png", dpi=160)
            plt.close(figure)

    def _write_debug(
        self,
        config: dict[str, Any],
        sets: dict[tuple[str, int, int, str, float], set[str]],
        output: Path,
    ) -> None:
        baseline = config["baseline"]
        circuit = self.reader.read(_circuit_path(config, "c1908"))
        generator = (
            self.legacy_generator
            if baseline["test_vector_method"] == "shield_legacy_random"
            else self.random_generator
        )
        vectors = generator.generate(circuit, baseline["M"], baseline["seed"])
        simulation = self.simulator.simulate(circuit, vectors)
        activity = self.activity_analyzer.analyze(simulation)
        targets = self.selector.select(activity, baseline["rarity_method"], baseline["threshold"])
        first20_activity = self.activity_analyzer.analyze(SimulationResults(
            simulation.primary_input_order,
            simulation.test_vectors[:20],
            simulation.net_values[:20],
            simulation.target_eligible_nodes,
        ))
        lines = ["TASK 1 DEBUG — c1908 baseline", ""]
        for target in targets.targets[:3]:
            values = [row[target.target_id] for row in simulation.net_values[:20]]
            node = first20_activity.nodes[target.target_id]
            lines.extend([
                f"net={target.target_id}",
                f"first20={values}",
                f"manual first20 zero={values.count(0)} one={values.count(1)} 01={sum(a == 0 and b == 1 for a, b in zip(values, values[1:]))} 10={sum(a == 1 and b == 0 for a, b in zip(values, values[1:]))}",
                f"ActivityInfo first20 zero={node.zero_count} one={node.one_count} 01={node.transition_0_to_1} 10={node.transition_1_to_0}",
                "",
            ])
        keys = [
            (
                seed,
                sets[(
                    "c1908", baseline["M"], seed,
                    baseline["rarity_method"], baseline["threshold"],
                )],
            )
            for seed in config["task1"]["seeds"]
        ]
        seed_a, set_a, seed_b, set_b, score = min(
            (
                (sa, a, sb, b, jaccard(a, b))
                for (sa, a), (sb, b) in combinations(keys, 2)
            ),
            key=lambda item: math.inf if math.isnan(item[4]) else item[4],
        )
        lines.extend([
            f"lowest pair: seed {seed_a} vs seed {seed_b}, J={score}",
            f"only seed {seed_a}: {sorted(set_a - set_b, key=_node_sort_key)}",
            f"only seed {seed_b}: {sorted(set_b - set_a, key=_node_sort_key)}",
        ])
        cache_dir = output / "activity_cache"
        activity_a, _ = _activity_from_json(json.loads(
            (cache_dir / f"c1908_M{baseline['M']}_seed{seed_a}.json").read_text(encoding="utf-8")
        ))
        activity_b, _ = _activity_from_json(json.loads(
            (cache_dir / f"c1908_M{baseline['M']}_seed{seed_b}.json").read_text(encoding="utf-8")
        ))
        lines.append("Farklı netlerin skorları (eşik uzaklığı ile):")
        for node in sorted(set_a ^ set_b, key=_node_sort_key):
            score_a = activity_a.nodes[node].switching_activity
            score_b = activity_b.nodes[node].switching_activity
            lines.append(
                f"net={node} seed{seed_a}={score_a:.6f} seed{seed_b}={score_b:.6f} "
                f"threshold_distance=({abs(score_a-baseline['threshold']):.6f}, "
                f"{abs(score_b-baseline['threshold']):.6f})"
            )
        lines.append(
            "Yorum: eşik uzaklığı küçük olan netlerde küçük örnekleme farkı "
            "rare/non-rare kararını değiştirebilir."
        )
        (output / "debug_c1908.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _node_sort_key(node: str) -> tuple[int, int | str]:
    try:
        return (0, int(node))
    except ValueError:
        return (1, node)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/week2.json")
    args = parser.parse_args()
    print(RarityStabilityExperiment().run(load_config(args.config)))


if __name__ == "__main__":
    main()
