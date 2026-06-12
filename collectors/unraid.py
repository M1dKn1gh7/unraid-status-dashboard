import requests
import urllib3
from datetime import datetime, timezone
from config import Config

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

TIMEOUT = 10

UNRAID_QUERY = """
query UnraidStatus {
  array {
    state
    capacity { kilobytes { free used total } }
    disks { name device status type size temp }
    parities { name device status type size temp }
    caches { name device status type size temp }
    parityCheckStatus { status progress speed errors duration running paused }
  }
  docker {
    containers { names state status image autoStart }
  }
  disks {
    device name vendor serialNum smartStatus temperature isSpinning
  }
  info {
    os { hostname uptime }
    versions { core { unraid } }
  }
}
"""


def collect():
    if not Config.UNRAID_API_URL or not Config.UNRAID_API_KEY:
        return _empty_response()

    data = _query_graphql(UNRAID_QUERY)
    if not data:
        return _empty_response()

    array_data = data.get("array")
    disks_detail = data.get("disks", [])

    return {
        "array": _parse_array(array_data, disks_detail),
        "parity": _parse_parity(array_data.get("parityCheckStatus") if array_data else None),
        "docker": _parse_docker(data.get("docker")),
        "system": _parse_system_info(data.get("info")),
    }


def _query_graphql(query):
    try:
        r = requests.post(
            Config.UNRAID_API_URL,
            json={"query": query},
            headers={
                "x-api-key": Config.UNRAID_API_KEY,
                "Content-Type": "application/json",
            },
            timeout=TIMEOUT,
            verify=False,
        )
        r.raise_for_status()
        result = r.json()
        return result.get("data")
    except Exception:
        return None


def _parse_array(array_data, disks_detail):
    if not array_data:
        return None

    state = array_data.get("state", "UNKNOWN")
    capacity = array_data.get("capacity", {}).get("kilobytes", {})
    disks_raw = array_data.get("disks", [])
    parities_raw = array_data.get("parities", [])
    caches_raw = array_data.get("caches", [])

    detail_by_device = {}
    for dd in disks_detail:
        dev = (dd.get("device") or "").replace("/dev/", "")
        detail_by_device[dev] = dd

    smart_issues = 0
    all_disks = []

    for d in disks_raw + parities_raw + caches_raw:
        status = d.get("status", "UNKNOWN")
        disk_state = _classify_disk_status(status)
        if disk_state in ("disabled", "missing"):
            pass  # counted below

        device = d.get("device", "")
        detail = detail_by_device.get(device, {})
        smart = detail.get("smartStatus", "UNKNOWN")
        if smart not in ("OK", "UNKNOWN"):
            smart_issues += 1

        all_disks.append({
            "name": d.get("name", ""),
            "device": device,
            "status": status,
            "state": disk_state,
            "type": d.get("type", ""),
            "size_bytes": d.get("size", 0),
            "temp_c": d.get("temp"),
            "smart": smart,
            "spinning": detail.get("isSpinning", False),
            "vendor": detail.get("vendor", ""),
            "serial": detail.get("serialNum", ""),
        })

    problems = sum(1 for d in all_disks if d["state"] in ("disabled", "missing"))

    return {
        "state": state,
        "started": state.upper() == "STARTED",
        "healthy": problems == 0 and smart_issues == 0 and state.upper() == "STARTED",
        "problem_count": problems,
        "smart_issues": smart_issues,
        "capacity_tb_used": round(int(capacity.get("used", 0)) / (1024 ** 2), 2),
        "capacity_tb_total": round(int(capacity.get("total", 0)) / (1024 ** 2), 2),
        "disk_count": len(disks_raw),
        "parity_count": len(parities_raw),
        "cache_count": len(caches_raw),
        "disks": all_disks,
    }


def _parse_parity(parity_data):
    if not parity_data:
        return None

    running = parity_data.get("running", False)
    speed_raw = parity_data.get("speed")
    speed_mb = None
    if speed_raw:
        try:
            speed_mb = round(int(speed_raw) / (1024 * 1024), 1)
        except (ValueError, TypeError):
            speed_mb = speed_raw

    return {
        "running": running,
        "status": parity_data.get("status", "IDLE"),
        "progress": parity_data.get("progress", 0),
        "speed": f"{speed_mb} MB/s" if speed_mb else None,
        "errors": parity_data.get("errors", 0),
        "duration": parity_data.get("duration"),
        "paused": parity_data.get("paused", False),
    }


def _parse_docker(docker_data):
    if not docker_data:
        return None

    containers = docker_data.get("containers", [])
    running = 0
    total = len(containers)
    problems = []

    for c in containers:
        state = (c.get("state") or "").lower()
        names = c.get("names", [])
        name = names[0].lstrip("/") if names else "unknown"
        if state == "running":
            running += 1
        elif c.get("autoStart") and state != "running":
            problems.append(name)

    return {
        "running": running,
        "total": total,
        "problems": problems,
        "problem_count": len(problems),
    }


def _parse_system_info(info_data):
    if not info_data:
        return None

    os_info = info_data.get("os", {})
    versions = info_data.get("versions", {}).get("core", {})

    uptime_str = os_info.get("uptime")
    uptime_days = None
    if uptime_str:
        try:
            boot_time = datetime.fromisoformat(uptime_str.replace("Z", "+00:00"))
            delta = datetime.now(timezone.utc) - boot_time
            uptime_days = delta.days
        except (ValueError, TypeError):
            pass

    return {
        "hostname": os_info.get("hostname", ""),
        "uptime_days": uptime_days,
        "version": versions.get("unraid", ""),
    }


def _classify_disk_status(status):
    status_upper = (status or "").upper()
    if "STANDBY" in status_upper:
        return "standby"
    elif "DSBL" in status_upper or "DISABLED" in status_upper:
        return "disabled"
    elif "NP" in status_upper or "MISSING" in status_upper:
        return "missing"
    return "active"


def _empty_response():
    return {
        "array": None,
        "parity": None,
        "docker": None,
        "system": None,
    }
