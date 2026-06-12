import requests
import urllib3
from config import Config

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

TIMEOUT = 8

_session = None
_csrf_token = None


def collect():
    _ensure_session()

    health = _get_health()
    clients = _get_clients()

    wan = None
    wlan = None
    lan = None

    if health:
        for subsystem in health:
            name = subsystem.get("subsystem", "")
            if name == "wan":
                wan = {
                    "status": "connected" if subsystem.get("status") == "ok" else "down",
                    "down_mbps": round(subsystem.get("rx_bytes-r", 0) * 8 / 1_000_000, 1),
                    "up_mbps": round(subsystem.get("tx_bytes-r", 0) * 8 / 1_000_000, 1),
                    "latency_ms": subsystem.get("latency"),
                    "uptime_s": subsystem.get("uptime"),
                }
            elif name == "wlan":
                wlan = {
                    "clients": subsystem.get("num_user", 0),
                    "status": "ok" if subsystem.get("status") == "ok" else "degraded",
                }
            elif name == "lan":
                lan = {
                    "clients": subsystem.get("num_user", 0),
                    "status": "ok" if subsystem.get("status") == "ok" else "degraded",
                }

    total_clients = 0
    wired = 0
    wireless = 0
    if clients:
        total_clients = len(clients)
        for c in clients:
            if c.get("is_wired"):
                wired += 1
            else:
                wireless += 1

    return {
        "wan": wan,
        "clients": {
            "total": total_clients,
            "wired": wired,
            "wireless": wireless,
        },
        "wlan_status": wlan,
        "lan_status": lan,
        "health": _overall_health(wan),
    }


def _ensure_session():
    global _session, _csrf_token

    if _session:
        test = _session.get(
            f"{Config.UNIFI_URL}/proxy/network/api/s/{Config.UNIFI_SITE}/stat/health",
            verify=False,
            timeout=TIMEOUT,
        )
        if test.status_code != 401:
            return

    _session = requests.Session()

    r = _session.post(
        f"{Config.UNIFI_URL}/api/auth/login",
        json={"username": Config.UNIFI_USERNAME, "password": Config.UNIFI_PASSWORD},
        verify=False,
        timeout=TIMEOUT,
    )
    r.raise_for_status()

    _csrf_token = r.headers.get("X-CSRF-Token")
    if _csrf_token:
        _session.headers.update({"X-CSRF-Token": _csrf_token})


def _get_health():
    try:
        r = _session.get(
            f"{Config.UNIFI_URL}/proxy/network/api/s/{Config.UNIFI_SITE}/stat/health",
            verify=False,
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        return r.json().get("data", [])
    except Exception:
        return None


def _get_clients():
    try:
        r = _session.get(
            f"{Config.UNIFI_URL}/proxy/network/api/s/{Config.UNIFI_SITE}/stat/sta",
            verify=False,
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        return r.json().get("data", [])
    except Exception:
        return None


def _overall_health(wan):
    if not wan:
        return "unknown"
    if wan["status"] == "connected":
        return "good"
    return "critical"
