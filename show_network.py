"""
show_network.py - Visual snapshot of DisasterMesh topology in three states.

Usage: .venv/bin/python show_network.py
Output: network_visualization.png
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import networkx as nx

from core.network import MeshNetwork
from core.node import NodeType

FAILED_NODES = [7, 9, 11]

C_SENSOR = "#2ecc71"   # green
C_RELAY  = "#3498db"   # blue
C_BASE   = "#f1c40f"   # yellow
C_FAILED = "#e74c3c"   # red
C_GREY   = "#aaaaaa"   # grey
C_HEAL   = "#00aaff"   # bright blue


def _node_color(graph, node_id):
    t = graph.nodes[node_id]["node_type"]
    if t == NodeType.SENSOR.value:
        return C_SENSOR
    if t == NodeType.RELAY.value:
        return C_RELAY
    return C_BASE


def _node_size(graph, node_id):
    return 400 if graph.nodes[node_id]["node_type"] == NodeType.BASE_STATION.value else 220


def _pos(graph):
    return {nid: (d["lng"], d["lat"]) for nid, d in graph.nodes(data=True)}


def _plot_normal(ax, net):
    g = net.graph
    pos = _pos(g)
    colors = [_node_color(g, n) for n in g.nodes()]
    sizes  = [_node_size(g, n) for n in g.nodes()]

    nx.draw_networkx_edges(g, pos, edge_color=C_GREY, width=0.8, alpha=0.5, ax=ax)
    nx.draw_networkx_nodes(g, pos, node_color=colors, node_size=sizes, ax=ax)
    nx.draw_networkx_labels(g, pos, font_size=7, font_weight="bold", ax=ax)

    ax.set_title(
        f"Normal State — {g.number_of_nodes()} Nodes, {g.number_of_edges()} Edges",
        fontsize=10, fontweight="bold",
    )
    ax.axis("off")


def _plot_failure(ax, net):
    g = net.graph
    pos = _pos(g)

    failed = set(FAILED_NODES)
    failed_edges = [(u, v) for u, v in g.edges() if u in failed or v in failed]
    normal_edges = [(u, v) for u, v in g.edges() if u not in failed and v not in failed]

    colors = [C_FAILED if n in failed else _node_color(g, n) for n in g.nodes()]
    sizes  = [_node_size(g, n) for n in g.nodes()]

    nx.draw_networkx_edges(g, pos, edgelist=normal_edges,
                           edge_color=C_GREY, width=0.8, alpha=0.5, ax=ax)
    nx.draw_networkx_edges(g, pos, edgelist=failed_edges,
                           edge_color=C_FAILED, width=1.5, style="dashed", alpha=0.75, ax=ax)
    nx.draw_networkx_nodes(g, pos, node_color=colors, node_size=sizes, ax=ax)
    nx.draw_networkx_labels(g, pos, font_size=7, font_weight="bold", ax=ax)

    ax.set_title("After Node Failures — Nodes 7, 9, 11 Failed",
                 fontsize=10, fontweight="bold")
    ax.axis("off")


def _plot_healed(ax, net):
    g = net.graph
    pos = _pos(g)

    heal_pairs = set()
    for route in net.healed_routes:
        path = route["after"].get("path", [])
        for i in range(len(path) - 1):
            u, v = path[i], path[i + 1]
            if g.has_edge(u, v):
                heal_pairs.add((min(u, v), max(u, v)))

    heal_edges   = [(u, v) for u, v in g.edges() if (min(u, v), max(u, v)) in heal_pairs]
    normal_edges = [(u, v) for u, v in g.edges() if (min(u, v), max(u, v)) not in heal_pairs]

    colors = [_node_color(g, n) for n in g.nodes()]
    sizes  = [_node_size(g, n) for n in g.nodes()]

    nx.draw_networkx_edges(g, pos, edgelist=normal_edges,
                           edge_color=C_GREY, width=0.8, alpha=0.5, ax=ax)
    if heal_edges:
        nx.draw_networkx_edges(g, pos, edgelist=heal_edges,
                               edge_color=C_HEAL, width=3.5, alpha=0.9, ax=ax)
    nx.draw_networkx_nodes(g, pos, node_color=colors, node_size=sizes, ax=ax)
    nx.draw_networkx_labels(g, pos, font_size=7, font_weight="bold", ax=ax)

    ax.set_title("After Self-Healing — Network Recovered",
                 fontsize=10, fontweight="bold")
    ax.axis("off")


def main():
    net_normal = MeshNetwork(seed=42)

    net_failed = MeshNetwork(seed=42)
    for fn in FAILED_NODES:
        net_failed.fail_node(fn)

    fig, axes = plt.subplots(1, 3, figsize=(20, 7))
    fig.suptitle("DisasterMesh — WSN Topology Visualization", fontsize=14, fontweight="bold")

    _plot_normal(axes[0], net_normal)
    _plot_failure(axes[1], net_normal)
    _plot_healed(axes[2], net_failed)

    legend_handles = [
        mpatches.Patch(color=C_SENSOR, label="Sensor (0–9)"),
        mpatches.Patch(color=C_RELAY,  label="Relay (10–13)"),
        mpatches.Patch(color=C_BASE,   label="Base Station (14)"),
        mpatches.Patch(color=C_FAILED, label="Failed Node"),
        mpatches.Patch(color=C_HEAL,   label="Healing Route"),
    ]
    fig.legend(handles=legend_handles, loc="lower center", ncol=5, fontsize=9,
               bbox_to_anchor=(0.5, 0.01))

    plt.tight_layout(rect=[0, 0.07, 1, 0.97])

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "network_visualization.png")
    plt.savefig(out, dpi=150, bbox_inches="tight")
    print(f"Saved → {out}")

    plt.show()


if __name__ == "__main__":
    main()
