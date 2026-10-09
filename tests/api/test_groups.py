from collections.abc import Callable

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from homelab_monitor.database import get_engine
from homelab_monitor.models import Agent, AgentGroup

REGISTRATION_KEY = "test-registration-key-at-least-24-chars"


def _register_agent(client: TestClient, name: str) -> tuple[str, str]:
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
    body = response.json()
    return str(body["agent_id"]), str(body["agent_token"])


def _create_group(
    client: TestClient,
    auth_header: Callable[..., dict[str, str]],
    name: str = "Rack A",
    description: str = "Primary rack",
) -> dict[str, object]:
    response = client.post(
        "/api/v1/groups",
        headers=auth_header(),
        json={"name": name, "description": description},
    )
    assert response.status_code == 201
    return response.json()


def test_group_crud_and_summary(
    client: TestClient,
    auth_header: Callable[..., dict[str, str]],
) -> None:
    created = _create_group(client, auth_header)
    group_id = str(created["id"])
    assert created["name"] == "Rack A"
    assert created["agents"] == 0
    assert created["online"] == 0
    assert created["members"] == []

    listed = client.get("/api/v1/groups", headers=auth_header("viewer", "viewer123"))
    assert listed.status_code == 200
    assert listed.json()[0]["id"] == group_id

    summary = client.get("/api/v1/groups/summary", headers=auth_header())
    assert summary.status_code == 200
    body = summary.json()
    assert body["total"] == 1
    assert body["groups"][0]["name"] == "Rack A"

    updated = client.put(
        f"/api/v1/groups/{group_id}",
        headers=auth_header("operator", "operator123"),
        json={"name": "Rack B", "description": "Moved"},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Rack B"

    deleted = client.delete(f"/api/v1/groups/{group_id}", headers=auth_header())
    assert deleted.status_code == 204
    missing = client.get(f"/api/v1/groups/{group_id}", headers=auth_header())
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "group_not_found"


def test_assign_and_remove_agents(
    client: TestClient,
    auth_header: Callable[..., dict[str, str]],
) -> None:
    group_id = str(_create_group(client, auth_header, name="LAN")["id"])
    first_id, first_token = _register_agent(client, "group-agent-one")
    second_id, _ = _register_agent(client, "group-agent-two")
    client.post(
        "/api/v1/agent/check-ins",
        headers={"Authorization": f"Bearer {first_token}"},
        json={"version": "0.1.0", "observed_at": "2026-09-07T12:00:00Z", "config_revision": 0},
    )

    assigned = client.post(
        f"/api/v1/groups/{group_id}/agents",
        headers=auth_header(),
        json={"agent_ids": [first_id, second_id, first_id]},
    )
    assert assigned.status_code == 200
    detail = assigned.json()
    assert detail["agents"] == 2
    assert detail["online"] == 1
    assert {member["id"] for member in detail["members"]} == {first_id, second_id}

    overview = client.get("/api/v1/dashboard/overview", headers=auth_header())
    assert overview.status_code == 200
    payload = overview.json()
    assert payload["groups"]["total"] == 1
    assert payload["group_stats"][0] == {
        "id": group_id,
        "name": "LAN",
        "agents": 2,
        "online": 1,
    }

    removed = client.delete(
        f"/api/v1/groups/{group_id}/agents/{second_id}",
        headers=auth_header(),
    )
    assert removed.status_code == 200
    assert removed.json()["agents"] == 1
    assert removed.json()["agent_ids"] == [first_id]

    client.delete(f"/api/v1/groups/{group_id}", headers=auth_header())
    with Session(get_engine()) as db:
        assert db.scalar(select(Agent).where(Agent.id == first_id)) is not None
        assert db.scalar(select(AgentGroup).where(AgentGroup.id == group_id)) is None


def test_group_name_must_be_unique(
    client: TestClient,
    auth_header: Callable[..., dict[str, str]],
) -> None:
    _create_group(client, auth_header, name="Shared")
    duplicate = client.post(
        "/api/v1/groups",
        headers=auth_header(),
        json={"name": "Shared", "description": ""},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "group_name_exists"


def test_assign_unknown_agent_returns_404(
    client: TestClient,
    auth_header: Callable[..., dict[str, str]],
) -> None:
    group_id = str(_create_group(client, auth_header, name="Empty")["id"])
    response = client.post(
        f"/api/v1/groups/{group_id}/agents",
        headers=auth_header(),
        json={"agent_ids": ["missing-agent"]},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "agent_not_found"


def test_viewer_cannot_mutate_groups(
    client: TestClient,
    auth_header: Callable[..., dict[str, str]],
) -> None:
    created = client.post(
        "/api/v1/groups",
        headers=auth_header("viewer", "viewer123"),
        json={"name": "Denied", "description": ""},
    )
    assert created.status_code == 403
    assert created.json()["error"]["code"] == "permission_denied"

    group_id = str(_create_group(client, auth_header, name="Writable")["id"])
    listed = client.get("/api/v1/groups", headers=auth_header("viewer", "viewer123"))
    assert listed.status_code == 200
    summary = client.get("/api/v1/groups/summary", headers=auth_header("viewer", "viewer123"))
    assert summary.status_code == 200
    mutated = client.delete(
        f"/api/v1/groups/{group_id}",
        headers=auth_header("viewer", "viewer123"),
    )
    assert mutated.status_code == 403


def test_groups_require_jwt(client: TestClient) -> None:
    assert client.get("/api/v1/groups").status_code == 401
    assert client.get("/api/v1/groups/summary").status_code == 401
    assert client.get("/api/v1/groups/missing").status_code == 401
    created = client.post("/api/v1/groups", json={"name": "Rack", "description": ""})
    assert created.status_code == 401


def test_invalid_group_payload_is_rejected(
    client: TestClient,
    auth_header: Callable[..., dict[str, str]],
) -> None:
    invalid_name = client.post(
        "/api/v1/groups",
        headers=auth_header(),
        json={"name": "!!!", "description": ""},
    )
    assert invalid_name.status_code == 422

    empty_members = client.post(
        "/api/v1/groups/not-a-group/agents",
        headers=auth_header(),
        json={"agent_ids": []},
    )
    assert empty_members.status_code == 422


def test_remove_unknown_member_returns_404(
    client: TestClient,
    auth_header: Callable[..., dict[str, str]],
) -> None:
    group_id = str(_create_group(client, auth_header, name="Solo")["id"])
    agent_id, _ = _register_agent(client, "unassigned-agent")
    response = client.delete(
        f"/api/v1/groups/{group_id}/agents/{agent_id}",
        headers=auth_header(),
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "group_member_not_found"
