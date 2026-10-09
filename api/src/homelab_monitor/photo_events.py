import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from homelab_monitor.models import PhotoEvent, PhotoMonitorSettings
from homelab_monitor.photo_folders import DEFAULT_WATCH_FOLDERS
from homelab_monitor.settings import Settings
from homelab_monitor.telegram import BANGKOK

SETTINGS_ROW_ID = 1
logger = logging.getLogger("homelab_monitor.photo_monitor")


def normalize_watch_folders(*groups: list[str] | str | None) -> list[str]:
    unique: list[str] = []
    seen: set[str] = set()
    for group in groups:
        items = [group] if isinstance(group, str) else group or []
        for item in items:
            folder = str(item).strip()
            if not folder or folder in seen:
                continue
            seen.add(folder)
            unique.append(folder)
    return unique


def resolved_watch_folders(row: PhotoMonitorSettings) -> list[str]:
    stored = row.watch_folders if isinstance(row.watch_folders, list) else []
    folders = normalize_watch_folders(stored)
    if folders:
        return folders
    return normalize_watch_folders(row.watch_folder)


def apply_watch_folders(row: PhotoMonitorSettings, folders: list[str]) -> None:
    normalized = normalize_watch_folders(folders)
    row.watch_folders = normalized
    row.watch_folder = normalized[0] if normalized else ""


def with_default_nas_shares(folders: list[str]) -> list[str]:
    if not folders:
        return list(DEFAULT_WATCH_FOLDERS)
    if any(not item.startswith("/mnt/") for item in folders):
        return folders
    return normalize_watch_folders(folders, DEFAULT_WATCH_FOLDERS)


class PhotoEventRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_settings(self) -> PhotoMonitorSettings | None:
        return self._db.get(PhotoMonitorSettings, SETTINGS_ROW_ID)

    def ensure_settings(self, settings: Settings) -> PhotoMonitorSettings:
        row = self.get_settings()
        if row is not None:
            current = resolved_watch_folders(row)
            folders = with_default_nas_shares(current)
            if folders != current or not row.watch_folders or row.watch_folder != folders[0]:
                apply_watch_folders(row, folders)
                self._db.flush()
            return row
        folders = normalize_watch_folders(settings.photo_watch_folders) or normalize_watch_folders(
            settings.photo_watch_folder
        )
        if not folders:
            folders = list(DEFAULT_WATCH_FOLDERS)
        row = PhotoMonitorSettings(
            id=SETTINGS_ROW_ID,
            enabled=settings.photo_watcher_enabled,
            watch_folder=folders[0] if folders else "",
            watch_folders=folders,
            recursive=True,
            scan_interval_seconds=(
                settings.photo_scan_interval_seconds
                if settings.photo_scan_interval_seconds in {5, 10, 30, 60}
                else 5
            ),
            max_events=500,
            auto_delete_days=0,
        )
        self._db.add(row)
        self._db.flush()
        logger.info("Photo Monitor initialized")
        if row.enabled:
            logger.info("Photo Monitor enabled")
        else:
            logger.info("Photo Monitor disabled")
        logger.info("Watching %s folders", len(folders))
        return row

    def exists(self, folder: str, filename: str) -> bool:
        return (
            self._db.scalar(
                select(PhotoEvent.id).where(
                    PhotoEvent.folder == folder,
                    PhotoEvent.filename == filename,
                )
            )
            is not None
        )

    def add(
        self,
        *,
        filename: str,
        folder: str,
        size_bytes: int,
        created_at: datetime,
        telegram_sent: bool,
    ) -> PhotoEvent:
        event = PhotoEvent(
            filename=filename,
            folder=folder,
            size_bytes=size_bytes,
            created_at=created_at,
            telegram_sent=telegram_sent,
        )
        self._db.add(event)
        self._db.flush()
        return event

    def mark_telegram_sent(self, event_ids: list[int]) -> None:
        if not event_ids:
            return
        self._db.execute(
            update(PhotoEvent).where(PhotoEvent.id.in_(event_ids)).values(telegram_sent=True)
        )

    def list_unsent(self) -> list[PhotoEvent]:
        return list(
            self._db.scalars(
                select(PhotoEvent)
                .where(PhotoEvent.telegram_sent.is_(False))
                .order_by(PhotoEvent.created_at.asc(), PhotoEvent.id.asc())
            ).all()
        )

    def list_latest(self, limit: int = 20) -> list[PhotoEvent]:
        return list(
            self._db.scalars(
                select(PhotoEvent)
                .order_by(PhotoEvent.created_at.desc(), PhotoEvent.id.desc())
                .limit(limit)
            ).all()
        )

    def latest(self) -> PhotoEvent | None:
        return self._db.scalar(
            select(PhotoEvent).order_by(PhotoEvent.created_at.desc(), PhotoEvent.id.desc()).limit(1)
        )

    def today_count(self, now: datetime | None = None) -> int:
        clock = now or datetime.now(UTC)
        if clock.tzinfo is None:
            clock = clock.replace(tzinfo=UTC)
        start = clock.astimezone(BANGKOK).replace(hour=0, minute=0, second=0, microsecond=0)
        start_utc = start.astimezone(UTC)
        return int(
            self._db.scalar(
                select(func.count())
                .select_from(PhotoEvent)
                .where(PhotoEvent.created_at >= start_utc)
            )
            or 0
        )

    def prune(self, *, max_events: int, auto_delete_days: int, now: datetime | None = None) -> None:
        if auto_delete_days > 0:
            clock = now or datetime.now(UTC)
            if clock.tzinfo is None:
                clock = clock.replace(tzinfo=UTC)
            cutoff = clock - timedelta(days=auto_delete_days)
            self._db.execute(delete(PhotoEvent).where(PhotoEvent.created_at < cutoff))
        extra = (self._db.scalar(select(func.count()).select_from(PhotoEvent)) or 0) - max_events
        if extra <= 0:
            return
        oldest_ids = list(
            self._db.scalars(
                select(PhotoEvent.id)
                .order_by(PhotoEvent.created_at.asc(), PhotoEvent.id.asc())
                .limit(extra)
            ).all()
        )
        if oldest_ids:
            self._db.execute(delete(PhotoEvent).where(PhotoEvent.id.in_(oldest_ids)))
