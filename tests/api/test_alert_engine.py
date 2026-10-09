from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from homelab_monitor.alert_engine import AlertEngine
from homelab_monitor.database import get_engine
from homelab_monitor.models import Agent, Alert
from homelab_monitor.security import hash_agent_token
from homelab_monitor.settings import Settings

REGISTRATION_KEY = "test-registration-key-at-least-24-chars"


def alert_settings(**overrides) -> Settings:
    return Settings(
        registration_key=REGISTRATION_KEY,
        alert_cpu_threshold_percent=90,
        alert_memory_threshold_percent=90,
        alert_disk_threshold_percent=90,
        alert_temperature_threshold_celsius=80,
        agent_offline_after_seconds=60,
        **overrides,
    )


def system_payload(
    *,
    cpu: float,
    memory: float,
    disk: float,
    temperature: float,
) -> dict[str, object]:
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


def create_agent(db: Session, name: str, last_seen_at: datetime | None = None) -> Agent:
    agent = Agent(
        name=name,
        hostname=f"{name}.local",
        version="0.1.0",
        token_hash=hash_agent_token(f"{name}-token"),
        status="online",
        capabilities=["ubuntu"],
        last_seen_at=last_seen_at,
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


def test_metric_alerts_open_update_and_resolve() -> None:
    observed_at = datetime.now(UTC)
    with Session(get_engine()) as db:
        agent = create_agent(db, "alert-metrics")
        engine = AlertEngine(alert_settings())

        high = system_payload(cpu=95, memory=96, disk=97, temperature=85)
        engine.evaluate_report(db, agent, high, observed_at)
        engine.evaluate_report(db, agent, high, observed_at + timedelta(minutes=2))
        db.commit()

        alerts = list(
            db.scalars(select(Alert).where(Alert.agent_id == agent.id).order_by(Alert.kind))
        )
        assert {alert.kind for alert in alerts} == {
            "cpu_high",
            "memory_high",
            "disk_high",
            "temperature_high",
        }
        assert all(alert.status == "active" for alert in alerts)

        low = system_payload(cpu=20, memory=30, disk=40, temperature=50)
        engine.evaluate_report(db, agent, low, observed_at + timedelta(minutes=3))
        engine.evaluate_report(db, agent, low, observed_at + timedelta(minutes=5))
        db.commit()

        resolved = list(db.scalars(select(Alert).where(Alert.agent_id == agent.id)))
        assert all(alert.status == "resolved" for alert in resolved)
        assert all(alert.resolved_at is not None for alert in resolved)


def test_agent_offline_alert_opens_and_resolves() -> None:
    now = datetime.now(UTC)
    with Session(get_engine()) as db:
        agent = create_agent(db, "alert-offline", now - timedelta(seconds=120))
        engine = AlertEngine(alert_settings())

        engine.evaluate_offline_agents(db, now)
        db.commit()
        db.refresh(agent)

        alert = db.scalar(
            select(Alert).where(
                Alert.agent_id == agent.id,
                Alert.kind == "agent_offline",
            )
        )
        assert agent.status == "offline"
        assert alert is not None
        assert alert.status == "active"
        assert alert.current_value == 120

        agent.status = "online"
        engine.mark_agent_online(db, agent, now + timedelta(seconds=1))
        db.commit()
        db.refresh(alert)

        assert alert.status == "resolved"
        assert alert.resolved_at is not None


def test_report_upload_persists_alert_without_changing_response(client: TestClient) -> None:
    registration = client.post(
        "/api/v1/agents/register",
        headers={"X-Registration-Key": REGISTRATION_KEY},
        json={
            "name": "alert-upload",
            "hostname": "alert-upload.local",
            "version": "0.1.0",
            "capabilities": ["ubuntu"],
        },
    )
    assert registration.status_code == 201
    credentials = registration.json()

    start = datetime(2026, 9, 10, 8, 0, tzinfo=UTC)
    payload = system_payload(cpu=95, memory=20, disk=30, temperature=40)
    first = client.post(
        "/api/v1/agent/reports",
        headers={"Authorization": f"Bearer {credentials['agent_token']}"},
        json={
            "report_id": "alert-report-001",
            "schema_version": "1.0",
            "observed_at": start.isoformat(),
            "config_revision": 1,
            **payload,
        },
    )
    report = client.post(
        "/api/v1/agent/reports",
        headers={"Authorization": f"Bearer {credentials['agent_token']}"},
        json={
            "report_id": "alert-report-002",
            "schema_version": "1.0",
            "observed_at": (start + timedelta(minutes=2)).isoformat(),
            "config_revision": 1,
            **payload,
        },
    )

    assert first.status_code == 200
    assert report.status_code == 200
    assert report.json()["accepted"] is True
    assert report.json()["duplicate"] is False

    with Session(get_engine()) as db:
        agent = db.scalar(select(Agent).where(Agent.name == "alert-upload"))
        assert agent is not None
        alert = db.scalar(
            select(Alert).where(
                Alert.agent_id == agent.id,
                Alert.kind == "cpu_high",
            )
        )
        assert alert is not None
        assert alert.status == "active"
        assert alert.current_value == 95
