import networkx as nx
from core.routing import RoutingEngine


def _linear_graph(weight=0.1):
    """0 - 1 - 2 - 3, plus a disconnected node 9."""
    g = nx.Graph()
    g.add_edge(0, 1, weight=weight)
    g.add_edge(1, 2, weight=weight)
    g.add_edge(2, 3, weight=weight)
    g.add_node(9)
    return g


def test_dijkstra_finds_shortest_path_over_reliable_links():
    engine = RoutingEngine(_linear_graph(weight=0.1))  # within RELIABLE_WEIGHT_MAX
    result = engine.find_path(0, 3)
    assert result["success"] is True
    assert result["method"] == "DIJKSTRA"
    assert result["path"] == [0, 1, 2, 3]
    assert result["hops"] == 3


def test_flood_fallback_triggers_when_only_weak_links_exist():
    """All links exceed RELIABLE_WEIGHT_MAX, so Dijkstra's reliable-only
    view has no path - flooding over the full graph must pick it up."""
    engine = RoutingEngine(_linear_graph(weight=1.0))
    result = engine.find_path(0, 3)
    assert result["success"] is True
    assert result["method"] == "FLOOD"
    assert result["path"] == [0, 1, 2, 3]


def test_flood_bfs_finds_a_path_directly():
    engine = RoutingEngine(_linear_graph())
    result = engine._flood(0, 3)
    assert result["success"] is True
    assert result["path"] == [0, 1, 2, 3]


def test_no_path_between_disconnected_nodes():
    engine = RoutingEngine(_linear_graph())
    result = engine.find_path(0, 9)
    assert result["success"] is False
    assert result["method"] == "NONE"
    assert result["path"] == []


def test_route_log_records_every_attempt():
    engine = RoutingEngine(_linear_graph())
    engine.find_path(0, 3)
    engine.find_path(0, 9)
    assert len(engine.get_route_log()) == 2


if __name__ == "__main__":
    test_dijkstra_finds_shortest_path_over_reliable_links()
    test_flood_fallback_triggers_when_only_weak_links_exist()
    test_flood_bfs_finds_a_path_directly()
    test_no_path_between_disconnected_nodes()
    test_route_log_records_every_attempt()
    print("OK")
