import json

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from homelab_monitor.routers.health import health

REGISTRATION_KEY = "test-registration-key-at-least-24-chars"


def register_agent(client: TestClient, name: str = "home-server") -> dict[str, object]:
    response = client.post(
        "/api/v1/agents/register",
        headers={"X-Registration-Key": REGISTRATION_KEY},
        json={
            "name": name,
            "hostname": f"{name}.local",
            "version": "0.1.0",
            "capabilities": ["ubuntu", "docker"],
        },
    )
    assert response.status_code == 201
    return response.json()


def test_health_reports_database_status(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
    assert response.json()["database"] == "up"


def test_health_is_degraded_when_migrations_are_missing() -> None:
    engine = create_engine("sqlite://")

    with Session(engine) as session:
        response = health(session)

    assert response.status_code == 503
    assert json.loads(response.body)["status"] == "degraded"
    assert json.loads(response.body)["database"] == "down"


def test_registration_requires_valid_bootstrap_key(client: TestClient) -> None:
    response = client.post(
        "/api/v1/agents/register",
        headers={"X-Registration-Key": "wrong-key"},
        json={
            "name": "unauthorized-agent",
            "hostname": "unauthorized.local",
            "version": "0.1.0",
        },
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_registration_key"


def test_agent_registration_and_check_in(client: TestClient) -> None:
    registration = register_agent(client, "mini-pc")
    token = str(registration["agent_token"])

    assert registration["report_interval_seconds"] == 60
    assert registration["config_revision"] == 1

    check_in = client.post(
        "/api/v1/agent/check-ins",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "version": "0.1.0",
            "observed_at": "2026-09-07T05:00:00Z",
            "config_revision": 0,
        },
    )

    assert check_in.status_code == 200
    control = check_in.json()
    assert control["next_report_in"] == 60
    assert control["config_revision"] == 1
    assert control["configuration"] == {}
    assert control["commands"] == []


def test_report_upload_is_idempotent(client: TestClient) -> None:
    registration = register_agent(client, "idempotent-agent")
    token = str(registration["agent_token"])
    headers = {"Authorization": f"Bearer {token}"}
    report = {
        "report_id": "report-001",
        "schema_version": "1.0",
        "observed_at": "2026-09-07T05:00:00Z",
        "config_revision": 1,
        "modules": [
            {
                "module": "system",
                "status": "healthy",
                "summary": "System resources are within thresholds",
                "metrics": {"cpu_percent": 12.5, "memory_percent": 44.0},
            }
        ],
    }

    first = client.post("/api/v1/agent/reports", headers=headers, json=report)
    duplicate = client.post("/api/v1/agent/reports", headers=headers, json=report)

    assert first.status_code == 200
    assert first.json()["accepted"] is True
    assert first.json()["duplicate"] is False
    assert duplicate.status_code == 200
    assert duplicate.json()["duplicate"] is True

    report["modules"][0]["summary"] = "Changed content"
    conflict = client.post("/api/v1/agent/reports", headers=headers, json=report)
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "report_id_conflict"


def test_agent_endpoint_rejects_unknown_token(client: TestClient) -> None:
    response = client.post(
        "/api/v1/agent/check-ins",
        headers={"Authorization": "Bearer invalid-token"},
        json={
            "version": "0.1.0",
            "observed_at": "2026-09-07T05:00:00Z",
            "config_revision": 0,
        },
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_agent_token"
