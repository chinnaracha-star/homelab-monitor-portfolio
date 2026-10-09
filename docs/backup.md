# Backup

HomeLab Monitor treats a secondary QNAP **TS-253 Pro** as a read-only backup
target. The dashboard never starts, stops, deletes, moves, or uploads backup
jobs. Hybrid Backup / replication status is observed through `BackupConnector`
behind `InfrastructureService`.

```text
Phone → Qfile Pro → QNAP TS-453Be → Shared Folder → Immich / QuMagie
InfrastructureService → Backup (TS-253 Pro) → GET /api/v1/backup → Dashboard
```

`GET /api/v1/backup` requires a dashboard JWT (admin, operator, viewer). Mock
mode is the default and shows a TS-253 Pro job with Healthy status, Last Backup
02:00, 18 minute duration, ~1.8 TB size, Running 43% progress, and Backup
History (Yesterday Success, Today Running, Last Week Failed). Live mode issues
GET `{HOMELAB_BACKUP_URL}/api/backup/status` only and records snapshots for
history windows.

Realtime uses existing `overview_updated` with `reason=backup_updated`.

# Backup and restore (application data)

Scripts live in `scripts/`. They copy SQLite, logs, and configuration. They do
not dump running container filesystems.

## Application backup

```bash
./scripts/backup.sh
```

The script prints the backup directory (`backups/<UTC-stamp>/` by default).

Layout:

```text
<stamp>/
  MANIFEST
  sqlite/homelab-monitor.db
  logs/logs.tar.gz
  config/config.tar.gz
```

SQLite is copied with `sqlite3 .backup` when `sqlite3` is installed so WAL
mode does not leave a torn file. Otherwise the `.db` (and WAL/SHM if present)
is copied.

Override paths:

| Variable | Meaning |
| --- | --- |
| `HOMELAB_BACKUP_DIR` | Parent directory for timestamped backups |
| `HOMELAB_BACKUP_DB` | Path to `homelab-monitor.db` |
| `HOMELAB_BACKUP_LOG_DIR` | Directory to archive as logs |
| `HOMELAB_BACKUP_CONFIG` | Newline-separated extra config paths |

Docker volumes can be copied from the host after locating the volume mount, or
by running the script inside a helper container that mounts `homelab-data` and
`homelab-logs`.

Example from the Compose host:

```bash
DB="$(docker volume inspect homelab-monitor_homelab-data --format '{{.Mountpoint}}')/homelab-monitor.db"
LOG="$(docker volume inspect homelab-monitor_homelab-logs --format '{{.Mountpoint}}')"
sudo HOMELAB_BACKUP_DB="$DB" HOMELAB_BACKUP_LOG_DIR="$LOG" ./scripts/backup.sh
```

## Restore

Stop the API first so SQLite is not rewritten during the copy.

```bash
docker compose stop api
# or: sudo systemctl stop homelab-monitor-api.service

./scripts/restore.sh backups/20260101T000000Z

docker compose start api
```

`HOMELAB_BACKUP_DB` and `HOMELAB_BACKUP_LOG_DIR` select restore destinations.
Set `HOMELAB_RESTORE_CONFIG_DIR` to unpack `config.tar.gz` automatically.

After restore, start the API so Alembic can apply any newer revisions
(`alembic upgrade head` runs in the API entrypoint).

# Automated SQLite gzip backups

The API process copies SQLite with the Python backup API, compresses it to
`.sqlite3.gz`, verifies integrity, then applies retention. This is independent
of the TS-253 Pro observer. PostgreSQL is not used.

| Item | Default |
| --- | --- |
| Schedule | Every day 02:00 `Asia/Bangkok` |
| Path | `/var/lib/homelab-monitor/backups` |
| Filename | `homelab-monitor-YYYY-MM-DD-HHMMSS.sqlite3.gz` |
| Retention | 7 daily, 4 weekly (Sundays), 6 monthly |
| Telegram | Reuses `TelegramNotifier` (`Backup Complete` / `Backup Failed`) |

Configuration (`.env` / Compose):

```bash
HOMELAB_BACKUP_ENABLED=true
HOMELAB_BACKUP_PATH=/var/lib/homelab-monitor/backups
HOMELAB_BACKUP_RETENTION_DAILY=7
HOMELAB_BACKUP_RETENTION_WEEKLY=4
HOMELAB_BACKUP_RETENTION_MONTHLY=6
HOMELAB_BACKUP_TIME=02:00
HOMELAB_BACKUP_TIMEZONE=Asia/Bangkok
```

`HOMELAB_BACKUP_URL` remains the QNAP observer URL and is not the SQLite path.

Verification after each backup: SQLite `PRAGMA integrity_check`, gzip decode,
non-zero file size, and timestamp in the filename. Failed archives are renamed
`*.failed`. Retention never deletes previous good copies when verification
fails.

The Backup dashboard page adds Latest Backup, Backup Status, Backup Size, Next
Scheduled Backup, Retention Summary, and Last Verification from `GET /api/v1/backup`
field `sqlite` (additive; existing QNAP fields are unchanged). Restore is
manual — see `docs/restore.md`.

## Operator checklist

- [ ] `HOMELAB_BACKUP_ENABLED=true` in production `.env`
- [ ] `homelab-data` volume includes `/var/lib/homelab-monitor/backups`
- [ ] Telegram bot token and chat ID are set if operators want backup messages
- [ ] Confirm one gzip file appears after 02:00 Bangkok (or run a one-shot backup)
- [ ] Confirm the Backup page shows integrity PASS
- [ ] Confirm failed backups do not remove older `.sqlite3.gz` files
- [ ] Keep `docs/restore.md` reachable for the on-call operator
