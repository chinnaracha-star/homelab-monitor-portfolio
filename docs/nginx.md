# Nginx

Nginx serves the React dashboard and reverse-proxies the FastAPI process.

## Paths

| Browser path | Upstream |
| --- | --- |
| `/` | SPA (`try_files` → `index.html`) |
| `/assets/` | Hashed Vite files, `Cache-Control: immutable` for one year |
| `/api/` | FastAPI (`/api/v1/...`) with standard HTTP proxy settings |
| `/api/v1/ws/` | FastAPI WebSocket endpoint with explicit upgrade handling |
| `/ws/` | FastAPI `/api/v1/ws/` |
| `/health` | FastAPI `/health` |

The dashboard WebSocket client uses `/api/v1/ws/dashboard`. That path and the
backward-compatible `/ws/` alias have dedicated upgrade handling, bounded idle
timeouts, disabled response buffering, and upstream TCP keepalive. Ordinary
REST requests do not carry WebSocket upgrade headers.

## Files

| File | Use |
| --- | --- |
| `deploy/nginx/nginx.conf` | Full nginx config inside `Dockerfile.dashboard` (listen 8080, upstream `api:8000`) |
| `deploy/nginx/nginx.host.conf` | Full nginx config for systemd (`/etc/homelab-monitor/nginx.conf`) |
| `deploy/nginx/homelab-monitor.conf` | Server block for host installs (upstream `127.0.0.1:8000`) |

## Compression and cache

- `gzip` is on for text, JavaScript, JSON, CSS, SVG, and web manifests
- `/assets/` is cached for 31536000 seconds
- `index.html` and SPA routes use `no-store`
- PWA manifests and common service-worker entry filenames use `no-store`

## Response security

Both Docker and systemd nginx configurations send a conservative same-origin
Content Security Policy plus `X-Content-Type-Options`, `X-Frame-Options`,
`Referrer-Policy`, and `Permissions-Policy`. TLS and HSTS remain owned by the
existing Tailscale HTTPS endpoint; nginx continues to listen on loopback HTTP
and does not attempt to terminate TLS.

## systemd

```bash
sudo cp deploy/nginx/nginx.host.conf /etc/homelab-monitor/nginx.conf
sudo cp deploy/nginx/homelab-monitor.conf /etc/homelab-monitor/homelab-monitor.conf
sudo nginx -c /etc/homelab-monitor/nginx.conf -t
sudo systemctl enable --now homelab-monitor-dashboard.service
```

The production Compose overlay binds nginx to `127.0.0.1:80`. Keep the existing
Tailscale HTTPS endpoint forwarding to that loopback listener; do not publish
the listener directly to the LAN or internet.
