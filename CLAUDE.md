# CLAUDE.md

## What This Is

A self-contained Docker container that displays real-time Unraid server status on a tablet-optimised dashboard. Four rotating panels (System, Media, UPS, Network) pull data from local APIs and present it in an Apple-inspired dark OLED aesthetic. Runs on Unraid at `192.168.1.200:9090` on `docker-media-network`.

## Architecture

```
┌──────────── status-dashboard container (:9090) ─────────────┐
│                                                              │
│   Python/Flask backend                                       │
│   ├── collectors/ (one per data source, each returns dict)   │
│   ├── cache.py (TTL cache, returns stale data on failure)    │
│   ├── config.py (all config from env vars)                   │
│   └── app.py (Flask routes + static file serving)            │
│                                                              │
│   Frontend (single HTML file, inline CSS+JS)                 │
│   └── static/dashboard.html                                  │
│                                                              │
│   Routes:                                                    │
│     GET /           → serves dashboard.html                  │
│     GET /api/system → Glances data (cached 10s)              │
│     GET /api/media  → Tautulli + qBit + Overseerr + Radarr  │
│                       + Sonarr (cached 15s)                  │
│     GET /api/ups    → HA REST API for NUT (cached 10s)       │
│     GET /api/network→ UniFi UDM SE (cached 30s)              │
│     GET /api/all    → all four combined (frontend polls this)│
│     GET /api/health → healthcheck                            │
└──────────────────────────────────────────────────────────────┘
```

### Data Flow

1. Frontend polls `GET /api/all` every 10 seconds
2. Flask checks TTL cache for each collector
3. If stale, calls the collector's `collect()` function
4. Collector makes HTTP requests to local service APIs
5. Returns normalised JSON dict
6. Cache stores result with timestamp
7. On collector failure, returns last-known-good data with `_stale: true`

### Collector Pattern

Each collector in `collectors/` exports a single `collect() -> dict` function:

```python
def collect():
    # Fetch data from one or more APIs
    # Return normalised dict (JSON-serializable)
    # Raise on total failure (cache handles graceful degradation)
    return {"key": "value", ...}
```

## File Structure

```
unraid-status-dashboard/
├── CLAUDE.md               ← this file
├── README.md               ← user-facing quickstart
├── Dockerfile              ← python:3.12-slim + gunicorn
├── docker-compose.yml      ← for systems with compose v2
├── requirements.txt        ← flask, gunicorn, gevent, requests
├── .env.example            ← template for all env vars
├── .gitignore              ← .env, __pycache__, .DS_Store
├── icon.png                ← 512x512 container icon (dashdot)
├── status-dashboard.xml    ← Unraid Docker template
├── app.py                  ← Flask app, routes, static serving
├── config.py               ← Config class, reads os.environ
├── cache.py                ← TTLCache with thread-safe get()
├── collectors/
│   ├── __init__.py
│   ├── system.py           ← Glances REST API v4
│   ├── media.py            ← Tautulli + qBittorrent + Overseerr + Radarr + Sonarr
│   ├── ups.py              ← Home Assistant REST API (NUT entities)
│   └── network.py          ← UniFi UDM SE API (API key auth)
└── static/
    └── dashboard.html      ← single-page frontend (HTML + CSS + JS, no build step)
```

## The Four Panels

### 1. System (`collectors/system.py`)
**Source:** Glances REST API at `:61208`
- CPU % (circular SVG arc gauge)
- RAM used/total with bar
- Total storage summary (TB used / TB total, colour-coded bar)
- Per-disk utilisation (Disk 1-5 + Cache NVMe, with bars)
- Temperatures (NVMe SSD, CPU Tctl, CPU Edge — colour-coded chips)
- Fans (RPM chips)
- Disk I/O throughput (read/write MB/s)

**Disk label mapping:** `/mnt/disk1` → "Disk 1", `/mnt/cache` → "Cache (NVMe)". Filters out `/mnt/user` and `/mnt/user0` virtual union mounts.

**Temp label mapping:** "Composite" → "NVMe SSD", "Tctl" → "CPU (Tctl)", "edge" → "CPU (Edge)".

### 2. Media (`collectors/media.py`)
**Sources:** Tautulli `:8181`, qBittorrent `:8080` (via gluetun), Overseerr `:5055`, Radarr `:7878`, Sonarr `:8989`

- **Library** (3-column grid with dividers):
  - Movies: count from Radarr (`hasFile` count) + storage in TB
  - Shows: count from Sonarr + episode count + storage in TB
  - Music: track count (large) from Tautulli, with "X artists · Y albums" subtitle
  - Total media storage chip
- **Active Streams:** from Tautulli `get_activity` — user, title, progress bar, state
- **Downloads:** global speed (Mbps), active count, pending Overseerr requests, top torrents with progress + ETA

**Tautulli music fields:** `count` = artists, `parent_count` = albums, `child_count` = tracks.

### 3. UPS (`collectors/ups.py`)
**Source:** Home Assistant REST API at `:8123` (Long-Lived Access Token auth)

Reads NUT integration entities:
- `sensor.ups_battery_charge` → battery %
- `sensor.ups_real_power` → watts draw
- `sensor.ups_load` → load %
- `sensor.ups_status` → Online/On Battery/Low Battery
- `sensor.ups_output_voltage` → voltage
- `sensor.ups_battery_runtime` → runtime in seconds

**Visuals:**
- SVG battery with animated fill level (colour by health state)
- Status badge (good/warning/critical)
- Power draw + headroom (550VA - current draw)
- Load bar with 0W–550VA labels
- Metrics: load %, voltage, runtime minutes

**Health derivation:** good = online + battery > 80%, warning = on battery or 50-80%, critical = low battery or < 50%.

### 4. Network (`collectors/network.py`)
**Source:** UniFi UDM SE at `192.168.1.1:443` (API key auth via `X-API-KEY` header)

Endpoints:
- `/proxy/network/api/s/{site}/stat/health` → WAN/LAN/WLAN subsystems
- `/proxy/network/api/s/{site}/stat/sta` → all connected clients

**Visuals:**
- WAN status badge (Connected/Down)
- WAN throughput (large Mbps numbers)
- Utilisation bars (% of 900 Mbps capacity, colour-coded)
- Client donut (wired vs wireless segments)
- Top 5 clients by bandwidth (name, down/up Mbps)

**Notes:** UDM SE uses `/api/auth/login` for session auth, but we use API key (`X-API-KEY` header) to avoid MFA issues. Self-signed cert: `verify=False`.

## Design System

### Philosophy

Apple-inspired dark OLED aesthetic. Pure black backgrounds for true OLED black. Minimal chrome, no borders heavier than 8% white. Typography-driven hierarchy using weight and opacity, not size differences. State communicated through colour (green/amber/red) applied sparingly. Designed for tablet in landscape, touch-first, ambient/kiosk mode.

### CSS Custom Properties (Design Tokens)

```css
:root {
  /* Backgrounds */
  --bg: #000000;                              /* Pure OLED black */
  --surface: rgba(255, 255, 255, 0.04);       /* Card background */
  --surface-raised: rgba(255, 255, 255, 0.08);/* Elevated elements (chips, stream items) */
  --border: rgba(255, 255, 255, 0.08);        /* Subtle dividers */

  /* Typography */
  --text-primary: rgba(255, 255, 255, 0.92);  /* Main content */
  --text-secondary: rgba(255, 255, 255, 0.55);/* Supporting text */
  --text-dim: rgba(255, 255, 255, 0.28);      /* Labels, subtle info */

  /* State colours (Apple system palette) */
  --green: #34C759;      /* Good / healthy / low usage */
  --amber: #FF9500;      /* Warning / moderate usage (50-80%) */
  --red: #FF3B30;        /* Critical / high usage (>80%) */
  --blue: #0A84FF;       /* Informational / active / accent */

  /* Glow variants (for box-shadow and bar glows) */
  --green-glow: rgba(52, 199, 89, 0.15);
  --amber-glow: rgba(255, 149, 0, 0.15);
  --red-glow: rgba(255, 59, 48, 0.15);
}
```

### Typography

- **Font stack:** `-apple-system, BlinkMacSystemFont, 'SF Pro Display', 'SF Pro Text', sans-serif`
- **Large values:** `font-size: 36px`, `font-weight: 200` (ultralight), `letter-spacing: -0.03em`
- **Medium values:** `font-size: 28px`, `font-weight: 300`
- **Labels:** `font-size: 10-11px`, `font-weight: 500`, `letter-spacing: 0.08-0.14em`, `text-transform: uppercase`
- **All numeric displays:** `font-variant-numeric: tabular-nums` (monospace digits for stable layout)
- **Panel titles:** `font-size: 22px`, `font-weight: 600`, `letter-spacing: -0.02em`

### Component Patterns

**Cards:**
```css
.card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 20px;
}
```

**Progress bars:**
```css
.bar-track { height: 6px; background: rgba(255,255,255,0.06); border-radius: 3px; }
.bar-fill { border-radius: 3px; transition: width 1s ease, background-color 0.6s ease; }
/* Apply .green/.amber/.red class based on stateColor(percent) */
```

**Chips (temp/fan/info badges):**
```css
.chip {
  padding: 6px 12px;
  background: var(--surface-raised);
  border-radius: 20px;
  font-size: 12px;
  color: var(--text-secondary);
}
```

**Status badges:**
```css
.status-badge {
  padding: 6px 14px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 500;
}
.status-badge.good { background: rgba(52,199,89,0.12); color: var(--green); }
.status-badge.warning { background: rgba(255,149,0,0.12); color: var(--amber); }
.status-badge.critical { background: rgba(255,59,48,0.12); color: var(--red); }
```

**Circular gauge (CPU):**
- SVG circle with `stroke-dasharray` and `stroke-dashoffset` animation
- Radius 42, circumference = 2π×42 = 263.9
- Offset = circumference × (1 - percent/100)
- Stroke colour from `stateColorVar(percent)`

**Donut chart (clients):**
- SVG circles with `stroke-dasharray` for segment lengths
- Circumference = 2π×40 = 251.3
- Wired segment: dasharray = `${wiredLen} ${circumference}`
- Wireless: dasharray + dashoffset to start after wired segment

**Battery (UPS):**
- SVG rect with animated `height` and `y` attributes
- Max fill height: 72px, fillY = 10 + (72 - fillHeight)
- Fill colour from health state

### State Colour Logic

```javascript
function stateColor(percent) {
  if (percent >= 80) return 'red';
  if (percent >= 50) return 'amber';
  return 'green';
}
```

Applied to: CPU gauge, RAM bar, disk bars, storage total bar, UPS load bar, WAN utilisation bars, temperature chips (>75°C red, >55°C amber, else green).

### Transitions & Animation

- **Panel transitions:** `opacity 0.5s ease, transform 0.5s ease` with `translateX(±40px)`
- **Bar fills:** `width 1s ease, background-color 0.6s ease`
- **Gauge strokes:** `stroke-dashoffset 1s ease, stroke 0.6s ease`
- **Battery fill:** `height 1s ease, fill 0.6s ease`
- **All transitions are CSS-only** — no JS animation libraries

### Navigation

- **Auto-rotate:** 30s interval, advances with left transition
- **Manual nav:** Dot indicators (44px touch targets), tap to jump
- **Swipe:** touchstart/touchend, >50px horizontal in <400ms
- **Keyboard:** ArrowLeft/ArrowRight
- **Auto-toggle:** Circular button next to dots (blue ▶ = active, dim ⏸ = paused)
- **Timer reset:** Any manual interaction resets the 30s auto-rotate timer

### Layout Principles

- Full viewport, no scroll (panels are `position: absolute; inset: 0`)
- Panels scroll individually if content overflows (`overflow-y: auto`)
- Grid-based metric layouts (`grid-template-columns: repeat(auto-fit, minmax(120px, 1fr))`)
- Cards stack vertically with `gap: 20px`
- Panel padding: `32px 24px 80px` (bottom padding clears nav dots)

## Configuration

All config via environment variables. See `.env.example` for full list.

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `DASHBOARD_PORT` | `9090` | No | Flask listen port |
| `GLANCES_URL` | `http://192.168.1.200:61208` | No | Glances API |
| `TAUTULLI_URL` | `http://192.168.1.200:8181` | No | Tautulli |
| `TAUTULLI_API_KEY` | — | Yes | Tautulli > Settings > Web Interface |
| `QBIT_URL` | `http://192.168.1.200:8080` | No | qBit WebUI (via gluetun) |
| `QBIT_USERNAME` | `admin` | No | qBit username |
| `QBIT_PASSWORD` | — | Yes | qBit password |
| `OVERSEERR_URL` | `http://192.168.1.200:5055` | No | Overseerr |
| `OVERSEERR_API_KEY` | — | Yes | Overseerr > Settings > General |
| `RADARR_URL` | `http://192.168.1.200:7878` | No | Radarr |
| `RADARR_API_KEY` | — | Yes | Radarr > Settings > General |
| `SONARR_URL` | `http://192.168.1.200:8989` | No | Sonarr |
| `SONARR_API_KEY` | — | Yes | Sonarr > Settings > General |
| `HA_URL` | `http://192.168.1.200:8123` | No | Home Assistant |
| `HA_TOKEN` | — | Yes | HA > Profile > Security > Long-Lived Token |
| `UNIFI_URL` | `https://192.168.1.1` | No | UniFi controller |
| `UNIFI_API_KEY` | — | Yes | UDM > Settings > Admins > API Keys |
| `UNIFI_SITE` | `default` | No | UniFi site name |
| `WAN_SPEED_MBPS` | `900` | No | Line speed for utilisation % calc |
| `CACHE_TTL_SYSTEM` | `10` | No | Seconds |
| `CACHE_TTL_MEDIA` | `15` | No | Seconds |
| `CACHE_TTL_UPS` | `10` | No | Seconds |
| `CACHE_TTL_NETWORK` | `30` | No | Seconds |

## Deployment

### Build and run on Unraid

```bash
git clone https://github.com/M1dKn1gh7/unraid-status-dashboard.git /mnt/user/appdata/status-dashboard
cd /mnt/user/appdata/status-dashboard
cp .env.example .env
nano .env  # fill in API keys

docker build -t status-dashboard .
docker run -d --name=status-dashboard --net=docker-media-network --env-file=/mnt/user/appdata/status-dashboard/.env -e TZ=Europe/London -p 9090:9090 --restart=unless-stopped status-dashboard
```

### Update workflow

```bash
cd /mnt/user/appdata/status-dashboard && git pull
docker stop status-dashboard && docker rm status-dashboard
docker build -t status-dashboard .
docker run -d --name=status-dashboard --net=docker-media-network --env-file=/mnt/user/appdata/status-dashboard/.env -e TZ=Europe/London -p 9090:9090 --restart=unless-stopped status-dashboard
```

### Unraid Docker icon

Copy template to get the icon in the Docker tab:
```bash
cp status-dashboard.xml /boot/config/plugins/dockerMan/templates-user/my-status-dashboard.xml
```

### Docker network note

Container joins `docker-media-network` (172.18.0.0/16). Can reach other containers by name (e.g., `http://gluetun:8080` for qBit). For services on host network (HA, Glances, Plex), use `192.168.1.200`.

## Adding a New Panel

1. Create `collectors/newpanel.py` with a `collect()` function
2. Add config vars to `config.py`
3. Add route in `app.py`:
   ```python
   from collectors import newpanel
   @app.route("/api/newpanel")
   def api_newpanel():
       data = cache.get("newpanel", Config.CACHE_TTL_NEWPANEL, newpanel.collect)
       return jsonify(data)
   ```
4. Add to `/api/all` response dict
5. Add HTML panel in `dashboard.html` with `data-panel="4"`
6. Add nav dot: `<button class="nav-dot" data-index="4"></button>`
7. Update `PANEL_COUNT` in JS to 5
8. Add `updateNewPanel(data.newpanel)` function in JS

## Adding a New Data Source to Existing Panel

1. Add fetch function in the relevant collector (e.g., `_fetch_newsource()`)
2. Call it from `collect()` and include in return dict
3. Add HTML elements in the panel
4. Update the panel's JS updater function

## Known Quirks

- **Unraid doesn't have `docker compose`** — use `docker run` with all flags on one line (no backslash line continuations, they break in Unraid's shell)
- **UniFi MFA** — API key auth bypasses MFA. Session-based login (`/api/auth/login`) triggers MFA emails
- **qBittorrent via gluetun** — WebUI is exposed on gluetun's port 8080, not qBit's own container. From docker-media-network use `http://gluetun:8080`, from outside Docker use `192.168.1.200:8080`
- **Glances disk temps** — Glances may not report individual HDD temps. Only sensors it detects via `psutil`/`lm-sensors` appear. Current setup shows NVMe + CPU temps
- **Tautulli bandwidth** — reported in kbps by the API, divided by 1000 for Mbps display
- **HA entity names** — depend on NUT integration config. If renamed in HA, update the `ENTITIES` list in `collectors/ups.py`

## Styling Guide for Other Projects

To reuse this aesthetic in another dashboard/page:

1. Copy the `:root` CSS custom properties block
2. Use the font stack: `-apple-system, BlinkMacSystemFont, 'SF Pro Display', 'SF Pro Text', sans-serif`
3. Apply `font-variant-numeric: tabular-nums` to ALL numbers
4. Cards: `rgba(255,255,255,0.04)` background, `0.08` border, `16px` radius
5. Use weight for hierarchy: 200 (values), 500 (labels), 600 (titles)
6. Use opacity for hierarchy: 0.92 (primary), 0.55 (secondary), 0.28 (dim)
7. State colour thresholds: <50% green, 50-80% amber, >80% red
8. All transitions 0.5-1s with `ease` timing
9. Background must be `#000000` — not near-black, true black (OLED pixel-off)
10. Never use white (`#fff`) text — always use the rgba variants above
