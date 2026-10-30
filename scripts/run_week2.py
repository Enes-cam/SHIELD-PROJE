#!/usr/bin/env python3
"""Run the Week 2 experiments without adding week-specific code to ``shield``."""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Iterable

from shield.activity import ActivityAnalyzer
from shield.circuit import BenchCircuitReader
from shield.experiment import evaluate_input_selection, measure_input_ranking
from shield.graph import (
    CircuitGraphBuilder,
    distance,
    fanin_cone,
    fanout_cone,
    reachable_inputs,
    reverse_traversal_trace,
)
from shield.input_analysis import (
    InputRanker,
    ReverseDFSInputAnalyzer,
    relevant_inputs,
    select_top_k,
    selected_inputs_from_scores,
)
from shield.models import RareTargets
from shield.rarity import RareTargetSelector
from shield.simulation import LogicSimulator
from shield.test_vectors import LegacyShieldTestVectorGenerator, RandomTestVectorGenerator

from rarity_stability import RarityStabilityExperiment


def load_week2_config(path: str | Path) -> dict[str, Any]:
    config_path = Path(path)
    data = json.loads(config_path.read_text(encoding="utf-8"))
    required = {"circuits", "dataset_dir", "output_dir", "baseline", "task1", "task3", "task4"}
    missing = required - data.keys()
    if missing:
        raise ValueError(f"week2 config is missing: {sorted(missing)}")
    data["_config_dir"] = str(config_path.resolve().parent)
    return data


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
        input_fanouts = {node: fanout_cone(graph, node) for node in graph.primary_input_nodes}
        symmetry_mismatches = 0
        for net in graph.nodes:
            net_fanin = fanin_cone(graph, net)
            symmetry_mismatches += sum(
                (node in net_fanin) != (net in input_fanouts[node])
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
            reverse_inputs = set(ReverseDFSInputAnalyzer(1).analyze(
                graph, RareTargets((targets.targets[0],), source=targets.source)
            ).input_ids)
            graph_inputs = reachable_inputs(graph, target_id)
            debug_lines.extend([
                f"target={target_id}",
                *[f"step {index}: visited={node} stack={list(stack)}" for index, (node, stack) in enumerate(reverse_traversal_trace(graph, target_id), 1)],
                f"fanin_cone_size={len(fanin_cone(graph, target_id))}",
                f"reachable_input_count={len(graph_inputs)}",
                f"SHIELD_reverse_DFS={sorted(reverse_inputs, key=_node_sort_key)}",
                f"reachable_inputs={sorted(graph_inputs, key=_node_sort_key)}",
                f"mismatch={sorted(reverse_inputs ^ graph_inputs, key=_node_sort_key)}",
                "Yorum: iki küme aynı; bu hedef için backward path hesabı eşleşiyor." if reverse_inputs == graph_inputs else "Yorum: iki küme farklı; traversal yönü ve node kimliği incelenmeli.",
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
    excluded_example_written = False
    repetitions = int(config["task4"]["runtime_repetitions"])

    for circuit_name in config["circuits"]:
        circuit = reader.read(_circuit_path(config, circuit_name))
        graph = builder.build(circuit)
        targets = _baseline_targets(config, circuit_name)
        P_R = relevant_inputs(graph, targets)
        legacy_set = set(ReverseDFSInputAnalyzer(2).analyze(graph, targets).input_ids)
        selections[circuit_name] = {}
        for method in config["task3"]["input_ranking_methods"]:
            scores, runtime_s = measure_input_ranking(
                graph, targets, P_R, method, repetitions
            )
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
                metrics, selected = evaluate_input_selection(
                    circuit_name, graph, targets, method, k, scores, runtime_s
                )
                selected_inputs = selected_inputs_from_scores(scores, selected, method, graph, targets)
                rows.append(asdict(metrics))
                selections[circuit_name][method][str(k)] = list(selected_inputs.input_ids)
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
        if circuit_name == "c1908" and not excluded:
            debug_lines.append("c1908 baseline: P_R dışı input yok; 33 primary input'un tamamı en az bir rare target'a ulaşıyor.")
        if excluded and not excluded_example_written:
            sample = excluded[0]
            reachable_targets = [target.target_id for target in targets.targets if target.target_id in fanout_cone(graph, sample)]
            debug_lines.append(f"P_R dışı örnek circuit={circuit_name} input={sample}; fanout_cone ile erişilen rare target'lar={reachable_targets}")
            excluded_example_written = True

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
    lost_lines.append("Yorum: Bu hedeflere ulaşan input'ların hiçbiri seçilen top-k kümesinde değil.")
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/week2.json")
    parser.add_argument("--task", choices=["1", "2", "3-4", "all"], default="all")
    args = parser.parse_args()
    config = load_week2_config(args.config)
    if args.task in {"1", "all"}:
        print("Task 1:", RarityStabilityExperiment().run(config))
    if args.task in {"2", "all"}:
        print("Task 2:", run_graph_checks(config))
    if args.task in {"3-4", "all"}:
        print("Tasks 3-4:", run_input_selection(config))


if __name__ == "__main__":
    main()
