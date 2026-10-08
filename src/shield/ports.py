"""Public module interfaces used for dependency inversion.

Modules may depend on these contracts, but never on another module's concrete
implementation or private state.
"""

from __future__ import annotations

from typing import Protocol

from .models import CircuitIR, SimulationResults, TestVectorSet


class SimulationPort(Protocol):
    """Public contract exposed by any logic-simulation implementation."""

    def simulate(self, circuit: CircuitIR, vectors: TestVectorSet) -> SimulationResults:
        ...

