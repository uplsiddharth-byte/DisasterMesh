import networkx as nx
from core.routing import RoutingEngine


def _linear_graph():
    """0 - 1 - 2 - 3, plus a disconnected node 9."""
    g = nx.Graph()
    g.add_edge(0, 1, weight=1)
    g.add_edge(1, 2, weight=1)
    g.add_edge(2, 3, weight=1)
    g.add_node(9)
    return g


def test_dijkstra_finds_shortest_path():
    engine = RoutingEngine(_linear_graph())
    result = engine.find_path(0, 3)
    assert result["success"] is True
    assert result["method"] == "DIJKSTRA"
    assert result["path"] == [0, 1, 2, 3]
    assert result["hops"] == 3


def test_flood_bfs_finds_a_path_directly():
    """_flood is a plain BFS; exercise it directly regardless of when
    find_path's fallback branch triggers it."""
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
    test_dijkstra_finds_shortest_path()
    test_flood_bfs_finds_a_path_directly()
    test_no_path_between_disconnected_nodes()
    test_route_log_records_every_attempt()
    print("OK")
