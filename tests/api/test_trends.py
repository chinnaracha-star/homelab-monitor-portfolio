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
from homelab_monitor.trends import _forecast_full_date

REGISTRATION_KEY = "test-registration-key-at-least-24-chars"
PATHS = ("/overview", "/cpu", "/memory", "/storage", "/photos", "/backup")


def test_forecast_full_date_clamps_overflow() -> None:
    end = datetime(2026, 9, 10, tzinfo=UTC)
    assert _forecast_full_date(end, 5.25).startswith("2026-09-")
    assert _forecast_full_date(end, 1e12)
    assert _forecast_full_date(end, None) == ""
    assert _forecast_full_date(end, -1) == ""


def _reset_analytics_sources() -> None:
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


def _register(client: TestClient, name: str = "trend-agent") -> str:
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


def test_trends_require_jwt(client: TestClient) -> None:
    assert client.get("/api/v1/trends/overview").status_code == 401
    assert client.get("/api/v1/trends/cpu").status_code == 401


def test_all_roles_can_read_trends(
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
            assert client.get(f"/api/v1/trends{path}", headers=headers).status_code == 200


def test_trends_empty_database(
    client: TestClient,
    auth_header: Callable[..., dict[str, str]],
) -> None:
    _reset_analytics_sources()
    headers = auth_header("viewer", "viewer123")
    cpu = client.get("/api/v1/trends/cpu", headers=headers).json()
    overview = client.get("/api/v1/trends/overview", headers=headers).json()
    assert cpu["latest"] is None
    assert cpu["trend"] == "stable"
    assert cpu["hourly"] == []
    assert overview["overall_score"] >= 0
    assert "healthy_count" in overview["health"]


def test_trend_calculations_and_forecast(
    client: TestClient,
    auth_header: Callable[..., dict[str, str]],
) -> None:
    _reset_analytics_sources()
    agent_id = _register(client)
    now = datetime.now(UTC)
    previous_day = now - timedelta(hours=36)
    last_week = now - timedelta(days=8)
    with Session(get_engine()) as db:
        db.add_all(
            [
                MetricHistory(
                    agent_id=agent_id,
                    timestamp=previous_day,
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
                    observed_at=last_week,
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
                    observed_at=now - timedelta(hours=2),
                    payload={
                        "job_status": "idle",
                        "backup_status": "success",
                        "duration_seconds": 600,
                        "progress_percent": 100,
                    },
                ),
                OpsSnapshot(
                    kind="backup",
                    observed_at=now - timedelta(hours=1),
                    payload={
                        "job_status": "failed",
                        "backup_status": "failed",
                        "duration_seconds": 900,
                    },
                ),
            ]
        )
        db.commit()

    headers = auth_header()
    cpu = client.get("/api/v1/trends/cpu", headers=headers).json()
    assert cpu["latest"] == 40
    assert cpu["average_1d"] == 40
    assert cpu["trend"] == "rising"
    assert cpu["difference_percent"] > 5
    assert cpu["hourly"]
    assert cpu["daily"]

    memory = client.get("/api/v1/trends/memory", headers=headers).json()
    assert memory["latest"] == 50
    assert memory["trend"] == "rising"

    storage = client.get("/api/v1/trends/storage", headers=headers).json()
    assert storage["current_used"] == 5800
    assert storage["daily_growth_bytes"] == 800
    assert storage["growth_per_day"] == 800
    assert storage["used_percent"] == 58
    assert storage["estimated_days_until_full"] == 5.25
    assert storage["trend"] == "rising"
    assert storage["estimated_full_date"]
    assert any(point["label"].startswith("+") for point in storage["series"])

    photos = client.get("/api/v1/trends/photos", headers=headers).json()
    assert photos["today"] == 200
    assert photos["this_week"] == 300
    assert photos["expected_next_week"] == 300
    assert photos["series"]

    backup = client.get("/api/v1/trends/backup", headers=headers).json()
    assert backup["last_30_backups"] == 2
    assert backup["success_rate"] == 50
    assert backup["failure_rate"] == 50
    assert backup["fastest"] == 600
    assert backup["slowest"] == 900
    assert backup["average_duration"] == 750

    overview = client.get("/api/v1/trends/overview", headers=headers).json()
    assert overview["cpu_trend"] == "rising"
    assert overview["storage_trend"] == "rising"
    assert 0 <= overview["overall_score"] <= 100
    assert overview["health"]["healthy_count"] >= 0
