"""Test Vector Module."""

from __future__ import annotations

from pathlib import Path
import random

from .models import CircuitIR, TestVectorSet


class RandomTestVectorGenerator:
    def generate(self, circuit: CircuitIR, sample_size: int, seed: int) -> TestVectorSet:
        if sample_size <= 0:
            raise ValueError("sample_size must be positive")
        rng = random.Random(seed)
        vectors = tuple(
            tuple(rng.randint(0, 1) for _ in circuit.primary_inputs)
            for _ in range(sample_size)
        )
        return TestVectorSet(circuit.primary_inputs, vectors, source="random", seed=seed)


class LegacyShieldTestVectorGenerator:
    """Reproduce the random-number consumption order of legacy SHIELD."""

    def generate(self, circuit: CircuitIR, sample_size: int, seed: int) -> TestVectorSet:
        if sample_size <= 0:
            raise ValueError("sample_size must be positive")
        rng = random.Random(seed)
        # Legacy __inputRand generated and discarded this many bits before
        # switchingActivity generated the characterization vectors.
        for _ in range(sample_size * len(circuit.primary_inputs)):
            rng.randint(0, 1)
        vectors = tuple(
            tuple(rng.randint(0, 1) for _ in circuit.primary_inputs)
            for _ in range(sample_size)
        )
        return TestVectorSet(
            circuit.primary_inputs, vectors, source="shield_legacy_random", seed=seed
        )


class TestVectorFileReader:
    """Reads whitespace/comma separated binary vectors; one vector per line."""

    def read(self, path: str | Path, primary_input_order: tuple[str, ...]) -> TestVectorSet:
        vectors = []
        for number, raw in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
            line = raw.split("#", 1)[0].strip().replace(",", " ")
            if not line:
                continue
            bits = tuple(int(bit) for bit in line.split()) if " " in line else tuple(int(bit) for bit in line)
            if any(bit not in (0, 1) for bit in bits) or len(bits) != len(primary_input_order):
                raise ValueError(f"invalid test vector at line {number}")
            vectors.append(bits)
        return TestVectorSet(primary_input_order, tuple(vectors), source=str(path))
