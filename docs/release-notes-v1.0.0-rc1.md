# Release notes — v1.0.0-rc1

**Version:** `1.0.0-rc1`  
**Date:** 2026-09-10  
**Status:** Release candidate for a trusted HomeLab LAN (HTTPS or Tailscale Serve in front of loopback).

## Highlights

- End-to-end monitoring: Ubuntu agents, SQLite history, alert engine, React dashboard
- Docker Compose deployment with healthchecks, non-root images, and loopback publish
- JWT login with admin / operator / viewer RBAC (passwords from bootstrap env vars)
- Telegram alert and recovery messages via a background worker (queue, batch, retry)
- Notification Center with delivery metrics, history table, search, and filters
- Read-only Photo Services and QNAP/NAS infrastructure snapshots
- Analytics, capacity, trends, incidents, and alert timeline

## Breaking changes

- **No default dashboard passwords.** Set `HOMELAB_BOOTSTRAP_ADMIN_PASSWORD` before
  the first production start. Optional operator/viewer bootstrap passwords create
  those accounts. `admin123` / `operator123` / `viewer123` are rejected in
  production.
- Fresh databases no longer insert users inside migration `0003`. Existing
  databases keep their rows; production still refuses known insecure hashes until
  a bootstrap password rotates them.
- Live alert delivery is **Telegram-only**. Settings UI may still mention other
  channels; they are not on the alert engine path in this RC.

## Known limitations

Full list: [known-limitations.md](known-limitations.md).

- Notification queue is in-memory (lost on API restart)
- Delivery history and metrics reset after restart (ring buffer, not SQLite)
- Discord, Slack, and email are not implemented on the live alert path
- `HOMELAB_INFRASTRUCTURE_MOCK` defaults to `true`
- No official SQLite volume backup procedure in this RC
- OpenAPI `/docs` remains enabled

## Future roadmap (v1.1)

- Persist the notification queue and delivery history
- Wire Discord, Slack, and email on the live alert path (or remove the UI)
- SQLite backup/restore runbook
- Test coverage gate
- Optional disable of `/docs` in production

## Upgrade notes

1. Copy `.env.production.example` to `.env` and set secrets plus
   `HOMELAB_BOOTSTRAP_ADMIN_PASSWORD`.
2. Rebuild API and dashboard images.
3. Confirm `GET /health` reports `version` `1.0.0-rc1`.
4. Enable Telegram with `HOMELAB_TELEGRAM_ENABLED=true` and a bot token/chat ID.

See also [CHANGELOG.md](../CHANGELOG.md) and the [README](../README.md).
