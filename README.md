# Unraid Status Dashboard

A self-contained Docker container that displays real-time server status across 4 rotating panels. Designed for tablets with a dark OLED aesthetic.

## Panels

| # | Panel | Data Source | What it shows |
|---|-------|-------------|---------------|
| 1 | **System** | Glances API | CPU, RAM, disk utilisation, temperatures, fans, I/O |
| 2 | **Media** | Tautulli, qBittorrent, Overseerr | Active Plex streams, downloads, pending requests |
| 3 | **UPS** | Home Assistant (NUT) | Battery, load, power draw, runtime, voltage |
| 4 | **Network** | UniFi UDM SE | WAN status/throughput, connected clients, latency |

## Features

- Auto-rotates every 30 seconds
- Manual navigation: tap dots or swipe
- Data refreshes every 10 seconds (backend caches per-source)
- Green/amber/red state colours based on metric thresholds
- Graceful degradation: stale data indicator if a source goes down

## Quick Start

```bash
# Clone
git clone https://github.com/M1dKn1gh7/unraid-status-dashboard.git
cd unraid-status-dashboard

# Configure
cp .env.example .env
nano .env  # Fill in your API keys

# Deploy
docker build -t status-dashboard .
docker compose up -d
```

Dashboard available at `http://<your-unraid-ip>:9090`

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GLANCES_URL` | No | Glances API base (default: `http://192.168.1.200:61208`) |
| `TAUTULLI_URL` | No | Tautulli base URL (default: `http://192.168.1.200:8181`) |
| `TAUTULLI_API_KEY` | Yes | Tautulli Settings > Web Interface > API Key |
| `QBIT_URL` | No | qBittorrent WebUI (default: `http://192.168.1.200:8080`) |
| `QBIT_USERNAME` | No | qBit username (default: `admin`) |
| `QBIT_PASSWORD` | Yes | qBit WebUI password |
| `OVERSEERR_URL` | No | Overseerr base URL (default: `http://192.168.1.200:5055`) |
| `OVERSEERR_API_KEY` | Yes | Overseerr Settings > General > API Key |
| `HA_URL` | No | Home Assistant URL (default: `http://192.168.1.200:8123`) |
| `HA_TOKEN` | Yes | HA Profile > Security > Long-Lived Access Token |
| `UNIFI_URL` | No | UniFi controller (default: `https://192.168.1.1`) |
| `UNIFI_USERNAME` | Yes | UniFi local admin username |
| `UNIFI_PASSWORD` | Yes | UniFi local admin password |
| `UNIFI_SITE` | No | UniFi site (default: `default`) |
| `DASHBOARD_PORT` | No | Port to serve on (default: `9090`) |

## Architecture

```
Flask backend (Python 3.12)
├── Collectors (fetch + normalise data from each source)
├── TTL cache (prevents hammering upstream APIs)
├── REST routes (/api/system, /api/media, /api/ups, /api/network, /api/all)
└── Static serving (single-page HTML frontend)
```

## Network

The container should be on `docker-media-network` to reach other containers. If services are only accessible via host IP, the defaults work as-is.

## Updating

```bash
git pull
docker build -t status-dashboard .
docker compose up -d
```