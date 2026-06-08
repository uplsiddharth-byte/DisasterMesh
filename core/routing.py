"""
routing.py - Ad-hoc routing engine for DisasterMesh.

Primary path: Dijkstra shortest path (via NetworkX).
Fallback: controlled flooding when the primary path is broken.
Simulates per-hop latency (10–50 ms) and maintains a route-discovery log.
"""

import random
import time
from datetime import datetime
import networkx as nx


class RoutingEngine:
    """
    Wraps a NetworkX graph and provides path-finding with latency simulation
    and an automatic fallback to flooding when Dijkstra fails.
    """

    HOP_LATENCY_MS = (10, 50)  # Min/max ms per hop

    def __init__(self, graph: nx.Graph):
        self.graph = graph
        self.route_log: list[dict] = []   # Full history of route decisions

    # ------------------------------------------------------------------
    # Primary routing
    # ------------------------------------------------------------------

    def find_path(self, src: int, dst: int,
                  label: str = "") -> dict:
        """
        Attempt Dijkstra; fall back to flooding if no path exists.
        Returns a route-result dict and appends it to route_log.
        """
        result = self._dijkstra(src, dst)

        if result["success"]:
            method = "DIJKSTRA"
        else:
            # Primary path broken – try flooding
            result = self._flood(src, dst)
            method = "FLOOD" if result["success"] else "NONE"

        result["method"] = method
        result["label"] = label
        result["timestamp"] = datetime.utcnow().isoformat() + "Z"
        self.route_log.append(result)
        return result

    # ------------------------------------------------------------------
    # Dijkstra wrapper
    # ------------------------------------------------------------------

    def _dijkstra(self, src: int, dst: int) -> dict:
        try:
            path = nx.dijkstra_path(self.graph, src, dst, weight="weight")
            hops = len(path) - 1
            latency = self._simulate_latency(hops)
            return {
                "success": True,
                "src": src,
                "dst": dst,
                "path": path,
                "hops": hops,
                "latency_ms": latency,
            }
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return {"success": False, "src": src, "dst": dst,
                    "path": [], "hops": 0, "latency_ms": 0}

    # ------------------------------------------------------------------
    # Controlled flooding fallback
    # ------------------------------------------------------------------

    def _flood(self, src: int, dst: int) -> dict:
        """
        BFS-based flooding: explores the graph layer by layer until the
        destination is reached or all reachable nodes are exhausted.
        Only traverses nodes that are currently in the graph (failed nodes
        are removed by network.py before this is called).
        """
        if src not in self.graph or dst not in self.graph:
            return {"success": False, "src": src, "dst": dst,
                    "path": [], "hops": 0, "latency_ms": 0}

        visited = {src: None}   # node → predecessor
        queue = [src]

        while queue:
            current = queue.pop(0)
            if current == dst:
                # Reconstruct path
                path = []
                node = dst
                while node is not None:
                    path.append(node)
                    node = visited[node]
                path.reverse()
                hops = len(path) - 1
                # Flooding adds overhead: +20 ms per hop
                latency = self._simulate_latency(hops, overhead=20)
                return {
                    "success": True,
                    "src": src,
                    "dst": dst,
                    "path": path,
                    "hops": hops,
                    "latency_ms": latency,
                }
            for neighbor in self.graph.neighbors(current):
                if neighbor not in visited:
                    visited[neighbor] = current
                    queue.append(neighbor)

        return {"success": False, "src": src, "dst": dst,
                "path": [], "hops": 0, "latency_ms": 0}

    # ------------------------------------------------------------------
    # Latency simulation
    # ------------------------------------------------------------------

    def _simulate_latency(self, hops: int, overhead: int = 0) -> float:
        """Sum random per-hop latency values, add optional overhead."""
        if hops == 0:
            return 0.0
        total = sum(
            random.randint(*self.HOP_LATENCY_MS) for _ in range(hops)
        )
        return round(total + overhead * hops, 2)

    # ------------------------------------------------------------------
    # Route discovery log helpers
    # ------------------------------------------------------------------

    def log_topology_change(self, change_type: str, node_id: int,
                             details: str = ""):
        """Record a topology event (node failure, link addition, etc.)."""
        self.route_log.append({
            "type": "TOPOLOGY_CHANGE",
            "change_type": change_type,
            "node_id": node_id,
            "details": details,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        })

    def get_route_log(self) -> list[dict]:
        return self.route_log

    def format_path(self, result: dict) -> str:
        """Human-readable one-liner for a route result."""
        if not result["success"]:
            return (f"  NO ROUTE  {result['src']} → {result['dst']}  "
                    f"[{result.get('method', '?')}]")
        path_str = " → ".join(str(n) for n in result["path"])
        return (
            f"  {result['src']} → {result['dst']}  "
            f"path=[{path_str}]  hops={result['hops']}  "
            f"latency={result['latency_ms']}ms  [{result.get('method', '?')}]"
        )
