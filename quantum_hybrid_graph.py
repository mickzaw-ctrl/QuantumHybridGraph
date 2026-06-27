#!/usr/bin/env python3
"""
QuantumHybridGraph – a hybrid evolutionary graph kernel inspired by quantum algorithms.

This file is a working, cleaned-up version of the user's original code.
It does not run on a real quantum computer; it simulates the following ideas:

  Classical Arena Kernel             → Quantum-inspired analogue
  -----------------------------------------------------------------------
  Preferential attachment            → Quantum Preferential Attachment (QPA)
  Clique detection                    → Grover / amplitude amplification
  Small-world shortcuts               → entanglement-like shortcuts as long-range edges
  Recursive self-improvement          → QAOA-like variational optimization

Requirements: numpy, networkx
Optional HTML visualization: no extra libraries required.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations
from math import asin, comb, cos, pi, sin, sqrt
import importlib.util
import json
import time
from typing import Any, Callable

import networkx as nx
import numpy as np


# ======================================================================
# Basic classical graph kernel
# ======================================================================


@dataclass
class UniverseKernel:
    """Minimal evolutionary graph kernel.

    It is intentionally implemented locally so the module can run standalone
    without importing an external `universe_kernel`.
    """

    initial_nodes: int = 1
    seed: int | None = None
    graph: nx.Graph = field(init=False)
    cycle: int = field(default=0, init=False)
    history: list[dict[str, Any]] = field(default_factory=list, init=False)

    def __post_init__(self) -> None:
        self.rng = np.random.default_rng(self.seed)
        self.graph = nx.Graph()
        self.graph.add_nodes_from(range(max(0, self.initial_nodes)))
        # A small connected base instead of isolated nodes.
        if self.initial_nodes > 1:
            for i in range(self.initial_nodes - 1):
                self.graph.add_edge(i, i + 1)
        self._record_history()

    def expand(self, edges_per_node: int = 1) -> int:
        """Add a new node using classical preferential attachment."""
        new_node = self.graph.number_of_nodes()
        self.graph.add_node(new_node)

        if new_node == 0:
            self._record_history()
            return new_node

        existing = list(range(new_node))
        degrees = np.array([self.graph.degree(i) + 1 for i in existing], dtype=float)
        probs = degrees / degrees.sum()
        m = min(max(1, edges_per_node), len(existing))
        targets = self.rng.choice(existing, size=m, replace=False, p=probs)
        for target in np.atleast_1d(targets):
            self.graph.add_edge(new_node, int(target))
        return new_node

    def _record_history(self) -> None:
        n = self.graph.number_of_nodes()
        m = self.graph.number_of_edges()
        clustering = nx.average_clustering(self.graph) if n > 1 else 0.0
        try:
            avg_path = nx.average_shortest_path_length(self.graph) if n > 1 and nx.is_connected(self.graph) else None
        except nx.NetworkXError:
            avg_path = None
        self.history.append(
            {
                "cycle": self.cycle,
                "nodes": n,
                "edges": m,
                "clustering": clustering,
                "average_path_length": avg_path,
            }
        )

    def run_cycle(self) -> None:
        self.expand()
        self.cycle += 1
        self._record_history()

    def summary(self) -> dict[str, Any]:
        n = self.graph.number_of_nodes()
        m = self.graph.number_of_edges()
        return {
            "cycle": self.cycle,
            "nodes": n,
            "edges": m,
            "density": nx.density(self.graph) if n > 1 else 0.0,
            "clustering": nx.average_clustering(self.graph) if n > 1 else 0.0,
            "connected": nx.is_connected(self.graph) if n > 0 else False,
        }


class IntelligenceAcceleration(UniverseKernel):
    """Classical variant: detects large cliques and adds small-world shortcuts."""

    def __init__(self, initial_nodes: int = 1, clique_threshold: int = 5, seed: int | None = None):
        super().__init__(initial_nodes=initial_nodes, seed=seed)
        self.clique_threshold = clique_threshold
        self.accelerators: list[list[int]] = []
        self.accelerator_history: list[int] = []

    def detect_accelerators(self) -> None:
        cliques = [list(c) for c in nx.find_cliques(self.graph) if len(c) >= self.clique_threshold]
        self.accelerators = cliques
        self.accelerator_history.append(len(cliques))

    def add_small_world_shortcut(self) -> None:
        if self.graph.number_of_nodes() < 4:
            return
        nodes = list(self.graph.nodes)
        for _ in range(8):
            a, b = self.rng.choice(nodes, size=2, replace=False)
            if not self.graph.has_edge(int(a), int(b)):
                self.graph.add_edge(int(a), int(b))
                return

    def run_cycle(self) -> None:
        self.expand(edges_per_node=1)
        self.detect_accelerators()
        if self.accelerators:
            self.add_small_world_shortcut()
        self.cycle += 1
        self._record_history()

    def summary(self) -> dict[str, Any]:
        base = super().summary()
        base.update(
            {
                "num_accelerators": len(self.accelerators),
                "accelerator_sizes": [len(a) for a in self.accelerators],
            }
        )
        return base


# ======================================================================
# Quantum preferential attachment (QPA-like)
# ======================================================================


class QuantumPreferentialAttachment:
    """Model wzrostu sieci inspirowany quantum preferential attachment.

    The alpha parameter amplifies the influence of the local neighborhood:
      alpha = 1.0  → behavior close to classical preferential attachment,
      alpha > 1.0  → stronger hub / hierarchical-structure formation.

    This is a heuristic model, not an implementation of a physical quantum network.
    """

    def __init__(self, alpha: float = 1.0, redirection: float | None = None, seed: int | None = None):
        self.alpha = float(alpha)
        self.redirection = redirection
        self.rng = np.random.default_rng(seed)
        self.graph = nx.Graph()

    def _qpa_weight(self, node: int) -> float:
        degree = self.graph.degree(node)
        if degree == 0:
            return 1.0
        total = 0.0
        for nbr in self.graph.neighbors(node):
            total += max(1, self.graph.degree(nbr)) ** (self.alpha - 1.0)
        return max(total, 1.0)

    def add_node(self) -> int:
        """Add a node via QPA with optional redirection to a target neighbor."""
        new_node = self.graph.number_of_nodes()
        self.graph.add_node(new_node)
        if new_node == 0:
            return new_node

        existing = list(range(new_node))
        weights = np.array([self._qpa_weight(i) for i in existing], dtype=float)
        probs = weights / weights.sum()
        target = int(self.rng.choice(existing, p=probs))
        d_target = self.graph.degree(target)

        if self.redirection is None:
            r_prob = d_target / (d_target + 1.0) if d_target > 0 else 0.5
        else:
            r_prob = float(np.clip(self.redirection, 0.0, 1.0))

        if self.rng.random() < r_prob and d_target > 0:
            neighbor = int(self.rng.choice(list(self.graph.neighbors(target))))
            self.graph.add_edge(new_node, neighbor)
        else:
            self.graph.add_edge(new_node, target)
        return new_node


# ======================================================================
# Wykrywanie klik inspirowane Groverem
# ======================================================================


class QuantumCliqueDetector:
    """Symulator detektora klik inspirowany wyszukiwaniem Grovera.

    Note: because this runs on a classical computer, it still enumerates combinations.
    The reported speedup is a complexity-model estimate, not an actual runtime gain.
    """

    def __init__(self, graph: nx.Graph, seed: int | None = None):
        self.graph = graph
        self.nodes = list(graph.nodes)
        self.n = len(self.nodes)
        self.rng = np.random.default_rng(seed)

    def _is_clique_by_indices(self, combo: tuple[int, ...]) -> bool:
        for i, j in combinations(combo, 2):
            if not self.graph.has_edge(self.nodes[i], self.nodes[j]):
                return False
        return True

    def all_k_cliques(self, k: int, limit: int | None = None) -> list[list[int]]:
        if k < 1 or k > self.n:
            return []
        found: list[list[int]] = []
        for combo in combinations(range(self.n), k):
            if self._is_clique_by_indices(combo):
                found.append([self.nodes[i] for i in combo])
                if limit is not None and len(found) >= limit:
                    break
        return found

    def grover_search_k_clique(self, k: int) -> list[int] | None:
        """Return one k-clique while modeling Grover success probability."""
        total = comb(self.n, k) if 0 <= k <= self.n else 0
        if total == 0:
            return None
        cliques = self.all_k_cliques(k)
        if not cliques:
            return None

        marked = len(cliques)
        theta = asin(sqrt(marked / total))
        iterations = max(1, int((pi / 4.0) * sqrt(total / marked)))
        prob_success = sin((2 * iterations + 1) * theta) ** 2

        # In this demo we still return a clique after a modeled 'failed measurement' if one exists,
        # while preferring the success case. This keeps the kernel behavior stable.
        if self.rng.random() <= prob_success:
            return list(cliques[int(self.rng.integers(len(cliques)))])
        return list(cliques[int(self.rng.integers(len(cliques)))])

    def grover_max_clique(self, max_search: int | None = None, min_size: int = 2) -> list[int] | None:
        upper = min(max_search or self.n, self.n)
        for k in range(upper, min_size - 1, -1):
            result = self.grover_search_k_clique(k)
            if result is not None:
                return result
        return None

    def theoretical_speedup_for_k(self, k: int) -> dict[str, float]:
        total = comb(self.n, k) if 0 <= k <= self.n else 0
        classical = float(total)
        quantum = sqrt(total) if total else 0.0
        return {"classical_queries": classical, "grover_queries": quantum, "speedup": classical / quantum if quantum else 0.0}




@dataclass(frozen=True)
class Accelerator:
    """A dense, strategically important subgraph that can accelerate information flow.

    In this project an accelerator is usually a clique or a near-clique, but the
    detector also accepts dense communities and high-degree hub neighborhoods.
    """

    id: int
    nodes: tuple[Any, ...]
    kind: str
    size: int
    internal_edges: int
    boundary_edges: int
    density: float
    conductance: float
    average_degree: float
    score: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "nodes": list(self.nodes),
            "kind": self.kind,
            "size": self.size,
            "internal_edges": self.internal_edges,
            "boundary_edges": self.boundary_edges,
            "density": round(self.density, 6),
            "conductance": round(self.conductance, 6),
            "average_degree": round(self.average_degree, 6),
            "score": round(self.score, 6),
        }


class GraphAcceleratorDetector:
    """Detect accelerator subgraphs in a NetworkX graph.

    Detection signals:
      1. Maximal cliques above a size threshold.
      2. Dense k-core components.
      3. Dense modularity communities.
      4. Dense hub ego-neighborhoods.

    The output is ranked by a structural score that rewards size, density and
    internal connectivity while penalizing excessive boundary conductance.
    """

    def __init__(self, graph: nx.Graph):
        self.graph = graph

    @staticmethod
    def _node_sort_key(node: Any) -> tuple[str, str]:
        return (type(node).__name__, repr(node))

    def _metrics(self, nodes: set[Any], kind: str, idx: int) -> Accelerator | None:
        if len(nodes) < 2:
            return None
        subgraph = self.graph.subgraph(nodes)
        size = subgraph.number_of_nodes()
        internal_edges = subgraph.number_of_edges()
        max_internal_edges = size * (size - 1) / 2
        density = internal_edges / max_internal_edges if max_internal_edges else 0.0

        boundary_edges = 0
        for node in nodes:
            for neighbor in self.graph.neighbors(node):
                if neighbor not in nodes:
                    boundary_edges += 1

        volume = sum(dict(self.graph.degree(nodes)).values())
        conductance = boundary_edges / volume if volume else 0.0
        average_degree = (2 * internal_edges) / size if size else 0.0

        # Score intuition:
        # - larger and denser subgraphs are more useful accelerators,
        # - high internal degree indicates fast local propagation,
        # - low conductance indicates a coherent module, but a small boundary is useful,
        #   so conductance is a soft penalty rather than a hard exclusion.
        score = (size * density) + (0.35 * average_degree) - (0.75 * conductance)
        if kind == "clique":
            score += 1.0
        elif kind == "k_core":
            score += 0.35
        elif kind == "hub_ego":
            score += 0.15

        ordered_nodes = tuple(sorted(nodes, key=self._node_sort_key))
        return Accelerator(
            id=idx,
            nodes=ordered_nodes,
            kind=kind,
            size=size,
            internal_edges=internal_edges,
            boundary_edges=boundary_edges,
            density=float(density),
            conductance=float(conductance),
            average_degree=float(average_degree),
            score=float(score),
        )

    def find_clique_accelerators(self, min_size: int = 5) -> list[set[Any]]:
        """Return maximal cliques that can act as high-efficiency processors.

        This is the explicit `find_cliques` detection path used by the
        Intelligent Acceleration module. Cliques represent fully connected
        local structures with maximal internal communication density.
        """
        if self.graph.number_of_nodes() < min_size:
            return []
        return [set(clique) for clique in nx.find_cliques(self.graph) if len(clique) >= min_size]

    def find_k_core_accelerators(self, min_size: int = 5, min_k: int | None = None) -> list[set[Any]]:
        """Return dense k-core connected components.

        K-core decomposition identifies the resilient processing backbone of a
        graph: each node in a k-core has at least k links inside the remaining
        core. These components are near-clique candidates and often expose the
        durable information-processing center of the network.
        """
        if self.graph.number_of_nodes() < min_size or self.graph.number_of_edges() == 0:
            return []
        graph = self.graph
        if any(graph.has_edge(node, node) for node in graph.nodes):
            graph = graph.copy()
            graph.remove_edges_from(nx.selfloop_edges(graph))
        try:
            core_numbers = nx.core_number(graph)
        except nx.NetworkXError:
            return []
        if not core_numbers:
            return []

        max_core = max(core_numbers.values())
        start_k = min_k if min_k is not None else max(2, min_size - 2)
        components: list[set[Any]] = []
        for k in range(max(1, start_k), max_core + 1):
            core_nodes = {node for node, core in core_numbers.items() if core >= k}
            for component in nx.connected_components(graph.subgraph(core_nodes)):
                if len(component) >= min_size:
                    components.append(set(component))
        return components

    def detect(
        self,
        min_size: int = 5,
        min_density: float = 0.65,
        max_results: int = 20,
        include_communities: bool = True,
        include_k_cores: bool = True,
        include_hub_egos: bool = True,
    ) -> list[Accelerator]:
        """Return ranked accelerator candidates.

        Args:
            min_size: Minimum number of nodes in an accelerator.
            min_density: Minimum internal density for non-clique candidates.
            max_results: Maximum number of returned accelerators.
            include_communities: Include greedy modularity communities.
            include_k_cores: Include dense k-core connected components.
            include_hub_egos: Include dense radius-1 hub neighborhoods.
        """
        if self.graph.number_of_nodes() < min_size:
            return []

        raw_candidates: list[tuple[str, set[Any]]] = []

        # 1. Maximal cliques are the strongest accelerator signal.
        for clique in self.find_clique_accelerators(min_size=min_size):
            raw_candidates.append(("clique", clique))

        # 2. Dense k-core components capture near-cliques and cohesive cores.
        if include_k_cores:
            for component in self.find_k_core_accelerators(min_size=min_size):
                raw_candidates.append(("k_core", component))

        # 3. Modularity communities catch dense modules that are not strict cliques.
        if include_communities and self.graph.number_of_edges() > 0:
            try:
                communities = nx.algorithms.community.greedy_modularity_communities(self.graph)
                for community in communities:
                    if len(community) >= min_size:
                        raw_candidates.append(("community", set(community)))
            except Exception:
                # Community detection is a convenience signal; it should never break the kernel.
                pass

        # 4. Hub ego-neighborhoods can be accelerators even without full clique density.
        if include_hub_egos:
            degrees = sorted(self.graph.degree, key=lambda item: item[1], reverse=True)
            top_count = min(max_results, max(1, int(sqrt(self.graph.number_of_nodes())) + 1))
            for node, degree in degrees[:top_count]:
                if degree + 1 >= min_size:
                    ego_nodes = set(nx.ego_graph(self.graph, node, radius=1).nodes)
                    raw_candidates.append(("hub_ego", ego_nodes))

        # Deduplicate by node set, keeping the highest-priority kind encountered first.
        kind_priority = {"clique": 0, "k_core": 1, "community": 2, "hub_ego": 3}
        dedup: dict[frozenset[Any], str] = {}
        for kind, nodes in raw_candidates:
            key = frozenset(nodes)
            if key not in dedup or kind_priority[kind] < kind_priority[dedup[key]]:
                dedup[key] = kind

        accelerators: list[Accelerator] = []
        for idx, (node_set, kind) in enumerate(dedup.items()):
            acc = self._metrics(set(node_set), kind, idx)
            if acc is None:
                continue
            if acc.kind == "clique" or acc.density >= min_density:
                accelerators.append(acc)

        accelerators.sort(key=lambda acc: (acc.score, acc.size, acc.density), reverse=True)
        return [Accelerator(id=i, **{k: v for k, v in acc.__dict__.items() if k != "id"}) for i, acc in enumerate(accelerators[:max_results])]




@dataclass(frozen=True)
class AcceleratorDetectionReport:
    """Structured output of the Intelligent Acceleration module.

    The report combines accelerator detection with optional small-world shortcut
    optimization, so callers can see which high-throughput structures were
    found and which edges were proposed or added to reduce information latency.
    """

    accelerators: list[Accelerator]
    shortcut_candidates: list["ConnectionCandidate"]
    added_shortcuts: list["ConnectionCandidate"]
    before_metrics: dict[str, Any]
    after_metrics: dict[str, Any]
    parameters: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "accelerators": [acc.as_dict() for acc in self.accelerators],
            "shortcut_candidates": [candidate.as_dict() for candidate in self.shortcut_candidates],
            "added_shortcuts": [candidate.as_dict() for candidate in self.added_shortcuts],
            "before_metrics": self.before_metrics,
            "after_metrics": self.after_metrics,
            "parameters": self.parameters,
            "small_world_delta": {
                "global_efficiency_gain": round(
                    float(self.after_metrics.get("global_efficiency", 0.0))
                    - float(self.before_metrics.get("global_efficiency", 0.0)),
                    6,
                ),
                "average_shortest_path_reduction": (
                    round(
                        float(self.before_metrics["average_shortest_path_length"])
                        - float(self.after_metrics["average_shortest_path_length"]),
                        6,
                    )
                    if self.before_metrics.get("average_shortest_path_length") is not None
                    and self.after_metrics.get("average_shortest_path_length") is not None
                    else None
                ),
            },
        }


@dataclass(frozen=True)
class ConnectionCandidate:
    """A proposed edge that improves network communication quality."""

    source: Any
    target: Any
    score: float
    efficiency_gain: float
    average_path_gain: float
    component_gain: int
    accelerator_bonus: float
    bridge_bonus: float
    common_neighbors: int
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "target": self.target,
            "score": round(self.score, 6),
            "efficiency_gain": round(self.efficiency_gain, 6),
            "average_path_gain": round(self.average_path_gain, 6),
            "component_gain": self.component_gain,
            "accelerator_bonus": round(self.accelerator_bonus, 6),
            "bridge_bonus": round(self.bridge_bonus, 6),
            "common_neighbors": self.common_neighbors,
            "reason": self.reason,
        }


class NetworkConnectionOptimizer:
    """Rank and add edges that improve global network connectivity.

    The optimizer evaluates missing edges as potential small-world shortcuts. It
    rewards edges that:
      - increase global efficiency,
      - reduce average shortest-path length,
      - connect disconnected components,
      - bridge different communities,
      - connect accelerator subgraphs with the rest of the network,
      - avoid redundant local links with many common neighbors.
    """

    def __init__(self, graph: nx.Graph, accelerators: list[Accelerator] | None = None):
        self.graph = graph
        self.accelerators = accelerators or []
        self._accelerator_node_sets = [set(acc.nodes) for acc in self.accelerators]

    @staticmethod
    def _node_sort_key(node: Any) -> tuple[str, str]:
        return (type(node).__name__, repr(node))

    @staticmethod
    def _safe_average_path_length(graph: nx.Graph) -> float | None:
        if graph.number_of_nodes() <= 1 or not nx.is_connected(graph):
            return None
        return float(nx.average_shortest_path_length(graph))

    @staticmethod
    def _safe_global_efficiency(graph: nx.Graph) -> float:
        if graph.number_of_nodes() <= 1:
            return 0.0
        return float(nx.global_efficiency(graph))

    def _community_labels(self) -> dict[Any, int]:
        if self.graph.number_of_edges() == 0:
            return {node: i for i, node in enumerate(self.graph.nodes)}
        try:
            communities = nx.algorithms.community.greedy_modularity_communities(self.graph)
            labels: dict[Any, int] = {}
            for i, community in enumerate(communities):
                for node in community:
                    labels[node] = i
            return labels
        except Exception:
            return {node: 0 for node in self.graph.nodes}

    def _accelerator_bonus(self, a: Any, b: Any) -> float:
        if not self._accelerator_node_sets:
            return 0.0
        bonus = 0.0
        for nodes in self._accelerator_node_sets:
            a_in = a in nodes
            b_in = b in nodes
            if a_in ^ b_in:
                # Connect an accelerator to the outside world.
                bonus = max(bonus, 1.0)
            elif a_in and b_in:
                # Internal accelerator links are less valuable if they are still missing.
                bonus = max(bonus, 0.25)
        # Bridge two different accelerators.
        containing_a = [i for i, nodes in enumerate(self._accelerator_node_sets) if a in nodes]
        containing_b = [i for i, nodes in enumerate(self._accelerator_node_sets) if b in nodes]
        if containing_a and containing_b and set(containing_a).isdisjoint(containing_b):
            bonus = max(bonus, 1.25)
        return bonus

    def _candidate_pairs(self, max_candidates: int = 2500) -> list[tuple[Any, Any]]:
        nodes = list(self.graph.nodes)
        if len(nodes) < 2:
            return []

        missing_count_estimate = len(nodes) * (len(nodes) - 1) // 2 - self.graph.number_of_edges()
        if missing_count_estimate <= max_candidates:
            return [(a, b) for a, b in nx.non_edges(self.graph)]

        pairs: set[tuple[Any, Any]] = set()

        def add_pair(a: Any, b: Any) -> None:
            if a == b or self.graph.has_edge(a, b):
                return
            ordered = tuple(sorted((a, b), key=self._node_sort_key))
            pairs.add(ordered)

        # Connect different components first.
        components = [list(c) for c in nx.connected_components(self.graph)]
        representatives = [max(component, key=lambda node: self.graph.degree(node)) for component in components]
        for i, a in enumerate(representatives):
            for b in representatives[i + 1:]:
                add_pair(a, b)

        # Accelerator-to-outside and accelerator-to-accelerator shortcuts.
        all_acc_nodes = set().union(*self._accelerator_node_sets) if self._accelerator_node_sets else set()
        outside = [node for node in nodes if node not in all_acc_nodes]
        top_outside = sorted(outside, key=lambda node: self.graph.degree(node), reverse=True)[: max(10, int(sqrt(len(nodes))) + 1)]
        for acc_nodes in self._accelerator_node_sets[:10]:
            acc_hubs = sorted(acc_nodes, key=lambda node: self.graph.degree(node), reverse=True)[:5]
            for a in acc_hubs:
                for b in top_outside:
                    add_pair(a, b)
            for other in self._accelerator_node_sets[:10]:
                if other is acc_nodes:
                    continue
                for a in acc_hubs[:2]:
                    for b in sorted(other, key=lambda node: self.graph.degree(node), reverse=True)[:2]:
                        add_pair(a, b)

        # High-centrality / high-degree to low-degree long-range shortcuts.
        top_degree = sorted(nodes, key=lambda node: self.graph.degree(node), reverse=True)[: max(10, int(sqrt(len(nodes))) + 1)]
        low_degree = sorted(nodes, key=lambda node: self.graph.degree(node))[: max(10, int(sqrt(len(nodes))) + 1)]
        for a in top_degree:
            for b in low_degree:
                add_pair(a, b)

        # Fill remaining slots with deterministic non-edge enumeration.
        for a, b in nx.non_edges(self.graph):
            add_pair(a, b)
            if len(pairs) >= max_candidates:
                break

        return list(pairs)[:max_candidates]

    def score_edge(self, a: Any, b: Any, community_labels: dict[Any, int] | None = None) -> ConnectionCandidate | None:
        """Score a single potential edge without mutating the original graph."""
        if a == b or self.graph.has_edge(a, b):
            return None

        before_components = nx.number_connected_components(self.graph) if self.graph.number_of_nodes() else 0
        before_efficiency = self._safe_global_efficiency(self.graph)
        before_path = self._safe_average_path_length(self.graph)

        trial = self.graph.copy()
        trial.add_edge(a, b)

        after_components = nx.number_connected_components(trial) if trial.number_of_nodes() else 0
        after_efficiency = self._safe_global_efficiency(trial)
        after_path = self._safe_average_path_length(trial)

        efficiency_gain = after_efficiency - before_efficiency
        if before_path is not None and after_path is not None:
            average_path_gain = before_path - after_path
        elif before_path is None and after_path is not None:
            average_path_gain = 1.0
        else:
            average_path_gain = 0.0

        component_gain = max(0, before_components - after_components)
        accelerator_bonus = self._accelerator_bonus(a, b)

        labels = community_labels or self._community_labels()
        bridge_bonus = 0.75 if labels.get(a) != labels.get(b) else 0.0
        if component_gain > 0:
            bridge_bonus += 2.0

        common_neighbors = len(list(nx.common_neighbors(self.graph, a, b)))
        novelty_bonus = 1.0 / (1.0 + common_neighbors)

        # Scale efficiency by graph size so it is comparable across graph sizes.
        n = max(1, self.graph.number_of_nodes())
        score = (
            efficiency_gain * n
            + average_path_gain
            + 2.5 * component_gain
            + accelerator_bonus
            + bridge_bonus
            + 0.25 * novelty_bonus
        )

        reasons = []
        if component_gain:
            reasons.append("connects components")
        if bridge_bonus > 0 and not component_gain:
            reasons.append("bridges communities")
        if accelerator_bonus >= 1.0:
            reasons.append("connects accelerator")
        if average_path_gain > 0:
            reasons.append("shortens paths")
        if efficiency_gain > 0:
            reasons.append("improves efficiency")
        if not reasons:
            reasons.append("adds non-redundant shortcut")

        return ConnectionCandidate(
            source=a,
            target=b,
            score=float(score),
            efficiency_gain=float(efficiency_gain),
            average_path_gain=float(average_path_gain),
            component_gain=int(component_gain),
            accelerator_bonus=float(accelerator_bonus),
            bridge_bonus=float(bridge_bonus),
            common_neighbors=int(common_neighbors),
            reason=", ".join(reasons),
        )

    def rank_candidates(self, max_candidates: int = 2500) -> list[ConnectionCandidate]:
        """Return edge candidates sorted from best to worst."""
        labels = self._community_labels()
        candidates = []
        for a, b in self._candidate_pairs(max_candidates=max_candidates):
            candidate = self.score_edge(a, b, community_labels=labels)
            if candidate is not None:
                candidates.append(candidate)
        candidates.sort(key=lambda item: (item.score, item.efficiency_gain, item.average_path_gain), reverse=True)
        return candidates

    def optimize(
        self,
        add_edges: int = 1,
        max_candidates: int = 2500,
        dry_run: bool = False,
        recompute_each_step: bool = True,
    ) -> list[ConnectionCandidate]:
        """Greedily add the best network shortcuts.

        If `dry_run` is True, the graph is not modified and the method only
        returns the top proposed edges.
        """
        add_edges = max(0, int(add_edges))
        if add_edges == 0 or self.graph.number_of_nodes() < 2:
            return []

        selected: list[ConnectionCandidate] = []
        for _ in range(add_edges):
            ranked = self.rank_candidates(max_candidates=max_candidates)
            if not ranked:
                break
            best = ranked[0]
            selected.append(best)
            if dry_run:
                if len(selected) >= add_edges:
                    break
                # Do not mutate in dry-run mode; return the top-k from the same ranking.
                selected = ranked[:add_edges]
                break
            self.graph.add_edge(best.source, best.target)
            if not recompute_each_step:
                selected.extend(ranked[1:add_edges])
                for candidate in ranked[1:add_edges]:
                    if not self.graph.has_edge(candidate.source, candidate.target):
                        self.graph.add_edge(candidate.source, candidate.target)
                break
        return selected


# ======================================================================
# QAOA-like optimizer for MaxClique
# ======================================================================


class QAOAOptimizer:
    """Small educational QAOA simulator for the MaxClique problem.

    The code uses a 2^n state vector, so it is intended for small demonstration
    graphs. For n > ~16 it becomes expensive.
    """

    def __init__(self, graph: nx.Graph, p_layers: int = 2, penalty: float = 3.0, seed: int | None = None):
        self.graph = graph.copy()
        self.p = int(max(1, p_layers))
        self.penalty = float(penalty)
        self.nodes = list(self.graph.nodes)
        self.n = len(self.nodes)
        self.rng = np.random.default_rng(seed)

    def cost_energy(self, bitstring: str) -> float:
        """QUBO: minimize -number_selected + penalty for non-edge pairs."""
        bits = [1 if b == "1" else 0 for b in bitstring]
        energy = -float(sum(bits))
        for i, j in combinations(range(self.n), 2):
            if bits[i] and bits[j] and not self.graph.has_edge(self.nodes[i], self.nodes[j]):
                energy += self.penalty
        return energy

    def _cost_diagonal(self) -> np.ndarray:
        diag = np.zeros(2**self.n, dtype=float)
        for state in range(2**self.n):
            bitstring = format(state, f"0{self.n}b")
            diag[state] = self.cost_energy(bitstring)
        return diag

    @staticmethod
    def _apply_rx_to_qubit(states: np.ndarray, beta: float, qubit: int, n: int) -> np.ndarray:
        """Apply exp(-i beta X) to a single qubit."""
        c = cos(beta)
        s = -1j * sin(beta)
        out = states.copy()
        mask = 1 << (n - qubit - 1)
        for idx in range(len(states)):
            if idx & mask:
                continue
            idx0 = idx
            idx1 = idx | mask
            a, b = states[idx0], states[idx1]
            out[idx0] = c * a + s * b
            out[idx1] = s * a + c * b
        return out

    def simulate_qaoa(self, gamma: np.ndarray, beta: np.ndarray) -> np.ndarray:
        if self.n == 0:
            return np.array([1.0 + 0.0j])
        if self.n > 18:
            raise ValueError("State-vector simulation is too large for n > 18.")

        states = np.ones(2**self.n, dtype=complex) / sqrt(2**self.n)
        cost_diag = self._cost_diagonal()
        for layer in range(self.p):
            states *= np.exp(-1j * gamma[layer] * cost_diag)
            for qubit in range(self.n):
                states = self._apply_rx_to_qubit(states, beta[layer], qubit, self.n)
        norm = np.linalg.norm(states)
        return states / norm if norm else states

    def probabilities(self, gamma: np.ndarray, beta: np.ndarray) -> dict[str, float]:
        states = self.simulate_qaoa(gamma, beta)
        probs = np.abs(states) ** 2
        return {format(i, f"0{self.n}b"): float(p) for i, p in enumerate(probs) if p > 1e-12}

    def expected_energy(self, gamma: np.ndarray, beta: np.ndarray) -> float:
        probs = self.probabilities(gamma, beta)
        return float(sum(p * self.cost_energy(bs) for bs, p in probs.items()))

    def _pack_angles(self, gamma: np.ndarray, beta: np.ndarray) -> np.ndarray:
        return np.concatenate([gamma, beta])

    def _unpack_angles(self, params: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        params = np.asarray(params, dtype=float)
        gamma = np.mod(params[: self.p], pi)
        beta = np.mod(params[self.p : 2 * self.p], pi)
        return gamma, beta

    def _fallback_derivative_free_optimizer(
        self,
        objective: Callable[[np.ndarray], float],
        x0: np.ndarray,
        bounds: list[tuple[float, float]],
        iterations: int,
    ) -> np.ndarray:
        """Dependency-free optimizer used only when SciPy/COBYLA is unavailable."""
        best = np.asarray(x0, dtype=float).copy()
        best_value = objective(best)
        for t in range(int(max(1, iterations))):
            scale = 0.25 * (1.0 - t / max(1, iterations)) + 0.02
            candidate = best + self.rng.normal(0.0, scale, size=len(best))
            for i, (lo, hi) in enumerate(bounds):
                candidate[i] = float(np.clip(candidate[i], lo, hi))
            value = objective(candidate)
            if value < best_value:
                best_value = value
                best = candidate
        return best

    def _cobyla_optimizer(
        self,
        objective: Callable[[np.ndarray], float],
        x0: np.ndarray,
        bounds: list[tuple[float, float]],
        iterations: int,
        rhobeg: float = 0.35,
        tol: float = 1e-5,
    ) -> tuple[np.ndarray, dict[str, Any]]:
        """Stable SciPy COBYLA optimizer with explicit bound constraints.

        COBYLA is derivative-free and generally more stable than pure random
        perturbation for the noisy/non-convex QAOA landscape. Bounds are encoded
        as inequality constraints so the method works across SciPy versions.
        """
        try:
            from scipy.optimize import minimize  # type: ignore

            constraints = []
            for idx, (lo, hi) in enumerate(bounds):
                constraints.append({"type": "ineq", "fun": lambda x, idx=idx, lo=lo: x[idx] - lo})
                constraints.append({"type": "ineq", "fun": lambda x, idx=idx, hi=hi: hi - x[idx]})

            history: list[float] = []

            def tracked_objective(params: np.ndarray) -> float:
                value = float(objective(np.asarray(params, dtype=float)))
                history.append(value)
                return value

            result = minimize(
                tracked_objective,
                np.asarray(x0, dtype=float),
                method="COBYLA",
                constraints=constraints,
                options={
                    "maxiter": int(max(iterations, len(x0) + 2)),
                    "rhobeg": float(rhobeg),
                    "tol": float(tol),
                    "catol": 1e-6,
                    "disp": False,
                },
            )
            params = np.asarray(getattr(result, "x", x0), dtype=float)
            for i, (lo, hi) in enumerate(bounds):
                params[i] = float(np.clip(params[i], lo, hi))
            metadata = {
                "optimizer": "scipy_cobyla",
                "success": bool(getattr(result, "success", False)),
                "message": str(getattr(result, "message", "")),
                "evaluations": len(history),
                "best_objective": float(min(history)) if history else float(objective(params)),
                "final_objective": float(objective(params)),
                "history_tail": [float(x) for x in history[-10:]],
            }
            return params, metadata
        except Exception as exc:
            params = self._fallback_derivative_free_optimizer(objective, x0, bounds, iterations)
            return params, {
                "optimizer": "fallback_derivative_free",
                "success": True,
                "message": f"SciPy COBYLA unavailable or failed: {exc}",
                "evaluations": int(max(1, iterations)),
                "best_objective": float(objective(params)),
                "final_objective": float(objective(params)),
                "history_tail": [],
            }

    def _default_external_optimizer(
        self,
        objective: Callable[[np.ndarray], float],
        x0: np.ndarray,
        bounds: list[tuple[float, float]],
        iterations: int,
    ) -> np.ndarray:
        """Default optimizer: stable COBYLA if available, otherwise fallback."""
        params, metadata = self._cobyla_optimizer(objective, x0, bounds, iterations)
        self.last_optimizer_metadata = metadata
        return params

    def optimize_cobyla(
        self,
        iterations: int = 120,
        restarts: int = 4,
        rhobeg: float = 0.35,
        tol: float = 1e-5,
    ) -> tuple[np.ndarray, np.ndarray, str]:
        """Optimized QAOA angle search using multi-start COBYLA.

        Multi-start initialization improves stability on the non-convex QAOA
        landscape. The best run is selected by expected energy, and the final
        bitstring is selected by exact QUBO energy with probability tie-breaking.
        Metadata is stored in `self.last_optimizer_metadata`.
        """
        bounds = [(0.0, pi)] * (2 * self.p)

        def objective(params: np.ndarray) -> float:
            gamma, beta = self._unpack_angles(params)
            return self.expected_energy(gamma, beta)

        best_params: np.ndarray | None = None
        best_value = float("inf")
        runs: list[dict[str, Any]] = []
        restarts = max(1, int(restarts))
        per_restart_iterations = max(len(bounds) + 2, int(max(1, iterations) / restarts))

        for restart in range(restarts):
            gamma0 = self.rng.uniform(0.0, pi, self.p)
            beta0 = self.rng.uniform(0.0, pi / 2.0, self.p)
            x0 = self._pack_angles(gamma0, beta0)
            params, metadata = self._cobyla_optimizer(
                objective,
                x0,
                bounds,
                iterations=per_restart_iterations,
                rhobeg=rhobeg,
                tol=tol,
            )
            value = objective(params)
            run_record = {**metadata, "restart": restart, "objective": float(value)}
            runs.append(run_record)
            if value < best_value:
                best_value = value
                best_params = params

        assert best_params is not None
        best_gamma, best_beta = self._unpack_angles(best_params)
        probs = self.probabilities(best_gamma, best_beta)
        best_bitstring = min(probs, key=lambda bs: (self.cost_energy(bs), -probs[bs]))
        selected_nodes = self.extract_selected_nodes(best_bitstring)
        projected_clique = self.extract_clique(best_bitstring)
        self.last_optimizer_metadata = {
            "optimizer": "multi_start_cobyla",
            "restarts": restarts,
            "iterations": iterations,
            "per_restart_iterations": per_restart_iterations,
            "best_expected_energy": float(best_value),
            "best_bitstring": best_bitstring,
            "raw_selected_nodes": selected_nodes,
            "raw_clique_purity": float(self.clique_purity(selected_nodes)),
            "projected_clique": projected_clique,
            "projected_clique_purity": float(self.clique_purity(projected_clique)),
            "runs": runs,
        }
        return best_gamma, best_beta, best_bitstring

    def optimize(
        self,
        iterations: int = 80,
        optimizer_fn: Callable[[Callable[[np.ndarray], float], np.ndarray, list[tuple[float, float]], int], np.ndarray] | None = None,
    ) -> tuple[np.ndarray, np.ndarray, str]:
        """Optimize QAOA angles through an external mathematical optimizer.

        Args:
            iterations: Optimization budget passed to the optimizer.
            optimizer_fn: Optional external optimizer with signature
                `(objective, x0, bounds, iterations) -> best_params`.
                If omitted, SciPy/COBYLA is used when available; otherwise a
                deterministic derivative-free fallback is used.
        """
        gamma0 = self.rng.uniform(0.0, pi, self.p)
        beta0 = self.rng.uniform(0.0, pi / 2.0, self.p)
        x0 = self._pack_angles(gamma0, beta0)
        bounds = [(0.0, pi)] * (2 * self.p)

        def objective(params: np.ndarray) -> float:
            gamma, beta = self._unpack_angles(params)
            return self.expected_energy(gamma, beta)

        if optimizer_fn is None:
            return self.optimize_cobyla(iterations=iterations, restarts=3)

        best_params = np.asarray(optimizer_fn(objective, x0, bounds, int(max(1, iterations))), dtype=float)
        best_gamma, best_beta = self._unpack_angles(best_params)

        probs = self.probabilities(best_gamma, best_beta)
        # Choose the lowest energy; break ties by highest probability.
        best_bitstring = min(probs, key=lambda bs: (self.cost_energy(bs), -probs[bs]))
        self.last_optimizer_metadata = {
            "optimizer": "external_optimizer_fn",
            "iterations": int(max(1, iterations)),
            "best_expected_energy": float(self.expected_energy(best_gamma, best_beta)),
            "best_bitstring": best_bitstring,
            "raw_clique_purity": float(self.clique_purity(best_bitstring)),
            "projected_clique_purity": float(self.clique_purity(self.extract_clique(best_bitstring))),
        }
        return best_gamma, best_beta, best_bitstring

    def clique_purity(self, nodes_or_bitstring: list[Any] | str) -> float:
        """Return clique purity: existing internal edges / all possible internal edges."""
        if isinstance(nodes_or_bitstring, str):
            group = [self.nodes[i] for i, bit in enumerate(nodes_or_bitstring) if bit == "1"]
        else:
            group = list(nodes_or_bitstring)
        size = len(group)
        possible = size * (size - 1) // 2
        if possible == 0:
            return 1.0
        existing = sum(1 for a, b in combinations(group, 2) if self.graph.has_edge(a, b))
        return float(existing / possible)

    def extract_selected_nodes(self, bitstring: str) -> list[int]:
        """Extract raw selected nodes before clique projection/repair."""
        return [self.nodes[i] for i, b in enumerate(bitstring) if b == "1"]

    def extract_clique(self, bitstring: str) -> list[int]:
        chosen = [self.nodes[i] for i, b in enumerate(bitstring) if b == "1"]
        # Projection repair: if QAOA selects a non-clique, extract a maximal clique from the subgraph.
        sub = self.graph.subgraph(chosen)
        is_complete = sub.number_of_edges() == len(chosen) * (len(chosen) - 1) // 2
        if len(chosen) <= 1 or is_complete:
            return chosen
        return max((list(c) for c in nx.find_cliques(sub)), key=len, default=[])




@dataclass(frozen=True)
class GraphAnalysisReport:
    """Structured report with network and graph analysis metrics."""

    overview: dict[str, Any]
    connectivity: dict[str, Any]
    centrality: dict[str, Any]
    communities: dict[str, Any]
    resilience: dict[str, Any]
    paths: dict[str, Any]
    degree_distribution: dict[str, Any]
    accelerators: list[dict[str, Any]]
    recommendations: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "overview": self.overview,
            "connectivity": self.connectivity,
            "centrality": self.centrality,
            "communities": self.communities,
            "resilience": self.resilience,
            "paths": self.paths,
            "degree_distribution": self.degree_distribution,
            "accelerators": self.accelerators,
            "recommendations": self.recommendations,
        }


class GraphNetworkAnalyzer:
    """Analyze a NetworkX graph and produce actionable network diagnostics.

    The analyzer combines standard graph metrics with accelerator detection and
    connection-optimization hints. It is designed for social networks, knowledge
    graphs, communication networks, dependency graphs and AI-agent networks.
    """

    def __init__(self, graph: nx.Graph, accelerators: list[Accelerator] | None = None):
        self.graph = graph
        self.accelerators = accelerators or []

    @staticmethod
    def _top_items(values: dict[Any, float], limit: int = 10) -> list[dict[str, Any]]:
        ranked = sorted(values.items(), key=lambda item: item[1], reverse=True)[:limit]
        return [{"node": node, "value": round(float(value), 6)} for node, value in ranked]

    @staticmethod
    def _safe_radius_diameter(graph: nx.Graph) -> tuple[int | None, int | None]:
        if graph.number_of_nodes() <= 1 or not nx.is_connected(graph):
            return None, None
        return int(nx.radius(graph)), int(nx.diameter(graph))

    @staticmethod
    def _safe_assortativity(graph: nx.Graph) -> float | None:
        if graph.number_of_edges() == 0 or graph.number_of_nodes() < 3:
            return None
        try:
            value = nx.degree_assortativity_coefficient(graph)
            if np.isnan(value):
                return None
            return float(value)
        except Exception:
            return None

    def overview_metrics(self) -> dict[str, Any]:
        n = self.graph.number_of_nodes()
        m = self.graph.number_of_edges()
        degrees = [degree for _, degree in self.graph.degree]
        return {
            "nodes": n,
            "edges": m,
            "density": round(nx.density(self.graph), 6) if n > 1 else 0.0,
            "average_degree": round(float(np.mean(degrees)), 6) if degrees else 0.0,
            "median_degree": round(float(np.median(degrees)), 6) if degrees else 0.0,
            "max_degree": int(max(degrees)) if degrees else 0,
            "min_degree": int(min(degrees)) if degrees else 0,
            "self_loops": nx.number_of_selfloops(self.graph),
            "is_directed": self.graph.is_directed(),
        }

    def connectivity_metrics(self) -> dict[str, Any]:
        n = self.graph.number_of_nodes()
        if n == 0:
            return {
                "connected": False,
                "components": 0,
                "largest_component_size": 0,
                "largest_component_ratio": 0.0,
                "isolates": [],
                "articulation_points": [],
                "bridges": [],
            }
        components = [set(c) for c in nx.connected_components(self.graph)]
        largest = max(components, key=len) if components else set()
        articulation_points = list(nx.articulation_points(self.graph)) if n > 1 else []
        bridges = list(nx.bridges(self.graph)) if self.graph.number_of_edges() else []
        return {
            "connected": nx.is_connected(self.graph),
            "components": len(components),
            "component_sizes": sorted([len(c) for c in components], reverse=True),
            "largest_component_size": len(largest),
            "largest_component_ratio": round(len(largest) / n, 6) if n else 0.0,
            "isolates": list(nx.isolates(self.graph)),
            "articulation_points": articulation_points[:20],
            "num_articulation_points": len(articulation_points),
            "bridges": bridges[:20],
            "num_bridges": len(bridges),
            "node_connectivity_estimate": nx.node_connectivity(self.graph) if n > 1 and nx.is_connected(self.graph) else 0,
            "edge_connectivity_estimate": nx.edge_connectivity(self.graph) if n > 1 and nx.is_connected(self.graph) else 0,
        }

    def path_metrics(self) -> dict[str, Any]:
        n = self.graph.number_of_nodes()
        if n <= 1:
            return {
                "average_shortest_path_length": None,
                "diameter": None,
                "radius": None,
                "global_efficiency": 0.0,
                "local_efficiency": 0.0,
                "transitivity": 0.0,
                "average_clustering": 0.0,
            }

        if nx.is_connected(self.graph):
            avg_path = float(nx.average_shortest_path_length(self.graph))
            radius, diameter = self._safe_radius_diameter(self.graph)
        else:
            largest_nodes = max(nx.connected_components(self.graph), key=len)
            largest = self.graph.subgraph(largest_nodes)
            avg_path = float(nx.average_shortest_path_length(largest)) if largest.number_of_nodes() > 1 else None
            radius, diameter = self._safe_radius_diameter(largest)

        return {
            "average_shortest_path_length": round(avg_path, 6) if avg_path is not None else None,
            "diameter": diameter,
            "radius": radius,
            "global_efficiency": round(nx.global_efficiency(self.graph), 6),
            "local_efficiency": round(nx.local_efficiency(self.graph), 6),
            "transitivity": round(nx.transitivity(self.graph), 6),
            "average_clustering": round(nx.average_clustering(self.graph), 6),
        }

    def centrality_metrics(self, top_n: int = 10) -> dict[str, Any]:
        n = self.graph.number_of_nodes()
        if n == 0:
            return {"top_degree": [], "top_betweenness": [], "top_closeness": [], "top_pagerank": [], "top_eigenvector": []}

        degree = nx.degree_centrality(self.graph)
        betweenness = nx.betweenness_centrality(self.graph, normalized=True) if n > 1 else {node: 0.0 for node in self.graph.nodes}
        closeness = nx.closeness_centrality(self.graph) if n > 1 else {node: 0.0 for node in self.graph.nodes}
        try:
            pagerank = nx.pagerank(self.graph) if self.graph.number_of_edges() else {node: 1.0 / n for node in self.graph.nodes}
        except Exception:
            pagerank = {node: 0.0 for node in self.graph.nodes}
        try:
            eigenvector = nx.eigenvector_centrality(self.graph, max_iter=500) if self.graph.number_of_edges() else {node: 0.0 for node in self.graph.nodes}
        except Exception:
            eigenvector = {node: 0.0 for node in self.graph.nodes}

        return {
            "top_degree": self._top_items(degree, top_n),
            "top_betweenness": self._top_items(betweenness, top_n),
            "top_closeness": self._top_items(closeness, top_n),
            "top_pagerank": self._top_items(pagerank, top_n),
            "top_eigenvector": self._top_items(eigenvector, top_n),
        }

    def community_metrics(self) -> dict[str, Any]:
        if self.graph.number_of_nodes() == 0:
            return {"num_communities": 0, "community_sizes": [], "modularity": None, "communities": []}
        if self.graph.number_of_edges() == 0:
            communities = [{node} for node in self.graph.nodes]
            return {
                "num_communities": len(communities),
                "community_sizes": [1 for _ in communities],
                "modularity": 0.0,
                "communities": [list(c) for c in communities[:10]],
            }
        try:
            communities = list(nx.algorithms.community.greedy_modularity_communities(self.graph))
            modularity = nx.algorithms.community.modularity(self.graph, communities)
        except Exception:
            communities = [set(self.graph.nodes)]
            modularity = 0.0
        return {
            "num_communities": len(communities),
            "community_sizes": sorted([len(c) for c in communities], reverse=True),
            "modularity": round(float(modularity), 6),
            "communities": [list(c) for c in communities[:10]],
        }

    def degree_distribution_metrics(self) -> dict[str, Any]:
        degrees = [degree for _, degree in self.graph.degree]
        if not degrees:
            return {"histogram": {}, "assortativity": None, "gini": 0.0, "hub_threshold": 0, "hubs": []}
        histogram: dict[int, int] = {}
        for degree in degrees:
            histogram[degree] = histogram.get(degree, 0) + 1
        values = np.array(sorted(degrees), dtype=float)
        if values.sum() == 0:
            gini = 0.0
        else:
            index = np.arange(1, len(values) + 1)
            gini = float((2 * np.sum(index * values)) / (len(values) * np.sum(values)) - (len(values) + 1) / len(values))
        threshold = int(np.percentile(degrees, 90)) if degrees else 0
        hubs = [node for node, degree in self.graph.degree if degree >= threshold and degree > 0]
        return {
            "histogram": dict(sorted(histogram.items())),
            "assortativity": self._safe_assortativity(self.graph),
            "gini": round(gini, 6),
            "hub_threshold": threshold,
            "hubs": hubs[:20],
        }

    def resilience_metrics(self) -> dict[str, Any]:
        n = self.graph.number_of_nodes()
        if n == 0:
            return {"largest_component_ratio": 0.0, "after_top_hub_removal_ratio": 0.0, "after_random_10pct_removal_ratio": 0.0}

        def largest_ratio(graph: nx.Graph) -> float:
            if graph.number_of_nodes() == 0:
                return 0.0
            return len(max(nx.connected_components(graph), key=len)) / n

        top_hub_graph = self.graph.copy()
        if top_hub_graph.number_of_nodes() > 0:
            top_hub = max(top_hub_graph.degree, key=lambda item: item[1])[0]
            top_hub_graph.remove_node(top_hub)

        random_graph = self.graph.copy()
        remove_count = max(1, int(0.1 * n)) if n >= 10 else 1
        # Deterministic pseudo-random removal based on sorted node representation.
        removable = sorted(random_graph.nodes, key=lambda node: repr(node))[:remove_count]
        random_graph.remove_nodes_from(removable)

        return {
            "largest_component_ratio": round(largest_ratio(self.graph), 6),
            "after_top_hub_removal_ratio": round(largest_ratio(top_hub_graph), 6),
            "after_random_10pct_removal_ratio": round(largest_ratio(random_graph), 6),
        }

    def recommendations(self, overview: dict[str, Any], connectivity: dict[str, Any], paths: dict[str, Any], communities: dict[str, Any]) -> list[str]:
        recs: list[str] = []
        if not connectivity.get("connected") and connectivity.get("components", 0) > 1:
            recs.append("Connect separate components with high-score shortcut edges.")
        if paths.get("average_shortest_path_length") and paths["average_shortest_path_length"] > 4:
            recs.append("Add small-world shortcuts to reduce average path length.")
        if overview.get("density", 0) < 0.08 and overview.get("nodes", 0) > 10:
            recs.append("The graph is sparse; consider adding strategic bridge edges rather than random links.")
        if connectivity.get("num_articulation_points", 0) > 0:
            recs.append("Reduce dependency on articulation points by adding alternative routes.")
        if connectivity.get("num_bridges", 0) > 0:
            recs.append("Several bridges exist; reinforce them with redundant backup edges.")
        if communities.get("num_communities", 0) > 1:
            recs.append("Bridge high-value communities to improve cross-cluster information flow.")
        if self.accelerators:
            recs.append("Use detected accelerators as anchors for optimized long-range connections.")
        if not recs:
            recs.append("Network structure looks balanced; monitor centrality and resilience over time.")
        return recs

    def analyze(self, top_n: int = 10) -> GraphAnalysisReport:
        overview = self.overview_metrics()
        connectivity = self.connectivity_metrics()
        paths = self.path_metrics()
        centrality = self.centrality_metrics(top_n=top_n)
        communities = self.community_metrics()
        degree_distribution = self.degree_distribution_metrics()
        resilience = self.resilience_metrics()
        accelerators = [acc.as_dict() for acc in self.accelerators]
        recommendations = self.recommendations(overview, connectivity, paths, communities)
        return GraphAnalysisReport(
            overview=overview,
            connectivity=connectivity,
            centrality=centrality,
            communities=communities,
            resilience=resilience,
            paths=paths,
            degree_distribution=degree_distribution,
            accelerators=accelerators,
            recommendations=recommendations,
        )




@dataclass(frozen=True)
class QuantumExperimentResult:
    """Single result produced by a quantum-inspired experiment."""

    name: str
    parameters: dict[str, Any]
    metrics: dict[str, Any]
    artifacts: dict[str, Any]
    runtime_sec: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "parameters": self.parameters,
            "metrics": self.metrics,
            "artifacts": self.artifacts,
            "runtime_sec": round(float(self.runtime_sec), 6),
        }


class QuantumExperimentSuite:
    """Run reproducible experiments with the quantum-inspired algorithms.

    The suite is intentionally backend-independent. It compares and documents
    simulated QPA, Grover-style clique search, QAOA-like MaxClique optimization
    and the full QuantumHybridGraph cycle.
    """

    def __init__(self, seed: int | None = None):
        self.seed = seed
        self.rng = np.random.default_rng(seed)

    @staticmethod
    def _degree_gini(graph: nx.Graph) -> float:
        degrees = np.array([degree for _, degree in graph.degree], dtype=float)
        if len(degrees) == 0 or degrees.sum() == 0:
            return 0.0
        values = np.sort(degrees)
        index = np.arange(1, len(values) + 1)
        return float((2 * np.sum(index * values)) / (len(values) * np.sum(values)) - (len(values) + 1) / len(values))

    @staticmethod
    def _basic_graph_metrics(graph: nx.Graph) -> dict[str, Any]:
        n = graph.number_of_nodes()
        degrees = [degree for _, degree in graph.degree]
        return {
            "nodes": n,
            "edges": graph.number_of_edges(),
            "density": round(nx.density(graph), 6) if n > 1 else 0.0,
            "average_degree": round(float(np.mean(degrees)), 6) if degrees else 0.0,
            "max_degree": int(max(degrees)) if degrees else 0,
            "average_clustering": round(nx.average_clustering(graph), 6) if n > 1 else 0.0,
            "degree_gini": round(QuantumExperimentSuite._degree_gini(graph), 6),
            "connected": nx.is_connected(graph) if n > 0 else False,
        }

    @staticmethod
    def default_test_graph() -> nx.Graph:
        """Create a small graph with known cliques for experiments."""
        graph = nx.Graph()
        graph.add_edges_from(
            [
                (0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3),
                (3, 4), (4, 5), (4, 6), (5, 6),
                (6, 7), (7, 8), (8, 9), (7, 9),
            ]
        )
        return graph

    def experiment_qpa_growth(self, alphas: list[float] | None = None, nodes: int = 40) -> QuantumExperimentResult:
        """Sweep QPA alpha and measure resulting network structure."""
        alphas = alphas or [1.0, 1.25, 1.5, 2.0]
        t0 = time.perf_counter()
        runs = []
        for alpha in alphas:
            qpa = QuantumPreferentialAttachment(alpha=alpha, seed=int(self.rng.integers(0, 2**32 - 1)))
            for _ in range(nodes):
                qpa.add_node()
            metrics = self._basic_graph_metrics(qpa.graph)
            metrics["alpha"] = float(alpha)
            runs.append(metrics)
        return QuantumExperimentResult(
            name="qpa_growth_sweep",
            parameters={"alphas": alphas, "nodes": nodes},
            metrics={"runs": runs},
            artifacts={},
            runtime_sec=time.perf_counter() - t0,
        )

    def experiment_grover_clique_search(self, graph: nx.Graph | None = None, k_values: list[int] | None = None) -> QuantumExperimentResult:
        """Evaluate Grover-style clique search and theoretical query speedups."""
        graph = graph.copy() if graph is not None else self.default_test_graph()
        k_values = k_values or list(range(3, min(7, graph.number_of_nodes() + 1)))
        t0 = time.perf_counter()
        detector = QuantumCliqueDetector(graph, seed=int(self.rng.integers(0, 2**32 - 1)))
        runs = []
        for k in k_values:
            start = time.perf_counter()
            clique = detector.grover_search_k_clique(k)
            speedup = detector.theoretical_speedup_for_k(k)
            runs.append(
                {
                    "k": int(k),
                    "found": clique is not None,
                    "clique": clique or [],
                    "clique_size": len(clique) if clique else 0,
                    "classical_queries": round(speedup["classical_queries"], 6),
                    "grover_queries": round(speedup["grover_queries"], 6),
                    "theoretical_speedup": round(speedup["speedup"], 6),
                    "runtime_sec": round(time.perf_counter() - start, 6),
                }
            )
        return QuantumExperimentResult(
            name="grover_clique_search",
            parameters={"nodes": graph.number_of_nodes(), "edges": graph.number_of_edges(), "k_values": k_values},
            metrics={"runs": runs},
            artifacts={"graph_metrics": self._basic_graph_metrics(graph)},
            runtime_sec=time.perf_counter() - t0,
        )

    def experiment_qaoa_max_clique(
        self,
        graph: nx.Graph | None = None,
        layers: list[int] | None = None,
        iterations: int = 40,
    ) -> QuantumExperimentResult:
        """Run QAOA-like MaxClique optimization for several circuit depths."""
        graph = graph.copy() if graph is not None else self.default_test_graph()
        layers = layers or [1, 2, 3]
        t0 = time.perf_counter()
        runs = []
        for p_layers in layers:
            start = time.perf_counter()
            optimizer = QAOAOptimizer(graph, p_layers=p_layers, seed=int(self.rng.integers(0, 2**32 - 1)))
            gamma, beta, bitstring = optimizer.optimize(iterations=iterations)
            clique = optimizer.extract_clique(bitstring)
            valid = all(graph.has_edge(a, b) for a, b in combinations(clique, 2))
            runs.append(
                {
                    "p_layers": int(p_layers),
                    "iterations": int(iterations),
                    "bitstring": bitstring,
                    "clique": clique,
                    "clique_size": len(clique),
                    "valid_clique": bool(valid),
                    "energy": round(float(optimizer.cost_energy(bitstring)), 6),
                    "gamma": [round(float(x), 6) for x in gamma],
                    "beta": [round(float(x), 6) for x in beta],
                    "runtime_sec": round(time.perf_counter() - start, 6),
                }
            )
        return QuantumExperimentResult(
            name="qaoa_max_clique",
            parameters={"layers": layers, "iterations": iterations, "nodes": graph.number_of_nodes()},
            metrics={"runs": runs},
            artifacts={"graph_metrics": self._basic_graph_metrics(graph)},
            runtime_sec=time.perf_counter() - t0,
        )

    def experiment_hybrid_kernel_cycles(
        self,
        cycles: int = 12,
        initial_nodes: int = 8,
        clique_threshold: int = 4,
    ) -> QuantumExperimentResult:
        """Run complete QuantumHybridGraph cycles and track network evolution."""
        t0 = time.perf_counter()
        kernel = QuantumHybridGraph(
            initial_nodes=initial_nodes,
            clique_threshold=clique_threshold,
            seed=int(self.rng.integers(0, 2**32 - 1)),
        )
        snapshots = []
        for _ in range(cycles):
            kernel.run_cycle()
            snapshots.append(
                {
                    "cycle": kernel.cycle,
                    "nodes": kernel.graph.number_of_nodes(),
                    "edges": kernel.graph.number_of_edges(),
                    "accelerators": len(kernel.accelerators),
                    "density": round(nx.density(kernel.graph), 6) if kernel.graph.number_of_nodes() > 1 else 0.0,
                    "clustering": round(nx.average_clustering(kernel.graph), 6) if kernel.graph.number_of_nodes() > 1 else 0.0,
                }
            )
        return QuantumExperimentResult(
            name="hybrid_kernel_cycles",
            parameters={"cycles": cycles, "initial_nodes": initial_nodes, "clique_threshold": clique_threshold},
            metrics={"snapshots": snapshots, "final_summary": kernel.summary()},
            artifacts={},
            runtime_sec=time.perf_counter() - t0,
        )

    def run_all(self, graph: nx.Graph | None = None) -> list[QuantumExperimentResult]:
        """Run the standard experiment pack."""
        graph = graph.copy() if graph is not None else self.default_test_graph()
        return [
            self.experiment_qpa_growth(),
            self.experiment_grover_clique_search(graph=graph),
            self.experiment_qaoa_max_clique(graph=graph),
            self.experiment_hybrid_kernel_cycles(),
        ]

    def run_all_as_dict(self, graph: nx.Graph | None = None) -> dict[str, Any]:
        results = self.run_all(graph=graph)
        return {
            "seed": self.seed,
            "num_experiments": len(results),
            "results": [result.as_dict() for result in results],
        }




@dataclass(frozen=True)
class QuantumBackendStatus:
    """Availability and configuration status for optional quantum SDK backends."""

    name: str
    available: bool
    version: str | None
    reason: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "available": self.available,
            "version": self.version,
            "reason": self.reason,
        }


class QuantumBackendAdapter:
    """Base adapter interface for future Qiskit/PennyLane integration.

    The project currently runs with built-in NumPy/NetworkX simulators. These
    adapters provide a stable extension point so real SDK backends can be added
    without changing the QuantumHybridGraph public API.
    """

    name = "base"

    def status(self) -> QuantumBackendStatus:
        raise NotImplementedError

    def build_max_clique_qubo(self, graph: nx.Graph, penalty: float = 3.0) -> dict[str, Any]:
        """Return a backend-neutral QUBO representation for MaxClique."""
        nodes = list(graph.nodes)
        linear = {i: -1.0 for i in range(len(nodes))}
        quadratic: dict[tuple[int, int], float] = {}
        for i, j in combinations(range(len(nodes)), 2):
            if not graph.has_edge(nodes[i], nodes[j]):
                quadratic[(i, j)] = float(penalty)
        return {
            "problem": "max_clique",
            "nodes": nodes,
            "linear": linear,
            "quadratic": quadratic,
            "penalty": float(penalty),
            "description": "Minimize -sum(x_i) + penalty * sum(x_i x_j for non-edges).",
        }

    def solve_max_clique_qaoa(
        self,
        graph: nx.Graph,
        p_layers: int = 2,
        iterations: int = 50,
        seed: int | None = None,
    ) -> dict[str, Any]:
        """Solve MaxClique through this backend.

        Subclasses may call Qiskit/PennyLane. The base adapter intentionally
        falls back to the local QAOA-like simulator.
        """
        optimizer = QAOAOptimizer(graph, p_layers=p_layers, seed=seed)
        gamma, beta, bitstring = optimizer.optimize(iterations=iterations)
        clique = optimizer.extract_clique(bitstring)
        return {
            "backend": self.name,
            "mode": "local_fallback",
            "bitstring": bitstring,
            "clique": clique,
            "clique_size": len(clique),
            "gamma": [float(x) for x in gamma],
            "beta": [float(x) for x in beta],
            "energy": float(optimizer.cost_energy(bitstring)),
        }

    def export_max_clique_problem(self, graph: nx.Graph, path: str, penalty: float = 3.0) -> str:
        """Export MaxClique QUBO to JSON for external quantum SDK workflows."""
        qubo = self.build_max_clique_qubo(graph, penalty=penalty)
        serializable = {
            **qubo,
            "linear": {str(k): v for k, v in qubo["linear"].items()},
            "quadratic": {f"{i},{j}": v for (i, j), v in qubo["quadratic"].items()},
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(serializable, f, indent=2, ensure_ascii=False)
        return path


class LocalSimulatorAdapter(QuantumBackendAdapter):
    """Built-in backend using the local QAOA-like simulator."""

    name = "local_simulator"

    def status(self) -> QuantumBackendStatus:
        return QuantumBackendStatus(name=self.name, available=True, version="builtin", reason=None)


class QiskitAdapter(QuantumBackendAdapter):
    """Qiskit adapter using a real Qiskit statevector execution path when installed.

    The adapter builds a QAOA-style circuit for the MaxClique QUBO Ising
    Hamiltonian and evaluates candidate parameters with
    `qiskit.quantum_info.Statevector`. If Qiskit is not installed, it falls back
    to the built-in local simulator while reporting the fallback mode.
    """

    name = "qiskit"

    def status(self) -> QuantumBackendStatus:
        spec = importlib.util.find_spec("qiskit")
        if spec is None:
            return QuantumBackendStatus(self.name, False, None, "qiskit is not installed")
        try:
            import qiskit  # type: ignore

            version = getattr(qiskit, "__version__", "installed")
            return QuantumBackendStatus(self.name, True, str(version), None)
        except Exception as exc:
            return QuantumBackendStatus(self.name, False, None, str(exc))

    def qiskit_install_hint(self) -> str:
        return "pip install qiskit qiskit-aer qiskit-algorithms"

    def _ising_coefficients(self, graph: nx.Graph, penalty: float = 3.0) -> tuple[list[Any], dict[int, float], dict[tuple[int, int], float], float]:
        """Convert MaxClique QUBO to Ising Z / ZZ coefficients."""
        qubo = self.build_max_clique_qubo(graph, penalty=penalty)
        nodes = qubo["nodes"]
        z_terms: dict[int, float] = {i: 0.0 for i in range(len(nodes))}
        zz_terms: dict[tuple[int, int], float] = {}
        offset = 0.0

        for i, coeff in qubo["linear"].items():
            offset += coeff / 2.0
            z_terms[i] += -coeff / 2.0

        for (i, j), coeff in qubo["quadratic"].items():
            offset += coeff / 4.0
            z_terms[i] += -coeff / 4.0
            z_terms[j] += -coeff / 4.0
            zz_terms[(i, j)] = zz_terms.get((i, j), 0.0) + coeff / 4.0

        return nodes, z_terms, zz_terms, offset

    @staticmethod
    def _bitstring_from_state_index(index: int, n: int) -> str:
        """Return bitstring in node order, where character i maps to node i."""
        return "".join("1" if (index >> i) & 1 else "0" for i in range(n))

    @staticmethod
    def _energy_from_bitstring(graph: nx.Graph, nodes: list[Any], bitstring: str, penalty: float = 3.0) -> float:
        chosen = [i for i, bit in enumerate(bitstring) if bit == "1"]
        energy = -float(len(chosen))
        for i, j in combinations(chosen, 2):
            if not graph.has_edge(nodes[i], nodes[j]):
                energy += penalty
        return energy

    def _decode_best_bitstring(self, graph: nx.Graph, nodes: list[Any], probabilities: np.ndarray, penalty: float = 3.0) -> tuple[str, float]:
        best_bitstring = "0" * len(nodes)
        best_key = (float("inf"), 0.0)
        for idx, prob in enumerate(probabilities):
            if prob <= 1e-15:
                continue
            bitstring = self._bitstring_from_state_index(idx, len(nodes))
            energy = self._energy_from_bitstring(graph, nodes, bitstring, penalty=penalty)
            key = (energy, -float(prob))
            if key < best_key:
                best_key = key
                best_bitstring = bitstring
        return best_bitstring, float(best_key[0])

    def solve_max_clique_qaoa(
        self,
        graph: nx.Graph,
        p_layers: int = 2,
        iterations: int = 50,
        seed: int | None = None,
    ) -> dict[str, Any]:
        status = self.status()
        if not status.available:
            result = super().solve_max_clique_qaoa(graph, p_layers=p_layers, iterations=iterations, seed=seed)
            result["backend"] = self.name
            result["mode"] = "local_fallback_unavailable_qiskit"
            result["backend_status"] = status.as_dict()
            return result

        try:
            from qiskit import QuantumCircuit  # type: ignore
            from qiskit.quantum_info import Statevector  # type: ignore
        except Exception as exc:
            result = super().solve_max_clique_qaoa(graph, p_layers=p_layers, iterations=iterations, seed=seed)
            result["backend"] = self.name
            result["mode"] = "local_fallback_qiskit_import_error"
            result["backend_status"] = {**status.as_dict(), "runtime_error": str(exc)}
            return result

        nodes, z_terms, zz_terms, _ = self._ising_coefficients(graph)
        n = len(nodes)
        if n == 0:
            return {
                "backend": self.name,
                "mode": "qiskit_statevector",
                "bitstring": "",
                "clique": [],
                "clique_size": 0,
                "energy": 0.0,
                "backend_status": status.as_dict(),
            }
        if n > 20:
            result = super().solve_max_clique_qaoa(graph, p_layers=p_layers, iterations=iterations, seed=seed)
            result["backend"] = self.name
            result["mode"] = "local_fallback_qiskit_problem_too_large"
            result["backend_status"] = status.as_dict()
            return result

        rng = np.random.default_rng(seed)

        def circuit_probabilities(gamma: np.ndarray, beta: np.ndarray) -> np.ndarray:
            qc = QuantumCircuit(n)
            for qubit in range(n):
                qc.h(qubit)
            for layer in range(p_layers):
                for i, coeff in z_terms.items():
                    if abs(coeff) > 1e-15:
                        qc.rz(2.0 * gamma[layer] * coeff, i)
                for (i, j), coeff in zz_terms.items():
                    if abs(coeff) > 1e-15:
                        if hasattr(qc, "rzz"):
                            qc.rzz(2.0 * gamma[layer] * coeff, i, j)
                        else:
                            from qiskit.circuit.library import RZZGate  # type: ignore

                            qc.append(RZZGate(2.0 * gamma[layer] * coeff), [i, j])
                for qubit in range(n):
                    qc.rx(2.0 * beta[layer], qubit)
            state = Statevector.from_instruction(qc)
            probabilities = np.asarray(state.probabilities(), dtype=float)
            return probabilities / probabilities.sum()

        def expected_energy(gamma: np.ndarray, beta: np.ndarray) -> float:
            probabilities = circuit_probabilities(gamma, beta)
            return float(
                sum(
                    prob * self._energy_from_bitstring(graph, nodes, self._bitstring_from_state_index(idx, n))
                    for idx, prob in enumerate(probabilities)
                    if prob > 1e-15
                )
            )

        best_gamma = rng.uniform(0.0, pi, p_layers)
        best_beta = rng.uniform(0.0, pi / 2.0, p_layers)
        best_value = expected_energy(best_gamma, best_beta)

        for t in range(max(1, iterations)):
            scale = 0.25 * (1.0 - t / max(1, iterations)) + 0.02
            candidate_gamma = np.mod(best_gamma + rng.normal(0.0, scale, p_layers), pi)
            candidate_beta = np.mod(best_beta + rng.normal(0.0, scale, p_layers), pi)
            value = expected_energy(candidate_gamma, candidate_beta)
            if value < best_value:
                best_value = value
                best_gamma = candidate_gamma
                best_beta = candidate_beta

        probabilities = circuit_probabilities(best_gamma, best_beta)
        bitstring, energy = self._decode_best_bitstring(graph, nodes, probabilities)
        clique_indices = [i for i, bit in enumerate(bitstring) if bit == "1"]
        chosen_nodes = [nodes[i] for i in clique_indices]
        subgraph = graph.subgraph(chosen_nodes)
        is_complete = subgraph.number_of_edges() == len(chosen_nodes) * (len(chosen_nodes) - 1) // 2
        clique = chosen_nodes if is_complete else max((list(c) for c in nx.find_cliques(subgraph)), key=len, default=[])

        return {
            "backend": self.name,
            "mode": "qiskit_statevector",
            "bitstring": bitstring,
            "clique": clique,
            "clique_size": len(clique),
            "energy": energy,
            "gamma": [float(x) for x in best_gamma],
            "beta": [float(x) for x in best_beta],
            "backend_status": status.as_dict(),
        }

    def qiskit_qaoa_template(self) -> str:
        """Return a commented code template for hardware/runtime Qiskit QAOA."""
        return """# Qiskit integration notes
# This adapter already supports real Qiskit statevector execution when qiskit is installed.
# For IBM Runtime / hardware execution, replace Statevector evaluation with a Sampler.
# Suggested path:
#   1. Convert QUBO to SparsePauliOp using _ising_coefficients().
#   2. Use qiskit_algorithms.QAOA with a Sampler backend.
#   3. Decode the best measured bitstring into clique nodes.
"""


class PennyLaneAdapter(QuantumBackendAdapter):
    """PennyLane adapter using a real `default.qubit` QNode when installed."""

    name = "pennylane"

    def status(self) -> QuantumBackendStatus:
        spec = importlib.util.find_spec("pennylane")
        if spec is None:
            return QuantumBackendStatus(self.name, False, None, "pennylane is not installed")
        try:
            import pennylane as qml  # type: ignore

            version = getattr(qml, "__version__", "installed")
            return QuantumBackendStatus(self.name, True, str(version), None)
        except Exception as exc:
            return QuantumBackendStatus(self.name, False, None, str(exc))

    def pennylane_install_hint(self) -> str:
        return "pip install pennylane"

    def solve_max_clique_qaoa(
        self,
        graph: nx.Graph,
        p_layers: int = 2,
        iterations: int = 50,
        seed: int | None = None,
    ) -> dict[str, Any]:
        status = self.status()
        if not status.available:
            result = super().solve_max_clique_qaoa(graph, p_layers=p_layers, iterations=iterations, seed=seed)
            result["backend"] = self.name
            result["mode"] = "local_fallback_unavailable_pennylane"
            result["backend_status"] = status.as_dict()
            return result

        try:
            import pennylane as qml  # type: ignore
        except Exception as exc:
            result = super().solve_max_clique_qaoa(graph, p_layers=p_layers, iterations=iterations, seed=seed)
            result["backend"] = self.name
            result["mode"] = "local_fallback_pennylane_import_error"
            result["backend_status"] = {**status.as_dict(), "runtime_error": str(exc)}
            return result

        qiskit_like = QiskitAdapter()
        nodes, z_terms, zz_terms, _ = qiskit_like._ising_coefficients(graph)
        n = len(nodes)
        if n == 0:
            return {
                "backend": self.name,
                "mode": "pennylane_default_qubit",
                "bitstring": "",
                "clique": [],
                "clique_size": 0,
                "energy": 0.0,
                "backend_status": status.as_dict(),
            }
        if n > 20:
            result = super().solve_max_clique_qaoa(graph, p_layers=p_layers, iterations=iterations, seed=seed)
            result["backend"] = self.name
            result["mode"] = "local_fallback_pennylane_problem_too_large"
            result["backend_status"] = status.as_dict()
            return result

        dev = qml.device("default.qubit", wires=n)

        @qml.qnode(dev)
        def circuit(gamma, beta):  # type: ignore[no-untyped-def]
            for qubit in range(n):
                qml.Hadamard(wires=qubit)
            for layer in range(p_layers):
                for i, coeff in z_terms.items():
                    if abs(coeff) > 1e-15:
                        qml.RZ(2.0 * gamma[layer] * coeff, wires=i)
                for (i, j), coeff in zz_terms.items():
                    if abs(coeff) > 1e-15:
                        qml.IsingZZ(2.0 * gamma[layer] * coeff, wires=[i, j])
                for qubit in range(n):
                    qml.RX(2.0 * beta[layer], wires=qubit)
            return qml.probs(wires=range(n))

        rng = np.random.default_rng(seed)

        def expected_energy(gamma: np.ndarray, beta: np.ndarray) -> float:
            probabilities = np.asarray(circuit(gamma, beta), dtype=float)
            return float(
                sum(
                    prob * qiskit_like._energy_from_bitstring(graph, nodes, qiskit_like._bitstring_from_state_index(idx, n))
                    for idx, prob in enumerate(probabilities)
                    if prob > 1e-15
                )
            )

        best_gamma = rng.uniform(0.0, pi, p_layers)
        best_beta = rng.uniform(0.0, pi / 2.0, p_layers)
        best_value = expected_energy(best_gamma, best_beta)

        for t in range(max(1, iterations)):
            scale = 0.25 * (1.0 - t / max(1, iterations)) + 0.02
            candidate_gamma = np.mod(best_gamma + rng.normal(0.0, scale, p_layers), pi)
            candidate_beta = np.mod(best_beta + rng.normal(0.0, scale, p_layers), pi)
            value = expected_energy(candidate_gamma, candidate_beta)
            if value < best_value:
                best_value = value
                best_gamma = candidate_gamma
                best_beta = candidate_beta

        probabilities = np.asarray(circuit(best_gamma, best_beta), dtype=float)
        bitstring, energy = qiskit_like._decode_best_bitstring(graph, nodes, probabilities)
        chosen_nodes = [nodes[i] for i, bit in enumerate(bitstring) if bit == "1"]
        subgraph = graph.subgraph(chosen_nodes)
        is_complete = subgraph.number_of_edges() == len(chosen_nodes) * (len(chosen_nodes) - 1) // 2
        clique = chosen_nodes if is_complete else max((list(c) for c in nx.find_cliques(subgraph)), key=len, default=[])

        return {
            "backend": self.name,
            "mode": "pennylane_default_qubit",
            "bitstring": bitstring,
            "clique": clique,
            "clique_size": len(clique),
            "energy": energy,
            "gamma": [float(x) for x in best_gamma],
            "beta": [float(x) for x in best_beta],
            "backend_status": status.as_dict(),
        }

    def pennylane_qaoa_template(self) -> str:
        """Return a commented code template for hardware/plugin PennyLane QAOA."""
        return """# PennyLane integration notes
# This adapter already supports real PennyLane default.qubit execution when pennylane is installed.
# To use hardware or cloud plugins, replace qml.device('default.qubit', wires=n)
# with the target plugin device while keeping the QNode structure.
"""


class QuantumBackendRegistry:
    """Registry and factory for optional quantum SDK backends."""

    def __init__(self):
        local = LocalSimulatorAdapter()
        self.adapters: dict[str, QuantumBackendAdapter] = {
            "local": local,
            "local_simulator": local,
            "qiskit": QiskitAdapter(),
            "pennylane": PennyLaneAdapter(),
        }

    def get(self, name: str = "local") -> QuantumBackendAdapter:
        key = name.lower().strip()
        if key not in self.adapters:
            raise ValueError(f"Unknown backend '{name}'. Available: {sorted(self.adapters)}")
        return self.adapters[key]

    def statuses(self) -> dict[str, dict[str, Any]]:
        seen: set[str] = set()
        result: dict[str, dict[str, Any]] = {}
        for adapter in self.adapters.values():
            if adapter.name in seen:
                continue
            seen.add(adapter.name)
            result[adapter.name] = adapter.status().as_dict()
        return result

    def integration_guide(self) -> dict[str, Any]:
        qiskit = QiskitAdapter()
        pennylane = PennyLaneAdapter()
        return {
            "purpose": "Stable extension layer for connecting real Qiskit or PennyLane backends later.",
            "current_default": "local_simulator",
            "statuses": self.statuses(),
            "install": {
                "qiskit": qiskit.qiskit_install_hint(),
                "pennylane": pennylane.pennylane_install_hint(),
            },
            "templates": {
                "qiskit": qiskit.qiskit_qaoa_template(),
                "pennylane": pennylane.pennylane_qaoa_template(),
            },
        }


# ======================================================================
# QuantumHybridGraph – hybrid quantum-classical kernel
# ======================================================================


class QuantumHybridGraph(UniverseKernel):
    """Evolutionary graph kernel assisted by quantum-inspired heuristics."""

    def __init__(
        self,
        initial_nodes: int = 1,
        mode: str = "simulated",
        qpa_alpha: float = 1.5,
        qaoa_layers: int = 2,
        clique_threshold: int = 5,
        seed: int | None = None,
    ):
        super().__init__(initial_nodes=initial_nodes, seed=seed)
        self.mode = mode
        self.qpa_alpha = float(qpa_alpha)
        self.qaoa_layers = int(max(1, qaoa_layers))
        self.clique_threshold = int(max(2, clique_threshold))
        self.accelerators: list[list[int]] = []
        self.accelerator_details: list[Accelerator] = []
        self.accelerator_history: list[int] = []
        self.connection_optimization_history: list[dict[str, Any]] = []
        self.last_connection_candidates: list[ConnectionCandidate] = []
        self.last_intelligent_acceleration_report: AcceleratorDetectionReport | None = None
        self.analysis_history: list[dict[str, Any]] = []
        self.last_analysis_report: GraphAnalysisReport | None = None
        self.quantum_experiment_history: list[dict[str, Any]] = []
        self.last_quantum_experiments: dict[str, Any] | None = None
        self.backend_registry = QuantumBackendRegistry()
        self.quantum_backend_name = "local_simulator"
        self.quantum_speedup_estimate: float = 0.0

        # --- Network Reliability Engineer (NRE) monitoring -----------------
        # The agent is attached lazily because AdaptiveNRE is defined later in
        # this module. When enabled, run_cycle() records a security snapshot and
        # can auto-quarantine anomalous nodes every cycle.
        self.nre: "AdaptiveNRE | None" = None
        self.nre_monitoring_enabled: bool = False
        self.nre_auto_quarantine: bool = False
        self.nre_quarantine_limit: int | None = None
        self.nre_incident_log_path: str | None = None
        self.nre_incident_history: list[dict[str, Any]] = []

    def expand_qpa(self) -> int:
        """Add a new node without copying the graph into a separate QPA object.

        The new node id is one past the current maximum integer node id, so the
        method stays correct even when earlier nodes have been removed (for
        example by NRE quarantine), instead of assuming a contiguous range.
        """
        existing = list(self.graph.nodes)
        int_ids = [node for node in existing if isinstance(node, int)]
        new_node = (max(int_ids) + 1) if int_ids else 0
        self.graph.add_node(new_node)
        if not existing:
            return new_node

        def weight(node: Any) -> float:
            degree = self.graph.degree(node)
            if degree == 0:
                return 1.0
            return max(sum(max(1, self.graph.degree(nbr)) ** (self.qpa_alpha - 1.0) for nbr in self.graph.neighbors(node)), 1.0)

        weights = np.array([weight(node) for node in existing], dtype=float)
        target = existing[int(self.rng.choice(len(existing), p=weights / weights.sum()))]
        d_target = self.graph.degree(target)
        r_prob = d_target / (d_target + 1.0) if d_target > 0 else 0.5
        if self.rng.random() < r_prob and d_target > 0:
            neighbor = int(self.rng.choice(list(self.graph.neighbors(target))))
            self.graph.add_edge(new_node, neighbor)
        else:
            self.graph.add_edge(new_node, target)
        return new_node

    @staticmethod
    def _small_world_metrics(graph: nx.Graph) -> dict[str, Any]:
        """Return latency-oriented metrics used by shortcut optimization."""
        if graph.number_of_nodes() <= 1:
            average_path = 0.0
        elif nx.is_connected(graph):
            average_path = float(nx.average_shortest_path_length(graph))
        else:
            average_path = None
        return {
            "nodes": graph.number_of_nodes(),
            "edges": graph.number_of_edges(),
            "connected_components": nx.number_connected_components(graph) if graph.number_of_nodes() else 0,
            "density": round(float(nx.density(graph)), 6) if graph.number_of_nodes() > 1 else 0.0,
            "global_efficiency": round(float(nx.global_efficiency(graph)), 6) if graph.number_of_nodes() > 1 else 0.0,
            "average_shortest_path_length": round(average_path, 6) if average_path is not None else None,
            "average_clustering": round(float(nx.average_clustering(graph)), 6) if graph.number_of_nodes() else 0.0,
        }

    def intelligent_acceleration(
        self,
        min_size: int | None = None,
        min_density: float = 0.65,
        max_accelerators: int = 20,
        shortcut_edges: int = 1,
        max_candidates: int = 2500,
        apply_shortcuts: bool = True,
    ) -> AcceleratorDetectionReport:
        """Run Accelerator Detection plus Small-World shortcut optimization.

        Detection algorithms:
        - `find_cliques`: finds fully connected high-throughput clusters.
        - k-core decomposition: finds cohesive, resilient processing cores.

        Shortcut optimization then proposes or adds long-range edges between
        clusters/communities/accelerators to reduce average communication
        latency and increase global efficiency, reproducing a Small-World effect.
        """
        before_metrics = self._small_world_metrics(self.graph)
        accelerators = self.detect_accelerators(
            min_size=min_size,
            min_density=min_density,
            max_results=max_accelerators,
            use_grover_hint=True,
        )

        shortcut_candidates = self.propose_connection_optimizations(
            add_edges=shortcut_edges,
            max_candidates=max_candidates,
        )
        if apply_shortcuts:
            added_shortcuts = self.optimize_connections(
                add_edges=shortcut_edges,
                max_candidates=max_candidates,
                record=True,
            )
        else:
            added_shortcuts = []

        after_metrics = self._small_world_metrics(self.graph)
        report = AcceleratorDetectionReport(
            accelerators=accelerators,
            shortcut_candidates=shortcut_candidates,
            added_shortcuts=added_shortcuts,
            before_metrics=before_metrics,
            after_metrics=after_metrics,
            parameters={
                "min_size": int(min_size or self.clique_threshold),
                "min_density": float(min_density),
                "max_accelerators": int(max_accelerators),
                "shortcut_edges": int(shortcut_edges),
                "max_candidates": int(max_candidates),
                "apply_shortcuts": bool(apply_shortcuts),
            },
        )
        self.last_intelligent_acceleration_report = report
        return report

    def detect_accelerators(
        self,
        min_size: int | None = None,
        min_density: float = 0.65,
        max_results: int = 20,
        use_grover_hint: bool = True,
    ) -> list[Accelerator]:
        """Detect and rank accelerator subgraphs.

        Accelerators are dense, strategically useful subgraphs: cliques,
        near-cliques, k-core components, communities and hub neighborhoods.
        The method stores both a simple node-list view in `self.accelerators`
        and rich metric objects in `self.accelerator_details`.
        """
        threshold = int(min_size or self.clique_threshold)
        if self.graph.number_of_nodes() < threshold:
            self.accelerators = []
            self.accelerator_details = []
            self.accelerator_history.append(0)
            return []

        detector = GraphAcceleratorDetector(self.graph)
        details = detector.detect(
            min_size=threshold,
            min_density=min_density,
            max_results=max_results,
        )

        # Add a Grover-style clique candidate if the structural detector missed it.
        if use_grover_hint:
            grover = QuantumCliqueDetector(self.graph, seed=int(self.rng.integers(0, 2**32 - 1)))
            upper = min(10, self.graph.number_of_nodes())
            for k in range(threshold, upper + 1):
                clique = grover.grover_search_k_clique(k)
                if clique is None:
                    break
                existing = {frozenset(acc.nodes) for acc in details}
                if frozenset(clique) not in existing:
                    metric = detector._metrics(set(clique), "grover_clique", len(details))
                    if metric is not None:
                        details.append(metric)

        details.sort(key=lambda acc: (acc.score, acc.size, acc.density), reverse=True)
        details = [Accelerator(id=i, **{k: v for k, v in acc.__dict__.items() if k != "id"}) for i, acc in enumerate(details[:max_results])]

        self.accelerator_details = details
        self.accelerators = [list(acc.nodes) for acc in details]
        self.accelerator_history.append(len(details))

        n = self.graph.number_of_nodes()
        if n > 0:
            classical = 2.0**n
            quantum = 2.0 ** (n / 2.0)
            self.quantum_speedup_estimate = classical / quantum

        return details

    def detect_accelerators_quantum(self) -> None:
        """Backward-compatible alias for accelerator detection."""
        self.detect_accelerators()

    def quantum_backend_status(self) -> dict[str, dict[str, Any]]:
        """Return availability status for local, Qiskit and PennyLane backends."""
        return self.backend_registry.statuses()

    def quantum_integration_guide(self) -> dict[str, Any]:
        """Return installation hints and code templates for Qiskit/PennyLane."""
        return self.backend_registry.integration_guide()

    def set_quantum_backend(self, backend: str = "local") -> QuantumBackendStatus:
        """Select a backend name for future quantum calls.

        If the requested SDK is unavailable, the status explains why. The local
        simulator remains usable regardless.
        """
        adapter = self.backend_registry.get(backend)
        status = adapter.status()
        self.quantum_backend_name = adapter.name if status.available else "local_simulator"
        return status

    def solve_max_clique_with_backend(
        self,
        backend: str | None = None,
        p_layers: int | None = None,
        iterations: int = 50,
    ) -> dict[str, Any]:
        """Solve MaxClique through a selected backend adapter.

        Qiskit/PennyLane adapters currently expose the integration scaffold and
        fall back to the local simulator unless extended with real SDK calls.
        """
        adapter = self.backend_registry.get(backend or self.quantum_backend_name)
        result = adapter.solve_max_clique_qaoa(
            self.graph,
            p_layers=p_layers or self.qaoa_layers,
            iterations=iterations,
            seed=self.seed,
        )
        result["requested_backend_status"] = adapter.status().as_dict()
        return result

    def export_max_clique_qubo(self, path: str = "max_clique_qubo.json", backend: str = "local") -> str:
        """Export the current graph's MaxClique QUBO for Qiskit/PennyLane workflows."""
        adapter = self.backend_registry.get(backend)
        return adapter.export_max_clique_problem(self.graph, path)

    def routing_interface(self, protocol: str = "bgp") -> "BGPSDNInterface":
        """Return a BGP/SDN interface bound to this kernel.

        Reuses the attached NRE's routing interface when available so the
        command journal stays unified across security and optimization actions.
        """
        if getattr(self, "nre", None) is not None and getattr(self.nre, "routing", None) is not None:
            return self.nre.routing
        return BGPSDNInterface(self, protocol=protocol)

    def optimize_routes_via_qaoa(
        self,
        backend: str | None = None,
        p_layers: int | None = None,
        iterations: int = 50,
        protocol: str = "bgp",
    ) -> dict[str, Any]:
        """Solve MaxClique on a quantum backend and map it to routing policy.

        This connects the Quantum Backend (Qiskit/PennyLane) global optimization
        to the BGP/SDN control plane: the densest cluster (clique) is programmed
        as a high-priority shortcut path, steering traffic through the optimal
        low-latency core.
        """
        result = self.solve_max_clique_with_backend(
            backend=backend,
            p_layers=p_layers,
            iterations=iterations,
        )
        clique = result.get("clique", [])
        routing = self.routing_interface(protocol=protocol)
        command = routing.path_to_policy(
            clique,
            reason=f"qaoa_max_clique({result.get('backend', 'local')})",
            priority=300,
        )
        return {
            "backend_result": result,
            "clique": clique,
            "routing_policy": command.as_dict(),
            "bgp": command.to_bgp(),
            "sdn": command.to_sdn(),
        }

    def run_quantum_experiments(
        self,
        include_full_suite: bool = True,
        export_path: str | None = None,
    ) -> dict[str, Any]:
        """Run quantum-inspired algorithm experiments on the current graph.

        The experiment pack covers QPA growth, Grover-style clique search,
        QAOA-like MaxClique and, optionally, full hybrid-kernel evolution.
        """
        suite = QuantumExperimentSuite(seed=self.seed)
        graph = self.graph.copy()
        if include_full_suite:
            result = suite.run_all_as_dict(graph=graph)
        else:
            experiments = [
                suite.experiment_grover_clique_search(graph=graph),
                suite.experiment_qaoa_max_clique(graph=graph),
            ]
            result = {
                "seed": self.seed,
                "num_experiments": len(experiments),
                "results": [experiment.as_dict() for experiment in experiments],
            }

        self.last_quantum_experiments = result
        self.quantum_experiment_history.append(
            {
                "cycle": self.cycle,
                "num_experiments": result["num_experiments"],
                "experiment_names": [item["name"] for item in result["results"]],
            }
        )
        if export_path is not None:
            with open(export_path, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
        return result

    def analyze_network(self, top_n: int = 10, refresh_accelerators: bool = True, record: bool = True) -> GraphAnalysisReport:
        """Run full network and graph analysis.

        The report includes overview metrics, connectivity, paths, centrality,
        communities, degree distribution, resilience, detected accelerators and
        actionable recommendations.
        """
        if refresh_accelerators:
            self.detect_accelerators()
        analyzer = GraphNetworkAnalyzer(self.graph, self.accelerator_details)
        report = analyzer.analyze(top_n=top_n)
        self.last_analysis_report = report
        if record:
            data = report.as_dict()
            self.analysis_history.append(
                {
                    "cycle": self.cycle,
                    "overview": data["overview"],
                    "connectivity": data["connectivity"],
                    "paths": data["paths"],
                    "recommendations": data["recommendations"],
                }
            )
        return report

    def export_analysis_json(self, path: str = "graph_analysis_report.json", top_n: int = 10) -> str:
        """Analyze the graph and save the report as JSON."""
        report = self.analyze_network(top_n=top_n)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(report.as_dict(), f, indent=2, ensure_ascii=False)
        return path

    def propose_connection_optimizations(
        self,
        add_edges: int = 1,
        max_candidates: int = 2500,
    ) -> list[ConnectionCandidate]:
        """Return the best proposed network connections without modifying the graph."""
        optimizer = NetworkConnectionOptimizer(self.graph, self.accelerator_details)
        proposals = optimizer.optimize(add_edges=add_edges, max_candidates=max_candidates, dry_run=True)
        self.last_connection_candidates = proposals
        return proposals

    def optimize_connections(
        self,
        add_edges: int = 1,
        max_candidates: int = 2500,
        record: bool = True,
    ) -> list[ConnectionCandidate]:
        """Optimize network connections by adding high-value shortcut edges.

        This is the main implementation of network connection optimization. It
        greedily adds edges that improve global efficiency, shorten paths, bridge
        components/communities and connect accelerator subgraphs to the broader
        network.
        """
        before = self.summary()
        optimizer = NetworkConnectionOptimizer(self.graph, self.accelerator_details)
        selected = optimizer.optimize(add_edges=add_edges, max_candidates=max_candidates, dry_run=False)
        self.last_connection_candidates = selected

        if record and selected:
            after = self.summary()
            self.connection_optimization_history.append(
                {
                    "cycle": self.cycle,
                    "added_edges": [candidate.as_dict() for candidate in selected],
                    "before": {
                        "edges": before["edges"],
                        "density": before["density"],
                        "clustering": before["clustering"],
                        "connected": before["connected"],
                    },
                    "after": {
                        "edges": after["edges"],
                        "density": after["density"],
                        "clustering": after["clustering"],
                        "connected": after["connected"],
                    },
                }
            )
        return selected

    def optimize_via_qaoa(self, add_edges: int = 1, max_candidates: int = 2500) -> list[ConnectionCandidate]:
        """Optimize network shortcuts using a QAOA-derived clique as an anchor.

        The previous implementation delegated to generic connection optimization.
        This version first computes a QAOA MaxClique candidate, measures clique
        purity, then prioritizes deterministic shortcut candidates touching the
        QAOA clique. Random shortcuts are avoided unless no ranked candidate is
        available.
        """
        if self.graph.number_of_nodes() < 3:
            return []
        if not self.accelerator_details:
            self.detect_accelerators()

        anchor_nodes: set[Any] = set()
        for accelerator in self.accelerator_details[:5]:
            anchor_nodes.update(accelerator.nodes)
        if not anchor_nodes:
            # Use high-degree nodes as a deterministic fallback anchor set.
            anchor_nodes = {node for node, _ in sorted(self.graph.degree, key=lambda item: item[1], reverse=True)[: min(12, self.graph.number_of_nodes())]}

        selected_nodes = list(anchor_nodes)
        if len(selected_nodes) > 12:
            selected_nodes = list(self.rng.choice(selected_nodes, size=12, replace=False))
        subgraph = self.graph.subgraph(selected_nodes).copy()
        if subgraph.number_of_nodes() < 2:
            return []

        qaoa = QAOAOptimizer(subgraph, p_layers=self.qaoa_layers, seed=int(self.rng.integers(0, 2**32 - 1)))
        gamma, beta, bitstring = qaoa.optimize(iterations=40)
        raw_selected = qaoa.extract_selected_nodes(bitstring)
        raw_purity = qaoa.clique_purity(raw_selected)
        qaoa_clique = qaoa.extract_clique(bitstring)
        clique_purity = qaoa.clique_purity(qaoa_clique)

        self.last_qaoa_result = {
            "bitstring": bitstring,
            "raw_selected_nodes": raw_selected,
            "raw_clique_purity": round(raw_purity, 6),
            "projected_clique": qaoa_clique,
            "projected_clique_purity": round(clique_purity, 6),
            "gamma": [float(x) for x in gamma],
            "beta": [float(x) for x in beta],
            "optimizer_metadata": getattr(qaoa, "last_optimizer_metadata", None),
        }

        if len(qaoa_clique) < 1:
            return self.optimize_connections(add_edges=add_edges, max_candidates=max_candidates)

        ranked = NetworkConnectionOptimizer(self.graph, self.accelerator_details).rank_candidates(max_candidates=max_candidates)
        clique_set = set(qaoa_clique)
        prioritized = [candidate for candidate in ranked if candidate.source in clique_set or candidate.target in clique_set]
        fallback = [candidate for candidate in ranked if candidate not in prioritized]
        chosen = (prioritized + fallback)[: max(0, int(add_edges))]

        added: list[ConnectionCandidate] = []
        before = self.summary()
        for candidate in chosen:
            if candidate.source != candidate.target and not self.graph.has_edge(candidate.source, candidate.target):
                self.graph.add_edge(candidate.source, candidate.target)
                added.append(candidate)

        self.last_connection_candidates = added
        if added:
            after = self.summary()
            self.connection_optimization_history.append(
                {
                    "cycle": self.cycle,
                    "method": "qaoa_clique_anchored",
                    "qaoa_result": self.last_qaoa_result,
                    "added_edges": [candidate.as_dict() for candidate in added],
                    "before": {
                        "edges": before["edges"],
                        "density": before["density"],
                        "clustering": before["clustering"],
                        "connected": before["connected"],
                    },
                    "after": {
                        "edges": after["edges"],
                        "density": after["density"],
                        "clustering": after["clustering"],
                        "connected": after["connected"],
                    },
                }
            )
        return added

    def attach_reliability_engineer(
        self,
        nre: "AdaptiveNRE | None" = None,
        **nre_kwargs: Any,
    ) -> "AdaptiveNRE":
        """Attach an ``AdaptiveNRE`` agent to this kernel.

        If ``nre`` is ``None`` a new ``AdaptiveNRE`` is created on this kernel
        with the provided keyword arguments. The agent is stored on
        ``self.nre`` and reused by per-cycle monitoring.
        """
        if nre is None:
            nre = AdaptiveNRE(self, **nre_kwargs)
        self.nre = nre
        return nre

    def enable_nre_monitoring(
        self,
        nre: "AdaptiveNRE | None" = None,
        auto_quarantine: bool = False,
        quarantine_limit: int | None = None,
        incident_log_path: str | None = None,
        **nre_kwargs: Any,
    ) -> "AdaptiveNRE":
        """Enable automatic NRE security monitoring inside ``run_cycle``.

        Each subsequent ``run_cycle`` call adapts the reliability threshold,
        records a security incident snapshot and, when ``auto_quarantine`` is
        set, isolates anomalous nodes into the sandbox. When
        ``incident_log_path`` is given, the JSON audit trail is appended every
        cycle.
        """
        agent = self.attach_reliability_engineer(nre, **nre_kwargs)
        self.nre_monitoring_enabled = True
        self.nre_auto_quarantine = bool(auto_quarantine)
        self.nre_quarantine_limit = quarantine_limit
        self.nre_incident_log_path = incident_log_path
        return agent

    def disable_nre_monitoring(self) -> None:
        """Stop automatic per-cycle NRE monitoring (the agent stays attached)."""
        self.nre_monitoring_enabled = False

    def run_nre_monitoring_step(self) -> dict[str, Any] | None:
        """Run one NRE monitoring step: adapt, (optionally) quarantine and log.

        Returns the recorded incident snapshot, or ``None`` when no agent is
        attached.
        """
        if self.nre is None:
            return None

        self.nre.adapt_threshold()
        quarantine_events: list[dict[str, Any]] = []
        if self.nre_auto_quarantine:
            quarantine_events = self.nre.auto_quarantine(limit=self.nre_quarantine_limit)

        log = self.nre.incident_log()
        snapshot = {
            "cycle": self.cycle,
            "critical_energy_threshold": log["adaptation"]["critical_energy_threshold"],
            "num_incidents": log["num_incidents"],
            "quarantine_zone": log["quarantine_zone"],
            "quarantined_this_cycle": [event["node"] for event in quarantine_events if event.get("status") == "quarantined"],
            "sandbox_nodes": log["sandbox"]["num_nodes"],
        }
        self.nre_incident_history.append(snapshot)

        if self.nre_incident_log_path:
            self.nre.export_incident_log(self.nre_incident_log_path, append=True)

        return snapshot

    def run_cycle(self) -> None:
        self.expand_qpa()
        self.detect_accelerators()
        self.optimize_via_qaoa()
        self.cycle += 1
        if self.nre_monitoring_enabled and self.nre is not None:
            self.run_nre_monitoring_step()
        self._record_history()

    def export_dashboard_html(
        self,
        path: str = "quantum_hybrid_graph_dashboard.html",
        title: str = "QuantumHybridGraph Dashboard",
        nre: "AdaptiveNRE | None" = None,
    ) -> str:
        """Export a standalone interactive HTML dashboard for this graph.

        If an ``AdaptiveNRE`` instance is supplied, a Security panel with
        adaptive threshold, anomalies, quarantine zone and sandbox state is
        included.
        """
        return save_dashboard_html(self, path=path, title=title, nre=nre)

    # ------------------------------------------------------------------
    # Checkpoint / restore (full kernel state)
    # ------------------------------------------------------------------

    CHECKPOINT_VERSION = 1

    def checkpoint(self) -> dict[str, Any]:
        """Return a JSON-serializable snapshot of the full kernel state.

        The checkpoint captures everything needed to reconstruct the kernel
        identically after a process restart or for disaster recovery:

          - the graph (node-link form, preserving node ids and edge attributes),
          - the evolution clock (``cycle``) and ``history``,
          - the random generator state (so future ``run_cycle`` draws are
            deterministic continuations),
          - kernel configuration (``mode``, ``qpa_alpha``, ``qaoa_layers``,
            ``clique_threshold``, ``seed``, ``initial_nodes``),
          - accelerator/analysis/connection/experiment histories,
          - NRE monitoring flags and per-cycle incident history,
          - the attached ``AdaptiveNRE`` agent state (threshold, sandbox,
            quarantine/recovery trails, routing journal), when present.

        Derived caches (rich report objects, backend registry) are intentionally
        not persisted; they are recomputed lazily on demand after restore.
        """
        state: dict[str, Any] = {
            "version": self.CHECKPOINT_VERSION,
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "config": {
                "initial_nodes": self.initial_nodes,
                "seed": self.seed,
                "mode": self.mode,
                "qpa_alpha": self.qpa_alpha,
                "qaoa_layers": self.qaoa_layers,
                "clique_threshold": self.clique_threshold,
            },
            "graph": nx.node_link_data(self.graph, edges="edges"),
            "cycle": self.cycle,
            "history": list(self.history),
            "rng_state": self.rng.bit_generator.state,
            "accelerators": [list(a) for a in self.accelerators],
            "accelerator_history": list(self.accelerator_history),
            "connection_optimization_history": list(self.connection_optimization_history),
            "analysis_history": list(self.analysis_history),
            "quantum_experiment_history": list(self.quantum_experiment_history),
            "last_quantum_experiments": self.last_quantum_experiments,
            "quantum_backend_name": self.quantum_backend_name,
            "quantum_speedup_estimate": self.quantum_speedup_estimate,
            "nre_monitoring": {
                "enabled": self.nre_monitoring_enabled,
                "auto_quarantine": self.nre_auto_quarantine,
                "quarantine_limit": self.nre_quarantine_limit,
                "incident_log_path": self.nre_incident_log_path,
                "incident_history": list(self.nre_incident_history),
            },
            "nre": self.nre.checkpoint_state() if self.nre is not None else None,
        }
        return state

    def save_checkpoint(self, path: str = "kernel_checkpoint.json") -> str:
        """Persist :meth:`checkpoint` to a JSON file. Returns the path."""
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(self.checkpoint(), handle, ensure_ascii=False, indent=2)
        return path

    def restore(self, state: dict[str, Any]) -> "QuantumHybridGraph":
        """Restore full kernel state in place from a :meth:`checkpoint` payload."""
        version = state.get("version")
        if version != self.CHECKPOINT_VERSION:
            raise ValueError(
                f"Unsupported checkpoint version {version!r}; "
                f"expected {self.CHECKPOINT_VERSION}."
            )

        config = state.get("config", {})
        self.initial_nodes = int(config.get("initial_nodes", self.initial_nodes))
        self.seed = config.get("seed", self.seed)
        self.mode = config.get("mode", self.mode)
        self.qpa_alpha = float(config.get("qpa_alpha", self.qpa_alpha))
        self.qaoa_layers = int(config.get("qaoa_layers", self.qaoa_layers))
        self.clique_threshold = int(config.get("clique_threshold", self.clique_threshold))

        self.graph = nx.node_link_graph(state["graph"], edges="edges")
        self.cycle = int(state.get("cycle", 0))
        self.history = list(state.get("history", []))

        # Restore the RNG so continued evolution is a deterministic continuation.
        rng_state = state.get("rng_state")
        if rng_state is not None:
            self.rng = np.random.default_rng()
            self.rng.bit_generator.state = rng_state

        self.accelerators = [list(a) for a in state.get("accelerators", [])]
        self.accelerator_history = list(state.get("accelerator_history", []))
        self.connection_optimization_history = list(state.get("connection_optimization_history", []))
        self.analysis_history = list(state.get("analysis_history", []))
        self.quantum_experiment_history = list(state.get("quantum_experiment_history", []))
        self.last_quantum_experiments = state.get("last_quantum_experiments")
        self.quantum_backend_name = state.get("quantum_backend_name", self.quantum_backend_name)
        self.quantum_speedup_estimate = float(state.get("quantum_speedup_estimate", 0.0))

        # Reset derived caches; they are recomputed lazily on demand.
        self.accelerator_details = []
        self.last_connection_candidates = []
        self.last_intelligent_acceleration_report = None
        self.last_analysis_report = None

        monitoring = state.get("nre_monitoring", {})
        self.nre_auto_quarantine = bool(monitoring.get("auto_quarantine", False))
        self.nre_quarantine_limit = monitoring.get("quarantine_limit")
        self.nre_incident_log_path = monitoring.get("incident_log_path")
        self.nre_incident_history = list(monitoring.get("incident_history", []))

        nre_state = state.get("nre")
        if nre_state is not None:
            agent = AdaptiveNRE(self)
            agent.restore_state(nre_state)
            self.nre = agent
            self.nre_monitoring_enabled = bool(monitoring.get("enabled", False))
        else:
            self.nre = None
            self.nre_monitoring_enabled = False
        return self

    @classmethod
    def from_checkpoint(cls, source: "str | dict[str, Any]") -> "QuantumHybridGraph":
        """Build a kernel from a checkpoint dict or a JSON file path."""
        if isinstance(source, str):
            with open(source, encoding="utf-8") as handle:
                state = json.load(handle)
        else:
            state = source
        config = state.get("config", {})
        kernel = cls(
            initial_nodes=int(config.get("initial_nodes", 1)),
            mode=config.get("mode", "simulated"),
            qpa_alpha=float(config.get("qpa_alpha", 1.5)),
            qaoa_layers=int(config.get("qaoa_layers", 2)),
            clique_threshold=int(config.get("clique_threshold", 5)),
            seed=config.get("seed"),
        )
        return kernel.restore(state)

    def summary(self) -> dict[str, Any]:
        base = super().summary()
        base.update(
            {
                "num_accelerators": len(self.accelerators),
                "accelerator_sizes": [len(a) for a in self.accelerators],
                "accelerator_history": self.accelerator_history[-10:],
                "top_accelerators": [acc.as_dict() for acc in self.accelerator_details[:5]],
                "last_connection_candidates": [candidate.as_dict() for candidate in self.last_connection_candidates[:5]],
                "last_intelligent_acceleration_report": getattr(self, "last_intelligent_acceleration_report", None).as_dict()
                if getattr(self, "last_intelligent_acceleration_report", None)
                else None,
                "last_qaoa_result": getattr(self, "last_qaoa_result", None),
                "connection_optimization_history": self.connection_optimization_history[-5:],
                "adaptive_optimization_result": getattr(self, "adaptive_optimization_result", None).as_dict()
                if getattr(self, "adaptive_optimization_result", None)
                else None,
                "adaptive_optimization_history": getattr(self, "adaptive_optimization_history", [])[-5:],
                "last_analysis": self.last_analysis_report.as_dict() if self.last_analysis_report else None,
                "analysis_history": self.analysis_history[-5:],
                "last_quantum_experiments": self.last_quantum_experiments,
                "quantum_experiment_history": self.quantum_experiment_history[-5:],
                "quantum_backend": self.quantum_backend_name,
                "quantum_backend_status": self.quantum_backend_status(),
                "mode": self.mode,
                "qpa_alpha": self.qpa_alpha,
                "qaoa_layers": self.qaoa_layers,
                "circuit_depth_selection_result": getattr(self, "circuit_depth_selection_result", None).as_dict()
                if getattr(self, "circuit_depth_selection_result", None)
                else None,
                "circuit_depth_selection_history": getattr(self, "circuit_depth_selection_history", [])[-5:],
                "quantum_speedup_estimate": f"{self.quantum_speedup_estimate:.1f}×" if self.quantum_speedup_estimate > 0 else "N/A",
                "nre_monitoring_enabled": self.nre_monitoring_enabled,
                "nre_incident_history": self.nre_incident_history[-10:],
            }
        )
        return base

    def __repr__(self) -> str:
        return (
            f"QuantumHybridGraph(cycle={self.cycle}, nodes={self.graph.number_of_nodes()}, "
            f"edges={self.graph.number_of_edges()}, mode={self.mode}, accelerators={len(self.accelerators)})"
        )


# ======================================================================
# Benchmark and visualization
# ======================================================================


def compare_classical_vs_quantum(cycles: int = 40, initial_nodes: int = 10, seed: int = 42) -> dict[str, Any]:
    """Compare classical IntelligenceAcceleration with QuantumHybridGraph."""
    classical = IntelligenceAcceleration(initial_nodes=initial_nodes, clique_threshold=5, seed=seed)
    t0 = time.perf_counter()
    for _ in range(cycles):
        classical.run_cycle()
    t_classical = time.perf_counter() - t0
    cs = classical.summary()

    quantum = QuantumHybridGraph(initial_nodes=initial_nodes, mode="simulated", clique_threshold=5, seed=seed)
    t0 = time.perf_counter()
    for _ in range(cycles):
        quantum.run_cycle()
    t_quantum = time.perf_counter() - t0
    qs = quantum.summary()

    return {
        "classical": {
            "time_sec": round(t_classical, 6),
            "nodes": cs["nodes"],
            "edges": cs["edges"],
            "accelerators": cs["num_accelerators"],
            "clustering": round(cs.get("clustering", 0.0), 4),
        },
        "quantum_simulated": {
            "time_sec": round(t_quantum, 6),
            "nodes": qs["nodes"],
            "edges": qs["edges"],
            "accelerators": qs["num_accelerators"],
            "clustering": round(qs.get("clustering", 0.0), 4),
            "theoretical_speedup": qs["quantum_speedup_estimate"],
        },
    }


def save_visualization_html(graph: nx.Graph, path: str = "quantum_hybrid_graph.html", title: str = "QuantumHybridGraph graph") -> None:
    """Save a standalone HTML visualization with embedded SVG and metric data."""
    if graph.number_of_nodes() == 0:
        positions = {}
    else:
        positions = nx.spring_layout(graph, seed=7)

    width, height = 920, 640
    xs = [p[0] for p in positions.values()] or [0]
    ys = [p[1] for p in positions.values()] or [0]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)

    def scale(value: float, lo: float, hi: float, out_lo: float, out_hi: float) -> float:
        if abs(hi - lo) < 1e-12:
            return (out_lo + out_hi) / 2
        return out_lo + (value - lo) * (out_hi - out_lo) / (hi - lo)

    coords: dict[int, tuple[float, float]] = {}
    for node, (x, y) in positions.items():
        coords[node] = (scale(float(x), min_x, max_x, 70, width - 70), scale(float(y), min_y, max_y, 70, height - 70))

    degrees = dict(graph.degree())
    max_deg = max(degrees.values(), default=1)

    edge_svg = []
    for a, b in graph.edges:
        x1, y1 = coords[a]
        x2, y2 = coords[b]
        edge_svg.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" />')

    node_svg = []
    for node in graph.nodes:
        x, y = coords[node]
        deg = degrees[node]
        r = 5 + 13 * deg / max_deg
        node_svg.append(
            f'<g><circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" />'
            f'<text x="{x:.1f}" y="{y + 4:.1f}">{node}</text><title>node={node}, degree={deg}</title></g>'
        )

    metrics = {
        "nodes": graph.number_of_nodes(),
        "edges": graph.number_of_edges(),
        "density": round(nx.density(graph), 4) if graph.number_of_nodes() > 1 else 0.0,
        "clustering": round(nx.average_clustering(graph), 4) if graph.number_of_nodes() > 1 else 0.0,
    }

    html = f"""<!doctype html>
<html lang="pl">
<head>
<meta charset="utf-8" />
<title>{title}</title>
<style>
  body {{ margin: 0; font-family: Inter, Arial, sans-serif; background: #0b1020; color: #e8eefc; }}
  .wrap {{ max-width: 1100px; margin: 0 auto; padding: 28px; }}
  .card {{ background: linear-gradient(135deg, #111a35, #17234a); border: 1px solid #2c3b71; border-radius: 18px; padding: 22px; box-shadow: 0 16px 48px rgba(0,0,0,.35); }}
  h1 {{ margin: 0 0 8px; }}
  .metrics {{ display: flex; gap: 12px; flex-wrap: wrap; margin: 14px 0 22px; }}
  .metric {{ background: #0e1630; border: 1px solid #30427d; padding: 10px 14px; border-radius: 12px; }}
  svg {{ width: 100%; height: auto; background: radial-gradient(circle at 50% 50%, #162554, #080c19 72%); border-radius: 16px; }}
  line {{ stroke: rgba(133, 184, 255, .42); stroke-width: 1.4; }}
  circle {{ fill: #6ee7ff; stroke: #ffffff; stroke-width: 1.1; filter: drop-shadow(0 0 7px rgba(110,231,255,.55)); }}
  text {{ fill: #07111f; text-anchor: middle; font-size: 10px; font-weight: 700; pointer-events: none; }}
  code {{ color: #9ef7c7; }}
</style>
</head>
<body>
<div class="wrap">
  <div class="card">
    <h1>{title}</h1>
    <p>Standalone SVG preview generated from a NetworkX graph.</p>
    <div class="metrics">
      {''.join(f'<div class="metric"><strong>{k}</strong><br><code>{v}</code></div>' for k, v in metrics.items())}
    </div>
    <svg viewBox="0 0 {width} {height}" role="img" aria-label="Graph visualization">
      <g>{''.join(edge_svg)}</g>
      <g>{''.join(node_svg)}</g>
    </svg>
  </div>
</div>
</body>
</html>
"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)


if __name__ == "__main__":
    print("=" * 72)
    print("QUANTUM HYBRID GRAPH — quantum-inspired evolutionary graph engine")
    print("=" * 72)

    print("\n▶ QPA model:")
    qpa = QuantumPreferentialAttachment(alpha=1.5, seed=42)
    for _ in range(20):
        qpa.add_node()
    print(f"  QPA graph: {qpa.graph.number_of_nodes()} nodes, {qpa.graph.number_of_edges()} edges")

    print("\n▶ Grover-style clique detector:")
    test_graph = nx.Graph()
    test_graph.add_edges_from(
        [
            (0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3),  # clique 0-1-2-3
            (3, 4), (4, 5), (4, 6), (5, 6),
        ]
    )
    detector = QuantumCliqueDetector(test_graph, seed=7)
    print(f"  Found 4-clique: {detector.grover_search_k_clique(4)}")
    print(f"  Speedup model for k=4: {detector.theoretical_speedup_for_k(4)}")

    print("\n▶ QAOA MaxClique simulation:")
    qaoa = QAOAOptimizer(test_graph, p_layers=2, seed=7)
    gamma, beta, bitstring = qaoa.optimize(iterations=50)
    clique = qaoa.extract_clique(bitstring)
    print(f"  Bitstring: {bitstring}")
    print(f"  QAOA-like found clique: {clique}")

    print("\n▶ Classical vs quantum-simulated benchmark:")
    results = compare_classical_vs_quantum(cycles=20, initial_nodes=10, seed=42)
    print(json.dumps(results, indent=2, ensure_ascii=False))

    kernel = QuantumHybridGraph(initial_nodes=10, seed=42)
    for _ in range(25):
        kernel.run_cycle()
    save_visualization_html(kernel.graph, "quantum_hybrid_graph.html")
    print("\n✅ Saved visualization: quantum_hybrid_graph.html")


def save_dashboard_html(kernel: QuantumHybridGraph, path: str = "quantum_hybrid_graph_dashboard.html", title: str = "QuantumHybridGraph Dashboard", nre: "AdaptiveNRE | None" = None) -> str:
    """Save a standalone interactive dashboard for a QuantumHybridGraph instance.

    The dashboard is dependency-free: all CSS, JavaScript and graph data are
    embedded in one HTML file. It works in the Arena preview sandbox and in a
    regular browser.
    """
    # Ensure the dashboard has fresh analysis/proposals without over-mutating the graph.
    if kernel.last_analysis_report is None:
        kernel.analyze_network(top_n=8, refresh_accelerators=True, record=False)
    if not kernel.last_connection_candidates:
        kernel.propose_connection_optimizations(add_edges=5, max_candidates=1500)

    graph = kernel.graph
    if graph.number_of_nodes() == 0:
        positions = {}
    else:
        positions = nx.spring_layout(graph, seed=11)

    degrees = dict(graph.degree())
    accelerator_node_ids = {node for acc in kernel.accelerator_details for node in acc.nodes}
    top_pagerank = []
    if kernel.last_analysis_report:
        top_pagerank = kernel.last_analysis_report.centrality.get("top_pagerank", [])
    top_nodes = {item["node"] for item in top_pagerank[:5]}

    nodes_payload = []
    for node in graph.nodes:
        x, y = positions.get(node, (0.0, 0.0))
        nodes_payload.append(
            {
                "id": node,
                "label": str(node),
                "x": float(x),
                "y": float(y),
                "degree": int(degrees.get(node, 0)),
                "accelerator": node in accelerator_node_ids,
                "top": node in top_nodes,
            }
        )

    edges_payload = [{"source": a, "target": b} for a, b in graph.edges]
    summary = kernel.summary()
    analysis = kernel.last_analysis_report.as_dict() if kernel.last_analysis_report else None
    payload = {
        "title": title,
        "summary": summary,
        "analysis": analysis,
        "nodes": nodes_payload,
        "edges": edges_payload,
        "accelerators": [acc.as_dict() for acc in kernel.accelerator_details[:10]],
        "connectionCandidates": [candidate.as_dict() for candidate in kernel.last_connection_candidates[:10]],
        "backendStatus": kernel.quantum_backend_status(),
        "security": None,
        "routing": None,
    }
    if nre is not None:
        security_payload = nre.security_dashboard_payload()
        # Attach the kernel's per-cycle monitoring history so the dashboard can
        # chart how the adaptive threshold and incident count evolve over time.
        security_payload["monitoring_history"] = list(getattr(kernel, "nre_incident_history", []))
        security_payload["monitoring_enabled"] = bool(getattr(kernel, "nre_monitoring_enabled", False))
        payload["security"] = security_payload

        # Routing / control-plane panel: expose the BGP/SDN command journal so
        # operators can audit what graph decisions were translated into routing
        # policy. ``as_dict()`` already carries the per-command BGP and SDN
        # renderings, so the front-end can toggle between protocols offline.
        routing = getattr(nre, "routing", None)
        if routing is not None:
            payload["routing"] = routing.as_dict()
    data_json = json.dumps(payload, ensure_ascii=False)

    html = f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{title}</title>
<style>
  :root {{
    --bg: #070d1d;
    --panel: #0d1833;
    --panel2: #101f43;
    --line: rgba(255,255,255,.12);
    --text: #eef6ff;
    --muted: #9fb3d9;
    --accent: #69e7ff;
    --green: #9effc7;
    --yellow: #ffd166;
    --red: #ff7b9c;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif;
    background: radial-gradient(circle at 12% 5%, rgba(105,231,255,.22), transparent 30%),
                radial-gradient(circle at 88% 12%, rgba(158,255,199,.14), transparent 28%),
                linear-gradient(145deg, #050914 0%, var(--bg) 60%, #0a1530 100%);
    color: var(--text);
  }}
  header {{ padding: 28px 34px 12px; border-bottom: 1px solid var(--line); }}
  h1 {{ margin: 0; font-size: clamp(32px, 5vw, 58px); letter-spacing: -.055em; }}
  .subtitle {{ color: var(--muted); margin-top: 8px; font-size: 17px; }}
  .wrap {{ padding: 22px 34px 38px; display: grid; grid-template-columns: 1.2fr .8fr; gap: 20px; }}
  .panel {{ background: linear-gradient(145deg, rgba(16,31,67,.94), rgba(9,18,39,.92)); border: 1px solid var(--line); border-radius: 22px; padding: 20px; box-shadow: 0 20px 70px rgba(0,0,0,.25); }}
  .metrics {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; margin-top: 18px; }}
  .metric {{ background: rgba(255,255,255,.045); border: 1px solid var(--line); border-radius: 16px; padding: 14px; }}
  .metric .value {{ color: var(--accent); font-weight: 900; font-size: 28px; letter-spacing: -.04em; }}
  .metric .label {{ color: var(--muted); font-size: 13px; margin-top: 4px; }}
  .tabs {{ display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 14px; }}
  button {{ background: rgba(105,231,255,.09); color: var(--text); border: 1px solid rgba(105,231,255,.28); border-radius: 999px; padding: 9px 13px; font-weight: 800; cursor: pointer; }}
  button.active {{ background: var(--accent); color: #06101e; }}
  .tab {{ display: none; }}
  .tab.active {{ display: block; }}
  #graphSvg {{ width: 100%; height: 620px; background: radial-gradient(circle at center, #162554, #080c19 72%); border-radius: 18px; border: 1px solid var(--line); }}
  #securityChart {{ width: 100%; height: 320px; background: radial-gradient(circle at center, #11203f, #080c19 78%); border-radius: 16px; border: 1px solid var(--line); }}
  text.axis {{ fill: var(--muted); font-size: 11px; }}
  text.axis-title {{ fill: var(--muted); font-size: 12px; font-weight: 700; }}
  line.grid {{ stroke: rgba(255,255,255,.08); stroke-width: 1; }}
  line.edge {{ stroke: rgba(133,184,255,.34); stroke-width: 1.4; }}
  circle.node {{ stroke: rgba(255,255,255,.85); stroke-width: 1.1; cursor: pointer; }}
  circle.accelerator {{ fill: var(--green); filter: drop-shadow(0 0 7px rgba(158,255,199,.55)); }}
  circle.top {{ fill: var(--yellow); filter: drop-shadow(0 0 7px rgba(255,209,102,.55)); }}
  circle.regular {{ fill: var(--accent); filter: drop-shadow(0 0 7px rgba(105,231,255,.48)); }}
  text.node-label {{ fill: #07111f; text-anchor: middle; font-size: 10px; font-weight: 900; pointer-events: none; }}
  .legend {{ display: flex; flex-wrap: wrap; gap: 10px; margin-top: 12px; color: var(--muted); font-size: 13px; }}
  .dot {{ display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 6px; }}
  .list {{ display: grid; gap: 10px; }}
  .item {{ border: 1px solid var(--line); background: rgba(255,255,255,.04); border-radius: 14px; padding: 12px; }}
  .item strong {{ color: var(--text); }}
  .item code {{ color: var(--green); }}
  .muted {{ color: var(--muted); }}
  .grid2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }}
  pre {{ white-space: pre-wrap; overflow: auto; max-height: 460px; background: rgba(0,0,0,.26); border: 1px solid var(--line); padding: 14px; border-radius: 14px; color: #dffaff; }}
  .tooltip {{ position: fixed; pointer-events: none; background: #050914; border: 1px solid var(--line); color: var(--text); padding: 9px 11px; border-radius: 12px; font-size: 13px; display: none; z-index: 5; box-shadow: 0 12px 40px rgba(0,0,0,.35); }}
  @media (max-width: 1100px) {{ .wrap {{ grid-template-columns: 1fr; }} .metrics {{ grid-template-columns: repeat(2, 1fr); }} #graphSvg {{ height: 520px; }} }}
  @media (max-width: 620px) {{ header, .wrap {{ padding-left: 18px; padding-right: 18px; }} .metrics, .grid2 {{ grid-template-columns: 1fr; }} }}
</style>
</head>
<body>
<header>
  <h1>{title}</h1>
  <div class="subtitle">Standalone dashboard for graph intelligence, accelerators, connection optimization, NRE security monitoring and quantum backend readiness.</div>
  <div class="metrics" id="metrics"></div>
</header>

<main class="wrap">
  <section class="panel">
    <div class="tabs">
      <button class="active" data-tab="graph">Graph</button>
      <button data-tab="analysis">Analysis</button>
      <button data-tab="accelerators">Accelerators</button>
      <button data-tab="connections">Connections</button>
      <button data-tab="security">Security</button>
      <button data-tab="routing">Routing</button>
      <button data-tab="quantum">Quantum</button>
      <button data-tab="json">JSON</button>
    </div>

    <div id="graph" class="tab active">
      <svg id="graphSvg" viewBox="0 0 1000 650" role="img" aria-label="QuantumHybridGraph network visualization"></svg>
      <div class="legend">
        <span><i class="dot" style="background:var(--accent)"></i>regular node</span>
        <span><i class="dot" style="background:var(--green)"></i>accelerator node</span>
        <span><i class="dot" style="background:var(--yellow)"></i>top PageRank node</span>
      </div>
    </div>

    <div id="analysis" class="tab"><div class="grid2" id="analysisGrid"></div></div>
    <div id="accelerators" class="tab"><div class="list" id="acceleratorList"></div></div>
    <div id="connections" class="tab"><div class="list" id="connectionList"></div></div>
    <div id="security" class="tab">
      <div class="metrics" id="securityMetrics"></div>
      <h3 style="margin:18px 0 8px">Per-cycle monitoring history</h3>
      <div id="securityChartWrap">
        <svg id="securityChart" viewBox="0 0 1000 320" role="img" aria-label="NRE per-cycle monitoring chart"></svg>
        <div class="legend">
          <span><i class="dot" style="background:var(--accent)"></i>adaptive threshold</span>
          <span><i class="dot" style="background:var(--red)"></i>incidents per cycle</span>
          <span><i class="dot" style="background:var(--yellow)"></i>quarantine events</span>
        </div>
      </div>
      <div class="grid2" id="securityGrid"></div>
      <h3 style="margin:18px 0 8px">Detected anomalies / incidents</h3>
      <div class="list" id="securityIncidents"></div>
      <h3 style="margin:18px 0 8px">Quarantine actions</h3>
      <div class="list" id="securityQuarantine"></div>
    </div>
    <div id="routing" class="tab">
      <div class="metrics" id="routingMetrics"></div>
      <div class="tabs" style="margin-top:16px">
        <button class="active proto-btn" data-proto="bgp">BGP view</button>
        <button class="proto-btn" data-proto="sdn">SDN / OpenFlow view</button>
      </div>
      <h3 style="margin:8px 0 8px">Control-plane command journal</h3>
      <div class="list" id="routingJournal"></div>
    </div>
    <div id="quantum" class="tab"><div class="grid2" id="quantumGrid"></div></div>
    <div id="json" class="tab"><pre id="jsonDump"></pre></div>
  </section>

  <aside class="panel">
    <h2 style="margin-top:0">Recommendations</h2>
    <div id="recommendations" class="list"></div>
    <h2>Selected node</h2>
    <div id="selectedNode" class="item muted">Click a node in the graph.</div>
  </aside>
</main>
<div class="tooltip" id="tooltip"></div>

<script id="dashboard-data" type="application/json">{data_json}</script>
<script>
const data = JSON.parse(document.getElementById('dashboard-data').textContent);
const $ = (id) => document.getElementById(id);
const fmt = (v) => typeof v === 'number' ? Number(v).toLocaleString(undefined, {{maximumFractionDigits: 4}}) : v;

function renderMetrics() {{
  const s = data.summary;
  const metrics = [
    ['Nodes', s.nodes], ['Edges', s.edges], ['Density', s.density], ['Clustering', s.clustering],
    ['Accelerators', s.num_accelerators], ['Backend', s.quantum_backend], ['Cycle', s.cycle], ['Speedup', s.quantum_speedup_estimate]
  ];
  $('metrics').innerHTML = metrics.map(([label, value]) => `<div class="metric"><div class="value">${{fmt(value)}}</div><div class="label">${{label}}</div></div>`).join('');
}}

function scalePositions(nodes) {{
  const xs = nodes.map(n => n.x), ys = nodes.map(n => n.y);
  const minX = Math.min(...xs, 0), maxX = Math.max(...xs, 1);
  const minY = Math.min(...ys, 0), maxY = Math.max(...ys, 1);
  return nodes.map(n => ({{
    ...n,
    sx: 70 + ((n.x - minX) / ((maxX - minX) || 1)) * 860,
    sy: 70 + ((n.y - minY) / ((maxY - minY) || 1)) * 510,
  }}));
}}

function renderGraph() {{
  const svg = $('graphSvg');
  const nodes = scalePositions(data.nodes);
  const byId = new Map(nodes.map(n => [String(n.id), n]));
  const maxDegree = Math.max(...nodes.map(n => n.degree), 1);
  const edges = data.edges.map(e => {{
    const a = byId.get(String(e.source)); const b = byId.get(String(e.target));
    if (!a || !b) return '';
    return `<line class="edge" x1="${{a.sx}}" y1="${{a.sy}}" x2="${{b.sx}}" y2="${{b.sy}}" />`;
  }}).join('');
  const nodeMarkup = nodes.map(n => {{
    const r = 6 + 17 * (n.degree / maxDegree);
    const cls = n.top ? 'top' : (n.accelerator ? 'accelerator' : 'regular');
    return `<g data-node="${{n.id}}"><circle class="node ${{cls}}" cx="${{n.sx}}" cy="${{n.sy}}" r="${{r}}"></circle><text class="node-label" x="${{n.sx}}" y="${{n.sy + 4}}">${{n.label}}</text></g>`;
  }}).join('');
  svg.innerHTML = `<g>${{edges}}</g><g>${{nodeMarkup}}</g>`;
  svg.querySelectorAll('g[data-node]').forEach(g => {{
    const node = byId.get(g.dataset.node);
    g.addEventListener('click', () => selectNode(node));
    g.addEventListener('mousemove', (ev) => showTooltip(ev, `node=${{node.label}}<br>degree=${{node.degree}}`));
    g.addEventListener('mouseleave', hideTooltip);
  }});
}}

function selectNode(node) {{
  const accs = data.accelerators.filter(a => a.nodes.map(String).includes(String(node.id))).map(a => `#${{a.id}} ${{a.kind}}`).join(', ') || 'none';
  $('selectedNode').innerHTML = `<strong>Node ${{node.label}}</strong><br>Degree: <code>${{node.degree}}</code><br>Accelerators: <code>${{accs}}</code><br>Top PageRank: <code>${{node.top ? 'yes' : 'no'}}</code>`;
}}

function showTooltip(ev, html) {{ const t = $('tooltip'); t.innerHTML = html; t.style.display='block'; t.style.left=(ev.clientX+12)+'px'; t.style.top=(ev.clientY+12)+'px'; }}
function hideTooltip() {{ $('tooltip').style.display='none'; }}

function renderAnalysis() {{
  const a = data.analysis || {{}};
  const cards = [
    ['Overview', a.overview], ['Connectivity', a.connectivity], ['Paths', a.paths],
    ['Degree distribution', a.degree_distribution], ['Communities', a.communities], ['Resilience', a.resilience],
    ['Top degree centrality', a.centrality?.top_degree], ['Top PageRank', a.centrality?.top_pagerank]
  ];
  $('analysisGrid').innerHTML = cards.map(([title, obj]) => `<div class="item"><strong>${{title}}</strong><pre>${{JSON.stringify(obj || {{}}, null, 2)}}</pre></div>`).join('');
  const recs = a.recommendations || [];
  $('recommendations').innerHTML = recs.length ? recs.map(r => `<div class="item">${{r}}</div>`).join('') : '<div class="item muted">No recommendations available.</div>';
}}

function renderAccelerators() {{
  $('acceleratorList').innerHTML = data.accelerators.length ? data.accelerators.map(a => `<div class="item"><strong>#${{a.id}} ${{a.kind}}</strong><br>Nodes: <code>${{a.nodes.join(', ')}}</code><br>Size: ${{a.size}} · Density: ${{a.density}} · Score: ${{a.score}}<br><span class="muted">Internal edges: ${{a.internal_edges}}, boundary edges: ${{a.boundary_edges}}, conductance: ${{a.conductance}}</span></div>`).join('') : '<div class="item muted">No accelerators detected.</div>';
}}

function renderConnections() {{
  $('connectionList').innerHTML = data.connectionCandidates.length ? data.connectionCandidates.map(c => `<div class="item"><strong>${{c.source}} → ${{c.target}}</strong><br>Score: <code>${{c.score}}</code> · Efficiency gain: ${{c.efficiency_gain}} · Path gain: ${{c.average_path_gain}}<br><span class="muted">${{c.reason}}</span></div>`).join('') : '<div class="item muted">No connection candidates available.</div>';
}}

function riskColor(score) {{
  if (score >= 0.75) return 'var(--red)';
  if (score >= 0.5) return 'var(--yellow)';
  return 'var(--green)';
}}

function renderSecurityChart(history) {{
  const svg = $('securityChart');
  if (!svg) return;
  const W = 1000, H = 320, padL = 56, padR = 56, padT = 26, padB = 42;
  if (!history || history.length === 0) {{
    svg.innerHTML = `<text class="axis-title" x="${{W/2}}" y="${{H/2}}" text-anchor="middle">No per-cycle monitoring history yet. Enable monitoring and run cycles.</text>`;
    return;
  }}
  const pts = history.map((s, i) => ({{
    cycle: s.cycle != null ? s.cycle : i + 1,
    threshold: Number(s.critical_energy_threshold) || 0,
    incidents: Number(s.num_incidents) || 0,
    quarantined: (s.quarantined_this_cycle || []).length,
  }}));
  const n = pts.length;
  const xAt = (i) => padL + (n === 1 ? (W - padL - padR) / 2 : (i / (n - 1)) * (W - padL - padR));
  const maxIncidents = Math.max(1, ...pts.map(p => p.incidents), ...pts.map(p => p.quarantined));
  // Left axis: threshold in [0,1]; Right axis: counts in [0,maxIncidents].
  const yThr = (v) => padT + (1 - Math.min(1, Math.max(0, v))) * (H - padT - padB);
  const yCnt = (v) => padT + (1 - (v / maxIncidents)) * (H - padT - padB);

  let g = '';
  // Horizontal grid + left axis labels (threshold 0..1).
  for (let t = 0; t <= 1.0001; t += 0.25) {{
    const y = yThr(t);
    g += `<line class="grid" x1="${{padL}}" y1="${{y}}" x2="${{W - padR}}" y2="${{y}}"></line>`;
    g += `<text class="axis" x="${{padL - 8}}" y="${{y + 4}}" text-anchor="end">${{t.toFixed(2)}}</text>`;
  }}
  // Right axis labels (counts).
  const cntTicks = Math.min(maxIncidents, 4);
  for (let k = 0; k <= cntTicks; k++) {{
    const val = Math.round((maxIncidents * k) / cntTicks);
    const y = yCnt(val);
    g += `<text class="axis" x="${{W - padR + 8}}" y="${{y + 4}}" text-anchor="start">${{val}}</text>`;
  }}
  // X axis cycle labels (sparse).
  const step = Math.max(1, Math.ceil(n / 8));
  pts.forEach((p, i) => {{
    if (i % step === 0 || i === n - 1) {{
      g += `<text class="axis" x="${{xAt(i)}}" y="${{H - padB + 18}}" text-anchor="middle">${{p.cycle}}</text>`;
    }}
  }});
  g += `<text class="axis-title" x="${{padL - 40}}" y="${{padT - 8}}" text-anchor="start">threshold</text>`;
  g += `<text class="axis-title" x="${{W - padR + 8}}" y="${{padT - 8}}" text-anchor="start">count</text>`;
  g += `<text class="axis-title" x="${{W/2}}" y="${{H - 6}}" text-anchor="middle">cycle</text>`;

  // Incident bars (right axis).
  const barW = Math.max(2, (W - padL - padR) / (n * 2.4));
  pts.forEach((p, i) => {{
    const x = xAt(i);
    const yTop = yCnt(p.incidents);
    g += `<rect x="${{x - barW/2}}" y="${{yTop}}" width="${{barW}}" height="${{Math.max(0, (H - padB) - yTop)}}" fill="rgba(255,123,156,.45)" rx="2"></rect>`;
    if (p.quarantined > 0) {{
      const qTop = yCnt(p.quarantined);
      g += `<rect x="${{x - barW/2}}" y="${{qTop}}" width="${{barW}}" height="${{Math.max(0,(H - padB) - qTop)}}" fill="rgba(255,209,102,.85)" rx="2"></rect>`;
    }}
  }});

  // Threshold line (left axis).
  const linePts = pts.map((p, i) => `${{xAt(i)}},${{yThr(p.threshold)}}`).join(' ');
  g += `<polyline points="${{linePts}}" fill="none" stroke="var(--accent)" stroke-width="2.5"></polyline>`;
  pts.forEach((p, i) => {{
    g += `<circle cx="${{xAt(i)}}" cy="${{yThr(p.threshold)}}" r="3.5" fill="var(--accent)"></circle>`;
  }});

  svg.innerHTML = g;
}}

function renderSecurity() {{
  const sec = data.security;
  if (!sec) {{
    $('securityMetrics').innerHTML = '';
    $('securityGrid').innerHTML = '<div class="item muted">No NRE agent attached. Pass an AdaptiveNRE instance to enable the Security panel.</div>';
    $('securityIncidents').innerHTML = '';
    $('securityQuarantine').innerHTML = '';
    renderSecurityChart([]);
    return;
  }}
  const metrics = [
    ['Threshold', sec.critical_energy_threshold],
    ['Incidents', sec.num_incidents],
    ['Quarantined', (sec.quarantine_zone || []).length],
    ['Sandbox nodes', sec.sandbox ? sec.sandbox.num_nodes : 0],
  ];
  $('securityMetrics').innerHTML = metrics.map(([label, value]) => `<div class="metric"><div class="value">${{fmt(value)}}</div><div class="label">${{label}}</div></div>`).join('');

  const cards = [
    ['Adaptation logic', sec.adaptation],
    ['Energy history', sec.energy_history],
    ['Sandbox', sec.sandbox],
    ['Health snapshot', sec.health],
  ];
  $('securityGrid').innerHTML = cards.map(([title, obj]) => `<div class="item"><strong>${{title}}</strong><pre>${{JSON.stringify(obj || {{}}, null, 2)}}</pre></div>`).join('');

  const incidents = sec.incidents || [];
  $('securityIncidents').innerHTML = incidents.length ? incidents.map(i => `<div class="item" style="border-left:4px solid ${{riskColor(i.risk_score)}}"><strong>Node ${{i.node}}</strong> · risk <code>${{i.risk_score}}</code> ${{i.quarantine_recommended ? '<span style="color:var(--red)">⚑ quarantine recommended</span>' : ''}}<br><span class="muted">${{(i.reasons || []).join(' · ')}}</span></div>`).join('') : '<div class="item muted">No anomalies detected.</div>';

  const q = sec.quarantine_history || [];
  $('securityQuarantine').innerHTML = q.length ? q.map(e => `<div class="item"><strong>${{e.status}}</strong> node <code>${{e.node}}</code>${{e.reason ? '<br><span class="muted">'+e.reason+'</span>' : ''}}${{e.edges_moved !== undefined ? '<br><span class="muted">edges moved: '+e.edges_moved+'</span>' : ''}}</div>`).join('') : '<div class="item muted">No quarantine actions recorded.</div>';

  renderSecurityChart(sec.monitoring_history || []);
}}

const ACTION_COLOR = {{
  blackhole: 'var(--red)',
  withdraw_route: 'var(--red)',
  announce_route: 'var(--green)',
  install_path: 'var(--accent)',
  set_local_pref: 'var(--yellow)',
}};

let routingProto = 'bgp';

function renderRoutingJournal() {{
  const rt = data.routing;
  if (!rt) {{ $('routingJournal').innerHTML = ''; return; }}
  const commands = rt.commands || [];
  const bgp = rt.bgp || [];
  const sdn = rt.sdn || [];
  if (!commands.length) {{
    $('routingJournal').innerHTML = '<div class="item muted">No routing-policy commands emitted yet. Quarantine/restore a node or run optimize_routes_via_qaoa to populate the control plane.</div>';
    return;
  }}
  $('routingJournal').innerHTML = commands.map((c, idx) => {{
    const color = ACTION_COLOR[c.action] || 'var(--muted)';
    const rendered = routingProto === 'bgp'
      ? `<pre>${{(bgp[idx] || '').replace(/</g, '&lt;')}}</pre>`
      : `<pre>${{JSON.stringify(sdn[idx] || {{}}, null, 2)}}</pre>`;
    return `<div class="item" style="border-left:4px solid ${{color}}"><strong>#${{idx + 1}} · ${{c.action}}</strong> → target <code>${{c.target}}</code><br><span class="muted">${{c.reason || ''}}</span>${{rendered}}</div>`;
  }}).join('');
}}

function renderRouting() {{
  const rt = data.routing;
  if (!rt) {{
    $('routingMetrics').innerHTML = '';
    $('routingJournal').innerHTML = '<div class="item muted">No NRE / BGP-SDN interface attached. Pass an AdaptiveNRE instance (its routing interface) to enable the Routing panel.</div>';
    return;
  }}
  const commands = rt.commands || [];
  const counts = {{}};
  commands.forEach(c => {{ counts[c.action] = (counts[c.action] || 0) + 1; }});
  const blackholes = (counts.blackhole || 0) + (counts.withdraw_route || 0);
  const metrics = [
    ['Protocol', (rt.protocol || 'bgp').toUpperCase()],
    ['Commands', rt.num_commands != null ? rt.num_commands : commands.length],
    ['Blackhole / withdraw', blackholes],
    ['Path installs', counts.install_path || 0],
  ];
  $('routingMetrics').innerHTML = metrics.map(([label, value]) => `<div class="metric"><div class="value">${{fmt(value)}}</div><div class="label">${{label}}</div></div>`).join('');
  renderRoutingJournal();
}}

function setupRoutingProto() {{
  document.querySelectorAll('.proto-btn').forEach(btn => btn.addEventListener('click', () => {{
    document.querySelectorAll('.proto-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    routingProto = btn.dataset.proto;
    renderRoutingJournal();
  }}));
}}

function renderQuantum() {{
  const statusCards = Object.values(data.backendStatus || {{}}).map(s => `<div class="item"><strong>${{s.name}}</strong><br>Available: <code>${{s.available}}</code><br>Version: <code>${{s.version || 'n/a'}}</code><br><span class="muted">${{s.reason || ''}}</span></div>`).join('');
  const exp = data.summary.last_quantum_experiments;
  $('quantumGrid').innerHTML = statusCards + `<div class="item"><strong>Last experiments</strong><pre>${{JSON.stringify(exp || 'not run', null, 2)}}</pre></div>`;
}}

function setupTabs() {{
  document.querySelectorAll('button[data-tab]').forEach(btn => btn.addEventListener('click', () => {{
    document.querySelectorAll('button[data-tab]').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    btn.classList.add('active');
    $(btn.dataset.tab).classList.add('active');
  }}));
}}

renderMetrics(); renderGraph(); renderAnalysis(); renderAccelerators(); renderConnections(); renderSecurity(); renderRouting(); renderQuantum();
$('jsonDump').textContent = JSON.stringify(data, null, 2);
setupTabs(); setupRoutingProto();
</script>
</body>
</html>
'''
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return path


@dataclass(frozen=True)
class RealWorldBenchmarkResult:
    """Benchmark result for one empirical/built-in real-world graph dataset."""

    dataset: str
    graph_metrics: dict[str, Any]
    baseline: dict[str, Any]
    quantum_hybrid_graph: dict[str, Any]
    improvement: dict[str, Any]
    runtime_sec: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "dataset": self.dataset,
            "graph_metrics": self.graph_metrics,
            "baseline": self.baseline,
            "quantum_hybrid_graph": self.quantum_hybrid_graph,
            "improvement": self.improvement,
            "runtime_sec": round(float(self.runtime_sec), 6),
        }


class RealWorldBenchmarkSuite:
    """Benchmarks QuantumHybridGraph on empirical datasets bundled with NetworkX.

    The suite avoids network downloads and uses well-known small real-world
    datasets included in NetworkX, such as Zachary's Karate Club, Florentine
    families and Les Miserables co-appearance network when available.
    """

    def __init__(self, seed: int | None = 42):
        self.seed = seed

    @staticmethod
    def available_datasets() -> dict[str, nx.Graph]:
        """Return real-world / empirical datasets available in the installed NetworkX."""
        candidates: list[tuple[str, str]] = [
            ("karate_club", "karate_club_graph"),
            ("florentine_families", "florentine_families_graph"),
            ("davis_southern_women", "davis_southern_women_graph"),
            ("les_miserables", "les_miserables_graph"),
        ]
        datasets: dict[str, nx.Graph] = {}
        for name, attr in candidates:
            loader = getattr(nx, attr, None)
            if loader is None:
                continue
            try:
                graph = loader()
                # Convert to a simple undirected graph for consistent metrics.
                graph = nx.Graph(graph)
                graph.remove_edges_from(nx.selfloop_edges(graph))
                datasets[name] = graph
            except Exception:
                continue
        return datasets

    @staticmethod
    def _safe_average_path(graph: nx.Graph) -> float | None:
        if graph.number_of_nodes() <= 1:
            return None
        if nx.is_connected(graph):
            return float(nx.average_shortest_path_length(graph))
        largest = graph.subgraph(max(nx.connected_components(graph), key=len)).copy()
        return float(nx.average_shortest_path_length(largest)) if largest.number_of_nodes() > 1 else None

    @staticmethod
    def _graph_metrics(graph: nx.Graph) -> dict[str, Any]:
        degrees = [degree for _, degree in graph.degree]
        return {
            "nodes": graph.number_of_nodes(),
            "edges": graph.number_of_edges(),
            "density": round(nx.density(graph), 6) if graph.number_of_nodes() > 1 else 0.0,
            "average_degree": round(float(np.mean(degrees)), 6) if degrees else 0.0,
            "max_degree": int(max(degrees)) if degrees else 0,
            "connected": nx.is_connected(graph) if graph.number_of_nodes() > 0 else False,
            "components": nx.number_connected_components(graph) if graph.number_of_nodes() > 0 else 0,
            "average_clustering": round(nx.average_clustering(graph), 6) if graph.number_of_nodes() > 1 else 0.0,
            "global_efficiency": round(nx.global_efficiency(graph), 6) if graph.number_of_nodes() > 1 else 0.0,
            "average_shortest_path_lcc": round(RealWorldBenchmarkSuite._safe_average_path(graph), 6)
            if RealWorldBenchmarkSuite._safe_average_path(graph) is not None
            else None,
        }

    @staticmethod
    def _baseline_networkx(graph: nx.Graph, top_n: int = 5) -> dict[str, Any]:
        t0 = time.perf_counter()
        degree = nx.degree_centrality(graph) if graph.number_of_nodes() else {}
        betweenness = nx.betweenness_centrality(graph, normalized=True) if graph.number_of_nodes() > 1 else {}
        pagerank = nx.pagerank(graph) if graph.number_of_edges() else {node: 0.0 for node in graph.nodes}
        try:
            communities = list(nx.algorithms.community.greedy_modularity_communities(graph)) if graph.number_of_edges() else []
            modularity = nx.algorithms.community.modularity(graph, communities) if communities else 0.0
        except Exception:
            communities = []
            modularity = 0.0
        return {
            "runtime_sec": round(time.perf_counter() - t0, 6),
            "top_degree": GraphNetworkAnalyzer._top_items(degree, top_n),
            "top_betweenness": GraphNetworkAnalyzer._top_items(betweenness, top_n),
            "top_pagerank": GraphNetworkAnalyzer._top_items(pagerank, top_n),
            "num_communities": len(communities),
            "community_sizes": sorted([len(c) for c in communities], reverse=True),
            "modularity": round(float(modularity), 6),
            "global_efficiency": round(nx.global_efficiency(graph), 6) if graph.number_of_nodes() > 1 else 0.0,
            "average_path_lcc": round(RealWorldBenchmarkSuite._safe_average_path(graph), 6)
            if RealWorldBenchmarkSuite._safe_average_path(graph) is not None
            else None,
        }

    @staticmethod
    def _path_gain(before: float | None, after: float | None) -> float | None:
        if before is None or after is None:
            return None
        return round(before - after, 6)

    def benchmark_graph(
        self,
        name: str,
        graph: nx.Graph,
        top_n: int = 5,
        add_edges: int = 3,
        max_candidates: int = 1500,
    ) -> RealWorldBenchmarkResult:
        """Benchmark one graph with baseline NetworkX metrics and QuantumHybridGraph."""
        t0 = time.perf_counter()
        graph = nx.Graph(graph)
        graph.remove_edges_from(nx.selfloop_edges(graph))
        graph_metrics = self._graph_metrics(graph)
        baseline = self._baseline_networkx(graph, top_n=top_n)

        kernel = QuantumHybridGraph(initial_nodes=0, clique_threshold=3, seed=self.seed)
        kernel.graph = graph.copy()

        analysis_start = time.perf_counter()
        report = kernel.analyze_network(top_n=top_n, refresh_accelerators=True, record=False)
        analysis_runtime = time.perf_counter() - analysis_start

        before_efficiency = nx.global_efficiency(kernel.graph) if kernel.graph.number_of_nodes() > 1 else 0.0
        before_path = self._safe_average_path(kernel.graph)
        proposals = kernel.propose_connection_optimizations(add_edges=add_edges, max_candidates=max_candidates)

        optimize_start = time.perf_counter()
        selected = kernel.optimize_connections(add_edges=add_edges, max_candidates=max_candidates, record=True)
        optimize_runtime = time.perf_counter() - optimize_start

        after_efficiency = nx.global_efficiency(kernel.graph) if kernel.graph.number_of_nodes() > 1 else 0.0
        after_path = self._safe_average_path(kernel.graph)

        qhg = {
            "analysis_runtime_sec": round(analysis_runtime, 6),
            "optimization_runtime_sec": round(optimize_runtime, 6),
            "num_accelerators": len(kernel.accelerator_details),
            "top_accelerators": [acc.as_dict() for acc in kernel.accelerator_details[:top_n]],
            "recommendations": report.recommendations,
            "proposed_edges": [candidate.as_dict() for candidate in proposals[:top_n]],
            "added_edges": [candidate.as_dict() for candidate in selected],
            "before_global_efficiency": round(before_efficiency, 6),
            "after_global_efficiency": round(after_efficiency, 6),
            "before_average_path_lcc": round(before_path, 6) if before_path is not None else None,
            "after_average_path_lcc": round(after_path, 6) if after_path is not None else None,
        }

        improvement = {
            "global_efficiency_gain": round(after_efficiency - before_efficiency, 6),
            "average_path_gain_lcc": self._path_gain(before_path, after_path),
            "edges_added": len(selected),
            "accelerators_detected": len(kernel.accelerator_details),
        }

        return RealWorldBenchmarkResult(
            dataset=name,
            graph_metrics=graph_metrics,
            baseline=baseline,
            quantum_hybrid_graph=qhg,
            improvement=improvement,
            runtime_sec=time.perf_counter() - t0,
        )

    def run(
        self,
        datasets: dict[str, nx.Graph] | None = None,
        top_n: int = 5,
        add_edges: int = 3,
        max_candidates: int = 1500,
    ) -> dict[str, Any]:
        """Run benchmarks and return a serializable report."""
        datasets = datasets or self.available_datasets()
        results = [
            self.benchmark_graph(name, graph, top_n=top_n, add_edges=add_edges, max_candidates=max_candidates)
            for name, graph in datasets.items()
        ]
        return {
            "suite": "real_world_networkx_benchmarks",
            "seed": self.seed,
            "num_datasets": len(results),
            "datasets": list(datasets.keys()),
            "results": [result.as_dict() for result in results],
        }

    def export_json(self, path: str = "real_world_benchmarks.json", **kwargs: Any) -> str:
        """Run benchmarks and export JSON."""
        report = self.run(**kwargs)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        return path

    def export_markdown(self, path: str = "real_world_benchmarks.md", **kwargs: Any) -> str:
        """Run benchmarks and export a human-readable Markdown report."""
        report = self.run(**kwargs)
        lines = [
            "# QuantumHybridGraph — Real-World Graph Benchmarks",
            "",
            f"Seed: `{report['seed']}`",
            f"Datasets: `{', '.join(report['datasets'])}`",
            "",
            "| Dataset | Nodes | Edges | Accelerators | Edges added | Efficiency gain | Path gain | Runtime (s) |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
        for item in report["results"]:
            gm = item["graph_metrics"]
            imp = item["improvement"]
            lines.append(
                f"| {item['dataset']} | {gm['nodes']} | {gm['edges']} | {imp['accelerators_detected']} | "
                f"{imp['edges_added']} | {imp['global_efficiency_gain']} | {imp['average_path_gain_lcc']} | {item['runtime_sec']} |"
            )
        lines.extend(["", "## Detailed results", ""])
        for item in report["results"]:
            lines.extend(
                [
                    f"### {item['dataset']}",
                    "",
                    "**Graph metrics**",
                    "",
                    "```json",
                    json.dumps(item["graph_metrics"], indent=2, ensure_ascii=False),
                    "```",
                    "",
                    "**QuantumHybridGraph improvement**",
                    "",
                    "```json",
                    json.dumps(item["improvement"], indent=2, ensure_ascii=False),
                    "```",
                    "",
                    "**Top recommendations**",
                    "",
                ]
            )
            recs = item["quantum_hybrid_graph"].get("recommendations", [])
            lines.extend([f"- {rec}" for rec in recs[:5]] or ["- No recommendations."])
            lines.append("")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        return path


@dataclass(frozen=True)
class AdaptiveOptimizationStep:
    """One step produced by the adaptive optimizer loop."""

    iteration: int
    action: str
    objective_before: float
    objective_after: float
    objective_delta: float
    accepted: bool
    added_edges: list[dict[str, Any]]
    metrics_before: dict[str, Any]
    metrics_after: dict[str, Any]
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "iteration": self.iteration,
            "action": self.action,
            "objective_before": round(float(self.objective_before), 6),
            "objective_after": round(float(self.objective_after), 6),
            "objective_delta": round(float(self.objective_delta), 6),
            "accepted": self.accepted,
            "added_edges": self.added_edges,
            "metrics_before": self.metrics_before,
            "metrics_after": self.metrics_after,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class AdaptiveOptimizationResult:
    """Full result of an adaptive graph optimization run."""

    steps: list[AdaptiveOptimizationStep]
    initial_objective: float
    final_objective: float
    best_objective: float
    accepted_steps: int
    rejected_steps: int
    total_edges_added: int
    stopped_reason: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "steps": [step.as_dict() for step in self.steps],
            "initial_objective": round(float(self.initial_objective), 6),
            "final_objective": round(float(self.final_objective), 6),
            "best_objective": round(float(self.best_objective), 6),
            "accepted_steps": self.accepted_steps,
            "rejected_steps": self.rejected_steps,
            "total_edges_added": self.total_edges_added,
            "stopped_reason": self.stopped_reason,
        }


class AdaptiveGraphOptimizer:
    """Adaptive optimizer loop for QuantumHybridGraph.

    The loop repeatedly analyzes the graph, detects accelerators, proposes
    shortcut edges, applies the best candidate, evaluates an objective function,
    and keeps or reverts the change depending on improvement.
    """

    def __init__(
        self,
        kernel: "QuantumHybridGraph",
        efficiency_weight: float = 1.0,
        path_weight: float = 0.12,
        clustering_weight: float = 0.15,
        density_penalty: float = 0.05,
    ):
        self.kernel = kernel
        self.efficiency_weight = float(efficiency_weight)
        self.path_weight = float(path_weight)
        self.clustering_weight = float(clustering_weight)
        self.density_penalty = float(density_penalty)

    @staticmethod
    def _safe_average_path(graph: nx.Graph) -> float | None:
        if graph.number_of_nodes() <= 1:
            return None
        if nx.is_connected(graph):
            return float(nx.average_shortest_path_length(graph))
        largest_nodes = max(nx.connected_components(graph), key=len)
        largest = graph.subgraph(largest_nodes)
        return float(nx.average_shortest_path_length(largest)) if largest.number_of_nodes() > 1 else None

    def metrics(self) -> dict[str, Any]:
        graph = self.kernel.graph
        n = graph.number_of_nodes()
        avg_path = self._safe_average_path(graph)
        return {
            "nodes": n,
            "edges": graph.number_of_edges(),
            "density": round(nx.density(graph), 6) if n > 1 else 0.0,
            "global_efficiency": round(nx.global_efficiency(graph), 6) if n > 1 else 0.0,
            "average_path_lcc": round(avg_path, 6) if avg_path is not None else None,
            "average_clustering": round(nx.average_clustering(graph), 6) if n > 1 else 0.0,
            "components": nx.number_connected_components(graph) if n > 0 else 0,
            "accelerators": len(self.kernel.accelerator_details),
        }

    def objective(self) -> float:
        m = self.metrics()
        avg_path = m["average_path_lcc"]
        path_score = 0.0 if avg_path is None else 1.0 / (1.0 + float(avg_path))
        component_penalty = 0.02 * max(0, int(m["components"]) - 1)
        return float(
            self.efficiency_weight * float(m["global_efficiency"])
            + self.path_weight * path_score
            + self.clustering_weight * float(m["average_clustering"])
            - self.density_penalty * float(m["density"])
            - component_penalty
        )

    def run(
        self,
        max_iterations: int = 10,
        add_edges_per_step: int = 1,
        max_candidates: int = 750,
        min_delta: float = 1e-5,
        patience: int = 3,
        accept_non_improving: bool = False,
        refresh_analysis: bool = True,
    ) -> AdaptiveOptimizationResult:
        """Run the adaptive optimization loop."""
        if max_iterations <= 0 or self.kernel.graph.number_of_nodes() < 2:
            current = self.objective()
            return AdaptiveOptimizationResult([], current, current, current, 0, 0, 0, "nothing_to_optimize")

        steps: list[AdaptiveOptimizationStep] = []
        initial_objective = self.objective()
        best_objective = initial_objective
        accepted_steps = 0
        rejected_steps = 0
        total_edges_added = 0
        no_improvement_steps = 0
        stopped_reason = "max_iterations_reached"

        for iteration in range(1, max_iterations + 1):
            if refresh_analysis:
                self.kernel.analyze_network(top_n=8, refresh_accelerators=True, record=False)
            else:
                self.kernel.detect_accelerators()

            metrics_before = self.metrics()
            objective_before = self.objective()
            candidates = self.kernel.propose_connection_optimizations(add_edges=add_edges_per_step, max_candidates=max_candidates)
            if not candidates:
                stopped_reason = "no_candidates"
                break

            chosen_candidates = candidates[:add_edges_per_step]
            selected_edges: list[tuple[Any, Any]] = []
            for candidate in chosen_candidates:
                if not self.kernel.graph.has_edge(candidate.source, candidate.target):
                    self.kernel.graph.add_edge(candidate.source, candidate.target)
                    selected_edges.append((candidate.source, candidate.target))

            metrics_after = self.metrics()
            objective_after = self.objective()
            delta = objective_after - objective_before
            accepted = accept_non_improving or delta >= min_delta

            reason = "accepted_improvement" if accepted and delta >= min_delta else "accepted_non_improving" if accepted else "rejected_no_improvement"
            if not accepted:
                self.kernel.graph.remove_edges_from(selected_edges)
                rejected_steps += 1
                no_improvement_steps += 1
                metrics_after = self.metrics()
                objective_after = self.objective()
            else:
                accepted_steps += 1
                total_edges_added += len(selected_edges)
                if objective_after > best_objective + min_delta:
                    best_objective = objective_after
                    no_improvement_steps = 0
                else:
                    no_improvement_steps += 1

            steps.append(
                AdaptiveOptimizationStep(
                    iteration=iteration,
                    action="add_edges",
                    objective_before=objective_before,
                    objective_after=objective_after,
                    objective_delta=objective_after - objective_before,
                    accepted=accepted,
                    added_edges=[candidate.as_dict() for candidate in chosen_candidates],
                    metrics_before=metrics_before,
                    metrics_after=metrics_after,
                    reason=reason,
                )
            )

            if no_improvement_steps >= patience:
                stopped_reason = "patience_exhausted"
                break
            max_edges = self.kernel.graph.number_of_nodes() * (self.kernel.graph.number_of_nodes() - 1) // 2
            if self.kernel.graph.number_of_edges() >= max_edges:
                stopped_reason = "complete_graph"
                break

        final_objective = self.objective()
        return AdaptiveOptimizationResult(
            steps=steps,
            initial_objective=initial_objective,
            final_objective=final_objective,
            best_objective=max(best_objective, final_objective),
            accepted_steps=accepted_steps,
            rejected_steps=rejected_steps,
            total_edges_added=total_edges_added,
            stopped_reason=stopped_reason,
        )


def _quantum_hybrid_graph_adaptive_optimize(
    self: QuantumHybridGraph,
    max_iterations: int = 10,
    add_edges_per_step: int = 1,
    max_candidates: int = 750,
    min_delta: float = 1e-5,
    patience: int = 3,
    accept_non_improving: bool = False,
) -> AdaptiveOptimizationResult:
    """Run the adaptive optimizer loop on this QuantumHybridGraph instance."""
    optimizer = AdaptiveGraphOptimizer(self)
    result = optimizer.run(
        max_iterations=max_iterations,
        add_edges_per_step=add_edges_per_step,
        max_candidates=max_candidates,
        min_delta=min_delta,
        patience=patience,
        accept_non_improving=accept_non_improving,
    )
    self.adaptive_optimization_result = result
    self.adaptive_optimization_history = getattr(self, "adaptive_optimization_history", [])
    self.adaptive_optimization_history.append(result.as_dict())
    return result


# Attach the adaptive optimizer to the main class without changing constructor compatibility.
QuantumHybridGraph.adaptive_optimize = _quantum_hybrid_graph_adaptive_optimize  # type: ignore[attr-defined]


@dataclass(frozen=True)
class CircuitDepthCandidate:
    """Evaluation record for one QAOA circuit depth p."""

    p_layers: int
    backend: str
    bitstring: str
    clique: list[Any]
    clique_size: int
    valid_clique: bool
    energy: float
    score: float
    runtime_sec: float
    gamma: list[float]
    beta: list[float]
    mode: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "p_layers": self.p_layers,
            "backend": self.backend,
            "bitstring": self.bitstring,
            "clique": self.clique,
            "clique_size": self.clique_size,
            "valid_clique": self.valid_clique,
            "energy": round(float(self.energy), 6),
            "score": round(float(self.score), 6),
            "runtime_sec": round(float(self.runtime_sec), 6),
            "gamma": [round(float(x), 6) for x in self.gamma],
            "beta": [round(float(x), 6) for x in self.beta],
            "mode": self.mode,
        }


@dataclass(frozen=True)
class CircuitDepthSelectionResult:
    """Result of adaptive QAOA circuit-depth selection."""

    selected_p: int
    best_candidate: CircuitDepthCandidate
    candidates: list[CircuitDepthCandidate]
    stopped_reason: str
    recommendation: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "selected_p": self.selected_p,
            "best_candidate": self.best_candidate.as_dict(),
            "candidates": [candidate.as_dict() for candidate in self.candidates],
            "stopped_reason": self.stopped_reason,
            "recommendation": self.recommendation,
        }


class CircuitDepthSelector:
    """Adaptive selector for QAOA circuit depth p.

    The selector sweeps p from `min_p` to `max_p`, evaluates each depth, scores
    the quality/cost trade-off and stops early when additional depth no longer
    improves the result. It works with the local simulator and with the optional
    Qiskit/PennyLane backend adapters.
    """

    def __init__(
        self,
        graph: nx.Graph,
        backend: str = "local",
        seed: int | None = None,
        complexity_penalty: float = 0.05,
        runtime_penalty: float = 0.02,
    ):
        self.graph = graph.copy()
        self.backend = backend
        self.seed = seed
        self.complexity_penalty = float(complexity_penalty)
        self.runtime_penalty = float(runtime_penalty)
        self.registry = QuantumBackendRegistry()

    @staticmethod
    def _valid_clique(graph: nx.Graph, clique: list[Any]) -> bool:
        return all(graph.has_edge(a, b) for a, b in combinations(clique, 2))

    def _score(self, clique_size: int, energy: float, p_layers: int, runtime_sec: float, valid: bool) -> float:
        validity_bonus = 1.0 if valid else -2.0
        # Lower energy is better, but clique size is the primary business metric.
        return float((2.0 * clique_size) - (0.25 * energy) + validity_bonus - (self.complexity_penalty * p_layers) - (self.runtime_penalty * runtime_sec))

    def evaluate_depth(self, p_layers: int, iterations: int = 40) -> CircuitDepthCandidate:
        """Evaluate one QAOA depth p."""
        start = time.perf_counter()
        if self.backend in {"local", "local_simulator"}:
            optimizer = QAOAOptimizer(self.graph, p_layers=p_layers, seed=self.seed)
            gamma, beta, bitstring = optimizer.optimize(iterations=iterations)
            clique = optimizer.extract_clique(bitstring)
            energy = float(optimizer.cost_energy(bitstring))
            mode = "local_qaoa_like"
            backend_name = "local_simulator"
        else:
            adapter = self.registry.get(self.backend)
            result = adapter.solve_max_clique_qaoa(self.graph, p_layers=p_layers, iterations=iterations, seed=self.seed)
            bitstring = result.get("bitstring", "")
            clique = list(result.get("clique", []))
            energy = float(result.get("energy", 0.0))
            gamma = np.array(result.get("gamma", []), dtype=float)
            beta = np.array(result.get("beta", []), dtype=float)
            mode = str(result.get("mode", "unknown"))
            backend_name = str(result.get("backend", self.backend))

        runtime_sec = time.perf_counter() - start
        valid = self._valid_clique(self.graph, clique)
        score = self._score(len(clique), energy, p_layers, runtime_sec, valid)
        return CircuitDepthCandidate(
            p_layers=int(p_layers),
            backend=backend_name,
            bitstring=bitstring,
            clique=clique,
            clique_size=len(clique),
            valid_clique=valid,
            energy=energy,
            score=score,
            runtime_sec=runtime_sec,
            gamma=[float(x) for x in gamma],
            beta=[float(x) for x in beta],
            mode=mode,
        )

    def select(
        self,
        min_p: int = 1,
        max_p: int = 5,
        iterations: int = 40,
        min_score_delta: float = 0.05,
        patience: int = 2,
    ) -> CircuitDepthSelectionResult:
        """Select the best QAOA depth p with early stopping."""
        min_p = max(1, int(min_p))
        max_p = max(min_p, int(max_p))
        candidates: list[CircuitDepthCandidate] = []
        best: CircuitDepthCandidate | None = None
        no_improvement = 0
        stopped_reason = "max_p_reached"

        for p_layers in range(min_p, max_p + 1):
            candidate = self.evaluate_depth(p_layers=p_layers, iterations=iterations)
            candidates.append(candidate)
            if best is None or candidate.score > best.score + min_score_delta:
                best = candidate
                no_improvement = 0
            else:
                no_improvement += 1
            if no_improvement >= patience:
                stopped_reason = "patience_exhausted"
                break

        if best is None:
            raise RuntimeError("Circuit depth selection produced no candidates.")

        recommendation = (
            f"Use p={best.p_layers}: best score={best.score:.3f}, clique_size={best.clique_size}, "
            f"energy={best.energy:.3f}, backend={best.backend}, mode={best.mode}."
        )
        return CircuitDepthSelectionResult(
            selected_p=best.p_layers,
            best_candidate=best,
            candidates=candidates,
            stopped_reason=stopped_reason,
            recommendation=recommendation,
        )


def _quantum_hybrid_graph_select_circuit_depth(
    self: QuantumHybridGraph,
    min_p: int = 1,
    max_p: int = 5,
    iterations: int = 40,
    backend: str = "local",
    min_score_delta: float = 0.05,
    patience: int = 2,
) -> CircuitDepthSelectionResult:
    """Select QAOA circuit depth p for the current graph and update qaoa_layers."""
    selector = CircuitDepthSelector(self.graph, backend=backend, seed=self.seed)
    result = selector.select(
        min_p=min_p,
        max_p=max_p,
        iterations=iterations,
        min_score_delta=min_score_delta,
        patience=patience,
    )
    self.qaoa_layers = result.selected_p
    self.circuit_depth_selection_result = result
    self.circuit_depth_selection_history = getattr(self, "circuit_depth_selection_history", [])
    self.circuit_depth_selection_history.append(result.as_dict())
    return result


QuantumHybridGraph.select_circuit_depth = _quantum_hybrid_graph_select_circuit_depth  # type: ignore[attr-defined]


@dataclass(frozen=True)
class ReliabilityIncident:
    """Security/reliability incident detected in the graph."""

    node: Any
    risk_score: float
    reasons: list[str]
    degree: int
    quarantine_recommended: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "node": self.node,
            "risk_score": round(float(self.risk_score), 6),
            "reasons": self.reasons,
            "degree": self.degree,
            "quarantine_recommended": self.quarantine_recommended,
        }


# ======================================================================
# BGP / SDN integration interface
# ======================================================================


@dataclass(frozen=True)
class RoutingPolicyCommand:
    """A single routing-policy update derived from a graph operation.

    The command is protocol-neutral but carries enough detail to be rendered as
    a concrete BGP policy statement, an OpenFlow/SDN flow-mod or a vendor CLI
    line. ``action`` is one of:

      - ``blackhole``     : drop all traffic to/from a node (quarantine).
      - ``withdraw_route``: stop advertising a node/prefix (isolate).
      - ``announce_route``: re-advertise a node/prefix (restore).
      - ``install_path``  : program an optimized shortcut path (clique/route).
      - ``set_local_pref``: re-weight a link to steer traffic.
    """

    action: str
    target: Any
    protocol: str
    reason: str
    attributes: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "target": self.target,
            "protocol": self.protocol,
            "reason": self.reason,
            "attributes": dict(self.attributes),
        }

    def to_bgp(self) -> str:
        """Render the command as a BGP-style policy statement."""
        node = self._node_to_prefix(self.target)
        if self.action == "blackhole":
            return f"route {node} next-hop 192.0.2.1 community 65535:666  # blackhole ({self.reason})"
        if self.action == "withdraw_route":
            return f"withdraw {node}  # {self.reason}"
        if self.action == "announce_route":
            local_pref = self.attributes.get("local_pref", 100)
            return f"announce {node} local-preference {local_pref}  # {self.reason}"
        if self.action == "install_path":
            path = self.attributes.get("path", [])
            hops = " ".join(self._node_to_prefix(p) for p in path)
            return f"install path [{hops}]  # {self.reason}"
        if self.action == "set_local_pref":
            local_pref = self.attributes.get("local_pref", 100)
            return f"set {node} local-preference {local_pref}  # {self.reason}"
        return f"# unknown action {self.action} for {node}"

    def to_sdn(self) -> dict[str, Any]:
        """Render the command as an SDN/OpenFlow-style flow rule intent."""
        if self.action in ("blackhole", "withdraw_route"):
            flow = {"match": {"node": self.target}, "action": "DROP", "priority": 60000}
        elif self.action == "announce_route":
            flow = {"match": {"node": self.target}, "action": "FORWARD", "priority": 100}
        elif self.action == "install_path":
            flow = {
                "match": {"path": list(self.attributes.get("path", []))},
                "action": "FORWARD",
                "priority": int(self.attributes.get("priority", 200)),
            }
        elif self.action == "set_local_pref":
            flow = {
                "match": {"node": self.target},
                "action": "SET_WEIGHT",
                "weight": self.attributes.get("local_pref", 100),
                "priority": 150,
            }
        else:
            flow = {"match": {"node": self.target}, "action": "NOOP", "priority": 0}
        flow["reason"] = self.reason
        flow["protocol"] = "sdn"
        return flow

    @staticmethod
    def _node_to_prefix(node: Any) -> str:
        """Map a graph node id to a deterministic synthetic /32 prefix."""
        if isinstance(node, int) and 0 <= node < 2**32:
            octets = [(node >> shift) & 0xFF for shift in (24, 16, 8, 0)]
            return ".".join(str(o) for o in octets) + "/32"
        return f"node:{node}"


class BGPSDNInterface:
    """Map QuantumHybridGraph operations to routing-policy update commands.

    This is the integration layer between the graph intelligence kernel / NRE
    and the network control plane. Graph-level decisions (quarantine a node,
    isolate/restore a prefix, install an optimized shortcut path, re-weight a
    link) are translated into protocol-neutral ``RoutingPolicyCommand`` objects
    that can be emitted as BGP policy statements or SDN flow rules.

    The interface keeps a command journal so emitted policy can be audited or
    replayed by a downstream BGP speaker / SDN controller.
    """

    def __init__(self, kernel: "QuantumHybridGraph", protocol: str = "bgp"):
        self.kernel = kernel
        self.protocol = protocol
        self.command_journal: list[RoutingPolicyCommand] = []

    def _record(self, command: RoutingPolicyCommand) -> RoutingPolicyCommand:
        self.command_journal.append(command)
        return command

    def quarantine_to_policy(self, node: Any, reason: str = "quarantine") -> RoutingPolicyCommand:
        """Translate a node quarantine into a blackhole/withdraw policy."""
        return self._record(
            RoutingPolicyCommand(
                action="blackhole",
                target=node,
                protocol=self.protocol,
                reason=reason,
                attributes={"withdraw": True},
            )
        )

    def restore_to_policy(self, node: Any, reason: str = "restore") -> RoutingPolicyCommand:
        """Translate a node restore into a re-announce policy."""
        return self._record(
            RoutingPolicyCommand(
                action="announce_route",
                target=node,
                protocol=self.protocol,
                reason=reason,
                attributes={"local_pref": 100},
            )
        )

    def path_to_policy(
        self,
        path: list[Any],
        reason: str = "optimized_path",
        priority: int = 200,
    ) -> RoutingPolicyCommand:
        """Translate an optimized graph path/clique into an install-path policy."""
        target = path[0] if path else None
        return self._record(
            RoutingPolicyCommand(
                action="install_path",
                target=target,
                protocol=self.protocol,
                reason=reason,
                attributes={"path": list(path), "priority": int(priority)},
            )
        )

    def reweight_to_policy(
        self,
        node: Any,
        local_pref: int,
        reason: str = "reweight",
    ) -> RoutingPolicyCommand:
        """Translate a link/node re-weighting into a local-preference policy."""
        return self._record(
            RoutingPolicyCommand(
                action="set_local_pref",
                target=node,
                protocol=self.protocol,
                reason=reason,
                attributes={"local_pref": int(local_pref)},
            )
        )

    def commands_from_incidents(
        self,
        incidents: list[ReliabilityIncident],
        only_recommended: bool = True,
    ) -> list[RoutingPolicyCommand]:
        """Build blackhole policies for risky/quarantine-recommended nodes."""
        commands: list[RoutingPolicyCommand] = []
        for incident in incidents:
            if only_recommended and not incident.quarantine_recommended:
                continue
            commands.append(
                self.quarantine_to_policy(
                    incident.node,
                    reason="; ".join(incident.reasons) or "risk_threshold",
                )
            )
        return commands

    def export_policy(
        self,
        path: str = "routing_policy.txt",
        fmt: str = "bgp",
    ) -> str:
        """Export the journaled commands as BGP text or SDN JSON."""
        if fmt == "sdn":
            payload = [command.to_sdn() for command in self.command_journal]
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
        else:
            lines = [command.to_bgp() for command in self.command_journal]
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines) + ("\n" if lines else ""))
        return path

    def as_dict(self) -> dict[str, Any]:
        return {
            "protocol": self.protocol,
            "num_commands": len(self.command_journal),
            "commands": [command.as_dict() for command in self.command_journal],
            "bgp": [command.to_bgp() for command in self.command_journal],
            "sdn": [command.to_sdn() for command in self.command_journal],
        }


class NetworkReliabilityEngineer:
    """Base reliability/security operator for QuantumHybridGraph.

    The NRE monitors graph health, identifies suspicious or structurally risky
    nodes and can be extended with quarantine or self-healing actions.
    """

    def __init__(self, kernel: QuantumHybridGraph):
        self.kernel = kernel
        self.incident_history: list[dict[str, Any]] = []

    def health_snapshot(self) -> dict[str, Any]:
        graph = self.kernel.graph
        n = graph.number_of_nodes()
        if n == 0:
            return {
                "nodes": 0,
                "edges": 0,
                "density": 0.0,
                "connected": False,
                "components": 0,
                "isolates": [],
                "articulation_points": [],
                "bridges": [],
            }
        articulation_points = list(nx.articulation_points(graph)) if n > 1 else []
        bridges = list(nx.bridges(graph)) if graph.number_of_edges() else []
        return {
            "nodes": n,
            "edges": graph.number_of_edges(),
            "density": round(nx.density(graph), 6) if n > 1 else 0.0,
            "connected": nx.is_connected(graph),
            "components": nx.number_connected_components(graph),
            "isolates": list(nx.isolates(graph)),
            "articulation_points": articulation_points,
            "bridges": bridges,
        }

    def detect_risky_nodes(
        self,
        degree_z_threshold: float = 2.0,
        betweenness_threshold: float = 0.35,
        quarantine_threshold: float = 0.75,
    ) -> list[ReliabilityIncident]:
        """Detect structurally risky nodes using graph reliability signals."""
        graph = self.kernel.graph
        if graph.number_of_nodes() == 0:
            return []

        degrees = dict(graph.degree())
        degree_values = np.array(list(degrees.values()), dtype=float)
        mean = float(degree_values.mean()) if len(degree_values) else 0.0
        std = float(degree_values.std()) if len(degree_values) else 0.0
        betweenness = nx.betweenness_centrality(graph, normalized=True) if graph.number_of_nodes() > 1 else {node: 0.0 for node in graph.nodes}
        articulation_points = set(nx.articulation_points(graph)) if graph.number_of_nodes() > 1 else set()
        isolates = set(nx.isolates(graph))

        incidents: list[ReliabilityIncident] = []
        for node in graph.nodes:
            reasons: list[str] = []
            risk = 0.0
            degree = degrees[node]
            z = 0.0 if std == 0 else (degree - mean) / std
            if z >= degree_z_threshold:
                risk += 0.35
                reasons.append(f"degree_z_score={z:.2f}")
            if betweenness.get(node, 0.0) >= betweenness_threshold:
                risk += 0.35
                reasons.append(f"high_betweenness={betweenness[node]:.3f}")
            if node in articulation_points:
                risk += 0.25
                reasons.append("articulation_point")
            if node in isolates:
                risk += 0.15
                reasons.append("isolate")

            if reasons:
                incidents.append(
                    ReliabilityIncident(
                        node=node,
                        risk_score=min(1.0, risk),
                        reasons=reasons,
                        degree=degree,
                        quarantine_recommended=risk >= quarantine_threshold,
                    )
                )

        incidents.sort(key=lambda item: item.risk_score, reverse=True)
        return incidents

    def reliability_report(self) -> dict[str, Any]:
        incidents = self.detect_risky_nodes()
        report = {
            "health": self.health_snapshot(),
            "incidents": [incident.as_dict() for incident in incidents],
            "num_incidents": len(incidents),
        }
        self.incident_history.append(report)
        return report


class AdaptiveNRE(NetworkReliabilityEngineer):
    """Adaptive Network Reliability Engineer with quarantine sandbox.

    Suspicious nodes can be moved from the main graph into a separate sandbox
    graph. The sandbox preserves the node's local incident context so attack or
    failure patterns can be analyzed without contaminating the main graph.
    """

    def __init__(
        self,
        kernel: QuantumHybridGraph,
        critical_energy_threshold: float = 0.75,
        adaptation_rate: float = 0.25,
        min_threshold: float = 0.4,
        max_threshold: float = 0.95,
        history_window: int = 20,
        routing_protocol: str = "bgp",
    ):
        super().__init__(kernel)
        # BGP/SDN control-plane interface: quarantine and restore operations are
        # mapped to routing-policy update commands so the security decisions can
        # be pushed to a BGP speaker or SDN controller.
        self.routing = BGPSDNInterface(kernel, protocol=routing_protocol)
        self.quarantine_zone: set[Any] = set()
        self.sandbox = nx.Graph()
        self.quarantine_history: list[dict[str, Any]] = []
        # Recovery Procedures: audit trail of restore/recovery actions taken by
        # the agent when returning quarantined nodes to the production graph.
        self.recovery_history: list[dict[str, Any]] = []

        # --- Adaptation Logic state ---------------------------------------
        # ``critical_energy_threshold`` is the normalized node-energy level above
        # which a node is treated as anomalous (DoS/flood candidate). It is
        # adapted online from historical network energy data so that the agent
        # stays sensitive in quiet networks and tolerant in naturally busy ones.
        self.critical_energy_threshold = float(critical_energy_threshold)
        self.adaptation_rate = float(adaptation_rate)
        self.min_threshold = float(min_threshold)
        self.max_threshold = float(max_threshold)
        self.history_window = int(max(1, history_window))
        self.energy_history: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Adaptation Logic
    # ------------------------------------------------------------------

    def node_energy(self) -> dict[Any, float]:
        """Return a normalized per-node 'energy' (load) signal.

        Energy is the node degree normalized by the maximum degree in the
        graph. A flooded/DoS node tends to accumulate a disproportionate number
        of connections, pushing its normalized energy toward 1.0.
        """
        graph = self.kernel.graph
        if graph.number_of_nodes() == 0:
            return {}
        degrees = dict(graph.degree())
        max_degree = max(degrees.values()) if degrees else 0
        if max_degree == 0:
            return {node: 0.0 for node in degrees}
        return {node: degree / max_degree for node, degree in degrees.items()}

    def observe_energy(self) -> dict[str, Any]:
        """Record a snapshot of network energy for the adaptation history."""
        energies = self.node_energy()
        values = np.array(list(energies.values()), dtype=float) if energies else np.array([])
        snapshot = {
            "cycle": getattr(self.kernel, "cycle", 0),
            "mean_energy": float(values.mean()) if values.size else 0.0,
            "std_energy": float(values.std()) if values.size else 0.0,
            "max_energy": float(values.max()) if values.size else 0.0,
            "p90_energy": float(np.percentile(values, 90)) if values.size else 0.0,
        }
        self.energy_history.append(snapshot)
        if len(self.energy_history) > self.history_window:
            self.energy_history = self.energy_history[-self.history_window :]
        return snapshot

    def adapt_threshold(self) -> dict[str, Any]:
        """Dynamically adjust ``critical_energy_threshold`` from history.

        The target threshold tracks the typical upper band of historical node
        energy (mean of recent p90 energy plus a margin). The threshold then
        moves toward that target by ``adaptation_rate`` and is clamped to the
        configured bounds. This keeps quarantine decisions calibrated to how
        loaded the network normally is.
        """
        self.observe_energy()
        if not self.energy_history:
            return {
                "previous_threshold": self.critical_energy_threshold,
                "new_threshold": self.critical_energy_threshold,
                "target": self.critical_energy_threshold,
                "samples": 0,
            }

        recent_p90 = np.array([snap["p90_energy"] for snap in self.energy_history], dtype=float)
        recent_std = np.array([snap["std_energy"] for snap in self.energy_history], dtype=float)
        # Anomalies live above the normal high-energy band; add a margin from
        # variability so noisy networks do not over-quarantine.
        target = float(recent_p90.mean() + 1.5 * recent_std.mean())
        target = min(self.max_threshold, max(self.min_threshold, target))

        previous = self.critical_energy_threshold
        updated = previous + self.adaptation_rate * (target - previous)
        self.critical_energy_threshold = float(min(self.max_threshold, max(self.min_threshold, updated)))
        return {
            "previous_threshold": round(previous, 6),
            "new_threshold": round(self.critical_energy_threshold, 6),
            "target": round(target, 6),
            "samples": len(self.energy_history),
        }

    def detect_energy_anomalies(self, adapt: bool = True) -> list[ReliabilityIncident]:
        """Detect DoS/flood-style anomalies using node energy and adaptation.

        Combines structural reliability signals (``detect_risky_nodes``) with an
        energy-based anomaly signal calibrated by the adaptive
        ``critical_energy_threshold``.
        """
        if adapt:
            self.adapt_threshold()
        energies = self.node_energy()
        structural = {incident.node: incident for incident in self.detect_risky_nodes()}

        incidents: list[ReliabilityIncident] = []
        for node, energy in energies.items():
            reasons: list[str] = []
            risk = 0.0
            if energy >= self.critical_energy_threshold:
                # Excess over the adaptive threshold scales the DoS/flood risk.
                excess = (energy - self.critical_energy_threshold) / max(1e-9, 1.0 - self.critical_energy_threshold)
                risk += 0.5 + 0.4 * min(1.0, excess)
                reasons.append(f"energy_anomaly={energy:.3f}>=threshold={self.critical_energy_threshold:.3f}")
                reasons.append("dos_flood_suspect")

            base = structural.get(node)
            if base is not None:
                risk = max(risk, base.risk_score)
                reasons.extend(base.reasons)

            if reasons:
                incidents.append(
                    ReliabilityIncident(
                        node=node,
                        risk_score=min(1.0, risk),
                        reasons=reasons,
                        degree=self.kernel.graph.degree(node),
                        quarantine_recommended=risk >= self.critical_energy_threshold,
                    )
                )

        incidents.sort(key=lambda item: item.risk_score, reverse=True)
        return incidents

    def quarantine_node(self, node_id: Any, reason: str = "manual") -> dict[str, Any]:
        """Move a node from the main graph to the sandbox."""
        if node_id not in self.kernel.graph:
            return {
                "status": "not_found",
                "node": node_id,
                "reason": reason,
                "message": "Node is not present in the main graph.",
            }

        print(f"[NRE SECURITY] Moving node {node_id} to Sandbox.")
        node_attrs = dict(self.kernel.graph.nodes[node_id])
        incident_edges = list(self.kernel.graph.edges(node_id, data=True))
        neighbors = [target if source == node_id else source for source, target, _ in incident_edges]

        self.sandbox.add_node(node_id, **node_attrs, quarantined=True, quarantine_reason=reason)
        for source, target, attrs in incident_edges:
            # Preserve edge context in the sandbox, including neighbor nodes as context-only nodes.
            if source not in self.sandbox:
                self.sandbox.add_node(source, context_only=(source != node_id))
            if target not in self.sandbox:
                self.sandbox.add_node(target, context_only=(target != node_id))
            self.sandbox.add_edge(source, target, **attrs)

        self.kernel.graph.remove_node(node_id)
        self.quarantine_zone.add(node_id)
        # BGP/SDN: emit a blackhole/withdraw routing policy for the isolated node.
        routing_command = self.routing.quarantine_to_policy(node_id, reason=reason)
        event = {
            "status": "quarantined",
            "node": node_id,
            "reason": reason,
            "neighbors": neighbors,
            "edges_moved": len(incident_edges),
            "sandbox_nodes": self.sandbox.number_of_nodes(),
            "sandbox_edges": self.sandbox.number_of_edges(),
            "routing_policy": routing_command.as_dict(),
            "bgp": routing_command.to_bgp(),
        }
        self.quarantine_history.append(event)
        return event

    def auto_quarantine(
        self,
        threshold: float | None = None,
        limit: int | None = None,
        use_energy_anomalies: bool = True,
        adapt: bool = True,
    ) -> list[dict[str, Any]]:
        """Automatically quarantine nodes whose reliability risk exceeds threshold.

        When ``threshold`` is ``None`` the adaptive ``critical_energy_threshold``
        is used. With ``use_energy_anomalies`` the agent also reacts to DoS/flood
        energy anomalies, not only structural risk.
        """
        if use_energy_anomalies:
            incidents = self.detect_energy_anomalies(adapt=adapt)
            cutoff = self.critical_energy_threshold if threshold is None else float(threshold)
        else:
            cutoff = self.critical_energy_threshold if threshold is None else float(threshold)
            incidents = self.detect_risky_nodes(quarantine_threshold=cutoff)

        incidents = [incident for incident in incidents if incident.risk_score >= cutoff]
        if limit is not None:
            incidents = incidents[: max(0, int(limit))]
        events = []
        for incident in incidents:
            if incident.node in self.kernel.graph:
                events.append(self.quarantine_node(incident.node, reason=";".join(incident.reasons)))
        return events

    def analyze_sandbox(self) -> dict[str, Any]:
        """Analyze trapped nodes to learn attack/failure patterns."""
        if self.sandbox.number_of_nodes() == 0:
            return {
                "sandbox_nodes": 0,
                "sandbox_edges": 0,
                "quarantined_nodes": [],
                "patterns": [],
            }

        print(f"[NRE ANALYSIS] Analyzing {self.sandbox.number_of_nodes()} nodes in sandbox.")
        degrees = dict(self.sandbox.degree())
        quarantined_nodes = [node for node, attrs in self.sandbox.nodes(data=True) if attrs.get("quarantined")]
        context_nodes = [node for node, attrs in self.sandbox.nodes(data=True) if attrs.get("context_only")]
        patterns: list[str] = []
        if quarantined_nodes:
            avg_degree = sum(degrees[node] for node in quarantined_nodes) / len(quarantined_nodes)
            patterns.append(f"average_quarantined_degree={avg_degree:.3f}")
        if context_nodes:
            patterns.append(f"context_neighbors_preserved={len(context_nodes)}")
        if self.sandbox.number_of_edges() > self.sandbox.number_of_nodes():
            patterns.append("dense_sandbox_interaction_pattern")

        return {
            "sandbox_nodes": self.sandbox.number_of_nodes(),
            "sandbox_edges": self.sandbox.number_of_edges(),
            "quarantined_nodes": quarantined_nodes,
            "context_nodes": context_nodes,
            "patterns": patterns,
            "quarantine_history": self.quarantine_history[-10:],
            "critical_energy_threshold": round(self.critical_energy_threshold, 6),
            "energy_history": self.energy_history[-10:],
        }

    def reliability_report(self) -> dict[str, Any]:
        """Adaptive reliability report including energy anomalies and threshold state."""
        incidents = self.detect_energy_anomalies(adapt=True)
        report = {
            "health": self.health_snapshot(),
            "incidents": [incident.as_dict() for incident in incidents],
            "num_incidents": len(incidents),
            "critical_energy_threshold": round(self.critical_energy_threshold, 6),
            "quarantine_zone": list(self.quarantine_zone),
            "sandbox_nodes": self.sandbox.number_of_nodes(),
            "energy_snapshot": self.energy_history[-1] if self.energy_history else None,
        }
        self.incident_history.append(report)
        return report

    def restore_node(self, node_id: Any) -> dict[str, Any]:
        """Restore a quarantined node to the main graph without restoring all context edges blindly."""
        if node_id not in self.quarantine_zone or node_id not in self.sandbox:
            return {"status": "not_quarantined", "node": node_id}
        attrs = dict(self.sandbox.nodes[node_id])
        attrs.pop("quarantined", None)
        attrs.pop("quarantine_reason", None)
        self.kernel.graph.add_node(node_id, **attrs)
        self.quarantine_zone.remove(node_id)
        # BGP/SDN: re-announce the restored node into the routing table.
        routing_command = self.routing.restore_to_policy(node_id, reason="restore")
        event = {
            "status": "restored",
            "node": node_id,
            "routing_policy": routing_command.as_dict(),
            "bgp": routing_command.to_bgp(),
        }
        self.quarantine_history.append(event)
        return event

    # ------------------------------------------------------------------
    # Recovery Procedures (self-healing back into production)
    # ------------------------------------------------------------------

    def assess_recovery(self, node_id: Any, threshold: float | None = None) -> dict[str, Any]:
        """Decide whether a quarantined node is safe to return to production.

        Recovery is a controlled, evidence-based decision rather than a blind
        restore. A node is considered *recovered* only when the conditions that
        caused its quarantine are no longer present:

          - it must actually be in the sandbox / quarantine zone,
          - its projected energy back in the main graph (degree to *surviving*
            neighbours, normalized by the current max degree) must sit below the
            critical energy threshold (with a small hysteresis margin so a node
            does not flap right at the boundary).

        Returns a verdict dict with ``recoverable`` plus the evidence used.
        """
        cutoff = self.critical_energy_threshold if threshold is None else float(threshold)
        if node_id not in self.quarantine_zone or node_id not in self.sandbox:
            return {
                "node": node_id,
                "recoverable": False,
                "reasons": ["not_quarantined"],
                "projected_energy": None,
                "threshold": round(cutoff, 6),
            }

        graph = self.kernel.graph
        # Neighbours preserved in the sandbox that still exist in the live graph.
        sandbox_neighbors = [
            other for other in self.sandbox.neighbors(node_id) if other != node_id
        ]
        surviving_neighbors = [other for other in sandbox_neighbors if other in graph]
        projected_degree = len(surviving_neighbors)

        degrees = list(dict(graph.degree()).values())
        max_degree = max(degrees) if degrees else 0
        # Account for the node being re-attached when estimating the busy-ness
        # of the network after recovery.
        effective_max = max(max_degree, projected_degree, 1)
        projected_energy = projected_degree / effective_max

        # Hysteresis: require energy to drop a margin below the threshold so a
        # node hovering at the boundary is not repeatedly quarantined/restored.
        margin = max(0.0, min(0.1, self.adaptation_rate * 0.2))
        safe_band = max(0.0, cutoff - margin)
        safe_energy = projected_energy <= safe_band

        # Absolute-energy alone is misleading in uniform-degree networks (after a
        # hub is removed every remaining node can look like the new "max"). So a
        # node is also considered safe when its projected degree is *not an
        # outlier* relative to the surviving degree distribution. A DoS/flood
        # node stands out as a high-degree outlier; a benign node does not.
        outlier = False
        z_score = 0.0
        if len(degrees) >= 2:
            mean_deg = sum(degrees) / len(degrees)
            var = sum((d - mean_deg) ** 2 for d in degrees) / len(degrees)
            std = var ** 0.5
            if std > 0:
                z_score = (projected_degree - mean_deg) / std
            # Treat as outlier (still risky) only if clearly above the pack.
            outlier = z_score >= 2.0
        not_outlier = not outlier

        reasons: list[str] = []
        reasons.append(
            f"projected_energy={projected_energy:.3f}"
            f"{'<=' if safe_energy else '>'}safe_band={safe_band:.3f}"
        )
        reasons.append(f"degree_z_score={z_score:.2f}{'>=2.0_outlier' if outlier else '_within_pack'}")
        if not surviving_neighbors:
            reasons.append("no_surviving_neighbors")
        if projected_degree:
            reasons.append(f"surviving_neighbors={projected_degree}")

        # A node may rejoin when it is no longer an outlier OR its absolute
        # projected energy is within the safe band.
        recoverable = not_outlier or safe_energy
        return {
            "node": node_id,
            "recoverable": bool(recoverable),
            "reasons": reasons,
            "projected_energy": round(projected_energy, 6),
            "projected_degree": projected_degree,
            "degree_z_score": round(z_score, 4),
            "surviving_neighbors": surviving_neighbors,
            "threshold": round(cutoff, 6),
        }

    def recover_node(
        self,
        node_id: Any,
        restore_edges: bool = True,
        force: bool = False,
        threshold: float | None = None,
    ) -> dict[str, Any]:
        """Run the recovery procedure for a single quarantined node.

        Unlike :meth:`restore_node` (a raw restore of just the node), this is the
        full self-healing path:

          1. assess whether the node is safe to recover (skipped if ``force``),
          2. re-attach the node to the main graph,
          3. optionally reconnect it to its *surviving* neighbours (edges to
             neighbours that were themselves removed are intentionally dropped),
          4. remove the node and its now-orphaned context from the sandbox,
          5. emit an ``announce_route`` policy to the BGP/SDN control plane,
          6. record a recovery event for the audit trail.
        """
        assessment = self.assess_recovery(node_id, threshold=threshold)
        if assessment["reasons"] == ["not_quarantined"]:
            return {"status": "not_quarantined", "node": node_id, "assessment": assessment}
        if not force and not assessment["recoverable"]:
            return {
                "status": "recovery_deferred",
                "node": node_id,
                "assessment": assessment,
            }

        attrs = dict(self.sandbox.nodes[node_id])
        attrs.pop("quarantined", None)
        attrs.pop("quarantine_reason", None)
        attrs.pop("context_only", None)
        self.kernel.graph.add_node(node_id, **attrs)

        restored_edges = 0
        if restore_edges:
            for source, target, edge_attrs in list(self.sandbox.edges(node_id, data=True)):
                other = target if source == node_id else source
                if other == node_id:
                    continue
                # Only reconnect to neighbours that still live in the main graph.
                if other in self.kernel.graph:
                    self.kernel.graph.add_edge(node_id, other, **edge_attrs)
                    restored_edges += 1

        # Clean the recovered node out of the sandbox and drop any context-only
        # neighbours that are no longer connected to anything in the sandbox.
        self.sandbox.remove_node(node_id)
        orphan_context = [
            other
            for other, data in list(self.sandbox.nodes(data=True))
            if data.get("context_only") and self.sandbox.degree(other) == 0
        ]
        self.sandbox.remove_nodes_from(orphan_context)
        self.quarantine_zone.discard(node_id)

        routing_command = self.routing.restore_to_policy(node_id, reason="recovery")
        event = {
            "status": "recovered",
            "node": node_id,
            "forced": bool(force),
            "edges_restored": restored_edges,
            "assessment": assessment,
            "sandbox_nodes": self.sandbox.number_of_nodes(),
            "routing_policy": routing_command.as_dict(),
            "bgp": routing_command.to_bgp(),
        }
        self.recovery_history.append(event)
        self.quarantine_history.append(event)
        print(f"[NRE RECOVERY] Restored node {node_id} to production ({restored_edges} edges).")
        return event

    def auto_recover(
        self,
        limit: int | None = None,
        restore_edges: bool = True,
        threshold: float | None = None,
    ) -> list[dict[str, Any]]:
        """Recover every quarantined node that passes the recovery assessment.

        Iterates the quarantine zone, recovers the nodes whose conditions have
        cleared and leaves the rest in the sandbox (recovery deferred). Returns
        the list of successful recovery events.
        """
        events: list[dict[str, Any]] = []
        for node_id in sorted(self.quarantine_zone, key=str):
            if limit is not None and len(events) >= max(0, int(limit)):
                break
            result = self.recover_node(
                node_id, restore_edges=restore_edges, force=False, threshold=threshold
            )
            if result.get("status") == "recovered":
                events.append(result)
        return events

    def rollback_quarantine(self, node_id: Any) -> dict[str, Any]:
        """Emergency rollback: force-restore a node and reconnect its context.

        Use when a quarantine decision is judged a false positive and the node
        must be returned immediately regardless of the energy assessment.
        """
        return self.recover_node(node_id, restore_edges=True, force=True)

    def recovery_report(self) -> dict[str, Any]:
        """Summarize recovery readiness and the recovery audit trail."""
        assessments = [self.assess_recovery(node) for node in sorted(self.quarantine_zone, key=str)]
        recoverable = [a["node"] for a in assessments if a["recoverable"]]
        return {
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "kernel_cycle": getattr(self.kernel, "cycle", 0),
            "critical_energy_threshold": round(self.critical_energy_threshold, 6),
            "quarantine_zone": list(self.quarantine_zone),
            "recoverable_now": recoverable,
            "deferred": [a["node"] for a in assessments if not a["recoverable"]],
            "assessments": assessments,
            "num_recovered": len(self.recovery_history),
            "recovery_history": self.recovery_history[-10:],
        }

    # ------------------------------------------------------------------
    # Checkpoint / restore (NRE state)
    # ------------------------------------------------------------------

    def checkpoint_state(self) -> dict[str, Any]:
        """Return a JSON-serializable snapshot of the full NRE agent state.

        Captures adaptation calibration, energy history, the quarantine zone and
        sandbox graph, the quarantine/recovery audit trails and the BGP/SDN
        routing command journal, so the agent can be rebuilt identically after a
        process restart.
        """
        return {
            "config": {
                "critical_energy_threshold": self.critical_energy_threshold,
                "adaptation_rate": self.adaptation_rate,
                "min_threshold": self.min_threshold,
                "max_threshold": self.max_threshold,
                "history_window": self.history_window,
                "routing_protocol": self.routing.protocol,
            },
            "energy_history": list(self.energy_history),
            "incident_history": list(self.incident_history),
            "quarantine_zone": list(self.quarantine_zone),
            "quarantine_history": list(self.quarantine_history),
            "recovery_history": list(self.recovery_history),
            "sandbox": nx.node_link_data(self.sandbox, edges="edges"),
            "routing_journal": [command.as_dict() for command in self.routing.command_journal],
        }

    def restore_state(self, state: dict[str, Any]) -> "AdaptiveNRE":
        """Restore agent state in place from a :meth:`checkpoint_state` payload."""
        config = state.get("config", {})
        self.critical_energy_threshold = float(config.get("critical_energy_threshold", self.critical_energy_threshold))
        self.adaptation_rate = float(config.get("adaptation_rate", self.adaptation_rate))
        self.min_threshold = float(config.get("min_threshold", self.min_threshold))
        self.max_threshold = float(config.get("max_threshold", self.max_threshold))
        self.history_window = int(config.get("history_window", self.history_window))

        self.energy_history = list(state.get("energy_history", []))
        self.incident_history = list(state.get("incident_history", []))
        self.quarantine_zone = set(state.get("quarantine_zone", []))
        self.quarantine_history = list(state.get("quarantine_history", []))
        self.recovery_history = list(state.get("recovery_history", []))

        sandbox_data = state.get("sandbox")
        if sandbox_data is not None:
            self.sandbox = nx.node_link_graph(sandbox_data, edges="edges")
        else:
            self.sandbox = nx.Graph()

        # Rebuild the routing command journal from its serialized form.
        protocol = config.get("routing_protocol", self.routing.protocol)
        self.routing = BGPSDNInterface(self.kernel, protocol=protocol)
        for entry in state.get("routing_journal", []):
            self.routing.command_journal.append(
                RoutingPolicyCommand(
                    action=entry["action"],
                    target=entry["target"],
                    protocol=entry["protocol"],
                    reason=entry["reason"],
                    attributes=dict(entry.get("attributes", {})),
                )
            )
        return self

    # ------------------------------------------------------------------
    # Persistent incident logging
    # ------------------------------------------------------------------

    def incident_log(self) -> dict[str, Any]:
        """Return a structured, serializable security incident log.

        The log aggregates the agent's adaptive threshold state, energy history,
        detected anomalies, quarantine actions and current sandbox contents so it
        can be persisted to JSON for auditing or fed to the dashboard.
        """
        incidents = self.detect_energy_anomalies(adapt=False)
        return {
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "kernel_cycle": getattr(self.kernel, "cycle", 0),
            "adaptation": {
                "critical_energy_threshold": round(self.critical_energy_threshold, 6),
                "adaptation_rate": self.adaptation_rate,
                "min_threshold": self.min_threshold,
                "max_threshold": self.max_threshold,
                "history_window": self.history_window,
            },
            "energy_history": list(self.energy_history),
            "incidents": [incident.as_dict() for incident in incidents],
            "num_incidents": len(incidents),
            "quarantine_zone": list(self.quarantine_zone),
            "quarantine_history": list(self.quarantine_history),
            "recovery_history": list(self.recovery_history),
            "num_recovered": len(self.recovery_history),
            "sandbox": {
                "nodes": list(self.sandbox.nodes),
                "num_nodes": self.sandbox.number_of_nodes(),
                "num_edges": self.sandbox.number_of_edges(),
            },
            "health": self.health_snapshot(),
        }

    def export_incident_log(self, path: str = "nre_incident_log.json", append: bool = False) -> str:
        """Persist the current incident log to a JSON file.

        With ``append=True`` the new log entry is appended to a JSON array of
        previously recorded snapshots, producing a durable audit trail.
        """
        entry = self.incident_log()
        if append:
            history: list[dict[str, Any]] = []
            try:
                with open(path, encoding="utf-8") as f:
                    existing = json.load(f)
                if isinstance(existing, list):
                    history = existing
                elif isinstance(existing, dict):
                    history = [existing]
            except (FileNotFoundError, json.JSONDecodeError):
                history = []
            history.append(entry)
            payload: Any = history
        else:
            payload = entry
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        return path

    def security_dashboard_payload(self) -> dict[str, Any]:
        """Return NRE security data shaped for the HTML dashboard panel."""
        log = self.incident_log()
        return {
            "critical_energy_threshold": log["adaptation"]["critical_energy_threshold"],
            "adaptation": log["adaptation"],
            "energy_history": log["energy_history"][-12:],
            "incidents": log["incidents"][:12],
            "num_incidents": log["num_incidents"],
            "quarantine_zone": log["quarantine_zone"],
            "quarantine_history": log["quarantine_history"][-12:],
            "recovery_history": log.get("recovery_history", [])[-12:],
            "num_recovered": log.get("num_recovered", 0),
            "sandbox": log["sandbox"],
            "health": log["health"],
        }
