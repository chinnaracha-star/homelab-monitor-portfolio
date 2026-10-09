# RFC-0002 — Job Engine execution wrapper

**Status:** Implemented
**Sprint:** 13.12
**Date:** 2026-09-28

Implemented in commit `f9e1375`. Production API image `sha256:a53e9a0b0c0b7453370eb9a33b2eef2874217c84b17a4a4ca8caccc6f8b47b36`, deployed `2026-09-28T04:36:32Z`. Final soak passed at `2026-09-28T05:13:17Z`. The accepted design below is unchanged.

## Problem

Phase 13.5 registered six jobs and did not start them. `JobEngine` in `api/src/homelab_monitor/jobs/engine.py` only stores `JobDefinition` metadata. Application startup still creates the tasks itself.

`create_app` uses `lifespan` in `api/src/homelab_monitor/main.py`. After user bootstrap and the registry validation log, lifespan calls `operations.factories(settings)` and passes each factory to `runtime_control.register_background`. On shutdown it cancels those tasks and awaits `CancelledError`. `restart_background` later cancels and replaces one named task. Operations Center uses that for `photo_watcher` and `sqlite_backup` only.

The metadata registry and the running loops are therefore two descriptions of the same six names. Phase 13.12 should make startup ask one wrapper to start those existing factories, without moving sleep, due checks, or delivery.

## Non-goals

This RFC does not include:

- schedule migration or interval redesign
- cron, APScheduler, Celery, Redis, or a separate worker service
- a persistent job queue or a new overlap or retry policy
- a dashboard scheduler page or a job editing API
- a new REST route for the engine
- notification architecture migration, including alert delivery
- backup clock, report clock, or photo clock migration
- QNAP connector, parser, TLS, timeout, or alert changes
- SQLite schema changes
- Agent protocol `0.1.0` changes
- JWT or RBAC changes

Scheduler plan phases 3–6 in `docs/refactor-scheduler.md` stay outside this RFC. Each of those later ownership changes still needs its own accepted RFC.

## Contracts touched

Execution ownership of the six existing background tasks moves from the lifespan loop to a Job Engine wrapper.

## Contracts explicitly preserved

- REST shapes, including `GET /api/v1/backup` and infrastructure payloads
- Agent protocol `0.1.0`
- JWT and roles `admin` | `operator` | `viewer`
- SQLite schema and WAL
- In-process plugins
- `NotificationService` ownership, retry owners, and Telegram text
- Backup gzip schedule, retention, and `INV-BACKUP-007` until a later scheduler RFC
- Report due rules in `telegram_reports.py`
- Photo scan interval and fallback
- QNAP behavior added in Phase 13.11
- Job names and the string fields on `JobDefinition`
- `restart_background("photo_watcher")` and `restart_background("sqlite_backup")`

Phase 13.12 changes execution ownership, not business behavior. For every job, the schedule, loop body, constructor dependencies, and notification path stay as they are. No job gains a new retry policy, overlap policy, persistence row, frequency, or error handler inside its loop.

## Current state

| Registry name | Coroutine | Start today | Timing | Depends on | Shutdown | Notification path |
| --- | --- | --- | --- | --- | --- | --- |
| `offline_monitor` | `run_offline_monitor` | `register_background` | sleep `alert_evaluation_interval_seconds`, default 30s | `Settings`, `AlertEngine`, database, realtime hub | cancelled with the lifespan task list | alert engine only |
| `infrastructure_monitor` | `run_infrastructure_monitor` | same | sleep `infrastructure_refresh_seconds`, default 30s | infrastructure service, ops history, QNAP disk alert sync | same | none for Telegram; QNAP alert sync stays inside the existing refresh |
| `telegram_reports` | `run_telegram_reports` | same | sleep 60s, then due check | report settings, `NotificationService.send_text` through the dispatcher | same | scheduled reports |
| `notification_worker` | `run_notification_worker` | same | returns immediately when disabled; otherwise poll about every 0.25s | in-memory queue, `NotificationService.send_text` | same; a returned task is already finished | queued alert text |
| `photo_watcher` | `run_photo_watcher` | same | returns when disabled; otherwise scan interval, default 5s | photo settings and watcher service | same, and `restart_background` can replace this one task | `send_photo`, then `send_text` fallback |
| `sqlite_backup` | `run_sqlite_backup` | same | 3600s while backup is disabled; otherwise sleep until the next Bangkok backup time | backup settings and gzip functions | same, and `restart_background` can replace this one task | `NotificationService.send_text` from the existing backup notify path |

`JobDefinition` stays frozen metadata: name, description, category, implementation string, schedule string, enabled string, and owner. It does not hold a callable today. This RFC does not add one. Two competing definitions would be worse than a name check.

The wrapper therefore takes the existing `factories(settings)` map and checks that its keys equal the names from `default_engine().jobs()`. The registry remains the description. The factory map remains the executable. Both must name the same six jobs.

## Proposed change

```text
application lifespan
    ↓
Job Engine wrapper.start(settings)
    ↓
factories(settings) checked against registry names
    ↓
existing register_background(name, factory) for each name
```

Shutdown:

```text
wrapper.stop()
    ↓
cancel the tasks the wrapper started
    ↓
await cancellation
    ↓
drop those task references
```

`register_background` remains the function that stores the factory and creates the task. `restart_background` remains the function that replaces one live task. Operations Center still calls it for `photo_watcher` and `sqlite_backup` only. The wrapper does not reimplement that restart and does not block it.

Lifespan calls `start` once. A second `start` while that start is still in effect does not create another task for any name, including a task that has already returned or failed. It is not a supervisor and it does not revive finished work. `start` after a completed `stop` is not used by lifespan. This phase does not add a restart-all cycle. Stop before start, and a second stop, do nothing.

Startup today builds the task list before the `try` that yields. If a later `register_background` raises, the assignment never finishes, so the `finally` block does not run and lifespan does not cancel the tasks already created. The exception fails application startup. Those earlier tasks are not rolled back by application code. The wrapper must do the same: let the exception propagate, do not call `stop` from the failure path, and do not cancel the earlier tasks inside `start`. There is no cancel timeout today. Shutdown, once `yield` has begun, cancels each task, awaits it, and suppresses `CancelledError`. The wrapper's `stop` does only that. It does not add a timeout or a new shutdown framework.

A job that returns because it is disabled stays finished. A job whose coroutine raises outside its own loop ends that task only. Nothing gathers the six tasks, so one failure does not cancel the others. The wrapper does not add a `TaskGroup`, a retry, or a restart. Today's loops already catch their own tick errors and keep sleeping. Those handlers stay inside the loops.

Logs use the existing logger style. The wrapper may log that a managed task started, that shutdown cancelled it, and that a task ended with an exception. It does not add a metric table, a REST status route, or a dashboard page.

## Test plan

Tests run against the wrapper and the existing suite. They do not send Telegram.

- Registry: the six names above stay registered and unchanged.
- Startup: `start` creates one task per name.
- Duplicate start: a second `start` does not add tasks.
- Shutdown: every task created by that start is cancelled and awaited.
- Repeated stop: a second `stop`, and `stop` before `start`, do not raise.
- Behavior: schedule strings, report due checks, backup sleep, photo interval, and notification call paths are still the current functions.
- Failure: a task that raises is not replaced, and the other tasks are not cancelled. A failed `start` propagates and does not call `stop`.
- Existing backend tests still pass, including job registry validation and the operations restart of `sqlite_backup` and `photo_watcher`.

## Rollout

1. Tests listed below pass. No test sends a real Telegram message.
2. Build a new API image and keep the previous API image as a rollback tag.
3. Deploy the API only. The dashboard stays on its current image unless a later change actually touches dashboard code.
4. Check `/health`, agent check-ins, and that each of the six names has one task.
5. Confirm scheduled reports are not sent twice and that backup and photo loops still log their current start lines.
6. If a second copy of a loop appears, or shutdown hangs, redeploy the previous API image. Lifespan then calls `factories` directly again.

Rollback does not need a database downgrade, a data conversion, an API change, or an agent upgrade. The wrapper is process-local task ownership.

## How to tell it failed

- More than one task exists for the same job name.
- A disabled worker or watcher is restarted in a loop.
- Report, backup, or photo timing changes.
- Cancelling the process leaves a job running.
- One job's exception cancels an unrelated job.
- `restart_scheduler` or `restart_photo_monitor` no longer replaces only its own task.

## Documentation debt

`docs/architecture-freeze.md` still says Phase 13 has not started. Git history from `eaff792` through `516a50c` shows that Phase 13 is in progress. This RFC does not edit that file. Correcting the freeze note is a separate documentation change.

## Later work

`docs/refactor-scheduler.md` phases 3–6 remain later RFCs: the backup clock, the report clock, the photo interval, and retiring private loops after a production release. Phase 13.12 only wraps the current start and stop.
