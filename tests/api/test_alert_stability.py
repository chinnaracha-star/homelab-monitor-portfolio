from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from homelab_monitor.alert_engine import AlertEngine
from homelab_monitor.database import get_engine
from homelab_monitor.models import Agent, Alert
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


def _payload(*, cpu: float, memory: float, disk: float, temperature: float) -> dict[str, object]:
    return {
        "modules": [
            {
                "module": "system",
                "status": "warning",
                "summary": "System thresholds evaluated",
                "metrics": {
                    "cpu": {"usage_percent": cpu},
                    "memory": {"usage_percent": memory},
                    "disks": [{"mount_point": "/", "usage_percent": disk}],
                    "temperatures": [
                        {
                            "source": "coretemp",
                            "label": "Package",
                            "current_celsius": temperature,
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


def test_cpu_activation_waits_two_minutes() -> None:
    start = datetime(2026, 9, 10, 8, 0, tzinfo=UTC)
    high = _payload(cpu=95, memory=20, disk=30, temperature=40)
    with Session(get_engine()) as db:
        agent = _agent(db, "stability-cpu-delay")
        engine = AlertEngine(_settings())

        pending = engine.evaluate_report(db, agent, high, start)
        db.commit()
        assert pending == []
        assert db.scalar(select(Alert).where(Alert.agent_id == agent.id)) is None

        too_soon = engine.evaluate_report(db, agent, high, start + timedelta(minutes=1))
        db.commit()
        assert too_soon == []
        assert db.scalar(select(Alert).where(Alert.agent_id == agent.id)) is None

        activated = engine.evaluate_report(db, agent, high, start + timedelta(minutes=2))
        db.commit()
        assert len(activated) == 1
        assert activated[0].transition == "activated"
        alert = db.scalar(select(Alert).where(Alert.agent_id == agent.id, Alert.kind == "cpu_high"))
        assert alert is not None
        assert alert.status == "active"


def test_temperature_activates_after_one_minute_storage_is_immediate() -> None:
    start = datetime(2026, 9, 10, 8, 0, tzinfo=UTC)
    high = _payload(cpu=20, memory=20, disk=97, temperature=85)
    with Session(get_engine()) as db:
        agent = _agent(db, "stability-temp-disk")
        engine = AlertEngine(_settings())

        first = engine.evaluate_report(db, agent, high, start)
        db.commit()
        kinds = {event.kind for event in first}
        assert kinds == {"disk_high"}
        assert (
            db.scalar(select(Alert).where(Alert.agent_id == agent.id, Alert.kind == "disk_high"))
            is not None
        )
        assert (
            db.scalar(
                select(Alert).where(Alert.agent_id == agent.id, Alert.kind == "temperature_high")
            )
            is None
        )

        later = engine.evaluate_report(db, agent, high, start + timedelta(minutes=1))
        db.commit()
        assert [event.kind for event in later] == ["temperature_high"]
        assert later[0].transition == "activated"


def test_cpu_recovery_waits_two_minutes_and_storage_recovers_immediately() -> None:
    start = datetime(2026, 9, 10, 8, 0, tzinfo=UTC)
    high = _payload(cpu=95, memory=20, disk=97, temperature=40)
    low = _payload(cpu=20, memory=20, disk=40, temperature=40)
    with Session(get_engine()) as db:
        agent = _agent(db, "stability-recover")
        engine = AlertEngine(_settings())
        engine.evaluate_report(db, agent, high, start)
        engine.evaluate_report(db, agent, high, start + timedelta(minutes=2))
        db.commit()

        first_healthy = engine.evaluate_report(db, agent, low, start + timedelta(minutes=3))
        db.commit()
        assert [event.kind for event in first_healthy] == ["disk_high"]
        assert first_healthy[0].transition == "recovered"
        cpu = db.scalar(select(Alert).where(Alert.agent_id == agent.id, Alert.kind == "cpu_high"))
        disk = db.scalar(select(Alert).where(Alert.agent_id == agent.id, Alert.kind == "disk_high"))
        assert cpu is not None and cpu.status == "active"
        assert disk is not None and disk.status == "resolved"

        recovered = engine.evaluate_report(db, agent, low, start + timedelta(minutes=5))
        db.commit()
        db.refresh(cpu)
        assert [event.kind for event in recovered] == ["cpu_high"]
        assert recovered[0].transition == "recovered"
        assert cpu.status == "resolved"


def test_brief_healthy_sample_resets_trigger_window() -> None:
    start = datetime(2026, 9, 10, 8, 0, tzinfo=UTC)
    high = _payload(cpu=95, memory=20, disk=30, temperature=40)
    low = _payload(cpu=20, memory=20, disk=30, temperature=40)
    with Session(get_engine()) as db:
        agent = _agent(db, "stability-reset-trigger")
        engine = AlertEngine(_settings())
        engine.evaluate_report(db, agent, high, start)
        engine.evaluate_report(db, agent, low, start + timedelta(minutes=1))
        still_pending = engine.evaluate_report(db, agent, high, start + timedelta(minutes=2))
        db.commit()
        assert still_pending == []
        activated = engine.evaluate_report(db, agent, high, start + timedelta(minutes=4))
        db.commit()
        assert len(activated) == 1
        assert activated[0].transition == "activated"


def test_duplicate_active_alert_is_suppressed() -> None:
    start = datetime(2026, 9, 10, 8, 0, tzinfo=UTC)
    high = _payload(cpu=95, memory=20, disk=30, temperature=40)
    with Session(get_engine()) as db:
        agent = _agent(db, "stability-duplicate")
        engine = AlertEngine(_settings())
        engine.evaluate_report(db, agent, high, start)
        first = engine.evaluate_report(db, agent, high, start + timedelta(minutes=2))
        duplicate = engine.evaluate_report(db, agent, high, start + timedelta(minutes=4))
        db.commit()
        assert len(first) == 1
        assert first[0].transition == "activated"
        assert duplicate == []
        count = db.scalar(
            select(func.count())
            .select_from(Alert)
            .where(
                Alert.agent_id == agent.id,
                Alert.kind == "cpu_high",
                Alert.status == "active",
            )
        )
        assert count == 1
