# RFC-0005 — Photo Watcher interval ownership

**Status:** Implemented
**Sprint:** 13.15
**Date:** 2026-09-29

Scheduler refactor phase 5 from [refactor-scheduler.md](../refactor-scheduler.md). Implemented in commit `5940ad9`. Controlled production validation passed. The accepted design below is unchanged.

## Implementation

`JobExecutionWrapper` still starts one `photo_watcher` factory. `run_photo_watcher` remains the lifecycle owner and repeatedly calls the internal `run_photo_watcher_interval` helper. One helper invocation runs the supplied scan/flush operation, normalizes its dynamically calculated delay, sleeps that delay, and returns. It has no lifecycle loop or task creation.

```text
JobExecutionWrapper
    ↓
photo_watcher
    ↓
run_photo_watcher                 (lifecycle loop)
    ↓
run_photo_watcher_interval        (one normal interval)
    ↓
scan/flush → dynamic delay → sleep → return
```

The first scan remains immediate. Configured values remain 5, 10, 30, and 60 seconds, with 5 seconds as the fallback. Pending batch state can still shorten the effective delay. Baseline priming and persistence, `photo_baseline.json`, notification delivery through `NotificationService`, per-folder errors, lifecycle recovery, and cancellation propagation are unchanged. Registry and factories remain six. `photo_watcher` remains the only photo job; the helper is not a registered job.

Implementation validation: 67 focused tests and 400 full backend tests passed, with 0 failures and 0 skips. Ruff check, Ruff format check, `git diff --check`, and architecture review passed.

The API-only production deploy was `2026-09-29T08:32:25Z` (`2026-09-29T15:32:25+07:00`), image `sha256:02ea247ed246d1c0865b39817b9a7608e177f04dc856d59c90f9ad637f8b1290`, container `1839a7c2b71d`. Configured interval was 10 seconds. Startup, baseline restore, and `photo_watcher_tick` were observed at about `08:32:30Z`; the first normal `photo_watcher_sleep` followed at `08:33:23Z`. Natural cycles then slept 10 seconds at `08:33:23Z`, `08:34:23Z`, and `08:35:22Z`. The API stayed healthy with restart count 0.

Dynamic shortened delay was not manufactured in production; automated tests cover it. `photo_baseline.json` remained present, six folders restored, and persistence continued. No artificial notification was triggered. One natural photo event occurred and Telegram delivery succeeded. Registry/factory health remained 6/6 with no interval or clock job. Dashboard container `5a8dee57e811` stayed healthy, restart count 0, and was not recreated. Rollback tag `homelab-monitor-api:rollback-phase13.15-predeploy` remains retained.

One HTTP agent check-in encountered `database is locked`, represented by two traceback headers/text occurrences. The same pattern existed before this deployment. It was not logged as `photo_watcher_failed`, and available evidence does not attribute it to Photo Watcher interval ownership. Root cause and remediation remain outside this RFC.

## Problem

`run_photo_watcher` currently owns the lifecycle loop, scan invocation, dynamic delay calculation, and sleep:

```text
JobExecutionWrapper
    ↓
photo_watcher factory
    ↓
run_photo_watcher
    while True:
        _scan_and_interval
            PhotoWatcherService.scan_once
            calculate dynamic delay
        sleep(delay)
```

The first scan is immediate. Sleep occurs after the scan. This differs deliberately from Report Clock, which sleeps before its tick. Phase 13.15 separates interval ownership without changing this observable behavior.

## Decision

`run_photo_watcher` remains the sole lifecycle owner and the Job Engine entrypoint. Introduce an internal single-iteration helper named `run_photo_watcher_interval`.

One helper invocation represents:

```text
scan and flush
    ↓
obtain the existing dynamically calculated delay
    ↓
sleep that delay
    ↓
return
```

`run_photo_watcher` repeatedly invokes the helper. The helper has no `while True`, `create_task`, `TaskGroup`, job registration, supervisor loop, or wall-clock schedule. The implementation must preserve existing health logging and exception ownership rather than move boundaries merely for symmetry.

## Startup invariant

The first scan remains immediate. There is no initial sleep:

```text
start
    ↓
scan
    ↓
dynamic sleep
    ↓
next scan
```

Changing this to sleep then scan is incompatible.

## Dynamic interval invariant

The configured value remains `PhotoEventSettings.scan_interval_seconds`, normalized by `_next_interval`.

- Allowed configured values: 5, 10, 30, and 60 seconds.
- Default: 5 seconds.
- Invalid or unsupported values fall back to 5 seconds.
- The effective sleep can be shorter than the configured value when `pending_flush_delay` requires pending batch-window work sooner.

The helper consumes the existing dynamic result from `_scan_and_interval`. It must not replace it with a fixed interval.

## Scan and baseline invariants

One scan keeps the existing behavior: inspect configured mounted photo folders, compare files with the baseline, record photo events, prune according to current settings, flush due notifications, persist dirty baseline state, and calculate the next delay.

No changes are made to:

- mounted-folder sources or scan algorithm
- process-start freshness rules
- folder priming
- in-memory baseline state
- `photo_baseline.json` format or location
- baseline persistence timing
- restart semantics
- database schema

For an unprimed folder, files older than process start remain baseline entries without notification. Files created at or after process start remain eligible as fresh under current rules.

## Notification invariants

The path remains:

```text
PhotoWatcherService.flush_photo_notifications
    ↓
NotificationService
    ↓
TelegramNotifier
```

Photo notifications do not move to `notification_worker`. Message formatting, batching, retries, delivery state, and notification ownership do not change.

## Error and cancellation invariants

Exception ownership remains with the `run_photo_watcher` lifecycle:

- `CancelledError` is logged and re-raised during scan or sleep.
- A lifecycle-level scan exception logs `photo_watcher_failed`, selects the existing 5-second recovery delay, sleeps, and continues.
- Per-folder exceptions remain isolated inside `scan_once`; other folders continue.
- A non-cancellation sleep failure must not acquire a new supervisor or retry behavior.

The helper must fit inside these existing boundaries. Moving broad exception handling into a generic scheduler abstraction is out of scope.

## Job Engine invariants

The registry and factories remain six jobs. The job remains:

```text
name: photo_watcher
entrypoint: homelab_monitor.photo_watcher.run_photo_watcher
owner: photo_watcher
```

`run_photo_watcher_interval` is an internal helper, not a Job Engine job. There is no `photo_clock`, `photo_interval`, or `photo_watcher_interval` registration and no seventh job.

## Non-goals

- Phase 13.16 or retiring remaining private loops
- a generic scheduler framework
- wall-clock or cron scheduling
- sleep before the first scan
- changing interval options
- changing photo sources or adding QNAP/Immich API dependencies
- changing scan, baseline, batching, or notification behavior
- database or baseline migration
- notification architecture changes
- adding a Job Engine job

## Alternatives considered

### Sleep before scan

Rejected. It delays the first scan and changes startup behavior.

### Fixed scheduler interval

Rejected. `pending_flush_delay` can require a sleep shorter than `scan_interval_seconds`.

### Separate Photo Clock Job Engine job

Rejected. It creates a seventh job and risks two owners evaluating the same photo state.

### Keep lifecycle and interval combined

Safe as a rollback, but it does not complete Phase 5 ownership separation.

### Force one generic clock abstraction

Rejected. Backup, Report, and Photo have different first-run semantics. Report is sleep then tick; Photo is scan then dynamic sleep.

## Test plan

Implementation must prove:

1. The first scan occurs before the first sleep.
2. One `run_photo_watcher_interval` call performs exactly one scan/delay/sleep iteration and returns.
3. The helper contains no lifecycle loop or task creation.
4. Configured values 5, 10, 30, and 60 remain valid.
5. Invalid values still fall back to 5.
6. Pending batch work still shortens the effective sleep.
7. `run_photo_watcher` remains the lifecycle loop.
8. Cancellation during scan or sleep propagates.
9. `photo_watcher_failed` recovery remains a 5-second wait followed by another lifecycle iteration.
10. Baseline priming, persistence, and restart behavior remain unchanged.
11. Notification delivery remains through `NotificationService`.
12. Registry and factories remain six with no photo interval job.
13. Existing Photo Monitor reliability and duplicate-prevention tests remain green.

## Production validation

Use a controlled API-only deployment. Do not manufacture a photo event solely for validation.

Verify API health and restart count, registry/factory 6/6, one `photo_watcher` job, no photo interval job, startup followed by an initial scan before the first interval sleep, subsequent natural scan/sleep cycles, delay values consistent with settings and pending batch state, baseline load/restore evidence, and no new `photo_watcher_failed`, task, or coroutine errors. Confirm no unexpected notification and no QNAP or Immich dependency.

If end-to-end new-photo delivery requires a real event, perform it later as a separately controlled validation.

## Rollback

Roll back to the previous API image or implementation. No schema rollback, baseline migration rollback, notification migration rollback, or state reset is required. The existing `photo_baseline.json` and photo-event rows remain readable.

## Acceptance

Phase 13.15 implementation matches this RFC only when:

- `run_photo_watcher` remains the lifecycle owner.
- `run_photo_watcher_interval` is one scan-then-dynamic-sleep iteration.
- The first scan remains immediate.
- Dynamic batch-aware sleep remains intact.
- Baseline, notification, error, and cancellation semantics remain intact.
- Registry/factories remain six and no new job is added.
- Tests and a later controlled production validation pass.
- Phase 13.16 remains out of scope.
