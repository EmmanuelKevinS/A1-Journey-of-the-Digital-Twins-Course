"""Shared lab asset model, environment config, and twin-state rules."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ASSET_MODEL_PATH = REPO_ROOT / "config" / "lab_asset_model.json"


def load_local_env() -> None:
    env_path = REPO_ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_local_env()


def env_str(name: str, default: str) -> str:
    return os.getenv(name, default)


def env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    return default if value in (None, "") else int(value)


def env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    return default if value in (None, "") else float(value)


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value in (None, ""):
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def load_asset_model() -> dict[str, Any]:
    path = Path(os.getenv("LAB_ASSET_MODEL", str(DEFAULT_ASSET_MODEL_PATH)))
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def sensors_by_type(asset_model: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {sensor["sensor_type"]: sensor for sensor in asset_model["sensors"]}


def topic_for_sensor(sensor: dict[str, Any]) -> str:
    topic_prefix = env_str("MQTT_TOPIC_PREFIX", "lab/sensors")
    return f"{topic_prefix}/{sensor['sensor_type']}"


def temperature_threshold(asset_model: dict[str, Any]) -> float:
    default = float(asset_model["thresholds"]["temperature_high_c"])
    return env_float("TEMP_ALERT_THRESHOLD", default)


def warm_threshold(asset_model: dict[str, Any]) -> float:
    default = float(asset_model["thresholds"]["temperature_warm_c"])
    return env_float("TEMP_WARM_THRESHOLD", default)


def classify_comfort(asset_model: dict[str, Any], temperature: float, humidity: float) -> str:
    if temperature > temperature_threshold(asset_model):
        return "OVERHEAT"
    if temperature >= warm_threshold(asset_model):
        return "WARM"
    if humidity > float(asset_model["thresholds"]["humidity_high_pct"]):
        return "HUMID"
    if temperature < 21:
        return "COOL"
    return "COMFORTABLE"


def classify_occupancy(asset_model: dict[str, Any], occupancy: int) -> str:
    capacity = int(asset_model["room"]["capacity_people"])
    high = int(asset_model["thresholds"]["occupancy_high_people"])
    if occupancy <= 0:
        return "EMPTY"
    if occupancy >= high:
        return "CROWDED"
    if occupancy >= capacity * 0.5:
        return "ACTIVE"
    return "LIGHT"


def build_sensor_payload(
    asset_model: dict[str, Any],
    sensor_type: str,
    value: float,
    sequence: int,
    timestamp: float | None = None,
    quality: str = "GOOD",
) -> dict[str, Any]:
    sensor = sensors_by_type(asset_model)[sensor_type]
    room = asset_model["room"]
    return {
        "reading_id": f"{sensor['sensor_id']}-{sequence:06d}",
        "room_id": room["room_id"],
        "room_name": room["name"],
        "run_id": env_str("SIM_RUN_ID", "manual"),
        "sensor_id": sensor["sensor_id"],
        "sensor": sensor_type,
        "sensor_type": sensor_type,
        "zone": sensor["zone_id"],
        "value": value,
        "unit": sensor["unit"],
        "quality": quality,
        "timestamp": timestamp or time.time(),
    }


def derive_twin_state(
    asset_model: dict[str, Any],
    readings: dict[str, dict[str, Any]],
    timestamp: float | None = None,
) -> dict[str, Any]:
    temperature = float(readings["temperature"]["value"])
    humidity = float(readings["humidity"]["value"])
    occupancy = int(float(readings["occupancy"]["value"]))
    threshold = temperature_threshold(asset_model)
    alert_active = temperature > threshold
    room = asset_model["room"]
    return {
        "room_id": room["room_id"],
        "room_name": room["name"],
        "temperature": temperature,
        "humidity": humidity,
        "occupancy": occupancy,
        "comfort_status": classify_comfort(asset_model, temperature, humidity),
        "occupancy_level": classify_occupancy(asset_model, occupancy),
        "alert_active": alert_active,
        "alert_active_numeric": 1 if alert_active else 0,
        "alert_message": (
            f"Temperature {temperature:.1f} degC exceeds {threshold:.1f} degC"
            if alert_active
            else "No active temperature alert"
        ),
        "temperature_threshold": threshold,
        "timestamp": timestamp or time.time(),
    }
