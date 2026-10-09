import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from homelab_monitor.database import get_engine
from homelab_monitor.models import PhotoEvent
from homelab_monitor.photo_events import PhotoEventRepository, apply_watch_folders
from homelab_monitor.photo_watcher import PhotoWatcherService
from homelab_monitor.settings import get_settings
from homelab_monitor.sqlite_diagnostics import active_connections


def _service(tmp_path: Path, folder: Path) -> PhotoWatcherService:
    settings = get_settings().model_copy(
        update={
            "photo_watch_folders": [str(folder)],
            "photo_watch_folder": str(folder),
            "photo_watcher_enabled": True,
        }
    )
    with Session(get_engine()) as db:
        row = PhotoEventRepository(db).ensure_settings(settings)
        row.enabled = True
        row.recursive = True
        apply_watch_folders(row, [str(folder)])
        db.commit()
    return PhotoWatcherService(
        settings,
        baseline_path=tmp_path / "baseline.json",
        batch_window_seconds=0,
        settle_seconds=0,
    )


def test_mark_sent_releases_connection_before_directory_walk(tmp_path: Path, monkeypatch) -> None:
    folder = tmp_path / "pictures"
    image = folder / "2026" / "10" / "new.jpg"
    image.parent.mkdir(parents=True)
    image.write_bytes(b"jpeg")
    service = _service(tmp_path, folder)
    service._primed.add(str(folder))
    service._seen[str(folder)] = set()
    entered = threading.Event()
    release = threading.Event()
    during: dict[str, object] = {}

    def recent(_path: Path) -> list[Path]:
        return [image]

    def walk(_path: Path, _recursive: bool) -> list[Path]:
        during["connections"] = active_connections()
        entered.set()
        assert release.wait(2)
        return []

    monkeypatch.setattr("homelab_monitor.photo_watcher.iter_recent_month_images", recent)
    monkeypatch.setattr("homelab_monitor.photo_watcher.iter_image_files", walk)
    monkeypatch.setattr("homelab_monitor.photo_watcher.hub.notify_ingest", lambda **_kwargs: None)

    def send(_message: str) -> dict:
        return {"ok": True}

    holder: dict[str, object] = {}

    def run() -> None:
        with Session(get_engine()) as db:
            holder["created"] = service.scan_once(db, send_text=send)

    thread = threading.Thread(target=run)
    thread.start()
    assert entered.wait(2)
    release.set()
    thread.join(2)
    connections = during["connections"]
    assert isinstance(connections, list)
    assert connections == []
    assert thread.is_alive() is False
    with Session(get_engine()) as db:
        row = db.scalar(select(PhotoEvent).where(PhotoEvent.filename == "new.jpg"))
        assert row is not None
        assert row.telegram_sent is True


def test_exists_releases_connection_before_size_settle(tmp_path: Path, monkeypatch) -> None:
    folder = tmp_path / "pictures"
    image = folder / "fresh.jpg"
    image.parent.mkdir(parents=True)
    image.write_bytes(b"jpeg-bytes")
    service = _service(tmp_path, folder)
    paused = threading.Event()
    release = threading.Event()
    during: dict[str, object] = {}

    def settle(path: Path, *, settle_seconds: float) -> int:
        del path, settle_seconds
        during["connections"] = active_connections()
        paused.set()
        assert release.wait(2)
        return image.stat().st_size

    monkeypatch.setattr("homelab_monitor.photo_watcher.wait_stable_size", settle)
    holder: dict[str, object] = {}

    def run() -> None:
        with Session(get_engine()) as db:
            repo = PhotoEventRepository(db)
            holder["result"] = service._handle_discovered(db, repo, set(), str(folder), image, None)

    thread = threading.Thread(target=run)
    thread.start()
    assert paused.wait(2)
    release.set()
    thread.join(2)
    assert during["connections"] == []
    assert holder["result"] == (1, 0, 0)


def test_exists_rollback_sees_no_pending_orm_work(tmp_path: Path) -> None:
    folder = tmp_path / "pictures"
    image = folder / "known.jpg"
    image.parent.mkdir(parents=True)
    image.write_bytes(b"jpeg")
    service = _service(tmp_path, folder)
    observed: dict[str, int] = {}
    with Session(get_engine()) as db:
        db.add(
            PhotoEvent(
                filename="known.jpg",
                folder=str(folder),
                size_bytes=4,
                created_at=datetime.now(UTC) - timedelta(days=1),
                telegram_sent=True,
            )
        )
        db.commit()
        repo = PhotoEventRepository(db)
        original = db.rollback

        def checked_rollback() -> None:
            observed["new"] = len(db.new)
            observed["dirty"] = len(db.dirty)
            observed["deleted"] = len(db.deleted)
            original()

        db.rollback = checked_rollback  # type: ignore[method-assign]
        seen: set[tuple[str, str]] = set()
        result = service._handle_discovered(db, repo, seen, str(folder), image, None)
    assert observed == {"new": 0, "dirty": 0, "deleted": 0}
    assert result == (0, 1, 0)
    assert (str(image.parent), "known.jpg") in seen
