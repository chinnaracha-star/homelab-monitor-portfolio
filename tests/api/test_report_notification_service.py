from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from homelab_monitor.database import get_engine
from homelab_monitor.models import Alert, Notification
from homelab_monitor.notifications import RETRY_ATTEMPTS
from homelab_monitor.notifications.config import load_payload, save_payload
from homelab_monitor.notifications.service import NotificationService
from homelab_monitor.settings import get_settings
from homelab_monitor.telegram_reports import (
    TelegramReportService,
    process_due_reports,
    reports_payload,
    send_manual_test_report,
)


def _reset() -> None:
    with Session(get_engine()) as db:
        db.execute(delete(Notification))
        db.execute(delete(Alert))
        payload = load_payload(db)
        payload["reports"] = reports_payload({})
        payload.pop("telegram", None)
        save_payload(db, payload)


def _configure(db: Session, **report_updates: object) -> None:
    payload = load_payload(db)
    reports = reports_payload(payload)
    reports.update(report_updates)
    payload["reports"] = reports
    payload["telegram"] = {"enabled": True, "bot_token": "test-bot-token", "chat_id": "-1001"}
    save_payload(db, payload)


def test_scheduled_reports_send_builder_text_once(monkeypatch) -> None:
    _reset()
    sent: list[str] = []
    monkeypatch.setattr(NotificationService, "send_text", lambda self, text: sent.append(text))
    settings_now = {
        "hourly_report": datetime(2026, 9, 8, 9, 0, tzinfo=UTC),
        "daily_report": datetime(2026, 9, 8, 1, 5, tzinfo=UTC),
        "weekly_report": datetime(2026, 9, 6, 1, 5, tzinfo=UTC),
    }
    flags = {
        "hourly_report": {"hourly_enabled": True},
        "daily_report": {
            "hourly_enabled": False,
            "daily_enabled": True,
            "timezone": "Asia/Bangkok",
        },
        "weekly_report": {
            "hourly_enabled": False,
            "daily_enabled": False,
            "weekly_enabled": True,
            "timezone": "Asia/Bangkok",
        },
    }
    for kind, clock in settings_now.items():
        with Session(get_engine()) as db:
            _configure(db, **flags[kind])
            expected = TelegramReportService().build(db, kind, now=clock)
            rows = process_due_reports(db, get_settings(), now=clock)
            assert rows[0].recipient == kind
            assert rows[0].channel == "telegram"
            assert rows[0].status == "sent"
            assert sent[-1] == expected
    with Session(get_engine()) as db:
        _configure(db)
        clock = datetime(2026, 9, 8, 9, 42, 18, tzinfo=UTC)
        expected = TelegramReportService().build_test_report(db, now=clock)
        row = send_manual_test_report(db, get_settings(), now=clock)
        assert row.recipient == "test_report"
        assert row.channel == "telegram"
        assert row.status == "sent"
        assert sent[-1] == expected
    with Session(get_engine()) as db:
        count = db.scalar(select(func.count()).select_from(Notification))
    assert count == 4


def test_failed_report_retries_without_a_second_history_row(monkeypatch) -> None:
    _reset()
    calls = {"n": 0}

    def fail(self: NotificationService, text: str) -> dict:
        calls["n"] += 1
        raise RuntimeError("timeout")

    monkeypatch.setattr(NotificationService, "send_text", fail)
    with Session(get_engine()) as db:
        _configure(db, hourly_enabled=True)
        rows = process_due_reports(db, get_settings(), now=datetime(2026, 9, 8, 9, 0, tzinfo=UTC))
        assert rows[0].status == "failed"
        assert rows[0].recipient == "hourly_report"
        count = db.scalar(select(func.count()).select_from(Notification))
    assert calls["n"] == RETRY_ATTEMPTS
    assert count == 1


def test_report_neighbors_do_not_use_notification_service() -> None:
    root = Path("api/src/homelab_monitor")
    photo = (root / "photo_watcher.py").read_text(encoding="utf-8")
    assert "NotificationService" in photo
    assert "send_photo" in photo
    caption = (root / "photo_telegram.py").read_text(encoding="utf-8")
    assert "NotificationService" not in caption
    backup = (root / "sqlite_backup.py").read_text(encoding="utf-8")
    assert "NotificationService" in backup
