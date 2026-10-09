"""In-memory FIFO notification queue for alert delivery."""

from __future__ import annotations

import threading
import uuid
from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


@dataclass
class NotificationJob:
    id: str
    created_at: datetime
    channel: str
    event: str
    message: str
    retry_count: int = 0


class NotificationQueue:
    def __init__(self) -> None:
        self._items: deque[NotificationJob] = deque()
        self._lock = threading.Lock()

    def enqueue(self, job: NotificationJob) -> None:
        with self._lock:
            self._items.append(job)

    def dequeue(self) -> NotificationJob | None:
        with self._lock:
            if not self._items:
                return None
            return self._items.popleft()

    def snapshot(self) -> list[NotificationJob]:
        with self._lock:
            return list(self._items)

    def clear(self) -> None:
        with self._lock:
            self._items.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._items)


_queue = NotificationQueue()


def get_notification_queue() -> NotificationQueue:
    return _queue


def reset_notification_queue() -> None:
    _queue.clear()


def new_notification_job(
    *,
    channel: str,
    event: str,
    message: str,
    retry_count: int = 0,
) -> NotificationJob:
    return NotificationJob(
        id=str(uuid.uuid4()),
        created_at=datetime.now(UTC),
        channel=channel,
        event=event,
        message=message,
        retry_count=retry_count,
    )


def enqueue_alert_events(
    events: Sequence[Any],
    queue: NotificationQueue | None = None,
) -> list[NotificationJob]:
    from homelab_monitor.telegram import format_alert_message

    target = queue if queue is not None else get_notification_queue()
    jobs: list[NotificationJob] = []
    for event in events:
        job = new_notification_job(
            channel="telegram",
            event=getattr(event, "transition", "activated"),
            message=format_alert_message(event),
        )
        target.enqueue(job)
        jobs.append(job)
    return jobs
