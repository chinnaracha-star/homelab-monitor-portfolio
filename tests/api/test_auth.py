from collections.abc import Callable
from datetime import timedelta

from fastapi.testclient import TestClient

from homelab_monitor.auth.passwords import hash_password, verify_password
from homelab_monitor.auth.tokens import create_access_token, decode_access_token
from homelab_monitor.errors import APIError
from homelab_monitor.settings import get_settings


def test_password_hashing_never_stores_plaintext() -> None:
    hashed = hash_password("admin123")
    assert hashed != "admin123"
    assert hashed.startswith("$2")
    assert verify_password("admin123", hashed)
    assert not verify_password("wrong-password", hashed)


def test_jwt_generation_and_validation() -> None:
    settings = get_settings()
    token = create_access_token(
        settings,
        subject="admin",
        user_id="user-1",
        role="admin",
    )
    payload = decode_access_token(settings, token)
    assert payload["sub"] == "admin"
    assert payload["uid"] == "user-1"
    assert payload["role"] == "admin"


def test_jwt_rejects_invalid_and_expired_tokens() -> None:
    settings = get_settings()
    expired = create_access_token(
        settings,
        subject="admin",
        user_id="user-1",
        role="admin",
        expires_delta=timedelta(seconds=-1),
    )
    try:
        decode_access_token(settings, expired)
        raise AssertionError("expired token should be rejected")
    except APIError as error:
        assert error.status_code == 401
        assert error.code == "token_expired"

    try:
        decode_access_token(settings, "not-a-valid-token")
        raise AssertionError("invalid token should be rejected")
    except APIError as error:
        assert error.status_code == 401
        assert error.code == "invalid_token"


def test_login_success(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "admin123"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == get_settings().jwt_expire_minutes * 60
    assert body["access_token"]


def test_login_failure(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "wrong-password"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"


def test_current_user_and_expired_token(
    client: TestClient,
    login: Callable[..., str],
) -> None:
    token = login()
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json() == {
        "id": me.json()["id"],
        "username": "admin",
        "full_name": "Administrator",
        "role": "admin",
        "is_active": True,
    }

    expired = create_access_token(
        get_settings(),
        subject="admin",
        user_id=me.json()["id"],
        role="admin",
        expires_delta=timedelta(seconds=-1),
    )
    expired_response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {expired}"},
    )
    assert expired_response.status_code == 401
    assert expired_response.json()["error"]["code"] == "token_expired"


def test_protected_endpoints_require_auth(client: TestClient) -> None:
    assert client.get("/health").status_code == 200
    assert client.get("/api/v1/dashboard/overview").status_code == 401
    assert client.get("/api/v1/agents").status_code == 401
    assert client.get("/api/v1/alerts/active").status_code == 401


def test_admin_and_viewer_can_read_dashboard(
    client: TestClient,
    auth_header: Callable[..., dict[str, str]],
) -> None:
    admin = client.get(
        "/api/v1/dashboard/overview",
        headers=auth_header("admin", "admin123"),
    )
    viewer = client.get(
        "/api/v1/dashboard/overview",
        headers=auth_header("viewer", "viewer123"),
    )
    operator = client.get(
        "/api/v1/alerts/active",
        headers=auth_header("operator", "operator123"),
    )
    assert admin.status_code == 200
    assert viewer.status_code == 200
    assert operator.status_code == 200
    assert admin.json()["agents"]["total"] == viewer.json()["agents"]["total"]
