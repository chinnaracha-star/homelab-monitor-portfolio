from datetime import UTC, datetime, timedelta, timezone, tzinfo
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.orm import Session

from homelab_monitor.connectors.base import ConnectorSnapshot
from homelab_monitor.connectors.http import as_int, as_str
from homelab_monitor.database import get_engine
from homelab_monitor.models import OpsSnapshot
from homelab_monitor.settings import get_settings

MOCK_STORAGE_TODAY = 4_980_000_000_000
MOCK_STORAGE_YESTERDAY = 4_850_000_000_000
MOCK_STORAGE_LAST_WEEK = 4_420_000_000_000
MOCK_PHOTO_GROWTH_TODAY = 250
MOCK_PHOTO_GROWTH_YESTERDAY = 180
MOCK_PHOTO_GROWTH_WEEK = 1200
MOCK_BACKUP_HISTORY = (
    {"period": "yesterday", "label": "Yesterday", "status": "success"},
    {"period": "today", "label": "Today", "status": "running"},
    {"period": "last_week", "label": "Last Week", "status": "failed"},
)


def mock_storage_history() -> dict[str, int]:
    return {
        "today": MOCK_STORAGE_TODAY,
        "yesterday": MOCK_STORAGE_YESTERDAY,
        "last_week": MOCK_STORAGE_LAST_WEEK,
    }


def mock_photo_growth() -> dict[str, int]:
    return {
        "today": MOCK_PHOTO_GROWTH_TODAY,
        "yesterday": MOCK_PHOTO_GROWTH_YESTERDAY,
        "this_week": MOCK_PHOTO_GROWTH_WEEK,
    }


def mock_backup_history() -> list[dict[str, str]]:
    return [dict(item) for item in MOCK_BACKUP_HISTORY]


def record_photo_snapshot(stats: dict, *, observed_at: datetime | None = None) -> None:
    if get_settings().infrastructure_mock:
        return
    payload = {
        "indexed_photos": as_int(stats.get("indexed_photos")),
        "storage_used": as_int(stats.get("storage_used")),
        "capacity_bytes": as_int(stats.get("capacity_bytes")),
    }
    _record("photo", payload, observed_at=observed_at)


def record_backup_snapshot(snapshot: ConnectorSnapshot) -> None:
    summary = snapshot.summary
    payload = {
        "job_status": as_str(summary.get("job_status")),
        "backup_status": as_str(summary.get("backup_status")),
        "backup_health": as_str(summary.get("backup_health")),
        "progress_percent": summary.get("progress_percent") or 0,
        "last_backup": as_str(summary.get("last_backup")),
        "last_success": as_str(summary.get("last_success") or summary.get("last_backup")),
        "duration_seconds": as_int(summary.get("duration_seconds")),
        "backup_size_bytes": as_int(summary.get("backup_size_bytes")),
    }
    _record("backup", payload, observed_at=snapshot.updated_at)


def photo_trends(stats: dict, *, use_mock: bool) -> tuple[dict[str, int], dict[str, int]]:
    if use_mock:
        storage = mock_storage_history()
        storage["today"] = as_int(stats.get("storage_used")) or storage["today"]
        return storage, mock_photo_growth()
    with Session(get_engine()) as db:
        now = datetime.now(UTC)
        current_used = as_int(stats.get("storage_used"))
        current_photos = as_int(stats.get("indexed_photos"))
        start_today = _start_of_local_day(now)
        start_yesterday = start_today - timedelta(days=1)
        start_week = start_today - timedelta(days=7)
        used_today = current_used
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
        return (
            {"today": used_today, "yesterday": used_yesterday, "last_week": used_week},
            {"today": today_growth, "yesterday": yesterday_growth, "this_week": week_growth},
        )


def backup_history_periods(snapshot: ConnectorSnapshot, *, use_mock: bool) -> list[dict[str, str]]:
    if use_mock:
        return mock_backup_history()
    with Session(get_engine()) as db:
        now = datetime.now(UTC)
        start_today = _start_of_day(now)
        start_yesterday = start_today - timedelta(days=1)
        start_week = start_today - timedelta(days=7)
        current = _status_from_payload(
            {
                "job_status": as_str(snapshot.summary.get("job_status")),
                "backup_status": as_str(snapshot.summary.get("backup_status")),
            }
        )
        return [
            {
                "period": "yesterday",
                "label": "Yesterday",
                "status": _period_status(db, start_yesterday, start_today, "unknown"),
            },
            {
                "period": "today",
                "label": "Today",
                "status": _period_status(db, start_today, now + timedelta(seconds=1), current),
            },
            {
                "period": "last_week",
                "label": "Last Week",
                "status": _week_status(db, start_week, start_yesterday),
            },
        ]


def _record(kind: str, payload: dict, *, observed_at: datetime | None) -> None:
    stamp = observed_at or datetime.now(UTC)
    with Session(get_engine()) as db:
        db.add(OpsSnapshot(kind=kind, observed_at=stamp, payload=payload))
        db.commit()


def _local_timezone() -> tzinfo:
    try:
        return ZoneInfo("Asia/Bangkok")
    except ZoneInfoNotFoundError:
        return timezone(timedelta(hours=7))


def _start_of_day(value: datetime) -> datetime:
    return value.astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0)


def _start_of_local_day(value: datetime, tz: tzinfo | None = None) -> datetime:
    zone = tz or _local_timezone()
    local = value.astimezone(zone)
    start = local.replace(hour=0, minute=0, second=0, microsecond=0)
    return start.astimezone(UTC)


def _value_at_or_before(db: Session, kind: str, field: str, at: datetime) -> int | None:
    row = db.scalar(
        select(OpsSnapshot)
        .where(OpsSnapshot.kind == kind, OpsSnapshot.observed_at <= at)
        .order_by(OpsSnapshot.observed_at.desc())
        .limit(1)
    )
    if row is None:
        return None
    return as_int(row.payload.get(field))


def _period_status(db: Session, start: datetime, end: datetime, fallback: str) -> str:
    rows = list(
        db.scalars(
            select(OpsSnapshot)
            .where(
                OpsSnapshot.kind == "backup",
                OpsSnapshot.observed_at >= start,
                OpsSnapshot.observed_at < end,
            )
            .order_by(OpsSnapshot.observed_at.asc())
        ).all()
    )
    if not rows:
        return fallback
    return _status_from_payload(rows[-1].payload)


def _week_status(db: Session, start: datetime, end: datetime) -> str:
    rows = list(
        db.scalars(
            select(OpsSnapshot)
            .where(
                OpsSnapshot.kind == "backup",
                OpsSnapshot.observed_at >= start,
                OpsSnapshot.observed_at < end,
            )
            .order_by(OpsSnapshot.observed_at.asc())
        ).all()
    )
    if not rows:
        return "unknown"
    statuses = [_status_from_payload(row.payload) for row in rows]
    if "failed" in statuses:
        return "failed"
    return statuses[-1]


def _status_from_payload(payload: dict) -> str:
    job = as_str(payload.get("job_status")).lower()
    result = as_str(payload.get("backup_status")).lower()
    if job == "running":
        return "running"
    if job == "failed" or result == "failed":
        return "failed"
    if result == "success" or job in {"idle", "success"}:
        return "success"
    return result or job or "unknown"
