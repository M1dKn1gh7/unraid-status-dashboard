import os


class Config:
    PORT = int(os.environ.get("DASHBOARD_PORT", "9090"))

    GLANCES_URL = os.environ.get("GLANCES_URL", "http://192.168.1.200:61208")

    TAUTULLI_URL = os.environ.get("TAUTULLI_URL", "http://192.168.1.200:8181")
    TAUTULLI_API_KEY = os.environ.get("TAUTULLI_API_KEY", "")

    QBIT_URL = os.environ.get("QBIT_URL", "http://192.168.1.200:8080")
    QBIT_USERNAME = os.environ.get("QBIT_USERNAME", "admin")
    QBIT_PASSWORD = os.environ.get("QBIT_PASSWORD", "")

    OVERSEERR_URL = os.environ.get("OVERSEERR_URL", "http://192.168.1.200:5055")
    OVERSEERR_API_KEY = os.environ.get("OVERSEERR_API_KEY", "")

    HA_URL = os.environ.get("HA_URL", "http://192.168.1.200:8123")
    HA_TOKEN = os.environ.get("HA_TOKEN", "")

    UNIFI_URL = os.environ.get("UNIFI_URL", "https://192.168.1.1")
    UNIFI_USERNAME = os.environ.get("UNIFI_USERNAME", "")
    UNIFI_PASSWORD = os.environ.get("UNIFI_PASSWORD", "")
    UNIFI_SITE = os.environ.get("UNIFI_SITE", "default")

    CACHE_TTL_SYSTEM = int(os.environ.get("CACHE_TTL_SYSTEM", "10"))
    CACHE_TTL_MEDIA = int(os.environ.get("CACHE_TTL_MEDIA", "15"))
    CACHE_TTL_UPS = int(os.environ.get("CACHE_TTL_UPS", "10"))
    CACHE_TTL_NETWORK = int(os.environ.get("CACHE_TTL_NETWORK", "30"))
