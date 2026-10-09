from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import httpx
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from homelab_monitor.connectors.immich import ImmichConnector
from homelab_monitor.connectors.qnap import QnapConnector, storage_health
from homelab_monitor.connectors.qumagie import QuMagieConnector
from homelab_monitor.database import get_engine
from homelab_monitor.infrastructure import InfrastructureService
from homelab_monitor.infrastructure_monitor import refresh_infrastructure
from homelab_monitor.models import OpsSnapshot
from homelab_monitor.ops_history import _start_of_local_day, photo_trends
from homelab_monitor.realtime import hub


def test_storage_health_thresholds() -> None:
    assert storage_health(79.9) == "healthy"
    assert storage_health(80) == "warning"
    assert storage_health(90) == "critical"


def test_immich_live_get_only() -> None:
    methods: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        methods.append(request.method)
        assert request.method == "GET"
        path = request.url.path
        if path.endswith("/server/ping"):
            return httpx.Response(200, json={"res": "pong"})
        if path.endswith("/server/version"):
            return httpx.Response(200, json={"major": 1, "minor": 118, "patch": 0})
        if path.endswith("/server/statistics"):
            return httpx.Response(
                200,
                json={"photos": 10, "videos": 2, "lastScan": "2026-09-08T00:40:00+00:00"},
            )
        if path.endswith("/jobs"):
            return httpx.Response(
                200,
                json={
                    "thumbnailGeneration": {"jobCounts": {"waiting": 3, "active": 0}},
                    "faceDetection": {"jobCounts": {"waiting": 1}},
                    "machineLearning": {"queueStatus": {"isActive": False, "isPaused": False}},
                },
            )
        if path.endswith("/users"):
            return httpx.Response(200, json=[{}, {}, {}])
        if path.endswith("/albums"):
            return httpx.Response(200, json=[{}, {}])
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler), timeout=2)
    snapshot = ImmichConnector(
        mock=False,
        base_url="https://immich.example",
        api_key="test-key",
        client=client,
    ).collect()
    assert snapshot.status == "healthy"
    assert snapshot.version == "1.118.0"
    assert snapshot.summary["indexed_photos"] == 10
    assert snapshot.summary["indexed_videos"] == 2
    assert snapshot.summary["albums"] == 2
    assert snapshot.summary["users"] == 3
    assert snapshot.summary["thumbnail_queue"] == 3
    assert snapshot.summary["face_queue"] == 1
    assert snapshot.summary["immich_health"] == 1
    assert methods
    assert set(methods) == {"GET"}


def test_qnap_live_reads_sysinfo_and_shares() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        path = str(request.url)
        if "authLogin.cgi" in path:
            return httpx.Response(200, text="<QDocRoot><authSid>sid-1</authSid></QDocRoot>")
        if "manaRequest.cgi" in path:
            return httpx.Response(
                200,
                json={
                    "hostname": "qnap-lab-01",
                    "model": "TS-453Be",
                    "firmware": "5.2.1",
                    "uptime_seconds": 100,
                    "online": True,
                    "capacity_bytes": 1000,
                    "used_bytes": 400,
                    "free_bytes": 600,
                    "temperature_celsius": 41,
                },
            )
        if "get_share_list" in path:
            return httpx.Response(200, json={"datas": [{}, {}, {}]})
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler), timeout=2)
    snapshot = QnapConnector(
        mock=False,
        base_url="https://qnap.example",
        username="admin",
        password="secret",
        client=client,
    ).collect()
    assert snapshot.summary["hostname"] == "qnap-lab-01"
    assert snapshot.summary["model"] == "TS-453Be"
    assert snapshot.summary["shared_folders"] == 3
    assert snapshot.summary["storage_percent"] == 40.0
    assert snapshot.summary["storage_health"] == "healthy"


def test_qumagie_live_status_endpoint() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        if request.url.path.endswith("/api/status"):
            return httpx.Response(
                200,
                json={
                    "version": "2.6.0",
                    "health": "ok",
                    "indexed_photos": 99,
                    "ai_status": "ready",
                    "index_status": "idle",
                    "last_scan": "2026-09-08T00:15:00+00:00",
                },
            )
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler), timeout=2)
    snapshot = QuMagieConnector(
        mock=False,
        base_url="https://qumagie.example",
        client=client,
    ).collect()
    assert snapshot.status == "healthy"
    assert snapshot.summary["indexed_photos"] == 99
    assert snapshot.summary["qumagie_health"] == 1


def test_photo_connector_failure_is_isolated() -> None:
    class Boom(ImmichConnector):
        def collect(self):  # type: ignore[no-untyped-def]
            raise RuntimeError("immich down")

    service = InfrastructureService(
        [
            Boom(mock=True),
            QuMagieConnector(mock=True),
            QnapConnector(mock=True),
        ]
    )
    collected_at, photos, stats = service.photo_services()
    assert collected_at
    by_name = {item.service: item for item in photos}
    assert by_name["immich"].status == "unhealthy"
    assert by_name["qumagie"].status == "healthy"
    assert by_name["qnap"].status == "healthy"
    assert stats["qumagie_health"] == 1


def test_refresh_publishes_photo_services_reason(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    published: list[tuple[str, str]] = []

    def fake_publish(event: str, *, reason: str) -> None:
        published.append((event, reason))

    monkeypatch.setattr(hub, "publish", fake_publish)
    monkeypatch.setattr(
        "homelab_monitor.infrastructure_monitor.get_infrastructure_service",
        lambda: InfrastructureService([ImmichConnector(mock=True)]),
    )
    refresh_infrastructure()
    assert ("overview_updated", "photo_services_updated") in published
    assert ("overview_updated", "backup_updated") in published


def test_photo_services_requires_jwt(client: TestClient) -> None:
    assert client.get("/api/v1/photo-services").status_code == 401


def test_all_roles_can_read_photo_services(
    client: TestClient,
    auth_header: Callable[..., dict[str, str]],
) -> None:
    for username, password in (
        ("admin", "admin123"),
        ("operator", "operator123"),
        ("viewer", "viewer123"),
    ):
        response = client.get("/api/v1/photo-services", headers=auth_header(username, password))
        assert response.status_code == 200
        body = response.json()
        assert body["read_only"] is True
        names = [item["service"] for item in body["services"]]
        assert names == ["immich", "qumagie", "qnap"]
        stats = body["stats"]
        assert stats["indexed_photos"] == 18420
        assert stats["indexed_videos"] == 412
        assert stats["albums"] == 28
        assert stats["users"] == 3
        assert stats["thumbnail_queue"] == 3
        assert stats["face_queue"] == 1
        assert "storage_percent" in stats
        assert "immich_health" in stats
        assert "qumagie_health" in stats
        assert "storage_percent_metric" in stats
        assert stats["storage_history"]["today"] == stats["storage_used"]
        assert stats["storage_history"]["yesterday"] > 0
        assert stats["storage_history"]["last_week"] > 0
        assert stats["photo_growth"]["today"] == 250
        assert stats["photo_growth"]["yesterday"] == 180
        assert stats["photo_growth"]["this_week"] == 1200


def test_live_photo_trends_use_stored_snapshots() -> None:
    now = datetime.now(UTC)
    start_today = _start_of_local_day(now)
    start_yesterday = start_today - timedelta(days=1)
    start_week = start_today - timedelta(days=7)
    with Session(get_engine()) as db:
        db.add_all(
            [
                OpsSnapshot(
                    kind="photo",
                    observed_at=start_week,
                    payload={"indexed_photos": 17230, "storage_used": 1000},
                ),
                OpsSnapshot(
                    kind="photo",
                    observed_at=start_yesterday - timedelta(minutes=1),
                    payload={"indexed_photos": 18000, "storage_used": 2000},
                ),
                OpsSnapshot(
                    kind="photo",
                    observed_at=start_today - timedelta(minutes=1),
                    payload={"indexed_photos": 18180, "storage_used": 3000},
                ),
            ]
        )
        db.commit()
    storage, growth = photo_trends(
        {"indexed_photos": 18430, "storage_used": 4000},
        use_mock=False,
    )
    assert storage["today"] == 4000
    assert storage["yesterday"] == 3000
    assert storage["last_week"] == 1000
    assert growth["today"] == 250
    assert growth["yesterday"] == 180
    assert growth["this_week"] == 1200


def test_mock_photo_refresh_does_not_overwrite_nas_snapshots(
    client: TestClient,
    auth_header: Callable[..., dict[str, str]],
) -> None:
    now = datetime.now(UTC)
    with Session(get_engine()) as db:
        db.execute(delete(OpsSnapshot).where(OpsSnapshot.kind == "photo"))
        db.add(
            OpsSnapshot(
                kind="photo",
                observed_at=now,
                payload={
                    "indexed_photos": 79119,
                    "storage_used": 113582165922,
                    "capacity_bytes": 12000000000000,
                },
            )
        )
        db.commit()
    refresh_infrastructure()
    response = client.get("/api/v1/photo-services", headers=auth_header())
    assert response.status_code == 200
    with Session(get_engine()) as db:
        rows = list(
            db.scalars(
                select(OpsSnapshot)
                .where(OpsSnapshot.kind == "photo")
                .order_by(OpsSnapshot.observed_at.desc())
            ).all()
        )
        assert {int(row.payload.get("indexed_photos") or 0) for row in rows} == {79119}
