import requests
from config import Config

TIMEOUT = 5


def collect():
    base = Config.GLANCES_URL

    cpu = _get(f"{base}/api/4/cpu")
    mem = _get(f"{base}/api/4/mem")
    fs = _get(f"{base}/api/4/fs")
    diskio = _get(f"{base}/api/4/diskio")
    sensors = _get(f"{base}/api/4/sensors")

    cpu_percent = cpu.get("total", 0) if cpu else None

    ram = None
    if mem:
        used = mem.get("used", 0)
        total = mem.get("total", 1)
        ram = {
            "used_gb": round(used / (1024**3), 1),
            "total_gb": round(total / (1024**3), 1),
            "percent": mem.get("percent", 0),
        }

    disks = []
    if fs:
        for d in fs:
            if d.get("mnt_point", "").startswith("/mnt"):
                disks.append({
                    "name": d.get("device_name", "").split("/")[-1],
                    "mount": d.get("mnt_point"),
                    "used_gb": round(d.get("used", 0) / (1024**3), 1),
                    "total_gb": round(d.get("size", 1) / (1024**3), 1),
                    "percent": d.get("percent", 0),
                })

    disk_io = None
    if diskio:
        total_read = sum(d.get("read_bytes", 0) for d in diskio)
        total_write = sum(d.get("write_bytes", 0) for d in diskio)
        disk_io = {
            "read_mb_s": round(total_read / (1024**2), 1),
            "write_mb_s": round(total_write / (1024**2), 1),
        }

    temperatures = []
    fans = []
    if sensors:
        for s in sensors:
            sensor_type = s.get("type", "")
            if sensor_type == "temperature_core":
                temperatures.append({
                    "label": s.get("label", "Unknown"),
                    "value": s.get("value", 0),
                    "unit": "C",
                })
            elif sensor_type == "fan_speed":
                fans.append({
                    "label": s.get("label", "Unknown"),
                    "rpm": s.get("value", 0),
                })

    return {
        "cpu_percent": cpu_percent,
        "ram": ram,
        "disks": disks,
        "temperatures": temperatures,
        "fans": fans,
        "disk_io": disk_io,
    }


def _get(url):
    try:
        r = requests.get(url, timeout=TIMEOUT)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None
