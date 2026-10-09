from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import httpx
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from homelab_monitor.connectors.backup import BackupConnector
from homelab_monitor.connectors.base import ConnectorSnapshot
from homelab_monitor.connectors.immich import ImmichConnector
from homelab_monitor.database import get_engine
from homelab_monitor.infrastructure import InfrastructureService
from homelab_monitor.infrastructure_monitor import refresh_infrastructure
from homelab_monitor.models import OpsSnapshot
from homelab_monitor.ops_history import backup_history_periods
from homelab_monitor.realtime import hub


def test_backup_mock_includes_legacy_and_ts253_fields() -> None:
    snapshot = BackupConnector(mock=True).collect()
    assert snapshot.status == "healthy"
    assert snapshot.summary["destination"] == "s3://homelab-backups"
    assert snapshot.summary["backup_status"] == "success"
    assert snapshot.summary["destination_model"] == "TS-253 Pro"
    assert snapshot.summary["progress_percent"] == 43
    assert snapshot.summary["duration_seconds"] == 1080
    assert snapshot.summary["job_status"] == "running"
    assert snapshot.summary["read_only"] is True
    assert BackupConnector(mock=True).health() == "healthy"
    assert BackupConnector(mock=True).version()
    assert "last_backup" in BackupConnector(mock=True).summary()


def test_backup_live_get_only() -> None:
    methods: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        methods.append(request.method)
        assert request.method == "GET"
        if request.url.path.endswith("/api/backup/status"):
            return httpx.Response(
                200,
                json={
                    "version": "HBS-26",
                    "health": "healthy",
                    "job_status": "idle",
                    "job_name": "Nightly copy",
                    "job_type": "replication",
                    "last_backup": "2026-09-08T02:00:00+00:00",
                    "next_backup": "2026-09-09T02:00:00+00:00",
                    "duration_seconds": 1080,
                    "progress_percent": 0,
                    "backup_size_bytes": 100,
                    "destination_name": "qnap-backup-01",
                    "destination_ip": "192.168.1.253",
                    "destination_model": "TS-253 Pro",
                    "backup_status": "success",
                },
            )
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler), timeout=2)
    snapshot = BackupConnector(
        mock=False,
        base_url="https://backup.example",
        client=client,
    ).collect()
    assert snapshot.summary["destination_model"] == "TS-253 Pro"
    assert snapshot.summary["job_name"] == "Nightly copy"
    assert set(methods) == {"GET"}


def test_backup_failure_is_isolated() -> None:
    class Boom(BackupConnector):
        def collect(self):  # type: ignore[no-untyped-def]
            raise RuntimeError("backup nas down")

    service = InfrastructureService([Boom(mock=True), ImmichConnector(mock=True)])
    _collected_at, snapshots = service.snapshot()
    by_name = {item.service: item for item in snapshots}
    assert by_name["backup"].status == "unhealthy"
    assert by_name["immich"].status == "healthy"


def test_refresh_publishes_backup_updated(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    published: list[tuple[str, str]] = []

    def fake_publish(event: str, *, reason: str) -> None:
        published.append((event, reason))

    monkeypatch.setattr(hub, "publish", fake_publish)
    monkeypatch.setattr(
        "homelab_monitor.infrastructure_monitor.get_infrastructure_service",
        lambda: InfrastructureService([BackupConnector(mock=True)]),
    )
    refresh_infrastructure()
    assert ("overview_updated", "backup_updated") in published


def test_backup_requires_jwt(client: TestClient) -> None:
    assert client.get("/api/v1/backup").status_code == 401


def test_backup_unknown_job_is_404(
    client: TestClient,
    auth_header: Callable[..., dict[str, str]],
) -> None:
    response = client.get("/api/v1/backup/missing-job", headers=auth_header())
    assert response.status_code == 404


def test_all_roles_can_read_backup(
    client: TestClient,
    auth_header: Callable[..., dict[str, str]],
) -> None:
    for username, password in (
        ("admin", "admin123"),
        ("operator", "operator123"),
        ("viewer", "viewer123"),
    ):
        response = client.get("/api/v1/backup", headers=auth_header(username, password))
        assert response.status_code == 200
        body = response.json()
        assert body["read_only"] is True
        assert body["status"] == "running"
        assert body["backup_health"] == "healthy"
        assert body["progress_percent"] == 43
        assert body["duration_seconds"] == 1080
        assert body["destination"]["model"] == "TS-253 Pro"
        assert "02:00" in body["last_backup"]
        assert body["job_name"]
        periods = {item["period"]: item["status"] for item in body["history"]}
        assert periods["yesterday"] == "success"
        assert periods["today"] == "running"
        assert periods["last_week"] == "failed"


def test_live_backup_history_from_snapshots() -> None:
    now = datetime.now(UTC)
    start_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    start_yesterday = start_today - timedelta(days=1)
    start_week = start_today - timedelta(days=7)
    with Session(get_engine()) as db:
        db.add_all(
            [
                OpsSnapshot(
                    kind="backup",
                    observed_at=start_week + timedelta(hours=1),
                    payload={"job_status": "failed", "backup_status": "failed"},
                ),
                OpsSnapshot(
                    kind="backup",
                    observed_at=start_yesterday + timedelta(hours=2),
                    payload={"job_status": "idle", "backup_status": "success"},
                ),
            ]
        )
        db.commit()
    snapshot = ConnectorSnapshot(
        service="backup",
        status="healthy",
        version="HBS-26",
        updated_at=now,
        summary={"job_status": "running", "backup_status": "success"},
    )
    periods = {
        item["period"]: item["status"] for item in backup_history_periods(snapshot, use_mock=False)
    }
    assert periods["yesterday"] == "success"
    assert periods["today"] == "running"
    assert periods["last_week"] == "failed"
