from collections.abc import Callable
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from homelab_monitor.notification_history import NotificationHistoryService
from homelab_monitor.notification_metrics import NotificationMetricsService


def _record(
    history: NotificationHistoryService,
    *,
    notification_id: str,
    success: bool,
    duration_ms: int,
    retry_count: int = 0,
    created_at: datetime | None = None,
    sent_at: datetime | None = None,
) -> None:
    history.record_attempt(
        notification_id=notification_id,
        channel="telegram",
        event="activated",
        success=success,
        retry_count=retry_count,
        duration_ms=duration_ms,
        error_message=None if success else "failed",
        created_at=created_at,
        sent_at=sent_at,
    )


def test_metrics_empty_history() -> None:
    metrics = NotificationMetricsService(NotificationHistoryService()).snapshot()
    assert metrics.total_sent == 0
    assert metrics.total_success == 0
    assert metrics.total_failed == 0
    assert metrics.success_rate == 0.0
    assert metrics.average_duration_ms == 0
    assert metrics.max_duration_ms == 0
    assert metrics.average_retry_count == 0.0
    assert metrics.last_notification_at is None


def test_metrics_single_notification() -> None:
    history = NotificationHistoryService()
    moment = datetime(2026, 9, 11, 9, 13, 21, tzinfo=UTC)
    _record(
        history,
        notification_id="one",
        success=True,
        duration_ms=142,
        created_at=moment,
        sent_at=moment,
    )
    metrics = NotificationMetricsService(history).snapshot()
    assert metrics.total_sent == 1
    assert metrics.total_success == 1
    assert metrics.total_failed == 0
    assert metrics.success_rate == 100.0
    assert metrics.average_duration_ms == 142
    assert metrics.max_duration_ms == 142
    assert metrics.average_retry_count == 0.0
    assert metrics.last_notification_at == moment


def test_metrics_multiple_notifications_success_rate_and_durations() -> None:
    history = NotificationHistoryService()
    first = datetime(2026, 9, 11, 9, 0, tzinfo=UTC)
    last = datetime(2026, 9, 11, 9, 13, 21, tzinfo=UTC)
    _record(
        history,
        notification_id="a",
        success=True,
        duration_ms=100,
        created_at=first,
        sent_at=first,
    )
    _record(
        history,
        notification_id="b",
        success=True,
        duration_ms=200,
        created_at=last,
        sent_at=last,
    )
    _record(
        history,
        notification_id="c",
        success=False,
        duration_ms=510,
        retry_count=1,
        created_at=last,
        sent_at=None,
    )
    metrics = NotificationMetricsService(history).snapshot()
    assert metrics.total_sent == 3
    assert metrics.total_success == 2
    assert metrics.total_failed == 1
    assert metrics.success_rate == 66.7
    assert metrics.average_duration_ms == 270
    assert metrics.max_duration_ms == 510
    assert metrics.average_retry_count == 0.33
    assert metrics.last_notification_at == last


def test_metrics_retry_average() -> None:
    history = NotificationHistoryService()
    _record(history, notification_id="a", success=True, duration_ms=10, retry_count=0)
    _record(history, notification_id="b", success=False, duration_ms=10, retry_count=2)
    metrics = NotificationMetricsService(history).snapshot()
    assert metrics.average_retry_count == 1.0


def test_metrics_last_notification_and_http(
    client: TestClient,
    auth_header: Callable[..., dict[str, str]],
) -> None:
    from homelab_monitor.notification_history import get_notification_history_service

    history = get_notification_history_service()
    moment = datetime(2026, 9, 11, 9, 13, 21, tzinfo=UTC)
    _record(
        history,
        notification_id="latest",
        success=True,
        duration_ms=50,
        created_at=moment,
        sent_at=moment,
    )
    assert client.get("/api/v1/notifications/metrics").status_code == 401
    response = client.get("/api/v1/notifications/metrics", headers=auth_header())
    assert response.status_code == 200
    body = response.json()
    assert body["total_sent"] == 1
    assert body["total_success"] == 1
    assert body["last_notification_at"].startswith("2026-09-11T09:13:21")
    assert set(body) == {
        "total_sent",
        "total_success",
        "total_failed",
        "success_rate",
        "average_duration_ms",
        "max_duration_ms",
        "average_retry_count",
        "last_notification_at",
    }
