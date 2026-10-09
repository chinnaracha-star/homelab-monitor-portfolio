from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy.orm import Session

from homelab_monitor.analytics import AnalyticsService
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
from homelab_monitor.ops_history import _start_of_local_day

REGISTRATION_KEY = "test-registration-key-at-least-24-chars"


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


def _register(client: TestClient, name: str = "analytics-agent") -> str:
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


def test_analytics_empty_database(
    client: TestClient,
    auth_header: Callable[..., dict[str, str]],
) -> None:
    _reset_analytics_sources()
    headers = auth_header("viewer", "viewer123")
    overview = client.get("/api/v1/analytics/overview", headers=headers)
    cpu = client.get("/api/v1/analytics/cpu", headers=headers)
    assert overview.status_code == 200
    assert cpu.status_code == 200
    body = overview.json()
    assert body["cpu_average"] is None
    assert body["storage_used"] == 0
    assert body["photos_today"] == 0
    assert body["daily"]["agents_total"] == 0
    assert cpu.json()["series"] == []
    assert cpu.json()["current"] is None


def test_analytics_requires_jwt(client: TestClient) -> None:
    assert client.get("/api/v1/analytics/overview").status_code == 401
    assert client.get("/api/v1/analytics/cpu").status_code == 401


def test_all_roles_can_read_analytics(
    client: TestClient,
    auth_header: Callable[..., dict[str, str]],
) -> None:
    for username, password in (
        ("admin", "admin123"),
        ("operator", "operator123"),
        ("viewer", "viewer123"),
    ):
        headers = auth_header(username, password)
        for path in (
            "/overview",
            "/cpu",
            "/memory",
            "/storage",
            "/temperature",
            "/photos",
            "/backup",
        ):
            response = client.get(f"/api/v1/analytics{path}", headers=headers)
            assert response.status_code == 200, path


def test_analytics_aggregates_history_and_ops(
    client: TestClient,
    auth_header: Callable[..., dict[str, str]],
) -> None:
    _reset_analytics_sources()
    agent_id = _register(client)
    now = datetime.now(UTC)
    older = now - timedelta(hours=2)
    start_today = _start_of_local_day(now)
    yesterday = start_today - timedelta(minutes=1)
    last_week = start_today - timedelta(days=8)
    with Session(get_engine()) as db:
        db.add_all(
            [
                MetricHistory(
                    agent_id=agent_id,
                    timestamp=older,
                    cpu_percent=10,
                    memory_percent=20,
                    disk_percent=30,
                    temperature_celsius=40,
                ),
                MetricHistory(
                    agent_id=agent_id,
                    timestamp=now,
                    cpu_percent=20,
                    memory_percent=40,
                    disk_percent=50,
                    temperature_celsius=50,
                ),
                OpsSnapshot(
                    kind="photo",
                    observed_at=last_week,
                    payload={"indexed_photos": 1000, "storage_used": 1_000},
                ),
                OpsSnapshot(
                    kind="photo",
                    observed_at=yesterday,
                    payload={"indexed_photos": 1100, "storage_used": 1_200},
                ),
                OpsSnapshot(
                    kind="photo",
                    observed_at=now,
                    payload={"indexed_photos": 1300, "storage_used": 1_500},
                ),
                OpsSnapshot(
                    kind="backup",
                    observed_at=now - timedelta(hours=3),
                    payload={
                        "job_status": "idle",
                        "backup_status": "success",
                        "last_backup": "2026-09-07T02:00:00+00:00",
                        "duration_seconds": 900,
                    },
                ),
                OpsSnapshot(
                    kind="backup",
                    observed_at=now - timedelta(hours=1),
                    payload={
                        "job_status": "failed",
                        "backup_status": "failed",
                        "duration_seconds": 400,
                    },
                ),
                Notification(channel="telegram", recipient="chat", status="sent"),
            ]
        )
        db.commit()

    headers = auth_header()
    cpu = client.get("/api/v1/analytics/cpu", headers=headers).json()
    assert cpu["current"] == 20
    assert cpu["average_24h"] == 15
    assert cpu["minimum"] == 10
    assert cpu["maximum"] == 20
    assert cpu["series"]

    memory = client.get("/api/v1/analytics/memory", headers=headers).json()
    assert memory["current"] == 40
    assert memory["average"] == 30

    temperature = client.get("/api/v1/analytics/temperature", headers=headers).json()
    assert temperature["current"] == 50
    assert temperature["average"] == 45

    storage = client.get("/api/v1/analytics/storage", headers=headers).json()
    assert storage["current"] == 1500
    assert storage["daily_growth"] == 300
    assert storage["weekly_growth"] == 500
    assert storage["series"]

    photos = client.get("/api/v1/analytics/photos", headers=headers).json()
    assert photos["today"] == 200
    assert photos["yesterday"] == 100
    assert photos["this_week"] == 300
    assert photos["growth"] == 300
    assert [point["label"] for point in photos["series"]] == ["Today", "Yesterday", "This week"]

    backup = client.get("/api/v1/analytics/backup", headers=headers).json()
    assert backup["success_rate"] == 50
    assert backup["duration_seconds"] == 400
    assert len(backup["series"]) == 2

    overview = client.get("/api/v1/analytics/overview", headers=headers).json()
    assert overview["cpu_average"] == 15
    assert overview["memory_average"] == 30
    assert overview["storage_used"] == 1500
    assert overview["photos_today"] == 200
    assert overview["backup_success_rate"] == 50
    assert overview["temperature_average"] == 45
    assert overview["daily"]["agents_total"] == 1
    assert overview["daily"]["history_points_today"] >= 1
    assert overview["daily"]["notifications_today"] >= 1


def test_photos_today_counts_from_local_midnight() -> None:
    _reset_analytics_sources()
    now = datetime(2026, 9, 10, 0, 33, tzinfo=UTC)
    start_today = _start_of_local_day(now)
    with Session(get_engine()) as db:
        db.add_all(
            [
                OpsSnapshot(
                    kind="photo",
                    observed_at=start_today - timedelta(minutes=5),
                    payload={"indexed_photos": 79100, "storage_used": 1000},
                ),
                OpsSnapshot(
                    kind="photo",
                    observed_at=now,
                    payload={"indexed_photos": 79119, "storage_used": 1100},
                ),
            ]
        )
        db.commit()
        photos = AnalyticsService().photos(db, now=now)
        overview = AnalyticsService().overview(db, now=now)
    assert photos.today == 19
    assert overview.photos_today == 19


def test_photos_today_resets_at_local_midnight() -> None:
    _reset_analytics_sources()
    just_after_midnight = datetime(2026, 9, 9, 17, 5, tzinfo=UTC)
    with Session(get_engine()) as db:
        db.add_all(
            [
                OpsSnapshot(
                    kind="photo",
                    observed_at=datetime(2026, 9, 9, 16, 55, tzinfo=UTC),
                    payload={"indexed_photos": 79100, "storage_used": 1000},
                ),
                OpsSnapshot(
                    kind="photo",
                    observed_at=just_after_midnight,
                    payload={"indexed_photos": 79100, "storage_used": 1000},
                ),
            ]
        )
        db.commit()
        photos = AnalyticsService().photos(db, now=just_after_midnight)
    assert photos.today == 0
