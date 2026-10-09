# HomeLab Monitor

## Overview

A small lab fails in more than one place at a time. An agent stops checking in, a disk fills, a scheduled backup does not finish, or a queued notification is never delivered. HomeLab Monitor is a self-hosted API and dashboard that collect those signals, store history in SQLite, and show alerts to signed-in users.

This repository is a portfolio snapshot of that application. It is meant to show the design, tests, and local setup. It is not a public demo of a running lab.

## Key Features

These features are in the release this snapshot is based on:

- Agent check-in, offline detection, and alert rules
- A notification queue, with Telegram delivery left off until you configure your own bot
- Read-only infrastructure status, using mock snapshots unless you point it at services you run
- Photo-folder watching for directories you mount yourself
- Scheduled SQLite backups written by the application
- JWT login with admin, operator, and viewer roles
- A REST API and an authenticated dashboard WebSocket
- Docker Compose for the API and dashboard
- GitHub Actions for API tests, dashboard tests, and image builds

## Tech Stack

- Frontend: React, TypeScript, Vite
- Backend: Python, FastAPI, SQLAlchemy
- Database: SQLite
- Infrastructure: Docker Compose
- Testing: pytest, Vitest

Alembic manages schema changes. The dashboard also uses React Router and Recharts. API style checks use Ruff. Dashboard lint uses oxlint.

## System Architecture

The browser loads the React dashboard. The dashboard calls FastAPI over HTTP and opens a WebSocket for live events. FastAPI stores data in SQLite and runs background jobs in the same process. Job results feed monitoring state and the notification queue.

See [docs/portfolio-architecture.md](docs/portfolio-architecture.md).

## Screenshots

Screenshots are not included. This snapshot was not exercised as a click-through demo, and production screens were not copied.

| Screen | File |
|---|---|
| Sign-in | `docs/screenshots/sign-in.png` |
| Dashboard overview | `docs/screenshots/overview.png` |
| Alerts | `docs/screenshots/alerts.png` |

Add those images only from a local run that uses your own placeholder configuration.

## Getting Started

External NAS, Immich, QuMagie, Telegram, and Tailscale are optional. Infrastructure connectors start in mock mode (`HOMELAB_INFRASTRUCTURE_MOCK=true`), so the API can boot without them.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
# Replace every change-me and replace-with value before starting the API.
mkdir -p data
uvicorn homelab_monitor.main:app --app-dir api/src --host 127.0.0.1 --port 8000
```

Dashboard, in a second terminal:

```bash
cd dashboard
npm ci
npm run dev
```

The Vite dev server proxies API calls. Docker Compose publishes the dashboard on localhost. A photo directory is needed only if you enable the photo watcher against real files.

## Configuration

Copy `.env.example` to `.env`. Do not commit `.env`.

| Variable | Purpose |
|---|---|
| `HOMELAB_DATABASE_URL` | SQLite URL, for example `sqlite:///./data/homelab-monitor.db` |
| `HOMELAB_REGISTRATION_KEY` | Agent registration secret, at least 24 characters |
| `HOMELAB_JWT_SECRET` | Signing secret, at least 32 characters |
| `HOMELAB_BOOTSTRAP_ADMIN_PASSWORD` | Password for the first admin user |
| `HOMELAB_INFRASTRUCTURE_MOCK` | `true` uses mock infrastructure snapshots |
| `HOMELAB_TELEGRAM_ENABLED` | Leave `false` until you supply your own bot settings |

Leave QNAP, Immich, QuMagie, and backup connector URLs empty unless you operate those services.

## Testing

Commands:

```bash
source .venv/bin/activate
pytest
cd dashboard && npm test
cd dashboard && npm run lint
cd dashboard && npm run build
```

API tests use temporary SQLite files. They do not open a production database.

Verified on this snapshot:

- API: 438 passed
- Dashboard: 204 passed
- Build: successful
- Lint: 6 non-blocking warnings

The lint warnings are React fast-refresh and effect notes in the dashboard. They did not fail the lint command.

## Engineering Challenges

**Real-time monitoring.** Agents check in over HTTP. The dashboard subscribes to `/api/v1/ws/dashboard` with a JWT. The API broadcasts connection, check-in, and alert events to open sockets. Viewers see updates without polling every page.

**Background scheduler jobs.** Six asyncio loops share the API process: offline monitor, infrastructure monitor, Telegram reports, notification worker, photo watcher, and SQLite backup. Each loop finishes one pass before it sleeps. Loops can overlap with each other. There is no separate worker service in this release.

**SQLite concurrency.** SQLAlchemy opens SQLite with `pool_pre_ping`. Each connection sets `PRAGMA busy_timeout=8000`, so a writer waits briefly instead of failing on the first lock. Request handlers and jobs still share one database file. A long job checkout can delay other checkouts.

**Production reliability investigation.** A production incident showed the API health check failing while the SQLAlchemy connection pool waited on checkouts. The process recovered without a restart. This snapshot keeps that behavior: pool size and the health probe are unchanged. A later diagnostic that records which operation holds a connection was written and tested, and it is not in this tree. That diagnostic only logs. It does not enlarge the pool or remove the wait. The underlying checkout pressure is an open reliability issue, not a fix shipped here.

## Security

Production credentials, personal hostnames, and private storage paths are not in this snapshot. `.env.example` uses placeholder secrets. Real tokens, NAS passwords, and chat IDs belong only in an untracked `.env`. Photo paths here are generic (`/data/photos`). The photo watcher and backup job can write metadata and backup files when you enable them, so review `.env` before pointing them at real directories.

## Project Status

The public snapshot follows Production R1, the release that is deployed. Configuration that identified a private network or storage layout has been replaced with examples. Private deployment notes are omitted. Unreleased work, including AI analysis and the pool-timeout diagnostic, is not included. A browser demo was not run while preparing this tree.
