"""
alerts/engine.py - Alert priority engine for DisasterMesh.

Responsibilities:
- Accept sensor readings, score them, and create Alert objects
- Maintain a priority queue (SOS always processed first via heapq)
- Persist every alert to SQLite (data/alerts.db)
- Provide a query interface for the simulation summary
"""

import heapq
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path

from alerts.scoring import evaluate_node_readings, compute_severity_score, score_to_level

# ──────────────────────────────────────────────────────────────────────
# Alert level priority (lower number = higher urgency for heapq)
# ──────────────────────────────────────────────────────────────────────
LEVEL_PRIORITY = {"SOS": 0, "CRITICAL": 1, "WARNING": 2, "INFO": 3}

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "alerts.db"


class Alert:
    """Immutable alert record."""

    def __init__(self, level: str, node_id: int, sensor_type: str,
                 value: float, gps_coords: dict, score: float = 0.0):
        self.alert_id = str(uuid.uuid4())[:8]
        self.level = level
        self.node_id = node_id
        self.sensor_type = sensor_type
        self.value = value
        self.gps_coords = gps_coords
        self.score = score
        self.timestamp = datetime.utcnow().isoformat() + "Z"
        self.status = "OPEN"

    # heapq compares items: lower priority int = processed first
    def __lt__(self, other):
        return LEVEL_PRIORITY[self.level] < LEVEL_PRIORITY[other.level]

    def __repr__(self):
        return (
            f"Alert({self.alert_id}  {self.level:8s}  "
            f"node={self.node_id}  {self.sensor_type}={self.value}  "
            f"score={self.score:.1f})"
        )


class AlertEngine:
    """
    Processes sensor readings into prioritised alerts and persists them.
    SOS alerts are always at the front of the processing queue.
    """

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self._queue: list[Alert] = []   # heapq
        self.processed: list[Alert] = []
        self._init_db()

    # ------------------------------------------------------------------
    # Ingestion
    # ------------------------------------------------------------------

    def ingest_readings(self, sensor_readings: list[dict]) -> list[Alert]:
        """
        Score a batch of sensor readings from one node tick.
        Creates one Alert per reading that breaches INFO threshold (value > 0),
        but uses the combined score to determine level.
        """
        if not sensor_readings:
            return []

        assessment = evaluate_node_readings(sensor_readings)
        new_alerts = []

        for reading in sensor_readings:
            sensor_type = reading["sensor_type"]
            value = reading["value"]
            node_id = reading["node_id"]
            gps_coords = reading.get("gps_coords", {})

            # Per-sensor threshold check
            from core.sensor import classify_level
            per_sensor_level = classify_level(sensor_type, value)

            # Promote to combined score level if higher urgency
            combined_level = assessment["level"]
            level = _higher_priority(per_sensor_level, combined_level)

            alert = Alert(
                level=level,
                node_id=node_id,
                sensor_type=sensor_type,
                value=value,
                gps_coords=gps_coords,
                score=assessment["score"],
            )
            heapq.heappush(self._queue, alert)
            self._persist(alert)
            new_alerts.append(alert)

        return new_alerts

    # ------------------------------------------------------------------
    # Processing
    # ------------------------------------------------------------------

    def process_next(self) -> Alert | None:
        """Pop and return the highest-priority alert from the queue."""
        if not self._queue:
            return None
        alert = heapq.heappop(self._queue)
        alert.status = "PROCESSED"
        self.processed.append(alert)
        self._update_status(alert)
        return alert

    def process_all(self) -> list[Alert]:
        """Drain the entire queue in priority order."""
        results = []
        while self._queue:
            results.append(self.process_next())
        return results

    def queue_size(self) -> int:
        return len(self._queue)

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def summary(self) -> dict:
        """Aggregate counts from the database for the final report."""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("SELECT level, COUNT(*) FROM alerts GROUP BY level")
        counts = dict(cur.fetchall())
        cur.execute("SELECT COUNT(*) FROM alerts")
        total = cur.fetchone()[0]
        conn.close()
        return {"total": total, "by_level": counts}

    # ------------------------------------------------------------------
    # SQLite persistence
    # ------------------------------------------------------------------

    def _init_db(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                alert_id    TEXT PRIMARY KEY,
                level       TEXT NOT NULL,
                node_id     INTEGER NOT NULL,
                sensor_type TEXT NOT NULL,
                value       REAL NOT NULL,
                score       REAL NOT NULL,
                lat         REAL,
                lng         REAL,
                timestamp   TEXT NOT NULL,
                status      TEXT NOT NULL DEFAULT 'OPEN'
            )
        """)
        conn.commit()
        conn.close()

    def _persist(self, alert: Alert):
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            """INSERT INTO alerts
               (alert_id, level, node_id, sensor_type, value, score,
                lat, lng, timestamp, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                alert.alert_id, alert.level, alert.node_id,
                alert.sensor_type, alert.value, alert.score,
                alert.gps_coords.get("lat"), alert.gps_coords.get("lng"),
                alert.timestamp, alert.status,
            ),
        )
        conn.commit()
        conn.close()

    def _update_status(self, alert: Alert):
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "UPDATE alerts SET status=? WHERE alert_id=?",
            (alert.status, alert.alert_id),
        )
        conn.commit()
        conn.close()


# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────

def _higher_priority(a: str, b: str) -> str:
    """Return whichever alert level has higher urgency."""
    if LEVEL_PRIORITY[a] <= LEVEL_PRIORITY[b]:
        return a
    return b
