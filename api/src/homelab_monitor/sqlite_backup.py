from __future__ import annotations

import asyncio
import gzip
import json
import logging
import sqlite3
import time
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from homelab_monitor.jobs.repetition import run_repeated
from homelab_monitor.notifications.service import NotificationService
from homelab_monitor.settings import Settings
from homelab_monitor.telegram import TelegramNotificationError

logger = logging.getLogger("homelab_monitor.sqlite_backup")

FILENAME_PREFIX = "homelab-monitor-"
FILENAME_SUFFIX = ".sqlite3.gz"
STATE_NAME = "sqlite-backup-state.json"
BANGKOK = ZoneInfo("Asia/Bangkok")


@dataclass
class BackupResult:
    ok: bool
    path: str = ""
    created_at: str = ""
    duration_seconds: float = 0
    uncompressed_bytes: int = 0
    compressed_bytes: int = 0
    integrity: str = "FAIL"
    gzip_ok: bool = False
    size_ok: bool = False
    timestamp_ok: bool = False
    error: str = ""
    retained: list[str] | None = None

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["retained"] = self.retained or []
        return payload


def database_file(settings: Settings) -> Path | None:
    url = settings.database_url
    if not url.startswith("sqlite:///"):
        return None
    raw = url.removeprefix("sqlite:///")
    if not raw or raw == ":memory:":
        return None
    return Path(raw)


def backup_dir(settings: Settings) -> Path:
    return Path(settings.backup_path)


def parse_backup_time(value: str) -> tuple[int, int]:
    text = (value or "02:00").strip()
    hour_s, _, minute_s = text.partition(":")
    hour = int(hour_s or 2)
    minute = int(minute_s or 0)
    return max(0, min(23, hour)), max(0, min(59, minute))


def next_scheduled(settings: Settings, *, now: datetime | None = None) -> datetime:
    zone = ZoneInfo(settings.backup_timezone or "Asia/Bangkok")
    clock = now.astimezone(zone) if now else datetime.now(zone)
    hour, minute = parse_backup_time(settings.backup_time)
    candidate = clock.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if candidate <= clock:
        candidate += timedelta(days=1)
    return candidate


def seconds_until_next(settings: Settings, *, now: datetime | None = None) -> float:
    zone = ZoneInfo(settings.backup_timezone or "Asia/Bangkok")
    clock = now.astimezone(zone) if now else datetime.now(zone)
    return max(1.0, (next_scheduled(settings, now=clock) - clock).total_seconds())


def _state_path(settings: Settings) -> Path:
    return backup_dir(settings) / STATE_NAME


def load_state(settings: Settings) -> dict:
    path = _state_path(settings)
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_state(settings: Settings, payload: dict) -> None:
    path = _state_path(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def sqlite_status_payload(settings: Settings) -> dict:
    state = load_state(settings)
    latest = state.get("latest") or {}
    return {
        "enabled": settings.backup_enabled,
        "status": latest.get("status") or ("idle" if settings.backup_enabled else "disabled"),
        "latest_file": latest.get("path") or "",
        "latest_at": latest.get("created_at") or "",
        "size_bytes": int(latest.get("compressed_bytes") or 0),
        "uncompressed_bytes": int(latest.get("uncompressed_bytes") or 0),
        "next_scheduled": next_scheduled(settings).isoformat(),
        "retention_daily": settings.backup_retention_daily,
        "retention_weekly": settings.backup_retention_weekly,
        "retention_monthly": settings.backup_retention_monthly,
        "last_verification": latest.get("verified_at") or "",
        "integrity": latest.get("integrity") or "unknown",
        "stored_path": str(backup_dir(settings)),
        "duration_seconds": float(latest.get("duration_seconds") or 0),
        "error": latest.get("error") or "",
    }


def _copy_database(source: Path, destination: Path) -> None:
    src = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
    try:
        dst = sqlite3.connect(destination)
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()


def _integrity_ok(path: Path) -> bool:
    connection = sqlite3.connect(path)
    try:
        row = connection.execute("PRAGMA integrity_check").fetchone()
        return bool(row and str(row[0]).lower() == "ok")
    finally:
        connection.close()


def _gzip_ok(path: Path) -> bool:
    try:
        with gzip.open(path, "rb") as handle:
            while handle.read(1024 * 1024):
                pass
        return True
    except OSError:
        return False


def apply_retention(
    directory: Path, settings: Settings, *, keep_extra: Path | None = None
) -> list[str]:
    files = sorted(directory.glob(f"{FILENAME_PREFIX}*{FILENAME_SUFFIX}"))
    keep: set[Path] = set()
    if keep_extra is not None:
        keep.add(keep_extra)
    dated: list[tuple[datetime, Path]] = []
    for item in files:
        stamp = _stamp_from_name(item.name)
        if stamp is None:
            keep.add(item)
            continue
        dated.append((stamp, item))
    dated.sort(key=lambda pair: pair[0], reverse=True)
    keep.update(path for _, path in dated[: settings.backup_retention_daily])
    sundays = [path for stamp, path in dated if stamp.weekday() == 6]
    keep.update(sundays[: settings.backup_retention_weekly])
    monthlies = [path for stamp, path in dated if stamp.day == 1]
    keep.update(monthlies[: settings.backup_retention_monthly])
    deleted: list[str] = []
    for item in files:
        if item in keep:
            continue
        try:
            item.unlink()
            sidecar = item.with_suffix("").with_suffix(".json")
            if sidecar.is_file():
                sidecar.unlink()
            deleted.append(item.name)
        except OSError as error:
            logger.warning("backup_retention_delete_failed path=%s error=%s", item, error)
    return deleted


def _stamp_from_name(name: str) -> datetime | None:
    if not name.startswith(FILENAME_PREFIX) or not name.endswith(FILENAME_SUFFIX):
        return None
    raw = name[len(FILENAME_PREFIX) : -len(FILENAME_SUFFIX)]
    try:
        return datetime.strptime(raw, "%Y-%m-%d-%H%M%S").replace(tzinfo=BANGKOK)
    except ValueError:
        return None


def format_backup_telegram(result: BackupResult, settings: Settings) -> str:
    if result.ok:
        return (
            "💾 Backup Complete\n"
            "\n"
            "Database\n"
            f"{_mb(result.uncompressed_bytes)}\n"
            "\n"
            "Compressed\n"
            f"{_mb(result.compressed_bytes)}\n"
            "\n"
            "Duration\n"
            f"{result.duration_seconds:.1f} sec\n"
            "\n"
            "Integrity\n"
            f"{result.integrity}\n"
            "\n"
            "Stored\n"
            f"{settings.backup_path}\n"
            "\n"
            "Retention\n"
            f"{settings.backup_retention_daily} Daily\n"
            f"{settings.backup_retention_weekly} Weekly\n"
            f"{settings.backup_retention_monthly} Monthly"
        )
    return (
        "💾 Backup Failed\n"
        "\n"
        f"{result.error or 'Verification failed'}\n"
        "\n"
        "Previous backups were not deleted."
    )


def _mb(size: int) -> str:
    return f"{size / (1024 * 1024):.0f} MB" if size >= 1024 * 1024 else f"{size} B"


def _notify(settings: Settings, result: BackupResult) -> None:
    if not settings.telegram_enabled:
        return
    try:
        service = NotificationService.from_settings(settings)
    except Exception:
        logger.warning("backup_telegram_unavailable")
        return
    if service is None:
        return
    try:
        service.send_text(format_backup_telegram(result, settings))
    except TelegramNotificationError:
        logger.exception("backup_telegram_failed")
    finally:
        service.close()


def run_backup_once(settings: Settings, *, notify: bool = True) -> BackupResult:
    started = time.perf_counter()
    created = datetime.now(BANGKOK)
    source = database_file(settings)
    target_dir = backup_dir(settings)
    if source is None or not source.is_file():
        result = BackupResult(ok=False, error="SQLite database file is missing")
        _record_failure(settings, result, created)
        if notify:
            _notify(settings, result)
        return result
    target_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{FILENAME_PREFIX}{created.strftime('%Y-%m-%d-%H%M%S')}{FILENAME_SUFFIX}"
    archive = target_dir / filename
    if archive.exists():
        created = created + timedelta(seconds=1)
        filename = f"{FILENAME_PREFIX}{created.strftime('%Y-%m-%d-%H%M%S')}{FILENAME_SUFFIX}"
        archive = target_dir / filename
    tmp_db = target_dir / f".tmp-{created.strftime('%Y%m%d%H%M%S')}.sqlite3"
    try:
        _copy_database(source, tmp_db)
        uncompressed = tmp_db.stat().st_size
        sqlite_ok = _integrity_ok(tmp_db)
        with tmp_db.open("rb") as raw, gzip.open(archive, "wb") as compressed:
            while chunk := raw.read(1024 * 1024):
                compressed.write(chunk)
        gzip_ok = _gzip_ok(archive)
        compressed_size = archive.stat().st_size
        size_ok = compressed_size > 0 and uncompressed > 0
        timestamp_ok = _stamp_from_name(archive.name) is not None
        duration = round(time.perf_counter() - started, 2)
        integrity = "PASS" if sqlite_ok and gzip_ok and size_ok and timestamp_ok else "FAIL"
        result = BackupResult(
            ok=integrity == "PASS",
            path=str(archive),
            created_at=created.isoformat(),
            duration_seconds=duration,
            uncompressed_bytes=uncompressed,
            compressed_bytes=compressed_size,
            integrity=integrity,
            gzip_ok=gzip_ok,
            size_ok=size_ok,
            timestamp_ok=timestamp_ok,
            error="" if integrity == "PASS" else "Backup verification failed",
        )
        if result.ok:
            result.retained = apply_retention(target_dir, settings, keep_extra=archive)
            sidecar = {
                **result.to_dict(),
                "role": _role_for(created),
            }
            archive.with_name(archive.name.replace(FILENAME_SUFFIX, ".json")).write_text(
                json.dumps(sidecar, indent=2),
                encoding="utf-8",
            )
            save_state(
                settings,
                {
                    "latest": {
                        "status": "healthy",
                        "path": str(archive),
                        "created_at": result.created_at,
                        "compressed_bytes": result.compressed_bytes,
                        "uncompressed_bytes": result.uncompressed_bytes,
                        "duration_seconds": result.duration_seconds,
                        "integrity": result.integrity,
                        "verified_at": datetime.now(BANGKOK).isoformat(),
                        "error": "",
                    }
                },
            )
        else:
            failed = archive.with_suffix(archive.suffix + ".failed")
            archive.rename(failed)
            _record_failure(settings, result, created, path=str(failed))
        if notify:
            _notify(settings, result)
        logger.info("sqlite_backup_complete ok=%s path=%s", result.ok, result.path)
        return result
    except Exception as error:
        result = BackupResult(
            ok=False,
            duration_seconds=round(time.perf_counter() - started, 2),
            error=str(error),
        )
        _record_failure(settings, result, created)
        if notify:
            _notify(settings, result)
        logger.exception("sqlite_backup_failed")
        return result
    finally:
        tmp_db.unlink(missing_ok=True)


def _role_for(created: datetime) -> str:
    if created.day == 1:
        return "monthly"
    if created.weekday() == 6:
        return "weekly"
    return "daily"


def _record_failure(
    settings: Settings,
    result: BackupResult,
    created: datetime,
    *,
    path: str = "",
) -> None:
    previous = load_state(settings)
    latest = dict(previous.get("latest") or {})
    latest.update(
        {
            "status": "failed",
            "error": result.error,
            "integrity": "FAIL",
            "verified_at": created.isoformat(),
        }
    )
    if path:
        latest["failed_path"] = path
    save_state(settings, {"latest": latest})


async def run_backup_clock(
    settings: Settings,
    *,
    sleep: Callable[[float], Awaitable[None]] | None = None,
    run_once: Callable[[Settings], None] | None = None,
    now: datetime | None = None,
) -> None:
    """One wait of the backup clock inside the sqlite_backup task.

    Disabled mode sleeps 3600 seconds and returns. Otherwise this waits until
    the next occurrence, then calls run_backup_once. It does not loop and it
    does not create another task. A cancel during the wait skips the backup.
    A cancel after run_backup_once has started is still the existing race.
    """
    sleeper = asyncio.sleep if sleep is None else sleep
    operation = run_backup_once if run_once is None else run_once
    if not settings.backup_enabled:
        await sleeper(3600)
        return
    delay = seconds_until_next(settings, now=now)
    logger.info("sqlite_backup_sleep seconds=%s", round(delay))
    await sleeper(delay)
    await asyncio.to_thread(operation, settings)


async def run_sqlite_backup(settings: Settings) -> None:
    logger.info("sqlite_backup_scheduler_started")
    try:
        await run_repeated(lambda: run_backup_clock(settings))
    except asyncio.CancelledError:
        logger.info("sqlite_backup_scheduler_cancelled")
        raise
