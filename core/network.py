"""
network.py - Mesh network graph engine for DisasterMesh.

Builds a NetworkX graph of 15 nodes (10 sensors, 4 relays, 1 base station).
Handles neighbor discovery, random node failure, and self-healing rerouting.
Logs every topology change.
"""

import random
import math
import networkx as nx

from core.node import SensorNode, NodeState, NodeType
from core.routing import RoutingEngine


# Signal range in "coordinate units" – nodes within this distance connect
SIGNAL_RANGE = 0.035   # ~3.5 km at 0.01 ≈ 1 km scale


class MeshNetwork:
    """
    Complete mesh network containing SensorNodes arranged on a
    simulated geographic grid.

    Responsibilities:
    - Build topology (nodes + edges)
    - Manage node failures and remove them from the graph
    - Provide self-healing by re-running routing after failures
    - Expose the RoutingEngine for path queries
    """

    def __init__(self, seed: int = 42):
        random.seed(seed)
        self.graph = nx.Graph()
        self.nodes: dict[int, SensorNode] = {}
        self.topology_log: list[str] = []
        self.healed_routes: list[dict] = []  # Routes rebuilt after failures
        self.routing = RoutingEngine(self.graph)
        self._build_network()

    # ------------------------------------------------------------------
    # Network construction
    # ------------------------------------------------------------------

    def _build_network(self):
        """Create 15 nodes and connect neighbours within SIGNAL_RANGE."""
        node_specs = self._define_node_specs()

        for spec in node_specs:
            node = SensorNode(
                node_id=spec["id"],
                node_type=spec["type"],
                lat=spec["lat"],
                lng=spec["lng"],
            )
            self.nodes[node.node_id] = node
            self.graph.add_node(
                node.node_id,
                node_type=node.node_type.value,
                lat=node.lat,
                lng=node.lng,
            )

        # Connect nodes within signal range
        ids = list(self.nodes.keys())
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                a = self.nodes[ids[i]]
                b = self.nodes[ids[j]]
                dist = a.distance_to(b)
                if dist <= SIGNAL_RANGE:
                    weight = round(dist * 100, 3)  # Normalised link cost
                    self.graph.add_edge(a.node_id, b.node_id, weight=weight)
                    a.neighbors.append(b.node_id)
                    b.neighbors.append(a.node_id)

        self._log(
            f"Network built: {self.graph.number_of_nodes()} nodes, "
            f"{self.graph.number_of_edges()} edges"
        )

    def _define_node_specs(self) -> list[dict]:
        """
        Hardcoded layout so scenarios reference stable node IDs.
        Nodes 0-9: sensors, 10-13: relays, 14: base station.
        Coordinates represent a ~5×5 km disaster area.
        """
        specs = []

        # 10 sensor nodes arranged in a rough grid
        sensor_positions = [
            (34.0500, -118.2500),  # Node 0
            (34.0520, -118.2450),  # Node 1
            (34.0480, -118.2480),  # Node 2
            (34.0510, -118.2420),  # Node 3  (fire cluster)
            (34.0490, -118.2400),  # Node 4  (fire cluster)
            (34.0470, -118.2380),  # Node 5  (fire cluster)
            (34.0540, -118.2550),  # Node 6
            (34.0560, -118.2530),  # Node 7  (quake cluster)
            (34.0545, -118.2510),  # Node 8  (quake cluster)
            (34.0530, -118.2490),  # Node 9  (quake cluster)
        ]
        for i, (lat, lng) in enumerate(sensor_positions):
            specs.append({"id": i, "type": NodeType.SENSOR, "lat": lat, "lng": lng})

        # 4 relay nodes (positioned to bridge clusters)
        relay_positions = [
            (34.0505, -118.2465),  # Node 10
            (34.0525, -118.2435),  # Node 11
            (34.0515, -118.2520),  # Node 12
            (34.0535, -118.2470),  # Node 13
        ]
        for i, (lat, lng) in enumerate(relay_positions):
            specs.append({"id": 10 + i, "type": NodeType.RELAY, "lat": lat, "lng": lng})

        # 1 base station (command centre)
        specs.append({"id": 14, "type": NodeType.BASE_STATION,
                       "lat": 34.0520, "lng": 34.0520 - 152.2460})
        # Fix: use proper lng value
        specs[-1]["lng"] = -118.2460

        return specs

    # ------------------------------------------------------------------
    # Failure & self-healing
    # ------------------------------------------------------------------

    def fail_node(self, node_id: int):
        """
        Mark node as FAILED, remove it from the graph, and attempt
        self-healing for any disrupted routes.
        """
        if node_id not in self.nodes:
            return
        node = self.nodes[node_id]
        if node.state == NodeState.FAILED:
            return  # Already failed

        affected_neighbors = list(self.graph.neighbors(node_id)) \
            if node_id in self.graph else []

        node.fail()
        if node_id in self.graph:
            self.graph.remove_node(node_id)

        self._log(f"NODE FAILED: {node_id} (was {node.node_type.value})")
        self.routing.log_topology_change("NODE_FAIL", node_id,
                                          f"neighbors={affected_neighbors}")

        # Self-heal: find new routes for affected neighbours to base station
        base_id = 14
        for neighbor in affected_neighbors:
            if neighbor == base_id or neighbor not in self.graph:
                continue
            result_before = {"success": False, "path": [],
                              "method": "N/A (node just failed)"}
            result_after = self.routing.find_path(
                neighbor, base_id,
                label=f"HEAL after node-{node_id} failure"
            )
            self.healed_routes.append({
                "failed_node": node_id,
                "affected_node": neighbor,
                "before": result_before,
                "after": result_after,
            })
            if result_after["success"]:
                self._log(
                    f"  SELF-HEAL: {neighbor}→{base_id} via "
                    f"{result_after['path']}  ({result_after['method']})"
                )
            else:
                self._log(
                    f"  HEAL FAILED: no path from {neighbor} to base station"
                )

    def random_fail_node(self, exclude_ids: list[int] = None) -> int | None:
        """
        Randomly fail one ACTIVE non-base-station node.
        Returns the failed node_id or None if no candidate exists.
        """
        exclude = set(exclude_ids or [])
        exclude.add(14)  # Never randomly fail the base station
        candidates = [
            nid for nid, n in self.nodes.items()
            if n.is_operational() and nid not in exclude
        ]
        if not candidates:
            return None
        victim = random.choice(candidates)
        self.fail_node(victim)
        return victim

    # ------------------------------------------------------------------
    # Per-tick simulation step
    # ------------------------------------------------------------------

    def tick(self):
        """Advance all nodes one simulation tick (battery drain, state update)."""
        for node in self.nodes.values():
            node.tick()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def get_operational_nodes(self) -> list[SensorNode]:
        return [n for n in self.nodes.values() if n.is_operational()]

    def get_failed_nodes(self) -> list[SensorNode]:
        return [n for n in self.nodes.values()
                if n.state == NodeState.FAILED]

    def _log(self, msg: str):
        from datetime import datetime
        entry = f"[{datetime.utcnow().strftime('%H:%M:%S')}] {msg}"
        self.topology_log.append(entry)

    def print_topology(self):
        print(f"\n  Nodes : {self.graph.number_of_nodes()}")
        print(f"  Edges : {self.graph.number_of_edges()}")
        for nid, node in sorted(self.nodes.items()):
            marker = ""
            if node.node_type == NodeType.BASE_STATION:
                marker = " ★"
            elif node.node_type == NodeType.RELAY:
                marker = " ⬡"
            print(f"    Node {nid:2d}{marker:3s} "
                  f"[{node.node_type.value:12s}] "
                  f"state={node.state.value:6s}  "
                  f"bat={node.battery:5.1f}%  "
                  f"neighbors={node.neighbors}")
