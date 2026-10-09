# Known limitations (v1.0.0-rc3)

Accepted gaps for this release candidate. Planned for **v1.1** unless noted.

## Notifications

- **Queue is in-memory.** Pending Telegram jobs disappear if the API process
  restarts.
- **Delivery history resets after restart.** `GET /api/v1/notifications/delivery-history`
  and metrics use a process-local ring buffer (max 1000 stored, 100 returned).
- **Discord, Slack, and email are not on the live alert path.** The alert engine
  enqueues Telegram only.
- **Telegram uses environment settings** (`TELEGRAM_*` / `HOMELAB_TELEGRAM_*`).

## Data and operations

- **SQLite** is the only supported database. Gzip backups and restore docs exist
  (`docs/backup.md`, `docs/restore.md`). Copies still live on the same data
  volume unless the operator copies them off-host.
- **Infrastructure mock mode** defaults to `true`.
- **OpenAPI** stays enabled in production images.
- **Compose** has no CPU/memory limits. JSON log rotation is in
  `docker-compose.prod.yml`.
- **Restart Dashboard/API from Operations Center** needs Docker CLI (and often
  the socket) inside the API container; otherwise the action fails and is logged.

## Product scope deferred

UPS monitoring, agent auto-update, PostgreSQL, Prometheus/Grafana, Kubernetes,
and writing/controlling NAS jobs remain out of scope.

## Related docs

- [Release notes rc2](release-notes-v1.0.0-rc2.md)
- [RC2 checklist](rc2-checklist.md)
- [Notifications](notifications.md)
- [Backup](backup.md)
- [Performance](performance.md)
- [Operations Center](operations-center.md)
