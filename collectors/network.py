import requests
import urllib3
from config import Config

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

TIMEOUT = 8

_session = None


def collect():
    _ensure_session()

    health = _get_health()
    clients = _get_clients()
    devices = _get_devices()

    wan = None
    wlan = None
    lan = None

    if health:
        for subsystem in health:
            name = subsystem.get("subsystem", "")
            if name == "wan":
                down_mbps = round(subsystem.get("rx_bytes-r", 0) * 8 / 1_000_000, 1)
                up_mbps = round(subsystem.get("tx_bytes-r", 0) * 8 / 1_000_000, 1)
                wan = {
                    "status": "connected" if subsystem.get("status") == "ok" else "down",
                    "down_mbps": down_mbps,
                    "up_mbps": up_mbps,
                    "latency_ms": subsystem.get("latency"),
                    "uptime_s": subsystem.get("uptime"),
                    "capacity_mbps": Config.WAN_SPEED_MBPS,
                    "utilisation_down_pct": round(down_mbps / Config.WAN_SPEED_MBPS * 100, 1) if Config.WAN_SPEED_MBPS else 0,
                    "utilisation_up_pct": round(up_mbps / Config.WAN_SPEED_MBPS * 100, 1) if Config.WAN_SPEED_MBPS else 0,
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
    top_clients = []
    if clients:
        total_clients = len(clients)
        for c in clients:
            if c.get("is_wired"):
                wired += 1
            else:
                wireless += 1

        sorted_by_bw = sorted(
            clients,
            key=lambda c: (c.get("rx_bytes-r", 0) + c.get("tx_bytes-r", 0)),
            reverse=True,
        )

        for c in sorted_by_bw[:5]:
            rx = c.get("rx_bytes-r", 0)
            tx = c.get("tx_bytes-r", 0)
            total_bw = rx + tx
            if total_bw < 1000:
                continue
            name = c.get("name") or c.get("hostname") or c.get("oui", c.get("mac", "Unknown"))
            top_clients.append({
                "name": name,
                "down_mbps": round(rx * 8 / 1_000_000, 2),
                "up_mbps": round(tx * 8 / 1_000_000, 2),
                "total_mbps": round(total_bw * 8 / 1_000_000, 2),
            })

    gateway = _parse_gateway(devices)

    return {
        "wan": wan,
        "clients": {
            "total": total_clients,
            "wired": wired,
            "wireless": wireless,
        },
        "top_clients": top_clients,
        "wlan_status": wlan,
        "lan_status": lan,
        "gateway": gateway,
        "health": _overall_health(wan, wlan, lan),
    }


def _parse_gateway(devices):
    if not devices:
        return None

    for d in devices:
        if d.get("type") == "ugw" or d.get("type") == "udm":
            sys_stats = d.get("system-stats", {})
            wan1 = d.get("wan1", {})
            uptime_s = d.get("uptime")
            uptime_days = round(uptime_s / 86400, 1) if uptime_s else None

            return {
                "name": d.get("name", "UDM"),
                "model": d.get("model", ""),
                "cpu_pct": _safe_float(sys_stats.get("cpu")),
                "mem_pct": _safe_float(sys_stats.get("mem")),
                "uptime_days": uptime_days,
                "wan_ip": wan1.get("ip") if wan1 else None,
                "satisfaction": d.get("satisfaction"),
            }

    return None


def _safe_float(val):
    if val is None:
        return None
    try:
        return round(float(val), 1)
    except (ValueError, TypeError):
        return None


def _ensure_session():
    global _session

    if _session:
        return

    _session = requests.Session()
    _session.headers.update({"X-API-KEY": Config.UNIFI_API_KEY})


def _get_health():
    try:
        r = _session.get(
            f"{Config.UNIFI_URL}/proxy/network/api/s/{Config.UNIFI_SITE}/stat/health",
            verify=False,
            timeout=TIMEOUT,
        )
        if r.status_code == 401:
            _reset_session()
            return None
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
        if r.status_code == 401:
            _reset_session()
            return None
        r.raise_for_status()
        return r.json().get("data", [])
    except Exception:
        return None


def _get_devices():
    try:
        r = _session.get(
            f"{Config.UNIFI_URL}/proxy/network/api/s/{Config.UNIFI_SITE}/stat/device",
            verify=False,
            timeout=TIMEOUT,
        )
        if r.status_code == 401:
            _reset_session()
            return None
        r.raise_for_status()
        return r.json().get("data", [])
    except Exception:
        return None


def _reset_session():
    global _session
    _session = None


def _overall_health(wan, wlan, lan):
    if not wan:
        return "unknown"
    if wan["status"] != "connected":
        return "critical"
    if wlan and wlan.get("status") != "ok":
        return "warning"
    if lan and lan.get("status") != "ok":
        return "warning"
    return "good"
