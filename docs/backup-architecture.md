# Backup architecture

**Sprint:** 13.10  
**Status:** Domains documented. Execution is unchanged.

Application backup and infrastructure backup are separate internal domains. Public REST paths and JSON fields stay as they are.

## Purpose

SQLite gzip copies and the TS-253 connector both use the word backup. They do not share an executor. This document is the boundary for later scheduler work.

## Current architecture

Application backup lives in `sqlite_backup.py`. It copies the SQLite file, gzips it, applies retention, and notifies through `NotificationService`.

Infrastructure backup lives in `connectors/backup.py`. It reads a mock or an HTTP status payload for the TS-253 Pro target. It does not copy the application database.

`backup_status.py` places both into one `BackupStatusResponse`: connector fields at the top level, SQLite fields under `sqlite`.

## Application Backup domain

| Piece | Owner |
| --- | --- |
| Copy and gzip | `run_backup_once` |
| Filename | timestamped name in `sqlite_backup.py` |
| Directory | `backup_path` |
| Retention | `apply_retention` on that directory |
| Manual run | Operations `backup_now` |
| Schedule | `run_sqlite_backup` calls `run_backup_clock`, then `run_backup_once` |
| Enable flag | `backup_enabled` |
| Last run | JSON state beside the backup directory |
| Notification | `_notify` → `NotificationService.send_text` |

QNAP availability is not an input.

## Infrastructure Backup domain

| Piece | Owner |
| --- | --- |
| Connector | `BackupConnector` |
| Mock TS-253 summary | `_mock_summary` when infrastructure mock is on or the URL is empty |
| Live read | GET `{backup_url}/api/backup/status` |
| Snapshot history | `record_backup_snapshot` |
| API | `GET /api/v1/backup` |

The connector does not call `run_backup_once`.

## Current call graphs

```text
lifespan
    ↓
operations.factories sqlite_backup
    ↓
run_sqlite_backup
    ↓
run_backup_clock
    ↓
run_backup_once
    ↓
gzip file, retention, NotificationService.send_text

POST /api/v1/operations/backup_now/run
    ↓
run_backup_once(notify=True)

GET /api/v1/backup
    ↓
BackupConnector.collect
    ↓
backup_status_from_snapshot
    ├── TS-253 fields
    └── sqlite_status_payload
```

## Target internal architecture

```text
Backup
├── Application backup
│     sqlite_backup.py
│     retention, status file, notification
└── Infrastructure backup
      connectors/backup.py
      TS-253 status
```

`GET /api/v1/backup` may keep returning both until a later contract change. Internally they stay different functions.

## Responsibility matrix

| Responsibility | Domain | Owner |
| --- | --- | --- |
| SQLite execution, gzip, filename, directory, retention | Application | `sqlite_backup.py` |
| Manual and scheduled runs | Application | Operations and `run_sqlite_backup` |
| Backup notification text | Application | `format_backup_telegram` |
| Delivery | Frozen notification facade | `NotificationService` |
| TS-253 status | Infrastructure | `BackupConnector` |
| Combined HTTP body | Both, read model only | `backup_status.py` |
| Dashboard Backup page | Both, one screen | `BackupPage.tsx` |

## Configuration ownership

| Setting | Domain | Default | Consumer |
| --- | --- | --- | --- |
| `backup_enabled` | Application | true | scheduler loop |
| `backup_path` | Application | `/var/lib/homelab-monitor/backups` | gzip output |
| `backup_time` | Application | `02:00` | next run |
| `backup_timezone` | Application | `Asia/Bangkok` | next run |
| `backup_retention_daily` | Application | 7 | retention |
| `backup_retention_weekly` | Application | 4 | retention |
| `backup_retention_monthly` | Application | 6 | retention |
| `backup_url` | Infrastructure | empty | connector base URL |
| `infrastructure_mock` | Infrastructure | existing default | mock TS-253 payload |

Keys are not renamed. A future grouping such as `backup.application.*` would be aliases only.

## API ownership

| Method | Path | Auth | Domain |
| --- | --- | --- | --- |
| GET | `/api/v1/backup` | read | Mixed body: TS-253 plus `sqlite` |
| POST | `/api/v1/operations/backup_now/run` | admin operation | Application |
| GET | `/health` | public | No backup payload |

Analytics, trends, capacity, insights, and predictions under `/backup` read infrastructure snapshot history, not the gzip files.

## Dashboard ownership

`BackupPage` shows SQLite cards from `sqlite` and TS-253 destination fields from the same response. The overview backup card uses the TS-253 model. Labels were not changed.

## Scheduler boundary

Startup calls `operations.factories`, which starts `run_sqlite_backup`. That loop calls `run_backup_clock` for one wait. When `backup_enabled` is false that wait is 3600 seconds and then returns to the loop. Otherwise it sleeps until `backup_time` in `backup_timezone`, then calls `run_backup_once`. `run_backup_clock` is not a second loop. Cancellation during the wait raises `CancelledError` and skips the backup. Cancellation after `run_backup_once` has started can still race and is not exactly-once.

A later job engine can call `run_backup_once` or `run_sqlite_backup` without reading `backup_url`.

## Notification boundary

```text
sqlite_backup._notify
        ↓
NotificationService.send_text
        ↓
TelegramNotifier.send_text
```

Success and failure text stay in `format_backup_telegram`. There is no notification-history row and no retry. This matches the frozen notification architecture.

## Health and status semantics

`GET /health` does not report backup. `BackupStatusResponse.status` is the TS-253 job display status. `sqlite.status` is the application copy state (`idle`, `disabled`, or the last run). The shared word status is compatibility debt.

## Architecture invariants

- **INV-BACKUP-001.** Application backup and infrastructure backup are separate internal domains.
- **INV-BACKUP-002.** SQLite backup execution does not depend on TS-253 availability.
- **INV-BACKUP-003.** Infrastructure status does not start or stop SQLite backup.
- **INV-BACKUP-004.** Existing REST paths and JSON fields stay compatible.
- **INV-BACKUP-005.** Existing backup setting names stay compatible.
- **INV-BACKUP-006.** Backup notification stays on `NotificationService.send_text`.
- **INV-BACKUP-007.** The scheduler loop stays until the scheduler migration.
- **INV-BACKUP-008.** Retention deletes only files in the application backup directory.
- **INV-BACKUP-009.** A connector failure does not write the SQLite backup state file.
- **INV-BACKUP-010.** A future job runner calls the existing backup function and does not absorb QNAP details.

## Compatibility guarantees

Gzip format, filenames, directory, retention counts, enable flag, and the 02:00 Bangkok schedule are unchanged. The connector timeout and mock payload are unchanged.

## Known technical debt

See [backup-technical-debt.md](backup-technical-debt.md).

## Future migration plan

1. Keep this boundary while the scheduler starts calling `run_sqlite_backup` without moving retention or gzip code into the job engine.
2. Split the public backup response only under a new contract. Do not rename fields in place.
