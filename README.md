# Unraid Status Dashboard

A self-contained Docker container that displays real-time Unraid server health across 4 rotating panels. Designed for wall-mounted tablets with a dark OLED aesthetic. One glance tells you if anything needs attention.

## Panels

| # | Panel | Data Sources | What it shows |
|---|-------|--------------|---------------|
| 1 | **System** | Glances + Unraid GraphQL | CPU/RAM/Load bars, array health, disk temps, SMART status, parity check, Docker containers, storage |
| 2 | **Media** | Tautulli, qBittorrent, Overseerr, Radarr, Sonarr | Library stats, active Plex streams, downloads, pending requests |
| 3 | **UPS** | Home Assistant (NUT) | Battery level, load, power draw, runtime, voltage |
| 4 | **Network** | UniFi UDM SE | WAN throughput, hardware stats (UDM + AP temps/CPU/mem), active LAN ports with device/client names + bandwidth, top clients |

## Features

- Auto-rotates every 30 seconds (toggle on/off)
- Manual navigation: tap dots, swipe, or arrow keys
- Data refreshes every 10 seconds (backend caches per-source with configurable TTLs)
- Colour-coded health at a glance: green (<50%), amber (50-80%), red (>80%)
- Graceful degradation: stale data served if a source goes down, optional sources hidden when not configured

## Quick Start

```bash
git clone https://github.com/M1dKn1gh7/unraid-status-dashboard.git /mnt/user/appdata/status-dashboard
cd /mnt/user/appdata/status-dashboard
cp .env.example .env
nano .env  # Fill in your API keys

docker build -t status-dashboard .
docker run -d --name=status-dashboard \
  --net=docker-media-network \
  --env-file=/mnt/user/appdata/status-dashboard/.env \
  -e TZ=Europe/London \
  -p 9090:9090 \
  --restart=unless-stopped \
  status-dashboard
```

Dashboard available at `http://<your-unraid-ip>:9090`

## Environment Variables

### Required

| Variable | Where to find it |
|----------|-----------------|
| `TAUTULLI_API_KEY` | Tautulli > Settings > Web Interface > API Key |
| `QBIT_PASSWORD` | qBittorrent WebUI password |
| `OVERSEERR_API_KEY` | Overseerr > Settings > General > API Key |
| `RADARR_API_KEY` | Radarr > Settings > General > API Key |
| `SONARR_API_KEY` | Sonarr > Settings > General > API Key |
| `HA_TOKEN` | Home Assistant > Profile > Security > Long-Lived Access Token |
| `UNIFI_API_KEY` | UDM > Settings > Admins & Users > API Keys |

### Optional

| Variable | Default | Description |
|----------|---------|-------------|
| `DASHBOARD_PORT` | `9090` | Port to serve on |
| `GLANCES_URL` | `http://192.168.1.200:61208` | Glances API base URL |
| `TAUTULLI_URL` | `http://192.168.1.200:8181` | Tautulli base URL |
| `QBIT_URL` | `http://192.168.1.200:8080` | qBittorrent WebUI (via gluetun) |
| `QBIT_USERNAME` | `admin` | qBit username |
| `OVERSEERR_URL` | `http://192.168.1.200:5055` | Overseerr base URL |
| `RADARR_URL` | `http://192.168.1.200:7878` | Radarr base URL |
| `SONARR_URL` | `http://192.168.1.200:8989` | Sonarr base URL |
| `HA_URL` | `http://192.168.1.200:8123` | Home Assistant URL |
| `UNIFI_URL` | `https://192.168.1.1` | UniFi controller URL |
| `UNIFI_SITE` | `default` | UniFi site name |
| `WAN_SPEED_MBPS` | `900` | Your line speed (for utilisation % calculation) |
| `UNRAID_API_URL` | *(empty)* | Unraid GraphQL endpoint (e.g. `http://192.168.1.200/graphql`) |
| `UNRAID_API_KEY` | *(empty)* | Unraid API key (Settings > Management Access > API Keys) |
| `CACHE_TTL_SYSTEM` | `10` | Glances cache TTL (seconds) |
| `CACHE_TTL_MEDIA` | `15` | Media cache TTL |
| `CACHE_TTL_UPS` | `10` | UPS cache TTL |
| `CACHE_TTL_NETWORK` | `30` | Network cache TTL |
| `CACHE_TTL_UNRAID` | `30` | Unraid GraphQL cache TTL |

### Unraid GraphQL API (Optional)

Requires Unraid 6.12+. Adds array health, disk temps/SMART, parity check progress, and Docker container status to the System panel. Without it, the System panel still works using Glances data alone.

Setup:
1. Unraid WebUI > Settings > Management Access > API Keys
2. Create a new key (read-only is sufficient)
3. Set `UNRAID_API_URL=http://192.168.1.200/graphql` and `UNRAID_API_KEY=<your-key>` in `.env`

## Architecture

```
Flask backend (Python 3.12 + Gunicorn)
├── collectors/        One per data source, each exports collect() -> dict
│   ├── system.py      Glances REST API v4 (CPU, RAM, disks, temps, I/O)
│   ├── unraid.py      Unraid GraphQL API (array, parity, docker, disk detail)
│   ├── media.py       Tautulli + qBittorrent + Overseerr + Radarr + Sonarr
│   ├── ups.py         Home Assistant REST API (NUT entities)
│   └── network.py     UniFi UDM SE API (health, clients, devices)
├── cache.py           TTL cache with thread-safe get(), serves stale on failure
├── config.py          All config from environment variables
└── app.py             Flask routes + static file serving

Frontend (single HTML file, zero build step)
└── static/dashboard.html   Inline CSS + JS, polls /api/all every 10s
```

## Updating

```bash
cd /mnt/user/appdata/status-dashboard && git pull
docker stop status-dashboard && docker rm status-dashboard
docker build -t status-dashboard .
docker run -d --name=status-dashboard --net=docker-media-network --env-file=/mnt/user/appdata/status-dashboard/.env -e TZ=Europe/London -p 9090:9090 --restart=unless-stopped status-dashboard
```

## Network Notes

- Container joins `docker-media-network` (172.18.0.0/16) to reach other containers by name
- qBittorrent is behind gluetun — use `http://gluetun:8080` from docker network, `192.168.1.200:8080` from outside
- UniFi uses API key auth (`X-API-KEY` header) to avoid MFA prompts. Self-signed cert is accepted.
- Unraid GraphQL uses `x-api-key` header. Use `http://` not `https://` unless you've set up SSL on your Unraid box.

## Unraid Docker Template

To get the container icon in the Unraid Docker tab:
```bash
cp status-dashboard.xml /boot/config/plugins/dockerMan/templates-user/my-status-dashboard.xml
```
