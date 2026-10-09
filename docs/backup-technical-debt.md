# Backup technical debt

Recorded in Sprint 13.10. Not fixed here.

## TD-BACKUP-001 — One HTTP body, two domains

- **Description:** `GET /api/v1/backup` returns TS-253 fields and a nested `sqlite` object.
- **Current behavior:** `backup_status_from_snapshot` always attaches `sqlite_status_payload` when settings are present.
- **Severity:** Low.
- **Impact:** A connector outage can fail the whole response even though the SQLite status file is local.
- **Not fixed now:** Splitting the body changes the JSON contract.
- **Later:** An additive endpoint, or a documented optional `sqlite` when the connector is down, under a contract review.
- **Risk:** High if current clients stop reading `destination.model`.

## TD-BACKUP-002 — Shared name backup

- **Description:** Settings, the connector, the job, and analytics routes all say backup.
- **Current behavior:** `backup_url` is the NAS connector. `backup_path` is the gzip directory.
- **Severity:** Low.
- **Impact:** A reader can point retention at the wrong path if the names are confused. The code does not do that today.
- **Not fixed now:** Renaming settings would break deployment env vars.
- **Later:** Aliases only, after ops agrees.
- **Risk:** Medium for deploys if keys are renamed in place.

## TD-BACKUP-003 — Analytics backup is infrastructure history

- **Description:** `/analytics/backup`, trends, capacity, insights, and predictions use ops snapshots from the connector, not gzip files.
- **Current behavior:** Those pages describe replication history.
- **Severity:** Low.
- **Impact:** They do not show SQLite copy success.
- **Not fixed now:** Changing the series would change dashboard numbers.
- **Later:** A separate application-backup series if the product wants it.
- **Risk:** Medium for charts.

## TD-BACKUP-004 — Scheduler still owns the loop

- **Description:** `run_sqlite_backup` both waits and executes.
- **Current behavior:** Job registry metadata matches the factory. The engine does not start it.
- **Severity:** Low.
- **Impact:** None until scheduler migration.
- **Not fixed now:** That is the next sprint's boundary, not this one.
- **Later:** Call the same function from the job runner.
- **Risk:** Medium if the sleep and the gzip step are rewritten together.
