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

REGISTRATION_KEY = "test-registration-key-at-least-24-chars"
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


def _register(client: TestClient, name: str = "insight-agent") -> str:
    response = client.post(
        "/api/v1/agents/register",
        headers={"X-Registration-Key": REGISTRATION_KEY},
        json={
            "name": name,
            "hostname": f"{name}.local",
            "version": "0.1.0",
            "capabilities": ["ubuntu"],
        },
    )
    assert response.status_code == 201
    return str(response.json()["agent_id"])


def test_insights_require_jwt(client: TestClient) -> None:
    assert client.get("/api/v1/insights/overview").status_code == 401
    assert client.get("/api/v1/insights/storage").status_code == 401


def test_all_roles_can_read_insights(
    client: TestClient,
    auth_header: Callable[..., dict[str, str]],
) -> None:
    for username, password in (
        ("admin", "admin123"),
        ("operator", "operator123"),
        ("viewer", "viewer123"),
    ):
        headers = auth_header(username, password)
        for path in PATHS:
            assert client.get(f"/api/v1/insights{path}", headers=headers).status_code == 200


def test_insights_empty_database(
    client: TestClient,
    auth_header: Callable[..., dict[str, str]],
) -> None:
    _reset()
    headers = auth_header("viewer", "viewer123")
    body = client.get("/api/v1/insights/overview", headers=headers).json()
    assert body["storage"]["severity"] == "unknown"
    assert body["cpu"]["severity"] == "unknown"
    assert body["memory"]["severity"] == "unknown"
    assert body["photos"]["severity"] == "unknown"
    assert body["infrastructure"]["severity"] in {"info", "unknown"}
    assert body["severity"] in {"info", "unknown", "warning"}


def test_insights_critical_storage(
    client: TestClient,
    auth_header: Callable[..., dict[str, str]],
) -> None:
    _reset()
    agent_id = _register(client)
    now = datetime.now(UTC)
    with Session(get_engine()) as db:
        db.add_all(
            [
                MetricHistory(
                    agent_id=agent_id,
                    timestamp=now,
                    cpu_percent=20,
                    memory_percent=20,
                    disk_percent=55,
                ),
                OpsSnapshot(
                    kind="photo",
                    observed_at=now - timedelta(hours=26),
                    payload={
                        "indexed_photos": 1100,
                        "storage_used": 5_000,
                        "capacity_bytes": 10_000,
                    },
                ),
                OpsSnapshot(
                    kind="photo",
                    observed_at=now,
                    payload={
                        "indexed_photos": 1300,
                        "storage_used": 5_800,
                        "capacity_bytes": 10_000,
                    },
                ),
                OpsSnapshot(
                    kind="backup",
                    observed_at=now,
                    payload={
                        "job_status": "idle",
                        "backup_status": "success",
                        "duration_seconds": 600,
                    },
                ),
            ]
        )
        db.commit()
    storage = client.get("/api/v1/insights/storage", headers=auth_header()).json()
    overview = client.get("/api/v1/insights/overview", headers=auth_header()).json()
    assert storage["severity"] == "critical"
    assert "94 days" not in storage["summary"]
    assert "days" in storage["summary"]
    assert storage["recommendation"] == "Consider adding larger disks."
    assert overview["severity"] == "critical"
    assert "Storage capacity should be reviewed." in overview["overall"]["summary"]


def test_insights_warning_cpu_and_photos(
    client: TestClient,
    auth_header: Callable[..., dict[str, str]],
) -> None:
    _reset()
    agent_id = _register(client, "insight-warn")
    now = datetime.now(UTC)
    with Session(get_engine()) as db:
        db.add_all(
            [
                MetricHistory(
                    agent_id=agent_id,
                    timestamp=now - timedelta(hours=36),
                    cpu_percent=10,
                    memory_percent=20,
                    disk_percent=20,
                ),
                MetricHistory(
                    agent_id=agent_id,
                    timestamp=now,
                    cpu_percent=40,
                    memory_percent=50,
                    disk_percent=22,
                ),
                OpsSnapshot(
                    kind="photo",
                    observed_at=now - timedelta(days=10),
                    payload={
                        "indexed_photos": 100,
                        "storage_used": 100,
                        "capacity_bytes": 1_000_000,
                    },
                ),
                OpsSnapshot(
                    kind="photo",
                    observed_at=now - timedelta(days=8),
                    payload={
                        "indexed_photos": 120,
                        "storage_used": 120,
                        "capacity_bytes": 1_000_000,
                    },
                ),
                OpsSnapshot(
                    kind="photo",
                    observed_at=now,
                    payload={
                        "indexed_photos": 400,
                        "storage_used": 200,
                        "capacity_bytes": 1_000_000,
                    },
                ),
            ]
        )
        db.commit()
    system = client.get("/api/v1/insights/system", headers=auth_header()).json()
    photos = client.get("/api/v1/insights/photos", headers=auth_header()).json()
    assert system["cpu"]["severity"] == "warning"
    assert system["cpu"]["summary"] == "CPU trend is rising."
    assert system["memory"]["severity"] == "warning"
    assert photos["severity"] in {"info", "warning"}
    assert photos["summary"]


def test_insights_healthy_backup_and_cpu(
    client: TestClient,
    auth_header: Callable[..., dict[str, str]],
) -> None:
    _reset()
    agent_id = _register(client, "insight-ok")
    now = datetime.now(UTC)
    with Session(get_engine()) as db:
        db.add_all(
            [
                MetricHistory(
                    agent_id=agent_id,
                    timestamp=now - timedelta(hours=2),
                    cpu_percent=20,
                    memory_percent=30,
                    disk_percent=20,
                ),
                MetricHistory(
                    agent_id=agent_id,
                    timestamp=now,
                    cpu_percent=21,
                    memory_percent=31,
                    disk_percent=20,
                ),
                OpsSnapshot(
                    kind="backup",
                    observed_at=now - timedelta(hours=2),
                    payload={
                        "job_status": "idle",
                        "backup_status": "success",
                        "duration_seconds": 100,
                    },
                ),
                OpsSnapshot(
                    kind="backup",
                    observed_at=now,
                    payload={
                        "job_status": "idle",
                        "backup_status": "success",
                        "duration_seconds": 110,
                    },
                ),
            ]
        )
        db.commit()
    backup = client.get("/api/v1/insights/backup", headers=auth_header()).json()
    system = client.get("/api/v1/insights/system", headers=auth_header()).json()
    assert backup["severity"] == "info"
    assert backup["summary"] == "Backup success rate is excellent."
    assert system["cpu"]["severity"] == "info"
    assert system["infrastructure"]["severity"] == "info"
    assert "healthy" in system["infrastructure"]["summary"].lower()
