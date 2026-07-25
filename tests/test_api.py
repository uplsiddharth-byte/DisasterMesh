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


def test_dispatch_unknown_alert_does_not_error():
    resp = _client().post("/api/dispatch/does-not-exist")
    # DB may not exist yet (background sim hasn't created it) or may exist
    # with no matching row - either way this must not 500.
    assert resp.status_code in (200, 404)


if __name__ == "__main__":
    test_health()
    test_topology_shape()
    test_alerts_returns_a_list()
    test_dispatch_unknown_alert_does_not_error()
    print("OK")
