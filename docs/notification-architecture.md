# Notification architecture

**Status:** Frozen after Sprints 13.6–13.9.  
**Stages 1–4 are complete.**

This is the baseline for later Phase 13 work. Moving ownership between the layers below requires an architecture review and, when a contract changes, [RFC-0001](rfc/RFC-0001-architecture-governance.md).

## Purpose

`NotificationService` is the delivery facade for backup text, scheduled reports, the notification worker, and Photo Monitor. `TelegramNotifier` remains the Telegram HTTP client. Scheduling, queues, retries, history, captions, and photo fallback stay with the features that already owned them.

## Architecture overview

```text
Backup._notify ─────────────── send_text ─┐
Reports dispatcher ─────────── send_text ─┤
Notification worker sender ─── send_text ─┼─ NotificationService ─ TelegramNotifier ─ Telegram
Photo watcher ─ send_photo / send_text ───┘
```

Direct paths that do not use the facade:

```text
Alert dispatcher ─ TelegramProvider.send ─ TelegramNotifier.send_text
Operations Center telegram test ─ TelegramNotifier.send_text
build_telegram_notifier ─ constructs TelegramNotifier for the alert and report providers
photo_watcher._resolve_notifier ─ constructs TelegramNotifier, then the watcher wraps it
```

## Component responsibilities

| Component | Responsibility |
| --- | --- |
| `NotificationService` | `send_text`, `send_photo`, `recipient`, `close` |
| `TelegramNotifier` | Bot API `sendMessage` and `sendPhoto`, keyboard URL retry inside one call |
| `TelegramProvider` | Alert and non-report test sends. Converts transport errors to `DeliveryError` |
| Dispatcher `_deliver` | Report and alert retry loop, then one history row |
| `TelegramReportService` | Report text and due rules |
| `NotificationWorker` | Queue, poll, three retries, history |
| `sqlite_backup._notify` | Backup text only. No history row |
| Photo watcher | Scan, baseline, caption, photo retry, text fallback |
| `format_*` helpers | Message text. Not inside the facade |

`NotificationService` does not import the watcher, the queue, the worker, report scheduling, backup, or history.

## Dependency graph

```text
Feature layer
  backup, reports, worker, photo watcher, alert dispatcher, operations test
        │
        ├─ facade: NotificationService   (backup, reports, worker, photo)
        └─ direct: TelegramProvider or TelegramNotifier
                (alerts, operations test, notifier construction)
        │
Transport
  TelegramNotifier
        │
Telegram Bot API
```

## Ownership matrix

| Responsibility | Owner |
| --- | --- |
| Delivery abstraction | `NotificationService` for the four migrated paths |
| Telegram transport | `TelegramNotifier` |
| Backup text | `format_backup_telegram` |
| Report text | `TelegramReportService` |
| Alert text | `format_alert_message`, stored on the queue job |
| Photo caption | `format_new_photo_message` |
| Report scheduling | `process_due_reports` and the 60-second report loop |
| Worker queue | `NotificationQueue` |
| Worker poll | `run_notification_worker` |
| Worker retry | `NotificationWorker` |
| Report and alert retry | Dispatcher `_deliver` |
| Photo retry | `retry_transient` in the photo watcher |
| Backup retry | None |
| Operations test retry | None |
| Report and alert history | Dispatcher `_record` on `notifications` |
| Worker history | In-memory `NotificationHistoryService` plus `_record_delivery` |
| Backup history | None |
| Photo sent flag | `PhotoEventRepository.mark_telegram_sent` |
| Photo fallback | Photo watcher |
| Photo scan, baseline, dedup | Photo watcher |
| Credentials | `notifications/config.py` and `TelegramNotifier.from_settings` |
| HTTP client lifecycle | The caller that constructs the notifier |

## Retry ownership

| Path | Owner | Attempts | Delay | Rule | Facade retries |
| --- | --- | --- | --- | --- | --- |
| Scheduled report and report retry | `_deliver` | 3 | 0.05s fixed | Any exception | No |
| Alert provider | `_deliver` via `TelegramProvider` | 3 | 0.05s fixed | Any exception | No. Alerts do not use the facade |
| Worker | `NotificationWorker` | 3 | 5s fixed | Any exception from `send` | No |
| Photo `send_photo` | `retry_transient` | 3 | 0.05s, then double | Transient errors only | No |
| Photo text fallback | `retry_transient` | 3 | Same | Transient errors only | No |
| Backup | `_notify` | 1 | None | Error is logged | No |
| Operations test | `_dispatch` | 1 | None | Error becomes `RuntimeError` | No |

Photo fallback is sequential: up to three photo attempts, then a separate text sequence. It is not three worker attempts times three facade attempts.

`TelegramNotifier.send_text` and `send_photo` may repeat one HTTP call when Telegram rejects the inline-button URL. That stays inside the transport.

## History ownership

| Writer | Store | When |
| --- | --- | --- |
| Dispatcher `_record` | `notifications` | Insert on report, alert, and channel test. Report retry updates the same row |
| Worker `_record_delivery` | `notifications` | Insert on success or the final drop |
| Worker `record_attempt` | In-memory ring | Every worker attempt |
| Photo repository | `photo_events.telegram_sent` | After a delivered file. Not a notification-history row |
| Backup `_notify` | None | Intentionally no row |

The facade writes none of these.

## Fallback ownership

Photo Monitor is the only fallback owner. `send_photo` raises on failure. The watcher then calls `send_text` with the same caption. The facade does not send that second message.

## Resource lifecycle

| Path | Creates | Closes | Note |
| --- | --- | --- | --- |
| Backup | `NotificationService.from_settings` | `service.close()` in `finally` | One client per notify |
| Reports | `build_telegram_notifier`, then wrap | Provider `close` | Service is not closed separately, so the client closes once |
| Worker | `from_settings` per job | `service.close()` in `finally` | New client per job |
| Photo | `_resolve_notifier` per flush | Not closed | Reused for every file in the flush. See TD-NOTIFY-001 |
| Alerts | `build_telegram_notifier` | Provider `close` | Direct provider |
| Operations test | `from_settings` | `close` in `finally` | Direct notifier |

## Direct Telegram callers

| Location | Class | Later migration |
| --- | --- | --- |
| `telegram.py` `TelegramNotifier` | Infrastructure | No |
| `notifications/config.py` `build_telegram_notifier` | Infrastructure | No, unless alert delivery is redesigned |
| `notifications/telegram.py` `TelegramProvider` | Technical debt for alerts | Only with an accepted design |
| `operations.py` telegram test | Intentional direct | Optional later |
| `photo_watcher._resolve_notifier` | Infrastructure | No. Delivery already uses the facade |
| `TelegramNotifier.send_alert` | Technical debt | Unused. Do not wire it without review |

## Architecture invariants

- **INV-NOTIFY-001.** The facade must not own scheduling.
- **INV-NOTIFY-002.** The facade must not retry on its own.
- **INV-NOTIFY-003.** The facade must not write notification history unless an accepted RFC changes that ownership.
- **INV-NOTIFY-004.** Photo fallback stays in Photo Monitor.
- **INV-NOTIFY-005.** One logical attempt must not send the same Telegram payload twice through two owners.
- **INV-NOTIFY-006.** Formatters stay outside the transport.
- **INV-NOTIFY-007.** `send_text` stays a forward to `TelegramNotifier.send_text` for backup, reports, and the worker.
- **INV-NOTIFY-008.** `send_photo` must raise delivery failures so the watcher can fall back.
- **INV-NOTIFY-009.** Scheduler, worker, and watcher loops stay independent of the facade.
- **INV-NOTIFY-010.** Ownership changes follow an architecture review and RFC-0001 when a contract changes.

## Known technical debt

See [notification-technical-debt.md](notification-technical-debt.md).

## Future migration candidates

Alert `TelegramProvider` and the Operations Center test could later call `send_text`. That is not scheduled. `send_alert` should stay unused until a review says otherwise.

## Change governance

The facade boundary, retry owners, history owners, photo fallback, formatters, and the transport boundary are frozen. Additive methods that preserve `send_text` and `send_photo` are allowed. Moving ownership is not a drive-by change.

Scheduler migration must keep report delivery, worker delivery, and photo delivery on this facade.

## Rollback / troubleshooting

Stage rollback notes are in the stage documents linked from [notification-migration-completion.md](notification-migration-completion.md). A wrong chat or a missing token is still configuration. A photo that arrives as text is the watcher fallback, not a second sender.
