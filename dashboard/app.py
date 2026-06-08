import gevent.monkey
gevent.monkey.patch_all()

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sqlite3
import threading
import time
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify
from flask_socketio import SocketIO

from core.network import MeshNetwork
from core.sensor import generate_all_sensors
from alerts.engine import AlertEngine, DB_PATH
from core.node import NodeState

app = Flask(__name__)
app.config["SECRET_KEY"] = "disastermesh-secret-key"
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="gevent")

SCENARIOS = [
    {
        "name": "FIRE",
        "icon": "🔥",
        "description": "High temperature and smoke detected in sector 3-5",
        "key": "fire",
        "affected": [3, 4, 5],
        "fail_on_ticks": {},
        "ticks": 30,
    },
    {
        "name": "EARTHQUAKE",
        "icon": "🌍",
        "description": "Seismic activity detected — nodes 7-9 at risk",
        "key": "earthquake",
        "affected": [7, 8, 9],
        "fail_on_ticks": {8: [9], 16: [7]},
        "ticks": 30,
    },
    {
        "name": "MASS CASUALTY",
        "icon": "🚨",
        "description": "Multiple casualties detected across sectors 0-4, 6",
        "key": "mass_casualty",
        "affected": [0, 1, 2, 3, 4, 6],
        "fail_on_ticks": {12: [11]},
        "ticks": 30,
    },
]

_lock = threading.Lock()
sim_state = {
    "network": None,
    "scenario": "INITIALIZING",
    "scenario_payload": None,   # last scenario_change payload, replayed on connect
    "tick": 0,
    "heals": 0,
    "total_alerts": 0,
    "topology_events": [],
}


def _add_topo_event(msg: str):
    with _lock:
        sim_state["topology_events"].append(
            f"[{datetime.utcnow().strftime('%H:%M:%S')}] {msg}"
        )
        if len(sim_state["topology_events"]) > 20:
            sim_state["topology_events"] = sim_state["topology_events"][-20:]


def simulation_loop():
    while True:
        net = MeshNetwork(seed=42)
        engine = AlertEngine()

        with _lock:
            sim_state["network"] = net
            sim_state["heals"] = 0
            sim_state["total_alerts"] = 0
            sim_state["topology_events"] = []
            sim_state["tick"] = 0

        # Clear DB for fresh cycle
        if DB_PATH.exists():
            conn = sqlite3.connect(DB_PATH)
            conn.execute("DELETE FROM alerts")
            conn.commit()
            conn.close()

        for scenario in SCENARIOS:
            payload = {
                "name": scenario["name"],
                "icon": scenario["icon"],
                "description": scenario["description"],
            }
            with _lock:
                sim_state["scenario"] = scenario["name"]
                sim_state["scenario_payload"] = payload
            socketio.emit("scenario_change", payload)

            prev_heal_count = len(net.healed_routes)

            for tick in range(1, scenario["ticks"] + 1):
                net.tick()

                # Inject node failures
                if tick in scenario["fail_on_ticks"]:
                    for nid in scenario["fail_on_ticks"][tick]:
                        if nid in net.nodes and net.nodes[nid].is_operational():
                            net.fail_node(nid)
                            socketio.emit("topology_change", {
                                "type": "fail",
                                "node_id": nid,
                                "new_route": None,
                            })
                            _add_topo_event(f"Node {nid} HARDWARE FAILURE")

                            # Emit any new self-heals triggered by this failure
                            new_heals = net.healed_routes[prev_heal_count:]
                            for heal in new_heals:
                                after = heal["after"]
                                if after["success"]:
                                    with _lock:
                                        sim_state["heals"] += 1
                                    path_str = " → ".join(str(n) for n in after["path"])
                                    socketio.emit("topology_change", {
                                        "type": "heal",
                                        "node_id": heal["affected_node"],
                                        "new_route": after["path"],
                                    })
                                    _add_topo_event(
                                        f"SELF-HEAL: {heal['affected_node']}→14 "
                                        f"via [{path_str}]"
                                    )
                                else:
                                    _add_topo_event(
                                        f"HEAL FAILED: node {heal['affected_node']} isolated"
                                    )
                            prev_heal_count = len(net.healed_routes)

                # Collect sensor readings and fire alerts
                for node in net.get_operational_nodes():
                    s_key = (
                        scenario["key"]
                        if node.node_id in scenario["affected"]
                        else "normal"
                    )
                    readings = generate_all_sensors(node, s_key)
                    new_alerts = engine.ingest_readings(readings)

                    with _lock:
                        sim_state["total_alerts"] += len(new_alerts)

                    for alert in new_alerts:
                        socketio.emit("alert_event", {
                            "alert_id": alert.alert_id,
                            "level": alert.level,
                            "node_id": alert.node_id,
                            "sensor_type": alert.sensor_type,
                            "value": round(alert.value, 1),
                            "gps": alert.gps_coords,
                            "timestamp": alert.timestamp,
                        })

                # Emit node statuses every tick
                for nid, node in net.nodes.items():
                    socketio.emit("node_status", {
                        "node_id": nid,
                        "state": node.state.value,
                        "battery_level": round(node.battery, 1),
                        "node_type": node.node_type.value,
                    })

                # Broadcast latest topology events to frontend
                with _lock:
                    topo_evts = list(sim_state["topology_events"])
                socketio.emit("topo_events_update", topo_evts)

                # Emit stats
                active = sum(
                    1 for n in net.nodes.values() if n.state == NodeState.ACTIVE
                )
                sleeping = sum(
                    1 for n in net.nodes.values() if n.state == NodeState.SLEEP
                )
                failed = sum(
                    1 for n in net.nodes.values() if n.state == NodeState.FAILED
                )
                survivability = round((active + sleeping) / len(net.nodes) * 100, 1)

                with _lock:
                    total_a = sim_state["total_alerts"]
                    heals = sim_state["heals"]

                socketio.emit("stats_update", {
                    "active": active,
                    "sleeping": sleeping,
                    "failed": failed,
                    "total_alerts": total_a,
                    "heals": heals,
                    "survivability": survivability,
                })

                with _lock:
                    sim_state["tick"] += 1

                time.sleep(2)


# ── SocketIO connect: replay current state to late-joining clients ──────

@socketio.on("connect")
def on_connect():
    from flask_socketio import emit
    with _lock:
        payload  = sim_state["scenario_payload"]
        active   = sim_state["total_alerts"]
        heals    = sim_state["heals"]
        net      = sim_state["network"]

    if payload:
        emit("scenario_change", payload)

    if net is not None:
        for nid, node in net.nodes.items():
            emit("node_status", {
                "node_id": nid,
                "state": node.state.value,
                "battery_level": round(node.battery, 1),
                "node_type": node.node_type.value,
            })

        from core.node import NodeState
        active_c  = sum(1 for n in net.nodes.values() if n.state == NodeState.ACTIVE)
        sleeping  = sum(1 for n in net.nodes.values() if n.state == NodeState.SLEEP)
        failed    = sum(1 for n in net.nodes.values() if n.state == NodeState.FAILED)
        surv      = round((active_c + sleeping) / len(net.nodes) * 100, 1)
        emit("stats_update", {
            "active": active_c, "sleeping": sleeping, "failed": failed,
            "total_alerts": active, "heals": heals, "survivability": surv,
        })

    with _lock:
        topo_evts = list(sim_state["topology_events"])
    if topo_evts:
        emit("topo_events_update", topo_evts)


# ── REST Endpoints ─────────────────────────────────────────────────────

@app.route("/api/topology")
def get_topology():
    with _lock:
        net = sim_state["network"]
    if net is None:
        return jsonify({"nodes": [], "edges": []})

    nodes = [
        {
            "id": nid,
            "node_type": node.node_type.value,
            "state": node.state.value,
            "battery": round(node.battery, 1),
            "lat": node.lat,
            "lng": node.lng,
        }
        for nid, node in net.nodes.items()
    ]
    edges = [
        {"source": u, "target": v, "weight": data.get("weight", 1)}
        for u, v, data in net.graph.edges(data=True)
    ]
    return jsonify({"nodes": nodes, "edges": edges})


@app.route("/api/alerts")
def get_alerts():
    if not DB_PATH.exists():
        return jsonify([])
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        "SELECT alert_id, level, node_id, sensor_type, value, score, "
        "lat, lng, timestamp, status "
        "FROM alerts ORDER BY timestamp DESC LIMIT 50"
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return jsonify(rows)


@app.route("/api/dispatch/<alert_id>", methods=["POST"])
def dispatch_alert(alert_id):
    if not DB_PATH.exists():
        return jsonify({"error": "Database not found"}), 404
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "UPDATE alerts SET status='RESPONDED' WHERE alert_id=?", (alert_id,)
    )
    conn.commit()
    conn.close()
    return jsonify({"status": "RESPONDED", "alert_id": alert_id})


@app.route("/")
def index():
    from flask import render_template
    return render_template("index.html")


# ── Start simulation thread (works for both `python app.py` and gunicorn) ──

_sim_thread = threading.Thread(target=simulation_loop, daemon=True)
_sim_thread.start()


# ── Entry point ────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    line = "═" * 58
    print(f"\n{line}")
    print("  DISASTERMESH — Emergency Response Network Dashboard")
    print(f"  ► http://localhost:{port}")
    print(f"  ► Simulation engine starting (3 scenarios, 30 ticks each)")
    print(f"{line}\n")

    socketio.run(app, host="0.0.0.0", port=port, debug=False,
                 use_reloader=False, allow_unsafe_werkzeug=True)
