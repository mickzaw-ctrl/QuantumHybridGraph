# Changelog

## 0.1.0 - 2026-06-27

Initial GitHub-ready release.

### Added

- Checkpoint / restore of full kernel state: `QuantumHybridGraph.checkpoint()`
  and `save_checkpoint(path)` serialize the graph, evolution clock/history, RNG
  state, configuration, accelerator/analysis histories, NRE monitoring flags and
  the attached `AdaptiveNRE` agent (threshold, sandbox, quarantine/recovery
  trails, routing journal). `restore(state)` (in place) and the
  `from_checkpoint(path_or_dict)` classmethod rebuild the kernel faithfully and
  restore the RNG so the next operation is a deterministic continuation.
  `AdaptiveNRE.checkpoint_state()` / `restore_state()` back the agent portion.
  Example `examples/checkpoint_restore_example.py`.
- Recovery Procedures (self-healing back into production) for `AdaptiveNRE`:
  `assess_recovery` (evidence-based verdict using projected energy and a degree
  z-score outlier test), `recover_node` (re-attach + reconnect surviving edges +
  emit `announce_route` + journal), `auto_recover` (batch recover only ready
  nodes), `rollback_quarantine` (forced false-positive restore) and
  `recovery_report`. Recovery data is surfaced in the incident log and the
  dashboard Security payload. New operational runbook `docs/recovery_procedures.md`
  and example `examples/recovery_procedures_example.py`.
- BGP/SDN integration interface (`BGPSDNInterface`, `RoutingPolicyCommand`):
  maps graph operations to routing-policy update commands. `AdaptiveNRE`
  quarantine/restore now emit blackhole/announce policies; `RoutingPolicyCommand`
  renders BGP statements (`to_bgp`) and SDN flow rules (`to_sdn`); policies are
  journaled and exportable (`export_policy`). `QuantumHybridGraph.routing_interface`
  and `optimize_routes_via_qaoa` connect the Qiskit/PennyLane MaxClique backend
  to the control plane as a high-priority `install_path`.
- Network Reliability Engineer (NRE) agent: `AdaptiveNRE` gains Adaptation Logic
  (`node_energy`, `observe_energy`, `adapt_threshold` dynamically tuning
  `critical_energy_threshold` from historical network-energy data),
  `detect_energy_anomalies` for DoS/flood detection, energy-driven
  `auto_quarantine`, and an adaptive `reliability_report`.
- NRE security monitoring: persistent incident logging via
  `AdaptiveNRE.export_incident_log` (with append-mode audit trail) and a
  Security panel in the HTML dashboard (`export_dashboard_html(..., nre=nre)`)
  showing adaptive threshold, anomalies, quarantine zone and sandbox state.
- Per-cycle NRE monitoring wired into `QuantumHybridGraph.run_cycle`:
  `enable_nre_monitoring` / `disable_nre_monitoring` /
  `attach_reliability_engineer` / `run_nre_monitoring_step` record a security
  snapshot (and optional auto-quarantine + JSON audit trail) every cycle;
  exposed via `summary()["nre_incident_history"]`.
- Dashboard Security panel now charts the per-cycle monitoring history
  (adaptive threshold line + incident/quarantine bars), embedded from
  `kernel.nre_incident_history`.
- Dashboard Routing / Control Plane panel: when an `AdaptiveNRE` is passed to
  `export_dashboard_html(..., nre=nre)`, the dashboard now embeds the BGP/SDN
  command journal (`AdaptiveNRE.routing.as_dict()`) and renders it in a new
  Routing tab — per-command action/target/reason cards colour-coded by action,
  summary metrics, and an offline BGP ⇄ SDN/OpenFlow view toggle.

### Changed

- `QuantumHybridGraph.expand_qpa` now derives the new node id from the maximum
  existing integer node id (not the node count), so QPA growth stays correct
  after nodes are removed (e.g. by NRE quarantine).
- Intelligent Acceleration module: `GraphAcceleratorDetector.find_clique_accelerators`
  (`find_cliques`) and `find_k_core_accelerators` (k-core decomposition), plus
  `QuantumHybridGraph.intelligent_acceleration` combining accelerator detection
  with Small-World shortcut optimization in an `AcceleratorDetectionReport`.
- Real Qiskit statevector and PennyLane `default.qubit` execution paths with local fallback.
- Standalone interactive HTML dashboard export.
- Real-world benchmark suite using empirical NetworkX datasets.
- Adaptive optimizer loop for iterative graph improvement.
- QAOA circuit-depth selection for choosing `p`.
- QAOA refactor with external optimizer injection.
- Clique purity validation metric.
- Multi-start COBYLA optimization for stable QAOA convergence.
- QAOA-derived clique anchoring for deterministic shortcut optimization.

- Quantum-inspired graph growth via QPA-like preferential attachment.
- Grover-style clique search simulation.
- QAOA-like MaxClique optimizer.
- Accelerator detection for cliques, k-cores, communities and hub ego-networks.
- Network connection optimization with ranked shortcut candidates.
- Full graph/network analysis reports.
- Quantum experiment suite.
- Adapter scaffolding for future Qiskit and PennyLane backends.
- JSON export for backend-neutral MaxClique QUBO.
- Standalone SVG/HTML visualization.
- Tests and GitHub Actions CI.
