# Architecture review

**Sprint:** 13.1  
**Scope:** Findings only. Nothing in this review was refactored.

Reviewed against the tree at product version `1.0.0-rc3`. Contracts from the Phase 12 freeze still hold.

## Duplicated services

- Analytics, trends, capacity, insights, and predictions each load `metric_history` for overlapping windows. Predictions call trends, and trends call analytics, so one dashboard page issues several reads of the same rows.
- Backup exists twice: the SQLite gzip job in `sqlite_backup.py`, and the read-only Backup connector in `connectors/backup.py` used by `GET /api/v1/backup`. The page can show connector status that is not the gzip job.
- Production health (`/api/v1/system/health`) and liveness (`GET /health`) answer different questions and both stay. They are easy to confuse in the UI.

## Duplicated schedulers

There is no second scheduler process. Timing is still split:

- `operations.factories` starts six asyncio loops in the API process.
- `sqlite_backup.py` has its own sleep loop and log line `sqlite_backup_scheduler_started`.
- `telegram_reports.py` decides hourly, daily, and weekly due times inside `telegram_reports`.
- Photo Monitor uses its own scan interval, separate from the report clock.

`restart_scheduler` in Operations Center reschedules the backup loop only.

## Duplicated configuration loading

- Process settings load once through `Settings` and `.env`.
- Notification and photo monitor settings are loaded again from SQLite on each relevant request or scan.
- Plugin `config.json` is loaded by `plugin_manager` and is not part of `Settings`.
- Public URL checks load `shared/public-url-rules.json` on the API and the same file in the dashboard build.

That split is intentional today. It is duplication of loaders, not a second source of truth for secrets.

## Duplicated notification paths

Telegram delivery does not go through one function:

- `telegram.py` — `TelegramNotifier` for alerts and direct sends
- `notifications/telegram.py` — `TelegramProvider` for the notification worker
- `notification_worker.py` — queue drain
- `photo_telegram.py` plus `photo_watcher.py` — per-photo send, with text fallback
- `telegram_reports.py` — scheduled reports
- `sqlite_backup.py` and `operations.py` — backup notices and the operations test send

The dashboard also has two notification screens (`/notifications` and `/monitoring/notifications`), matching debt item M1.

## Not in this sprint

No service was merged, no scheduler was unified, and no notification path was redirected. Follow-up needs an accepted RFC if it changes behavior.
