from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from homelab_monitor.settings import get_settings

REGISTRATION_KEY = "test-registration-key-at-least-24-chars"


def register_agent(
    client: TestClient,
    name: str,
    capabilities: list[str] | None = None,
) -> tuple[str, str]:
    response = client.post(
        "/api/v1/agents/register",
        headers={"X-Registration-Key": REGISTRATION_KEY},
        json={
            "name": name,
            "hostname": f"{name}.local",
            "version": "0.1.0",
            "capabilities": capabilities or ["ubuntu"],
        },
    )
    assert response.status_code == 201
    body = response.json()
    return body["agent_id"], body["agent_token"]


def upload_report(
    client: TestClient,
    token: str,
    report_id: str,
    observed_at: str,
    cpu_percent: float,
) -> None:
    response = client.post(
        "/api/v1/agent/reports",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "report_id": report_id,
            "schema_version": "1.0",
            "observed_at": observed_at,
            "config_revision": 1,
            "modules": [
                {
                    "module": "system",
                    "status": "healthy",
                    "summary": "System operating normally",
                    "metrics": {"cpu": {"usage_percent": cpu_percent}},
                    "diagnostics": {},
                }
            ],
        },
    )
    assert response.status_code == 200


def test_dashboard_overview_and_agent_list(
    client: TestClient,
    auth_header: Callable[..., dict[str, str]],
) -> None:
    online_id, online_token = register_agent(client, "dashboard-online")
    register_agent(client, "dashboard-offline")
    check_in = client.post(
        "/api/v1/agent/check-ins",
        headers={"Authorization": f"Bearer {online_token}"},
        json={
            "version": "0.1.0",
            "observed_at": "2026-09-07T06:00:00Z",
            "config_revision": 1,
        },
    )
    assert check_in.status_code == 200

    agents_response = client.get("/api/v1/agents", headers=auth_header())
    overview_response = client.get("/api/v1/dashboard/overview", headers=auth_header())

    assert agents_response.status_code == 200
    assert overview_response.status_code == 200
    agents = agents_response.json()
    overview = overview_response.json()
    assert [agent["name"] for agent in agents] == sorted(agent["name"] for agent in agents)
    assert overview["agents"]["total"] == len(agents)
    assert overview["agents"]["online"] == sum(agent["status"] == "online" for agent in agents)
    assert overview["agents"]["offline"] == (
        overview["agents"]["total"] - overview["agents"]["online"]
    )
    assert isinstance(overview["reports"]["total"], int)
    assert overview["groups"]["total"] == 0
    assert overview["group_stats"] == []

    listed_agent = next(agent for agent in agents if agent["id"] == online_id)
    assert set(listed_agent) == {
        "id",
        "name",
        "hostname",
        "version",
        "status",
        "last_seen_at",
    }


def test_agent_detail_returns_configuration_and_capabilities(
    client: TestClient,
    auth_header: Callable[..., dict[str, str]],
) -> None:
    agent_id, _ = register_agent(
        client,
        "dashboard-detail",
        capabilities=["ubuntu", "docker"],
    )

    response = client.get(f"/api/v1/agents/{agent_id}", headers=auth_header())

    assert response.status_code == 200
    assert response.json() == {
        "id": agent_id,
        "name": "dashboard-detail",
        "hostname": "dashboard-detail.local",
        "version": "0.1.0",
        "status": "registered",
        "last_seen_at": None,
        "configuration_revision": 1,
        "capabilities": ["docker", "ubuntu"],
    }


def test_latest_report_uses_observation_time(
    client: TestClient,
    auth_header: Callable[..., dict[str, str]],
) -> None:
    agent_id, token = register_agent(client, "dashboard-reports")
    upload_report(
        client,
        token,
        "dashboard-newer-report",
        "2026-09-07T07:00:00Z",
        20.0,
    )
    upload_report(
        client,
        token,
        "dashboard-older-report",
        "2026-09-07T06:00:00Z",
        10.0,
    )

    response = client.get(
        f"/api/v1/agents/{agent_id}/latest-report",
        headers=auth_header(),
    )

    assert response.status_code == 200
    assert response.json()["agent_id"] == agent_id
    assert response.json()["report_id"] == "dashboard-newer-report"
    assert response.json()["payload"]["modules"][0]["metrics"]["cpu"]["usage_percent"] == 20.0


def test_dashboard_agent_not_found_responses(
    client: TestClient,
    auth_header: Callable[..., dict[str, str]],
) -> None:
    headers = auth_header()
    detail = client.get("/api/v1/agents/missing-agent", headers=headers)
    latest = client.get("/api/v1/agents/missing-agent/latest-report", headers=headers)

    assert detail.status_code == 404
    assert detail.json()["error"]["code"] == "agent_not_found"
    assert latest.status_code == 404
    assert latest.json()["error"]["code"] == "agent_not_found"


def test_latest_report_not_found_for_registered_agent(
    client: TestClient,
    auth_header: Callable[..., dict[str, str]],
) -> None:
    agent_id, _ = register_agent(client, "dashboard-no-reports")

    response = client.get(
        f"/api/v1/agents/{agent_id}/latest-report",
        headers=auth_header(),
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "latest_report_not_found"


def test_dashboard_routes_are_documented_in_openapi(client: TestClient) -> None:
    paths = client.get("/openapi.json").json()["paths"]

    assert "/api/v1/auth/login" in paths
    assert "/api/v1/auth/me" in paths
    assert "/api/v1/dashboard/overview" in paths
    assert "/api/v1/agents" in paths
    assert "/api/v1/agents/{agent_id}" in paths
    assert "/api/v1/agents/{agent_id}/latest-report" in paths
    assert "/api/v1/agents/{agent_id}/reports" in paths
    assert "/api/v1/alerts/active" in paths
    assert "/api/v1/alerts/history" in paths
    assert "/api/v1/alerts/statistics" in paths
    assert "/api/v1/alerts/{alert_id}/acknowledge" in paths
    assert "/api/v1/users" in paths
    assert "/api/v1/users/{user_id}" in paths
    assert "/api/v1/users/{user_id}/password" in paths
    assert "/api/v1/users/{user_id}/status" in paths
    assert "/api/v1/groups" in paths
    assert "/api/v1/groups/summary" in paths
    assert "/api/v1/groups/{group_id}" in paths
    assert "/api/v1/groups/{group_id}/agents" in paths
    assert "/api/v1/groups/{group_id}/agents/{agent_id}" in paths
    assert "/api/v1/history/agents/{agent_id}" in paths
    assert "/api/v1/history/agents/{agent_id}/export" in paths
    assert "/api/v1/notifications" in paths
    assert "/api/v1/notifications/history" in paths
    assert "/api/v1/notifications/delivery-history" in paths
    assert "/api/v1/notifications/metrics" in paths
    assert "/api/v1/notifications/statistics" in paths
    assert "/api/v1/notifications/{notification_id}" in paths
    assert "/api/v1/notifications/test" in paths
    assert "/api/v1/notifications/test-report" in paths
    assert "/api/v1/notifications/{notification_id}/retry" in paths
    assert "/api/v1/settings/notifications" in paths
    assert "/api/v1/alert-rules" in paths
    assert "/api/v1/alert-rules/{rule_id}" in paths
    assert "/api/v1/alert-rules/{rule_id}/enable" in paths
    assert "/api/v1/infrastructure" in paths
    assert "/api/v1/infrastructure/{service}" in paths
    assert "/api/v1/photo-services" in paths
    assert "/api/v1/photos" in paths
    assert "/api/v1/photos/latest" in paths
    assert "/api/v1/photos/stats" in paths
    assert "/api/v1/photos/settings" in paths
    assert "/api/v1/backup" in paths
    assert "/api/v1/incidents" in paths
    assert "/api/v1/incidents/statistics" in paths
    assert "/api/v1/incidents/{incident_id}" in paths
    assert "/api/v1/predictions/overview" in paths
    assert "/api/v1/predictions/storage" in paths
    assert "/api/v1/predictions/system" in paths
    assert "/api/v1/predictions/photos" in paths
    assert "/api/v1/predictions/backup" in paths
    assert "/api/v1/system/remote-access" in paths


def test_agent_report_history_returns_newest_reports_first(
    client: TestClient,
    auth_header: Callable[..., dict[str, str]],
) -> None:
    agent_id, token = register_agent(client, "dashboard-history")
    upload_report(
        client,
        token,
        "history-oldest",
        "2026-09-07T05:00:00Z",
        10.0,
    )
    upload_report(
        client,
        token,
        "history-newest",
        "2026-09-07T07:00:00Z",
        30.0,
    )
    upload_report(
        client,
        token,
        "history-middle",
        "2026-09-07T06:00:00Z",
        20.0,
    )

    response = client.get(
        f"/api/v1/agents/{agent_id}/reports",
        params={"limit": 2},
        headers=auth_header(),
    )

    assert response.status_code == 200
    assert [report["report_id"] for report in response.json()] == [
        "history-newest",
        "history-middle",
    ]


def test_agent_report_history_validates_agent_and_limit(
    client: TestClient,
    auth_header: Callable[..., dict[str, str]],
) -> None:
    headers = auth_header()
    missing = client.get("/api/v1/agents/missing-agent/reports", headers=headers)
    invalid_limit = client.get(
        "/api/v1/agents/missing-agent/reports",
        params={"limit": 1},
        headers=headers,
    )

    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "agent_not_found"
    assert invalid_limit.status_code == 422


def test_active_alerts_include_agent_context(
    client: TestClient,
    auth_header: Callable[..., dict[str, str]],
) -> None:
    agent_id, token = register_agent(client, "dashboard-active-alert")
    start = datetime(2026, 9, 7, 8, 0, tzinfo=UTC)
    upload_report(
        client,
        token,
        "dashboard-alert-report",
        start.isoformat().replace("+00:00", "Z"),
        100.0,
    )
    upload_report(
        client,
        token,
        "dashboard-alert-report-held",
        (start + timedelta(minutes=2)).isoformat().replace("+00:00", "Z"),
        100.0,
    )

    response = client.get("/api/v1/alerts/active", headers=auth_header())

    assert response.status_code == 200
    alert = next(item for item in response.json() if item["agent_id"] == agent_id)
    assert alert["agent_name"] == "dashboard-active-alert"
    assert alert["kind"] == "cpu_high"
    assert alert["severity"] == "critical"
    assert alert["current_value"] == 100
    assert alert["threshold"] == get_settings().alert_cpu_threshold_percent
