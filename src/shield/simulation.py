"""Logic Simulation Module."""

from __future__ import annotations

from .models import Bit, CircuitIR, SimulationResults, TestVectorSet


def _evaluate_gate(gate_type: str, inputs: list[Bit]) -> Bit:
    if gate_type == "NOT":
        return 1 - inputs[0]
    if gate_type == "BUFF":
        return inputs[0]
    if gate_type == "AND":
        return int(all(inputs))
    if gate_type == "NAND":
        return 1 - int(all(inputs))
    if gate_type == "OR":
        return int(any(inputs))
    if gate_type == "NOR":
        return 1 - int(any(inputs))
    if gate_type == "XOR":
        return sum(inputs) % 2
    if gate_type == "XNOR":
        return 1 - (sum(inputs) % 2)
    raise ValueError(f"unsupported gate type: {gate_type}")


class LogicSimulator:
    def simulate(self, circuit: CircuitIR, vectors: TestVectorSet) -> SimulationResults:
        if vectors.primary_input_order != circuit.primary_inputs:
            raise ValueError("TestVectorSet primary_input_order does not match CircuitIR")
        gate_by_id = circuit.gate_by_id
        all_results = []
        for vector in vectors.test_vectors:
            if len(vector) != len(circuit.primary_inputs):
                raise ValueError("test vector width does not match circuit input count")
            values = dict(zip(circuit.primary_inputs, vector))
            for gate_id in circuit.topological_gate_order:
                gate = gate_by_id[gate_id]
                values[gate.output_net] = _evaluate_gate(gate.gate_type, [values[n] for n in gate.input_nets])
            all_results.append(values)
        return SimulationResults(
            circuit.primary_inputs,
            vectors.test_vectors,
            tuple(all_results),
            tuple(gate.output_net for gate in circuit.gates),
        )
