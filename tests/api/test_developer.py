from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy.orm import Session

from homelab_monitor.database import get_engine
from homelab_monitor.developer_dashboard import DeveloperDashboardService
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
from homelab_monitor.routers import developer as developer_router

REGISTRATION_KEY = "test-registration-key-at-least-24-chars"


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


def test_developer_overview_requires_jwt(client: TestClient) -> None:
    assert client.get("/api/v1/developer/overview").status_code == 401


def test_developer_overview_is_admin_only(
    client: TestClient,
    auth_header: Callable[..., dict[str, str]],
) -> None:
    admin = client.get("/api/v1/developer/overview", headers=auth_header("admin", "admin123"))
    operator = client.get(
        "/api/v1/developer/overview", headers=auth_header("operator", "operator123")
    )
    viewer = client.get("/api/v1/developer/overview", headers=auth_header("viewer", "viewer123"))
    assert admin.status_code == 200
    assert operator.status_code == 403
    assert viewer.status_code == 403
    body = admin.json()
    assert body["project"]["application_version"] == "1.0.0-rc3"
    assert body["project"]["current_sprint"] == "11.5"
    assert body["project"]["current_phase"] == 11
    assert body["tests"]["backend_tests"] == "unknown"
    assert body["build"]["build_status"] == "unknown"
    assert 0 <= body["health"]["overall_health"] <= 100
    assert body["statistics"]["rest_apis"] > 0
    assert body["statistics"]["database_tables"] > 0
    assert "state" in body["agent_service"]
    assert body["agent_service"]["state"] in {"running", "stopped", "restarting", "unknown"}
    assert len(body["progress"]["phases"]) == 11


def test_developer_git_unavailable(
    client: TestClient,
    auth_header: Callable[..., dict[str, str]],
    monkeypatch,
) -> None:
    monkeypatch.setattr(developer_router.service, "_git", lambda *_args, **_kwargs: None)
    body = client.get("/api/v1/developer/overview", headers=auth_header()).json()
    git = body["project"]["git"]
    assert git["branch"] is None
    assert git["commit"] is None
    assert git["dirty"] is None
    assert git["ahead_count"] is None


def test_developer_empty_activity(
    client: TestClient,
    auth_header: Callable[..., dict[str, str]],
) -> None:
    _reset()
    body = client.get("/api/v1/developer/overview", headers=auth_header()).json()
    assert body["activity"] == []


def test_developer_unknown_build_metadata(
    client: TestClient,
    auth_header: Callable[..., dict[str, str]],
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(developer_router.service, "metadata_path", tmp_path / "missing.json")
    body = client.get("/api/v1/developer/overview", headers=auth_header()).json()
    assert body["build"]["last_build"] is None
    assert body["build"]["backend"] == "unknown"
    assert body["tests"]["qa"] == "unknown"


def test_developer_activity_newest_first(
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
                    observed_at=now,
                    payload={"indexed_photos": 12, "storage_used": 100},
                ),
                OpsSnapshot(
                    kind="backup",
                    observed_at=now,
                    payload={"backup_status": "success"},
                ),
            ]
        )
        db.commit()
    body = client.get("/api/v1/developer/overview", headers=auth_header()).json()
    assert len(body["activity"]) == 2
    assert body["activity"][0]["timestamp"] >= body["activity"][1]["timestamp"]
    assert body["statistics"]["photos"] == 12
    assert "Mission Control" in body["progress"]["roadmap"]


def test_developer_service_does_not_raise_without_git() -> None:
    service = DeveloperDashboardService()
    status = service._git_status()
    assert status.branch is None or isinstance(status.branch, str)
