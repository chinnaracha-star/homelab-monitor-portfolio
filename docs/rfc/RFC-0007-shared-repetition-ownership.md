# RFC-0007 — Shared repetition ownership

**Status:** Implemented
**Sprint:** 13.16
**Date:** 2026-10-02

Scheduler refactor phase 6 from [refactor-scheduler.md](../refactor-scheduler.md). [RFC-0006](RFC-0006-retire-private-loops.md) extracted timing for `offline_monitor` and `infrastructure_monitor`. This RFC moves repetition for the five periodic jobs into one shared primitive. Implemented in commit `339d15a`. Production validation passed. The accepted design below is unchanged. Phase 13.16 and roadmap phase 6 are complete.

## Implementation

`run_repeated` in `api/src/homelab_monitor/jobs/repetition.py` is the only shared repetition owner. It awaits one operation, then awaits it again. It does not sleep, catch `Exception`, retry, or call `create_task`. It is not a seventh job and it does not own intervals.

```text
JobExecutionWrapper          task start and stop
    ↓
run_* lifecycle              factory entry, logs, and job-specific cancel handling
    ↓
run_repeated                 repetition only
    ↓
one-iteration helper         timing and order
    ↓
domain operation             the work
```

`run_notification_worker` stays a queue worker. Its `while True`, empty-queue sleep, and batch drain stay. WebSocket receive loops and the realtime heartbeat stay. Phase 6 does not mean every `while True` in the repository is gone. It means the five scheduler lifecycles no longer each own repetition.

| Lifecycle | Repeated operation |
| --- | --- |
| `run_offline_monitor` | `run_offline_monitor_interval` directly |
| `run_infrastructure_monitor` | `run_infrastructure_monitor_interval` directly |
| `run_telegram_reports` | `report_pass`: `run_report_clock`, and on `SQLAlchemyError` log `telegram_report_tick_failed` and return |
| `run_photo_watcher` | `run_photo_watcher_interval(scan_for_interval)` after the disabled return |
| `run_sqlite_backup` | `run_backup_clock` directly |

Before deploy, the backend suite was 435 passed, 0 failed. Ruff, format, and `git diff --check` passed. Focused tests cover repetition, the report catch inside the pass, and the five lifecycles no longer containing `while True`.

Production image `homelab-monitor-api:phase13.16-339d15a`, id `sha256:6e178cc41530d73aa0a166f2f36c9c8ba42652ea143fe91cce927fd16998800c`. Predeploy image `sha256:2ed9e6b7fadaf90992d776facf60e06815274a244f0f2788828f7c0150cf3ad9`, tagged `homelab-monitor-api:rollback-phase13.16-rfc0007-predeploy`. API-only recreate `2026-10-02T10:49:03+07:00` through `2026-10-02T10:49:04+07:00`. Container start `2026-10-02T03:49:04Z`. API stayed healthy with restart count 0. Registry remained six jobs. Rollback was not required.

Configured intervals were 30 seconds for offline and 3600 seconds for infrastructure. Offline success ticks are silent, so this soak does not record timestamps of successful evaluations. The process stayed up with restart count 0 well past two 30-second intervals. No offline error and no duplicate offline execution were seen. Sleep-before stayed consistent with that observation.

Infrastructure did not refresh at startup. The first natural refresh was `2026-10-02T04:49:12Z`, about 3608 seconds after start. The second was `2026-10-02T05:49:15Z`, 3603 seconds later. No duplicate refresh and no infrastructure logger error. QNAP monitoring stayed healthy.

Telegram sent one notification at `2026-10-02T04:00:34Z` and one at `2026-10-02T05:00:57Z`. No duplicate. No `telegram_report_tick_failed` in this window. Production did not exercise the `SQLAlchemyError` recovery path. Tests and the guarded `report_pass` cover that path.

Photo watcher ticked at `2026-10-02T03:49:09Z`, before the first `photo_watcher_sleep` at `2026-10-02T03:52:06Z`. Later logs show 116 `photo_watcher_scan_finished` lines and sleeps of 10 seconds. One scanner started. No tight loop and no `photo_watcher_failed`. Production did not exercise the 5-second scan-failure delay. That delay remains inside `scan_for_interval` plus `run_photo_watcher_interval`, and tests cover it.

SQLite backup logged `sqlite_backup_scheduler_started` and `sqlite_backup_sleep seconds=54651` at `2026-10-02T03:49:09Z`. That wait targets the next 02:00 Asia/Bangkok, which was outside this window. No natural backup ran during Step 10. No duplicate backup and no scheduler error. The scheduler stayed alive.

`notification_worker` logged neither disabled nor crashed. The API process did not restart.

Three `POST /api/v1/agent/check-ins` responses returned HTTP 500 with SQLite `database is locked` while the photo watcher was scanning. Scheduler loggers did not record a task failure. Restart count stayed 0. The same class of lock was seen before this RFC. No evidence attributes it to `run_repeated`. It stays a separate follow-up. This closure does not change pool size or transactions.

## Context

Five jobs now have a one-iteration helper. Each lifecycle function still repeats that helper:

| Job | Lifecycle | One-iteration helper | Order inside the helper |
| --- | --- | --- | --- |
| `offline_monitor` | `run_offline_monitor` | `run_offline_monitor_interval` | sleep, then evaluate |
| `infrastructure_monitor` | `run_infrastructure_monitor` | `run_infrastructure_monitor_interval` | sleep, then refresh |
| `telegram_reports` | `run_telegram_reports` | `run_report_clock` | sleep 60 seconds, then tick |
| `photo_watcher` | `run_photo_watcher` | `run_photo_watcher_interval` | scan, then sleep |
| `sqlite_backup` | `run_sqlite_backup` | `run_backup_clock` | wait until due, then `run_backup_once` |

`JobExecutionWrapper` starts one task per factory through `register_background`. It cancels that set on stop. It does not sleep, retry, or revive a finished task. [RFC-0002](RFC-0002-job-engine-execution-wrapper.md) keeps sleep and loop bodies out of the wrapper.

`run_notification_worker` is the sixth job. It drains a queue. It is not one of the five periodic helpers.

The roadmap sentence still open is "Retire private loops." [RFC-0006](RFC-0006-retire-private-loops.md) says that sentence is not finished by timing extraction. The future sketch in [refactor-scheduler.md](../refactor-scheduler.md) describes an engine with interval or cron, overlap, and sleep ownership. That sketch is larger than the loops that remain.

## Problem

Each periodic lifecycle still contains its own `while True`. Those five loops are the private repetition left after phases 13.13–13.16. Deleting them without a replacement stops the jobs. Putting the same loop inside `JobExecutionWrapper` would make the wrapper a scheduler, which RFC-0002 forbids.

The five helpers do not share one interval or one order. A generic "every N seconds, then run" engine would change startup and due-time behavior. Offline and infrastructure sleep before work. Reports sleep 60 seconds before a tick. Photo scans first. Backup waits until 02:00 Asia/Bangkok, or 3600 seconds when disabled.

## Goals

- One shared repetition primitive owns `while True` for the five periodic jobs.
- Each existing helper keeps its own wait and its own operation order.
- `JobExecutionWrapper` still owns task start and stop only.
- The registry stays six names.
- `notification_worker` keeps its queue loop.
- Failure and cancellation stay as they are today.

## Non-goals

- Implementing this RFC in the same change as the proposal.
- An interval, cron, overlap, or retry engine.
- A seventh job.
- Moving sleep out of the five helpers.
- Changing `notification_worker` poll, retry, or batch behavior.
- Changing `JobExecutionWrapper` into a supervisor.
- SQLite pool settings, schema, or snapshot write behavior.
- WebSocket and realtime loops.
- QNAP, Telegram, backup, report, or photo business rules.

## Current execution model

```text
application lifespan
    ↓
JobExecutionWrapper.start
    ↓
factories(settings) checked against the six registry names
    ↓
register_background(name, factory)   one task per name
    ↓
run_* lifecycle                       while True
    ↓
one-iteration helper                  sleep or due wait, and one operation
```

Shutdown calls `wrapper.stop`, which cancels those tasks and awaits them. `CancelledError` is swallowed by the wrapper. Any other exception from a task is raised from `stop`. `restart_background` replaces `photo_watcher` or `sqlite_backup` only. It calls the same factory again. Nothing gathers the six tasks, so one failure does not cancel the others.

WebSocket receive loops and the realtime heartbeat are not these tasks.

### Current failure and cancellation

| Job | Contained inside the repeated pass | Escapes and ends the task | Cancellation |
| --- | --- | --- | --- |
| `offline_monitor` | `SQLAlchemyError` logged as `offline_evaluation_failed` inside the helper | any other exception from the helper | sleep is outside `try`; `CancelledError` skips that evaluation and ends the task |
| `infrastructure_monitor` | `Exception` logged as `infrastructure_refresh_failed` inside the helper | none from the refresh thread; `CancelledError` is not an `Exception` | sleep is outside `try`; cancel skips that refresh and ends the task |
| `telegram_reports` | `SQLAlchemyError` logged as `telegram_report_tick_failed` around `run_report_clock` | any other exception | cancel during the 60-second sleep propagates; the lifecycle does not catch it |
| `photo_watcher` | scan `Exception` logged as `photo_watcher_failed`, then the 5-second failure delay | none from a normal scan | cancel is logged as `photo_watcher_cancelled` and re-raised; `finally` logs `photo_watcher_stopped` |
| `sqlite_backup` | none around `run_backup_clock` | any exception other than cancel | cancel is logged as `sqlite_backup_scheduler_cancelled` and re-raised; cancel during the wait skips `run_backup_once` |

`photo_watcher` returns without looping when `photo_watcher_enabled` is false. `notification_worker` returns without looping when `notification_worker_enabled` is false. A disabled `sqlite_backup` still loops: each pass sleeps 3600 seconds inside `run_backup_clock`.

## Definitions

A private scheduler loop is a lifecycle function that both repeats one job and calculates that job's sleep or due time in the same function. After RFC-0003 through RFC-0006, the five periodic lifecycles repeat, and the helpers calculate time. The remaining private loop is the repetition `while True` in each lifecycle.

A repetition owner calls one already-timed operation, waits until that call returns, then calls it again, until cancellation or a terminal exception. It does not choose the delay. It does not catch `Exception` and continue. It does not start another task.

A timing owner is the one-iteration helper. It keeps the sleep, the due-time wait, and the order of work.

A task owner creates the asyncio task and cancels it on shutdown. That owner is still `JobExecutionWrapper` through `register_background`.

A worker lifecycle drains queued work. `run_notification_worker` is that loop: `process_one`, then 0.25 seconds only when the queue did not yield work. Retry and batching stay inside `NotificationWorker`. Removing that `while True` would stop the worker, not retire a schedule.

## Decision

Phase 13.16 may add one shared async primitive, conceptually `run_repeated`, and point the five periodic lifecycles at it. The primitive is:

```text
while True:
    await operation()
```

`operation` is the existing one-iteration helper, or a closure that already contains that job's per-pass handler. The primitive does not sleep on its own, does not catch `Exception`, does not catch `CancelledError`, and does not call `create_task`.

The five lifecycle functions remain the factory entries and the registered implementations. They may keep logs and the handlers that are not part of repetition: backup start and cancel logs, photo enablement check, photo cancel log, and `finally`. The `while True` in those five functions goes away.

`notification_worker` does not call `run_repeated`.

This is repetition ownership only. It is not the interval-or-cron engine sketched under "Future Job Engine" in the scheduler plan. That engine would own sleep and overlap. The helpers already own sleep, and they do not share one interval. Building that engine here would change timing. It is rejected for this RFC.

## Repetition ownership

`run_repeated` lives next to the job modules, not inside `JobExecutionWrapper`.

Each periodic factory still returns the current `run_*` coroutine. That coroutine awaits `run_repeated` once. One iteration of `run_repeated` is one helper call. The next call starts only after the previous call returns. There is no overlap and no second task.

Per-job handlers that must keep running after a contained error stay inside the operation passed to `run_repeated`, not inside the primitive, and not around the whole `await run_repeated(...)`. A catch around `run_repeated` would end the task on the first contained error.

Exact composition:

| Lifecycle | Operation passed to `run_repeated` | Why |
| --- | --- | --- |
| `run_offline_monitor` | `run_offline_monitor_interval` directly | `SQLAlchemyError` is already logged inside the helper. Any other exception escapes. |
| `run_infrastructure_monitor` | `run_infrastructure_monitor_interval` directly | Refresh `Exception` is already logged inside the helper. `CancelledError` is not an `Exception`. |
| `run_telegram_reports` | a guarded pass: `try` `run_report_clock`, `except SQLAlchemyError` log `telegram_report_tick_failed` and return | `run_report_clock` does not catch that error. The catch is inside the pass so the next call still happens. Any other exception escapes `run_repeated`. |
| `run_photo_watcher` | `run_photo_watcher_interval(scan_for_interval)` directly, after the existing disabled return | Scan `Exception` is already inside `scan_for_interval`. It logs `photo_watcher_failed` and returns 5. The helper then sleeps `max(interval, 5)`, so the failure delay stays 5 seconds. Do not add a second catch or a second sleep in the lifecycle. |
| `run_sqlite_backup` | `run_backup_clock` directly | The clock already waits, then runs `run_backup_once`. No new catch. |

`run_photo_watcher` still wraps `await run_repeated(...)` only to log `photo_watcher_cancelled` and re-raise `CancelledError`, and `finally` still logs `photo_watcher_stopped`. That wrapper does not catch `Exception`. `run_sqlite_backup` still logs `sqlite_backup_scheduler_started` before `run_repeated`, and still logs `sqlite_backup_scheduler_cancelled` and re-raises `CancelledError` around it. That wrapper does not catch `Exception`.

None of these passes returns without a prior sleep except the photo scan, which is the existing scan-then-sleep order. After a contained offline, infrastructure, or report error, the next pass sleeps again inside the helper before the next operation. Photo's failure path sleeps 5 seconds inside `run_photo_watcher_interval`. Backup's disabled path sleeps 3600 seconds inside `run_backup_clock`, and the due path waits `seconds_until_next` (at least 1 second). `run_repeated` adds no sleep of its own, and these passes do not spin.

## Task ownership

`JobExecutionWrapper.start` still registers the six factories. `register_background` still creates one task per name. `run_repeated` is awaited inside that task. It does not create a nested task. `wrapper.stop` still cancels the same tasks. `restart_background` still replaces `photo_watcher` or `sqlite_backup` by calling the same factory.

The wrapper does not learn intervals, due times, or which jobs repeat.

## Timing ownership

Unchanged helpers:

- `run_offline_monitor_interval` sleeps `alert_evaluation_interval_seconds`, then evaluates.
- `run_infrastructure_monitor_interval` sleeps `infrastructure_refresh_seconds`, then refreshes.
- `run_report_clock` sleeps 60 seconds, then ticks.
- `run_photo_watcher_interval` scans, then sleeps the dynamic delay, including 5 seconds after a scan failure.
- `run_backup_clock` sleeps 3600 seconds when backup is disabled, otherwise waits until the next 02:00 Asia/Bangkok and then runs `run_backup_once`.

The first offline and infrastructure passes still wait. The first photo scan is still immediate. The first report tick still waits 60 seconds. Backup still does not run at process start unless that start is already the due time.

## Failure semantics

`run_repeated` lets exceptions propagate. It does not restart.

- Offline: `SQLAlchemyError` stays inside the helper. Any other exception ends `offline_monitor`. The wrapper does not replace it.
- Infrastructure: `Exception` from refresh stays inside the helper. The loop continues only because the helper returns. `CancelledError` still propagates.
- Reports: `SQLAlchemyError` stays in the guarded operation around `run_report_clock`. Any other exception ends `telegram_reports`.
- Photo: scan failures stay in `scan_for_interval`, return 5, and `run_photo_watcher_interval` still sleeps that delay. There is no separate lifecycle sleep after `photo_watcher_failed`. Cancel still logs and re-raises around `run_repeated`. `photo_watcher_stopped` still runs from `finally`.
- Backup: an exception from `run_backup_clock` or `run_backup_once` still ends `sqlite_backup`, except `CancelledError`, which is still logged and re-raised.

A generic `except Exception: continue` around every operation is forbidden. It would hide the terminal exceptions that end offline, report, and backup tasks today.

## Cancellation semantics

Cancel still hits the task the wrapper started. Because `run_repeated` only awaits the helper, cancel during a helper sleep propagates through that sleep, then through `run_repeated`, then through the lifecycle. No extra task is left running. `notification_worker` shutdown is unchanged: cancel during `process_one` or the 0.25-second sleep still leaves that coroutine, and the wrapper still awaits it.

## Notification worker boundary

`run_notification_worker` remains a worker lifecycle. Empty-queue polling, `process_one`, retry, and the batch window stay in `NotificationWorker`. This RFC must not delete that `while True` to make every job module look the same.

## Registry boundary

Six names stay: `offline_monitor`, `infrastructure_monitor`, `telegram_reports`, `notification_worker`, `photo_watcher`, `sqlite_backup`. Schedule strings stay descriptive. This RFC does not add `execution_mode`, a callable, or a cron field to `JobDefinition`.

## JobExecutionWrapper boundary

The wrapper still starts the six factories, refuses a second start, cancels on stop, and does not revive a failed task. It does not call `run_repeated`. It does not own repetition policy. RFC-0002 remains in force.

## Implementation plan

Only after this RFC is Accepted:

1. Add `run_repeated` with the body above and no other policy.
2. Replace `while True` in the five periodic lifecycles with one `await run_repeated(...)`.
3. Keep each job's existing contained-error handler on that operation, not on the primitive.
4. Keep photo's disabled return, backup's start and cancel logs, and photo's cancel and stop logs.
5. Leave `run_notification_worker`, factories' six names, the registry, and `JobExecutionWrapper` behavior unchanged.

## Test plan

Shared repetition:

- Calls the operation again after it returns.
- Does not sleep by itself.
- Stops when the operation raises `CancelledError`.
- Lets any other exception escape.
- Does not restart after that exception.
- Does not overlap two calls.

Five periodic jobs:

- Each lifecycle awaits `run_repeated` and no longer contains `while True`.
- Helper order and startup stay as in the current interval tests.
- The failure rows in this RFC stay true.
- Cancel during sleep still skips the operation that follows that sleep.

Other:

- `notification_worker` still polls and still sleeps 0.25 seconds on an empty queue.
- Registry and factories still name the same six jobs.
- `JobExecutionWrapper` tests still pass without new restart behavior.
- Existing backup clock, report clock, photo watcher, and monitor interval tests still pass.
- Full backend suite, Ruff, format, and `git diff --check` pass.

## Production validation

Not part of authoring this proposal. After an accepted implementation:

- Read the configured `alert_evaluation_interval_seconds` and `infrastructure_refresh_seconds` from the running process. Do not assume 30 and 3600 if production config differs. At the RFC-0006 validation they were 30 and 3600.
- Keep a rollback image of the running API.
- Recreate only the API if the image must change.
- Confirm health, restart count, and six registry jobs.
- Confirm one task name per job and no second factory start in the logs.
- Watch at least two natural offline intervals and two natural infrastructure intervals. Do not call the helpers by hand. Do not shorten the infrastructure interval to speed the check. A 3600-second interval needs more than one hour.
- Confirm photo watcher, telegram reports, sqlite backup, and notification worker are still alive. Do not wait until 02:00 only to prove backup timing if the existing backup-clock tests already cover that wait, unless a natural backup occurs during the window.
- Confirm the first offline and infrastructure passes still wait, and the first photo scan is still immediate.
- SQLite QueuePool timeout and `database is locked` seen during RFC-0006 validation are out of scope. Do not change pool size, SQLite settings, or snapshot writes in this implementation.

## Rollback

The implementation commit is the code boundary. Tag the pre-deploy API image before rollout. Rollback is that image, or the previous commit, with no schema migration. This proposal does not create the tag.

## Risks

- Catching `Exception` inside `run_repeated` would keep a job alive that today stops.
- An extra sleep in `run_repeated` would double every interval.
- Calling `create_task` inside `run_repeated` would orphan work after cancel.
- Wrapping photo's disabled return inside `run_repeated` would turn a finished task into an infinite no-op.
- Treating this primitive as the interval-or-cron engine would reopen timing that RFC-0003 through RFC-0006 already froze.

## Alternatives considered

Put `while True` in `JobExecutionWrapper`. Rejected. RFC-0002 says the wrapper does not own sleep or loop bodies and does not revive failed work. `notification_worker` is not the same kind of repeat.

Start a second component from lifespan that creates the five tasks. Rejected. The wrapper already creates those tasks. A second owner duplicates cancel and restart.

Add `execution_mode` to the registry and drive a generic engine from it. Rejected. Schedule strings are descriptions, not executable timing. A mode field does not remove the loops and invites the cron engine this RFC rejects.

Build the future Job Engine that owns interval, cron, overlap, and sleep. Rejected for this phase. The helpers already disagree on order and delay. Moving sleep there changes production behavior.

Leave the five `while True` loops. Rejected. That does not finish "Retire private loops."

## Completion criteria

This RFC is Implemented in commit `339d15a`. Phase 13.16 and roadmap phase 6 are complete. `run_repeated` is not an interval or cron engine.

Phase 13.16 does not mean every `while True` in the repository is gone. It means the five scheduler-style lifecycle functions no longer implement their own repetition. After completion, repetition may remain only as: one shared `run_repeated` loop, the `notification_worker` queue loop, WebSocket receive loops, and the realtime heartbeat. Those last three are not scheduler loops.

Phase 13.16 may be closed only after a later implementation step, and only when all of the following are true:

- The five periodic lifecycle functions no longer contain `while True`.
- One shared `run_repeated` is the only repetition owner for those five jobs.
- The five timing helpers are unchanged.
- `run_notification_worker` still has its queue loop.
- The registry still has exactly six jobs and the same names.
- `JobExecutionWrapper` still only starts and stops tasks.
- The tests in this RFC pass.
- Production validation passes, including two natural intervals of each in-scope monitor at the configured values, with no duplicate task and no startup drift.
- Documentation records the implementation and does not claim an interval or cron engine exists.

Those criteria are met. Phase 13.16 and roadmap phase 6 are complete. Completing them does not remove `run_notification_worker`, the notification batch drain, WebSocket receive loops, or the realtime heartbeat.
