from collections.abc import Callable
from pathlib import Path

from fastapi.testclient import TestClient

from homelab_monitor.operations import catalog
from homelab_monitor.settings import get_settings


def test_operations_require_auth(client: TestClient) -> None:
    assert client.get("/api/v1/operations").status_code == 401
    posted = client.post("/api/v1/operations/health_check/run", json={"confirm": True})
    assert posted.status_code == 401


def test_operations_catalog_and_confirm(
    client: TestClient,
    auth_header: Callable[..., dict[str, str]],
    tmp_path: Path,
    monkeypatch,
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{tmp_path / 'ops.db'}")
    ids = {item["id"] for item in catalog()}
    assert "backup_now" in ids
    listed = client.get("/api/v1/operations", headers=auth_header())
    assert listed.status_code == 200
    denied = client.post(
        "/api/v1/operations/health_check/run",
        headers=auth_header(),
        json={"confirm": False},
    )
    assert denied.status_code == 400
    ok = client.post(
        "/api/v1/operations/health_check/run",
        headers=auth_header(),
        json={"confirm": True},
    )
    assert ok.status_code == 200
    body = ok.json()
    assert body["status"] in {"success", "failed"}
    history = client.get("/api/v1/operations/history", headers=auth_header())
    assert history.status_code == 200
    assert history.json()


def test_viewer_cannot_run_operations(
    client: TestClient,
    auth_header: Callable[..., dict[str, str]],
) -> None:
    response = client.get("/api/v1/operations", headers=auth_header("viewer", "viewer123"))
    assert response.status_code == 403
