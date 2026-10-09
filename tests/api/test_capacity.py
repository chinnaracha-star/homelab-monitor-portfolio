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
PATHS = ("/overview", "/storage", "/photos", "/backup", "/system")


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


def _register(client: TestClient, name: str = "capacity-agent") -> str:
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


def test_capacity_requires_jwt(client: TestClient) -> None:
    assert client.get("/api/v1/capacity/overview").status_code == 401
    assert client.get("/api/v1/capacity/storage").status_code == 401


def test_all_roles_can_read_capacity(
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
            assert client.get(f"/api/v1/capacity{path}", headers=headers).status_code == 200


def test_capacity_empty_database(
    client: TestClient,
    auth_header: Callable[..., dict[str, str]],
) -> None:
    _reset()
    headers = auth_header("viewer", "viewer123")
    storage = client.get("/api/v1/capacity/storage", headers=headers).json()
    overview = client.get("/api/v1/capacity/overview", headers=headers).json()
    assert storage["risk"] == "unknown"
    assert storage["estimated_days_remaining"] is None
    assert overview["capacity_score"] >= 0
    assert overview["recommendations"]


def test_capacity_no_growth(
    client: TestClient,
    auth_header: Callable[..., dict[str, str]],
) -> None:
    _reset()
    now = datetime.now(UTC)
    with Session(get_engine()) as db:
        db.add_all(
            [
                OpsSnapshot(
                    kind="photo",
                    observed_at=now - timedelta(days=8),
                    payload={
                        "indexed_photos": 1000,
                        "storage_used": 5_000,
                        "capacity_bytes": 10_000,
                    },
                ),
                OpsSnapshot(
                    kind="photo",
                    observed_at=now - timedelta(days=2),
                    payload={
                        "indexed_photos": 1000,
                        "storage_used": 5_000,
                        "capacity_bytes": 10_000,
                    },
                ),
                OpsSnapshot(
                    kind="photo",
                    observed_at=now,
                    payload={
                        "indexed_photos": 1000,
                        "storage_used": 5_000,
                        "capacity_bytes": 10_000,
                    },
                ),
            ]
        )
        db.commit()
    storage = client.get(
        "/api/v1/capacity/storage", headers=auth_header("viewer", "viewer123")
    ).json()
    assert storage["average_daily_growth"] == 0
    assert storage["risk"] == "unknown"
    assert storage["estimated_full_in"] == "Unknown"


def test_capacity_forecast_score_and_recommendations(
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
                    timestamp=now - timedelta(hours=36),
                    cpu_percent=10,
                    memory_percent=20,
                    disk_percent=40,
                ),
                MetricHistory(
                    agent_id=agent_id,
                    timestamp=now,
                    cpu_percent=40,
                    memory_percent=50,
                    disk_percent=55,
                ),
                OpsSnapshot(
                    kind="photo",
                    observed_at=now - timedelta(days=8),
                    payload={
                        "indexed_photos": 1000,
                        "storage_used": 4_000,
                        "capacity_bytes": 10_000,
                    },
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
                    observed_at=now - timedelta(days=7),
                    payload={
                        "job_status": "idle",
                        "backup_status": "success",
                        "duration_seconds": 600,
                        "backup_size_bytes": 1_000,
                    },
                ),
                OpsSnapshot(
                    kind="backup",
                    observed_at=now,
                    payload={
                        "job_status": "idle",
                        "backup_status": "success",
                        "duration_seconds": 900,
                        "backup_size_bytes": 1_700,
                    },
                ),
            ]
        )
        db.commit()

    headers = auth_header()
    storage = client.get("/api/v1/capacity/storage", headers=headers).json()
    assert storage["current_used"] == 5800
    assert storage["capacity"] == 10_000
    assert storage["current_free"] == 4200
    assert storage["average_daily_growth"] == 800
    assert storage["estimated_days_remaining"] == 5.25
    assert storage["estimated_full_in"] == "5 Days"
    assert storage["risk"] == "critical"
    assert storage["estimated_full_date"]

    photos = client.get("/api/v1/capacity/photos", headers=headers).json()
    assert photos["photos_today"] == 200
    assert photos["photos_this_week"] == 300
    assert photos["average_photos_per_day"] > 0
    assert photos["expected_photos_next_month"] > 0
    assert photos["average_size_per_photo"] > 0

    backup = client.get("/api/v1/capacity/backup", headers=headers).json()
    assert backup["current_backup_size"] == 1700
    assert backup["growth_per_day"] > 0
    assert backup["success_percent"] == 100
    assert backup["average_duration"] == 750

    system = client.get("/api/v1/capacity/system", headers=headers).json()
    assert 0 <= system["overall_score"] <= 100
    assert system["bottleneck"] in {"storage", "backup", "cpu", "memory"}
    assert system["cpu_trend"] == "rising"

    overview = client.get("/api/v1/capacity/overview", headers=headers).json()
    assert overview["storage_risk"] == "critical"
    assert overview["capacity_score"] == system["overall_score"]
    joined = " ".join(overview["recommendations"])
    assert "approximately 5.25 days" in joined
    assert "larger NAS" in joined
    assert "bottleneck first" in joined


def test_capacity_large_history(
    client: TestClient,
    auth_header: Callable[..., dict[str, str]],
) -> None:
    _reset()
    agent_id = _register(client)
    now = datetime.now(UTC)
    rows: list[MetricHistory] = []
    for index in range(400):
        rows.append(
            MetricHistory(
                agent_id=agent_id,
                timestamp=now - timedelta(hours=index % 200),
                cpu_percent=20,
                memory_percent=30,
                disk_percent=40,
            )
        )
    with Session(get_engine()) as db:
        db.add_all(rows)
        db.commit()
    response = client.get("/api/v1/capacity/overview", headers=auth_header())
    assert response.status_code == 200
    assert 0 <= response.json()["capacity_score"] <= 100
