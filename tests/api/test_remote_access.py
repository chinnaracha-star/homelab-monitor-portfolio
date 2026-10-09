from collections.abc import Callable
from typing import Any

from fastapi.testclient import TestClient

from homelab_monitor.remote_access import RemoteAccessService
from homelab_monitor.routers import system as system_router
from homelab_monitor.schemas import RemoteAccessResponse

CONNECTED_STATUS = {
    "BackendState": "Running",
    "Self": {
        "DNSName": "monitor.example.com.",
        "Online": True,
        "TailscaleIPs": ["100.64.0.12", "fd7a:115c:a1e0::12"],
    },
    "CertDomains": ["monitor.example.com"],
}

DISCONNECTED_STATUS = {
    "BackendState": "Stopped",
    "Self": {
        "DNSName": "monitor.example.com.",
        "Online": False,
        "TailscaleIPs": ["100.64.0.12"],
    },
}

SERVE_HTTPS = {
    "TCP": {"443": {"HTTPS": True}},
    "Web": {
        "monitor.example.com:443": {
            "Handlers": {"/": {"Proxy": "http://127.0.0.1:18081"}}
        }
    },
    "AllowFunnel": {"monitor.example.com:443": False},
}

SERVE_HTTP_ONLY = {
    "TCP": {"80": {"HTTP": True}},
    "Web": {
        "monitor.example.com:80": {
            "Handlers": {"/": {"Proxy": "http://127.0.0.1:18081"}}
        }
    },
    "AllowFunnel": {},
}


def _cli(
    status: dict[str, Any] | None,
    serve: dict[str, Any] | None,
    *,
    missing: bool = False,
) -> Callable[[list[str]], tuple[int, str]]:
    def run(args: list[str]) -> tuple[int, str]:
        if missing:
            raise FileNotFoundError("tailscale")
        import json

        if args[:2] == ["status", "--json"]:
            if status is None:
                return 1, ""
            return 0, json.dumps(status)
        if args[:3] == ["serve", "status", "--json"] or args[:2] == ["serve", "status"]:
            if serve is None:
                return 1, ""
            return 0, json.dumps(serve)
        return 1, ""

    return run


def test_remote_access_requires_jwt(client: TestClient) -> None:
    assert client.get("/api/v1/system/remote-access").status_code == 401


def test_remote_access_rbac_allows_all_roles(
    client: TestClient,
    auth_header: Callable[..., dict[str, str]],
) -> None:
    for username, password in (
        ("admin", "admin123"),
        ("operator", "operator123"),
        ("viewer", "viewer123"),
    ):
        response = client.get(
            "/api/v1/system/remote-access",
            headers=auth_header(username, password),
        )
        assert response.status_code == 200


def test_remote_access_not_installed(
    client: TestClient,
    auth_header: Callable[..., dict[str, str]],
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        system_router,
        "service",
        RemoteAccessService(
            run=_cli(None, None, missing=True),
            binary_available=lambda _path: False,
            socket_exists=lambda _path: False,
        ),
    )
    body = client.get("/api/v1/system/remote-access", headers=auth_header()).json()
    assert body["status"] == "not_installed"
    assert body["enabled"] is False
    assert body["provider"] == "tailscale"
    assert body["https"] is False
    assert body["serve_enabled"] is False
    assert body["funnel_enabled"] is False
    assert body["public"] is False
    assert body["hostname"] is None
    assert body["tailnet_ip"] is None


def test_remote_access_connected_serve_https(
    client: TestClient,
    auth_header: Callable[..., dict[str, str]],
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        system_router,
        "service",
        RemoteAccessService(
            run=_cli(CONNECTED_STATUS, SERVE_HTTPS),
            binary_available=lambda _path: True,
            socket_exists=lambda _path: False,
        ),
    )
    body = client.get("/api/v1/system/remote-access", headers=auth_header()).json()
    assert body == {
        "enabled": True,
        "provider": "tailscale",
        "hostname": "monitor.example.com",
        "tailnet_ip": "100.64.0.12",
        "https": True,
        "serve_enabled": True,
        "funnel_enabled": False,
        "public": False,
        "status": "connected",
    }


def test_remote_access_disconnected(
    client: TestClient,
    auth_header: Callable[..., dict[str, str]],
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        system_router,
        "service",
        RemoteAccessService(
            run=_cli(DISCONNECTED_STATUS, None),
            binary_available=lambda _path: True,
            socket_exists=lambda _path: False,
        ),
    )
    body = client.get("/api/v1/system/remote-access", headers=auth_header()).json()
    assert body["status"] == "disconnected"
    assert body["enabled"] is False
    assert body["tailnet_ip"] == "100.64.0.12"


def test_remote_access_serve_disabled(
    client: TestClient,
    auth_header: Callable[..., dict[str, str]],
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        system_router,
        "service",
        RemoteAccessService(
            run=_cli(CONNECTED_STATUS, {}),
            binary_available=lambda _path: True,
            socket_exists=lambda _path: False,
        ),
    )
    body = client.get("/api/v1/system/remote-access", headers=auth_header()).json()
    assert body["status"] == "connected"
    assert body["serve_enabled"] is False
    assert body["https"] is True
    assert body["funnel_enabled"] is False


def test_remote_access_https_disabled_when_serve_http_only(
    monkeypatch,
) -> None:
    service = RemoteAccessService(
        run=_cli({**CONNECTED_STATUS, "CertDomains": []}, SERVE_HTTP_ONLY),
        binary_available=lambda _path: True,
        socket_exists=lambda _path: False,
    )
    snapshot = service.snapshot()
    assert snapshot.serve_enabled is True
    assert snapshot.https is False
    assert snapshot.status == "connected"


def test_remote_access_funnel_is_detected_read_only() -> None:
    funnel = {
        **SERVE_HTTPS,
        "AllowFunnel": {"monitor.example.com:443": True},
    }
    snapshot = RemoteAccessService(
        run=_cli(CONNECTED_STATUS, funnel),
        binary_available=lambda _path: True,
        socket_exists=lambda _path: False,
    ).snapshot()
    assert snapshot.funnel_enabled is True
    assert snapshot.public is True
    assert snapshot.serve_enabled is True


def test_remote_access_never_raises_on_unknown_errors() -> None:
    def boom(_args: list[str]) -> tuple[int, str]:
        raise RuntimeError("unexpected")

    snapshot = RemoteAccessService(
        run=boom,
        binary_available=lambda _path: True,
        socket_exists=lambda _path: False,
    ).snapshot()
    assert snapshot == RemoteAccessResponse(status="unknown")
