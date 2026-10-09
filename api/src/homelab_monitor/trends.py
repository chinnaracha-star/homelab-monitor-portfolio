from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from homelab_monitor.analytics import AnalyticsService, _now, _round, _success_rate
from homelab_monitor.connectors.http import as_int
from homelab_monitor.history import as_utc
from homelab_monitor.infrastructure import get_infrastructure_service
from homelab_monitor.ops_history import _status_from_payload
from homelab_monitor.schemas import (
    AnalyticsSeriesPoint,
    TrendBackupResponse,
    TrendCpuResponse,
    TrendHealthSummary,
    TrendMemoryResponse,
    TrendOverviewResponse,
    TrendPhotosResponse,
    TrendStorageResponse,
)

STABLE_PERCENT = 5.0
MAX_STORAGE_FORECAST_DAYS = 36500


def _forecast_full_date(end: datetime, days: float | None) -> str:
    if days is None:
        return ""
    try:
        span = int(days)
    except (OverflowError, ValueError):
        return ""
    if span < 0:
        return ""
    span = min(span, MAX_STORAGE_FORECAST_DAYS)
    try:
        return (end + timedelta(days=span)).date().isoformat()
    except OverflowError:
        return ""


def _classify(current: float | None, previous: float | None) -> tuple[str, float | None]:
    if current is None or previous is None:
        return "stable", None
    if previous == 0:
        if current == 0:
            return "stable", 0.0
        return ("rising" if current > 0 else "falling"), None
    difference = _round(((current - previous) / abs(previous)) * 100)
    assert difference is not None
    if difference > STABLE_PERCENT:
        return "rising", difference
    if difference < -STABLE_PERCENT:
        return "falling", difference
    return "stable", difference


def _health_bucket(status: str) -> str:
    value = status.lower()
    if value in {"healthy", "ok", "success"}:
        return "healthy"
    if value in {"degraded", "warning"}:
        return "warning"
    if value in {"unhealthy", "critical", "failed"}:
        return "critical"
    return "unknown"


class TrendService:
    def __init__(self, analytics: AnalyticsService | None = None) -> None:
        self.analytics = analytics or AnalyticsService()

    def cpu(self, db: Session, *, now: datetime | None = None) -> TrendCpuResponse:
        return self._metric_trend(db, "cpu_percent", now=now)

    def memory(self, db: Session, *, now: datetime | None = None) -> TrendMemoryResponse:
        payload = self._metric_trend(db, "memory_percent", now=now)
        return TrendMemoryResponse.model_validate(payload.model_dump())

    def _metric_trend(
        self, db: Session, field: str, *, now: datetime | None = None
    ) -> TrendCpuResponse:
        end = now or _now()
        if field == "cpu_percent":
            latest_cpu = self.analytics.cpu(db, now=end)
            latest = latest_cpu.current
            average_1d = latest_cpu.average_24h
            hourly = latest_cpu.series
        else:
            latest_mem = self.analytics.memory(db, now=end)
            latest = latest_mem.current
            average_1d = latest_mem.average
            hourly = latest_mem.series
        average_7d = self.analytics.average_for(db, field, hours=24 * 7, now=end)
        average_30d = self.analytics.average_for(db, field, hours=24 * 30, now=end)
        previous = self.analytics.average_between(
            db, field, start=end - timedelta(hours=48), end=end - timedelta(hours=24)
        )
        direction, difference = _classify(average_1d, previous)
        return TrendCpuResponse(
            latest=latest,
            average_1d=average_1d,
            average_7d=average_7d,
            average_30d=average_30d,
            trend=direction,
            difference_percent=difference,
            hourly=hourly,
            daily=self.analytics.daily_series(db, field, days=30, now=end),
        )

    def storage(self, db: Session, *, now: datetime | None = None) -> TrendStorageResponse:
        end = now or _now()
        storage = self.analytics.storage(db, now=end)
        _, detail, _ = self.analytics.photo_detail(db, now=end)
        capacity = detail.get("capacity", 0)
        current = storage.current
        daily = storage.daily_growth
        weekly = storage.weekly_growth
        monthly = max(0, current - detail.get("last_month", 0))
        growth_per_day = float(daily) if daily > 0 else (weekly / 7 if weekly > 0 else 0.0)
        used_percent = None
        if capacity > 0:
            used_percent = _round((current / capacity) * 100)
        elif storage.series:
            used_percent = storage.series[-1].value
        days_until_full = None
        full_date = None
        if growth_per_day > 0 and capacity > current:
            days_until_full = _round((capacity - current) / growth_per_day)
            if days_until_full is not None:
                full_date = _forecast_full_date(end, days_until_full)
        direction = "rising" if growth_per_day > 0 else "stable"
        forecast = _storage_forecast(storage.series, growth_per_day, used_percent, days_until_full)
        return TrendStorageResponse(
            current_used=current,
            used_percent=used_percent,
            daily_growth_bytes=daily,
            weekly_growth_bytes=weekly,
            monthly_growth_bytes=monthly,
            growth_per_day=_round(growth_per_day) or 0.0,
            estimated_days_until_full=days_until_full,
            estimated_full_date=full_date or "",
            trend=direction,
            series=forecast,
        )

    def photos(self, db: Session, *, now: datetime | None = None) -> TrendPhotosResponse:
        end = now or _now()
        photos = self.analytics.photos(db, now=end)
        _, _, growth = self.analytics.photo_detail(db, now=end)
        last_week = growth.get("last_week", 0)
        this_month = growth.get("this_month", 0)
        direction, difference = _classify(float(photos.today), float(photos.yesterday))
        expected_next_week = photos.this_week
        series = [
            AnalyticsSeriesPoint(label="Today", value=float(photos.today)),
            AnalyticsSeriesPoint(label="Yesterday", value=float(photos.yesterday)),
            AnalyticsSeriesPoint(label="This week", value=float(photos.this_week)),
            AnalyticsSeriesPoint(label="Last week", value=float(last_week)),
            AnalyticsSeriesPoint(label="This month", value=float(this_month)),
        ]
        return TrendPhotosResponse(
            today=photos.today,
            yesterday=photos.yesterday,
            this_week=photos.this_week,
            last_week=last_week,
            this_month=this_month,
            growth=photos.this_week,
            daily=photos.today,
            weekly=photos.this_week,
            monthly=this_month,
            expected_next_week=expected_next_week,
            trend=direction,
            difference_percent=difference,
            series=series,
        )

    def backup(self, db: Session, *, now: datetime | None = None) -> TrendBackupResponse:
        end = now or _now()
        rows = [
            row
            for row in self.analytics.backup_snapshots(db)
            if as_utc(row.observed_at) >= end - timedelta(days=30)
        ]
        durations: list[int] = []
        running = 0
        latest_progress = 0.0
        for row in rows:
            status = _status_from_payload(row.payload)
            if status == "running":
                running += 1
            seconds = as_int(row.payload.get("duration_seconds"))
            if seconds > 0:
                durations.append(seconds)
            latest_progress = float(row.payload.get("progress_percent") or latest_progress)
        success = _success_rate(rows)
        failure = None if success is None else _round(100 - success)
        average = _round(sum(durations) / len(durations)) if durations else None
        analytics_backup = self.analytics.backup(db, now=end)
        remaining = None
        if running and analytics_backup.duration_seconds:
            remaining = _round(
                analytics_backup.duration_seconds * max(0.0, (100 - latest_progress) / 100)
            )
        direction = "stable"
        if success is not None:
            if success >= 80:
                direction = "rising"
            elif success < 50:
                direction = "falling"
        return TrendBackupResponse(
            last_30_backups=len(rows),
            success_rate=success,
            failure_rate=failure,
            average_duration=average,
            fastest=min(durations) if durations else None,
            slowest=max(durations) if durations else None,
            running_count=running,
            expected_completion_seconds=int(remaining) if remaining is not None else None,
            last_backup=analytics_backup.last_backup,
            trend=direction,
            series=analytics_backup.series[-30:],
        )

    def health(self) -> TrendHealthSummary:
        _, services = get_infrastructure_service().snapshot()
        counts = {"healthy": 0, "warning": 0, "critical": 0, "unknown": 0}
        for item in services:
            counts[_health_bucket(item.status)] += 1
        return TrendHealthSummary(
            healthy_count=counts["healthy"],
            warning_count=counts["warning"],
            critical_count=counts["critical"],
            unknown_count=counts["unknown"],
        )

    def overview(self, db: Session, *, now: datetime | None = None) -> TrendOverviewResponse:
        end = now or _now()
        cpu = self.cpu(db, now=end)
        memory = self.memory(db, now=end)
        storage = self.storage(db, now=end)
        photos = self.photos(db, now=end)
        backup = self.backup(db, now=end)
        health = self.health()
        total = (
            health.healthy_count
            + health.warning_count
            + health.critical_count
            + health.unknown_count
        )
        health_score = (health.healthy_count / total * 100) if total else 50.0
        backup_score = backup.success_rate if backup.success_rate is not None else 50.0
        storage_score = (
            max(0.0, 100.0 - storage.used_percent) if storage.used_percent is not None else 50.0
        )
        cpu_score = max(0.0, 100.0 - cpu.average_1d) if cpu.average_1d is not None else 50.0
        memory_score = (
            max(0.0, 100.0 - memory.average_1d) if memory.average_1d is not None else 50.0
        )
        overall = _round(
            health_score * 0.4
            + backup_score * 0.25
            + storage_score * 0.15
            + cpu_score * 0.1
            + memory_score * 0.1
        )
        overall_trend = "stable"
        if (overall or 0) >= 80 and health.critical_count == 0:
            overall_trend = "rising"
        elif health.critical_count > 0 or (overall or 0) < 50:
            overall_trend = "falling"
        return TrendOverviewResponse(
            cpu_trend=cpu.trend,
            memory_trend=memory.trend,
            storage_trend=storage.trend,
            photo_trend=photos.trend,
            backup_trend=backup.trend,
            overall_health=overall_trend,
            overall_score=overall or 0.0,
            health=health,
        )


def _storage_forecast(
    history: list[AnalyticsSeriesPoint],
    growth_per_day: float,
    used_percent: float | None,
    days_until_full: float | None,
) -> list[AnalyticsSeriesPoint]:
    points = [
        AnalyticsSeriesPoint(timestamp=item.timestamp, label=item.label, value=item.value)
        for item in history
    ]
    if used_percent is None or growth_per_day <= 0:
        return points
    last_label = history[-1].label if history else "now"
    last_value = used_percent
    horizon = 7
    if days_until_full is not None:
        horizon = max(1, min(14, int(days_until_full)))
    daily_percent = None
    if (
        history
        and len(history) >= 2
        and history[0].value is not None
        and history[-1].value is not None
    ):
        span = max(1, len(history) - 1)
        daily_percent = (history[-1].value - history[0].value) / span
    increment = daily_percent if daily_percent and daily_percent > 0 else 0.0
    for offset in range(1, horizon + 1):
        projected = min(100.0, last_value + increment * offset)
        points.append(
            AnalyticsSeriesPoint(
                label=f"+{offset}d",
                value=_round(projected),
            )
        )
    del last_label
    return points
