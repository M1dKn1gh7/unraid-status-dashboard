import requests
from config import Config

TIMEOUT = 5


def collect():
    streams = _fetch_tautulli()
    downloads = _fetch_qbittorrent()
    requests_pending = _fetch_overseerr()
    libraries = _fetch_libraries()

    return {
        "streams": streams,
        "downloads": downloads,
        "requests_pending": requests_pending,
        "libraries": libraries,
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
                "episode_title": s.get("title", ""),
                "media_type": s.get("media_type", ""),
                "grandparent_title": s.get("grandparent_title", ""),
                "season": s.get("parent_media_index"),
                "episode": s.get("media_index"),
                "progress": int(s.get("progress_percent", 0)),
                "view_offset_ms": int(s.get("view_offset", 0)),
                "duration_ms": int(s.get("duration", 0)),
                "state": s.get("state", ""),
                "video_decision": s.get("video_decision", ""),
                "audio_decision": s.get("audio_decision", ""),
                "quality": s.get("stream_video_resolution") or s.get("video_resolution", ""),
                "location": s.get("location", ""),
                "player": s.get("player", ""),
                "thumb": s.get("parent_thumb") or s.get("thumb", "") if s.get("media_type") == "track" else s.get("grandparent_thumb") or s.get("thumb", ""),
                "user_thumb": s.get("user_thumb", ""),  # add this line
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

        seeding_r = session.get(
            f"{Config.QBIT_URL}/api/v2/torrents/info",
            params={"filter": "seeding"},
            timeout=TIMEOUT,
        )
        seeding_count = len(seeding_r.json()) if seeding_r.status_code == 200 else 0

        completed_r = session.get(
            f"{Config.QBIT_URL}/api/v2/torrents/info",
            params={"filter": "completed"},
            timeout=TIMEOUT,
        )
        completed_count = len(completed_r.json()) if completed_r.status_code == 200 else 0

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
            "seeding_count": seeding_count,
            "completed_count": completed_count,
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


def _fetch_libraries():
    movies = _fetch_radarr()
    shows = _fetch_sonarr()
    tautulli_libs = _fetch_tautulli_libraries()

    return {
        "movies": movies,
        "shows": shows,
        "music": tautulli_libs.get("music") if tautulli_libs else None,
    }


def _fetch_radarr():
    if not Config.RADARR_API_KEY:
        return None
    try:
        r = requests.get(
            f"{Config.RADARR_URL}/api/v3/movie",
            params={"apikey": Config.RADARR_API_KEY},
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        movies = r.json()
        total_size = sum(m.get("sizeOnDisk", 0) for m in movies)
        has_file = sum(1 for m in movies if m.get("hasFile"))
        return {
            "count": has_file,
            "total": len(movies),
            "size_gb": round(total_size / (1024**3), 1),
        }
    except Exception:
        return None


def _fetch_sonarr():
    if not Config.SONARR_API_KEY:
        return None
    try:
        r = requests.get(
            f"{Config.SONARR_URL}/api/v3/series",
            params={"apikey": Config.SONARR_API_KEY},
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        series = r.json()
        total_size = sum(s.get("statistics", {}).get("sizeOnDisk", 0) for s in series)
        total_episodes = sum(s.get("statistics", {}).get("episodeFileCount", 0) for s in series)
        return {
            "count": len(series),
            "episodes": total_episodes,
            "size_gb": round(total_size / (1024**3), 1),
        }
    except Exception:
        return None


def _fetch_tautulli_libraries():
    try:
        r = requests.get(
            f"{Config.TAUTULLI_URL}/api/v2",
            params={"apikey": Config.TAUTULLI_API_KEY, "cmd": "get_libraries"},
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
        libs = data.get("response", {}).get("data", [])

        result = {}
        for lib in libs:
            section_type = lib.get("section_type", "")
            if section_type == "artist":
                result["music"] = {
                    "artists": int(lib.get("count", 0)),
                    "albums": int(lib.get("parent_count", 0)),
                    "tracks": int(lib.get("child_count", 0)),
                }
        return result
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
