import requests
import urllib3
from config import Config

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

TIMEOUT = 10

UNRAID_QUERY = """
query UnraidStatus {
  array {
    state
    capacity { kilobytes { free used total } }
    disks { name device status type size temp }
    parityCheckStatus { status progress speed errors duration running paused }
  }
  docker {
    containers { names state status image autoStart }
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
    return {
        "array": _parse_array(array_data),
        "parity": _parse_parity(array_data.get("parityCheckStatus") if array_data else None),
        "docker": _parse_docker(data.get("docker")),
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


def _parse_array(array_data):
    if not array_data:
        return None

    state = array_data.get("state", "UNKNOWN")
    capacity = array_data.get("capacity", {}).get("kilobytes", {})
    disks_raw = array_data.get("disks", [])

    disks = []
    problems = 0
    for d in disks_raw:
        status = d.get("status", "UNKNOWN")
        disk_state = _classify_disk_status(status)
        if disk_state in ("disabled", "missing"):
            problems += 1
        disks.append({
            "name": d.get("name", ""),
            "device": d.get("device", ""),
            "status": status,
            "state": disk_state,
            "type": d.get("type", ""),
            "size_bytes": d.get("size", 0),
            "temp_c": d.get("temp"),
        })

    return {
        "state": state,
        "started": state.upper() == "STARTED",
        "healthy": problems == 0 and state.upper() == "STARTED",
        "problem_count": problems,
        "capacity_tb_used": round(int(capacity.get("used", 0)) / (1024 ** 2), 2),
        "capacity_tb_total": round(int(capacity.get("total", 0)) / (1024 ** 2), 2),
        "disk_count": len(disks_raw),
        "disks": disks,
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
    }
