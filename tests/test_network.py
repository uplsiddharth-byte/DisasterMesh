from core.network import MeshNetwork
from core.node import SensorNode, NodeState, NodeType


def test_network_builds_15_nodes_fully_meshed():
    net = MeshNetwork(seed=42)
    assert net.graph.number_of_nodes() == 15
    assert net.nodes[14].node_type == NodeType.BASE_STATION


def test_fail_node_marks_failed_and_removes_from_graph():
    net = MeshNetwork(seed=42)
    net.fail_node(3)
    assert net.nodes[3].state == NodeState.FAILED
    assert 3 not in net.graph
    assert net.graph.number_of_nodes() == 14


def test_fail_node_is_idempotent():
    net = MeshNetwork(seed=42)
    net.fail_node(3)
    heals_after_first = len(net.healed_routes)
    net.fail_node(3)  # already failed - should be a no-op
    assert len(net.healed_routes) == heals_after_first


def test_fail_node_triggers_self_heal_for_neighbors():
    net = MeshNetwork(seed=42)
    net.fail_node(3)
    assert len(net.healed_routes) > 0
    assert all(h["failed_node"] == 3 for h in net.healed_routes)
    # every neighbor of node 3 (other than base station 14) got a heal attempt
    assert all(h["after"]["success"] for h in net.healed_routes)


def test_self_heal_uses_both_dijkstra_and_flood_across_failures():
    """Regression check for issue #1: the flood fallback must actually be
    reachable, not dead code shadowed by an always-successful Dijkstra."""
    methods_seen = set()
    for fail_id in range(14):  # every non-base node
        net = MeshNetwork(seed=42)
        net.fail_node(fail_id)
        methods_seen.update(h["after"]["method"] for h in net.healed_routes)
    assert {"DIJKSTRA", "FLOOD"} <= methods_seen


def test_tick_drains_battery():
    node = SensorNode(0, NodeType.SENSOR, lat=0.0, lng=0.0)
    node.battery = 50.0
    node.tick()
    assert node.battery == 49.7  # SENSOR drain rate is 0.3/tick


def test_low_battery_enters_sleep_state():
    node = SensorNode(0, NodeType.SENSOR, lat=0.0, lng=0.0)
    node.battery = 20.2
    node.tick()  # drops below 20
    assert node.state == NodeState.SLEEP


def test_failed_node_ignores_ticks():
    node = SensorNode(0, NodeType.SENSOR, lat=0.0, lng=0.0)
    node.fail()
    node.tick()
    assert node.battery == 0.0
    assert node.state == NodeState.FAILED


if __name__ == "__main__":
    test_network_builds_15_nodes_fully_meshed()
    test_fail_node_marks_failed_and_removes_from_graph()
    test_fail_node_is_idempotent()
    test_fail_node_triggers_self_heal_for_neighbors()
    test_self_heal_uses_both_dijkstra_and_flood_across_failures()
    test_tick_drains_battery()
    test_low_battery_enters_sleep_state()
    test_failed_node_ignores_ticks()
    print("OK")
