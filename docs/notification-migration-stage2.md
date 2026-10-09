# Notification migration stage 2

**Sprint:** 13.7  
**Scope:** Hourly, daily, weekly, and test report delivery.

## Migration scope

`dispatch_telegram_report` and report retries in `retry_notification` send through `NotificationService`. Report builders, due rules, and `run_telegram_reports` are unchanged. The notification worker, alert dispatch, Photo Monitor, and SQLite backup notification behavior are unchanged.

## Old flow

```text
TelegramReportService.build
        ↓
dispatch_telegram_report
        ↓
TelegramProvider.send
        ↓
TelegramNotifier.send_text
```

History and the three-attempt retry lived in the dispatcher.

## New flow

```text
TelegramReportService.build
        ↓
dispatch_telegram_report
        ↓
NotificationService.send_text
        ↓
TelegramNotifier.send_text
```

`_deliver` still retries. `_record` still writes one history row. `NotificationService` does not retry and does not write history.

## Responsibility boundaries

| Owner | Responsibility |
| --- | --- |
| TelegramReportService | Report text |
| Scheduler (`process_due_reports`, 60s tick) | When a report is due |
| NotificationService | Delivery call |
| TelegramNotifier | Telegram HTTP |
| Dispatcher | Retry, history, skipped when Telegram is not configured |

## Compatibility

Message text is the builder return value, passed through unchanged. Recipients stay `hourly_report`, `daily_report`, `weekly_report`, and `test_report`. Channel stays `telegram`. Status stays `sent`, `failed`, or `skipped`. A failed send retries inside `_deliver` and stores one row. Manual retry rebuilds that report and updates the same row. `POST /api/v1/notifications/test-report` is unchanged.

## Rollback

In `notifications/dispatcher.py`, pass the Telegram provider to `_deliver` again in `dispatch_telegram_report` and in the report branch of `retry_notification`. Remove `_ReportDelivery`. No schema change.

## Remaining stages

| Stage | Caller |
| --- | --- |
| 3 | Notification worker |
| 4 | Photo Monitor, last, including photo fallback |
