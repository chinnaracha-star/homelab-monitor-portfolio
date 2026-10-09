# Docker

Images are built from the repository root.

| File | Role |
| --- | --- |
| `Dockerfile.api` | Python 3.12 slim API, non-root user `homelab` (uid 10001) |
| `Dockerfile.dashboard` | Vite build, then nginx 1.27 alpine serving the SPA |
| `docker-compose.yml` | Local production-like stack |
| `docker-compose.prod.yml` | Loopback HTTP, read-only API rootfs, log rotation |
| `.dockerignore` | Keeps secrets, tests, and local data out of the build context |

## Layout

```text
browser --> dashboard:8080 (nginx, read-only)
              |  /
              |  static SPA
              |
              +--> /api/*  --> api:8000
              +--> /ws/*   --> api:8000 /api/v1/ws/*
              +--> /health --> api:8000 /health

api volumes
  homelab-data  -> /var/lib/homelab-monitor   (SQLite)
  homelab-logs  -> /var/log/homelab-monitor   (api.jsonl)
```

Only the dashboard port is published. The dashboard and API share an internal
`backend` network. The API additionally joins `egress` so notification providers
and monitored services remain reachable; nginx has no outbound network beyond
the API network.

## Run

```bash
cp .env.production.example .env
# set HOMELAB_REGISTRATION_KEY, HOMELAB_JWT_SECRET, and HOMELAB_BOOTSTRAP_ADMIN_PASSWORD
docker compose up -d --build
curl -fsS http://127.0.0.1:8080/health
curl -fsS http://127.0.0.1:8080/

If host port 8080 is already in use, set `HOMELAB_DASHBOARD_PORT` (for example
`18081`) when running Compose.
```

Stop:

```bash
docker compose down
```

Data remains in the named volumes until `docker compose down -v`.

## Production overlay

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

Differences:

- dashboard published as `127.0.0.1:80`
- API container root filesystem is read-only (data and log volumes stay writable)
- json-file log rotation
- `cap_drop: ALL` and `no-new-privileges` on both services
- explicit internal nginx-to-API network; API-only egress network

## Security defaults

- API process uid 10001
- dashboard process is `nginx` (non-root)
- dashboard `read_only: true` with tmpfs for nginx state
- `restart: unless-stopped`
- healthchecks on `/health` (API) and `/` (dashboard)

## Build only

```bash
docker build -f Dockerfile.api -t homelab-monitor-api:local .
docker build -f Dockerfile.dashboard -t homelab-monitor-dashboard:local .
```

The dashboard image bakes `VITE_API_BASE_URL=/api/v1` so the browser talks to
the same origin. Do not bake an absolute `http://api:8000` URL; that hostname
is not reachable from the browser.
