from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from httpx import Response

from homelab_monitor.auth.dependencies import PERMISSION_DENIED_MESSAGE

REGISTRATION_KEY = "test-registration-key-at-least-24-chars"


def _permission_denied(response: Response) -> None:
    assert response.status_code == 403
    error = response.json()["error"]
    assert error["code"] == "permission_denied"
    assert error["message"] == PERMISSION_DENIED_MESSAGE


def test_all_roles_can_read_dashboard_and_alerts(
    client: TestClient,
    auth_header: Callable[..., dict[str, str]],
) -> None:
    for username, password in (
        ("admin", "admin123"),
        ("operator", "operator123"),
        ("viewer", "viewer123"),
    ):
        headers = auth_header(username, password)
        overview = client.get("/api/v1/dashboard/overview", headers=headers)
        alerts = client.get("/api/v1/alerts/active", headers=headers)
        groups = client.get("/api/v1/groups", headers=headers)
        summary = client.get("/api/v1/groups/summary", headers=headers)
        notifications = client.get("/api/v1/notifications", headers=headers)
        notify_settings = client.get("/api/v1/settings/notifications", headers=headers)
        rules = client.get("/api/v1/alert-rules", headers=headers)
        infrastructure = client.get("/api/v1/infrastructure", headers=headers)
        photos = client.get("/api/v1/photo-services", headers=headers)
        photo_monitor = client.get("/api/v1/photos/stats", headers=headers)
        backup = client.get("/api/v1/backup", headers=headers)
        analytics = client.get("/api/v1/analytics/overview", headers=headers)
        trends = client.get("/api/v1/trends/overview", headers=headers)
        capacity = client.get("/api/v1/capacity/overview", headers=headers)
        insights = client.get("/api/v1/insights/overview", headers=headers)
        history = client.get("/api/v1/alerts/history", headers=headers)
        incidents = client.get("/api/v1/incidents", headers=headers)
        notify_history = client.get("/api/v1/notifications/history", headers=headers)
        predictions = client.get("/api/v1/predictions/overview", headers=headers)
        remote_access = client.get("/api/v1/system/remote-access", headers=headers)
        developer = client.get("/api/v1/developer/overview", headers=headers)
        assert overview.status_code == 200
        assert alerts.status_code == 200
        assert groups.status_code == 200
        assert summary.status_code == 200
        assert notifications.status_code == 200
        assert notify_settings.status_code == 200
        assert rules.status_code == 200
        assert infrastructure.status_code == 200
        assert photos.status_code == 200
        assert photo_monitor.status_code == 200
        assert backup.status_code == 200
        assert analytics.status_code == 200
        assert trends.status_code == 200
        assert capacity.status_code == 200
        assert insights.status_code == 200
        assert history.status_code == 200
        assert incidents.status_code == 200
        assert notify_history.status_code == 200
        assert predictions.status_code == 200
        assert remote_access.status_code == 200
        if username == "admin":
            assert developer.status_code == 200
        else:
            _permission_denied(developer)


def test_admin_is_allowed_to_list_users(
    client: TestClient,
    auth_header: Callable[..., dict[str, str]],
) -> None:
    response = client.get("/api/v1/users", headers=auth_header("admin", "admin123"))
    assert response.status_code == 200
    usernames = [user["username"] for user in response.json()]
    assert usernames == sorted(usernames)
    assert {"admin", "operator", "viewer", "disabled"}.issubset(set(usernames))
    assert all("password_hash" not in user for user in response.json())


def test_operator_and_viewer_are_denied_user_management(
    client: TestClient,
    auth_header: Callable[..., dict[str, str]],
) -> None:
    _permission_denied(client.get("/api/v1/users", headers=auth_header("operator", "operator123")))
    _permission_denied(client.get("/api/v1/users", headers=auth_header("viewer", "viewer123")))


def test_viewer_cannot_acknowledge_alerts(
    client: TestClient,
    auth_header: Callable[..., dict[str, str]],
) -> None:
    _permission_denied(
        client.post(
            "/api/v1/alerts/missing-alert/acknowledge",
            headers=auth_header("viewer", "viewer123"),
        )
    )


def test_operator_and_admin_can_acknowledge_alerts(
    client: TestClient,
    auth_header: Callable[..., dict[str, str]],
) -> None:
    register = client.post(
        "/api/v1/agents/register",
        headers={"X-Registration-Key": REGISTRATION_KEY},
        json={
            "name": "rbac-alert-agent",
            "hostname": "rbac-alert-agent.local",
            "version": "0.1.0",
            "capabilities": ["ubuntu"],
        },
    )
    assert register.status_code == 201
    token = register.json()["agent_token"]
    start = datetime(2026, 9, 7, 9, 0, tzinfo=UTC)
    report_body = {
        "schema_version": "1.0",
        "config_revision": 1,
        "modules": [
            {
                "module": "system",
                "status": "warning",
                "summary": "CPU is high",
                "metrics": {"cpu": {"usage_percent": 100.0}},
                "diagnostics": {},
            }
        ],
    }
    first = client.post(
        "/api/v1/agent/reports",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "report_id": "rbac-alert-report",
            "observed_at": start.isoformat(),
            **report_body,
        },
    )
    report = client.post(
        "/api/v1/agent/reports",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "report_id": "rbac-alert-report-held",
            "observed_at": (start + timedelta(minutes=2)).isoformat(),
            **report_body,
        },
    )
    assert first.status_code == 200
    assert report.status_code == 200
    alerts = client.get(
        "/api/v1/alerts/active",
        headers=auth_header("operator", "operator123"),
    )
    assert alerts.status_code == 200
    alert_id = next(item["id"] for item in alerts.json() if item["kind"] == "cpu_high")

    operator = client.post(
        f"/api/v1/alerts/{alert_id}/acknowledge",
        headers=auth_header("operator", "operator123"),
    )
    admin = client.post(
        f"/api/v1/alerts/{alert_id}/acknowledge",
        headers=auth_header("admin", "admin123"),
    )
    assert operator.status_code == 200
    assert admin.status_code == 200
    assert operator.json()["id"] == alert_id
    assert operator.json()["status"] == "active"
