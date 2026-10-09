# Architecture

## Version 1 boundary

HomeLab Monitor Toolkit uses an agent-server architecture. Python agents collect
host-local information while the central server owns persistence, policy,
history, alert transitions, Telegram delivery, and the dashboard.

```text
Ubuntu host                         Central server
┌────────────────────┐             ┌───────────────────────────┐
│ Python CLI/agent   │ HTTPS POST  │ FastAPI                   │
│ System checks      ├────────────►│ Authentication            │
│ Docker checks      │             │ Config service            │
│ Immich checks      │◄────────────┤ Metrics and health score  │
│ QNAP adapter       │  Control    │ Alerts and Telegram       │
└────────────────────┘  response   │ SQLite and history        │
                                   │ React dashboard (REST+WS) │
                                   └───────────────────────────┘
```

## Communication model

Agents initiate outbound HTTPS requests every 60 seconds by default. The server
does not initiate connections to agents, and agents expose no network listener.
This works across normal LAN firewalls and avoids distributing TLS server
credentials to every monitored host.

Each accepted report response includes:

- next reporting interval
- current configuration revision and changed configuration
- minimum and latest supported agent versions
- reserved command metadata

Agent auto-update is not part of version 1.

## Dashboard realtime

The React dashboard still reads REST endpoints. After login it also opens
`GET /api/v1/ws/dashboard` with the dashboard JWT. The API broadcasts compact
events when a check-in succeeds, a report is accepted, an alert changes, or an
agent goes online or offline. The dashboard refetches the existing REST
resources instead of receiving full payloads on the socket.

Polling every 30 seconds remains as a fallback while the socket is connecting
or disconnected. Details are in [realtime.md](realtime.md).

Sprint 2 sends a full system snapshot each cycle. The report and buffer
interfaces preserve stable report IDs so changed-data reporting can be added
later without changing the server ingestion contract.

## Trust boundaries

- The bootstrap registration key only authorizes registration.
- Registration returns a high-entropy agent token exactly once.
- Only a SHA-256 digest of the high-entropy token is stored.
- Each subsequent agent request uses its bearer token.
- Dashboard authentication is separate from agent authentication.
- Dashboard authorization is enforced by user roles (`admin`, `operator`, `viewer`).
- Integration credentials must not be included in metric payloads or API responses.

The intended deployment boundary for version 1 is a trusted HomeLab LAN, with
optional remote access only through a private Tailscale tailnet (no public
ports). See [remote-access.md](remote-access.md). Internet-facing Funnel,
Cloudflare Tunnel, and extra reverse proxies are out of scope.

Production packaging is Docker Compose (API + dashboard nginx inside Compose)
or systemd units on Ubuntu. The dashboard container's nginx is the SPA server
and same-origin proxy for `/api` and WebSockets. Remote HTTPS is provided by
Tailscale Serve, not by publishing host ports. See [deployment.md](deployment.md).

## Persistence

SQLite is the version 1 database. Foreign keys and WAL mode are enabled. Alembic
owns schema changes. PostgreSQL is intentionally deferred until multi-site or
higher-write-volume requirements justify it.

Reports use a client-generated report ID and server-computed content hash.
Replaying the same report is safe; reusing an ID with different content is
rejected.

Each newly accepted report also writes one `metric_history` row with extracted
CPU, memory, disk, temperature, and network counters. The dashboard reads
aggregated history through `GET /api/v1/history/agents/{agent_id}` rather than
scanning full JSON payloads. See [history.md](history.md).

Named agent groups live in `agent_groups` with membership in
`agent_group_members`. Group membership is independent of agent tokens and
metric history. See [groups.md](groups.md).

Read-only photo connectors sit behind `InfrastructureService`. Immich, QuMagie,
and QNAP snapshots are aggregated for the dashboard; the existing NAS upload
path is unchanged and the API never writes photos. See
[photo-services.md](photo-services.md).

Photo Monitor polls a NAS folder for new image files, writes `photo_events`,
and sends Telegram. See [photo-monitor.md](photo-monitor.md).

A secondary QNAP TS-253 Pro is observed only as a backup destination. The
backup connector is GET-only and never starts, stops, or deletes jobs. See
[backup.md](backup.md).

The agent uses a separate local SQLite database as a bounded offline queue. It
stores complete report payloads before retry, survives agent restarts, sends the
oldest report first, and keeps the original report ID. This database is not the
central metrics database.

## Alert state

The API evaluates accepted system reports through a metric evaluator and
database-backed alert rules, then the existing alert engine opens, updates, or
resolves rows in `alerts`. Event kinds remain `cpu_high`, `memory_high`,
`disk_high`, `temperature_high`, and `agent_offline`. See
[alert-rules.md](alert-rules.md).

A periodic server task compares each agent's last contact with offline rules
(or the environment offline threshold when no rules exist) and persists an
`agent_offline` alert. A successful check-in or report resolves that state.
Alert evaluation and report persistence share the same database transaction.

New and reopened alert transitions are enqueued for Telegram after alert
state commits. Repeated active observations do not produce duplicate messages,
and delivery failures do not roll back reports or alert state. See
[notifications.md](notifications.md) and
[known-limitations.md](known-limitations.md).
