# Security review (Sprint 12.7)

No auth, JWT, or RBAC code was changed in this freeze.

## Checklist

| Control | Status |
| --- | --- |
| Dashboard JWT (`HOMELAB_JWT_SECRET` min 32) | Present |
| Role checks `require_roles` | Present on routers |
| Agent token SHA-256 at rest | Present |
| Registration key separate from JWT | Present |
| Telegram token only in env | Present |
| Plugin config JSON no secrets (convention) | Present |
| SQLite backups hashed | Present |
| Foreign keys + WAL | Present |
| Plugin manifest signing | Absent |
| Knowledge CSV restricted to admin | Absent (viewers can export) |
| GET health without auth | Intentional for Compose healthcheck |
| Operations docker restart | Admin-only operations |

## Secrets

- `.env` is gitignored; `.env.example` documents `HOMELAB_*` and `TELEGRAM_*`.
- `.env.example` currently contains a non-empty `HOMELAB_BOOTSTRAP_ADMIN_PASSWORD` sample. Treat as a **credential hygiene** issue for copies of the repo.
- Bootstrap passwords in production must not be the documented `admin123` defaults (code already rejects weak defaults in production).

## Docker

API runs as uid 10001. Photo mounts are read-only. Docker socket exposure is operator-configured (`HOMELAB_DOCKER_URL`). Operations Center can `docker restart` containers when the socket is available.

## Plugin loading

Local JSON only. A writable `plugins/` directory on the API image would allow an operator to drop a manifest that the manager will load. Capabilities are labels, not sandbox permissions.

## Backup / export

- Backup files live on the data volume; restore is an operator procedure (`docs/restore.md`).
- `GET /api/v1/knowledge/export` returns CSV of alert messages, photo filenames, Telegram errors to any logged-in viewer.

## Risk assessment

| ID | Risk | Severity | Notes |
| --- | --- | --- | --- |
| S1 | Viewer CSV export of operational history | Medium | Knowledge Center product choice |
| S2 | Unsigned plugin manifests | Medium | Single-operator homelab assumption |
| S3 | Plugin stop does not stop workers | Medium | Misleading control plane |
| S4 | GET `/system/health` writes snapshots | Low | Integrity of audit vs cache |
| S5 | Example bootstrap password in `.env.example` | Low | Hygiene |
| S6 | JWT in WebSocket query string | Low | Already documented in realtime.md |
| S7 | SQLite file permissions on volume | Low | depends on host umask |

**Critical:** none identified for a single-tenant homelab. Multi-tenant enterprise would elevate S1–S3.
