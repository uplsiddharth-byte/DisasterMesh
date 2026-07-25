from core.sensor import classify_level
from alerts.scoring import compute_severity_score, score_to_level, evaluate_node_readings


def test_classify_level_thresholds():
    assert classify_level("temperature", 30) == "INFO"
    assert classify_level("temperature", 50) == "WARNING"
    assert classify_level("temperature", 70) == "CRITICAL"
    assert classify_level("temperature", 95) == "SOS"


def test_compute_severity_score_all_max_is_100():
    readings = {
        "temperature": 120.0,
        "smoke_level": 500.0,
        "seismic_activity": 8.0,
        "heart_rate": 180.0,
    }
    assert compute_severity_score(readings) == 100.0


def test_compute_severity_score_all_min_is_0():
    readings = {
        "temperature": 20.0,
        "smoke_level": 0.0,
        "seismic_activity": 0.0,
        "heart_rate": 60.0,
    }
    assert compute_severity_score(readings) == 0.0


def test_compute_severity_score_partial_readings():
    # Only temperature present, at its midpoint -> that sensor's weight
    # alone determines the score (missing sensors don't drag it down).
    score = compute_severity_score({"temperature": 70.0})
    assert score == 50.0


def test_score_to_level_boundaries():
    assert score_to_level(80.0) == "SOS"
    assert score_to_level(75.0) == "CRITICAL"  # boundary: SOS is strictly > 75
    assert score_to_level(50.0) == "CRITICAL"
    assert score_to_level(25.0) == "WARNING"
    assert score_to_level(10.0) == "INFO"


def test_evaluate_node_readings_combines_score_and_level():
    readings = [
        {"sensor_type": "temperature", "value": 120.0},
        {"sensor_type": "smoke_level", "value": 500.0},
        {"sensor_type": "seismic_activity", "value": 8.0},
        {"sensor_type": "heart_rate", "value": 180.0},
    ]
    result = evaluate_node_readings(readings)
    assert result["score"] == 100.0
    assert result["level"] == "SOS"
    assert result["sensor_values"]["temperature"] == 120.0


if __name__ == "__main__":
    test_classify_level_thresholds()
    test_compute_severity_score_all_max_is_100()
    test_compute_severity_score_all_min_is_0()
    test_compute_severity_score_partial_readings()
    test_score_to_level_boundaries()
    test_evaluate_node_readings_combines_score_and_level()
    print("OK")
