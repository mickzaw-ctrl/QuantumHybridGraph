# Contributing

Thank you for your interest in QuantumHybridGraph.

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -e .[dev]
pytest
```

## Development guidelines

- Keep the core module dependency-light: `numpy` and `networkx` are required; Qiskit/PennyLane remain optional.
- Add tests for every public API change.
- Prefer deterministic examples with a fixed `seed`.
- Do not commit generated files such as `quantum_hybrid_graph.html`, `max_clique_qubo.json`, or cache directories.

## Quantum backend work

Real Qiskit/PennyLane integration should be added through the adapter layer:

- `QuantumBackendAdapter`
- `QiskitAdapter`
- `PennyLaneAdapter`
- `QuantumBackendRegistry`
