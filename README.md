# 🌐 DisasterMesh — Emergency Response Network

> A real-time wireless sensor network (WSN) simulation that models multi-disaster scenarios, self-healing mesh routing, and live emergency dispatch — all visualized in a D3.js dashboard.

![Python](https://img.shields.io/badge/Python-3.12+-blue?logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.1-green?logo=flask&logoColor=white)
![NetworkX](https://img.shields.io/badge/NetworkX-3.6-orange)
![License](https://img.shields.io/badge/License-MIT-yellow)
![Status](https://img.shields.io/badge/Status-Active-brightgreen)

---

## ✨ Features

- **15-Node Mesh Network** — 10 sensors, 4 relay nodes, 1 base station arranged on a geographic grid
- **3 Disaster Scenarios** — FIRE (nodes 3-5), EARTHQUAKE (nodes 7-9), MASS CASUALTY (nodes 0-4, 6)
- **Dijkstra + Flood Routing** — primary shortest-path routing with automatic BFS flooding fallback
- **Self-Healing** — failed nodes are detected and affected routes are instantly rerouted
- **Priority Alert Queue** — SOS → CRITICAL → WARNING → INFO, scored by weighted multi-sensor analysis
- **Live Dashboard** — real-time D3.js force-directed network graph with SocketIO event streaming
- **SQLite Persistence** — every alert is persisted with GPS coordinates, score, and dispatch status
- **REST API** — topology, alerts, and emergency dispatch endpoints

---

## 🛠 Tech Stack

| Layer | Technology |
|---|---|
| Simulation Engine | Python 3.12, NetworkX 3.6 |
| Web Backend | Flask 3.1, Flask-SocketIO 5.6 |
| Async Worker | Eventlet 0.41 |
| Database | SQLite (via stdlib `sqlite3`) |
| Frontend | D3.js v7, Socket.IO 4.7 |
| Routing | Dijkstra (NetworkX) + BFS Flood fallback |
| Deployment | Gunicorn + Eventlet |

---

## 📸 Screenshots

> _Screenshots will be added after first deployment._

| Dashboard View | Network Topology |
|---|---|
| ![Dashboard](docs/screenshot-dashboard.png) | ![Topology](docs/screenshot-topology.png) |

---

## 🚀 Live Demo

> **[https://disastermesh.onrender.com](https://disastermesh.onrender.com)** ← _replace with your URL after deploy_

---

## 🖥 How to Run Locally

### Prerequisites
- Python 3.12+ (3.14 works locally; see [Deployment Notes](#deployment-notes))
- Git

### Setup

```bash
# 1. Clone the repository
git clone https://github.com/YOUR_USERNAME/DisasterMesh.git
cd DisasterMesh

# 2. Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate          # macOS/Linux
# .venv\Scripts\activate           # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the CLI simulation (standalone, no server required)
python simulate.py

# 5. Start the live dashboard
python dashboard/app.py
# Open http://localhost:5001 in your browser
```

The dashboard auto-loops through all 3 scenarios. The SQLite database is created automatically at `data/alerts.db` on first run.

### API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/topology` | Returns all 15 nodes + 105 edges |
| GET | `/api/alerts` | Returns last 50 alerts from SQLite |
| POST | `/api/dispatch/<alert_id>` | Marks an alert as RESPONDED |

---

## 📁 Project Structure

```
DisasterMesh/
├── alerts/
│   ├── engine.py          # Alert priority queue + SQLite persistence
│   └── scoring.py         # Weighted severity scoring (0–100)
├── core/
│   ├── network.py         # Mesh network graph engine (NetworkX)
│   ├── node.py            # SensorNode: battery, duty-cycle, state
│   ├── routing.py         # Dijkstra routing + BFS flood fallback
│   └── sensor.py          # Sensor data generators per scenario
├── dashboard/
│   ├── app.py             # Flask + SocketIO live dashboard server
│   └── templates/
│       └── index.html     # D3.js network visualization UI
├── data/
│   └── alerts.db          # SQLite DB (gitignored, auto-created)
├── simulate.py            # CLI simulation runner (no server needed)
├── Procfile               # Gunicorn deployment config
├── runtime.txt            # Python version for deployment platforms
├── requirements.txt
└── LICENSE
```

---

## 📡 SocketIO Events

The dashboard subscribes to these real-time events:

| Event | Payload |
|---|---|
| `alert_event` | `{alert_id, level, node_id, sensor_type, value, gps, timestamp}` |
| `node_status` | `{node_id, state, battery_level, node_type}` |
| `topology_change` | `{type: "fail"\|"heal", node_id, new_route}` |
| `scenario_change` | `{name, icon, description}` |
| `stats_update` | `{active, sleeping, failed, total_alerts, heals, survivability}` |

---

## 🏗 Deployment Notes

Deployment platforms (Render, Railway) currently support up to Python **3.12**. If your local environment uses Python 3.14, you may need to create a fresh venv with Python 3.12 when deploying. The `runtime.txt` file pins this to 3.12.

---

## 👤 Author

**Siddharth** — WSN Simulation Project

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
