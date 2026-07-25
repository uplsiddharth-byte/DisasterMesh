"""
Smoke tests for the Flask routes in dashboard/app.py.

Importing dashboard.app starts the real background simulation thread
(existing app behavior, not something these tests control) - so we only
assert response shape/type, not specific simulation values, to stay
non-flaky regardless of how far the simulation has progressed.
"""
from dashboard.app import app as flask_app


def _client():
    flask_app.config["TESTING"] = True
    return flask_app.test_client()


def test_health():
    resp = _client().get("/health")
    assert resp.status_code == 200


def test_topology_shape():
    resp = _client().get("/api/topology")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "nodes" in data and "edges" in data
    assert isinstance(data["nodes"], list)
    assert isinstance(data["edges"], list)


def test_alerts_returns_a_list():
    resp = _client().get("/api/alerts")
    assert resp.status_code == 200
    assert isinstance(resp.get_json(), list)


def test_dispatch_unknown_alert_returns_404():
    """Regression check for issue #2: an alert_id that isn't in the DB
    must 404, not silently report success."""
    resp = _client().post("/api/dispatch/does-not-exist")
    assert resp.status_code == 404


def test_dispatch_known_alert_succeeds():
    import sqlite3
    from alerts.engine import AlertEngine
    from dashboard.app import DB_PATH

    AlertEngine()  # ensures the alerts table exists, regardless of sim timing
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """INSERT OR REPLACE INTO alerts
           (alert_id, level, node_id, sensor_type, value, score,
            lat, lng, timestamp, status)
           VALUES ('test-alert-1', 'SOS', 0, 'temperature', 99.0, 90.0,
                   0, 0, '2026-01-01T00:00:00Z', 'OPEN')"""
    )
    conn.commit()
    conn.close()

    resp = _client().post("/api/dispatch/test-alert-1")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "RESPONDED", "alert_id": "test-alert-1"}


if __name__ == "__main__":
    test_health()
    test_topology_shape()
    test_alerts_returns_a_list()
    test_dispatch_unknown_alert_returns_404()
    test_dispatch_known_alert_succeeds()
    print("OK")
