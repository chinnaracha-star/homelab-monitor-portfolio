import asyncio
import inspect
from datetime import UTC, datetime
from typing import ClassVar

from homelab_monitor.alert_engine import AlertEvent
from homelab_monitor.notification_queue import NotificationQueue, new_notification_job
from homelab_monitor.notification_worker import (
    MAX_ATTEMPTS,
    RETRY_DELAY_SECONDS,
    NotificationWorker,
    TelegramSender,
    run_notification_worker,
)
from homelab_monitor.operations import factories
from homelab_monitor.settings import Settings
from homelab_monitor.telegram import TelegramNotificationError, format_alert_message


def _settings(**updates: object) -> Settings:
    values: dict[str, object] = {
        "notification_worker_enabled": True,
        "telegram_enabled": True,
    }
    values.update(updates)
    return Settings.model_construct(**values)


def _event() -> AlertEvent:
    now = datetime(2026, 9, 8, 9, 0, tzinfo=UTC)
    return AlertEvent(
        agent_id="agent-1",
        agent_name="monitor",
        kind="cpu_high",
        resource="cpu",
        transition="activated",
        value=95.0,
        threshold=90.0,
        message="cpu",
        observed_at=now,
        started_at=now,
        duration_seconds=None,
    )


class _Service:
    recipient = "-100123"
    calls: ClassVar[list[str]] = []
    closed: ClassVar[int] = 0

    def __init__(self) -> None:
        self.sent: list[str] = []

    @classmethod
    def from_settings(cls, _settings: Settings) -> "_Service":
        return cls()

    def send_text(self, text: str) -> dict:
        self.sent.append(text)
        _Service.calls.append(text)
        return {"ok": True}

    def close(self) -> None:
        _Service.closed += 1


def _patch(monkeypatch, service: type[_Service] = _Service) -> None:
    monkeypatch.setattr(
        "homelab_monitor.notification_worker.NotificationService",
        service,
    )


def test_worker_sends_formatter_text_once(monkeypatch) -> None:
    _Service.calls = []
    _Service.closed = 0
    _patch(monkeypatch)
    message = format_alert_message(_event())
    TelegramSender(_settings()).send(
        new_notification_job(channel="telegram", event="activated", message=message)
    )
    assert _Service.calls == [message]
    assert "🔴" in message
    assert "monitor" in message or "Current:" in message
    assert _Service.closed == 1


def test_success_does_not_retry(monkeypatch) -> None:
    _Service.calls = []
    _patch(monkeypatch)
    queue = NotificationQueue()
    queue.enqueue(new_notification_job(channel="telegram", event="activated", message="once"))
    worker = NotificationWorker(
        queue,
        TelegramSender(_settings()),
        retry_delay_seconds=0,
        batch_window_seconds=0,
        sleep=lambda _seconds: None,
    )
    assert worker.process_one() is True
    assert _Service.calls == ["once"]
    assert worker.process_one() is False


def test_failure_retries_three_times_and_keeps_the_next_job(monkeypatch) -> None:
    class _Down(_Service):
        def send_text(self, text: str) -> dict:
            _Service.calls.append(text)
            if text == "first":
                raise TelegramNotificationError("timeout")
            return {"ok": True}

    _Service.calls = []
    _patch(monkeypatch, _Down)
    queue = NotificationQueue()
    queue.enqueue(new_notification_job(channel="telegram", event="activated", message="first"))
    worker = NotificationWorker(
        queue,
        TelegramSender(_settings()),
        retry_delay_seconds=0,
        batch_window_seconds=0,
        sleep=lambda _seconds: None,
    )
    for _ in range(MAX_ATTEMPTS):
        worker.process_one()
    assert _Service.calls.count("first") == MAX_ATTEMPTS
    assert len(queue) == 0
    queue.enqueue(new_notification_job(channel="telegram", event="activated", message="second"))
    assert worker.process_one() is True
    assert _Service.calls[-1] == "second"


def test_unconfigured_telegram_skips_without_raising(monkeypatch) -> None:
    class _Missing(_Service):
        @classmethod
        def from_settings(cls, _settings: Settings) -> None:
            return None

    _patch(monkeypatch, _Missing)
    TelegramSender(_settings(telegram_enabled=False)).send(
        new_notification_job(channel="telegram", event="activated", message="skip")
    )


def test_worker_flag_poll_and_startup_are_unchanged() -> None:
    source = inspect.getsource(run_notification_worker)
    assert "notification_worker_enabled" in source
    assert "asyncio.sleep(0.25)" in source
    assert RETRY_DELAY_SECONDS == 5.0
    assert MAX_ATTEMPTS == 3
    factory = factories(_settings())["notification_worker"]
    assert "run_notification_worker" in factory.__code__.co_names


def test_disabled_worker_returns(monkeypatch) -> None:
    called = {"n": 0}

    class _Boom(_Service):
        @classmethod
        def from_settings(cls, _settings: Settings) -> "_Service":
            called["n"] += 1
            return cls()

    _patch(monkeypatch, _Boom)

    async def run() -> None:
        await run_notification_worker(_settings(notification_worker_enabled=False))

    asyncio.run(run())
    assert called["n"] == 0


def test_worker_cancellation_is_not_caught_as_delivery_failure() -> None:
    source = inspect.getsource(run_notification_worker)
    assert "except Exception" in source
    assert "CancelledError" not in source
