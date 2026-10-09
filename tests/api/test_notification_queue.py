import inspect
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from homelab_monitor import alert_engine as alert_engine_module
from homelab_monitor.alert_engine import AlertEngine, AlertEvent
from homelab_monitor.database import get_engine
from homelab_monitor.models import Agent
from homelab_monitor.notification_queue import (
    NotificationQueue,
    enqueue_alert_events,
    get_notification_queue,
    new_notification_job,
)
from homelab_monitor.notification_worker import MAX_ATTEMPTS, NotificationWorker, TelegramSender
from homelab_monitor.routers import agents as agents_router
from homelab_monitor.security import hash_agent_token
from homelab_monitor.settings import Settings

REGISTRATION_KEY = "test-registration-key-at-least-24-chars"


def _settings() -> Settings:
    return Settings(
        registration_key=REGISTRATION_KEY,
        alert_cpu_threshold_percent=90,
        alert_memory_threshold_percent=90,
        alert_disk_threshold_percent=90,
        alert_temperature_threshold_celsius=80,
        agent_offline_after_seconds=60,
    )


def _payload() -> dict[str, object]:
    return {
        "modules": [
            {
                "module": "system",
                "status": "warning",
                "summary": "System thresholds evaluated",
                "metrics": {
                    "cpu": {"usage_percent": 95},
                    "memory": {"usage_percent": 20},
                    "disks": [{"mount_point": "/", "usage_percent": 30}],
                    "temperatures": [
                        {
                            "source": "coretemp",
                            "label": "Package",
                            "current_celsius": 40,
                        }
                    ],
                },
                "diagnostics": {},
            }
        ]
    }


def _agent(db: Session, name: str) -> Agent:
    agent = Agent(
        name=name,
        hostname=f"{name}.local",
        version="0.1.0",
        token_hash=hash_agent_token(f"{name}-token"),
        status="online",
        capabilities=["ubuntu"],
        last_seen_at=datetime.now(UTC),
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


def _job(message: str = "alert"):
    return new_notification_job(channel="telegram", event="activated", message=message)


def test_enqueue_alert_events_creates_telegram_jobs() -> None:
    queue = NotificationQueue()
    event = AlertEvent(
        agent_id="agent-id",
        agent_name="monitor",
        kind="cpu_high",
        resource="system",
        value=95,
        threshold=90,
        message="CPU high",
        observed_at=datetime(2026, 9, 10, 8, 0, tzinfo=UTC),
        transition="activated",
    )
    jobs = enqueue_alert_events([event], queue)
    assert len(jobs) == 1
    assert len(queue) == 1
    job = jobs[0]
    assert job.channel == "telegram"
    assert job.event == "activated"
    assert job.retry_count == 0
    assert "CPU Usage High" in job.message


def test_queue_is_fifo() -> None:
    queue = NotificationQueue()
    first = _job("one")
    second = _job("two")
    third = _job("three")
    queue.enqueue(first)
    queue.enqueue(second)
    queue.enqueue(third)
    assert queue.dequeue() is first
    assert queue.dequeue() is second
    assert queue.dequeue() is third
    assert queue.dequeue() is None


def test_worker_retries_then_drops_after_max_attempts(caplog) -> None:
    queue = NotificationQueue()
    queue.enqueue(_job("failing"))
    attempts: list[int] = []

    class Boom:
        def send(self, job) -> None:
            attempts.append(job.retry_count)
            raise RuntimeError("telegram down")

    sleeps: list[float] = []
    worker = NotificationWorker(
        queue,
        Boom(),
        retry_delay_seconds=5,
        batch_window_seconds=0,
        sleep=sleeps.append,
    )
    caplog.set_level("WARNING")
    worker.process_one()
    worker.process_one()
    worker.process_one()

    assert attempts == [0, 1, 2]
    assert sleeps == [5, 5]
    assert len(queue) == 0
    assert any("notification_dropped" in record.message for record in caplog.records)
    assert MAX_ATTEMPTS == 3


def test_worker_dispatches_job_to_sender() -> None:
    queue = NotificationQueue()
    job = _job("deliver me")
    queue.enqueue(job)
    sent: list[str] = []

    class Capture:
        def send(self, item) -> None:
            sent.append(item.message)

    worker = NotificationWorker(
        queue,
        Capture(),
        retry_delay_seconds=0,
        batch_window_seconds=0,
        sleep=lambda _: None,
    )
    assert worker.process_one() is True
    assert sent == ["deliver me"]
    assert len(queue) == 0
    assert worker.process_one() is False


def test_telegram_sender_uses_notifier(monkeypatch) -> None:
    sent: list[str] = []

    class StubNotifier:
        recipient = "-100123"

        def send_text(self, text: str) -> dict:
            sent.append(text)
            return {}

        def close(self) -> None:
            return None

        @classmethod
        def from_settings(cls, _settings: Settings) -> "StubNotifier":
            return cls()

    monkeypatch.setattr(
        "homelab_monitor.notification_worker.NotificationService",
        StubNotifier,
    )
    settings = Settings(
        registration_key="test-registration-key-at-least-24-chars",
        jwt_secret="test-jwt-secret-key-at-least-32-chars",
    )
    TelegramSender(settings).send(_job("queued message"))
    assert sent == ["queued message"]


def test_alert_engine_enqueues_and_does_not_call_telegram(monkeypatch) -> None:
    sent: list[str] = []

    def forbidden(_self, text: str) -> dict:
        sent.append(text)
        return {}

    monkeypatch.setattr(
        "homelab_monitor.telegram.TelegramNotifier.send_text",
        forbidden,
    )
    start = datetime(2026, 9, 10, 8, 0, tzinfo=UTC)
    high = _payload()
    with Session(get_engine()) as db:
        agent = _agent(db, "queue-engine-cpu")
        engine = AlertEngine(_settings())
        engine.evaluate_report(db, agent, high, start)
        engine.evaluate_report(db, agent, high, start + timedelta(minutes=2))
        db.commit()

    jobs = get_notification_queue().snapshot()
    assert sent == []
    assert len(jobs) == 1
    assert jobs[0].event == "activated"
    assert jobs[0].channel == "telegram"


def test_alert_engine_and_agent_routes_are_independent_from_telegram() -> None:
    engine_source = inspect.getsource(alert_engine_module)
    assert "TelegramNotifier" not in engine_source
    assert "dispatch_alert_events" not in engine_source
    assert "send_text" not in engine_source
    assert "enqueue_alert_events" in engine_source
    router_source = inspect.getsource(agents_router)
    assert "dispatch_alert_events" not in router_source
    assert "TelegramNotifier" not in router_source
