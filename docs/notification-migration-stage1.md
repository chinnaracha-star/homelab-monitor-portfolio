# Notification migration stage 1

**Sprint:** 13.6  
**Scope:** SQLite backup text only.

## Current flow

`sqlite_backup._notify` built a `TelegramNotifier` from settings and called `send_text` with `format_backup_telegram`. Missing configuration returned quietly. `TelegramNotificationError` was logged as `backup_telegram_failed` and did not escape. The notifier was closed afterward. This path did not write a notification-history row and did not retry inside `_notify`.

## New flow

`_notify` builds a `NotificationService` and calls `send_text` with the same string. The service forwards to `TelegramNotifier.send_text` and `close`. The same logs and the same swallowed errors remain.

```text
sqlite_backup._notify
        ↓
NotificationService.send_text
        ↓
TelegramNotifier.send_text
```

## Migration scope

Only `_notify` in `sqlite_backup.py`. Photo Monitor, the notification worker, scheduled reports, alert sends, and the Operations Center Telegram test still call `TelegramNotifier` directly.

## Compatibility guarantees

- Success and failure message text is still `format_backup_telegram`.
- Backup disabled still skips the send inside the backup loop and does not change this text path.
- Manual and scheduled backups both call `run_backup_once`, which calls `_notify` when `notify` is true.
- No history row is added, so recipient, channel, status, retry, and timestamp records are unchanged.
- Telegram disabled, a missing service, configuration errors, and send timeouts stay inside `_notify`.

## Rollback

Point `_notify` back at `TelegramNotifier.from_settings` and `send_text`. No schema change to undo.

## Future stages

| Stage | Caller | Note |
| --- | --- | --- |
| 2 | Scheduled reports | Keep due rules and one history update per send |
| 3 | Notification worker | Keep queue retry and history |
| 4 | Photo Monitor | Last. Keep `sendPhoto`, then text fallback |
