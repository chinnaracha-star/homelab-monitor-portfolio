"""Notification delivery-attempt history.

Persistent storage can replace InMemoryNotificationHistory later by
implementing NotificationHistoryStore. This sprint uses a ring buffer.
"""

from __future__ import annotations

import threading
from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

HISTORY_BUFFER_SIZE = 1000
HISTORY_API_LIMIT = 100


@dataclass(frozen=True)
class NotificationHistoryRecord:
    id: str
    created_at: datetime
    sent_at: datetime | None
    channel: str
    event: str
    success: bool
    retry_count: int
    duration_ms: int
    error_message: str | None


class NotificationHistoryStore(Protocol):
    def record(self, entry: NotificationHistoryRecord) -> None: ...

    def list_recent(self, limit: int) -> list[NotificationHistoryRecord]: ...

    def clear(self) -> None: ...


class InMemoryNotificationHistory:
    def __init__(self, maxlen: int = HISTORY_BUFFER_SIZE) -> None:
        self._entries: deque[NotificationHistoryRecord] = deque(maxlen=maxlen)
        self._lock = threading.Lock()

    def record(self, entry: NotificationHistoryRecord) -> None:
        with self._lock:
            self._entries.append(entry)

    def list_recent(self, limit: int) -> list[NotificationHistoryRecord]:
        with self._lock:
            items = list(self._entries)
        items.reverse()
        return items[: max(0, limit)]

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()


class NotificationHistoryService:
    def __init__(self, store: NotificationHistoryStore | None = None) -> None:
        self._store = store or InMemoryNotificationHistory()

    def record_attempt(
        self,
        *,
        notification_id: str,
        channel: str,
        event: str,
        success: bool,
        retry_count: int,
        duration_ms: int,
        error_message: str | None = None,
        created_at: datetime | None = None,
        sent_at: datetime | None = None,
    ) -> NotificationHistoryRecord:
        started = created_at or datetime.now(UTC)
        finished = sent_at if sent_at is not None else (datetime.now(UTC) if success else None)
        entry = NotificationHistoryRecord(
            id=notification_id,
            created_at=started,
            sent_at=finished,
            channel=channel,
            event=event,
            success=success,
            retry_count=retry_count,
            duration_ms=max(0, duration_ms),
            error_message=error_message,
        )
        self._store.record(entry)
        return entry

    def list_history(self, limit: int = HISTORY_API_LIMIT) -> Sequence[NotificationHistoryRecord]:
        return self._store.list_recent(min(max(limit, 0), HISTORY_API_LIMIT))

    def list_all(self) -> Sequence[NotificationHistoryRecord]:
        return self._store.list_recent(HISTORY_BUFFER_SIZE)

    def clear(self) -> None:
        self._store.clear()


_service = NotificationHistoryService()


def get_notification_history_service() -> NotificationHistoryService:
    return _service


def reset_notification_history() -> None:
    _service.clear()
