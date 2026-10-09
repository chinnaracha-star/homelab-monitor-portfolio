import asyncio
from datetime import UTC, datetime, timedelta, timezone

import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from homelab_monitor.database import get_engine
from homelab_monitor.jobs.engine import default_engine
from homelab_monitor.notifications.config import load_payload, save_payload
from homelab_monitor.notifications.service import NotificationService
from homelab_monitor.operations import factories
from homelab_monitor.settings import get_settings
from homelab_monitor.telegram_reports import (
    TICK_SECONDS,
    TelegramReportService,
    due_daily,
    due_hourly,
    due_weekly,
    process_due_reports,
    reports_payload,
    run_report_clock,
    run_telegram_reports,
)

BANGKOK = timezone(timedelta(hours=7))


def _reset() -> None:
    from sqlalchemy import delete

    from homelab_monitor.models import Alert, Notification

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


def _local(hour: int, minute: int, second: int, *, day: int = 10) -> datetime:
    return datetime(2026, 9, day, hour, minute, second, tzinfo=BANGKOK)


def test_clock_sleeps_tick_seconds_before_one_process() -> None:
    events: list[object] = []

    async def sleeper(seconds: float) -> None:
        events.append(("sleep", seconds))

    def tick(_settings: object) -> None:
        events.append("process")

    asyncio.run(run_report_clock(get_settings(), sleep=sleeper, tick=tick))
    assert events == [("sleep", TICK_SECONDS), "process"]
    assert TICK_SECONDS == 60


def test_cancel_during_sleep_skips_processing() -> None:
    processed: list[str] = []

    async def sleeper(_seconds: float) -> None:
        raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(
            run_report_clock(
                get_settings(),
                sleep=sleeper,
                tick=lambda _settings: processed.append("process"),
            )
        )
    assert processed == []


def test_lifecycle_repeats_clock_and_continues_after_database_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    async def fake_clock(_settings: object) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise SQLAlchemyError("locked")
        raise RuntimeError("stop")

    monkeypatch.setattr("homelab_monitor.telegram_reports.run_report_clock", fake_clock)
    with pytest.raises(RuntimeError, match="stop"):
        asyncio.run(run_telegram_reports(get_settings()))
    assert calls == 2


def test_unexpected_error_ends_the_lifecycle(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    async def fake_clock(_settings: object) -> None:
        nonlocal calls
        calls += 1
        raise RuntimeError("render failed")

    monkeypatch.setattr("homelab_monitor.telegram_reports.run_report_clock", fake_clock)
    with pytest.raises(RuntimeError, match="render failed"):
        asyncio.run(run_telegram_reports(get_settings()))
    assert calls == 1


def test_hourly_slot_boundaries() -> None:
    before = _local(10, 59, 59)
    exact = _local(11, 0, 0)
    after = _local(11, 0, 1)
    sent_this_hour = datetime(2026, 9, 10, 4, 0, tzinfo=UTC)
    assert due_hourly(before, sent_this_hour, 1) is False
    assert due_hourly(exact, datetime(2026, 9, 10, 3, 0, tzinfo=UTC), 1) is True
    assert due_hourly(after, datetime(2026, 9, 10, 3, 0, tzinfo=UTC), 1) is True
    assert due_hourly(after, sent_this_hour, 1) is False


def test_unsent_current_hour_sends_once(monkeypatch: pytest.MonkeyPatch) -> None:
    _reset()
    sent: list[str] = []
    monkeypatch.setattr(
        NotificationService, "send_text", lambda self, message: sent.append(message)
    )
    late = _local(11, 30, 0).astimezone(UTC)
    with Session(get_engine()) as db:
        _configure(db, hourly_enabled=True, timezone="Asia/Bangkok", hour_interval=1)
        first = [row.recipient for row in process_due_reports(db, get_settings(), now=late)]
        second = process_due_reports(db, get_settings(), now=late)
    assert first == ["hourly_report"]
    assert second == []
    assert len(sent) == 1


def test_daily_boundaries_and_same_day_late_send(monkeypatch: pytest.MonkeyPatch) -> None:
    before = _local(7, 59, 59)
    exact = _local(8, 0, 0)
    after = _local(8, 0, 1)
    assert due_daily(before, None, 8, 0) is False
    assert due_daily(exact, None, 8, 0) is True
    assert due_daily(after, None, 8, 0) is True
    _reset()
    monkeypatch.setattr(NotificationService, "send_text", lambda self, message: None)
    with Session(get_engine()) as db:
        _configure(db, daily_enabled=True, timezone="Asia/Bangkok", daily_time="08:00")
        kinds = [
            row.recipient
            for row in process_due_reports(db, get_settings(), now=_local(18, 0, 0).astimezone(UTC))
        ]
    assert kinds == ["daily_report"]


def test_weekly_sunday_does_not_replay_on_monday(monkeypatch: pytest.MonkeyPatch) -> None:
    sunday_before = datetime(2026, 9, 6, 7, 59, 59, tzinfo=BANGKOK)
    sunday_due = datetime(2026, 9, 6, 8, 0, 0, tzinfo=BANGKOK)
    monday = datetime(2026, 9, 7, 8, 5, 0, tzinfo=BANGKOK)
    assert sunday_due.weekday() == 6
    assert due_weekly(sunday_before, None, 6, 8, 0) is False
    assert due_weekly(sunday_due, None, 6, 8, 0) is True
    assert due_weekly(monday, None, 6, 8, 0) is False
    _reset()
    monkeypatch.setattr(NotificationService, "send_text", lambda self, message: None)
    with Session(get_engine()) as db:
        _configure(
            db,
            weekly_enabled=True,
            timezone="Asia/Bangkok",
            weekly_day="sunday",
            weekly_time="08:00",
        )
        rows = process_due_reports(db, get_settings(), now=monday.astimezone(UTC))
    assert rows == []


def test_overlapping_reports_stay_sequential(monkeypatch: pytest.MonkeyPatch) -> None:
    _reset()
    monkeypatch.setattr(NotificationService, "send_text", lambda self, message: None)
    sunday = datetime(2026, 9, 6, 8, 0, 0, tzinfo=BANGKOK)
    with Session(get_engine()) as db:
        _configure(
            db,
            hourly_enabled=True,
            daily_enabled=True,
            weekly_enabled=True,
            timezone="Asia/Bangkok",
            daily_time="08:00",
            weekly_day="sunday",
            weekly_time="08:00",
        )
        kinds = [
            row.recipient
            for row in process_due_reports(db, get_settings(), now=sunday.astimezone(UTC))
        ]
    assert kinds == ["hourly_report", "daily_report", "weekly_report"]


def test_registry_has_one_telegram_reports_job_and_no_report_clock() -> None:
    names = [job.name for job in default_engine().jobs()]
    factory_names = list(factories(get_settings()))
    assert names.count("telegram_reports") == 1
    assert factory_names.count("telegram_reports") == 1
    assert "report_clock" not in names
    assert "report_clock" not in factory_names
    assert len(names) == 6
    assert len(factory_names) == 6
    source = run_report_clock.__code__.co_names
    assert "create_task" not in source
    assert TelegramReportService is not None
