"""Week-2 experiment orchestration.

This is part of the Experiment Module: it composes public module contracts but
does not move experiment-specific logic into algorithm modules.
"""

from __future__ import annotations

import csv
import json
import math
from dataclasses import asdict
from itertools import combinations
from pathlib import Path
from statistics import mean, pstdev
from time import perf_counter
from typing import Any, Iterable

from .activity import ActivityAnalyzer
from .circuit import BenchCircuitReader
from .graph import (
    CircuitGraphBuilder,
    distance,
    fanin_cone,
    fanout_cone,
    reachable_inputs,
    reverse_traversal_trace,
)
from .input_analysis import (
    InputRanker,
    ReverseDFSInputAnalyzer,
    relevant_inputs,
    select_top_k,
)
from .models import ActivityInfo, InputSelectionMetrics, NodeActivity, RareTargets
from .rarity import RareTargetSelector
from .simulation import LogicSimulator
from .test_vectors import LegacyShieldTestVectorGenerator, RandomTestVectorGenerator


def load_week2_config(path: str | Path) -> dict[str, Any]:
    config_path = Path(path)
    data = json.loads(config_path.read_text(encoding="utf-8"))
    required = {"circuits", "dataset_dir", "output_dir", "baseline", "task1", "task3", "task4"}
    missing = required - data.keys()
    if missing:
        raise ValueError(f"week2 config is missing: {sorted(missing)}")
    data["_config_dir"] = str(config_path.resolve().parent)
    return data


def jaccard(a: set[str], b: set[str]) -> float:
    """Jaccard similarity; empty/empty is deliberately undefined (NaN)."""
    union = a | b
    return math.nan if not union else len(a & b) / len(union)


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


def _output_dir(config: dict[str, Any]) -> Path:
    return Path(config["output_dir"])


class RarityStabilityExperiment:
    """Task 1: cache each simulation once and sweep rarity thresholds."""

    def __init__(self) -> None:
        self.reader = BenchCircuitReader()
        self.legacy_generator = LegacyShieldTestVectorGenerator()
        self.random_generator = RandomTestVectorGenerator()
        self.simulator = LogicSimulator()
        self.activity_analyzer = ActivityAnalyzer()
        self.selector = RareTargetSelector()

    def run(self, config: dict[str, Any]) -> tuple[Path, Path]:
        output = _output_dir(config) / "task1"
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
                        generator = self.legacy_generator if method == "shield_legacy_random" else self.random_generator
                        vectors = generator.generate(circuit, sample_size, seed)
                        activity = self.activity_analyzer.analyze(self.simulator.simulate(circuit, vectors))
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
        _write_csv(rare_path, ["circuit", "M", "seed", "method", "threshold", "rare_count", "rare_net_ids"], rare_rows)
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
                                runtimes[(circuit_name, sample_size, seed)] for seed in settings["seeds"]
                            ),
                        })
        stability_path = output / "stability.csv"
        fields = ["circuit", "M", "method", "threshold", "mean_jaccard", "std_jaccard", "min_jaccard", "mean_rare_count", "mean_runtime_s"]
        _write_csv(stability_path, fields, stability_rows)
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
                points = [row for row in rows if row["circuit"] == circuit and math.isclose(row["threshold"], threshold)]
                axis.plot([row["M"] for row in points], [row["mean_jaccard"] for row in points], marker="o", label=f"t={threshold:g}")
            axis.set_xscale("log")
            axis.set_xlabel("M (test vector count, log scale)")
            axis.set_ylabel("Mean Jaccard")
            axis.set_title(f"{circuit}: rarity stability")
            axis.grid(True, alpha=0.3)
            axis.legend()
            figure.tight_layout()
            figure.savefig(output / f"{circuit}_stability.png", dpi=160)
            plt.close(figure)

    def _write_debug(self, config: dict[str, Any], sets: dict[tuple[str, int, int, str, float], set[str]], output: Path) -> None:
        baseline = config["baseline"]
        circuit = self.reader.read(_circuit_path(config, "c1908"))
        vectors = self.legacy_generator.generate(circuit, baseline["M"], baseline["seed"])
        simulation = self.simulator.simulate(circuit, vectors)
        activity = self.activity_analyzer.analyze(simulation)
        targets = self.selector.select(activity, baseline["rarity_method"], baseline["threshold"])
        lines = ["TASK 1 DEBUG — c1908 baseline", ""]
        for target in targets.targets[:3]:
            values = [row[target.target_id] for row in simulation.net_values[:20]]
            node = activity.nodes[target.target_id]
            lines.extend([
                f"net={target.target_id}",
                f"first20={values}",
                f"manual first20 zero={values.count(0)} one={values.count(1)} transitions={sum(a != b for a, b in zip(values, values[1:]))}",
                f"ActivityInfo fullM zero={node.zero_count} one={node.one_count} 01={node.transition_0_to_1} 10={node.transition_1_to_0} score={target.rarity_score}",
                "",
            ])
        # Lowest-J pair at baseline M/threshold among task seeds.
        keys = [(seed, sets[("c1908", baseline["M"], seed, baseline["rarity_method"], baseline["threshold"])]) for seed in config["task1"]["seeds"]]
        seed_a, set_a, seed_b, set_b, score = min(
            ((sa, a, sb, b, jaccard(a, b)) for (sa, a), (sb, b) in combinations(keys, 2)),
            key=lambda item: math.inf if math.isnan(item[4]) else item[4],
        )
        lines.extend([
            f"lowest pair: seed {seed_a} vs seed {seed_b}, J={score}",
            f"only seed {seed_a}: {sorted(set_a - set_b, key=_node_sort_key)}",
            f"only seed {seed_b}: {sorted(set_b - set_a, key=_node_sort_key)}",
        ])
        cache_dir = output / "activity_cache"
        activity_a, _ = _activity_from_json(json.loads((cache_dir / f"c1908_M{baseline['M']}_seed{seed_a}.json").read_text(encoding="utf-8")))
        activity_b, _ = _activity_from_json(json.loads((cache_dir / f"c1908_M{baseline['M']}_seed{seed_b}.json").read_text(encoding="utf-8")))
        differing = sorted(set_a ^ set_b, key=_node_sort_key)
        lines.append("Farklı netlerin skorları (eşik uzaklığı ile):")
        for node in differing:
            score_a = activity_a.nodes[node].switching_activity
            score_b = activity_b.nodes[node].switching_activity
            lines.append(
                f"net={node} seed{seed_a}={score_a:.6f} seed{seed_b}={score_b:.6f} "
                f"threshold_distance=({abs(score_a-baseline['threshold']):.6f}, {abs(score_b-baseline['threshold']):.6f})"
            )
        lines.append("Yorum: eşik uzaklığı küçük olan netlerde küçük örnekleme farkı rare/non-rare kararını değiştirebilir.")
        (output / "debug_c1908.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_graph_checks(config: dict[str, Any]) -> Path:
    """Task 2 checks and c1908 traversal debug output."""
    reader = BenchCircuitReader()
    builder = CircuitGraphBuilder()
    output = _output_dir(config) / "task2"
    rows: list[dict[str, Any]] = []
    debug_lines: list[str] = []
    baseline_targets = _baseline_targets(config, "c1908")

    for circuit_name in config["circuits"]:
        circuit = reader.read(_circuit_path(config, circuit_name))
        graph = builder.build(circuit)
        targets = baseline_targets if circuit_name == "c1908" else _baseline_targets(config, circuit_name)
        target_fanins = {target.target_id: fanin_cone(graph, target.target_id) for target in targets.targets}
        input_fanouts = {node: fanout_cone(graph, node) for node in graph.primary_input_nodes}
        symmetry_mismatches = sum(
            (node in target_fanins[target.target_id]) != (target.target_id in input_fanouts[node])
            for target in targets.targets
            for node in graph.primary_input_nodes
        )
        no_pi_cones = sum(not reachable_inputs(graph, node) for node in graph.nodes if node not in graph.primary_input_nodes)
        reverse_dfs_mismatches = sum(
            set(ReverseDFSInputAnalyzer(1).analyze(
                graph, RareTargets((target,), source=targets.source)
            ).input_ids) != reachable_inputs(graph, target.target_id)
            for target in targets.targets
        )
        rows.append({
            "circuit": circuit_name,
            "symmetry_mismatches": symmetry_mismatches,
            "internal_nodes_without_PI": no_pi_cones,
            "reverse_dfs_mismatch_count": reverse_dfs_mismatches,
        })
        if circuit_name == "c1908" and targets.targets:
            target_id = targets.targets[0].target_id
            debug_lines.extend([
                f"target={target_id}",
                *[f"step {index}: visited={node} stack={list(stack)}" for index, (node, stack) in enumerate(reverse_traversal_trace(graph, target_id), 1)],
                f"fanin_cone_size={len(fanin_cone(graph, target_id))}",
                f"reachable_input_count={len(reachable_inputs(graph, target_id))}",
                f"SHIELD reverse DFS == reachable_inputs for every target: {reverse_dfs_mismatches == 0}",
                "Yorum: eşleşme yoksa traversal yönü, node kimliği veya minimum_target_impact filtresi kontrol edilmelidir.",
            ])
    result = output / "graph_checks.csv"
    _write_csv(result, ["circuit", "symmetry_mismatches", "internal_nodes_without_PI", "reverse_dfs_mismatch_count"], rows)
    (output / "debug_c1908.txt").write_text("\n".join(debug_lines) + "\n", encoding="utf-8")
    return result


def run_input_selection(config: dict[str, Any]) -> Path:
    """Tasks 3 and 4: rank/select inputs and measure DR/TP."""
    reader = BenchCircuitReader()
    builder = CircuitGraphBuilder()
    output = _output_dir(config) / "task3_4"
    output.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    regression_rows: list[dict[str, Any]] = []
    selections: dict[str, Any] = {}
    debug_lines: list[str] = []
    repetitions = int(config["task4"]["runtime_repetitions"])

    for circuit_name in config["circuits"]:
        circuit = reader.read(_circuit_path(config, circuit_name))
        graph = builder.build(circuit)
        targets = _baseline_targets(config, circuit_name)
        P_R = relevant_inputs(graph, targets)
        legacy_set = set(ReverseDFSInputAnalyzer(1).analyze(graph, targets).input_ids)
        selections[circuit_name] = {}
        for method in config["task3"]["input_ranking_methods"]:
            ranker = InputRanker(method)
            timings: list[float] = []
            scores: dict[str, float] = {}
            for _ in range(repetitions):
                started = perf_counter()
                scores = ranker.rank(graph, targets, P_R)
                timings.append(perf_counter() - started)
            runtime_s = mean(timings)
            if method == "shield_dfs":
                ranked_set = set(select_top_k(scores, 100))
                regression_rows.append({
                    "circuit": circuit_name,
                    "legacy_count": len(legacy_set),
                    "ranked_count": len(ranked_set),
                    "exact_match": legacy_set == ranked_set,
                    "mismatch_ids": " ".join(sorted(legacy_set ^ ranked_set, key=_node_sort_key)),
                })
            selections[circuit_name][method] = {}
            for k in config["task3"]["k_values"]:
                selected = select_top_k(scores, k)
                covered = {
                    target.target_id
                    for target in targets.targets
                    if any(distance(graph, node, target.target_id) is not None for node in selected)
                }
                metrics = InputSelectionMetrics(
                    circuit=circuit_name,
                    method=method,
                    k=k,
                    num_P=len(graph.primary_input_nodes),
                    num_PR=len(P_R),
                    num_selected=len(selected),
                    num_R=len(targets.targets),
                    DR_k=1 - len(selected) / len(graph.primary_input_nodes),
                    TP_k=len(covered) / len(targets.targets) if targets.targets else 1.0,
                    runtime_s=runtime_s,
                )
                rows.append(asdict(metrics))
                selections[circuit_name][method][str(k)] = list(selected)
            if circuit_name == "c1908":
                debug_lines.append(f"METHOD={method}")
                for node in select_top_k(scores, 100)[:10]:
                    reached = [target.target_id for target in targets.targets if distance(graph, node, target.target_id) is not None]
                    distances = [distance(graph, node, target) for target in reached]
                    debug_lines.append(f"input={node} score={scores[node]:.6f} reached={len(reached)} nearest={min(distances) if distances else None}")
                debug_lines.append("")
        if circuit_name == "c1908":
            method_orders = {
                method: select_top_k(
                    InputRanker(method).rank(graph, targets, P_R), 100
                )
                for method in config["task3"]["input_ranking_methods"]
            }
            pair = next(
                (
                    node
                    for node in method_orders["shield_dfs"]
                    if method_orders["shield_dfs"].index(node)
                    != method_orders["dist_weighted"].index(node)
                ),
                None,
            )
            if pair is not None:
                debug_lines.append(
                    f"Sırası değişen örnek input={pair}: shield_dfs_rank={method_orders['shield_dfs'].index(pair)+1}, "
                    f"dist_weighted_rank={method_orders['dist_weighted'].index(pair)+1}. "
                    "Neden: shield_dfs hedef sayısını, dist_weighted ise hedeflere olan yol uzunluklarını da hesaba katar."
                )
        excluded = sorted(set(graph.primary_input_nodes) - P_R, key=_node_sort_key)
        if circuit_name == "c1908" and excluded:
            sample = excluded[0]
            debug_lines.append(f"P_R dışı örnek input={sample}; rare target yolları={[distance(graph, sample, target.target_id) for target in targets.targets]}")

    csv_path = output / "input_selection_results.csv"
    fields = ["circuit", "method", "k", "num_P", "num_PR", "num_selected", "num_R", "DR_k", "TP_k", "runtime_s"]
    _write_csv(csv_path, fields, rows)
    _write_csv(
        output / "shield_dfs_regression.csv",
        ["circuit", "legacy_count", "ranked_count", "exact_match", "mismatch_ids"],
        regression_rows,
    )
    (output / "selected_inputs.json").write_text(json.dumps(selections, indent=2) + "\n", encoding="utf-8")
    (output / "debug_c1908.txt").write_text("\n".join(debug_lines) + "\n", encoding="utf-8")
    noteworthy = min(rows, key=lambda row: row["TP_k"])
    circuit = reader.read(_circuit_path(config, noteworthy["circuit"]))
    graph = builder.build(circuit)
    targets = _baseline_targets(config, noteworthy["circuit"])
    chosen = set(selections[noteworthy["circuit"]][noteworthy["method"]][str(noteworthy["k"])])
    lost = [
        target.target_id
        for target in targets.targets
        if not any(distance(graph, node, target.target_id) is not None for node in chosen)
    ]
    lost_lines = [
        f"circuit={noteworthy['circuit']} method={noteworthy['method']} k={noteworthy['k']} TP={noteworthy['TP_k']}",
        f"lost_targets={lost}",
    ]
    for target_id in lost:
        lost_lines.append(
            f"target={target_id} reachable_inputs={sorted(reachable_inputs(graph, target_id), key=_node_sort_key)}"
        )
    (output / "debug_lost_targets.txt").write_text("\n".join(lost_lines) + "\n", encoding="utf-8")
    _plot_selection(config, rows, output)
    return csv_path


def _baseline_targets(config: dict[str, Any], circuit_name: str) -> RareTargets:
    baseline = config["baseline"]
    circuit = BenchCircuitReader().read(_circuit_path(config, circuit_name))
    generator = LegacyShieldTestVectorGenerator() if baseline["test_vector_method"] == "shield_legacy_random" else RandomTestVectorGenerator()
    vectors = generator.generate(circuit, baseline["M"], baseline["seed"])
    activity = ActivityAnalyzer().analyze(LogicSimulator().simulate(circuit, vectors))
    return RareTargetSelector().select(activity, baseline["rarity_method"], baseline["threshold"])


def _plot_selection(config: dict[str, Any], rows: list[dict[str, Any]], output: Path) -> None:
    try:
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise RuntimeError("Task 4 plots require matplotlib") from exc
    for circuit in config["circuits"]:
        for metric in ("TP_k", "DR_k"):
            figure, axis = plt.subplots(figsize=(8, 5))
            for method in config["task3"]["input_ranking_methods"]:
                points = [row for row in rows if row["circuit"] == circuit and row["method"] == method]
                axis.plot([row["k"] for row in points], [row[metric] for row in points], marker="o", label=method)
            axis.set_xlabel("k (%)")
            axis.set_ylabel(metric)
            axis.set_ylim(-0.02, 1.02)
            axis.set_title(f"{circuit}: {metric}")
            axis.grid(True, alpha=0.3)
            axis.legend()
            figure.tight_layout()
            figure.savefig(output / f"{circuit}_{metric}.png", dpi=160)
            plt.close(figure)


def _node_sort_key(node: str) -> tuple[int, int | str]:
    try:
        return (0, int(node))
    except ValueError:
        return (1, node)
