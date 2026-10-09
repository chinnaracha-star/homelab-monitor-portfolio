import asyncio
import logging
import os
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from homelab_monitor.database import get_engine
from homelab_monitor.jobs.repetition import run_repeated
from homelab_monitor.notifications.retry import retry_transient
from homelab_monitor.notifications.service import NotificationService
from homelab_monitor.photo_baseline import baseline_file_path, load_baseline, save_baseline
from homelab_monitor.photo_events import PhotoEventRepository, resolved_watch_folders
from homelab_monitor.photo_folders import inspect_watch_folder
from homelab_monitor.photo_telegram import format_new_photo_message
from homelab_monitor.realtime import hub
from homelab_monitor.settings import Settings
from homelab_monitor.sqlite_diagnostics import writer_operation
from homelab_monitor.telegram import TelegramNotificationError, TelegramNotifier

logger = logging.getLogger("homelab_monitor.photo_watcher")

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".heic", ".gif", ".bmp", ".webp"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv"}
IGNORE_SUFFIXES = {".tmp", ".part"}
ALLOWED_INTERVALS = {5, 10, 30, 60}
PHOTO_BATCH_WINDOW_SECONDS = 10
STABLE_SIZE_SETTLE_SECONDS = 0.2
ALLOWED_MAX_EVENTS = {100, 500, 1000}
ALLOWED_AUTO_DELETE_DAYS = {0, 30, 90}


def is_ignored_name(name: str) -> bool:
    if name.startswith("."):
        return True
    lowered = name.lower()
    return any(lowered.endswith(suffix) for suffix in IGNORE_SUFFIXES)


def is_image_file(path: Path) -> bool:
    if is_ignored_name(path.name):
        return False
    return path.suffix.lower() in IMAGE_EXTENSIONS


def path_is_hidden(path: Path, root: Path) -> bool:
    try:
        relative = path.relative_to(root)
    except ValueError:
        relative = path
    return any(part.startswith(".") for part in relative.parts)


def _skip(reason: str, path: Path, **detail: object) -> None:
    extra = " ".join(f"{key}={value}" for key, value in detail.items())
    name = path.name.encode("utf-8", "replace").decode("utf-8")
    if extra:
        logger.debug("SKIP: %s file=%s %s", reason, name, extra)
    else:
        logger.debug("SKIP: %s file=%s", reason, name)


def _entry_is_file(path: Path) -> bool | None:
    try:
        return path.is_file()
    except OSError as exc:
        if path.suffix.lower() in IMAGE_EXTENSIONS and not is_ignored_name(path.name):
            logger.debug(
                "cifs_stat_unknown_including_candidate file=%s reason=%s",
                path.name.encode("utf-8", "replace").decode("utf-8"),
                exc.strerror or exc,
            )
            return True
        _skip("stat failed", path, reason=exc.strerror or str(exc))
        return None


def iter_image_files(watch_folder: Path, recursive: bool) -> list[Path]:
    if not watch_folder.is_dir():
        logger.info("scan_ended reason=not_a_directory folder=%s", watch_folder)
        return []
    files: list[Path] = []

    def on_walk_error(error: OSError) -> None:
        logger.warning(
            "walk_error folder=%s error=%s",
            error.filename,
            error.strerror or error,
        )

    try:
        if recursive:
            for dirpath, dirnames, filenames in os.walk(
                watch_folder, followlinks=False, onerror=on_walk_error
            ):
                dirnames[:] = [name for name in dirnames if not name.startswith(".")]
                current = Path(dirpath)
                for name in filenames:
                    if name.startswith("."):
                        continue
                    try:
                        candidate = current / name
                        if _include_candidate(candidate, watch_folder):
                            files.append(candidate)
                    except Exception:
                        logger.exception("SKIP: candidate_failed file=%s", name)
        else:
            with os.scandir(watch_folder) as entries:
                for entry in entries:
                    if entry.name.startswith("."):
                        continue
                    try:
                        candidate = Path(entry.path)
                        if _include_candidate(candidate, watch_folder):
                            files.append(candidate)
                    except Exception:
                        logger.exception("SKIP: candidate_failed file=%s", entry.name)
    except OSError as exc:
        logger.info(
            "scan_ended reason=walk_failed folder=%s error=%s",
            watch_folder,
            exc.strerror or exc,
        )
        return files
    return files


def _include_candidate(candidate: Path, root: Path) -> bool:
    if path_is_hidden(candidate, root):
        _skip("hidden file", candidate)
        return False
    if any(candidate.name.lower().endswith(suffix) for suffix in IGNORE_SUFFIXES):
        _skip("partial upload", candidate)
        return False
    if candidate.name.startswith("."):
        _skip("hidden file", candidate)
        return False
    is_file = _entry_is_file(candidate)
    if is_file is None:
        return False
    if not is_file:
        if candidate.suffix.lower() in IMAGE_EXTENSIONS:
            _skip("not a file", candidate)
        return False
    if candidate.suffix.lower() not in IMAGE_EXTENSIONS:
        _skip("unsupported extension", candidate)
        return False
    logger.debug("discovered filename=%s path=%s", candidate.name, candidate)
    return True


def file_created_at(path: Path) -> datetime:
    stamp = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
    return stamp


def wait_stable_size(path: Path, *, settle_seconds: float) -> int | None:
    try:
        first = path.stat().st_size
        if settle_seconds > 0:
            time.sleep(settle_seconds)
        second = path.stat().st_size
    except OSError:
        return None
    if first <= 0 or first != second:
        return None
    return second


@dataclass
class _PendingPhoto:
    event_id: int
    filename: str
    folder: str
    size_bytes: int
    created_at: datetime
    image_path: str = ""


def iter_recent_month_images(watch_folder: Path) -> list[Path]:
    """Phone gallery uploads land in YYYY/MM. Check that directory before the full share walk."""
    now = datetime.now()
    year = f"{now.year:04d}"
    month = f"{now.month:02d}"
    candidates = [watch_folder / year / month]
    try:
        children = [
            child
            for child in watch_folder.iterdir()
            if child.is_dir() and not child.name.startswith(".")
        ]
    except OSError:
        children = []
    candidates.extend(child / year / month for child in children)
    files: list[Path] = []
    ignored_videos = 0
    for folder in candidates:
        try:
            if not folder.is_dir():
                continue
            files.extend(iter_image_files(folder, recursive=False))
            ignored_videos += sum(
                1
                for path in folder.iterdir()
                if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS
            )
        except OSError:
            continue
    if ignored_videos:
        logger.info(
            "ignored_video month=%s-%s count=%s",
            year,
            month,
            ignored_videos,
        )
    return files


def _priority_watch_folders(folders: list[str]) -> list[str]:
    """Scan phone shares before the large aggregate folder so Telegram is not stuck behind it."""

    def rank(folder: str) -> tuple[int, str]:
        name = folder.rstrip("/").lower()
        if name.endswith("photos"):
            return (1, name)
        return (0, name)

    return sorted(folders, key=rank)


def _file_key(path: Path) -> tuple[str, str]:
    return (os.path.normpath(str(path.parent)), path.name)


class PhotoWatcherService:
    def __init__(
        self,
        settings: Settings,
        *,
        baseline_path: Path | None = None,
        batch_window_seconds: float = PHOTO_BATCH_WINDOW_SECONDS,
        settle_seconds: float = STABLE_SIZE_SETTLE_SECONDS,
    ) -> None:
        self._settings = settings
        self._baseline_path = baseline_path or baseline_file_path(settings)
        self._seen = load_baseline(self._baseline_path)
        self._primed: set[str] = set(self._seen)
        self._dirty = False
        self._logged_enabled: bool | None = None
        self.batch_window_seconds = batch_window_seconds
        self.settle_seconds = settle_seconds
        self._pending: list[_PendingPhoto] = []
        self._pending_since: datetime | None = None
        self.indexed_files = 0
        self.last_folders: list[str] = []
        self.events_today = 0
        self.telegram_ok_total = 0
        self.telegram_failed_total = 0
        self.last_successful_scan: datetime | None = None
        self.last_scan_duration_ms: float | None = None
        self.last_successful_telegram: datetime | None = None
        self.last_telegram_error: str | None = None
        self.self_check_status = "unknown"
        self.self_check_label = "UNKNOWN"
        self.self_check_reasons: list[str] = []
        self._started_at = datetime.now(UTC)
        self._cycle_scan_ms = 0.0
        self._cycle_db_ms = 0.0
        self._cycle_telegram_ms = 0.0
        if self._primed:
            logger.info(
                "photo_baseline_restored folders=%s files=%s",
                len(self._primed),
                sum(len(keys) for keys in self._seen.values()),
            )

    def reset_baseline(self) -> None:
        self._primed = set()
        self._seen = {}
        self._dirty = True
        self._persist()

    def sync_watch_roots(self, folders: list[str]) -> None:
        incoming = {os.path.normpath(item) for item in folders}
        primed = {item for item in self._primed if item in incoming}
        seen = {key: value for key, value in self._seen.items() if key in incoming}
        if primed != self._primed or seen.keys() != self._seen.keys():
            self._dirty = True
        self._primed = primed
        self._seen = seen

    def _persist(self) -> None:
        if not self._dirty:
            return
        try:
            save_baseline(self._baseline_path, self._seen)
            self._dirty = False
        except OSError:
            logger.exception("photo_baseline_save_failed path=%s", self._baseline_path)

    def scan_once(
        self,
        db: Session,
        *,
        send_text: Callable[[str], dict] | None = None,
    ) -> int:
        logger.info("photo_watcher_tick")
        cycle_started = time.perf_counter()
        self._cycle_scan_ms = 0.0
        self._cycle_db_ms = 0.0
        self._cycle_telegram_ms = 0.0
        repo = PhotoEventRepository(db)
        with writer_operation("photo_settings_update"):
            config = repo.ensure_settings(self._settings)
            folders = _priority_watch_folders(
                [os.path.normpath(item) for item in resolved_watch_folders(config)]
            )
            self.last_folders = folders
            self.sync_watch_roots(folders)
            if not config.enabled:
                if self._logged_enabled is not False:
                    logger.info("Photo Monitor disabled")
                    self._logged_enabled = False
                self.indexed_files = 0
                db.commit()
                logger.info("scan_ended reason=disabled")
                return 0
            if not folders:
                db.commit()
                logger.info("scan_ended reason=no_watch_folders")
                return 0
            if self._logged_enabled is not True:
                self._log_startup(folders)
                self._logged_enabled = True
            logger.info("recursive=%s folders=%s", config.recursive, len(folders))
            recursive = config.recursive
            max_events = config.max_events
            auto_delete_days = config.auto_delete_days
            db.commit()
        self._restore_unsent(repo)
        created = 0
        scanned = 0
        skipped = 0
        telegram_ok = 0
        folders_scanned = 0
        for watch_root in folders:
            logger.info("loading_settings folder=%s", watch_root)
            try:
                reason = inspect_watch_folder(watch_root)
                accessible = reason is None
                logger.info(
                    "checking_folder folder=%s exists=%s accessible=%s",
                    watch_root,
                    Path(watch_root).exists(),
                    accessible,
                )
                if reason is not None:
                    logger.warning("⚠ Cannot access")
                    logger.warning("%s", watch_root)
                    logger.warning("Reason")
                    logger.warning("%s", reason)
                    logger.info("scan_ended reason=folder_unavailable folder=%s", watch_root)
                    continue
                folders_scanned += 1
                if watch_root in self._primed:
                    recent = iter_recent_month_images(Path(watch_root))
                    if recent:
                        added, folder_skipped, folder_telegram = self._scan_folder(
                            db,
                            repo,
                            watch_root=watch_root,
                            discovered=recent,
                            send_text=send_text,
                        )
                        created += added
                        skipped += folder_skipped
                        telegram_ok += folder_telegram
                        if added:
                            db.commit()
                            telegram_ok += self.flush_photo_notifications(
                                db,
                                repo,
                                send_text=send_text,
                                now=datetime.now(UTC)
                                + timedelta(seconds=self.batch_window_seconds),
                            )
                logger.info("scanning_files folder=%s recursive=%s", watch_root, recursive)
                walk_started = time.perf_counter()
                discovered = iter_image_files(Path(watch_root), recursive)
                self._cycle_scan_ms += (time.perf_counter() - walk_started) * 1000
                scanned += len(discovered)
                added, folder_skipped, folder_telegram = self._scan_folder(
                    db,
                    repo,
                    watch_root=watch_root,
                    discovered=discovered,
                    send_text=send_text,
                )
                created += added
                skipped += folder_skipped
                telegram_ok += folder_telegram
                logger.info("scan_complete folder=%s files=%s", watch_root, len(discovered))
            except Exception:
                logger.exception("scan_ended reason=folder_exception folder=%s", watch_root)
        self.indexed_files = scanned
        with writer_operation("photo_prune"):
            try:
                prune_started = time.perf_counter()
                repo.prune(max_events=max_events, auto_delete_days=auto_delete_days)
                self._cycle_db_ms += (time.perf_counter() - prune_started) * 1000
            except Exception:
                logger.exception("photo_watcher_prune_failed")
            commit_started = time.perf_counter()
            if created:
                db.commit()
                hub.notify_ingest(reason="photo_monitor", agent_id=None, alerts_changed=False)
            else:
                db.commit()
        telegram_ok += self.flush_photo_notifications(
            db, repo, send_text=send_text, now=datetime.now(UTC)
        )
        db.commit()
        self._cycle_db_ms += (time.perf_counter() - commit_started) * 1000
        persist_started = time.perf_counter()
        self._persist()
        self._cycle_db_ms += (time.perf_counter() - persist_started) * 1000
        self.last_successful_scan = datetime.now(UTC)
        self.events_today = repo.today_count()
        elapsed_ms = (time.perf_counter() - cycle_started) * 1000
        self.last_scan_duration_ms = round(elapsed_ms, 2)
        logger.info("Folders scanned: %s", folders_scanned)
        logger.info("Files discovered: %s", scanned)
        logger.info("New files: %s", created)
        logger.info("Skipped: %s", skipped)
        logger.info("Inserted: %s", created)
        logger.info("Telegram sent: %s", telegram_ok)
        logger.info("Elapsed scan time ms=%.2f", self._cycle_scan_ms)
        logger.info("Elapsed database time ms=%.2f", self._cycle_db_ms)
        logger.info("Elapsed telegram time ms=%.2f", self._cycle_telegram_ms)
        logger.info("Elapsed cycle time ms=%.2f", elapsed_ms)
        logger.info("scan_ended reason=cycle_complete created=%s", created)
        return created

    def _log_startup(self, folders: list[str]) -> None:
        logger.info("Photo Monitor enabled")
        logger.info("Watching %s folders", len(folders))
        for folder in folders:
            reason = inspect_watch_folder(folder)
            if reason is None:
                logger.info("✓ %s", folder)
                continue
            logger.warning("⚠ Cannot access")
            logger.warning("%s", folder)
            logger.warning("Reason")
            logger.warning("%s", reason)
        logger.info("current_month_selected month=%s", datetime.now().strftime("%Y-%m"))
        logger.info(
            "baseline_loaded folders=%s",
            len(self._primed),
        )
        self.startup_self_check(folders)

    def _database_writable(self) -> bool:
        url = str(self._settings.database_url)
        if url.startswith("sqlite:///"):
            raw = url.removeprefix("sqlite:///")
            if raw in {":memory:", ""}:
                return True
            path = Path(raw)
            parent = path.parent if str(path.parent) else Path(".")
            target = path if path.exists() else parent
            return os.access(target, os.W_OK)
        return True

    def startup_self_check(self, folders: list[str]) -> str:
        reasons: list[str] = []
        if not self._settings.photo_watcher_enabled:
            reasons.append("watcher_disabled")
        token = ""
        chat = ""
        try:
            token = self._settings.telegram_bot_token.get_secret_value().strip()
        except Exception:
            token = ""
        try:
            chat = str(self._settings.telegram_chat_id or "").strip()
        except Exception:
            chat = ""
        if not token or not chat:
            reasons.append("telegram_not_configured")
        if not folders:
            reasons.append("no_watch_folders")
        for folder in folders:
            problem = inspect_watch_folder(folder)
            if problem is not None:
                reasons.append(f"folder_unavailable:{folder}")
        if not self._database_writable():
            reasons.append("database_not_writable")
        warnings: list[str] = []
        if not self._primed:
            warnings.append("baseline_not_loaded")
        if reasons:
            status = "fail"
            label = "FAIL"
        elif warnings:
            status = "pass"
            label = "WARN"
        else:
            status = "pass"
            label = "PASS"
        self.self_check_status = status
        self.self_check_label = label
        self.self_check_reasons = [*reasons, *warnings]
        logger.info(
            "photo_monitor_self_check status=%s reasons=%s",
            label,
            ",".join(self.self_check_reasons) if self.self_check_reasons else "none",
        )
        return status

    def log_health(self) -> None:
        last_scan = self.last_successful_scan.isoformat() if self.last_successful_scan else "never"
        last_telegram = (
            self.last_successful_telegram.isoformat() if self.last_successful_telegram else "never"
        )
        baseline_size = sum(len(keys) for keys in self._seen.values())
        logger.info("Photo Monitor Health")
        logger.info("Running")
        logger.info("Watching folders %s", len(self.last_folders) or len(self._primed))
        logger.info("Current queue %s", len(self._pending))
        logger.info("Events today %s", self.events_today)
        logger.info(
            "Telegram OK/Failed %s/%s",
            self.telegram_ok_total,
            self.telegram_failed_total,
        )
        logger.info("Baseline size %s", baseline_size)
        logger.info("Last successful scan %s", last_scan)
        logger.info("Last successful Telegram %s", last_telegram)

    def _scan_folder(
        self,
        db: Session,
        repo: PhotoEventRepository,
        *,
        watch_root: str,
        discovered: list[Path],
        send_text: Callable[[str], dict] | None,
    ) -> tuple[int, int, int]:
        seen = self._seen.setdefault(watch_root, set())
        logger.info("seen_cache folder=%s size=%s", watch_root, len(seen))
        if watch_root not in self._primed:
            cutoff = self._started_at
            baseline_keys: set[tuple[str, str]] = set()
            fresh: list[Path] = []
            for path in discovered:
                try:
                    stamp = file_created_at(path)
                except OSError:
                    baseline_keys.add(_file_key(path))
                    continue
                if stamp >= cutoff:
                    fresh.append(path)
                else:
                    baseline_keys.add(_file_key(path))
            self._seen[watch_root] = baseline_keys
            self._primed.add(watch_root)
            self._dirty = True
            logger.info(
                "baseline_created folder=%s files=%s fresh=%s",
                watch_root,
                len(baseline_keys),
                len(fresh),
            )
            discovered = fresh
            seen = self._seen[watch_root]
            if not discovered:
                logger.info(
                    "scan_ended reason=baseline folder=%s files=%s",
                    watch_root,
                    len(baseline_keys),
                )
                return 0, len(baseline_keys), 0
        created = 0
        skipped = 0
        telegram_ok = 0
        for path in discovered:
            try:
                added, was_skip, sent = self._handle_discovered(
                    db, repo, seen, watch_root, path, send_text
                )
            except Exception:
                logger.exception("SKIP: candidate_failed file=%s", path.name)
                skipped += 1
                continue
            created += added
            skipped += was_skip
            telegram_ok += sent
        return created, skipped, telegram_ok

    def _handle_discovered(
        self,
        db: Session,
        repo: PhotoEventRepository,
        seen: set[tuple[str, str]],
        watch_root: str,
        path: Path,
        send_text: Callable[[str], dict] | None,
    ) -> tuple[int, int, int]:
        del send_text
        folder, filename = _file_key(path)
        key = (folder, filename)
        in_seen = key in seen
        logger.debug(
            "candidate folder=%s file=%s seen_cache_size=%s in_seen=%s",
            watch_root,
            filename,
            len(seen),
            in_seen,
        )
        if in_seen:
            _skip("already in _seen", path, folder=watch_root)
            return 0, 1, 0
        exists_started = time.perf_counter()
        exists = repo.exists(folder, filename)
        self._cycle_db_ms += (time.perf_counter() - exists_started) * 1000
        db.rollback()
        logger.debug("repo.exists=%s folder=%s file=%s", exists, folder, filename)
        if exists:
            _skip("repo.exists=True", path, folder=watch_root)
            seen.add(key)
            self._dirty = True
            return 0, 1, 0
        size_bytes = wait_stable_size(path, settle_seconds=self.settle_seconds)
        if size_bytes is None:
            _skip("size not stable", path, folder=watch_root)
            return 0, 1, 0
        created_at = file_created_at(path)
        logger.debug(
            "file_stat file=%s size=%s mtime=%s",
            filename,
            size_bytes,
            created_at.isoformat(),
        )
        logger.info("insert_begin folder=%s file=%s", folder, filename)
        try:
            insert_started = time.perf_counter()
            with writer_operation("photo_event_insert"):
                with db.begin_nested():
                    event = repo.add(
                        filename=filename,
                        folder=folder,
                        size_bytes=size_bytes,
                        created_at=created_at,
                        telegram_sent=False,
                    )
                self._cycle_db_ms += (time.perf_counter() - insert_started) * 1000
                db.commit()
        except IntegrityError:
            _skip("repo.exists=True", path, reason="integrity_error")
            seen.add(key)
            self._dirty = True
            return 0, 1, 0
        logger.info("insert_complete folder=%s file=%s", folder, filename)
        logger.info("new_photo_detected folder=%s file=%s", watch_root, filename)
        self._queue_pending(
            event_id=event.id,
            filename=filename,
            folder=watch_root,
            size_bytes=size_bytes,
            created_at=created_at,
            image_path=str(path),
        )
        seen.add(key)
        self._dirty = True
        return 1, 0, 0

    def _queue_pending(
        self,
        *,
        event_id: int,
        filename: str,
        folder: str,
        size_bytes: int,
        created_at: datetime,
        image_path: str = "",
    ) -> None:
        if self._pending_since is None:
            self._pending_since = datetime.now(UTC)
        self._pending.append(
            _PendingPhoto(
                event_id=event_id,
                filename=filename,
                folder=folder,
                size_bytes=size_bytes,
                created_at=created_at,
                image_path=image_path,
            )
        )

    def pending_flush_delay(self, now: datetime) -> int | None:
        if not self._pending or self._pending_since is None:
            return None
        remain = self.batch_window_seconds - (now - self._pending_since).total_seconds()
        if remain <= 0:
            return 0
        return max(1, int(remain))

    def flush_photo_notifications(
        self,
        db: Session,
        repo: PhotoEventRepository,
        *,
        send_text: Callable[[str], dict] | None,
        now: datetime,
    ) -> int:
        if not self._pending or self._pending_since is None:
            return 0
        elapsed = (now - self._pending_since).total_seconds()
        if elapsed < self.batch_window_seconds:
            return 0
        notifier = self._resolve_notifier()
        service = NotificationService(notifier) if notifier is not None else None
        sender = send_text or (service.send_text if service is not None else None)
        if sender is None:
            self.telegram_failed_total += 1
            return 0
        grouped: dict[str, list[_PendingPhoto]] = {}
        for item in self._pending:
            grouped.setdefault(item.folder, []).append(item)
        sent_ids: list[int] = []
        messages = 0
        for folder, items in grouped.items():
            send_started = time.perf_counter()
            logger.info("telegram_send_begin folder=%s count=%s", folder, len(items))
            try:
                delivered = self._deliver_photo_group(items, folder, sender=sender, service=service)
            except TelegramNotificationError:
                self._cycle_telegram_ms += (time.perf_counter() - send_started) * 1000
                logger.exception("photo_telegram_failed")
                self.telegram_failed_total += 1
                continue
            except Exception:
                self._cycle_telegram_ms += (time.perf_counter() - send_started) * 1000
                logger.exception("photo_telegram_failed")
                self.telegram_failed_total += 1
                continue
            self._cycle_telegram_ms += (time.perf_counter() - send_started) * 1000
            missed = len(items) - len(delivered)
            if missed:
                self.telegram_failed_total += 1
            if not delivered:
                logger.warning("telegram_send_none folder=%s count=%s", folder, len(items))
                continue
            logger.info(
                "telegram_send_complete folder=%s count=%s delivered=%s",
                folder,
                len(items),
                len(delivered),
            )
            sent_ids.extend(delivered)
            messages += 1
            self.telegram_ok_total += 1
            self.last_successful_telegram = datetime.now(UTC)
        with writer_operation("photo_notification_mark_sent"):
            repo.mark_telegram_sent(sent_ids)
            db.commit()
        sent = set(sent_ids)
        self._pending = [item for item in self._pending if item.event_id not in sent]
        if not self._pending:
            self._pending_since = None
        return messages

    def _restore_unsent(self, repo: PhotoEventRepository) -> None:
        pending_ids = {item.event_id for item in self._pending}
        restored = False
        for event in repo.list_unsent():
            if event.id in pending_ids:
                continue
            folder = event.folder
            self._pending.append(
                _PendingPhoto(
                    event_id=event.id,
                    filename=event.filename,
                    folder=folder,
                    size_bytes=event.size_bytes,
                    created_at=event.created_at,
                    image_path=os.path.join(event.folder, event.filename),
                )
            )
            pending_ids.add(event.id)
            restored = True
        if restored and self._pending_since is None:
            self._pending_since = datetime(1970, 1, 1, tzinfo=UTC)

    def _deliver_photo_group(
        self,
        items: list[_PendingPhoto],
        folder: str,
        *,
        sender: Callable[[str], dict],
        service: NotificationService | None,
    ) -> list[int]:
        delivered: list[int] = []
        for item in items:
            message = format_new_photo_message(
                filename=item.filename,
                folder=folder,
                size_bytes=item.size_bytes,
                created_at=item.created_at,
            )
            image = Path(item.image_path) if item.image_path else Path(item.folder) / item.filename
            sent = False
            if service is not None:
                try:
                    retry_transient(
                        lambda img=image, cap=message: service.send_photo(img, caption=cap)
                    )
                    sent = True
                except Exception as exc:
                    self.last_telegram_error = str(exc)
                    logger.error(
                        "photo_send_photo_fallback file=%s reason=%s",
                        item.filename,
                        exc,
                    )
            if not sent:
                try:
                    retry_transient(lambda send=sender, text=message: send(text))
                    sent = True
                except Exception as exc:
                    self.last_telegram_error = str(exc)
                    logger.error(
                        "photo_telegram_delivery_failed file=%s reason=%s",
                        item.filename,
                        exc,
                    )
            if sent:
                delivered.append(item.event_id)
                logger.info("telegram_sent folder=%s file=%s", folder, item.filename)
        return delivered

    def _resolve_notifier(self) -> TelegramNotifier | None:
        try:
            return TelegramNotifier.from_settings(self._settings)
        except ValueError:
            logger.warning("photo_telegram_config_invalid")
            return None

    def _drop_pending_folder(self, folder: str) -> None:
        self._pending = [item for item in self._pending if item.folder != folder]
        if not self._pending:
            self._pending_since = None


_service: PhotoWatcherService | None = None


def get_photo_watcher_service(settings: Settings) -> PhotoWatcherService:
    global _service
    if _service is None:
        _service = PhotoWatcherService(settings)
    return _service


def reset_photo_watcher_service() -> None:
    global _service
    _service = None


def _next_interval(value: object) -> int:
    try:
        seconds = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 5
    if seconds in ALLOWED_INTERVALS:
        return seconds
    return 5


async def run_photo_watcher_interval(
    operation: Callable[[], Awaitable[int]],
    *,
    sleep: Callable[[float], Awaitable[None]] | None = None,
) -> None:
    interval = await operation()
    delay = max(_next_interval(interval), 5)
    logger.info("photo_watcher_sleep seconds=%s", delay)
    sleeper = asyncio.sleep if sleep is None else sleep
    await sleeper(delay)


async def run_photo_watcher(settings: Settings) -> None:
    logger.info("photo_watcher_started")
    try:
        if not settings.photo_watcher_enabled:
            logger.info("photo_watcher_disabled")
            logger.info("scan_ended reason=process_disabled")
            return

        service = get_photo_watcher_service(settings)
        last_health = 0.0

        async def scan_for_interval() -> int:
            nonlocal last_health
            interval = 5
            try:
                interval = await asyncio.to_thread(_scan_and_interval, settings, service)
                logger.info("photo_watcher_scan_finished interval=%s", interval)
                now = time.monotonic()
                if last_health == 0.0 or now - last_health >= 60:
                    service.log_health()
                    last_health = now
            except Exception:
                logger.exception("photo_watcher_failed")
                logger.info("scan_ended reason=scan_exception")
                interval = 5
            return interval

        try:
            await run_repeated(lambda: run_photo_watcher_interval(scan_for_interval))
        except asyncio.CancelledError:
            logger.info("photo_watcher_cancelled")
            logger.info("scan_ended reason=cancelled")
            raise
    finally:
        logger.info("photo_watcher_stopped")


def _scan_and_interval(settings: Settings, service: PhotoWatcherService) -> int:
    del settings
    with Session(get_engine()) as db:
        service.scan_once(db)
        if db.in_transaction():
            db.commit()
        row = PhotoEventRepository(db).get_settings()
        if row is None:
            logger.info("scan_ended reason=settings_missing")
            return 5
        interval = _next_interval(row.scan_interval_seconds)
        remaining = service.pending_flush_delay(datetime.now(UTC))
        if remaining is None:
            return interval
        if remaining == 0:
            return interval
        return min(interval, remaining)
