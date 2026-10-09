import asyncio
import time
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from homelab_monitor.database import get_engine
from homelab_monitor.models import PhotoEvent
from homelab_monitor.photo_events import PhotoEventRepository, apply_watch_folders
from homelab_monitor.photo_folders import DEFAULT_WATCH_FOLDERS
from homelab_monitor.photo_watcher import PhotoWatcherService, run_photo_watcher
from homelab_monitor.settings import get_settings

NAS_BASENAMES = [Path(path).name for path in DEFAULT_WATCH_FOLDERS]


def _settings(folders: list[str]):
    return get_settings().model_copy(
        update={
            "photo_watch_folders": folders,
            "photo_watch_folder": folders[0],
            "photo_watcher_enabled": True,
        }
    )


def _write_image(path: Path, payload: bytes = b"img") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def _write_sized(path: Path, size_bytes: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        if size_bytes <= 1:
            handle.write(b"x")
            return
        handle.seek(size_bytes - 1)
        handle.write(b"x")


def _enable(service_folders: list[str], *, recursive: bool = True, max_events: int = 1000):
    settings = _settings(service_folders)
    with Session(get_engine()) as db:
        row = PhotoEventRepository(db).ensure_settings(settings)
        row.enabled = True
        row.recursive = recursive
        row.max_events = max_events
        apply_watch_folders(row, service_folders)
        db.commit()
    return settings


def _scan(service: PhotoWatcherService, send) -> int:
    with Session(get_engine()) as db:
        return service.scan_once(db, send_text=send)


def _event_count() -> int:
    with Session(get_engine()) as db:
        return int(db.scalar(select(func.count()).select_from(PhotoEvent)) or 0)


def test_qfile_auto_upload_nested_phone_path(tmp_path: Path, monkeypatch) -> None:
    watch = tmp_path / "library-a"
    nested = watch / "S22-Ultra" / "2026" / "09"
    nested.mkdir(parents=True)
    _write_image(nested / "old.jpg")
    settings = _enable([str(watch)])
    service = PhotoWatcherService(
        settings, baseline_path=tmp_path / "baseline.json", batch_window_seconds=0, settle_seconds=0
    )
    ingest = {"count": 0}

    def notify_ingest(**_kwargs) -> None:
        ingest["count"] += 1

    monkeypatch.setattr("homelab_monitor.photo_watcher.hub.notify_ingest", notify_ingest)
    sent: list[str] = []
    assert _scan(service, sent.append) == 0
    _write_image(nested / "FB_IMG_qfile.jpg", b"phone")
    created = _scan(service, sent.append)
    with Session(get_engine()) as db:
        latest = PhotoEventRepository(db).latest()
        assert created == 1
        assert latest is not None
        assert latest.filename == "FB_IMG_qfile.jpg"
        assert latest.folder == str(nested)
        assert latest.telegram_sent is True
    assert len(sent) == 1
    assert ingest["count"] == 1
    assert _scan(service, sent.append) == 0
    assert len(sent) == 1
    assert _event_count() == 1


def test_windows_explorer_copy_into_every_watch_folder(tmp_path: Path) -> None:
    folders = [tmp_path / name for name in NAS_BASENAMES]
    for folder in folders:
        folder.mkdir()
        _write_image(folder / "seed.jpg")
    paths = [str(folder) for folder in folders]
    settings = _enable(paths, recursive=False)
    service = PhotoWatcherService(
        settings, baseline_path=tmp_path / "baseline.json", batch_window_seconds=0, settle_seconds=0
    )
    sent: list[str] = []
    assert _scan(service, sent.append) == 0
    for folder in folders:
        _write_image(folder / "from-pc.jpg")
        _write_image(folder / "from-pc.png")
        _write_image(folder / "from-pc.heic")
    created = _scan(service, sent.append)
    assert created == 18
    assert len(sent) == 18
    assert _event_count() == 18
    assert _scan(service, sent.append) == 0
    assert _event_count() == 18


def test_smb_tmp_and_part_rename_detected_once(tmp_path: Path) -> None:
    watch = tmp_path / "library-b"
    watch.mkdir()
    settings = _enable([str(watch)], recursive=False)
    service = PhotoWatcherService(
        settings, baseline_path=tmp_path / "baseline.json", batch_window_seconds=0, settle_seconds=0
    )
    sent: list[str] = []
    assert _scan(service, sent.append) == 0
    tmp_file = watch / "DSC_0001.jpg.tmp"
    part_file = watch / "DSC_0002.jpg.part"
    tmp_file.write_bytes(b"uploading")
    part_file.write_bytes(b"uploading")
    assert _scan(service, sent.append) == 0
    tmp_file.rename(watch / "DSC_0001.jpg")
    part_file.rename(watch / "DSC_0002.jpg")
    created = _scan(service, sent.append)
    assert created == 2
    assert len(sent) == 2
    assert _scan(service, sent.append) == 0
    assert _event_count() == 2


def test_multiple_files_none_lost_or_duplicated(tmp_path: Path, caplog) -> None:
    watch = tmp_path / "photos"
    watch.mkdir()
    settings = _enable([str(watch)], recursive=False, max_events=1000)
    service = PhotoWatcherService(
        settings, baseline_path=tmp_path / "baseline.json", batch_window_seconds=0, settle_seconds=0
    )
    sent: list[str] = []
    assert _scan(service, sent.append) == 0
    for count in (10, 50, 100):
        start = time.perf_counter()
        for index in range(count):
            _write_image(watch / f"burst-{count}-{index:03d}.jpg")
        with caplog.at_level("INFO", logger="homelab_monitor.photo_watcher"):
            created = _scan(service, sent.append)
        elapsed = time.perf_counter() - start
        assert created == count
        assert "Elapsed scan time" in caplog.text
        assert "Elapsed database time" in caplog.text
        assert "Elapsed telegram time" in caplog.text
        assert elapsed < 30
    assert len(sent) == 160
    assert _event_count() == 160
    assert _scan(service, sent.append) == 0


def test_large_images_are_detected_without_timeout(tmp_path: Path) -> None:
    watch = tmp_path / "library-e"
    watch.mkdir()
    settings = _enable([str(watch)], recursive=False)
    service = PhotoWatcherService(
        settings, baseline_path=tmp_path / "baseline.json", batch_window_seconds=0, settle_seconds=0
    )
    sent: list[str] = []
    assert _scan(service, sent.append) == 0
    sizes = {
        "10mb.jpg": 10 * 1024 * 1024,
        "20mb.png": 20 * 1024 * 1024,
        "50mb.heic": 50 * 1024 * 1024,
        "100mb.jpg": 100 * 1024 * 1024,
    }
    for name, size in sizes.items():
        _write_sized(watch / name, size)
    started = time.perf_counter()
    created = _scan(service, sent.append)
    assert time.perf_counter() - started < 15
    assert created == 4
    assert len(sent) == 4
    with Session(get_engine()) as db:
        rows = PhotoEventRepository(db).list_latest(10)
        by_name = {row.filename: row for row in rows}
        assert by_name["100mb.jpg"].size_bytes == sizes["100mb.jpg"]
        assert all(row.telegram_sent for row in rows)


def test_docker_or_ubuntu_restart_restores_baseline(tmp_path: Path) -> None:
    watch = tmp_path / "library-c"
    watch.mkdir()
    _write_image(watch / "already-there.jpg")
    baseline = tmp_path / "photo_baseline.json"
    settings = _enable([str(watch)], recursive=False)
    first = PhotoWatcherService(
        settings, baseline_path=baseline, batch_window_seconds=0, settle_seconds=0
    )
    sent: list[str] = []
    assert _scan(first, sent.append) == 0
    _write_image(watch / "while-api-down.jpg")
    restarted = PhotoWatcherService(
        settings, baseline_path=baseline, batch_window_seconds=0, settle_seconds=0
    )
    created = _scan(restarted, sent.append)
    assert created == 1
    assert sent[-1]
    assert _scan(restarted, sent.append) == 0
    assert _event_count() == 1


def test_nas_unavailable_retries_then_resumes(tmp_path: Path) -> None:
    live = tmp_path / "library-a"
    missing = tmp_path / "library-d"
    live.mkdir()
    _write_image(live / "seed.jpg")
    settings = _enable([str(live), str(missing)], recursive=False)
    service = PhotoWatcherService(
        settings, baseline_path=tmp_path / "baseline.json", batch_window_seconds=0, settle_seconds=0
    )
    sent: list[str] = []
    assert _scan(service, sent.append) == 0
    _write_image(live / "during-nas-outage.jpg")
    created = _scan(service, sent.append)
    assert created == 1
    missing.mkdir()
    created = _scan(service, sent.append)
    assert created == 0
    _write_image(missing / "after-nas-back.jpg")
    created = _scan(service, sent.append)
    assert created == 1
    names = set()
    with Session(get_engine()) as db:
        for row in PhotoEventRepository(db).list_latest(10):
            names.add(row.filename)
    assert names == {"during-nas-outage.jpg", "after-nas-back.jpg"}


def test_telegram_outage_stores_event_and_recovers(tmp_path: Path) -> None:
    watch = tmp_path / "photos"
    watch.mkdir()
    settings = _enable([str(watch)], recursive=False)
    service = PhotoWatcherService(
        settings, baseline_path=tmp_path / "baseline.json", batch_window_seconds=0, settle_seconds=0
    )

    def fail(_text: str) -> dict:
        raise TimeoutError("internet down")

    sent: list[str] = []
    assert _scan(service, fail) == 0
    _write_image(watch / "offline.jpg")
    created = _scan(service, fail)
    with Session(get_engine()) as db:
        latest = PhotoEventRepository(db).latest()
        assert created == 1
        assert latest is not None
        assert latest.telegram_sent is False
    _write_image(watch / "online.jpg")
    created = _scan(service, sent.append)
    with Session(get_engine()) as db:
        rows = {row.filename: row for row in PhotoEventRepository(db).list_latest(10)}
        assert created == 1
        assert rows["online.jpg"].telegram_sent is True
        assert rows["offline.jpg"].telegram_sent is True
    assert service.telegram_ok_total == 1
    assert service.telegram_failed_total == 1
    service.log_health()


def test_one_thousand_mixed_uploads_are_complete(tmp_path: Path) -> None:
    watch = tmp_path / "library-b"
    nested = watch / "2026" / "09"
    nested.mkdir(parents=True)
    settings = _enable([str(watch)], recursive=True, max_events=1000)
    service = PhotoWatcherService(
        settings, baseline_path=tmp_path / "baseline.json", batch_window_seconds=0, settle_seconds=0
    )
    sent: list[str] = []
    assert _scan(service, sent.append) == 0
    extensions = [".jpg", ".jpeg", ".png", ".heic", ".gif", ".bmp", ".webp"]
    expected = 0
    for index in range(1000):
        suffix = extensions[index % len(extensions)]
        target = nested if index % 2 == 0 else watch
        _write_image(target / f"mix-{index:04d}{suffix}")
        expected += 1
    created = _scan(service, sent.append)
    assert created == expected
    assert len(sent) == expected
    assert _event_count() == expected
    assert _scan(service, sent.append) == 0
    assert _event_count() == expected


def test_loop_logs_health_and_stopped(monkeypatch, caplog) -> None:
    import homelab_monitor.photo_watcher as module

    scans = {"count": 0}

    def fake_scan(_settings: object, _service: object) -> int:
        scans["count"] += 1
        return 5

    async def fake_sleep(_seconds: float) -> None:
        if scans["count"] >= 1:
            raise asyncio.CancelledError

    monkeypatch.setattr(module, "_scan_and_interval", fake_scan)
    monkeypatch.setattr(module.asyncio, "sleep", fake_sleep)
    with (
        caplog.at_level("INFO", logger="homelab_monitor.photo_watcher"),
        pytest.raises(asyncio.CancelledError),
    ):
        asyncio.run(run_photo_watcher(_settings(["/tmp"])))
    assert "photo_watcher_started" in caplog.text
    assert "Photo Monitor Health" in caplog.text
    assert "photo_watcher_stopped" in caplog.text
