# Changelog

All notable changes to HomeLab Monitor Toolkit are documented here.

## [1.0.0-rc3] — 2026-09-23

Release candidate after Phase 12. Agent protocol remains `0.1.0`. SQLite schema is unchanged.

### Added

- Phase 12 read routes for plugins, assistant briefing, knowledge, and system topology
- Photo Monitor startup self-check and additive `photo_monitor` fields on `GET /health`

### Changed

- Package, API, and dashboard version strings report `1.0.0-rc3`
- New photos created after process start are not swallowed by an unprimed baseline
- Current month folders are scanned before the full share walk
- Photo Telegram text includes the source, and a failed photo send falls back to a text message

## [1.0.0-rc2] — 2026-09-21

Release candidate 2 baseline after Phase 11.1–11.5. Agent protocol remains `0.1.0`.

### Added

- Sprint 11.1: scheduled gzip SQLite backups, retention, verification, Telegram backup notices, restore/DR docs
- Sprint 11.2: Production Health last-event cards and extra dependency checks
- Sprint 11.3: Agents fleet health, group labels, derived OS/NAS tags (no protocol change)
- Sprint 11.4: performance and reliability scores with 24h/7d/30d sample windows
- Sprint 11.5: Operations Center on Production Health with confirmation and history
- `PROJECT_STATUS.md`, RC2 checklist, performance and operations docs

### Changed

- Package/API/dashboard version strings report `1.0.0-rc2`
- Developer Mission Control phase/sprint metadata tracks Phase 11
- Known limitations: SQLite backup runbook now exists

### 10.3.x (included in rc1 lineage)

- 10.3.3 production Compose/env alignment
- 10.3.4 hardening (PWA cache headers, Telegram-safe dashboard URLs)
- 10.3.5 RC1 certification documentation

[1.0.0-rc3]: docs/release-notes-v1.0.0-rc3.md
[1.0.0-rc2]: docs/release-notes-v1.0.0-rc2.md
[1.0.0-rc1]: docs/release-notes-v1.0.0-rc1.md

## [1.0.0-rc1] — 2026-09-10

First release candidate. Package, API, and dashboard version strings report
`1.0.0-rc1`. Agent protocol compatibility remains `0.1.0` unless operators raise
`HOMELAB_MINIMUM_AGENT_VERSION`.

### Added

- Ubuntu agent with outbound HTTPS reports, local retry queue, and systemd units
- FastAPI control plane with SQLite history, JWT dashboard auth, and RBAC
- React dashboard (Overview, Agents, Groups, Alerts, Alert Rules, Users, Settings)
- Analytics, trends, capacity, insights, and predictions pages
- Alert timeline, incidents, Notification Center, and production health
- Photo Services (Immich, QuMagie, QNAP storage) and Backup observer pages
- Configurable alert rules and alert stability windows
- Telegram delivery worker with in-memory queue, 10s batching, three retries
- Notification delivery history and metrics APIs (process memory)
- Docker Compose stack (API + nginx dashboard), PWA, Tailscale Serve notes
- Bootstrap passwords via `HOMELAB_BOOTSTRAP_*_PASSWORD` (no shipped defaults)

### Changed

- Alert engine enqueues Telegram jobs instead of calling the multi-channel
  dispatcher on the live path
- Notification Center loads delivery history and metrics from dedicated endpoints
- Production Compose uses `backend` plus `egress` networks (API egress, dashboard
  internal to the API)
- README and operator docs describe v1.0.0-rc1 instead of early Phase 8 status

### Fixed

- Reverse-proxy compose test matches the backend + egress layout
- Production no longer seeds `admin123` / `operator123` / `viewer123`
- Version strings aligned across pyproject, API health/OpenAPI, and dashboard PWA

### Security

- Dashboard users must be created from environment bootstrap passwords
- Known insecure default passwords are rejected in `production`
- JWT secret and registration key remain required; examples are placeholders only
- Dashboard published on loopback; API is not published on the host

### Known Limitations

See [docs/known-limitations.md](docs/known-limitations.md). Summary: in-memory
notification queue and delivery history; Discord/Slack/email not on the live
alert path; SQLite gzip backups exist (same volume); infrastructure mock
defaults to on.

[1.0.0-rc1]: docs/release-notes-v1.0.0-rc1.md
