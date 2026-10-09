# Notification migration completion

Stages 1–4 are complete. The frozen baseline is [notification-architecture.md](notification-architecture.md).

## Sprint 13.6 — Backup

- Old: `sqlite_backup._notify` → `TelegramNotifier.send_text`
- New: `_notify` → `NotificationService.send_text` → `TelegramNotifier.send_text`
- Guarantee: same backup text, no history row, errors stay inside `_notify`
- Regression: passed in the stage suite and again after later stages
- Debt: none new. Details in [notification-migration-stage1.md](notification-migration-stage1.md)

## Sprint 13.7 — Scheduled reports

- Old: dispatcher → `TelegramProvider.send` → `TelegramNotifier.send_text`
- New: dispatcher → `NotificationService.send_text` → `TelegramNotifier.send_text`
- Guarantee: same report text, same recipients, retry and history stay in the dispatcher
- Regression: passed
- Debt: the dispatcher still builds a `TelegramProvider` so it can close the shared client. Details in [notification-migration-stage2.md](notification-migration-stage2.md)

## Sprint 13.8 — Notification worker

- Old: `TelegramSender` → `TelegramNotifier.send_text`
- New: `TelegramSender` → `NotificationService.send_text` → `TelegramNotifier.send_text`
- Guarantee: same job text, queue, three retries at 5 seconds, and the same history writers
- Regression: passed
- Debt: a new HTTP client per job, which matches the previous notifier. Details in [notification-migration-stage3.md](notification-migration-stage3.md)

## Sprint 13.9 — Photo Monitor

- Old: watcher → `send_photo`, then `send_text` on failure
- New: watcher → `NotificationService.send_photo` / `send_text` → `TelegramNotifier`
- Guarantee: same caption, same fallback owner, same transient retry, baseline unchanged
- Regression: 346 pytest tests passed after this stage, with 201 frontend tests
- Debt: the flush notifier is still not closed. Details in [notification-migration-stage4.md](notification-migration-stage4.md)

## Not migrated

Alert delivery, the Operations Center Telegram test, and notifier construction stay direct. They are listed in the architecture document and in [notification-technical-debt.md](notification-technical-debt.md).
