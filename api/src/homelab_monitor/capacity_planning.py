from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from homelab_monitor.analytics import AnalyticsService, _now, _round
from homelab_monitor.connectors.http import as_int
from homelab_monitor.history import as_utc
from homelab_monitor.infrastructure import get_infrastructure_service
from homelab_monitor.schemas import (
    AnalyticsSeriesPoint,
    CapacityBackupResponse,
    CapacityOverviewResponse,
    CapacityPhotosResponse,
    CapacityStorageResponse,
    CapacitySystemResponse,
    TrendBackupResponse,
    TrendOverviewResponse,
    TrendStorageResponse,
)
from homelab_monitor.trends import TrendService

GIB = 1024**3


def estimated_full_in(days: float | None, growth_per_day: float) -> str:
    if growth_per_day <= 0 or days is None:
        return "Unknown"
    return f"{round(days)} Days"


def _risk_from_days(days: float | None, growth: float) -> str:
    if growth <= 0 or days is None:
        return "unknown"
    if days > 180:
        return "healthy"
    if days >= 90:
        return "warning"
    return "critical"


def _days_score(days: float | None, growth: float) -> float:
    if growth <= 0 or days is None:
        return 50.0
    return min(100.0, max(0.0, (days / 180.0) * 100))


def _bytes_label(value: float) -> str:
    if value >= GIB:
        return f"{round(value / GIB, 2)} GB"
    if value >= 1024**2:
        return f"{round(value / (1024**2), 1)} MB"
    if value >= 1024:
        return f"{round(value / 1024, 1)} KB"
    return f"{int(value)} B"


MAX_DATE_DAYS = 36500


def _remaining(
    capacity: int, used: int, growth_per_day: float, now: datetime
) -> tuple[float | None, str]:
    if growth_per_day <= 0 or capacity <= used:
        return None, ""
    days = _round((capacity - used) / growth_per_day)
    if days is None:
        return None, ""
    if days > MAX_DATE_DAYS:
        return days, ""
    return days, (now + timedelta(days=days)).date().isoformat()


class CapacityPlanningService:
    def __init__(
        self,
        analytics: AnalyticsService | None = None,
        trends: TrendService | None = None,
    ) -> None:
        self.analytics = analytics or AnalyticsService()
        self.trends = trends or TrendService(analytics=self.analytics)

    def storage(self, db: Session, *, now: datetime | None = None) -> CapacityStorageResponse:
        end = now or _now()
        trend = self.trends.storage(db, now=end)
        _, detail, _ = self.analytics.photo_detail(db, now=end)
        return self._storage_from_trend(trend, detail)

    def photos(self, db: Session, *, now: datetime | None = None) -> CapacityPhotosResponse:
        end = now or _now()
        photos = self.trends.photos(db, now=end)
        current_photos, storage, _ = self.analytics.photo_detail(db, now=end)
        used = storage.get("today", 0)
        average_per_day = photos.this_week / 7 if photos.this_week else float(photos.today)
        expected_month = round(average_per_day * 30)
        average_size = (used / current_photos) if current_photos > 0 else 0.0
        expected_storage = int(used + average_size * expected_month)
        series = [
            AnalyticsSeriesPoint(label="Today", value=float(photos.today)),
            AnalyticsSeriesPoint(label="This week", value=float(photos.this_week)),
            AnalyticsSeriesPoint(label="Next month", value=float(expected_month)),
        ]
        return CapacityPhotosResponse(
            photos_today=photos.today,
            photos_this_week=photos.this_week,
            average_photos_per_day=_round(average_per_day) or 0.0,
            expected_photos_next_month=expected_month,
            expected_storage_next_month=expected_storage,
            average_size_per_photo=_round(average_size) or 0.0,
            series=series,
        )

    def backup(self, db: Session, *, now: datetime | None = None) -> CapacityBackupResponse:
        end = now or _now()
        trend = self.trends.backup(db, now=end)
        return self._backup_from_trend(db, trend, end)

    def system(self, db: Session, *, now: datetime | None = None) -> CapacitySystemResponse:
        end = now or _now()
        overview = self.trends.overview(db, now=end)
        storage = self.storage(db, now=end)
        backup = self.backup(db, now=end)
        cpu = self.trends.cpu(db, now=end)
        memory = self.trends.memory(db, now=end)
        score, bottleneck = self._score(
            overview, storage, backup, cpu.average_1d, memory.average_1d
        )
        return CapacitySystemResponse(
            cpu_trend=overview.cpu_trend,
            memory_trend=overview.memory_trend,
            storage_trend=overview.storage_trend,
            backup_trend=overview.backup_trend,
            overall_score=score,
            bottleneck=bottleneck,
            health=overview.health,
        )

    def overview(self, db: Session, *, now: datetime | None = None) -> CapacityOverviewResponse:
        end = now or _now()
        storage = self.storage(db, now=end)
        photos = self.photos(db, now=end)
        backup = self.backup(db, now=end)
        system = self.system(db, now=end)
        backup_forecast = backup.estimated_full_date or (
            "sufficient" if backup.trend == "healthy" else backup.trend
        )
        return CapacityOverviewResponse(
            storage_remaining_days=storage.estimated_days_remaining,
            estimated_full_date=storage.estimated_full_date,
            growth_per_day=storage.average_daily_growth,
            photo_forecast=photos.expected_photos_next_month,
            backup_forecast=backup_forecast,
            capacity_score=system.overall_score,
            bottleneck=system.bottleneck,
            storage_risk=storage.risk,
            backup_risk=backup.trend,
            recommendations=self._recommendations(storage, photos, backup, system),
            series=storage.series,
        )

    def _storage_from_trend(
        self, trend: TrendStorageResponse, detail: dict[str, int]
    ) -> CapacityStorageResponse:
        capacity = detail.get("capacity", 0)
        used = trend.current_used
        free = max(0, capacity - used) if capacity else 0
        risk = _risk_from_days(trend.estimated_days_until_full, trend.growth_per_day)
        return CapacityStorageResponse(
            current_used=used,
            current_free=free,
            capacity=capacity,
            average_daily_growth=trend.growth_per_day,
            average_weekly_growth=float(trend.weekly_growth_bytes),
            estimated_days_remaining=trend.estimated_days_until_full,
            estimated_full_date=trend.estimated_full_date,
            estimated_full_in=estimated_full_in(
                trend.estimated_days_until_full, trend.growth_per_day
            ),
            risk=risk,
            series=trend.series,
        )

    def _backup_from_trend(
        self, db: Session, trend: TrendBackupResponse, now: datetime
    ) -> CapacityBackupResponse:
        rows = self.analytics.backup_snapshots(db)
        sizes: list[tuple[datetime, int]] = []
        for row in rows:
            size = as_int(row.payload.get("backup_size_bytes"))
            if size > 0:
                sizes.append((as_utc(row.observed_at), size))
        current = sizes[-1][1] if sizes else 0
        if current == 0:
            current = self._live_backup_size()
        capacity = self._destination_capacity(db, now)
        growth = 0.0
        if len(sizes) >= 2:
            span_days = max(1.0, (sizes[-1][0] - sizes[0][0]).total_seconds() / 86400)
            delta = sizes[-1][1] - sizes[0][1]
            growth = max(0.0, delta / span_days)
        days, full_date = _remaining(capacity, current, growth, now)
        fill_risk = _risk_from_days(days, growth)
        if fill_risk == "unknown" and trend.success_rate is not None:
            if trend.success_rate >= 80:
                status = "healthy"
            elif trend.success_rate >= 50:
                status = "warning"
            else:
                status = "critical"
        else:
            status = fill_risk
        series = [
            AnalyticsSeriesPoint(
                timestamp=stamp,
                label=stamp.strftime("%m-%d"),
                value=float(size),
            )
            for stamp, size in sizes[-30:]
        ]
        if not series:
            series = trend.series[-30:]
        return CapacityBackupResponse(
            destination_capacity=capacity,
            current_backup_size=current,
            growth_per_day=_round(growth) or 0.0,
            estimated_days_remaining=days,
            estimated_full_date=full_date,
            success_percent=trend.success_rate,
            average_duration=trend.average_duration,
            trend=status,
            series=series,
        )

    def _live_backup_size(self) -> int:
        _, services = get_infrastructure_service().snapshot()
        for item in services:
            if item.service == "backup":
                return as_int(item.summary.get("backup_size_bytes"))
        return 0

    def _destination_capacity(self, db: Session, now: datetime) -> int:
        _, services = get_infrastructure_service().snapshot()
        for item in services:
            if item.service == "qnap":
                capacity = as_int(item.summary.get("capacity_bytes"))
                if capacity > 0:
                    return capacity
        _, detail, _ = self.analytics.photo_detail(db, now=now)
        return detail.get("capacity", 0)

    def _score(
        self,
        overview: TrendOverviewResponse,
        storage: CapacityStorageResponse,
        backup: CapacityBackupResponse,
        cpu_average: float | None,
        memory_average: float | None,
    ) -> tuple[float, str]:
        health = overview.health
        total = (
            health.healthy_count
            + health.warning_count
            + health.critical_count
            + health.unknown_count
        )
        health_score = (health.healthy_count / total * 100) if total else 50.0
        storage_score = _days_score(storage.estimated_days_remaining, storage.average_daily_growth)
        backup_fill = _days_score(backup.estimated_days_remaining, backup.growth_per_day)
        backup_success = backup.success_percent if backup.success_percent is not None else 50.0
        backup_score = (backup_fill + backup_success) / 2
        cpu_score = max(0.0, 100.0 - cpu_average) if cpu_average is not None else 50.0
        memory_score = max(0.0, 100.0 - memory_average) if memory_average is not None else 50.0
        parts = {
            "storage": storage_score,
            "backup": backup_score,
            "cpu": cpu_score,
            "memory": memory_score,
        }
        bottleneck = min(parts, key=parts.get)
        overall = _round(
            storage_score * 0.4
            + backup_score * 0.25
            + cpu_score * 0.15
            + memory_score * 0.1
            + health_score * 0.1
        )
        return overall or 0.0, bottleneck

    def _recommendations(
        self,
        storage: CapacityStorageResponse,
        photos: CapacityPhotosResponse,
        backup: CapacityBackupResponse,
        system: CapacitySystemResponse,
    ) -> list[str]:
        messages: list[str] = []
        if storage.risk == "unknown":
            messages.append("Storage growth is unknown; remaining days cannot be estimated.")
        elif storage.estimated_days_remaining is not None:
            days = storage.estimated_days_remaining
            messages.append(f"Storage will be full in approximately {days} days.")
            if storage.risk == "critical":
                messages.append("Consider upgrading to a larger NAS.")
            elif storage.risk == "warning":
                messages.append("Plan a NAS upgrade within the next six months.")
        if storage.average_daily_growth > 0:
            messages.append(
                f"Average storage growth is {_bytes_label(storage.average_daily_growth)}/day."
            )
        if photos.average_photos_per_day >= 20:
            messages.append("Photo library is growing rapidly.")
        if backup.trend == "healthy":
            messages.append("Backup destination has sufficient capacity.")
        elif backup.trend == "critical":
            messages.append("Backup destination is approaching capacity or failing often.")
        elif backup.trend == "warning":
            messages.append("Monitor backup destination capacity and success rate.")
        if system.bottleneck != "unknown":
            messages.append(f"{system.bottleneck.capitalize()} is the likely bottleneck first.")
        messages.append(f"Current infrastructure health score is {system.overall_score}.")
        return messages
