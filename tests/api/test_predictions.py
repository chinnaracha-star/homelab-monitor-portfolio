from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy.orm import Session

from homelab_monitor.database import get_engine
from homelab_monitor.models import (
    Agent,
    AgentConfiguration,
    AgentGroupMember,
    Alert,
    MetricHistory,
    MetricReport,
    Notification,
    OpsSnapshot,
)

PATHS = ("/overview", "/storage", "/system", "/photos", "/backup")


def _reset() -> None:
    with Session(get_engine()) as db:
        db.execute(delete(Notification))
        db.execute(delete(Alert))
        db.execute(delete(MetricHistory))
        db.execute(delete(MetricReport))
        db.execute(delete(AgentGroupMember))
        db.execute(delete(AgentConfiguration))
        db.execute(delete(Agent))
        db.execute(delete(OpsSnapshot))
        db.commit()


def test_predictions_jwt_rbac_empty(
    client: TestClient,
    auth_header: Callable[..., dict[str, str]],
) -> None:
    _reset()
    assert client.get("/api/v1/predictions/overview").status_code == 401
    for username, password in (
        ("admin", "admin123"),
        ("operator", "operator123"),
        ("viewer", "viewer123"),
    ):
        headers = auth_header(username, password)
        for path in PATHS:
            response = client.get(f"/api/v1/predictions{path}", headers=headers)
            assert response.status_code == 200, path
    body = client.get(
        "/api/v1/predictions/overview", headers=auth_header("viewer", "viewer123")
    ).json()
    assert body["overall_risk"] in {"unknown", "healthy", "warning", "critical"}
    assert body["storage"]["forecasts"]


def test_predictions_with_history(
    client: TestClient,
    auth_header: Callable[..., dict[str, str]],
) -> None:
    _reset()
    now = datetime.now(UTC)
    registration = client.post(
        "/api/v1/agents/register",
        headers={"X-Registration-Key": "test-registration-key-at-least-24-chars"},
        json={
            "name": "pred-agent",
            "hostname": "pred-agent.local",
            "version": "0.1.0",
            "capabilities": ["ubuntu"],
        },
    )
    agent_id = registration.json()["agent_id"]
    with Session(get_engine()) as db:
        db.add_all(
            [
                MetricHistory(
                    agent_id=agent_id,
                    timestamp=now - timedelta(hours=26),
                    cpu_percent=20,
                    memory_percent=30,
                    disk_percent=40,
                    temperature_celsius=40,
                ),
                MetricHistory(
                    agent_id=agent_id,
                    timestamp=now,
                    cpu_percent=40,
                    memory_percent=35,
                    disk_percent=50,
                    temperature_celsius=45,
                ),
                OpsSnapshot(
                    kind="photo",
                    observed_at=now,
                    payload={"indexed_photos": 1000, "storage_used": 50_000, "capacity": 100_000},
                ),
                OpsSnapshot(
                    kind="backup",
                    observed_at=now,
                    payload={
                        "destination_capacity": 1_000_000,
                        "backup_size_bytes": 100_000,
                        "job_status": "idle",
                        "backup_status": "success",
                    },
                ),
            ]
        )
        db.commit()
    headers = auth_header()
    storage = client.get("/api/v1/predictions/storage", headers=headers).json()
    assert len(storage["forecasts"]) == 3
    system = client.get("/api/v1/predictions/system", headers=headers).json()
    assert system["summary"]
    overview = client.get("/api/v1/predictions/overview", headers=headers).json()
    assert overview["storage"]["recommendation"]
    photos = client.get("/api/v1/predictions/photos", headers=headers).json()
    assert photos["forecasts"][1]["horizon_days"] == 30
    backup = client.get("/api/v1/predictions/backup", headers=headers).json()
    assert backup["forecasts"]


def test_predictions_large_history(
    client: TestClient,
    auth_header: Callable[..., dict[str, str]],
) -> None:
    _reset()
    now = datetime.now(UTC)
    registration = client.post(
        "/api/v1/agents/register",
        headers={"X-Registration-Key": "test-registration-key-at-least-24-chars"},
        json={
            "name": "pred-large",
            "hostname": "pred-large.local",
            "version": "0.1.0",
            "capabilities": ["ubuntu"],
        },
    )
    agent_id = registration.json()["agent_id"]
    with Session(get_engine()) as db:
        db.add_all(
            [
                MetricHistory(
                    agent_id=agent_id,
                    timestamp=now - timedelta(hours=index),
                    cpu_percent=20 + (index % 10),
                    memory_percent=30,
                    disk_percent=40 + index * 0.05,
                    temperature_celsius=40,
                )
                for index in range(120)
            ]
        )
        db.commit()
    overview = client.get("/api/v1/predictions/overview", headers=auth_header()).json()
    assert overview["system"]["forecasts"]
    assert overview["overall_risk"] in {"unknown", "healthy", "warning", "critical"}
