# QuantumHybridGraph

QuantumHybridGraph is a quantum-inspired hybrid evolutionary graph toolkit for network analysis, accelerator detection, connection optimization and algorithm experiments.

It does **not** require a real quantum computer. The current implementation runs with `numpy` and `networkx`; optional Qiskit and PennyLane adapters can execute QAOA-style MaxClique experiments on local statevector simulators when those SDKs are installed.

## Features

- QPA-like quantum preferential attachment graph growth.
- Grover-style clique detection simulation.
- QAOA-like MaxClique optimization.
- Accelerator detection in graphs:
  - cliques,
  - k-core components,
  - modularity communities,
  - hub ego-networks.
- Network connection optimization with ranked shortcut candidates.
- Intelligent Acceleration module: clique + k-core detection combined with
  Small-World shortcut optimization in a single report.
- Full graph/network analysis reports.
- Quantum-inspired experiment suite.
- Optional Qiskit and PennyLane adapters for QAOA-style MaxClique statevector execution.
- QUBO export for MaxClique.
- BGP/SDN integration interface that maps graph operations (quarantine, restore,
  optimized clique paths) to routing-policy update commands.
- Standalone HTML/SVG graph visualization.

## Installation

```bash
git clone https://github.com/YOUR_USERNAME/quantum-hybrid-graph.git
cd quantum-hybrid-graph
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -e .
```

For development:

```bash
pip install -e .[dev]
pytest
```

Optional future quantum SDK dependencies:

```bash
pip install -e .[quantum]
```

## Quick start

```python
from quantum_hybrid_graph import QuantumHybridGraph

kernel = QuantumHybridGraph(initial_nodes=10, clique_threshold=3, seed=42)

for _ in range(10):
    kernel.run_cycle()

print(kernel.summary())
```

## Stable QAOA optimization with COBYLA

`QAOAOptimizer` now uses a multi-start COBYLA optimization path by default when SciPy is available, with a dependency-free fallback when SciPy is not installed.

```python
from quantum_hybrid_graph import QAOAOptimizer

optimizer = QAOAOptimizer(graph, p_layers=2, seed=42)
gamma, beta, bitstring = optimizer.optimize_cobyla(
    iterations=120,
    restarts=4,
)

print(optimizer.last_optimizer_metadata)
```

The optimizer records metadata including expected energy, selected bitstring, raw clique purity and projected clique purity.

## QAOA circuit depth selection

Select the QAOA circuit depth `p` automatically by sweeping candidate depths and balancing solution quality against runtime/complexity:

```python
from quantum_hybrid_graph import QuantumHybridGraph

kernel = QuantumHybridGraph(initial_nodes=0, seed=42)
kernel.graph.add_edges_from([(0, 1), (0, 2), (1, 2), (2, 3)])

result = kernel.select_circuit_depth(
    min_p=1,
    max_p=4,
    iterations=20,
    backend="local",  # or "qiskit" / "pennylane" when installed
)

print(result.recommendation)
print("Selected p:", kernel.qaoa_layers)
```

The selector evaluates each depth with QAOA-like MaxClique optimization, scores clique quality, energy, runtime and depth complexity, then updates `kernel.qaoa_layers`.

## Adaptive optimizer loop

Run a closed-loop optimizer that repeatedly analyzes the graph, proposes shortcut edges, evaluates an objective function and accepts or reverts changes:

```python
from quantum_hybrid_graph import QuantumHybridGraph

kernel = QuantumHybridGraph(initial_nodes=0, clique_threshold=3, seed=42)
kernel.graph.add_edges_from([(0, 1), (1, 2), (3, 4), (4, 5)])

result = kernel.adaptive_optimize(
    max_iterations=5,
    add_edges_per_step=1,
    max_candidates=200,
    patience=3,
)

print(result.as_dict())
```

The optimizer objective rewards global efficiency, shorter paths and clustering while penalizing excessive density and disconnected components.

## Real-world benchmarks

Run benchmarks on empirical datasets bundled with NetworkX:

```python
from quantum_hybrid_graph import RealWorldBenchmarkSuite

suite = RealWorldBenchmarkSuite(seed=42)
report = suite.run(top_n=5, add_edges=2)
print(report)

suite.export_json("real_world_benchmarks.json")
suite.export_markdown("real_world_benchmarks.md")
```

Bundled datasets may include:

- Zachary's Karate Club,
- Florentine families,
- Davis Southern Women,
- Les Miserables, depending on the installed NetworkX version.

## Intelligent Acceleration module

Detect high-throughput structures and reduce inter-cluster latency in one call.
The module runs two detection algorithms and then optimizes Small-World shortcuts:

- **Detection**
  - `find_cliques`: fully connected, high-throughput clusters.
  - k-core decomposition: cohesive, resilient processing cores.
- **Shortcut optimization**: adds long-range edges between clusters to reduce
  communication latency and increase global efficiency (Small-World effect).

```python
from quantum_hybrid_graph import GraphAcceleratorDetector, QuantumHybridGraph

kernel = QuantumHybridGraph(initial_nodes=0, clique_threshold=4, seed=11)
kernel.graph.add_edges_from((a, b) for i, a in enumerate(range(5)) for b in range(i + 1, 5))
kernel.graph.add_edges_from((a, b) for i, a in enumerate(range(5, 10)) for b in range(i + 1, 10))
kernel.graph.add_edge(4, 5)  # single bridge -> long cross-cluster paths

# Raw detection algorithms
detector = GraphAcceleratorDetector(kernel.graph)
detector.find_clique_accelerators(min_size=5)   # clique clusters
detector.find_k_core_accelerators(min_size=5)   # k-core backbone

# Detection + Small-World shortcut optimization in one report
report = kernel.intelligent_acceleration(min_size=4, shortcut_edges=2)
print(report.as_dict()["small_world_delta"])
```

See `examples/intelligent_acceleration_example.py` for a full walkthrough.

## Network Reliability Engineer (NRE) agent

`AdaptiveNRE` is the agent responsible for network stability and security:

- **Adaptation Logic**: `critical_energy_threshold` is dynamically adjusted from
  historical network-energy data (`adapt_threshold`), so quarantine decisions
  stay calibrated to how loaded the network normally is.
- **Self-Healing**:
  - **Quarantine**: `quarantine_node(node_id)` / `auto_quarantine()` isolate
    nodes showing DoS/flood anomalies (`dos_flood_suspect`).
  - **Sandbox**: infected nodes are moved into `self.sandbox` (an isolated
    graph), enabling threat analysis without interrupting the main network.
- **Recovery Procedures**: evidence-based self-healing back into production.
  `assess_recovery(node)` decides if a node is safe to restore (projected energy
  + degree z-score outlier test); `recover_node()` / `auto_recover()` re-attach
  recovered nodes and reconnect only their surviving edges; `rollback_quarantine()`
  force-restores a false positive; `recovery_report()` summarizes readiness. A
  flood/DoS hub stays deferred until its conditions clear.

```python
from quantum_hybrid_graph import AdaptiveNRE, QuantumHybridGraph

kernel = QuantumHybridGraph(initial_nodes=0, seed=13)
kernel.graph.add_edges_from([(i, i + 1) for i in range(12)])
for i in range(13):
    kernel.graph.add_edge(99, i)  # flooding / DoS hub

nre = AdaptiveNRE(kernel, critical_energy_threshold=0.85, adaptation_rate=0.4)
nre.adapt_threshold()             # tune threshold from history
nre.detect_energy_anomalies()     # flag DoS/flood suspects
nre.auto_quarantine(limit=1)      # isolate into sandbox
print(nre.analyze_sandbox())

# Persistent incident logging (audit trail) + dashboard Security panel
nre.export_incident_log("nre_incident_log.json", append=True)
kernel.export_dashboard_html("nre_security_dashboard.html", nre=nre)
```

- **Incident logging**: `export_incident_log(path, append=True)` writes a
  JSON audit trail (adaptive threshold state, energy history, anomalies,
  quarantine actions, sandbox contents).
- **Dashboard Security panel**: pass an `AdaptiveNRE` to
  `export_dashboard_html(..., nre=nre)` to add a live Security tab with the
  adaptive threshold, detected anomalies, quarantine zone and sandbox state. The
  panel also charts the **per-cycle monitoring history** (adaptive threshold
  line plus incident/quarantine bars) when monitoring has been run.
- **Per-cycle monitoring**: wire the NRE agent into the evolution loop so every
  `run_cycle()` adapts the threshold, records a security snapshot and optionally
  auto-quarantines anomalies and appends a JSON audit trail:

  ```python
  kernel = QuantumHybridGraph(initial_nodes=6, clique_threshold=3, seed=7)
  kernel.enable_nre_monitoring(
      auto_quarantine=True,
      quarantine_limit=1,
      incident_log_path="cycle_incidents.json",
      critical_energy_threshold=0.8,
  )
  for _ in range(10):
      kernel.run_cycle()  # logs an incident snapshot every cycle

  print(kernel.nre_incident_history[-1])
  ```

  See `examples/nre_run_cycle_monitoring_example.py` for a full walkthrough.

See `examples/network_reliability_engineer_example.py`,
`examples/nre_dashboard_example.py` and
`examples/recovery_procedures_example.py` for full walkthroughs. The operational
runbook for incident recovery (roles, failure scenarios, restart/state rebuild,
verification checklist) is in [`docs/recovery_procedures.md`](docs/recovery_procedures.md).

## Checkpoint / restore (state recovery)

Kernel state lives in memory. Take periodic checkpoints and rebuild after a
restart for disaster recovery:

```python
from quantum_hybrid_graph import QuantumHybridGraph

kernel.save_checkpoint("kernel_checkpoint.json")
# ... process restart ...
kernel = QuantumHybridGraph.from_checkpoint("kernel_checkpoint.json")
```

A checkpoint captures the graph, evolution clock/history, the RNG state, the
configuration and the attached `AdaptiveNRE` agent (threshold, sandbox,
quarantine/recovery trails, BGP/SDN routing journal). Restore reproduces the
graph, NRE state and RNG faithfully, so the next deterministic operation is a
continuation. Use `checkpoint()` for the dict form and `restore(state)` to
rebuild in place. See `examples/checkpoint_restore_example.py`.

## Algorithmic Architect role

The technical leadership role for the project is documented in:

```text
docs/team/algorithmic_architect.md
```

This role owns graph mathematics, optimization stability, thermodynamic-style system metrics, reproducibility and predictable iteration behavior in `quantum_hybrid_graph.py`.

## NexusGraph Dynamics technical reference

The technical reference manual for the physics-inspired graph architecture is available at:

```text
docs/nexusgraph_dynamics_technical_reference.md
```

It defines the Core Kernel, graph Hamiltonian, expansion constant `Λ`, cost edges `J`, accelerator dynamics, QAOA layer, adaptive optimization and reliability sandbox model.

## Project execution matrix

The implementation phases, lead roles and README-linked tasks are documented in:

```text
docs/project_execution_matrix.md
```

It maps Development, Benchmarks, Deployment and Presentation to the responsible roles and concrete deliverables.

## Deployment Core — Environment Architects

The deployment architecture roles are documented in:

```text
docs/team/deployment_core_environment_architects.md
```

This document defines the Systems Integration Specialist and Data Visualisation Engineer roles, covering customer environment integration, deployment profiles, algorithm configuration constants, dashboard UX and executive-facing visualization.

## Strategic Core — Business Architects

The business architecture roles are documented in:

```text
docs/team/strategic_core_business_architects.md
```

This document defines the Product Manager / Technical PM and Investor Relations & Sales roles, including product lifecycle ownership, fundraising narrative, pilot packaging and deeptech sales positioning.

## Quantum-Inspired Software Engineer role

The quantum software engineering role for the project is documented in:

```text
docs/team/quantum_inspired_software_engineer.md
```

This role owns Qiskit/PennyLane integration, QAOA-style MaxClique, QUBO/Ising conversion, circuit-depth selection, clique purity validation and the quantum-inspired product differentiator.

## Chatbot platform UI

A standalone product platform mockup with an embedded rule-based chatbot is available at:

```text
docs/platform/chatbot_platform.html
```

It presents the product modules, investor status, pilot package and answers questions about dashboard, Qiskit/PennyLane, benchmarks, social trend forecasting and valuation.

## Dashboard / UI

Export a standalone interactive HTML dashboard:

```python
from quantum_hybrid_graph import QuantumHybridGraph

kernel = QuantumHybridGraph(initial_nodes=10, clique_threshold=3, seed=42)
for _ in range(10):
    kernel.run_cycle()

kernel.export_dashboard_html("quantum_hybrid_graph_dashboard.html")
```

The dashboard includes:

- graph visualization,
- core metrics,
- full analysis sections,
- accelerator list,
- ranked connection candidates,
- a Security panel (when an `AdaptiveNRE` is passed via `nre=`) with the
  adaptive threshold, anomalies, quarantine zone and per-cycle monitoring chart,
- a Routing / Control Plane panel auditing the BGP/SDN command journal, with an
  offline BGP ⇄ SDN/OpenFlow view toggle,
- quantum backend status,
- embedded JSON data.

## Analyze a graph

```python
report = kernel.analyze_network(top_n=5)

print(report.overview)
print(report.centrality["top_pagerank"])
print(report.recommendations)
```

Export analysis:

```python
kernel.export_analysis_json("graph_analysis_report.json")
```

## Detect accelerators

```python
accelerators = kernel.detect_accelerators(min_size=4, min_density=0.7)

for accelerator in accelerators:
    print(accelerator.as_dict())
```

## Optimize network connections

Preview proposed edges without modifying the graph:

```python
proposals = kernel.propose_connection_optimizations(add_edges=3)
for edge in proposals:
    print(edge.as_dict())
```

Add the best edges:

```python
added = kernel.optimize_connections(add_edges=2)
```

## Run quantum-inspired experiments

```python
results = kernel.run_quantum_experiments(
    include_full_suite=False,
    export_path="quantum_experiments.json",
)

print(results)
```

Or use the experiment suite directly:

```python
from quantum_hybrid_graph import QuantumExperimentSuite

suite = QuantumExperimentSuite(seed=42)
results = suite.run_all_as_dict()
```

## Qiskit/PennyLane integration

Check backend availability:

```python
print(kernel.quantum_backend_status())
```

Export MaxClique QUBO:

```python
kernel.export_max_clique_qubo("max_clique_qubo.json")
```

Solve through the backend adapter interface:

```python
result = kernel.solve_max_clique_with_backend("local", iterations=50)
print(result)
```

See [`docs/backend-integration.md`](docs/backend-integration.md) for backend details, installation instructions and limitations.

## Integration & protocols (BGP/SDN)

The `BGPSDNInterface` maps graph and security operations onto routing-policy
update commands so decisions can be pushed to a BGP speaker or SDN controller:

- **BGP/SDN Interface**: the NRE translates node quarantine into a
  `blackhole`/`withdraw` policy and node restore into an `announce` policy.
- **Quantum Backend**: the Qiskit/PennyLane (or local) MaxClique solver feeds the
  optimal cluster back into the control plane as a high-priority `install_path`.

```python
from quantum_hybrid_graph import QuantumHybridGraph

kernel = QuantumHybridGraph(initial_nodes=0, clique_threshold=3, seed=7)
kernel.graph.add_edges_from((a, b) for i, a in enumerate(range(4)) for b in range(i + 1, 4))
kernel.graph.add_edges_from([(3, 4), (4, 5)])

nre = kernel.attach_reliability_engineer(critical_energy_threshold=0.85)
nre.adapt_threshold()
event = nre.auto_quarantine(limit=1, adapt=False)[0]
print(event["bgp"])  # route ... community 65535:666  # blackhole (...)

# Quantum Backend MaxClique -> optimal routing path
result = kernel.optimize_routes_via_qaoa(backend="local", iterations=30)
print(result["bgp"])   # install path [...]
print(result["sdn"])   # {'match': {'path': [...]}, 'action': 'FORWARD', ...}

# Export the journaled policy for the control plane
nre.routing.export_policy("routing_policy.txt", fmt="bgp")
nre.routing.export_policy("routing_policy.json", fmt="sdn")
```

See `examples/bgp_sdn_integration_example.py` for a full walkthrough.

## Run tests

```bash
pytest
```

Expected result:

```text
15 passed
```

## Repository structure

```text
.
├── quantum_hybrid_graph.py
├── tests/
│   └── test_quantum_hybrid_graph.py
├── examples/
│   └── quantum_backend_example.py
├── docs/
│   ├── backend-integration.md
│   └── investor/
│       ├── investor_pitch_deck_en.html
│       ├── investor_pitch_deck_en.md
│       └── valuation_memo_en.md
├── .github/workflows/ci.yml
├── pyproject.toml
├── requirements.txt
├── requirements-dev.txt
├── README.md
├── CHANGELOG.md
├── CONTRIBUTING.md
└── LICENSE
```

## Investor materials

Investor materials are available in `docs/investor/`:

- `investor_pitch_deck_en.html`
- `investor_pitch_deck_en.md`
- `valuation_memo_en.md`

## License

MIT
