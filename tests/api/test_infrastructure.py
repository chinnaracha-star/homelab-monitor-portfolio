from collections.abc import Callable

from fastapi.testclient import TestClient

SERVICES = ("qnap", "docker", "immich", "qumagie", "backup")


def test_infrastructure_requires_jwt(client: TestClient) -> None:
    assert client.get("/api/v1/infrastructure").status_code == 401
    assert client.get("/api/v1/infrastructure/qnap").status_code == 401


def test_all_roles_can_read_infrastructure(
    client: TestClient,
    auth_header: Callable[..., dict[str, str]],
) -> None:
    for username, password in (
        ("admin", "admin123"),
        ("operator", "operator123"),
        ("viewer", "viewer123"),
    ):
        headers = auth_header(username, password)
        listed = client.get("/api/v1/infrastructure", headers=headers)
        assert listed.status_code == 200
        body = listed.json()
        names = [item["service"] for item in body["services"]]
        assert names == list(SERVICES)
        for item in body["services"]:
            assert item["status"] in {"healthy", "degraded", "unhealthy", "unknown"}
            assert "version" in item
            assert "updated_at" in item
            assert isinstance(item["summary"], dict)


def test_infrastructure_service_endpoints(
    client: TestClient,
    auth_header: Callable[..., dict[str, str]],
) -> None:
    headers = auth_header()
    for service in SERVICES:
        response = client.get(f"/api/v1/infrastructure/{service}", headers=headers)
        assert response.status_code == 200
        assert response.json()["service"] == service
        assert response.json()["status"] == "healthy"

    missing = client.get("/api/v1/infrastructure/nas", headers=headers)
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "infrastructure_service_not_found"


def test_qnap_and_backup_summaries(
    client: TestClient,
    auth_header: Callable[..., dict[str, str]],
) -> None:
    qnap = client.get("/api/v1/infrastructure/qnap", headers=auth_header()).json()
    assert qnap["summary"]["hostname"] == "qnap-lab-01"
    assert "storage_used_percent" in qnap["summary"]
    backup = client.get("/api/v1/infrastructure/backup", headers=auth_header()).json()
    assert backup["summary"]["destination"] == "s3://homelab-backups"
    assert backup["summary"]["backup_status"] == "success"
