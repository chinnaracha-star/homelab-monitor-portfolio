# RFC-0004 — Report clock ownership

**Status:** Implemented
**Sprint:** 13.14
**Date:** 2026-09-29

Scheduler refactor phase 4 from [refactor-scheduler.md](../refactor-scheduler.md). Implemented in commit `ab23831`. Natural hourly production validation passed. The accepted design below is unchanged. Due rules stay in `telegram_reports.py`.

## Implementation

`JobExecutionWrapper` starts one `telegram_reports` factory. That factory calls `run_telegram_reports`, which remains the lifecycle loop. Each pass calls `run_report_clock` once. `run_report_clock` sleeps `TICK_SECONDS` (60) and then runs one tick. It does not contain `while True`, `create_task`, or a second lifecycle. `SQLAlchemyError` stays on the lifecycle and is logged as `telegram_report_tick_failed`. `CancelledError` is not swallowed. The registry stays six jobs. There is no `report_clock` job.

```text
run_telegram_reports      (lifecycle loop)
    ↓
run_report_clock          (one sleep, then one tick)
```

The Phase 13.14 API image is `sha256:afd8282c119ae07f490c72c2587be860d0453889365ff06401bdeaf9c25414ed`. Controlled deploy was `2026-09-29T05:07:37Z` (`2026-09-29 12:07:37` Asia/Bangkok). The API was healthy with restart count 0. The already-sent 12:00 Asia/Bangkok hourly slot was not sent again.

Natural hourly rows, each status `sent` and one row per slot:

- 12:00 Asia/Bangkok: `2026-09-29 05:01:03` UTC
- 13:00 Asia/Bangkok / 06:00 UTC: notification `cbb105d3-c470-4f59-91f0-feb3722f5a24`, `2026-09-29 06:01:06` UTC, exactly one row, no duplicate
- 14:00 Asia/Bangkok: `2026-09-29 07:00:30` UTC, one row

Hourly `last_sent` moved from `2026-09-29T05:00:39.335089+00:00` to `2026-09-29T07:00:07.045860+00:00`. Daily stayed `2026-09-29T01:00:07.300723+00:00`. Weekly stayed `2026-09-27T01:00:24.224692+00:00`.

An unrelated API recreate at `2026-09-29T07:10:27Z` (container `f135f0e4812d`, same Phase 13.14 image) did not resend the 14:00 slot. That container was healthy, restart count 0, and its logs had no `telegram_report_tick_failed`, traceback, `CancelledError`, or `database is locked`. Phase 13.14 needs no further runtime work. Phase 5 and phase 6 stay open.

## Problem

`run_telegram_reports` in `api/src/homelab_monitor/telegram_reports.py` owns two jobs at once. It is the lifecycle loop, and it owns the fixed 60-second wait.

Current wait, confirmed in source:

```text
JobExecutionWrapper
    ↓
telegram_reports factory
    ↓
run_telegram_reports
    while True:
        await sleep(TICK_SECONDS)
        try:
            tick_telegram_reports()
                process_due_reports()
        except SQLAlchemyError:
            log telegram_report_tick_failed
            continue
```

- Sleep happens before processing.
- The first due evaluation is after 60 seconds. There is no `process_due_reports()` before the first sleep.
- `TICK_SECONDS` is 60. It is a module constant, not a setting.
- `process_due_reports` owns due determination for hourly, daily, and weekly reports.
- `run_telegram_reports` owns the lifecycle and the 60-second clock.
- `tick_telegram_reports` opens a session and calls `process_due_reports` once.

Phase 13.12 already starts one `telegram_reports` task through `JobExecutionWrapper`. Phase 13.13 moved only the backup wait. This RFC moves only the report wait. It does not change when a report is due.

## Proposed change

Keep one lifecycle task named `telegram_reports`. Split the wait from due processing. Do not add a second task. Do not replace the fixed tick with a sleep until the next hourly, daily, or weekly occurrence.

```text
JobExecutionWrapper
    ↓
telegram_reports          (still the only report lifecycle job)
    ↓
run_telegram_reports      (lifecycle loop)
    ↓
run_report_clock          (one iteration)
    ↓
process_due_reports       (due rules, unchanged)
```

One iteration of `run_report_clock` sleeps `TICK_SECONDS`, then runs one due evaluation, then returns. `run_telegram_reports` starts the next iteration. `run_report_clock` must not contain `while True`, `create_task`, `TaskGroup`, `ensure_future`, a second lifecycle, or a supervisor loop.

Preferred shape:

```text
async def run_report_clock(...):
    await asyncio.sleep(TICK_SECONDS)
    tick / process due reports once
    return

async def run_telegram_reports(...):
    while True:
        try:
            await run_report_clock(...)
        except SQLAlchemyError:
            log telegram_report_tick_failed
            continue
```

The `SQLAlchemyError` handler stays on the lifecycle, matching today's continue behavior. `run_report_clock` does not swallow that error and does not swallow `CancelledError`.

Phase 4 does not calculate the earliest of the next hourly, daily, and weekly times and sleep until that instant. Due policy stays in `process_due_reports` and the existing `due_*` helpers. A fixed 60-second sleep followed by evaluation of all enabled due rules is the behavior to keep.

Parameters may follow the current test seams (`now` on `process_due_reports`, a sleep callable if tests need one). No new public REST surface and no new class are required.

## Startup

On lifecycle start the first action is `sleep(60)`, then the first due evaluation.

A start at 11:00:30 does not call `process_due_reports` at 11:00:30. The first evaluation is about 60 seconds later. If the 11:00 hourly slot is enabled and not yet sent, that later tick may send it. This RFC does not add an immediate startup catch-up beyond that existing tick.

An API process restart creates the lifecycle again. The new lifecycle also sleeps 60 seconds before its first evaluation. If `last_sent` already covers the current slot, that tick does not send a duplicate.

## Due rules to preserve

Defaults live in `DEFAULT_REPORTS`: `hour_interval` 1, `daily_time` `08:00`, `weekly_day` `sunday` (`weekday()` 6), `weekly_time` `08:00`, `timezone` `Asia/Bangkok`. Reports are disabled until enabled in the stored payload. Disabled kinds are skipped and do not update `last_sent`.

### Hourly

The current slot is local time floored to `hour_interval` (default 1 hour), with minute, second, and microsecond 0.

- `10:59:59` is the `10:00` slot.
- `11:00:00` is the `11:00` slot.
- `11:00:01` is the `11:00` slot.

The hourly report is due when it is enabled and `last_sent` for `hourly_report` is missing or earlier than the current slot boundary. A return during the 11:00 hour, after the process was down at 11:00, may send that 11:00 slot on the first tick. Older hourly slots are not replayed one by one. There is no catch-up queue.

### Daily

Before `08:00` in the report timezone the daily report is not due. At or after `08:00` it is due when enabled and the daily `last_sent` local date is not today, including when `last_sent` is missing. A start later the same day may still send today's daily report. A missed previous day is not replayed on the next day before that day's own due time.

### Weekly

The weekly report is due only on the configured weekday, at or after the configured time, under the same local-date rule as daily. If Sunday is missed entirely, Monday does not replay Sunday's weekly report.

### Time

`process_due_reports` uses `datetime.now(UTC)` when `now` is omitted, then converts that instant into the report timezone. Hourly, daily, and weekly share that timezone. `report_timezone` uses `ZoneInfo`. An unknown name falls back to `UTC+7`. Tests may pass `now`. Phase 4 does not redesign clock injection. `run_telegram_reports` today does not pass `now`; the production loop still follows the wall clock.

### Order

Due kinds are handled sequentially: hourly, then daily, then weekly. They are not dispatched concurrently. If an earlier kind raises before later kinds run, those later kinds do not run on that tick. Each kind that finishes `dispatch_telegram_report` updates its own `last_sent` through its own `save_payload` commit. There is no transaction across the three kinds.

## Persistence

`last_sent` stays in `NotificationSettings.payload.reports.last_sent`.

Keys: `hourly_report`, `daily_report`, `weekly_report`.

Values: UTC ISO timestamps written by `_mark_sent`.

Phase 4 does not move `last_sent` into the Job Engine and does not add scheduler rows.

`last_sent` is updated after `dispatch_telegram_report` returns a notification row. That includes status `sent`, `failed`, and `skipped`. If `build` raises before dispatch, `last_sent` is not updated.

Duplicate prevention is this comparison against the current period. There is no lock that stops two report lifecycles from reading a stale `last_sent` and both sending. Phase 4 therefore keeps exactly one `telegram_reports` lifecycle and one factory.

## Delivery and rendering

A due report still follows:

```text
TelegramReportService.build
    ↓
dispatch_telegram_report
    ↓
NotificationService
```

Delivery does not move into `notification_worker`. Existing retry of a failed notification row stays on that row's retry path. A failed or skipped send still advances `last_sent`, so the next tick does not treat the same slot as unsent.

Commit `571d782` stays intact: `_compact_metric` places the percent on the metric-name line when a bar is present; hourly and test reports take backup status and `latest_at` from `sqlite_status_payload`; daily and weekly reports still use the analytics success-rate wording. The report clock does not render text.

`sqlite_status_payload` is read when the report is built, during the tick, not before the 60-second sleep. Phase 4 does not snapshot backup status into the clock.

## Failure and cancellation

`SQLAlchemyError` during a tick is caught by `run_telegram_reports`, logged as `telegram_report_tick_failed`, and the lifecycle continues.

Any other exception may leave `run_telegram_reports`. That ends the `telegram_reports` task. [RFC-0002](RFC-0002-job-engine-execution-wrapper.md) still applies: `JobExecutionWrapper` does not supervise or retry a failed coroutine. Phase 4 adds no `TaskGroup`, no restart policy, and no retry framework.

Cancel while `run_report_clock` is sleeping propagates. `process_due_reports` does not run for that cancelled wait. `CancelledError` is not suppressed in the clock iteration. After processing has started, today's operation semantics remain. This RFC does not claim exactly-once delivery.

## Job Engine and operations

Registry stays six jobs. The report job stays `telegram_reports`. Implementation stays `run_telegram_reports`. There is no seventh job named `report_clock`.

`JobExecutionWrapper` start, stop, partial-start behavior, and the duplicate-start guard stay as in RFC-0002.

Operations Center has no action that restarts `telegram_reports`. `restart_scheduler` still restarts only `sqlite_backup`. Phase 4 does not add a report restart endpoint. A full API process restart is the existing way to recreate the report lifecycle, and that recreation sleeps 60 seconds first.

The old loop and a new independent clock must not run together. Two clocks can send duplicate Telegram reports.

## What this RFC does not change

Phase 4 does not:

- migrate the photo interval (phase 5, not started)
- migrate offline-monitor, infrastructure-monitor, or notification-worker timing
- modify the backup clock
- redesign hourly, daily, or weekly due rules
- change the `TICK_SECONDS` policy or replace it with a sleep until the next due report
- add a missed-report queue or other scheduler persistence
- change the `last_sent` schema or the notification schema
- redesign Telegram formatting or the SQLite backup status source
- redesign notification delivery
- add a report restart action, a seventh job, or a second report lifecycle
- add `TaskGroup`, a supervisor, or a distributed scheduler
- change REST, the database schema, agent protocol `0.1.0`, JWT, RBAC, the dashboard, QNAP, NAS, or Tailscale

Phase 6, retiring the remaining private loops, stays not started. Completing phase 4 does not complete the scheduler refactor.

A separate soak saw `database is locked` around `2026-09-29T01:58:13Z`. Report processing writes notification rows and the `NotificationSettings` payload, so it shares SQLite with other work. The cause is not established here. This RFC does not change locking, add a queue, or add a transaction to address that observation.

## Observability

There is no log line for every report sleep. Production may not expose an asyncio task dump. A single lifecycle in production is inferred from the registry and factory counts, startup evidence when it exists, notification rows, `last_sent`, the absence of duplicate rows for one slot, and restart count. Do not claim a task dump proved one task unless one was actually taken.

A later implementation may add a narrow lifecycle or clock log only if it does not change timing, delivery, or `last_sent`. Prefer no new log.

## Contracts touched

Ownership of the 60-second wait inside the single `telegram_reports` lifecycle.

## Contracts explicitly preserved

- One registered name: `telegram_reports`
- Six jobs and six factories
- Sleep 60 seconds before each due evaluation, including the first
- `process_due_reports`, `due_hourly`, `due_daily`, `due_weekly`, and the `next_*` helpers used for display
- Report timezone, `UTC+7` fallback, and `datetime.now(UTC)` when `now` is omitted
- `last_sent` location, keys, UTC ISO values, and update-after-dispatch timing, including `failed` and `skipped`
- Sequential hourly, then daily, then weekly processing
- `dispatch_telegram_report` and `NotificationService`
- Compact formatting and the SQLite backup status read at build time
- `SQLAlchemyError` continue behavior and no wrapper retry
- RFC-0002 wrapper behavior and RFC-0003 backup clock behavior

## Test plan

Future tests, not part of this draft.

1. One clock iteration sleeps `TICK_SECONDS` before processing, calls due processing once, and does not process if cancelled during the sleep.
2. The lifecycle repeats that iteration. `SQLAlchemyError` is logged and the loop continues. Other unexpected failures still leave the lifecycle as they do now.
3. Hourly: just before a boundary, exactly on it, and just after it. A start inside an unsent current slot does not evaluate until after the first sleep, and does not replay older slots.
4. Daily: before, exactly at, and after `08:00`. A later start on the same due day may send. A missed prior day is not replayed before the next day's due time.
5. Weekly: configured weekday and time. A missed Sunday is not sent on Monday.
6. A slot already recorded in `last_sent` does not send again. `failed` and `skipped` still record `last_sent`.
7. Hourly plus daily, and hourly plus weekly, stay sequential in that order.
8. Existing compact-metric and SQLite backup-status report tests still pass.
9. Registry and factories stay six names, with one `telegram_reports` factory and no `report_clock` job. Wrapper lifecycle tests still pass.

## Future validation

Not executed by this draft. After a later implementation and API deploy, observe without a manual report trigger: healthy API, database up, registry 6/6, no `report_clock` job, restart count 0 after the deploy settles, one report lifecycle where that can be seen, one natural hourly row for the due slot, `last_sent` advanced, no duplicate hourly row, compact formatting and the SQLite backup status source unchanged, photo watcher and backup clock still running, and `monitor` still checking in. No new unawaited-task errors.

If the deploy is up across 08:00 Asia/Bangkok, the natural daily report can be observed the same way. The weekly report can be observed only on Sunday at or after 08:00.

## Rollback

Ship as an API image change only. No schema migration. Rolling back the image restores the previous `run_telegram_reports` wait. Notification rows and `last_sent` stay readable.

## Acceptance

A future implementation matches this RFC only when all of these hold:

- The wait lives in one `run_report_clock` iteration under `run_telegram_reports`
- One `telegram_reports` lifecycle and factory
- Registry 6/6 and no `report_clock` job
- Fixed 60-second sleep, and sleep before process, including the first tick
- `process_due_reports` and the hourly, daily, and weekly rules unchanged
- Timezone and `last_sent` semantics unchanged
- Sequential report order and the current notification path unchanged
- Rendering and the SQLite backup status read unchanged
- `SQLAlchemyError` handling unchanged
- Cancellation during the wait skips that tick's processing and is not called exactly-once
- Tests and the production soak above pass
- Phase 5 and phase 6 stay out of scope
- The database-lock observation stays a separate investigation

## How to tell it failed

- Two tasks or two clocks both evaluate due reports
- A seventh job name appears
- The first evaluation runs before the first 60-second sleep
- The loop sleeps until the next due report instead of ticking every 60 seconds
- A missed day or a missed Sunday is replayed as a queue
- `last_sent` moves before dispatch, or stops updating on `failed` or `skipped`
- Hourly, daily, and weekly run concurrently or change order
- Formatting or the backup status source changes
- `SQLAlchemyError` ends the lifecycle, or other failures start a supervisor retry
- Report, photo, or backup timing changes outside this wait split
