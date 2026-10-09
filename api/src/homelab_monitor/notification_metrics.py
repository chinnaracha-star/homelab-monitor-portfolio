"""Aggregate delivery metrics from NotificationHistory."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from homelab_monitor.notification_history import (
    NotificationHistoryService,
    get_notification_history_service,
)


@dataclass(frozen=True)
class NotificationMetrics:
    total_sent: int
    total_success: int
    total_failed: int
    success_rate: float
    average_duration_ms: int
    max_duration_ms: int
    average_retry_count: float
    last_notification_at: datetime | None


class NotificationMetricsService:
    def __init__(self, history: NotificationHistoryService | None = None) -> None:
        self._history = history or get_notification_history_service()

    def snapshot(self) -> NotificationMetrics:
        records = list(self._history.list_all())
        if not records:
            return NotificationMetrics(
                total_sent=0,
                total_success=0,
                total_failed=0,
                success_rate=0.0,
                average_duration_ms=0,
                max_duration_ms=0,
                average_retry_count=0.0,
                last_notification_at=None,
            )
        total = len(records)
        success = sum(1 for record in records if record.success)
        failed = total - success
        durations = [record.duration_ms for record in records]
        retries = [record.retry_count for record in records]
        newest = records[0]
        last_at = newest.sent_at or newest.created_at
        return NotificationMetrics(
            total_sent=total,
            total_success=success,
            total_failed=failed,
            success_rate=round((success / total) * 100, 1),
            average_duration_ms=round(sum(durations) / total),
            max_duration_ms=max(durations),
            average_retry_count=round(sum(retries) / total, 2),
            last_notification_at=last_at,
        )
