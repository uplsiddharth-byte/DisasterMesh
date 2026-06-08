"""
simulate.py - DisasterMesh main simulation runner.

Runs three disaster scenarios in sequence:
  1. FIRE          – nodes 3, 4, 5 detect rising temperature + smoke
  2. EARTHQUAKE    – seismic spike on nodes 7, 8, 9; node failures injected
  3. MASS CASUALTY – heart-rate distress across many nodes

Each scenario simulates 30 "ticks" (compressed time steps).
Real-time console output is printed throughout; a full summary follows.
"""

import time
import random
from datetime import datetime

from core.network import MeshNetwork
from core.sensor import generate_all_sensors
from alerts.engine import AlertEngine, LEVEL_PRIORITY

# ──────────────────────────────────────────────────────────────────────
# Console styling helpers
# ──────────────────────────────────────────────────────────────────────

LEVEL_COLORS = {
    "SOS":      "\033[1;31m",   # bold red
    "CRITICAL": "\033[0;31m",   # red
    "WARNING":  "\033[0;33m",   # yellow
    "INFO":     "\033[0;36m",   # cyan
}
RESET  = "\033[0m"
BOLD   = "\033[1m"
GREEN  = "\033[0;32m"
YELLOW = "\033[0;33m"
RED    = "\033[0;31m"
CYAN   = "\033[0;36m"
GREY   = "\033[0;90m"

def clr(level: str, text: str) -> str:
    return f"{LEVEL_COLORS.get(level, '')}{text}{RESET}"

def banner(title: str, char: str = "═", width: int = 66):
    line = char * width
    pad  = (width - len(title) - 2) // 2
    print(f"\n{BOLD}{line}")
    print(f"{' ' * pad} {title} ")
    print(f"{line}{RESET}")

def section(title: str):
    print(f"\n{CYAN}{BOLD}── {title} {'─' * (58 - len(title))}{RESET}")

# ──────────────────────────────────────────────────────────────────────
# Scenario runner
# ──────────────────────────────────────────────────────────────────────

def run_scenario(
    name: str,
    affected_nodes: list[int],
    scenario_key: str,
    ticks: int,
    net: MeshNetwork,
    engine: AlertEngine,
    fail_on_ticks: dict[int, list[int]] | None = None,
):
    """
    Execute one disaster scenario.

    Args:
        name          : Display name
        affected_nodes: Node IDs that use the disaster sensor profile
        scenario_key  : Sensor generator key ('fire', 'earthquake', etc.)
        ticks         : Number of simulation steps (≈30 s simulated time)
        net           : Shared MeshNetwork instance
        engine        : Shared AlertEngine instance
        fail_on_ticks : {tick_number: [node_ids_to_fail]} injection map
    """
    banner(f"SCENARIO: {name}", "═")
    fail_on_ticks = fail_on_ticks or {}
    base_id = 14

    sos_count = crit_count = warn_count = info_count = 0

    for tick in range(1, ticks + 1):
        net.tick()

        # Inject failures on specific ticks
        if tick in fail_on_ticks:
            for nid in fail_on_ticks[tick]:
                if nid in net.nodes and net.nodes[nid].is_operational():
                    print(f"\n  {RED}[TICK {tick:02d}] ⚠  NODE {nid} HARDWARE FAILURE INJECTED{RESET}")
                    net.fail_node(nid)
                    # Show route healing
                    for healed in net.healed_routes[-3:]:
                        after = healed["after"]
                        if after["success"]:
                            path_str = " → ".join(str(n) for n in after["path"])
                            print(f"  {GREEN}  ↺  SELF-HEAL route: [{path_str}]  "
                                  f"{after['hops']} hops  {after['latency_ms']}ms "
                                  f"[{after['method']}]{RESET}")
                        else:
                            print(f"  {RED}  ✗  HEAL FAILED – node {healed['affected_node']} "
                                  f"isolated{RESET}")

        # Collect sensor readings from operational nodes
        for node in net.get_operational_nodes():
            s_key = scenario_key if node.node_id in affected_nodes else "normal"
            readings = generate_all_sensors(node, s_key)
            new_alerts = engine.ingest_readings(readings)

            for alert in new_alerts:
                level = alert.level
                if level == "INFO":
                    info_count += 1
                    continue  # Suppress INFO spam in console; they're in the DB

                if level == "SOS":
                    sos_count += 1
                elif level == "CRITICAL":
                    crit_count += 1
                elif level == "WARNING":
                    warn_count += 1

                ts = datetime.utcnow().strftime("%H:%M:%S")
                print(
                    f"  {clr(level, f'[{level:8s}]')} "
                    f"tick={tick:02d}  node={alert.node_id:2d}  "
                    f"{alert.sensor_type:18s}={alert.value:7.1f}  "
                    f"score={alert.score:5.1f}  "
                    f"{GREY}{ts}{RESET}"
                )

        # Route sample: node in affected cluster → base station
        if tick % 6 == 0 and affected_nodes:
            src = affected_nodes[0]
            if src in net.graph and base_id in net.graph:
                result = net.routing.find_path(src, base_id, label=name)
                path_str = " → ".join(str(n) for n in result["path"])
                status = f"{GREEN}OK{RESET}" if result["success"] else f"{RED}FAIL{RESET}"
                print(
                    f"\n  {CYAN}[ROUTE CHECK tick={tick:02d}]{RESET} "
                    f"{src}→{base_id}  [{path_str}]  "
                    f"{result['hops']} hops  {result['latency_ms']}ms  "
                    f"[{result['method']}]  {status}\n"
                )

        time.sleep(0.05)   # Throttle output for readability

    # Scenario mini-summary
    section(f"Scenario '{name}' complete")
    print(f"  Alerts this scenario:  "
          f"{clr('SOS', f'SOS={sos_count}')}  "
          f"{clr('CRITICAL', f'CRITICAL={crit_count}')}  "
          f"{clr('WARNING', f'WARNING={warn_count}')}  "
          f"{clr('INFO', f'INFO={info_count}')}  (INFO suppressed from console)")
    print(f"  Failed nodes so far:   "
          f"{[n.node_id for n in net.get_failed_nodes()]}")
    print(f"  Self-heals performed:  {len(net.healed_routes)}")


# ──────────────────────────────────────────────────────────────────────
# Final summary
# ──────────────────────────────────────────────────────────────────────

def print_summary(net: MeshNetwork, engine: AlertEngine):
    banner("SIMULATION SUMMARY", "═")
    db_summary = engine.summary()

    print(f"\n  {BOLD}ALERT TOTALS{RESET}")
    print(f"  ┌─────────────┬──────────┐")
    print(f"  │ Level       │  Count   │")
    print(f"  ├─────────────┼──────────┤")
    by_level = db_summary["by_level"]
    for level in ["SOS", "CRITICAL", "WARNING", "INFO"]:
        count = by_level.get(level, 0)
        print(f"  │ {clr(level, f'{level:11s}')} │ {count:8d} │")
    print(f"  ├─────────────┼──────────┤")
    print(f"  │ {BOLD}{'TOTAL':11s}{RESET} │ {db_summary['total']:8d} │")
    print(f"  └─────────────┴──────────┘")

    print(f"\n  {BOLD}NODE FAILURES{RESET}")
    failed = net.get_failed_nodes()
    if failed:
        for node in failed:
            print(f"    ✗  Node {node.node_id:2d}  [{node.node_type.value}]  "
                  f"lat={node.lat}  lng={node.lng}")
    else:
        print("    None")

    print(f"\n  {BOLD}SELF-HEALING EVENTS{RESET}")
    heals = net.healed_routes
    if heals:
        for h in heals:
            after = h["after"]
            if after["success"]:
                path_str = " → ".join(str(n) for n in after["path"])
                print(f"    ↺  Node {h['failed_node']} failed → "
                      f"Node {h['affected_node']} re-routed via [{path_str}]  "
                      f"({after['method']}  {after['latency_ms']}ms)")
            else:
                print(f"    ✗  Node {h['failed_node']} failed → "
                      f"Node {h['affected_node']} ISOLATED (no heal path)")
    else:
        print("    No healing events recorded.")

    print(f"\n  {BOLD}ROUTING LOG ENTRIES{RESET}")
    log = net.routing.get_route_log()
    route_entries  = [e for e in log if e.get("type") != "TOPOLOGY_CHANGE"]
    topo_entries   = [e for e in log if e.get("type") == "TOPOLOGY_CHANGE"]
    print(f"    Route queries:     {len(route_entries)}")
    print(f"    Topology changes:  {len(topo_entries)}")

    print(f"\n  {BOLD}TOPOLOGY LOG (last 8 entries){RESET}")
    for entry in net.topology_log[-8:]:
        print(f"    {GREY}{entry}{RESET}")

    print(f"\n  {BOLD}DATABASE{RESET}")
    from alerts.engine import DB_PATH
    print(f"    Alerts stored at: {DB_PATH}")
    print()


# ──────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────

def main():
    banner("DisasterMesh  –  WSN Disaster Simulation Engine", "▓")
    print(f"  {GREY}Started: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC{RESET}")

    # Wipe previous DB for a clean run
    from alerts.engine import DB_PATH
    if DB_PATH.exists():
        DB_PATH.unlink()

    net    = MeshNetwork(seed=42)
    engine = AlertEngine()

    section("Initial Topology")
    net.print_topology()

    # ── Scenario 1: FIRE ──────────────────────────────────────────────
    run_scenario(
        name="FIRE",
        affected_nodes=[3, 4, 5],
        scenario_key="fire",
        ticks=30,
        net=net,
        engine=engine,
        fail_on_ticks={},
    )

    # ── Scenario 2: EARTHQUAKE ────────────────────────────────────────
    run_scenario(
        name="EARTHQUAKE",
        affected_nodes=[7, 8, 9],
        scenario_key="earthquake",
        ticks=30,
        net=net,
        engine=engine,
        fail_on_ticks={8: [9], 16: [7]},   # Nodes 9 and 7 fail mid-scenario
    )

    # ── Scenario 3: MASS CASUALTY ─────────────────────────────────────
    run_scenario(
        name="MASS CASUALTY",
        affected_nodes=[0, 1, 2, 3, 4, 6],
        scenario_key="mass_casualty",
        ticks=30,
        net=net,
        engine=engine,
        fail_on_ticks={12: [11]},           # Relay 11 fails under load
    )

    print_summary(net, engine)


if __name__ == "__main__":
    main()
