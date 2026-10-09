# RFC-0006 — Retire private loops

**Status:** Implemented
**Sprint:** 13.16
**Date:** 2026-10-01

Scheduler refactor phase 6 from [refactor-scheduler.md](../refactor-scheduler.md). This RFC is the timing-extraction prerequisite inside Phase 13.16. It is not a new phase number. Implementing it does not retire lifecycle loops and does not complete Phase 13.16. A later RFC is required before any central scheduler owns repetition. [RFC-0002](RFC-0002-job-engine-execution-wrapper.md) requires phases 3–6 to have their own RFC before code changes. Implemented in commit `ec9768e`. Production validation passed. The accepted design below is unchanged.

## Implementation

`run_offline_monitor` remains the lifecycle loop and calls `run_offline_monitor_interval` once per pass. One helper call sleeps `alert_evaluation_interval_seconds`, then evaluates. `run_infrastructure_monitor` remains the lifecycle loop and calls `run_infrastructure_monitor_interval` once per pass. One helper call sleeps `infrastructure_refresh_seconds`, then refreshes. Neither helper loops or registers a job. The registry stays six names. `notification_worker`, `JobExecutionWrapper`, `run_backup_clock`, `run_report_clock`, and `run_photo_watcher_interval` were not changed.

```text
run_offline_monitor
    ↓
run_offline_monitor_interval
    ↓
sleep, then evaluate_offline_agents

run_infrastructure_monitor
    ↓
run_infrastructure_monitor_interval
    ↓
sleep, then refresh_infrastructure
```

Test isolation for live local settings is commit `081d1f2` (`tests/api/conftest.py` only). Before deploy, focused checks passed: monitor intervals 12, JobExecutionWrapper 12, backup clock 11, report clock 21, photo watcher 38. Full backend was 429 passed, 0 failed. Ruff, format, and `git diff --check` passed.

Production image `homelab-monitor-api:phase13.16-ec9768e`, id `sha256:2ed9e6b7fadaf90992d776facf60e06815274a244f0f2788828f7c0150cf3ad9`. Predeploy image `sha256:02ea247ed246d1c0865b39817b9a7608e177f04dc856d59c90f9ad637f8b1290`, tagged `homelab-monitor-api:rollback-phase13.16-rfc0006-predeploy`. API-only recreate `2026-10-01T21:02:02+07:00` through `2026-10-01T21:02:05+07:00`. Container start `2026-10-01T14:02:04Z`. API stayed healthy with restart count 0. Registry remained six jobs. Rollback was not required.

Configured production intervals were 30 seconds for offline and 3600 seconds for infrastructure. Offline success ticks are silent, so two successful offline iterations were not read from logs. No offline error appeared in the first 30 seconds. The task stayed in the same process. No duplicate offline execution was seen. One contained `SQLAlchemyError` (`offline_evaluation_failed`) occurred at `2026-10-01T15:11:50Z`, long after startup. Existing handling logged it and the loop continued.

Infrastructure did not refresh at startup. The first natural refresh was `2026-10-01T15:02:12Z`. The second was `2026-10-01T16:02:16Z`. Later refreshes stayed about one hour apart through `2026-10-02T01:02:47Z`. No second monitor loop was seen. QNAP monitoring stayed healthy. One contained `infrastructure_refresh_failed` at `2026-10-02T02:02:59Z` was SQLite `database is locked` while writing a photo snapshot. Existing handling logged it.

`telegram_reports`, `photo_watcher`, `sqlite_backup`, and `notification_worker` stayed alive. SQLite backup completed naturally at `2026-10-01T19:00:05Z` as `homelab-monitor-2026-10-02-020000.sqlite3.gz`.

Production validation also saw contained SQLite contention: a QueuePool timeout around `2026-10-01T15:11–15:12Z` (offline monitor, telegram report tick, and photo watcher) and the lock above. Existing error boundaries recovered without an API restart. No causal link to RFC-0006 was established. That contention is a follow-up candidate only. It is not Phase 13.16 scope.

RFC-0006 implementation is complete. Phase 13.16 is not complete. `run_offline_monitor`, `run_infrastructure_monitor`, `run_telegram_reports`, `run_photo_watcher`, and `run_sqlite_backup` still own lifecycle repetition. This RFC extracted the remaining monitor timing. It did not move that repetition to a central scheduler. Lifecycle-loop retirement stays future work under a separate RFC. That RFC is not created here.

## Context

Phases 13.13–13.15 moved timing for three jobs into one-iteration helpers. Each lifecycle function still owns `while True`:

| Job | Lifecycle | One-iteration helper | Order |
| --- | --- | --- | --- |
| `sqlite_backup` | `run_sqlite_backup` | `run_backup_clock` | wait until due, then `run_backup_once` |
| `telegram_reports` | `run_telegram_reports` | `run_report_clock` | sleep 60 seconds, then tick |
| `photo_watcher` | `run_photo_watcher` | `run_photo_watcher_interval` | scan, then sleep |

`offline_monitor` and `infrastructure_monitor` still sleep inside the lifecycle loop. `notification_worker` polls a queue. WebSocket and realtime loops are not Job Engine jobs.

The roadmap sentence is:

> 6. **Retire private loops** only after each later phase has run in production for a release without missed jobs. Not started.

[RFC-0003](RFC-0003-backup-clock-ownership.md) names the same step "Broad private-loop deletion (scheduler phase 6)" and says a compatibility `while True` may remain until that later cleanup. [docs/job-engine.md](../job-engine.md) says removing a loop before a coordinator has the same intervals would change runtime behavior.

## Problem

"Retire private loops" can be read as deleting every `while True`. That reading is not what phases 13.13–13.15 did, and it is not safe. Those loops are what keep the six jobs running. Deleting them without a replacement owner stops the work.

Two scheduler-style jobs still mix lifecycle and timing in one function:

```text
run_offline_monitor
    while True:
        sleep alert_evaluation_interval_seconds
        evaluate_offline_agents

run_infrastructure_monitor
    while True:
        sleep infrastructure_refresh_seconds
        refresh_infrastructure
```

Both sleep before the operation. The first pass after process start does not evaluate or refresh immediately.

## Definition of a private loop

A private scheduler loop is a Job Engine lifecycle function that both:

- owns the indefinite run of one registered job, and
- owns that job's sleep, delay, or due-time calculation inside the same function.

`run_offline_monitor` and `run_infrastructure_monitor` are private scheduler loops today. After phases 13.13–13.15, `run_sqlite_backup`, `run_telegram_reports`, and `run_photo_watcher` still own the indefinite run, but the sleep or due-time calculation lives in a helper. Those three are lifecycle loops with extracted timing. They are not in scope here.

A queue worker loop exists to drain work, not to meet a schedule. `run_notification_worker` is that kind of loop. An empty queue sleeps 0.25 seconds. Retry delay and batch window live in `NotificationWorker.process_one`. That loop may stay.

A realtime loop serves a connected client. `while True` in the dashboard WebSocket and the realtime hub is outside this RFC.

## What "retire" means here

This RFC does not authorize deleting lifecycle loops.

Phases 13.13–13.15 retired private timing ownership and kept the lifecycle `while True`. [RFC-0003](RFC-0003-backup-clock-ownership.md) left the backup `while True` in place on purpose. The phrase "broad private-loop deletion" in that RFC describes a later cleanup after a central owner exists. [refactor-scheduler.md](../refactor-scheduler.md) describes that owner as a future in-process engine that calls the current `run_*` functions and owns sleep. That engine is not this RFC. `JobExecutionWrapper` stays a start/stop wrapper.

So:

- Extracting one-iteration helpers retires private timing ownership for the two jobs below.
- It does not retire lifecycle loops.
- It does not, by itself, complete the roadmap sentence "Retire private loops."

Literal retirement of lifecycle loops needs a later accepted RFC for the future engine in the scheduler plan. Until that engine exists, deleting `while True` from a lifecycle function drops that job.

## Decision

Phase 13.16, once accepted, may only extract private timing for `offline_monitor` and `infrastructure_monitor`.

`run_offline_monitor` remains the lifecycle and the registered entry. It calls an internal helper once per pass. Proposed name, matching `run_backup_clock`, `run_report_clock`, and `run_photo_watcher_interval`:

`run_offline_monitor_interval`

One call does exactly this and returns:

```text
sleep settings.alert_evaluation_interval_seconds
    ↓
evaluate_offline_agents
    ↓
return
```

`run_infrastructure_monitor` remains the lifecycle. Proposed helper:

`run_infrastructure_monitor_interval`

One call does exactly this and returns:

```text
sleep settings.infrastructure_refresh_seconds
    ↓
refresh_infrastructure
    ↓
return
```

Neither helper loops, creates a task, or registers a job. There is no `offline_clock` job and no `infrastructure_clock` job. The registry stays six names.

`notification_worker` is out of scope. It is not a clock. A later RFC is required before its loop, poll delay, retry, or batch window changes.

`run_backup_clock`, `run_report_clock`, and `run_photo_watcher_interval` stay as implemented. This RFC does not reopen them.

## Behavior freeze

### offline_monitor

Current code in `run_offline_monitor`:

- Sleep uses `settings.alert_evaluation_interval_seconds` (default 30, bounds 5–3600) before every evaluation, including the first pass after start.
- `evaluate_offline_agents` then opens a session, calls `AlertEngine.evaluate_offline_agents`, and commits.
- If that returns events or a status change, `hub.notify_ingest(reason="offline_evaluation", agent_id=None)` runs.
- `SQLAlchemyError` is logged as `offline_evaluation_failed`. The loop continues.
- Any other exception leaves the coroutine. `JobExecutionWrapper` does not restart it.
- Sleep sits outside the `try`. Cancel during sleep propagates and skips that evaluation.

The helper must keep that order and those handlers. Sleep stays before evaluation. The lifecycle `while True` delegates to the helper and does not add a second sleep.

### infrastructure_monitor

Current code in `run_infrastructure_monitor`:

- Sleep uses `settings.infrastructure_refresh_seconds` (default 30, bounds 5–3600) before every refresh, including the first pass after start.
- `refresh_infrastructure` calls `get_infrastructure_service().refresh()`.
- When infrastructure mock is off, it records a photo snapshot from `build_photo_stats`.
- A backup snapshot is recorded when a backup item is present.
- A QNAP item triggers `sync_qnap_disk_alerts` on that item's summary. Failure is logged as `qnap_disk_alerts_failed` and does not replace the outer handler.
- The hub then publishes `overview_updated` for `photo_services_updated` and `backup_updated`.
- Any `Exception` from the thread call is logged as `infrastructure_refresh_failed`. The loop continues.
- Sleep sits outside the `try`. Cancel during sleep propagates and skips that refresh.

No QNAP login, temperature rule, or alert text changes.

### Already extracted jobs

Backup still waits until the next 02:00 Asia/Bangkok occurrence when enabled, sleeps 3600 seconds when disabled, then runs the existing once-path. Reports still sleep 60 seconds, then apply the existing hourly, daily, and weekly rules, timezone, and `last_sent` update. Photo watcher still scans first, then sleeps the existing dynamic delay, including the 5-second failure delay. Notification batching and baseline behavior stay put.

### notification_worker

Stays a queue worker: `process_one` on a thread, 0.25 second sleep when the queue is empty, existing retry delay and batch window inside `NotificationWorker`. Phase 13.16 must not turn it into a scheduled clock.

### JobExecutionWrapper

Still starts the six factories, cancels them on stop, and does not supervise, retry, or schedule. It does not gain cron or interval ownership.

## In scope

- Internal helpers `run_offline_monitor_interval` and `run_infrastructure_monitor_interval`.
- Lifecycle functions call those helpers and keep `while True`.
- Tests that lock the freeze above.

## Out of scope

- A seventh job, or renaming the six jobs.
- Deleting lifecycle `while True` from any job.
- The future central Job Engine that would own sleep for all six.
- `JobExecutionWrapper` redesign, restart policy, or retry supervisor.
- Notification queue, retry, or backoff changes.
- QNAP, Telegram, backup, report, or photo-watcher behavior.
- SQLite schema, REST, agent protocol, JWT, RBAC, dashboard.
- Essential Backup, Immich, Nginx, Tailscale, storage cleanup, AI.
- WebSocket and realtime loops.

## Implementation plan

Only after this RFC is Accepted:

1. Add the two helpers next to the existing lifecycle functions.
2. Move the current sleep-then-operation body into the helper, including the existing `try` / log behavior.
3. Leave `while True` in `run_offline_monitor` and `run_infrastructure_monitor`, each iteration one helper call.
4. Do not change factories, registry, wrapper, or the other four jobs.

## Test plan

Offline helper:

- One call returns after one sleep and one evaluation.
- Sleep uses `alert_evaluation_interval_seconds` and happens before evaluation, including the first call.
- Commit and `notify_ingest` stay in the current order.
- `SQLAlchemyError` is logged and does not escape the helper.
- Cancel during sleep propagates and does not evaluate.
- The lifecycle loop calls the helper and does not sleep on its own.

Infrastructure helper:

- One call returns after one sleep and one refresh.
- Sleep uses `infrastructure_refresh_seconds` and happens before refresh.
- Photo snapshot, backup snapshot, QNAP disk-alert sync, and hub publishes stay in the current order.
- `Exception` from refresh is logged and does not escape the helper.
- Cancel during sleep propagates and does not refresh.
- The lifecycle loop calls the helper and does not sleep on its own.

Regression:

- Registry and factories still name exactly the same six jobs.
- `notification_worker` poll, retry, and batch behavior unchanged.
- Backup clock, report clock, and photo interval tests still pass without edits to those helpers.

## Production validation

Not part of this proposal's authoring. After an accepted implementation and before calling the phase done:

- Run the backend tests and lint.
- Keep a rollback image tag of the running API before deploy.
- Recreate only the API if the image must change.
- Confirm health and that the registry is still six jobs.
- Watch at least one natural offline sleep of the configured `alert_evaluation_interval_seconds` (default 30) and one natural infrastructure sleep of the configured `infrastructure_refresh_seconds` (default 30). Do not treat startup as an immediate evaluate or refresh.
- Confirm those passes are not duplicated and not skipped.
- Confirm QNAP disk monitoring still reports, and that Telegram delivery for unrelated alerts is unchanged.

## Rollback

The implementation commit is the only code boundary. Tag the pre-deploy API image before rollout. Rollback is that image, or the previous commit, with no schema migration and no NAS or QNAP configuration change. This proposal does not create the tag.

## Risks

- Moving sleep inside the `try` would swallow cancellation or change which errors are logged.
- An extra sleep in the lifecycle would double the interval.
- Evaluating or refreshing before the first sleep would change startup.
- Treating this extraction as the end of "retire private loops" would hide the still-open central-engine step.

## Alternatives considered

Delete every `while True` now. Rejected. Nothing else would reschedule the jobs, and [job-engine.md](../job-engine.md) says that changes runtime behavior.

Build the future Job Engine in this phase. Rejected. That replaces `JobExecutionWrapper` with a scheduler, which this RFC does not allow.

Include `notification_worker` so every `while True` in the job modules looks the same. Rejected. It is a queue consumer. Its 0.25 second sleep is idle polling, not a monitor interval.

## Completion criteria

This RFC is accepted as that prerequisite. Acceptance allows the helper extraction only.

The implementation is complete only when status is Implemented and all of the following are true:

- The two helpers exist and the lifecycle loops only delegate.
- The behavior freeze above holds in tests.
- Production validation saw one natural interval of each in-scope job without an immediate first pass.
- The other four jobs and the wrapper are unchanged.
- The roadmap still does not claim that lifecycle loops are gone, or that the future central engine exists.

Completing that implementation retires private timing for offline and infrastructure monitors. It does not finish roadmap phase 6's broader "retire private loops" sentence. That sentence stays open until a later RFC introduces the engine that owns sleep.
