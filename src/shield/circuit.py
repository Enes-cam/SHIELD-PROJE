"""Circuit Module: the only production module allowed to read BENCH files."""

from __future__ import annotations

from collections import defaultdict, deque
from pathlib import Path
import re

from .models import CircuitIR, Gate


_IO_RE = re.compile(r"^(INPUT|OUTPUT)\s*\(\s*([^()]+)\s*\)$", re.IGNORECASE)
_GATE_RE = re.compile(r"^([^=\s]+)\s*=\s*([A-Za-z]+)\s*\(([^()]*)\)\s*$")
SUPPORTED_GATES = {"AND", "OR", "NAND", "NOR", "NOT", "BUFF", "BUF", "XOR", "XNOR"}


class BenchParseError(ValueError):
    pass


class BenchCircuitReader:
    def read(self, path: str | Path) -> CircuitIR:
        source = Path(path)
        inputs: list[str] = []
        outputs: list[str] = []
        gates: list[Gate] = []

        for line_number, raw_line in enumerate(source.read_text(encoding="utf-8").splitlines(), 1):
            line = raw_line.split("#", 1)[0].strip()
            if not line:
                continue
            io_match = _IO_RE.match(line)
            if io_match:
                kind, net = io_match.groups()
                (inputs if kind.upper() == "INPUT" else outputs).append(net.strip())
                continue
            gate_match = _GATE_RE.match(line)
            if not gate_match:
                raise BenchParseError(f"{source}:{line_number}: invalid BENCH statement: {raw_line!r}")
            output_net, gate_type, raw_inputs = gate_match.groups()
            gate_type = gate_type.upper()
            if gate_type not in SUPPORTED_GATES:
                raise BenchParseError(f"{source}:{line_number}: unsupported gate type {gate_type}")
            gate_type = "BUFF" if gate_type == "BUF" else gate_type
            input_nets = tuple(item.strip() for item in raw_inputs.split(",") if item.strip())
            expected = 1 if gate_type in {"NOT", "BUFF"} else 2
            if len(input_nets) < expected:
                raise BenchParseError(f"{source}:{line_number}: {gate_type} has too few inputs")
            gates.append(Gate(output_net, gate_type, input_nets, output_net))

        if not inputs or not outputs:
            raise BenchParseError(f"{source}: circuit must declare at least one INPUT and OUTPUT")
        order = self._topological_order(inputs, gates, source)
        all_nets = list(dict.fromkeys([*inputs, *(n for g in gates for n in (*g.input_nets, g.output_net)), *outputs]))
        connections = tuple(
            (input_net, gate.output_net)
            for gate in gates
            for input_net in gate.input_nets
        )
        return CircuitIR(
            name=source.stem,
            primary_inputs=tuple(inputs),
            primary_outputs=tuple(outputs),
            gates=tuple(gates),
            nets=tuple(all_nets),
            connections=connections,
            topological_gate_order=tuple(order),
        )

    @staticmethod
    def _topological_order(inputs: list[str], gates: list[Gate], source: Path) -> list[str]:
        driver: dict[str, str] = {}
        gate_by_id = {gate.gate_id: gate for gate in gates}
        for gate in gates:
            if gate.output_net in driver:
                raise BenchParseError(f"{source}: multiple drivers for net {gate.output_net}")
            driver[gate.output_net] = gate.gate_id

        dependencies: dict[str, set[str]] = {gate.gate_id: set() for gate in gates}
        consumers: dict[str, set[str]] = defaultdict(set)
        known_inputs = set(inputs)
        for gate in gates:
            for net in gate.input_nets:
                if net in driver:
                    dependencies[gate.gate_id].add(driver[net])
                    consumers[driver[net]].add(gate.gate_id)
                elif net not in known_inputs:
                    raise BenchParseError(f"{source}: net {net} is used but never driven")

        queue = deque(gid for gid in gate_by_id if not dependencies[gid])
        result: list[str] = []
        processed: set[str] = set()
        while queue:
            gate_id = queue.popleft()
            if gate_id in processed:
                continue
            processed.add(gate_id)
            result.append(gate_id)
            for consumer in consumers[gate_id]:
                dependencies[consumer].discard(gate_id)
                if not dependencies[consumer]:
                    queue.append(consumer)
        if len(result) != len(gates):
            raise BenchParseError(f"{source}: combinational cycle detected")
        return result
