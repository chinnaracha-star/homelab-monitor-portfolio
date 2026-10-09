# Notification migration stage 4

**Sprint:** 13.9  
**Scope:** Photo Monitor Telegram delivery. This completes the planned notification migration.

## Current Photo Monitor architecture

`run_photo_watcher` scans watch folders, ignores video extensions, and keeps the baseline so already-seen files are not sent again. New images become pending events. After the batch window, `flush_photo_notifications` sends one message per file. Caption text comes from `format_new_photo_message`. `retry_transient` retries transient Telegram errors. A photo send that still fails falls back to the same caption as text. Seen state is updated by the existing scan and `mark_telegram_sent` paths, not by the delivery facade.

## Old delivery call graph

```text
PhotoWatcherService._deliver_photo_group
        ↓
TelegramNotifier.send_photo
        ↓
on failure: TelegramNotifier.send_text
```

## New delivery call graph

```text
PhotoWatcherService._deliver_photo_group
        ↓
NotificationService.send_photo
        ↓
TelegramNotifier.send_photo
        ↓
on failure, still inside the watcher:
NotificationService.send_text
        ↓
TelegramNotifier.send_text
```

Tests may inject a `send_text` callable. That injection remains the fallback sender, as it did before.

## Ownership

| Concern | Owner |
| --- | --- |
| Scan, baseline, deduplication, video filter | Photo watcher |
| Caption | `format_new_photo_message` |
| Fallback policy | Photo watcher, one layer |
| Transient retry | `retry_transient` around each send |
| Delivery | `NotificationService` |
| Telegram HTTP | `TelegramNotifier` |

`send_photo` does not catch errors, so a failure still reaches the watcher fallback. The service does not send a second message.

## Lifecycle

The watcher still creates one notifier for a flush and reuses it for every file in that flush. It does not close that client. `NotificationService.close` is not called on this path, so the client is not closed twice and is not closed between photos. The unclosed client is existing behavior.

## Rollback

In `flush_photo_notifications` and `_deliver_photo_group`, call `notifier.send_photo` and `notifier.send_text` again and stop wrapping the notifier. No baseline reset and no schema change.

## Completion

Backup, scheduled reports, the notification worker, and Photo Monitor now deliver through `NotificationService`. Remaining direct `TelegramNotifier` construction is the transport itself, Operations Center telegram test, and alert-provider setup in `notifications/config.py`. Those were not migrated in this sprint.
