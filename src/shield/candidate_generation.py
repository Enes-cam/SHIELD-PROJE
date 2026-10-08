"""Candidate Generation Module."""

from __future__ import annotations

import random

from .models import Candidate, CandidatePool, CircuitIR, SelectedInputs


class RandomSelectedInputCandidateGenerator:
    method = "random_selected_inputs"

    def __init__(self, candidate_count: int = 100, seed: int = 42) -> None:
        if candidate_count <= 0:
            raise ValueError("candidate_count must be positive")
        self._candidate_count = candidate_count
        self._seed = seed

    def generate(
        self,
        circuit: CircuitIR,
        selected_inputs: SelectedInputs,
    ) -> CandidatePool:
        rng = random.Random(self._seed)
        selected = set(selected_inputs.input_ids)
        seen: set[tuple[int, ...]] = set()
        candidates = []
        attempts = 0
        max_attempts = max(self._candidate_count * 20, 100)
        while len(candidates) < self._candidate_count and attempts < max_attempts:
            attempts += 1
            vector = tuple(rng.randint(0, 1) if node in selected else 0 for node in circuit.primary_inputs)
            if vector in seen:
                continue
            seen.add(vector)
            candidates.append(Candidate(f"T{len(candidates) + 1}", vector))
        return CandidatePool(circuit.primary_inputs, tuple(candidates), self.method)


class RandomFullInputCandidateGenerator:
    """Compatibility pool for the active legacy code, which randomizes all PIs."""

    method = "random_full_inputs"

    def __init__(self, candidate_count: int = 100, seed: int = 42) -> None:
        if candidate_count <= 0:
            raise ValueError("candidate_count must be positive")
        self._candidate_count = candidate_count
        self._seed = seed

    def generate(self, circuit: CircuitIR, selected_inputs: SelectedInputs) -> CandidatePool:
        del selected_inputs  # Contract input retained; legacy behavior uses every PI.
        rng = random.Random(self._seed)
        seen: set[tuple[int, ...]] = set()
        candidates = []
        attempts = 0
        max_attempts = max(self._candidate_count * 20, 100)
        while len(candidates) < self._candidate_count and attempts < max_attempts:
            attempts += 1
            vector = tuple(rng.randint(0, 1) for _ in circuit.primary_inputs)
            if vector in seen:
                continue
            seen.add(vector)
            candidates.append(Candidate(f"T{len(candidates) + 1}", vector))
        return CandidatePool(circuit.primary_inputs, tuple(candidates), self.method)
