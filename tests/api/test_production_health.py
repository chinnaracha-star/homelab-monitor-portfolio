from collections.abc import Callable
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from homelab_monitor.routers import system as system_router
from homelab_monitor.schemas import (
    AgentRuntimeResponse,
    ProductionHealthCheck,
    ProductionHealthResponse,
    ProductionNetworkResponse,
    ProductionRuntimeResponse,
    ProductionStorageResponse,
    TailscaleRuntimeResponse,
    TelegramRuntimeResponse,
)


class StubHealthService:
    def health(self, _db) -> ProductionHealthResponse:
        now = datetime.now(UTC)
        return ProductionHealthResponse(
            generated_at=now,
            score=92,
            status="excellent",
            checks=[
                ProductionHealthCheck(
                    component="API",
                    status="healthy",
                    last_check=now,
                    latency_ms=1.2,
                    message="API process is responding.",
                )
            ],
        )

    def runtime(self, _db) -> ProductionRuntimeResponse:
        return ProductionRuntimeResponse(
            agent=AgentRuntimeResponse(state="running", restart_count=1),
            docker_available=False,
            telegram=TelegramRuntimeResponse(bot_connected=True),
            tailscale=TailscaleRuntimeResponse(
                connected=True,
                tailnet="monitor.example.com",
                remote_access_url="https://monitor.example.com",
            ),
        )

    def storage(self) -> ProductionStorageResponse:
        return ProductionStorageResponse(
            filesystem="/",
            disk_usage_percent=72.5,
            free_space_bytes=1024,
            status="healthy",
        )

    def network(self) -> ProductionNetworkResponse:
        return ProductionNetworkResponse(
            lan_ip="192.168.1.10",
            tailscale_ip="100.64.0.10",
            gateway="192.168.1.1",
            internet="healthy",
            dns="healthy",
        )


def test_production_health_endpoints_require_jwt(client: TestClient) -> None:
    for path in ("health", "runtime", "storage", "network"):
        assert client.get(f"/api/v1/system/{path}").status_code == 401


def test_production_health_contracts(
    client: TestClient,
    auth_header: Callable[..., dict[str, str]],
    monkeypatch,
) -> None:
    monkeypatch.setattr(system_router, "health_service", StubHealthService())
    headers = auth_header()

    health = client.get("/api/v1/system/health", headers=headers)
    runtime = client.get("/api/v1/system/runtime", headers=headers)
    storage = client.get("/api/v1/system/storage", headers=headers)
    network = client.get("/api/v1/system/network", headers=headers)

    assert health.status_code == 200
    assert health.json()["score"] == 92
    assert health.json()["checks"][0]["component"] == "API"
    assert runtime.json()["agent"]["state"] == "running"
    assert runtime.json()["docker_available"] is False
    assert runtime.json()["tailscale"]["connected"] is True
    assert storage.json()["disk_usage_percent"] == 72.5
    assert network.json()["internet"] == "healthy"


def test_production_health_endpoints_allow_read_roles(
    client: TestClient,
    auth_header: Callable[..., dict[str, str]],
    monkeypatch,
) -> None:
    monkeypatch.setattr(system_router, "health_service", StubHealthService())
    for username, password in (("operator", "operator123"), ("viewer", "viewer123")):
        response = client.get(
            "/api/v1/system/health",
            headers=auth_header(username, password),
        )
        assert response.status_code == 200
