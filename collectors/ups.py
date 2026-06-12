import requests
from config import Config

TIMEOUT = 5

ENTITIES = [
    "sensor.ups_battery_charge",
    "sensor.ups_real_power",
    "sensor.ups_load",
    "sensor.ups_status",
    "sensor.ups_output_voltage",
    "sensor.ups_battery_runtime",
]


def collect():
    headers = {
        "Authorization": f"Bearer {Config.HA_TOKEN}",
        "Content-Type": "application/json",
    }

    states = {}
    for entity_id in ENTITIES:
        try:
            r = requests.get(
                f"{Config.HA_URL}/api/states/{entity_id}",
                headers=headers,
                timeout=TIMEOUT,
            )
            r.raise_for_status()
            data = r.json()
            states[entity_id] = data.get("state")
        except Exception:
            states[entity_id] = None

    battery = _to_float(states.get("sensor.ups_battery_charge"))
    real_power = _to_float(states.get("sensor.ups_real_power"))
    load = _to_float(states.get("sensor.ups_load"))
    voltage = _to_float(states.get("sensor.ups_output_voltage"))
    runtime_s = _to_float(states.get("sensor.ups_battery_runtime"))
    status_raw = states.get("sensor.ups_status") or "unknown"

    status = _parse_status(status_raw)
    runtime_min = round(runtime_s / 60, 1) if runtime_s else None
    headroom_w = round(550 - real_power) if real_power else None
    health = _derive_health(status, battery)

    return {
        "status": status,
        "status_raw": status_raw,
        "battery_percent": battery,
        "load_percent": load,
        "real_power_w": real_power,
        "capacity_va": 550,
        "output_voltage": voltage,
        "runtime_minutes": runtime_min,
        "headroom_w": headroom_w,
        "health": health,
    }


def _parse_status(raw):
    raw_lower = raw.lower()
    if "ol" in raw_lower or "online" in raw_lower:
        return "Online"
    if "ob" in raw_lower or "on battery" in raw_lower:
        return "On Battery"
    if "lb" in raw_lower or "low battery" in raw_lower:
        return "Low Battery"
    return raw


def _derive_health(status, battery):
    if status == "Online" and battery and battery > 80:
        return "good"
    if status == "On Battery" or (battery and 50 <= battery <= 80):
        return "warning"
    if status == "Low Battery" or (battery and battery < 50):
        return "critical"
    return "good"


def _to_float(val):
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None
