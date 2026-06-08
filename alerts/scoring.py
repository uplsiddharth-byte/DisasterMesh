"""
scoring.py - Weighted severity scoring for DisasterMesh alerts.

Combines readings from all four sensors into a single 0-100 score,
then maps that score to an alert level.

Weights:
  smoke_level       30%
  temperature       25%
  seismic_activity  25%
  heart_rate        20%
"""

# Sensor weight configuration
WEIGHTS = {
    "smoke_level":       0.30,
    "temperature":       0.25,
    "seismic_activity":  0.25,
    "heart_rate":        0.20,
}

# Per-sensor normalisation ranges: (normal_min, emergency_max)
# Values are clipped to [0, emergency_max] before normalisation.
NORM_RANGES = {
    "temperature":       (20.0,  120.0),
    "smoke_level":       (0.0,   500.0),
    "seismic_activity":  (0.0,   8.0),
    "heart_rate":        (60.0,  180.0),
}

# Score thresholds → alert level  (SOS strictly > 75, not >= 75)
SCORE_LEVELS = [
    (75.0, "SOS"),       # > 75
    (50.0, "CRITICAL"),  # 50–75
    (25.0, "WARNING"),   # 25–49
    (0.0,  "INFO"),      # < 25
]


def compute_severity_score(readings: dict[str, float]) -> float:
    """
    Calculate a weighted 0-100 severity score from a dict of
    {sensor_type: value}.  Missing sensors are treated as 0 contribution.

    Args:
        readings: e.g. {"temperature": 95.0, "smoke_level": 420.0, ...}

    Returns:
        float score in [0, 100]
    """
    total_weight = 0.0
    weighted_sum = 0.0

    for sensor, weight in WEIGHTS.items():
        value = readings.get(sensor)
        if value is None:
            continue

        low, high = NORM_RANGES[sensor]
        # Normalise to [0, 1]; clip extremes
        normalised = max(0.0, min(1.0, (value - low) / (high - low)))
        weighted_sum += normalised * weight
        total_weight += weight

    if total_weight == 0:
        return 0.0

    # Scale to [0, 100], adjusted for missing sensors
    raw_score = (weighted_sum / total_weight) * 100.0
    return round(raw_score, 2)


def score_to_level(score: float) -> str:
    """Map a numeric severity score to its alert level string."""
    if score > 75.0:
        return "SOS"
    for threshold, level in SCORE_LEVELS[1:]:   # CRITICAL, WARNING, INFO
        if score >= threshold:
            return level
    return "INFO"


def evaluate_node_readings(sensor_readings: list[dict]) -> dict:
    """
    Accept the list of sensor-reading dicts from sensor.py and return
    a combined assessment dict.

    Each reading dict must have 'sensor_type' and 'value' keys.
    """
    values = {r["sensor_type"]: r["value"] for r in sensor_readings}
    score = compute_severity_score(values)
    level = score_to_level(score)
    return {
        "score": score,
        "level": level,
        "sensor_values": values,
    }
