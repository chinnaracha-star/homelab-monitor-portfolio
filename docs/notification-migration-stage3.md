# Notification migration stage 3

**Sprint:** 13.8  
**Scope:** Notification worker Telegram text delivery.

## Existing worker architecture

Alert evaluation enqueues a `NotificationJob` on the in-memory queue. `run_notification_worker` starts from `operations.factories` when `notification_worker_enabled` is true and polls about every 0.25 seconds. `NotificationWorker` dequeues, may coalesce a batch, and calls `TelegramSender.send`. The worker owns retry: three attempts, five seconds apart, then a drop. `NotificationHistoryService.record_attempt` records each attempt. `_record_delivery` writes one `notifications` row on success or on the final drop. Photo Monitor is not on this path.

## Old call graph

```text
AlertEngine
        ↓
notification queue
        ↓
NotificationWorker
        ↓
TelegramSender
        ↓
TelegramNotifier.send_text
```

## New call graph

```text
AlertEngine
        ↓
notification queue
        ↓
NotificationWorker
        ↓
TelegramSender
        ↓
NotificationService.send_text
        ↓
TelegramNotifier.send_text
```

## Ownership

| Concern | Owner |
| --- | --- |
| Polling and startup | `run_notification_worker` |
| Queue | `NotificationQueue` |
| Retry count and delay | `NotificationWorker` (`MAX_ATTEMPTS` 3, `RETRY_DELAY_SECONDS` 5) |
| History | `NotificationHistoryService` and `_record_delivery` |
| Message text | Existing formatters, stored on the job before enqueue |
| Delivery | `NotificationService` |
| Telegram HTTP | `TelegramNotifier` |

`NotificationService` does not poll, retry, or write history.

## Resource lifecycle

Each send builds a service from settings and closes it in `finally`. That matches the previous per-send notifier. The client is not kept across polls. Closing the service closes the notifier once.

## Double delivery

`TelegramSender` calls `send_text` once per attempt. The service does not call the dispatcher and does not retry. Three worker attempts remain three Telegram attempts.

## Compatibility

Queue order, batching, the enable flag, the 0.25 second poll, and cancellation of the async loop are unchanged. A missing or invalid Telegram configuration still returns without raising, so the worker loop continues. A `TelegramNotificationError` still increments `retry_count` and requeues until three attempts.

## Rollback

In `TelegramSender.send`, construct `TelegramNotifier.from_settings` again and call `send_text` on it. No schema or dashboard change.

## Remaining stage

Stage 4 is Photo Monitor, including `sendPhoto` and the text fallback. It stays on `TelegramNotifier` until that sprint.
