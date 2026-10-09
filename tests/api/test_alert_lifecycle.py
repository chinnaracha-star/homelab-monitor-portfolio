from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from homelab_monitor.alert_engine import AlertEngine, alert_duration_seconds
from homelab_monitor.database import get_engine
from homelab_monitor.models import (
    Agent,
    AgentConfiguration,
    AgentGroupMember,
    Alert,
    MetricHistory,
    MetricReport,
    Notification,
)
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


def _payload(cpu: float) -> dict[str, object]:
    return {
        "modules": [
            {
                "module": "system",
                "status": "warning",
                "summary": "cpu",
                "metrics": {
                    "cpu": {"usage_percent": cpu},
                    "memory": {"usage_percent": 10},
                    "disks": [{"mount_point": "/", "usage_percent": 10}],
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


def _reset() -> None:
    with Session(get_engine()) as db:
        db.execute(delete(Notification))
        db.execute(delete(Alert))
        db.execute(delete(MetricHistory))
        db.execute(delete(MetricReport))
        db.execute(delete(AgentGroupMember))
        db.execute(delete(AgentConfiguration))
        db.execute(delete(Agent))
        db.commit()


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


def test_duration_calculation() -> None:
    start = datetime(2026, 9, 8, 8, 0, tzinfo=UTC)
    recovered = datetime(2026, 9, 8, 8, 17, tzinfo=UTC)
    assert alert_duration_seconds(None, None, recovered, recovered=False) is None
    assert alert_duration_seconds(start, recovered, recovered, recovered=True) == 17 * 60
    assert alert_duration_seconds(start, None, start + timedelta(minutes=3), recovered=False) == 180


def test_first_activation_duplicate_recovery_and_repeat() -> None:
    observed = datetime(2026, 9, 8, 8, 0, tzinfo=UTC)
    with Session(get_engine()) as db:
        agent = _agent(db, "lifecycle-cpu")
        engine = AlertEngine(_settings())

        first_pending = engine.evaluate_report(db, agent, _payload(96), observed)
        db.commit()
        assert first_pending == []
        assert (
            db.scalar(select(Alert).where(Alert.agent_id == agent.id, Alert.kind == "cpu_high"))
            is None
        )

        activated_at = observed + timedelta(minutes=2)
        first = engine.evaluate_report(db, agent, _payload(96), activated_at)
        db.commit()
        assert len(first) == 1
        assert first[0].transition == "activated"
        assert first[0].duration_seconds == 0
        alert = db.scalar(select(Alert).where(Alert.agent_id == agent.id, Alert.kind == "cpu_high"))
        assert alert is not None
        assert alert.status == "active"
        opened = alert.opened_at

        duplicate = engine.evaluate_report(db, agent, _payload(97), observed + timedelta(minutes=5))
        db.commit()
        db.refresh(alert)
        assert duplicate == []
        assert alert.status == "active"
        assert alert.opened_at == opened
        assert alert.current_value == 97

        still_active = engine.evaluate_report(
            db, agent, _payload(41), observed + timedelta(minutes=17)
        )
        db.commit()
        db.refresh(alert)
        assert still_active == []
        assert alert.status == "active"

        recovered_at = observed + timedelta(minutes=19)
        recovered = engine.evaluate_report(db, agent, _payload(41), recovered_at)
        db.commit()
        db.refresh(alert)
        assert len(recovered) == 1
        assert recovered[0].transition == "recovered"
        assert recovered[0].duration_seconds == 17 * 60
        assert alert.status == "resolved"
        assert alert.resolved_at is not None

        later = observed + timedelta(minutes=20)
        pending_again = engine.evaluate_report(db, agent, _payload(96), later)
        db.commit()
        db.refresh(alert)
        assert pending_again == []
        assert alert.status == "resolved"

        reopened_at = later + timedelta(minutes=2)
        again = engine.evaluate_report(db, agent, _payload(96), reopened_at)
        db.commit()
        db.refresh(alert)
        assert len(again) == 1
        assert again[0].transition == "activated"
        assert alert.status == "active"
        assert alert.resolved_at is None
        assert AlertEngine._as_utc(alert.opened_at) == reopened_at
        assert alert.id  # same unique row, new lifecycle timestamps


def test_alerts_api_empty_jwt_and_rbac(
    client: TestClient,
    auth_header: Callable[..., dict[str, str]],
) -> None:
    _reset()
    assert client.get("/api/v1/alerts/active").status_code == 401
    viewer = client.get(
        "/api/v1/alerts/active",
        headers=auth_header("viewer", "viewer123"),
    )
    operator = client.get(
        "/api/v1/alerts/active",
        headers=auth_header("operator", "operator123"),
    )
    recovered = client.get(
        "/api/v1/alerts/active",
        params={"include_recovered": True},
        headers=auth_header("admin", "admin123"),
    )
    assert viewer.status_code == 200
    assert operator.status_code == 200
    assert recovered.status_code == 200
    assert viewer.json() == []
    assert recovered.json() == []


def test_alerts_api_exposes_lifecycle_fields(
    client: TestClient,
    auth_header: Callable[..., dict[str, str]],
) -> None:
    _reset()
    registration = client.post(
        "/api/v1/agents/register",
        headers={"X-Registration-Key": REGISTRATION_KEY},
        json={
            "name": "lifecycle-api",
            "hostname": "lifecycle-api.local",
            "version": "0.1.0",
            "capabilities": ["ubuntu"],
        },
    )
    token = registration.json()["agent_token"]
    start = datetime(2026, 9, 8, 8, 0, tzinfo=UTC)
    high = client.post(
        "/api/v1/agent/reports",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "report_id": "lifecycle-high",
            "schema_version": "1.0",
            "observed_at": start.isoformat(),
            "config_revision": 1,
            **_payload(96),
        },
    )
    assert high.status_code == 200
    held = client.post(
        "/api/v1/agent/reports",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "report_id": "lifecycle-high-held",
            "schema_version": "1.0",
            "observed_at": (start + timedelta(minutes=2)).isoformat(),
            "config_revision": 1,
            **_payload(96),
        },
    )
    assert held.status_code == 200
    headers = auth_header()
    active = client.get("/api/v1/alerts/active", headers=headers).json()
    assert len(active) == 1
    item = active[0]
    assert item["status"] == "active"
    assert item["started_at"] == item["opened_at"]
    assert item["last_triggered_at"] == item["last_observed_at"]
    assert item["recovered_at"] is None
    assert item["duration_seconds"] is not None
    assert item["duration_seconds"] >= 0

    low = client.post(
        "/api/v1/agent/reports",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "report_id": "lifecycle-low",
            "schema_version": "1.0",
            "observed_at": (start + timedelta(minutes=3)).isoformat(),
            "config_revision": 1,
            **_payload(41),
        },
    )
    assert low.status_code == 200
    recovering = client.get("/api/v1/alerts/active", headers=headers).json()
    assert len(recovering) == 1
    assert recovering[0]["status"] == "active"

    recovered_report = client.post(
        "/api/v1/agent/reports",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "report_id": "lifecycle-low-held",
            "schema_version": "1.0",
            "observed_at": (start + timedelta(minutes=5)).isoformat(),
            "config_revision": 1,
            **_payload(41),
        },
    )
    assert recovered_report.status_code == 200
    still_active = client.get("/api/v1/alerts/active", headers=headers).json()
    assert still_active == []
    recovered = client.get(
        "/api/v1/alerts/active",
        params={"include_recovered": True},
        headers=headers,
    ).json()
    assert len(recovered) == 1
    assert recovered[0]["status"] == "recovered"
    assert recovered[0]["recovered_at"] is not None
    assert recovered[0]["duration_seconds"] is not None


def test_websocket_events_stay_compatible(
    client: TestClient,
    login: Callable[..., str],
) -> None:
    _reset()
    dashboard_token = login()
    registration = client.post(
        "/api/v1/agents/register",
        headers={"X-Registration-Key": REGISTRATION_KEY},
        json={
            "name": "lifecycle-ws",
            "hostname": "lifecycle-ws.local",
            "version": "0.1.0",
            "capabilities": ["ubuntu"],
        },
    )
    agent_token = registration.json()["agent_token"]
    allowed = {"connection", "overview_updated", "agent_updated", "alert_updated"}
    with client.websocket_connect(
        "/api/v1/ws/dashboard",
        headers={"Authorization": f"Bearer {dashboard_token}"},
    ) as websocket:
        assert websocket.receive_json()["type"] == "connection"
        response = client.post(
            "/api/v1/agent/reports",
            headers={"Authorization": f"Bearer {agent_token}"},
            json={
                "report_id": "lifecycle-ws-high",
                "schema_version": "1.0",
                "observed_at": datetime.now(UTC).isoformat(),
                "config_revision": 1,
                **_payload(96),
            },
        )
        assert response.status_code == 200
        types = {websocket.receive_json()["type"] for _ in range(3)}
        assert types <= allowed
        held = client.post(
            "/api/v1/agent/reports",
            headers={"Authorization": f"Bearer {agent_token}"},
            json={
                "report_id": "lifecycle-ws-high-held",
                "schema_version": "1.0",
                "observed_at": (datetime.now(UTC) + timedelta(minutes=2)).isoformat(),
                "config_revision": 1,
                **_payload(96),
            },
        )
        assert held.status_code == 200
        held_types = {websocket.receive_json()["type"] for _ in range(3)}
        assert held_types <= allowed
        assert "alert_updated" in held_types
