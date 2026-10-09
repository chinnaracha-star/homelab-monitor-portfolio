from collections.abc import Callable
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from homelab_monitor.notification_history import (
    HISTORY_API_LIMIT,
    NotificationHistoryService,
    get_notification_history_service,
)
from homelab_monitor.notification_queue import NotificationQueue, new_notification_job
from homelab_monitor.notification_worker import NotificationWorker


def _job(message: str = "alert", event: str = "activated"):
    return new_notification_job(channel="telegram", event=event, message=message)


def _worker(queue: NotificationQueue, sender, history: NotificationHistoryService):
    return NotificationWorker(
        queue,
        sender,
        retry_delay_seconds=0,
        batch_window_seconds=0,
        sleep=lambda _: None,
        history=history,
    )


def test_history_records_success() -> None:
    history = NotificationHistoryService()
    queue = NotificationQueue()
    job = _job("ok")
    queue.enqueue(job)

    class Capture:
        def send(self, item) -> None:
            return None

    _worker(queue, Capture(), history).process_one()
    items = list(history.list_history())
    assert len(items) == 1
    record = items[0]
    assert record.id == job.id
    assert record.channel == "telegram"
    assert record.event == "activated"
    assert record.success is True
    assert record.retry_count == 0
    assert record.duration_ms >= 0
    assert record.error_message is None
    assert record.sent_at is not None


def test_history_records_retry() -> None:
    history = NotificationHistoryService()
    queue = NotificationQueue()
    queue.enqueue(_job("flaky"))
    calls = {"n": 0}

    class Flaky:
        def send(self, item) -> None:
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("temporary")

    worker = _worker(queue, Flaky(), history)
    worker.process_one()
    worker.process_one()
    items = list(history.list_history())
    assert [item.success for item in items] == [True, False]
    assert [item.retry_count for item in items] == [1, 0]
    assert items[1].error_message == "temporary"
    assert items[0].error_message is None


def test_history_records_failure() -> None:
    history = NotificationHistoryService()
    queue = NotificationQueue()
    queue.enqueue(_job("failing"))

    class Boom:
        def send(self, item) -> None:
            raise RuntimeError("telegram down")

    worker = _worker(queue, Boom(), history)
    worker.process_one()
    worker.process_one()
    worker.process_one()
    items = list(history.list_history())
    assert len(items) == 3
    assert all(item.success is False for item in items)
    assert [item.retry_count for item in items] == [2, 1, 0]
    assert all(item.error_message == "telegram down" for item in items)
    assert all(item.sent_at is None for item in items)


def test_history_ordering_newest_first() -> None:
    history = NotificationHistoryService()
    first = history.record_attempt(
        notification_id="one",
        channel="telegram",
        event="activated",
        success=True,
        retry_count=0,
        duration_ms=1,
        created_at=datetime(2026, 9, 10, 8, 0, tzinfo=UTC),
        sent_at=datetime(2026, 9, 10, 8, 0, tzinfo=UTC),
    )
    second = history.record_attempt(
        notification_id="two",
        channel="telegram",
        event="recovered",
        success=True,
        retry_count=0,
        duration_ms=2,
        created_at=datetime(2026, 9, 10, 8, 1, tzinfo=UTC),
        sent_at=datetime(2026, 9, 10, 8, 1, tzinfo=UTC),
    )
    items = list(history.list_history())
    assert [item.id for item in items] == [second.id, first.id]


def test_history_limit_100(
    client: TestClient,
    auth_header: Callable[..., dict[str, str]],
) -> None:
    service = get_notification_history_service()
    for index in range(HISTORY_API_LIMIT + 20):
        service.record_attempt(
            notification_id=f"job-{index}",
            channel="telegram",
            event="activated",
            success=True,
            retry_count=0,
            duration_ms=index,
        )
    assert len(list(service.list_history(500))) == HISTORY_API_LIMIT
    response = client.get("/api/v1/notifications/delivery-history", headers=auth_header())
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == HISTORY_API_LIMIT
    assert body["items"][0]["id"] == "job-119"
    assert body["items"][-1]["id"] == "job-20"
    item = body["items"][0]
    assert set(item) == {
        "id",
        "created_at",
        "sent_at",
        "channel",
        "event",
        "success",
        "retry_count",
        "duration_ms",
        "error_message",
    }


def test_delivery_history_requires_jwt(client: TestClient) -> None:
    assert client.get("/api/v1/notifications/delivery-history").status_code == 401
