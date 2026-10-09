from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from homelab_monitor.agent_presence import online_count, presence_for_agents
from homelab_monitor.connectors.http import as_int, as_str
from homelab_monitor.history import aggregate_history, as_utc
from homelab_monitor.models import Agent, Alert, MetricHistory, Notification, OpsSnapshot
from homelab_monitor.ops_history import (
    _start_of_day,
    _start_of_local_day,
    _status_from_payload,
    _value_at_or_before,
)
from homelab_monitor.schemas import (
    AnalyticsBackupResponse,
    AnalyticsCpuResponse,
    AnalyticsDailyOverview,
    AnalyticsMemoryResponse,
    AnalyticsOverviewResponse,
    AnalyticsPhotosResponse,
    AnalyticsSeriesPoint,
    AnalyticsStorageResponse,
    AnalyticsTemperatureResponse,
)


def _now() -> datetime:
    return datetime.now(UTC)


def _round(value: float | None) -> float | None:
    if value is None:
        return None
    return round(value, 2)


def _values(rows: list[MetricHistory], field: str) -> list[float]:
    numbers: list[float] = []
    for row in rows:
        value = getattr(row, field)
        if value is not None:
            numbers.append(float(value))
    return numbers


def _current(rows: list[MetricHistory], field: str) -> float | None:
    for row in sorted(rows, key=lambda item: as_utc(item.timestamp), reverse=True):
        value = getattr(row, field)
        if value is not None:
            return _round(float(value))
    return None


def _average(values: list[float]) -> float | None:
    if not values:
        return None
    return _round(sum(values) / len(values))


def _history_window(db: Session, *, start: datetime, end: datetime) -> list[MetricHistory]:
    return list(
        db.scalars(
            select(MetricHistory)
            .where(MetricHistory.timestamp >= start, MetricHistory.timestamp <= end)
            .order_by(MetricHistory.timestamp.asc())
        ).all()
    )


def _series(rows: list[MetricHistory], field: str) -> list[AnalyticsSeriesPoint]:
    points: list[AnalyticsSeriesPoint] = []
    for bucket in aggregate_history(rows, "1h"):
        points.append(
            AnalyticsSeriesPoint(
                timestamp=bucket["timestamp"],
                label=as_utc(bucket["timestamp"]).strftime("%H:%M"),
                value=_round(bucket.get(field)),
            )
        )
    return points


def _latest_photo(db: Session) -> OpsSnapshot | None:
    return db.scalar(
        select(OpsSnapshot)
        .where(OpsSnapshot.kind == "photo")
        .order_by(OpsSnapshot.observed_at.desc())
        .limit(1)
    )


def _photo_growth(db: Session, now: datetime) -> tuple[int, dict[str, int], dict[str, int]]:
    latest = _latest_photo(db)
    current_used = as_int(latest.payload.get("storage_used")) if latest else 0
    current_photos = as_int(latest.payload.get("indexed_photos")) if latest else 0
    start_today = _start_of_local_day(now)
    start_yesterday = start_today - timedelta(days=1)
    start_week = start_today - timedelta(days=7)
    used_yesterday = _value_at_or_before(db, "photo", "storage_used", start_today) or 0
    used_week = _value_at_or_before(db, "photo", "storage_used", start_week) or 0
    photos_start_today = _value_at_or_before(db, "photo", "indexed_photos", start_today)
    photos_start_yesterday = _value_at_or_before(db, "photo", "indexed_photos", start_yesterday)
    photos_week = _value_at_or_before(db, "photo", "indexed_photos", start_week)
    today_growth = (
        max(0, current_photos - photos_start_today) if photos_start_today is not None else 0
    )
    yesterday_growth = (
        max(0, photos_start_today - photos_start_yesterday)
        if photos_start_today is not None and photos_start_yesterday is not None
        else 0
    )
    week_growth = max(0, current_photos - photos_week) if photos_week is not None else 0
    photos_two_weeks = _value_at_or_before(
        db, "photo", "indexed_photos", start_week - timedelta(days=7)
    )
    photos_month = _value_at_or_before(
        db, "photo", "indexed_photos", start_today - timedelta(days=30)
    )
    used_month = (
        _value_at_or_before(db, "photo", "storage_used", start_today - timedelta(days=30)) or 0
    )
    last_week_growth = (
        max(0, photos_week - photos_two_weeks)
        if photos_week is not None and photos_two_weeks is not None
        else 0
    )
    month_growth = max(0, current_photos - photos_month) if photos_month is not None else 0
    capacity = as_int(latest.payload.get("capacity_bytes")) if latest else 0
    growth = {
        "today": today_growth,
        "yesterday": yesterday_growth,
        "this_week": week_growth,
        "last_week": last_week_growth,
        "this_month": month_growth,
    }
    storage = {
        "today": current_used,
        "yesterday": used_yesterday,
        "last_week": used_week,
        "last_month": used_month,
        "capacity": capacity,
    }
    return current_photos, storage, growth


def _backup_rows(db: Session) -> list[OpsSnapshot]:
    return list(
        db.scalars(
            select(OpsSnapshot)
            .where(OpsSnapshot.kind == "backup")
            .order_by(OpsSnapshot.observed_at.asc())
        ).all()
    )


def _success_rate(rows: list[OpsSnapshot]) -> float | None:
    counted = 0
    successes = 0
    for row in rows:
        status = _status_from_payload(row.payload)
        if status == "running":
            continue
        if status in {"success", "failed"}:
            counted += 1
            if status == "success":
                successes += 1
    if counted == 0:
        return None
    return _round((successes / counted) * 100)


class AnalyticsService:
    def cpu(self, db: Session, *, now: datetime | None = None) -> AnalyticsCpuResponse:
        end = now or _now()
        rows = _history_window(db, start=end - timedelta(hours=24), end=end)
        values = _values(rows, "cpu_percent")
        return AnalyticsCpuResponse(
            current=_current(rows, "cpu_percent"),
            average_24h=_average(values),
            minimum=_round(min(values)) if values else None,
            maximum=_round(max(values)) if values else None,
            series=_series(rows, "cpu_percent"),
        )

    def memory(self, db: Session, *, now: datetime | None = None) -> AnalyticsMemoryResponse:
        end = now or _now()
        rows = _history_window(db, start=end - timedelta(hours=24), end=end)
        return AnalyticsMemoryResponse(
            current=_current(rows, "memory_percent"),
            average=_average(_values(rows, "memory_percent")),
            series=_series(rows, "memory_percent"),
        )

    def storage(self, db: Session, *, now: datetime | None = None) -> AnalyticsStorageResponse:
        end = now or _now()
        rows = _history_window(db, start=end - timedelta(hours=24), end=end)
        _, storage, _ = _photo_growth(db, end)
        return AnalyticsStorageResponse(
            current=storage["today"],
            daily_growth=max(0, storage["today"] - storage["yesterday"]),
            weekly_growth=max(0, storage["today"] - storage["last_week"]),
            series=_series(rows, "disk_percent"),
        )

    def temperature(
        self, db: Session, *, now: datetime | None = None
    ) -> AnalyticsTemperatureResponse:
        end = now or _now()
        rows = _history_window(db, start=end - timedelta(hours=24), end=end)
        return AnalyticsTemperatureResponse(
            current=_current(rows, "temperature_celsius"),
            average=_average(_values(rows, "temperature_celsius")),
            series=_series(rows, "temperature_celsius"),
        )

    def photos(self, db: Session, *, now: datetime | None = None) -> AnalyticsPhotosResponse:
        end = now or _now()
        _, _, growth = _photo_growth(db, end)
        return AnalyticsPhotosResponse(
            today=growth["today"],
            yesterday=growth["yesterday"],
            this_week=growth["this_week"],
            growth=growth["this_week"],
            series=[
                AnalyticsSeriesPoint(label="Today", value=float(growth["today"])),
                AnalyticsSeriesPoint(label="Yesterday", value=float(growth["yesterday"])),
                AnalyticsSeriesPoint(label="This week", value=float(growth["this_week"])),
            ],
        )

    def backup(self, db: Session, *, now: datetime | None = None) -> AnalyticsBackupResponse:
        del now
        rows = _backup_rows(db)
        latest = rows[-1] if rows else None
        last_backup = ""
        duration: int | None = None
        if latest is not None:
            last_backup = as_str(
                latest.payload.get("last_backup") or latest.payload.get("last_success")
            )
            duration = as_int(latest.payload.get("duration_seconds")) or None
            if not last_backup:
                last_backup = as_utc(latest.observed_at).isoformat()
        series: list[AnalyticsSeriesPoint] = []
        for row in rows:
            seconds = as_int(row.payload.get("duration_seconds"))
            if seconds <= 0:
                continue
            stamp = as_utc(row.observed_at)
            series.append(
                AnalyticsSeriesPoint(
                    timestamp=stamp,
                    label=stamp.strftime("%m-%d %H:%M"),
                    value=float(seconds),
                )
            )
        return AnalyticsBackupResponse(
            last_backup=last_backup,
            duration_seconds=duration,
            success_rate=_success_rate(rows),
            series=series,
        )

    def overview(self, db: Session, *, now: datetime | None = None) -> AnalyticsOverviewResponse:
        end = now or _now()
        start_today = _start_of_day(end)
        cpu = self.cpu(db, now=end)
        memory = self.memory(db, now=end)
        storage = self.storage(db, now=end)
        temperature = self.temperature(db, now=end)
        photos = self.photos(db, now=end)
        backup = self.backup(db, now=end)
        agents = list(db.scalars(select(Agent)).all())
        agents_total = len(agents)
        agents_online = online_count(presence_for_agents(db, agents, now=end))
        alerts_today = (
            db.scalar(select(func.count()).select_from(Alert).where(Alert.opened_at >= start_today))
            or 0
        )
        notifications_today = (
            db.scalar(
                select(func.count())
                .select_from(Notification)
                .where(Notification.created_at >= start_today)
            )
            or 0
        )
        history_today = (
            db.scalar(
                select(func.count())
                .select_from(MetricHistory)
                .where(MetricHistory.timestamp >= start_today)
            )
            or 0
        )
        return AnalyticsOverviewResponse(
            cpu_average=cpu.average_24h,
            memory_average=memory.average,
            storage_used=storage.current,
            photos_today=photos.today,
            backup_success_rate=backup.success_rate,
            temperature_average=temperature.average,
            daily=AnalyticsDailyOverview(
                agents_total=int(agents_total),
                agents_online=int(agents_online),
                alerts_today=int(alerts_today),
                notifications_today=int(notifications_today),
                history_points_today=int(history_today),
            ),
        )

    def average_for(
        self,
        db: Session,
        field: str,
        *,
        hours: int,
        now: datetime | None = None,
    ) -> float | None:
        end = now or _now()
        rows = _history_window(db, start=end - timedelta(hours=hours), end=end)
        return _average(_values(rows, field))

    def average_between(
        self,
        db: Session,
        field: str,
        *,
        start: datetime,
        end: datetime,
    ) -> float | None:
        rows = _history_window(db, start=start, end=end)
        return _average(_values(rows, field))

    def daily_series(
        self,
        db: Session,
        field: str,
        *,
        days: int,
        now: datetime | None = None,
    ) -> list[AnalyticsSeriesPoint]:
        end = now or _now()
        rows = _history_window(db, start=end - timedelta(days=days), end=end)
        buckets: dict[datetime, list[float]] = {}
        for row in rows:
            day = as_utc(row.timestamp).replace(hour=0, minute=0, second=0, microsecond=0)
            value = getattr(row, field)
            if value is None:
                continue
            buckets.setdefault(day, []).append(float(value))
        points: list[AnalyticsSeriesPoint] = []
        for day in sorted(buckets):
            points.append(
                AnalyticsSeriesPoint(
                    timestamp=day,
                    label=day.strftime("%m-%d"),
                    value=_average(buckets[day]),
                )
            )
        return points

    def photo_detail(
        self, db: Session, *, now: datetime | None = None
    ) -> tuple[int, dict[str, int], dict[str, int]]:
        return _photo_growth(db, now or _now())

    def backup_snapshots(self, db: Session) -> list[OpsSnapshot]:
        return _backup_rows(db)
