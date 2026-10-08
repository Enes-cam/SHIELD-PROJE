"""Optimization Module. The modular baseline uses deterministic greedy set cover."""

from __future__ import annotations

import random

from .models import CandidatePool, CoverageMatrix, ProblemDefinition, SelectedTestSet


def _candidate_constraints(
    pool: CandidatePool, problem: ProblemDefinition
) -> tuple[list[str], list[str]]:
    available = {candidate.candidate_id for candidate in pool.candidates}
    required = list(problem.constraints.get("required_candidate_ids", ()))
    forbidden = set(problem.constraints.get("forbidden_candidate_ids", ()))
    unknown = (set(required) | forbidden) - available
    if unknown:
        raise ValueError(f"unknown candidate ids in constraints: {sorted(unknown)}")
    if set(required) & forbidden:
        raise ValueError("a candidate cannot be both required and forbidden")
    optional = [candidate.candidate_id for candidate in pool.candidates if candidate.candidate_id not in forbidden]
    return required, optional


def _build_result(
    pool: CandidatePool,
    matrix: CoverageMatrix,
    selected: list[str],
    problem_type: str,
) -> SelectedTestSet:
    selected = list(dict.fromkeys(selected))
    covered = set().union(*(matrix.covered_targets(cid) for cid in selected)) if selected else set()
    coverage = len(covered) / max(len(matrix.target_order), 1)
    lookup = {candidate.candidate_id: candidate for candidate in pool.candidates}
    objective = len(selected) if problem_type == "minimum_test_set" else len(covered)
    return SelectedTestSet(
        selected_test_ids=tuple(selected),
        selected_test_vectors=tuple(lookup[cid].test_vector for cid in selected),
        test_set_size=len(selected),
        coverage=coverage,
        objective_value=float(objective),
    )


class GreedyCoverageOptimizer:
    method = "greedy"

    def optimize(
        self,
        pool: CandidatePool,
        matrix: CoverageMatrix,
        problem: ProblemDefinition,
    ) -> SelectedTestSet:
        if problem.problem_type not in {"minimum_test_set", "maximum_coverage_fixed_budget"}:
            raise ValueError(f"unsupported problem_type: {problem.problem_type}")
        required, allowed = _candidate_constraints(pool, problem)
        candidates = {cid for cid in allowed if cid not in required}
        remaining = set(matrix.target_order)
        selected: list[str] = list(required)
        for cid in selected:
            remaining -= matrix.covered_targets(cid)
        budget = problem.test_budget
        if problem.problem_type == "maximum_coverage_fixed_budget" and budget is None:
            raise ValueError("maximum_coverage_fixed_budget requires test_budget")
        if budget is not None and len(selected) > budget:
            raise ValueError("required candidates exceed test_budget")

        while remaining and candidates and (budget is None or len(selected) < budget):
            best_id = max(
                candidates,
                key=lambda cid: (len(matrix.covered_targets(cid) & remaining), -int(cid[1:]) if cid[1:].isdigit() else 0),
            )
            gain = matrix.covered_targets(best_id) & remaining
            if not gain:
                break
            selected.append(best_id)
            remaining -= gain
            candidates.remove(best_id)

        return _build_result(pool, matrix, selected, problem.problem_type)


class DiscretePSOOptimizer:
    """PSO strategy over candidate IDs while preserving the module contract.

    Particles hold a fixed-size list of candidate indices. Personal and global
    best solutions guide per-slot replacement. For minimum-test-set problems,
    budgets are tried from one upward and the first full-coverage result wins.
    """

    method = "pso"

    def __init__(self, seed: int = 42, particles: int = 40, iterations: int = 100) -> None:
        if particles <= 0 or iterations <= 0:
            raise ValueError("particles and iterations must be positive")
        self._seed = seed
        self._particles = particles
        self._iterations = iterations

    def optimize(
        self,
        pool: CandidatePool,
        matrix: CoverageMatrix,
        problem: ProblemDefinition,
    ) -> SelectedTestSet:
        if problem.problem_type not in {"minimum_test_set", "maximum_coverage_fixed_budget"}:
            raise ValueError(f"unsupported problem_type: {problem.problem_type}")
        required, allowed = _candidate_constraints(pool, problem)
        optional = [cid for cid in allowed if cid not in required]
        if problem.problem_type == "maximum_coverage_fixed_budget":
            if problem.test_budget is None:
                raise ValueError("maximum_coverage_fixed_budget requires test_budget")
            return self._search(pool, matrix, problem, required, optional, problem.test_budget)

        max_budget = int(problem.constraints.get("max_test_set_size", min(20, len(allowed))))
        best = _build_result(pool, matrix, required, problem.problem_type)
        for budget in range(max(len(required), 1), max_budget + 1):
            candidate = self._search(pool, matrix, problem, required, optional, budget)
            if candidate.coverage > best.coverage or (
                candidate.coverage == best.coverage and candidate.test_set_size < best.test_set_size
            ):
                best = candidate
            if candidate.coverage == 1.0:
                return candidate
        return best

    def _search(self, pool, matrix, problem, required, optional, budget):
        if budget < len(required):
            raise ValueError("required candidates exceed test_budget")
        slots = budget - len(required)
        if slots == 0 or not optional:
            return _build_result(pool, matrix, required, problem.problem_type)
        rng = random.Random(self._seed + budget)

        def random_position():
            if slots <= len(optional):
                return rng.sample(optional, slots)
            return [rng.choice(optional) for _ in range(slots)]

        def score(position):
            ids = list(dict.fromkeys([*required, *position]))
            covered = set().union(*(matrix.covered_targets(cid) for cid in ids)) if ids else set()
            return len(covered), -len(ids)

        positions = [random_position() for _ in range(self._particles)]
        personal = [list(position) for position in positions]
        personal_scores = [score(position) for position in positions]
        global_index = max(range(self._particles), key=lambda i: personal_scores[i])
        global_best = list(personal[global_index])
        global_score = personal_scores[global_index]

        for iteration in range(self._iterations):
            inertia = 0.9 - 0.5 * (iteration / max(self._iterations - 1, 1))
            for index, position in enumerate(positions):
                for slot in range(slots):
                    draw = rng.random()
                    if draw < 0.35 * inertia:
                        position[slot] = rng.choice(optional)
                    elif draw < 0.70:
                        position[slot] = personal[index][slot]
                    else:
                        position[slot] = global_best[slot]
                current_score = score(position)
                if current_score > personal_scores[index]:
                    personal[index] = list(position)
                    personal_scores[index] = current_score
                if current_score > global_score:
                    global_best = list(position)
                    global_score = current_score
        return _build_result(pool, matrix, [*required, *global_best], problem.problem_type)
