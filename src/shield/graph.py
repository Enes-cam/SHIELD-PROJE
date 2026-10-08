"""Graph Module, independent from NetworkX."""

from __future__ import annotations

from collections import defaultdict

from .models import CircuitGraph, CircuitIR


class CircuitGraphBuilder:
    def build(self, circuit: CircuitIR) -> CircuitGraph:
        edges = circuit.connections
        predecessors: dict[str, list[str]] = defaultdict(list)
        successors: dict[str, list[str]] = defaultdict(list)
        for source, destination in edges:
            predecessors[destination].append(source)
            successors[source].append(destination)
        return CircuitGraph(
            nodes=circuit.nets,
            directed_edges=edges,
            primary_input_nodes=circuit.primary_inputs,
            primary_output_nodes=circuit.primary_outputs,
            predecessors={node: tuple(predecessors[node]) for node in circuit.nets},
            successors={node: tuple(successors[node]) for node in circuit.nets},
        )
