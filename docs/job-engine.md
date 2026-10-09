# Job engine

**Sprint:** 13.5 registry, 13.12 execution wrapper
**Status:** Metadata registry plus lifespan ownership. Not a generalized scheduler.

## Current architecture

`JobEngine` still only stores `JobDefinition` metadata. `JobExecutionWrapper` in `jobs/execution.py` creates and stops the six background tasks during application lifespan. It checks `operations.factories(settings)` against `default_engine().jobs()` before calling `register_background`. Sleep, due checks, and delivery stay in the existing loops.

| Job | Loop |
| --- | --- |
| offline_monitor | `run_offline_monitor` |
| infrastructure_monitor | `run_infrastructure_monitor` |
| telegram_reports | `run_telegram_reports` |
| notification_worker | `run_notification_worker` |
| photo_watcher | `run_photo_watcher` |
| sqlite_backup | `run_sqlite_backup` loop, `run_backup_clock` once per pass, then `run_backup_once` |

Lifespan calls `jobs.start(settings)` before `yield`. Shutdown is `hub.stop()`, then `await jobs.stop()`. A second `start()` while that start is active does not create more tasks and does not revive a finished or failed task. `stop()` cancels the tasks from the successful start and the current `runtime_control` task for each of those names, including one replaced by `restart_background`. One running task failure does not cancel the others. There is no `TaskGroup`, retry loop, or persistent scheduler.

If a later registration raises, the exception propagates, the wrapper does not mark itself started, `start()` does not call `stop()`, and earlier tasks from that attempt are not cancelled. That matches [RFC-0002](rfc/RFC-0002-job-engine-execution-wrapper.md).

## Target architecture

```text
Application lifespan
    ↓
JobExecutionWrapper
    ↓
Job registry names checked against operations.factories
    ↓
Existing loop (still owns timing and delivery)
```

A later scheduler that owns intervals is a separate RFC. See [refactor-scheduler.md](refactor-scheduler.md).

## Registry

`default_engine()` registers the six jobs above. Each `JobDefinition` has name, description, category, current implementation, schedule text, enabled flag, and owner. Execution stays in the named function.

## Categories

Every job uses one of:

- Monitoring
- Notification
- Backup
- Reporting
- Maintenance
- Infrastructure

Maintenance is reserved for future work. A new job must use one of these names.

## Lifecycle

Documented states only. The engine does not transition them.

```text
Registered
    ↓
Enabled
    ↓
Running
    ↓
Paused
    ↓
Stopped
    ↓
Disabled
```

Today every factory job is started with the process. Pause, stop, and disable are not implemented here.

## Migration phases

1. Metadata registry. Done in Phase 13.5.
2. Startup checks registry names and still calls the same factories. Done in Phase 13.12 as `JobExecutionWrapper`.
3. Backup clock only. Done in Phase 13.13 under [RFC-0003](rfc/RFC-0003-backup-clock-ownership.md).
4. Report clock only. Done in Phase 13.14 under [RFC-0004](rfc/RFC-0004-report-clock-ownership.md).
5. Photo Watcher interval only. Done in Phase 13.15 under [RFC-0005](rfc/RFC-0005-photo-watcher-interval-ownership.md). `photo_watcher` remains the registered job and `run_photo_watcher` remains its lifecycle. `run_photo_watcher_interval` is an internal helper, not a job. Registry and factories remain six.

## Phase 13.12 production checkpoint

Complete, deployed, and soak passed. Commit `f9e1375`. API image `sha256:a53e9a0b0c0b7453370eb9a33b2eef2874217c84b17a4a4ca8caccc6f8b47b36`, deployed `2026-09-28T04:36:32Z`. Soak at `2026-09-28T05:13:17Z` (about 37 minutes): API healthy, restart count 0, registry 6/6, startup once, no lifecycle traceback. One natural `hourly_report` at `2026-09-28 05:01:02` UTC, status `sent`, with no second row in that window. The notification row does not store the message body.

Live task count is inferred from the health registry, a single startup, and that one report. It was not read from an asyncio task dump. The soak did not call `restart_background`; tests cover shutdown of a replaced task. Photo watcher kept ticking and had no new photo event. Backup logged one start and a sleep of about 51802 seconds, so a backup run was not due. `monitor` stayed online. QNAP stayed healthy as `Chin-HomeNas` / `TS-X53B`, four disks, thresholds 55°C / 60°C, with storage percent, SMART, manufacturer, disk model, and capacity still null. Dashboard stayed on `sha256:0e5486e2f0379c3a3f30b21d16538b518c85427cdc714cec716800472ad201f8`. Rollback image `homelab-monitor-api:rollback-phase13.12-predeploy` is `sha256:27eadf9bfa71e3b53dce7bd6d55e21b72083bede444b4e5a974d99ea6a965916`. Phase 13.11 rollback tags and the QNAP recovery copies under `/tmp/homelab-qnap-recovery` and `~/homelab-qnap-recovery` stay in place. No credential leak was seen in post-deploy logs. No manual report, backup, photo scan, or Docker prune was used for the soak.

## Phase 13.13 production checkpoint

Backup clock is implemented in commit `477a355`. Natural backup production validation passed. The running API at that check was container `bee766186df8`, image `sha256:9f2518a3734436b06286d86dde11e10dc7b9d7290beea3bc3b9078124dc272f2`, not the first Phase 13.13 image `sha256:ed87de5f751a0bca2690c2ad778e458c0bc051af725ed6d5afaf759fcfea487b`. One natural backup completed `2026-09-28T19:00:04Z`, integrity `PASS`, artifact 11,770,422 bytes, then the same lifecycle slept `86396` seconds. Scheduler start count stayed 1 and API restart count stayed 0. A single lifecycle is inferred. Report clock and photo interval are not migrated. Live QNAP was not configured in that runtime. Details are in [RFC-0003](rfc/RFC-0003-backup-clock-ownership.md).

## Phase 13.14 production checkpoint

Report clock is implemented in commit `ab23831`. Natural hourly production validation passed. API image `sha256:afd8282c119ae07f490c72c2587be860d0453889365ff06401bdeaf9c25414ed`, deployed `2026-09-29T05:07:37Z`. The 13:00 Asia/Bangkok slot produced one `sent` hourly row, `cbb105d3-c470-4f59-91f0-feb3722f5a24`, at `2026-09-29 06:01:06` UTC. The 14:00 slot produced one `sent` row at `2026-09-29 07:00:30` UTC. Hourly `last_sent` advanced from `2026-09-29T05:00:39.335089+00:00` to `2026-09-29T07:00:07.045860+00:00`. Container `f135f0e4812d`, started `2026-09-29T07:10:27Z` for an unrelated dashboard URL change, stayed healthy with restart count 0 and did not resend the 14:00 slot. No `report_clock` job was added. Photo interval is not migrated. Details are in [RFC-0004](rfc/RFC-0004-report-clock-ownership.md).

## Phase 13.15 production checkpoint

Photo Watcher interval ownership is implemented in commit `5940ad9`. API image `sha256:02ea247ed246d1c0865b39817b9a7608e177f04dc856d59c90f9ad637f8b1290`, deployed `2026-09-29T08:32:25Z`. Container `1839a7c2b71d` stayed healthy with restart count 0. With a configured 10-second interval, production logged startup/baseline restore/tick before the first sleep, then three natural `photo_watcher_sleep seconds=10` cycles. The first scan remained immediate. Dynamic shortened delay was covered by tests and was not artificially induced in production.

Baseline state remained present and restored six folders. No artificial photo notification was triggered; one natural photo event delivered successfully. Registry and factories remained 6/6. `photo_watcher` remains the registered job, and no photo interval or clock job exists. Dashboard container `5a8dee57e811` was not recreated. The rollback tag `homelab-monitor-api:rollback-phase13.15-predeploy` remains retained. One pre-existing HTTP agent check-in database-lock pattern recurred and was not attributed to Photo Watcher interval ownership. Details are in [RFC-0005](rfc/RFC-0005-photo-watcher-interval-ownership.md).

## Future scheduler replacement

One coordinator can own the six loops. It must keep `alert_evaluation_interval_seconds`, `infrastructure_refresh_seconds`, the 60-second report tick, the notification poll, the photo scan interval, and the backup delay. Removing a loop before that parity check would change runtime behavior.
