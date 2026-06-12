import requests
from config import Config

TIMEOUT = 5

DISK_LABELS = {
    "/mnt/disk1": "Disk 1",
    "/mnt/disk2": "Disk 2",
    "/mnt/disk3": "Disk 3",
    "/mnt/disk4": "Disk 4",
    "/mnt/disk5": "Disk 5",
    "/mnt/cache": "Cache (NVMe)",
}

SKIP_MOUNTS = {"/mnt/user", "/mnt/user0"}

TEMP_LABELS = {
    "Composite": "NVMe SSD",
    "Tctl": "CPU (Tctl)",
    "edge": "CPU (Edge)",
    "Package id 0": "CPU Package",
    "Core 0": "CPU Core 0",
    "Core 1": "CPU Core 1",
    "Core 2": "CPU Core 2",
    "Core 3": "CPU Core 3",
}


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
            mount = d.get("mnt_point", "")
            if mount in SKIP_MOUNTS:
                continue
            if not mount.startswith("/mnt"):
                continue
            label = DISK_LABELS.get(mount, mount.split("/")[-1])
            disks.append({
                "name": label,
                "mount": mount,
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
            label = s.get("label", "Unknown")
            if "temperature" in sensor_type:
                display_label = TEMP_LABELS.get(label, label)
                temperatures.append({
                    "label": display_label,
                    "value": s.get("value", 0),
                    "unit": "C",
                })
            elif "fan" in sensor_type:
                fans.append({
                    "label": label,
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
