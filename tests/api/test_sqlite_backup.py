from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from homelab_monitor.settings import Settings
from homelab_monitor.sqlite_backup import (
    _notify,
    apply_retention,
    format_backup_telegram,
    next_scheduled,
    run_backup_once,
)
from homelab_monitor.telegram import TelegramNotificationError


def _settings(tmp_path: Path, db_path: Path) -> Settings:
    return Settings.model_construct(
        database_url=f"sqlite:///{db_path}",
        backup_enabled=True,
        backup_path=str(tmp_path / "backups"),
        backup_retention_daily=7,
        backup_retention_weekly=4,
        backup_retention_monthly=6,
        backup_time="02:00",
        backup_timezone="Asia/Bangkok",
        telegram_enabled=False,
    )


def test_next_scheduled_is_bangkok_two_am() -> None:
    settings = Settings.model_construct(
        backup_time="02:00",
        backup_timezone="Asia/Bangkok",
    )
    now = datetime(2026, 9, 21, 1, 0, tzinfo=ZoneInfo("Asia/Bangkok"))
    nxt = next_scheduled(settings, now=now)
    assert nxt.hour == 2
    assert nxt.minute == 0
    assert str(nxt.tzinfo) == "Asia/Bangkok"


def test_run_backup_creates_gzip_and_passes_integrity(tmp_path: Path) -> None:
    db_path = tmp_path / "homelab-monitor.db"
    import sqlite3

    connection = sqlite3.connect(db_path)
    connection.execute("CREATE TABLE sample (id INTEGER)")
    connection.execute("INSERT INTO sample VALUES (1)")
    connection.commit()
    connection.close()
    settings = _settings(tmp_path, db_path)
    result = run_backup_once(settings, notify=False)
    assert result.ok is True
    assert result.integrity == "PASS"
    assert result.path.endswith(".sqlite3.gz")
    assert Path(result.path).is_file()
    assert "Backup Complete" in format_backup_telegram(result, settings)


def test_retention_keeps_daily_weekly_monthly(tmp_path: Path) -> None:
    settings = Settings.model_construct(
        backup_retention_daily=1,
        backup_retention_weekly=1,
        backup_retention_monthly=1,
    )
    folder = tmp_path / "backups"
    folder.mkdir()
    names = [
        "homelab-monitor-2026-09-01-020000.sqlite3.gz",
        "homelab-monitor-2026-09-13-020000.sqlite3.gz",
        "homelab-monitor-2026-09-20-020000.sqlite3.gz",
        "homelab-monitor-2026-09-21-020000.sqlite3.gz",
    ]
    for name in names:
        (folder / name).write_bytes(b"x")
    apply_retention(folder, settings)
    remaining = sorted(path.name for path in folder.glob("*.sqlite3.gz"))
    assert remaining == [
        "homelab-monitor-2026-09-01-020000.sqlite3.gz",
        "homelab-monitor-2026-09-20-020000.sqlite3.gz",
        "homelab-monitor-2026-09-21-020000.sqlite3.gz",
    ]


def test_backup_failed_telegram_mentions_previous_copies() -> None:
    from homelab_monitor.sqlite_backup import BackupResult

    settings = Settings.model_construct(
        backup_path="/var/lib/homelab-monitor/backups",
        backup_retention_daily=7,
        backup_retention_weekly=4,
        backup_retention_monthly=6,
    )
    text = format_backup_telegram(BackupResult(ok=False, error="gzip damaged"), settings)
    assert "Backup Failed" in text
    assert "Previous backups were not deleted" in text


class _Service:
    def __init__(self) -> None:
        self.sent: list[str] = []
        self.closed = False

    def send_text(self, text: str) -> dict:
        self.sent.append(text)
        return {"ok": True}

    def close(self) -> None:
        self.closed = True


def test_backup_notify_uses_notification_service(monkeypatch) -> None:
    from homelab_monitor.sqlite_backup import BackupResult

    service = _Service()
    monkeypatch.setattr(
        "homelab_monitor.sqlite_backup.NotificationService.from_settings",
        lambda _settings: service,
    )
    settings = Settings.model_construct(telegram_enabled=True, backup_path="/tmp/backups")
    result = BackupResult(ok=False, error="gzip damaged")
    _notify(settings, result)
    assert service.sent == [format_backup_telegram(result, settings)]
    assert service.closed is True


def test_backup_notify_swallows_telegram_errors(monkeypatch) -> None:
    from homelab_monitor.sqlite_backup import BackupResult

    class _Broken(_Service):
        def send_text(self, text: str) -> dict:
            raise TelegramNotificationError("timeout")

    monkeypatch.setattr(
        "homelab_monitor.sqlite_backup.NotificationService.from_settings",
        lambda _settings: _Broken(),
    )
    settings = Settings.model_construct(telegram_enabled=True)
    _notify(settings, BackupResult(ok=False, error="offline"))


def test_backup_notify_skips_when_service_unavailable(monkeypatch) -> None:
    from homelab_monitor.sqlite_backup import BackupResult

    monkeypatch.setattr(
        "homelab_monitor.sqlite_backup.NotificationService.from_settings",
        lambda _settings: None,
    )
    settings = Settings.model_construct(telegram_enabled=True)
    _notify(settings, BackupResult(ok=True))
