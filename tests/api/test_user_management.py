from collections.abc import Callable

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from homelab_monitor.auth.passwords import verify_password
from homelab_monitor.database import get_engine
from homelab_monitor.models import User


def _create_user(
    client: TestClient,
    auth_header: Callable[..., dict[str, str]],
    username: str = "newuser",
) -> dict[str, object]:
    response = client.post(
        "/api/v1/users",
        headers=auth_header("admin", "admin123"),
        json={
            "username": username,
            "full_name": "New User",
            "password": "password123",
            "role": "viewer",
            "is_active": True,
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert "password_hash" not in body
    return body


def test_create_user(client: TestClient, auth_header: Callable[..., dict[str, str]]) -> None:
    body = _create_user(client, auth_header)
    assert body["username"] == "newuser"
    assert body["full_name"] == "New User"
    assert body["role"] == "viewer"
    assert body["is_active"] is True


def test_duplicate_username_is_rejected(
    client: TestClient,
    auth_header: Callable[..., dict[str, str]],
) -> None:
    _create_user(client, auth_header, "duplicate")
    response = client.post(
        "/api/v1/users",
        headers=auth_header("admin", "admin123"),
        json={
            "username": "duplicate",
            "full_name": "Someone Else",
            "password": "password123",
            "role": "operator",
            "is_active": True,
        },
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "username_taken"


def test_update_user(client: TestClient, auth_header: Callable[..., dict[str, str]]) -> None:
    created = _create_user(client, auth_header, "editable")
    response = client.put(
        f"/api/v1/users/{created['id']}",
        headers=auth_header("admin", "admin123"),
        json={"full_name": "Edited Name", "role": "operator", "is_active": True},
    )
    assert response.status_code == 200
    assert response.json()["full_name"] == "Edited Name"
    assert response.json()["role"] == "operator"
    assert "password_hash" not in response.json()


def test_delete_user(client: TestClient, auth_header: Callable[..., dict[str, str]]) -> None:
    created = _create_user(client, auth_header, "deletable")
    response = client.delete(
        f"/api/v1/users/{created['id']}",
        headers=auth_header("admin", "admin123"),
    )
    assert response.status_code == 204
    remaining = client.get("/api/v1/users", headers=auth_header("admin", "admin123"))
    assert all(user["username"] != "deletable" for user in remaining.json())


def test_cannot_delete_self(
    client: TestClient,
    auth_header: Callable[..., dict[str, str]],
) -> None:
    me = client.get("/api/v1/auth/me", headers=auth_header("admin", "admin123"))
    response = client.delete(
        f"/api/v1/users/{me.json()['id']}",
        headers=auth_header("admin", "admin123"),
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "cannot_delete_self"


def test_cannot_disable_self(
    client: TestClient,
    auth_header: Callable[..., dict[str, str]],
) -> None:
    me = client.get("/api/v1/auth/me", headers=auth_header("admin", "admin123"))
    response = client.patch(
        f"/api/v1/users/{me.json()['id']}/status",
        headers=auth_header("admin", "admin123"),
        json={"is_active": False},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "cannot_disable_self"


def test_cannot_remove_last_admin(
    client: TestClient,
    auth_header: Callable[..., dict[str, str]],
) -> None:
    me = client.get("/api/v1/auth/me", headers=auth_header("admin", "admin123"))
    extra = client.post(
        "/api/v1/users",
        headers=auth_header("admin", "admin123"),
        json={
            "username": "secondadmin",
            "full_name": "Second Admin",
            "password": "password123",
            "role": "admin",
            "is_active": True,
        },
    )
    assert extra.status_code == 201
    assert (
        client.delete(
            f"/api/v1/users/{extra.json()['id']}",
            headers=auth_header("admin", "admin123"),
        ).status_code
        == 204
    )

    demote = client.put(
        f"/api/v1/users/{me.json()['id']}",
        headers=auth_header("admin", "admin123"),
        json={"full_name": "Administrator", "role": "viewer", "is_active": True},
    )
    assert demote.status_code == 409
    assert demote.json()["error"]["code"] == "last_active_admin"


def test_password_reset(
    client: TestClient,
    auth_header: Callable[..., dict[str, str]],
) -> None:
    created = _create_user(client, auth_header, "resetme")
    response = client.patch(
        f"/api/v1/users/{created['id']}/password",
        headers=auth_header("admin", "admin123"),
        json={"password": "newpass123"},
    )
    assert response.status_code == 200
    login = client.post(
        "/api/v1/auth/login",
        json={"username": "resetme", "password": "newpass123"},
    )
    assert login.status_code == 200
    with Session(get_engine()) as db:
        user = db.scalar(select(User).where(User.username == "resetme"))
        assert user is not None
        assert verify_password("newpass123", user.password_hash)
        assert not verify_password("password123", user.password_hash)


def test_operator_cannot_mutate_users(
    client: TestClient,
    auth_header: Callable[..., dict[str, str]],
) -> None:
    response = client.post(
        "/api/v1/users",
        headers=auth_header("operator", "operator123"),
        json={
            "username": "blocked",
            "full_name": "Blocked",
            "password": "password123",
            "role": "viewer",
            "is_active": True,
        },
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "permission_denied"
