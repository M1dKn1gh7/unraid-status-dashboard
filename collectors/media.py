import requests
from config import Config

TIMEOUT = 5


def collect():
    streams = _fetch_tautulli()
    downloads = _fetch_qbittorrent()
    requests_pending = _fetch_overseerr()

    return {
        "streams": streams,
        "downloads": downloads,
        "requests_pending": requests_pending,
    }


def _fetch_tautulli():
    try:
        r = requests.get(
            f"{Config.TAUTULLI_URL}/api/v2",
            params={"apikey": Config.TAUTULLI_API_KEY, "cmd": "get_activity"},
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()

        response = data.get("response", {}).get("data", {})
        sessions = response.get("sessions", [])

        items = []
        for s in sessions:
            items.append({
                "user": s.get("friendly_name", "Unknown"),
                "title": s.get("full_title", s.get("title", "Unknown")),
                "progress": int(s.get("progress_percent", 0)),
                "quality": s.get("quality_profile", ""),
                "state": s.get("state", ""),
            })

        return {
            "count": len(sessions),
            "bandwidth_mbps": round(int(response.get("total_bandwidth", 0)) / 1000, 1),
            "items": items,
        }
    except Exception:
        return None


def _fetch_qbittorrent():
    try:
        session = requests.Session()

        session.post(
            f"{Config.QBIT_URL}/api/v2/auth/login",
            data={"username": Config.QBIT_USERNAME, "password": Config.QBIT_PASSWORD},
            timeout=TIMEOUT,
        )

        info = session.get(f"{Config.QBIT_URL}/api/v2/transfer/info", timeout=TIMEOUT)
        info.raise_for_status()
        transfer = info.json()

        torrents_r = session.get(
            f"{Config.QBIT_URL}/api/v2/torrents/info",
            params={"filter": "downloading"},
            timeout=TIMEOUT,
        )
        torrents_r.raise_for_status()
        torrents = torrents_r.json()

        active = []
        for t in torrents[:5]:
            eta = t.get("eta", 0)
            eta_str = _format_eta(eta) if eta < 8640000 else "∞"
            active.append({
                "name": t.get("name", "Unknown"),
                "progress": round(t.get("progress", 0) * 100, 1),
                "dlspeed_mbps": round(t.get("dlspeed", 0) / (1024**2), 1),
                "eta": eta_str,
            })

        return {
            "speed_mbps": round(transfer.get("dl_info_speed", 0) / (1024**2), 1),
            "upload_mbps": round(transfer.get("up_info_speed", 0) / (1024**2), 1),
            "active_count": len(torrents),
            "active": active,
        }
    except Exception:
        return None


def _fetch_overseerr():
    try:
        r = requests.get(
            f"{Config.OVERSEERR_URL}/api/v1/request",
            params={"filter": "pending", "take": 20, "skip": 0},
            headers={"X-Api-Key": Config.OVERSEERR_API_KEY},
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
        return data.get("pageInfo", {}).get("results", 0)
    except Exception:
        return None


def _format_eta(seconds):
    if seconds <= 0:
        return "done"
    h = seconds // 3600
    m = (seconds % 3600) // 60
    if h > 0:
        return f"{h}h {m}m"
    return f"{m}m"
