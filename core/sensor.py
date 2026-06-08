"""
sensor.py - Sensor data generators for each disaster scenario.

Provides both per-node helpers and batch generation across a node set.
Each reading is a self-contained dict with value, unit, timestamp,
node_id, and gps_coords so alerts/engine.py can be fully self-sufficient.
"""

import random
from datetime import datetime


# ──────────────────────────────────────────────────────────────────────
# Threshold definitions (used by alerts/engine.py as well)
# ──────────────────────────────────────────────────────────────────────

THRESHOLDS = {
    "temperature": {
        "WARNING":  45.0,   # °C
        "CRITICAL": 65.0,
        "SOS":      90.0,
    },
    "smoke_level": {
        "WARNING":  150.0,  # AQI
        "CRITICAL": 250.0,
        "SOS":      400.0,
    },
    "seismic_activity": {
        "WARNING":  2.5,    # Richter
        "CRITICAL": 4.0,
        "SOS":      6.0,
    },
    "heart_rate": {
        "WARNING":  110.0,  # BPM
        "CRITICAL": 140.0,
        "SOS":      165.0,
    },
}


# ──────────────────────────────────────────────────────────────────────
# Individual sensor generators
# ──────────────────────────────────────────────────────────────────────

def generate_temperature(scenario: str = "normal", node_id: int = 0,
                         lat: float = 0.0, lng: float = 0.0) -> dict:
    """Generate a temperature reading. Fire scenario: 93-120 °C (always SOS)."""
    if scenario == "fire":
        value = round(random.uniform(93, 120), 1)   # always above SOS threshold (90)
    else:
        value = round(random.uniform(20, 35), 1)
    return _wrap("temperature", value, "°C", node_id, lat, lng)


def generate_smoke(scenario: str = "normal", node_id: int = 0,
                   lat: float = 0.0, lng: float = 0.0) -> dict:
    """Generate a smoke/AQI reading. Fire scenario: 410-500 AQI (always SOS)."""
    if scenario == "fire":
        value = round(random.uniform(410, 500), 1)  # always above SOS threshold (400)
    else:
        value = round(random.uniform(0, 100), 1)
    return _wrap("smoke_level", value, "AQI", node_id, lat, lng)


def generate_seismic(scenario: str = "normal", node_id: int = 0,
                     lat: float = 0.0, lng: float = 0.0) -> dict:
    """Generate a seismic reading. Earthquake scenario: 5.0-8.0 Richter."""
    if scenario == "earthquake":
        value = round(random.uniform(5.0, 8.0), 2)
    else:
        value = round(random.uniform(0, 2.0), 2)
    return _wrap("seismic_activity", value, "Richter", node_id, lat, lng)


def generate_heart_rate(scenario: str = "normal", node_id: int = 0,
                        lat: float = 0.0, lng: float = 0.0) -> dict:
    """Generate a heart-rate reading. Mass-casualty scenario: 130-180 BPM."""
    if scenario == "mass_casualty":
        value = round(random.uniform(130, 180), 0)
    else:
        value = round(random.uniform(60, 100), 0)
    return _wrap("heart_rate", value, "BPM", node_id, lat, lng)


# ──────────────────────────────────────────────────────────────────────
# Batch helper used by simulate.py
# ──────────────────────────────────────────────────────────────────────

def generate_all_sensors(node, scenario: str = "normal") -> list[dict]:
    """
    Return a list of four sensor readings for a given SensorNode object.
    node must expose: node_id, lat, lng
    """
    lat, lng = node.lat, node.lng
    nid = node.node_id
    return [
        generate_temperature(scenario, nid, lat, lng),
        generate_smoke(scenario, nid, lat, lng),
        generate_seismic(scenario, nid, lat, lng),
        generate_heart_rate(scenario, nid, lat, lng),
    ]


# ──────────────────────────────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────────────────────────────

def _wrap(sensor_type: str, value: float, unit: str,
          node_id: int, lat: float, lng: float) -> dict:
    return {
        "sensor_type": sensor_type,
        "value": value,
        "unit": unit,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "node_id": node_id,
        "gps_coords": {"lat": round(lat, 6), "lng": round(lng, 6)},
    }


def classify_level(sensor_type: str, value: float) -> str:
    """Return the alert level string for a given sensor value."""
    thresholds = THRESHOLDS.get(sensor_type, {})
    if value >= thresholds.get("SOS", float("inf")):
        return "SOS"
    if value >= thresholds.get("CRITICAL", float("inf")):
        return "CRITICAL"
    if value >= thresholds.get("WARNING", float("inf")):
        return "WARNING"
    return "INFO"
