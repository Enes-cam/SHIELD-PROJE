"""Graph Module, independent from NetworkX."""

from __future__ import annotations

from collections import defaultdict
from collections import deque

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


# Week 2 Task 2: Yalnızca CircuitGraph kullanan graph sorguları bu modülde tutulur.
def fanin_cone(graph: CircuitGraph, node: str) -> set[str]:
    """Return all nodes that can reach *node*, excluding *node* itself."""
    if node not in graph.nodes:
        raise KeyError(f"unknown graph node: {node}")
    visited: set[str] = set()
    stack = list(reversed(graph.predecessors.get(node, ())))
    while stack:
        current = stack.pop()
        if current in visited:
            continue
        visited.add(current)
        stack.extend(reversed(graph.predecessors.get(current, ())))
    return visited


def reachable_inputs(graph: CircuitGraph, node: str) -> set[str]:
    """Return primary inputs in the transitive fan-in of *node*."""
    primary_inputs = set(graph.primary_input_nodes)
    return fanin_cone(graph, node) & primary_inputs


def fanout_cone(graph: CircuitGraph, node: str) -> set[str]:
    """Return all nodes reachable from *node*, excluding *node* itself."""
    if node not in graph.nodes:
        raise KeyError(f"unknown graph node: {node}")
    visited: set[str] = set()
    stack = list(reversed(graph.successors.get(node, ())))
    while stack:
        current = stack.pop()
        if current in visited:
            continue
        visited.add(current)
        stack.extend(reversed(graph.successors.get(current, ())))
    return visited


def distance(graph: CircuitGraph, src: str, dst: str) -> int | None:
    """Return directed shortest-path edge count, or ``None`` if unreachable."""
    if src not in graph.nodes:
        raise KeyError(f"unknown graph node: {src}")
    if dst not in graph.nodes:
        raise KeyError(f"unknown graph node: {dst}")
    if src == dst:
        return 0
    queue = deque([(src, 0)])
    visited = {src}
    while queue:
        current, current_distance = queue.popleft()
        for successor in graph.successors.get(current, ()):
            if successor == dst:
                return current_distance + 1
            if successor not in visited:
                visited.add(successor)
                queue.append((successor, current_distance + 1))
    return None


def reverse_traversal_trace(
    graph: CircuitGraph, node: str, limit: int = 10
) -> tuple[tuple[str, tuple[str, ...]], ...]:
    """Trace the first steps of the same backward traversal as fanin_cone."""
    if node not in graph.nodes:
        raise KeyError(f"unknown graph node: {node}")
    trace: list[tuple[str, tuple[str, ...]]] = []
    visited: set[str] = set()
    stack = list(reversed(graph.predecessors.get(node, ())))
    while stack and len(trace) < limit:
        current = stack.pop()
        if current in visited:
            continue
        visited.add(current)
        stack.extend(reversed(graph.predecessors.get(current, ())))
        trace.append((current, tuple(stack)))
    return tuple(trace)
