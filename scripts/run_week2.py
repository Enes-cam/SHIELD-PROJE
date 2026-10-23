#!/usr/bin/env python3
"""Run one or all week-2 tasks from the shared JSON configuration."""

from __future__ import annotations

import argparse

from shield.week2 import (
    RarityStabilityExperiment,
    load_week2_config,
    run_graph_checks,
    run_input_selection,
)


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
