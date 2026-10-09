from collections.abc import Callable
from datetime import UTC, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from homelab_monitor.analytics import AnalyticsService
from homelab_monitor.database import get_engine
from homelab_monitor.models import Agent, Alert, Notification
from homelab_monitor.notifications.config import load_payload, save_payload
from homelab_monitor.notifications.service import NotificationService
from homelab_monitor.schemas import AnalyticsBackupResponse
from homelab_monitor.security import hash_agent_token
from homelab_monitor.settings import get_settings
from homelab_monitor.telegram_reports import (
    TelegramReportService,
    format_daily_report,
    format_hourly_report,
    format_weekly_report,
    process_due_reports,
    reports_payload,
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
    payload["telegram"] = {
        "enabled": True,
        "bot_token": "test-bot-token",
        "chat_id": "-1001",
    }
    save_payload(db, payload)


def test_reports_jwt_rbac_and_empty_settings(
    client: TestClient,
    auth_header: Callable[..., dict[str, str]],
) -> None:
    _reset()
    assert client.get("/api/v1/settings/notifications").status_code == 401
    body = client.get(
        "/api/v1/settings/notifications", headers=auth_header("viewer", "viewer123")
    ).json()
    assert body["reports"]["hourly_enabled"] is False
    assert body["reports"]["timezone"] == "Asia/Bangkok"
    denied = client.put(
        "/api/v1/settings/notifications",
        headers=auth_header("operator", "operator123"),
        json={"reports": {"hourly_enabled": True}},
    )
    assert denied.status_code == 403
    updated = client.put(
        "/api/v1/settings/notifications",
        headers=auth_header(),
        json={"reports": {"hourly_enabled": True, "timezone": "Asia/Bangkok"}},
    )
    assert updated.status_code == 200
    assert updated.json()["reports"]["hourly_enabled"] is True


def test_hourly_daily_weekly_generation_and_history(monkeypatch) -> None:
    _reset()
    sent: list[str] = []

    def fake_send(self: NotificationService, message: str) -> None:
        sent.append(message)

    monkeypatch.setattr(NotificationService, "send_text", fake_send)
    settings = get_settings()
    hourly_at = datetime(2026, 9, 8, 9, 0, tzinfo=UTC)
    with Session(get_engine()) as db:
        _configure(db, hourly_enabled=True)
        rows = process_due_reports(db, settings, now=hourly_at)
        assert len(rows) == 1
        assert rows[0].recipient == "hourly_report"
        assert rows[0].status == "sent"
        assert "Hourly Executive Report" in sent[-1]
        assert "Photos Today" in sent[-1]
        assert "Immich Indexed" in sent[-1]
        assert "💡 Recommendation" in sent[-1]
        assert "http://dashboard" not in sent[-1]
        assert "http://127.0.0.1" not in sent[-1]
        assert "• Status:" not in sent[-1]
        again = process_due_reports(db, settings, now=hourly_at)
        assert again == []
    daily_at = datetime(2026, 9, 8, 1, 5, tzinfo=UTC)
    with Session(get_engine()) as db:
        _configure(db, hourly_enabled=False, daily_enabled=True, timezone="Asia/Bangkok")
        rows = process_due_reports(db, settings, now=daily_at)
        assert len(rows) == 1
        assert rows[0].recipient == "daily_report"
        assert "Daily Executive Report" in sent[-1]
        assert "8 September 2026" in sent[-1]
    weekly_at = datetime(2026, 9, 6, 1, 5, tzinfo=UTC)
    with Session(get_engine()) as db:
        _configure(
            db,
            hourly_enabled=False,
            daily_enabled=False,
            weekly_enabled=True,
            timezone="Asia/Bangkok",
        )
        rows = process_due_reports(db, settings, now=weekly_at)
        assert len(rows) == 1
        assert rows[0].recipient == "weekly_report"
        assert "Weekly Executive Report" in sent[-1]
    with Session(get_engine()) as db:
        kinds = [
            row.recipient
            for row in db.scalars(select(Notification).order_by(Notification.created_at.asc()))
        ]
    assert kinds == ["hourly_report", "daily_report", "weekly_report"]


def test_disabled_reports_do_not_send(monkeypatch) -> None:
    _reset()
    sent: list[str] = []
    monkeypatch.setattr(
        NotificationService, "send_text", lambda self, message: sent.append(message)
    )
    with Session(get_engine()) as db:
        _configure(db, hourly_enabled=False, daily_enabled=False, weekly_enabled=False)
        rows = process_due_reports(db, get_settings(), now=datetime(2026, 9, 6, 1, 5, tzinfo=UTC))
    assert rows == []
    assert sent == []


def test_skipped_failed_retry_and_timezone(
    monkeypatch,
    client: TestClient,
    auth_header: Callable[..., dict[str, str]],
) -> None:
    _reset()
    settings = get_settings()
    now = datetime(2026, 9, 8, 9, 0, tzinfo=UTC)
    with Session(get_engine()) as db:
        payload = load_payload(db)
        reports = reports_payload(payload)
        reports["hourly_enabled"] = True
        payload["reports"] = reports
        save_payload(db, payload)
        rows = process_due_reports(db, settings, now=now)
        assert rows[0].status == "skipped"
    sent: list[str] = []

    def fail_send(self: NotificationService, message: str) -> None:
        raise RuntimeError("telegram down")

    monkeypatch.setattr(NotificationService, "send_text", fail_send)
    fail_at = datetime(2026, 9, 8, 10, 0, tzinfo=UTC)
    with Session(get_engine()) as db:
        _configure(db, hourly_enabled=True)
        rows = process_due_reports(db, settings, now=fail_at)
        assert rows[0].status == "failed"
        failed_id = rows[0].id
    monkeypatch.setattr(
        NotificationService, "send_text", lambda self, message: sent.append(message)
    )
    retried = client.post(
        f"/api/v1/notifications/{failed_id}/retry",
        headers=auth_header("operator", "operator123"),
    )
    assert retried.status_code == 200
    assert retried.json()["status"] == "sent"
    assert retried.json()["recipient"] == "hourly_report"
    assert "Hourly Executive Report" in sent[-1]
    assert "Photos Today" in sent[-1]
    bangkok = datetime(2026, 9, 8, 1, 5, tzinfo=UTC)
    with Session(get_engine()) as db:
        _configure(
            db,
            hourly_enabled=False,
            daily_enabled=True,
            timezone="UTC",
            daily_time="08:00",
        )
        utc_rows = process_due_reports(db, settings, now=bangkok)
        assert utc_rows == []
        _configure(
            db,
            hourly_enabled=False,
            daily_enabled=True,
            timezone="Asia/Bangkok",
            daily_time="08:00",
        )
        bangkok_rows = process_due_reports(db, settings, now=bangkok)
        assert len(bangkok_rows) == 1
        assert bangkok_rows[0].recipient == "daily_report"


def test_manual_test_report_jwt_rbac_disabled_success_retry_and_history(
    client: TestClient,
    auth_header: Callable[..., dict[str, str]],
    monkeypatch,
) -> None:
    _reset()
    assert client.post("/api/v1/notifications/test-report").status_code == 401
    viewer = client.post(
        "/api/v1/notifications/test-report",
        headers=auth_header("viewer", "viewer123"),
    )
    operator = client.post(
        "/api/v1/notifications/test-report",
        headers=auth_header("operator", "operator123"),
    )
    assert viewer.status_code == 403
    assert operator.status_code == 403
    missing = client.post("/api/v1/notifications/test-report", headers=auth_header())
    assert missing.status_code == 409
    assert missing.json() == {"status": "telegram_not_configured"}
    sent: list[str] = []
    monkeypatch.setattr(
        NotificationService, "send_text", lambda self, message: sent.append(message)
    )
    with Session(get_engine()) as db:
        _configure(db)
        now = datetime(2026, 9, 8, 9, 42, 18, tzinfo=UTC)
        body = TelegramReportService().build_test_report(db, now=now)
    assert "🧪 Test Report" in body
    assert "8 September 2026" in body
    assert "16:42" in body
    assert "http://dashboard" not in body
    assert "http://127.0.0.1" not in body
    posted = client.post("/api/v1/notifications/test-report", headers=auth_header())
    assert posted.status_code == 200
    payload = posted.json()
    assert payload["status"] == "sent"
    assert payload["provider"] == "telegram"
    assert payload["notification_id"]
    assert "🧪 Test Report" in sent[-1]
    history = client.get(
        "/api/v1/notifications/history",
        headers=auth_header("viewer", "viewer123"),
    )
    titles = [item["title"] for item in history.json()["items"]]
    assert "Test Report" in titles

    def fail_send(self: NotificationService, message: str) -> None:
        raise RuntimeError("telegram down")

    monkeypatch.setattr(NotificationService, "send_text", fail_send)
    failed = client.post("/api/v1/notifications/test-report", headers=auth_header())
    assert failed.status_code == 200
    assert failed.json()["status"] == "failed"
    failed_id = failed.json()["notification_id"]
    sent.clear()
    monkeypatch.setattr(
        NotificationService, "send_text", lambda self, message: sent.append(message)
    )
    retried = client.post(
        f"/api/v1/notifications/{failed_id}/retry",
        headers=auth_header("operator", "operator123"),
    )
    assert retried.status_code == 200
    assert retried.json()["status"] == "sent"
    assert retried.json()["recipient"] == "test_report"
    assert "🧪 Test Report" in sent[-1]


def test_hourly_report_groups_warning_and_critical_and_skips_info(monkeypatch) -> None:
    _reset()
    sent: list[str] = []
    monkeypatch.setattr(
        NotificationService, "send_text", lambda self, message: sent.append(message)
    )
    hourly_at = datetime(2026, 9, 10, 1, 0, tzinfo=UTC)
    with Session(get_engine()) as db:
        agent = Agent(
            name="hourly-alerts",
            hostname="hourly-alerts.local",
            version="0.1.0",
            token_hash=hash_agent_token("hourly-alerts-token"),
            status="online",
            capabilities=["ubuntu"],
        )
        db.add(agent)
        db.flush()
        db.add_all(
            [
                Alert(
                    agent_id=agent.id,
                    kind="cpu_high",
                    resource="cpu",
                    status="active",
                    severity="info",
                    current_value=40,
                    threshold=70,
                    message="cpu info",
                    opened_at=hourly_at,
                    last_observed_at=hourly_at,
                ),
                Alert(
                    agent_id=agent.id,
                    kind="disk_high",
                    resource="/",
                    status="active",
                    severity="warning",
                    current_value=82,
                    threshold=80,
                    message="disk warning",
                    opened_at=hourly_at,
                    last_observed_at=hourly_at,
                ),
                Alert(
                    agent_id=agent.id,
                    kind="temperature_high",
                    resource="cpu",
                    status="active",
                    severity="critical",
                    current_value=81,
                    threshold=75,
                    message="temp critical",
                    opened_at=hourly_at,
                    last_observed_at=hourly_at,
                ),
            ]
        )
        _configure(db, hourly_enabled=True)
        rows = process_due_reports(db, get_settings(), now=hourly_at)
        assert rows[0].status == "sent"
    body = sent[-1]
    assert "⚠ Alerts 3" in body
    assert "Check cooling" in body or "Check storage capacity" in body
    assert "CPU High" not in body


def _sample_hourly(**overrides: object) -> str:
    local = datetime(2026, 9, 10, 14, 0, tzinfo=timezone(timedelta(hours=7)))
    payload = {
        "local": local,
        "cpu": 57.0,
        "memory": 32.0,
        "temperature": 51.0,
        "storage_percent": 1.0,
        "photos_new_today": "9",
        "immich_indexed": "18,421",
        "backup_status": "Success",
        "last_backup": "",
        "active_alerts": 0,
        "recovered_today": 2,
        "health_score": 84.0,
        "recommendation": "Everything looks healthy.",
        "dashboard_url": "http://127.0.0.1:18081",
    }
    payload.update(overrides)
    return format_hourly_report(**payload)  # type: ignore[arg-type]


def test_hourly_format_healthy_layout() -> None:
    body = _sample_hourly()
    assert "🏠 HomeLab Monitor" in body
    assert "Hourly Executive Report" in body
    assert "10 September 2026" in body
    assert "14:00" in body
    assert "🖥 CPU" in body
    assert "📷 Photos Today" in body
    assert "Immich Indexed" in body
    assert "18,421" in body
    assert "✅ Success" in body
    assert "🟢" in body
    assert "█" in body
    assert "░" in body
    assert "Everything looks healthy." in body
    assert "Continue monitoring." in body
    assert "Dashboard" in body
    assert "http://127.0.0.1:18081" in body
    assert "Sprint" in body
    assert "10.2.8.3" in body
    assert "Version" in body
    assert "**" not in body


def test_hourly_format_one_alert() -> None:
    body = _sample_hourly(
        active_alerts=1,
        recommendation="Check CPU load",
    )
    assert "⚠ Alerts" in body
    assert "Check CPU load" in body
    assert "Everything looks healthy." not in body


def test_hourly_format_multiple_alerts() -> None:
    body = _sample_hourly(
        backup_status="Failed",
        active_alerts=2,
        recommendation="Verify NAS Backup",
    )
    assert "❌ Failed" in body
    assert "Verify NAS Backup" in body


def test_hourly_format_unknown_and_missing_values() -> None:
    body = _sample_hourly(
        health_score=None,
        cpu=None,
        memory=None,
        storage_percent=None,
        temperature=None,
        backup_status="Unknown",
        last_backup="",
        photos_new_today="—",
        immich_indexed="0",
    )
    assert "Unknown" in body
    assert "—°C" not in body
    assert "Everything looks healthy." in body
    assert "New Today\n—" not in body
    assert "Photos Today" in body
    assert "—" in body
    assert "⚪" in body


def _line_after(body: str, label: str) -> str:
    lines = body.splitlines()
    return lines[lines.index(label) + 1]


def test_hourly_compact_metrics_put_percent_on_the_label_line() -> None:
    body = _sample_hourly(health_score=54.0, cpu=57.0, memory=32.0, storage_percent=1.0)
    assert _line_after(body, "🟡 Health 54%") == "█████░░░░░"
    assert _line_after(body, "🖥 CPU 57%") == "██████░░░░"
    assert _line_after(body, "🧠 Memory 32%") == "███░░░░░░░"
    assert _line_after(body, "💾 Storage 1%") == "░░░░░░░░░░"
    assert "📷 Photos Today 9" in body


def test_daily_and_weekly_compact_bars_keep_analytics_backup_wording() -> None:
    local = datetime(2026, 9, 10, 8, 0, tzinfo=timezone(timedelta(hours=7)))
    daily = format_daily_report(
        local=local,
        cpu_average=40.0,
        memory_average=20.0,
        temperature_average=36.0,
        storage_growth="+1%",
        photo_growth="+3",
        backup_success="12%",
        alerts_yesterday=0,
        health_score=54.0,
        recommendation="Everything looks healthy.",
        dashboard_url="http://127.0.0.1:18081",
    )
    weekly = format_weekly_report(
        local=local,
        cpu_average=40.0,
        memory_average=20.0,
        storage_growth="+1%",
        photo_growth="+3",
        backup_success="12%",
        forecast="Stable",
        recommendation="Everything looks healthy.",
        dashboard_url="http://127.0.0.1:18081",
    )
    assert _line_after(daily, "🟡 Health 54%") == "█████░░░░░"
    assert _line_after(daily, "🖥 CPU 40%") == "████░░░░░░"
    assert _line_after(daily, "🧠 Memory 20%") == "██░░░░░░░░"
    assert _line_after(weekly, "🖥 CPU 40%") == "████░░░░░░"
    assert _line_after(weekly, "🧠 Memory 20%") == "██░░░░░░░░"
    assert "💾 Backup 12%" in daily
    assert "💾 Backup 12%" in weekly
    assert "✅ Success" not in daily
    assert "✅ Success" not in weekly


@pytest.mark.parametrize(
    ("raw_status", "label"),
    [
        ("healthy", "✅ Success"),
        ("success", "✅ Success"),
        ("failed", "❌ Failed"),
        ("disabled", "Disabled"),
        ("idle", "Idle"),
        ("mystery", "Unknown"),
    ],
)
def test_hourly_backup_status_uses_sqlite_payload_not_snapshot(
    monkeypatch: pytest.MonkeyPatch,
    raw_status: str,
    label: str,
) -> None:
    monkeypatch.setattr(
        AnalyticsService,
        "backup",
        lambda self, db, now=None: AnalyticsBackupResponse(
            last_backup="2020-01-01T00:00:00+00:00",
            success_rate=0,
        ),
    )
    monkeypatch.setattr(
        "homelab_monitor.telegram_reports.sqlite_status_payload",
        lambda settings: {"status": raw_status, "latest_at": "2026-09-29T02:00:00+07:00"},
    )
    with Session(get_engine()) as db:
        body = TelegramReportService().build(db, "hourly_report")
    assert f"💾 Backup {label}" in body
    assert "🕒 Last Backup 02:00" in body
    assert "07:00" not in body


def test_test_report_last_backup_uses_sqlite_latest_at(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        AnalyticsService,
        "backup",
        lambda self, db, now=None: AnalyticsBackupResponse(
            last_backup="2020-01-01T00:00:00+00:00",
            success_rate=0,
        ),
    )
    monkeypatch.setattr(
        "homelab_monitor.telegram_reports.sqlite_status_payload",
        lambda settings: {"status": "healthy", "latest_at": "2026-09-29T02:00:00+07:00"},
    )
    with Session(get_engine()) as db:
        body = TelegramReportService().build(db, "test_report")
    assert "🧪 Test Report" in body
    assert "✅ Success" in body
    assert "🕒 Last Backup 02:00" in body
    assert "07:00" not in body


def test_daily_report_keeps_analytics_success_rate_when_sqlite_disagrees(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        AnalyticsService,
        "backup",
        lambda self, db, now=None: AnalyticsBackupResponse(
            last_backup="2020-01-01T00:00:00+00:00",
            success_rate=12,
        ),
    )
    monkeypatch.setattr(
        "homelab_monitor.telegram_reports.sqlite_status_payload",
        lambda settings: {"status": "failed", "latest_at": "2026-09-29T02:00:00+07:00"},
    )
    with Session(get_engine()) as db:
        body = TelegramReportService().build(db, "daily_report")
    assert "💾 Backup 12%" in body
    assert "❌ Failed" not in body


def test_telegram_inline_keyboard_uses_configured_urls(monkeypatch) -> None:
    from homelab_monitor.schemas import RemoteAccessResponse
    from homelab_monitor.telegram import telegram_reply_markup

    monkeypatch.setattr(
        "homelab_monitor.telegram_links.RemoteAccessService.snapshot",
        lambda self: RemoteAccessResponse(),
    )
    empty = telegram_reply_markup(
        get_settings().model_copy(
            update={
                "dashboard_health_url": "",
                "dashboard_public_url": "",
                "immich_public_url": "",
                "qnap_public_url": "",
                "immich_url": "",
                "qnap_url": "",
            }
        )
    )
    assert empty is None
    markup = telegram_reply_markup(
        get_settings().model_copy(
            update={
                "dashboard_health_url": "http://dashboard:8080/",
                "dashboard_public_url": "",
                "immich_public_url": "https://immich.example/",
                "immich_url": "http://immich:2283",
                "qnap_url": "",
            }
        )
    )
    assert markup is not None
    labels = [row[0]["text"] for row in markup["inline_keyboard"]]
    assert labels == ["📷 Immich"]
