# Notification technical debt

Recorded at the Sprint 13.9.1 freeze. None of these items are fixed here.

## TD-NOTIFY-001 — Photo flush HTTP client

- **Description:** Each photo flush constructs a `TelegramNotifier` and does not close it.
- **Current behavior:** One client is reused for every file in that flush, then left open.
- **Severity:** Medium.
- **Production impact:** Extra HTTP clients across flushes. Delivery behavior is unchanged.
- **Not fixed now:** Closing it in the wrong place would close the client between files or double-close a shared client.
- **Later:** A lifecycle sprint that closes the client once after the flush.
- **Prerequisite:** Tests that a second file in the same flush still sends.
- **Regression risk:** High if close runs before the last file.

## TD-NOTIFY-002 — Alert path uses TelegramProvider

- **Description:** Alert dispatch and non-report channel tests call `TelegramProvider.send`, not `NotificationService`.
- **Current behavior:** `_deliver` retries that provider three times and writes one history row.
- **Severity:** Low.
- **Production impact:** None while the provider still calls `send_text`.
- **Not fixed now:** The four-stage migration excluded alerts on purpose.
- **Later:** Only after a review that keeps `_deliver` as the only retry and history owner.
- **Prerequisite:** Alert tests that still expect one history row and three attempts.
- **Regression risk:** Medium. A facade retry plus `_deliver` would triple sends.

## TD-NOTIFY-003 — Operations Center Telegram test

- **Description:** `operations._dispatch` for `telegram_test` constructs `TelegramNotifier` and sends one fixed sentence.
- **Current behavior:** One send, then `close`. Failure becomes `RuntimeError`.
- **Severity:** Low.
- **Production impact:** None.
- **Not fixed now:** The test is an operator action, not one of the four migrated features.
- **Later:** Optional switch to `send_text` with the same sentence and the same error mapping.
- **Prerequisite:** The operations test still expects that sentence.
- **Regression risk:** Low.

## TD-NOTIFY-004 — Mixed construction

- **Description:** Backup and the worker call `NotificationService.from_settings`. Reports and photos construct a notifier first, then wrap it.
- **Current behavior:** Both end at `TelegramNotifier`. Close ownership differs, as described in the architecture doc.
- **Severity:** Low.
- **Production impact:** None today. A later helper can close the wrong object if it assumes one construction style.
- **Not fixed now:** Unifying construction would touch lifecycle.
- **Later:** The same lifecycle sprint as TD-NOTIFY-001.
- **Prerequisite:** A diagram of who closes each client.
- **Regression risk:** Medium.

## TD-NOTIFY-005 — Several history writers

- **Description:** Reports and alerts use `notifications`. The worker also writes that table and an in-memory ring. Photos use `photo_events`. Backup writes nothing.
- **Current behavior:** The facade adds no writer. Worker success can appear in both the table and the ring. That split predates the facade.
- **Severity:** Low.
- **Production impact:** Operators can see worker attempts in more than one view. Counts are not a single ledger.
- **Not fixed now:** Normalizing history would change API results.
- **Later:** A history RFC, not a transport change.
- **Prerequisite:** RFC-0001 if the history contract changes.
- **Regression risk:** High for dashboard history if rows are merged blindly.

## TD-NOTIFY-006 — Unused `send_alert`

- **Description:** `TelegramNotifier.send_alert` is not called.
- **Current behavior:** Dead method on the transport.
- **Severity:** Low.
- **Production impact:** None.
- **Not fixed now:** Deleting it is cleanup, not this review.
- **Later:** Remove only after a search shows no external caller.
- **Prerequisite:** None.
- **Regression risk:** Low.
