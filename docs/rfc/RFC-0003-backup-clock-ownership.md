# RFC-0003 — Backup clock ownership

**Status:** Implemented
**Sprint:** 13.13
**Date:** 2026-09-28

Scheduler refactor phase 3 from [refactor-scheduler.md](../refactor-scheduler.md). Implemented in commit `477a355`. Natural backup production validation passed. The accepted design below is unchanged.

## Implementation

`JobExecutionWrapper` starts one `sqlite_backup` factory. That factory calls `run_sqlite_backup`, which is the lifecycle loop. Each pass calls `run_backup_clock` once. `run_backup_clock` does not contain a second infinite loop and does not call `create_task`. After the wait it calls `run_backup_once` in a thread. The registry stays six jobs. `sqlite_backup` stays one registry name and one factory.

```text
JobExecutionWrapper
    ↓
sqlite_backup
    ↓
run_sqlite_backup          (lifecycle loop)
    ↓
run_backup_clock           (one iteration)
    ↓
run_backup_once            (operation boundary)
```

`next_scheduled` keeps `candidate <= clock`. The candidate uses `backup_time` in `backup_timezone` (default `Asia/Bangkok`) with second 0 and microsecond 0. Now before the candidate stays on today. Now equal to the candidate, or later than it, selects the next day. `seconds_until_next` is `max(1.0, ...)`. Disabled backup sleeps 3600 seconds and returns to the loop. It does not stop the lifecycle, run a backup, queue a catch-up, or start a second task.

`restart_scheduler` calls `restart_background("sqlite_backup")` only. The replacement recalculates the next time. Restart alone does not call `run_backup_once`. Equality still selects the next day.

Cancel while waiting propagates and the backup does not run. Cancel after `run_backup_once` has started can still race. This is not exactly-once. No lock, ledger, or persistent queue was added.

Tests at the implementation checkpoint: 40 focused tests passed; full backend 388 passed, 0 failed, 0 skipped, with `HOMELAB_INFRASTRUCTURE_MOCK=true` and live QNAP values isolated. `ruff check`, `ruff format --check`, and `git diff --check` passed. Those suites did not exercise live QNAP.

The first Phase 13.13 API image was `sha256:ed87de5f751a0bca2690c2ad778e458c0bc051af725ed6d5afaf759fcfea487b`, tagged `homelab-monitor-api:phase13.13-477a355`. The image before that deploy was `sha256:a53e9a0b0c0b7453370eb9a33b2eef2874217c84b17a4a4ca8caccc6f8b47b36`, tagged `homelab-monitor-api:rollback-phase13.13-predeploy`. Later unrelated Telegram and dashboard work replaced the running container. The natural backup was observed on container `bee766186df8`, image `sha256:9f2518a3734436b06286d86dde11e10dc7b9d7290beea3bc3b9078124dc272f2`, started `2026-09-28T15:48:17Z`. That image is not the initial `ed87de5f` image.

Early soak at `2026-09-28T16:02:45Z`: API healthy, restart count 0, `/health` HTTP 200, database up, registry 6/6. `sqlite_backup_scheduler_started` once, then `sqlite_backup_sleep seconds=11498`, targeting `2026-09-28T19:00:00Z` (`2026-09-29 02:00` Asia/Bangkok). Deploy and restart did not run a backup immediately.

Natural hourly reports continued. First observed after that deploy: `2026-09-28 16:00:32` UTC, status `sent`. Later hours continued through `2026-09-29 02:00:44` UTC, one row per due window. Daily report `2026-09-29 01:00:31` UTC, status `sent`. Report clock is still Phase 4.

Natural backup executed once. Completion `2026-09-28T19:00:04Z`. State `created_at` `2026-09-29T02:00:00.005079+07:00`. Result `ok=True`, status `healthy`, integrity `PASS`, duration 3.51 seconds. Artifact `/var/lib/homelab-monitor/backups/homelab-monitor-2026-09-29-020000.sqlite3.gz`, 11,770,422 bytes, non-zero gzip, one file for that due time. Status metadata has integrity `PASS` and does not store `gzip_ok`. Files for 23, 24, 25, 27, and 28 September remained. The 26 September file was already absent. This run did not wipe the set and did not write a duplicate. Why 26 September is absent is not recorded here.

No `backup_telegram_failed` or `backup_telegram_unavailable`. A Telegram button log at about `19:00:03Z` sat next to completion at `19:00:04Z`. No duplicate notification was seen. This path does not write a notification-history row.

The same lifecycle then logged `sqlite_backup_sleep seconds=86396` at `2026-09-28T19:00:04.465Z`, targeting about `2026-09-29T19:00:00Z` (`2026-09-30 02:00` Asia/Bangkok). Scheduler start count stayed 1. API restart count stayed 0. No second scheduler start was required.

A single `sqlite_backup` lifecycle is inferred from registry 6/6, one factory, one scheduler-start, one natural backup, one next-day sleep, no duplicate execution, and restart count 0. Production did not dump asyncio tasks.

Photo watcher stayed up with baseline loaded. Latest scan in that check was `2026-09-29T02:41:29Z`. A natural event was `2026-09-29T01:57:03`. No stop or failure was seen around the backup. `monitor` was online at `2026-09-29 02:41:41`.

That runtime had `infrastructure_mock` true and no live QNAP address. Live QNAP continuity was not exercised. That does not change the backup-clock pass.

A separate database-lock observation was seen during soak and is outside RFC-0003 scope; it did not prevent the validated natural backup execution. Four HTTP tracebacks around `2026-09-29T01:58:13Z` reported `database is locked`. They were not in the `19:00Z` backup window. The API stayed healthy with restart count 0. Root cause was not established and was not fixed here.

## Problem

`run_sqlite_backup` in `api/src/homelab_monitor/sqlite_backup.py` owns two jobs at once. It waits, and it starts the backup.

Current wait, confirmed in source:

- `backup_enabled` false: `asyncio.sleep(3600)`, then loop.
- `backup_enabled` true: `seconds_until_next(settings)`, log `sqlite_backup_sleep`, `asyncio.sleep(delay)`, then `run_backup_once`.
- `backup_timezone` defaults to `Asia/Bangkok` in `Settings`. `next_scheduled` builds today's candidate with `backup_time` (default `02:00`), second 0 and microsecond 0, in that zone. If the candidate is less than or equal to the current clock, it moves one day forward. Now before the candidate stays on today. Now equal to the candidate, or later than it, selects the next day. The backup clock must keep this `<=` rule. It must not become `<`.
- `seconds_until_next` is at least 1 second.
- There is no cron, systemd timer, or second process.

`run_backup_once` is the operation: SQLite copy, gzip, retention, and the existing notification path. Result metadata stays in the backup state file. This RFC does not say the current loop is broken. Phase 13.13 only moves who owns the wait.

Phase 13.12 already starts one `sqlite_backup` task through `JobExecutionWrapper` and `operations.factories`. `restart_scheduler` calls `restart_background("sqlite_backup")` only.

## Non-goals

- Report clock (scheduler phase 4)
- Photo interval (scheduler phase 5)
- Broad private-loop deletion (scheduler phase 6)
- REST redesign, including backup JSON fields
- SQLite schema migration or a scheduler table
- Agent protocol `0.1.0`
- JWT or RBAC
- Dashboard redesign
- QNAP behavior
- Notification architecture or message text
- Gzip, retention, destination, or NAS backup connector
- A persistent, distributed, or external scheduler
- A message queue, Kubernetes, or a workflow engine
- AI, including any permission for AI to run or restart backups

A small compatibility wrapper may remain inside `run_sqlite_backup` if that is the smallest way to keep one loop. Phase 6 is the later cleanup, after this clock has lived through a production release.

## Contracts touched

Ownership of the wait inside the single `sqlite_backup` lifecycle job.

## Contracts explicitly preserved

- One registered name: `sqlite_backup`
- Six jobs in `default_engine()` and six factories
- One factory for `sqlite_backup`
- `JobExecutionWrapper` start, duplicate-start guard, no revival, partial-start behavior, and `stop()` from RFC-0002
- `restart_background` and Operations Center `restart_scheduler` → `restart_background("sqlite_backup")` only
- `run_backup_once` as the backup operation
- `backup_timezone`, `backup_time`, and the 3600-second disabled sleep
- No catch-up for a missed clock time
- The other five loops: `offline_monitor`, `infrastructure_monitor`, `telegram_reports`, `notification_worker`, `photo_watcher`

## Current behavior

```text
JobExecutionWrapper
    ↓
sqlite_backup factory
    ↓
run_sqlite_backup
    ├── next time and sleep
    └── run_backup_once
            ├── backup file and gzip
            ├── retention
            └── existing notification
```

`runtime_control` stores that one task. `restart_background` cancels it and creates one replacement from the same factory. The replacement calculates `seconds_until_next` again and sleeps. Restart is not itself a due backup.

If the process is down across `backup_time`, including a start at the exact candidate timestamp, the next start uses the same `<=` rule and does not replay the missed run. There is no catch-up queue. A cancel that lands in the same moment `run_backup_once` has already started is a race the current code does not make exactly-once. This RFC does not add that guarantee.

## Proposed change

Keep one lifecycle task named `sqlite_backup`. Split the wait from the operation. Do not add a second task.

```text
JobExecutionWrapper
    ↓
sqlite_backup          (still the only backup lifecycle job)
    ↓
Backup clock
    ├── next scheduled time
    ├── wait until due
    └── run_backup_once
            ├── backup file and gzip
            ├── retention
            └── existing notification
```

The clock may live in a function the existing `run_sqlite_backup` calls. It must not be a seventh registry job and must not be a hidden extra `create_task`. Old and new wait loops must not run together.

`restart_scheduler` still restarts only `sqlite_backup`:

1. Cancel the current task.
2. Create one replacement from the registered factory.
3. Recalculate `next_scheduled` from now, including the `<=` boundary. A restart whose clock equals the candidate waits until the next day. It does not treat that instant as due.
4. Wait until that time.

Restart must not call `run_backup_once` merely because restart was requested. If the task is cancelled while `run_backup_once` is already inside the thread, the current race remains. Tests should cover a deterministic cancel-during-wait case. They should not claim transactional exactly-once.

Disabled backup stays `sleep(3600)` and continue. No new disabled policy.

No scheduler table, cron row, execution queue, or distributed lock. Backup result JSON stays where it is.

Job Engine still does not own gzip, retention, file creation, notification text, or the NAS connector. RFC-0002 failure rules stay: no `TaskGroup`, no retry supervisor, no revival, no cancel-all, duplicate `start()` still a no-op, partial `start()` still does not call `stop()`.

## Invariants

- One registered `sqlite_backup` job.
- One active scheduling loop for that name.
- Restart replaces. It does not add.
- The old task is cancelled before the replacement runs.
- No intentional overlap of an old clock and a new clock.
- Restart does not fire a backup by itself.
- Phase 13.13 does not aim to create a second scheduled backup for the same due time.

## Observability

Use what already exists. No new public REST route.

- `GET /health` registry 6/6
- `sqlite_backup_scheduler_started` once per process start
- `sqlite_backup_sleep seconds=...`
- `sqlite_backup_complete` only when a backup actually finishes
- `next_scheduled` from the existing backup status payload

After a future deploy, check one startup line, a sleep that matches the next future time, no second `sqlite_backup` start, no backup notification caused only by `restart_scheduler`, and unchanged hourly report behavior. Live asyncio task count stays inferred unless a later change adds a dump. This RFC does not add one.

## Alternatives

- Leave `run_sqlite_backup` unchanged. No duplicate-loop risk. The wait and the gzip stay mixed, which is the debt this phase exists to separate.
- Add `sqlite_backup_clock` beside the current loop. That is a seventh task and can run two backups.
- Move gzip and retention into `JobEngine`. That pulls backup business rules into the registry and is larger than phase 3.
- Use cron or a systemd timer. That adds an external scheduler the process does not own today.
- Selected: one `sqlite_backup` lifecycle job, clock separate from `run_backup_once`, still in process, still no extra task.

## Risks

| Risk | Mitigation |
| --- | --- |
| Old and new loops both sleep | One factory, one `register_background` name, no second task |
| Next-time math skips or double-fires a day | Keep `next_scheduled` / `seconds_until_next` and `candidate <= clock`; test before, equal, and after |
| Restart runs a backup immediately | Replacement only waits; test that restart during sleep does not call `run_backup_once` |
| Cancel exactly as the backup starts | Document the race; test cancel during wait; do not claim exactly-once |
| Two backups, two notifications | Do not overlap clocks |
| Timezone drift | Keep `backup_timezone`, default `Asia/Bangkok` |
| Phase 4 or 5 clocks move too | This RFC names only `sqlite_backup` |
| Phase 6 deletes other loops early | Leave the other five loops in place |

## Test plan

Future tests, not part of this draft. Prefer a fake clock.

1. Now strictly before today's candidate selects that candidate. The candidate is `backup_time` with second and microsecond set to 0.
2. Now exactly equal to that candidate selects the next day. This case is separate from before and after.
3. Now strictly after that candidate selects the next day.
4. Timezone follows `backup_timezone`.
5. Disabled backup still sleeps 3600 seconds and does not call `run_backup_once`.
6. The clock waits before `run_backup_once`.
7. Restart during sleep does not call `run_backup_once` because of the restart. A restart at a clock equal to the candidate waits until the next day.
8. Restart replaces the `sqlite_backup` task instead of adding one.
9. Registry and factories stay six names, with one `sqlite_backup` factory.
10. Restart does not restart the other five jobs.
11. `run_backup_once` remains the operation. Gzip and retention tests still describe today's behavior.
12. Telegram due checks and the 60-second report tick stay in `telegram_reports.py`.
13. Photo scan interval stays in the photo watcher.
14. Cancel while waiting is deterministic. Cancel that overlaps an in-flight `run_backup_once` is recorded as the existing race.

## Future validation

Not executed by this draft. After a later implementation and API deploy: healthy API, `/health` 200, database up, registry 6/6, restart count 0, one `sqlite_backup_scheduler_started`, sleep matches `next_scheduled`, no duplicate backup file or backup notification from the deploy itself, `monitor` still checking in, QNAP still healthy, hourly report still one per due window. Do not trigger a backup to prove the clock.

## Rollback

Ship as an API image change only. No schema migration. Rolling back the image restores the previous `run_sqlite_backup` wait. Backup files and the state JSON stay readable.

## Acceptance

A future implementation is complete only when all of these hold:

- One `sqlite_backup` registration and one scheduling loop
- Registry 6/6
- `restart_scheduler` restarts only that name and replaces rather than adds
- Restart does not itself call `run_backup_once`
- `run_backup_once` still performs the backup
- Timezone, disabled sleep, and `next_scheduled` match today, including `candidate <= clock` so an equal timestamp advances one day
- No scheduler table
- The other five jobs are unchanged
- No REST, schema, agent, JWT, QNAP, or dashboard contract change
- The tests above pass
- Production validation shows no duplicate scheduled backup

## AI note

A named clock next to `run_backup_once` can later be explained read-only: next time, whether the loop is waiting, and the last result already stored. Phase 13.13 does not add AI and does not let AI start or restart a backup.

## How to tell it failed

- Two tasks or two startup log lines for `sqlite_backup`
- A backup or backup notification caused only by `restart_scheduler`
- `backup_time` or timezone no longer matches `next_scheduled`
- Disabled backup stops sleeping or starts calling `run_backup_once`
- A missed window is replayed
- Report, photo, notification, offline, or infrastructure timing changes
- A seventh job name appears
