# Backup consolidation plan

**Sprint:** 13.2  
**Status:** Plan only. No backup code is added.

## Current split

Two features share the name Backup:

| Piece | Behavior |
| --- | --- |
| `sqlite_backup.py` | Gzip copy of the HomeLab SQLite file, retention, its own scheduler, Telegram text on result |
| `connectors/backup.py` | Read-only status for the TS-253 Pro story. Sample summary when `backup_url` is empty |
| `GET /api/v1/backup` | Maps the connector snapshot to the dashboard Backup page. History writes `ops_snapshots` and still returns status when that write fails |
| Operations `restart_scheduler` | Restarts the gzip loop only |

The dashboard can show connector sample data while the gzip job is the one that actually writes files. Those are different backups.

## Future Backup Service

```text
BackupService
    ├── SqliteBackupJob     (today's gzip loop)
    ├── StatusConnector     (today's read-only TS-253 view)
    └── Notifier            (later, the notification facade)
```

The service does not merge the two meanings. The page keeps showing connector status. A later RFC can add a second field for the gzip job without removing the current fields.

## Restore path

Restore stays a documented operator action, not an API in this plan.

1. Stop the API so no writer holds the SQLite file.
2. Copy the chosen gzip back to the database path from `Settings`.
3. Start the API and run the existing migration head. Restore does not add a migration.
4. Confirm `GET /health` reports the database up.

The gzip job already stores files under the configured backup directory. Retention counts stay as they are until a storage RFC.

## Storage abstraction

Later, the gzip writer and the connector destination can sit behind one interface:

- `local` — current directory of gzip files
- `connector` — read-only status URL, no writes from HomeLab

The first implementation sprint, when accepted, only wraps the local writer. It does not upload to the NAS and does not change `HOMELAB_BACKUP_PATH`.

## Compatibility strategy

`GET /api/v1/backup` fields stay. The gzip schedule, retention, and Telegram backup text stay. Plugin id `backup` stays a v1 adapter and does not become the job.
