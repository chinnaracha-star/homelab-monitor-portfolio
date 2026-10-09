from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from homelab_monitor.realtime import hub

REGISTRATION_KEY = "test-registration-key-at-least-24-chars"


def register_agent(client: TestClient, name: str) -> dict[str, object]:
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
    return response.json()


def test_dashboard_websocket_requires_jwt(client: TestClient) -> None:
    with (
        pytest.raises(WebSocketDisconnect) as exc_info,
        client.websocket_connect("/api/v1/ws/dashboard"),
    ):
        pass
    assert exc_info.value.code == 4401


def test_dashboard_websocket_rejects_invalid_jwt(client: TestClient) -> None:
    with (
        pytest.raises(WebSocketDisconnect) as exc_info,
        client.websocket_connect("/api/v1/ws/dashboard?token=not-a-jwt"),
    ):
        pass
    assert exc_info.value.code == 4401


def test_dashboard_websocket_connects_with_jwt(
    client: TestClient,
    login: Callable[..., str],
) -> None:
    token = login()
    with client.websocket_connect(f"/api/v1/ws/dashboard?token={token}") as websocket:
        message = websocket.receive_json()
        assert message["type"] == "connection"
        assert message["payload"]["status"] == "connected"
        assert "timestamp" in message
        assert hub.manager.client_count == 1
    assert hub.manager.client_count == 0


def test_dashboard_websocket_broadcasts_check_in(
    client: TestClient,
    login: Callable[..., str],
) -> None:
    dashboard_token = login()
    registration = register_agent(client, "realtime-agent")
    agent_token = str(registration["agent_token"])

    with client.websocket_connect(
        "/api/v1/ws/dashboard",
        headers={"Authorization": f"Bearer {dashboard_token}"},
    ) as websocket:
        assert websocket.receive_json()["type"] == "connection"
        check_in = client.post(
            "/api/v1/agent/check-ins",
            headers={"Authorization": f"Bearer {agent_token}"},
            json={
                "version": "0.1.0",
                "observed_at": "2026-09-07T14:00:00Z",
                "config_revision": 0,
            },
        )
        assert check_in.status_code == 200

        types = {websocket.receive_json()["type"] for _ in range(3)}
        assert types == {"overview_updated", "agent_updated", "alert_updated"}
