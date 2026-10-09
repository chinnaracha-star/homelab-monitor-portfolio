# Notification consolidation plan

**Sprint:** 13.2  
**Status:** Plan only. Callers are unchanged.

## Current architecture

Telegram sends do not share one service. Each caller builds a `TelegramNotifier` or wraps it:

| Path | Role |
| --- | --- |
| `telegram.py` | `TelegramNotifier`: Bot API, alert text, `send_text` / `send_photo` |
| `notifications/telegram.py` | `TelegramProvider` adapts the notifier to the notification worker's `send()` |
| `notifications/dispatcher.py` | Chooses a provider and records delivery rows |
| `notification_worker.py` | Drains the queued notification jobs |
| `photo_telegram.py` | Caption text for one photo |
| `photo_watcher.py` | Sends the photo, then falls back to text |
| `telegram_reports.py` | Hourly, daily, weekly, and test reports |
| `sqlite_backup.py` | Backup result text |
| `operations.py` | Operations Center test send |

Message shape, retry, and history are different in each path. Photo delivery can fall back from `sendPhoto` to `sendMessage`. Reports and alerts do not use that fallback.

## Target architecture

One `NotificationService` facade in front of the existing `TelegramNotifier`.

```text
Caller (alerts, photos, reports, backup, operations)
        ↓
NotificationService
        ↓
TelegramProvider  →  TelegramNotifier  →  Bot API
        ↓
Existing notification history row
```

The facade accepts a channel, a purpose (`alert`, `photo`, `report`, `backup`, `test`), and a payload the current formatters already produce. It does not format messages itself in the first step. Photo fallback stays inside the photo caller until a later phase moves it behind the facade without changing the Telegram text.

Plugin API v1 is not the transport. The `telegram` plugin remains an adapter record.

## Migration steps

1. Add `NotificationService` that delegates `send_text` to the current notifier. No caller switches yet.
2. Point the operations test send at the facade. Compare the Telegram text with today's message.
3. Point backup notices, then the notification worker, then reports.
4. Point Photo Monitor last. Keep `sendPhoto` then `sendMessage` and the same caption.
5. Leave `TelegramNotifier` in place as the Bot API client. Do not delete it in the same change as the move.

Each step is one sprint and needs the regression suite green before the next caller moves.

## Compatibility strategy

- REST, agent protocol, SQLite, JWT, and RBAC stay as they are.
- Existing functions keep their names until the caller has switched and a follow-up RFC allows removal.
- Telegram text, buttons, and photo captions stay as they are unless an RFC says otherwise.
- Sprint 13.2 does not add the facade. An unused type would not change behavior, and wiring any caller would. The first implementation sprint adds it and switches no caller in the same change.

## Risk assessment

| Risk | Level | Note |
| --- | --- | --- |
| A shared retry policy drops photo fallback | High | Photo path moves last and keeps its own fallback until tests cover both sends |
| Two history rows for one send | Medium | The facade must call the existing history write, not add another |
| Report scheduler and worker both send | Medium | Do not merge those loops in the notification sprint |
| Token handling diverges | Low | The facade reads the same `Settings` fields |
