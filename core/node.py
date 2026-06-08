"""
node.py - Sensor node representation for the DisasterMesh network.

Each node models a physical WSN device with battery management,
duty cycling (ACTIVE/SLEEP), and multi-sensor readings.
"""

import random
import math
from datetime import datetime
from enum import Enum


class NodeState(Enum):
    ACTIVE = "ACTIVE"
    SLEEP = "SLEEP"       # Low-power duty-cycle mode (battery < 20%)
    FAILED = "FAILED"     # Hardware failure or out of range


class NodeType(Enum):
    SENSOR = "sensor"
    RELAY = "relay"
    BASE_STATION = "base_station"


class SensorNode:
    """
    Represents a single wireless sensor node in the mesh network.

    Battery drains each tick; falls below 20% → SLEEP mode.
    Nodes can be manually failed to simulate hardware faults.
    """

    # Battery drain per simulation tick (percentage points)
    DRAIN_RATES = {
        NodeType.SENSOR: 0.3,
        NodeType.RELAY: 0.5,        # Relays forward more traffic
        NodeType.BASE_STATION: 0.1,  # Mains-powered approximation
    }

    def __init__(self, node_id: int, node_type: NodeType, lat: float, lng: float):
        self.node_id = node_id
        self.node_type = node_type
        self.lat = lat
        self.lng = lng
        self.state = NodeState.ACTIVE
        self.battery = random.uniform(70, 100)  # Start with partial charge
        self.neighbors: list[int] = []          # Populated by network.py
        self.message_count = 0                  # Messages forwarded
        self.last_reading_time: datetime | None = None

    # ------------------------------------------------------------------
    # Battery & state management
    # ------------------------------------------------------------------

    def tick(self):
        """Advance one simulation tick: drain battery, update state."""
        if self.state == NodeState.FAILED:
            return

        drain = self.DRAIN_RATES[self.node_type]
        # Transmitting costs extra
        drain += self.message_count * 0.05
        self.message_count = 0

        self.battery = max(0.0, self.battery - drain)

        if self.battery < 20.0 and self.state == NodeState.ACTIVE:
            self.state = NodeState.SLEEP
        elif self.battery >= 20.0 and self.state == NodeState.SLEEP:
            # Simulate partial recharge in sleep (solar/capacitor)
            self.battery = min(100.0, self.battery + 0.5)
            if self.battery >= 30.0:
                self.state = NodeState.ACTIVE

    def fail(self):
        """Mark node as permanently failed (hardware fault)."""
        self.state = NodeState.FAILED
        self.battery = 0.0

    def is_operational(self) -> bool:
        return self.state == NodeState.ACTIVE

    # ------------------------------------------------------------------
    # Sensor readings
    # ------------------------------------------------------------------

    def read_sensors(self, scenario: str = "normal") -> dict:
        """
        Return a dict of all sensor readings for the current scenario.
        Scenarios: 'normal', 'fire', 'earthquake', 'mass_casualty'
        """
        self.last_reading_time = datetime.utcnow()
        return {
            "node_id": self.node_id,
            "node_type": self.node_type.value,
            "timestamp": self.last_reading_time.isoformat() + "Z",
            "gps_coords": {"lat": round(self.lat, 6), "lng": round(self.lng, 6)},
            "battery": round(self.battery, 1),
            "state": self.state.value,
            "sensors": {
                "temperature": self._read_temperature(scenario),
                "smoke_level": self._read_smoke(scenario),
                "seismic_activity": self._read_seismic(scenario),
                "heart_rate": self._read_heart_rate(scenario),
            },
        }

    def _read_temperature(self, scenario: str) -> dict:
        if scenario == "fire":
            value = round(random.uniform(80, 120), 1)
        else:
            value = round(random.uniform(20, 35), 1)
        return {"value": value, "unit": "°C"}

    def _read_smoke(self, scenario: str) -> dict:
        if scenario == "fire":
            value = round(random.uniform(300, 500), 1)
        else:
            value = round(random.uniform(0, 100), 1)
        return {"value": value, "unit": "AQI"}

    def _read_seismic(self, scenario: str) -> dict:
        if scenario == "earthquake":
            value = round(random.uniform(5.0, 8.0), 2)
        else:
            value = round(random.uniform(0, 2.0), 2)
        return {"value": value, "unit": "Richter"}

    def _read_heart_rate(self, scenario: str) -> dict:
        if scenario == "mass_casualty":
            value = round(random.uniform(130, 180), 0)
        else:
            value = round(random.uniform(60, 100), 0)
        return {"value": value, "unit": "BPM"}

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def distance_to(self, other: "SensorNode") -> float:
        """Euclidean distance treating lat/lng as a flat plane (small area)."""
        dlat = self.lat - other.lat
        dlng = self.lng - other.lng
        return math.sqrt(dlat ** 2 + dlng ** 2)

    def __repr__(self):
        return (
            f"Node({self.node_id}, {self.node_type.value}, "
            f"state={self.state.value}, bat={self.battery:.1f}%)"
        )
