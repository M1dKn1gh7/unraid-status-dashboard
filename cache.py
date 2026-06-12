import threading
import time


class TTLCache:
    def __init__(self):
        self._store = {}
        self._lock = threading.Lock()

    def get(self, key, ttl, fetch_fn):
        with self._lock:
            entry = self._store.get(key)
            now = time.time()

            if entry and (now - entry["ts"]) < ttl:
                return entry["data"]

        try:
            data = fetch_fn()
            data["_stale"] = False
            data["_last_updated"] = time.time()
        except Exception as e:
            with self._lock:
                if entry:
                    entry["data"]["_stale"] = True
                    return entry["data"]
            return {"_stale": True, "_error": str(e), "_last_updated": None}

        with self._lock:
            self._store[key] = {"data": data, "ts": time.time()}

        return data


cache = TTLCache()
