# Notification facade

**Sprint:** 13.3  
**Status:** Facade added. No caller uses it yet.

## Facade

`NotificationService` in `notifications/service.py` holds a `TelegramNotifier` and forwards `send_text` and `close`. `from_settings` uses `TelegramNotifier.from_settings`, so a missing token still returns no service.

It does not format messages, retry, write history, or send photos. Those stay in the modules that already do them.

## Provider

`NotificationProvider` in `notifications/provider.py` is the existing interface: `channel`, `recipient`, `send`, and `close`. `TelegramProvider` is the default implementation and still calls `TelegramNotifier.send_text`. Discord, Slack, and email providers stay unused by this sprint. Nothing replaces Telegram.

## Notification types

Types are names for future facade calls. Sprint 13.3 does not route by type.

| Type | Current sender | Behavior that must stay |
| --- | --- | --- |
| Alert | `TelegramNotifier` alert path and the notification worker | Queue, retry, history row |
| Photo | `photo_watcher.py` via `photo_telegram.py` | `sendPhoto`, then `sendMessage` if that fails |
| Backup | `sqlite_backup.py` | Same backup text |
| Scheduled report | `telegram_reports.py` | Hourly, daily, weekly due rules and one history update per send |
| Test report | Report service test kind and Operations Center test send | Same text as today |
| Plugin | Plugin record only | Plugins do not send by themselves |

New types may be added later. Existing types are not renamed or removed without an RFC.

## Compatibility

History schema, retry counts, deduplication, photo fallback, and scheduled reports are unchanged because no caller was switched.
