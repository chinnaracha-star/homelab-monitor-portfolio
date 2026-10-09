from collections.abc import Callable
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from homelab_monitor.database import get_engine
from homelab_monitor.history import as_utc, csv_filename, render_history_csv
from homelab_monitor.models import MetricHistory

REGISTRATION_KEY = "test-registration-key-at-least-24-chars"


def register_agent(client: TestClient, name: str) -> tuple[str, str]:
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
    return body["agent_id"], body["agent_token"]


def upload_full_report(
    client: TestClient,
    token: str,
    report_id: str,
    observed_at: str,
    *,
    cpu: float,
    memory: float,
    disk: float,
    temperature: float,
    rx: float,
    tx: float,
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
                    "metrics": {
                        "cpu": {"usage_percent": cpu},
                        "memory": {"usage_percent": memory},
                        "disks": [{"mount_point": "/", "usage_percent": disk}],
                        "temperatures": [
                            {
                                "source": "core",
                                "label": "Package",
                                "current_celsius": temperature,
                            }
                        ],
                        "network": {"rx_bytes": rx, "tx_bytes": tx},
                    },
                    "diagnostics": {},
                }
            ],
        },
    )
    assert response.status_code == 200
    return response.json()


def test_metric_history_is_persisted_on_report_upload(client: TestClient) -> None:
    agent_id, token = register_agent(client, "history-persist")
    upload_full_report(
        client,
        token,
        "hist-1",
        "2026-09-07T10:00:00Z",
        cpu=12.5,
        memory=40.0,
        disk=55.0,
        temperature=48.0,
        rx=1000,
        tx=2000,
    )

    with Session(get_engine()) as db:
        row = db.scalar(select(MetricHistory).where(MetricHistory.agent_id == agent_id))

    assert row is not None
    assert row.cpu_percent == 12.5
    assert row.memory_percent == 40.0
    assert row.disk_percent == 55.0
    assert row.temperature_celsius == 48.0
    assert row.network_rx_bytes == 1000
    assert row.network_tx_bytes == 2000
    assert as_utc(row.timestamp) == datetime(2026, 9, 7, 10, 0, tzinfo=UTC)


def test_duplicate_report_does_not_write_history(client: TestClient) -> None:
    agent_id, token = register_agent(client, "history-duplicate")
    payload_time = "2026-09-07T10:05:00Z"
    first = upload_full_report(
        client,
        token,
        "hist-dup",
        payload_time,
        cpu=10.0,
        memory=20.0,
        disk=30.0,
        temperature=40.0,
        rx=1,
        tx=2,
    )
    second = upload_full_report(
        client,
        token,
        "hist-dup",
        payload_time,
        cpu=10.0,
        memory=20.0,
        disk=30.0,
        temperature=40.0,
        rx=1,
        tx=2,
    )
    assert first["duplicate"] is False
    assert second["duplicate"] is True

    with Session(get_engine()) as db:
        rows = db.scalars(select(MetricHistory).where(MetricHistory.agent_id == agent_id)).all()
    assert len(rows) == 1


def test_history_api_filters_and_orders_by_timestamp(
    client: TestClient,
    auth_header: Callable[..., dict[str, str]],
) -> None:
    agent_id, token = register_agent(client, "history-filter")
    upload_full_report(
        client,
        token,
        "h-old",
        "2026-09-07T08:00:00Z",
        cpu=10.0,
        memory=11.0,
        disk=12.0,
        temperature=30.0,
        rx=1,
        tx=2,
    )
    upload_full_report(
        client,
        token,
        "h-mid",
        "2026-09-07T10:00:00Z",
        cpu=20.0,
        memory=21.0,
        disk=22.0,
        temperature=31.0,
        rx=3,
        tx=4,
    )
    upload_full_report(
        client,
        token,
        "h-new",
        "2026-09-07T12:00:00Z",
        cpu=30.0,
        memory=31.0,
        disk=32.0,
        temperature=32.0,
        rx=5,
        tx=6,
    )

    response = client.get(
        f"/api/v1/history/agents/{agent_id}",
        params={
            "from": "2026-09-07T09:00:00Z",
            "to": "2026-09-07T11:00:00Z",
            "interval": "1h",
        },
        headers=auth_header(),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["agent_id"] == agent_id
    assert body["interval"] == "1h"
    assert "from" in body
    assert "to" in body
    timestamps = [point["timestamp"] for point in body["points"]]
    assert timestamps == sorted(timestamps)
    assert len(body["points"]) == 1
    assert body["points"][0]["cpu_percent"] == 20.0


def test_history_aggregates_points_in_interval(
    client: TestClient,
    auth_header: Callable[..., dict[str, str]],
) -> None:
    agent_id, token = register_agent(client, "history-aggregate")
    upload_full_report(
        client,
        token,
        "agg-1",
        "2026-09-07T10:01:00Z",
        cpu=10.0,
        memory=20.0,
        disk=30.0,
        temperature=40.0,
        rx=100,
        tx=200,
    )
    upload_full_report(
        client,
        token,
        "agg-2",
        "2026-09-07T10:04:00Z",
        cpu=20.0,
        memory=30.0,
        disk=40.0,
        temperature=50.0,
        rx=300,
        tx=400,
    )

    response = client.get(
        f"/api/v1/history/agents/{agent_id}",
        params={
            "from": "2026-09-07T10:00:00Z",
            "to": "2026-09-07T10:10:00Z",
            "interval": "5m",
        },
        headers=auth_header(),
    )
    assert response.status_code == 200
    points = response.json()["points"]
    assert len(points) == 1
    assert points[0]["cpu_percent"] == 15.0
    assert points[0]["memory_percent"] == 25.0


def test_history_requires_dashboard_jwt(client: TestClient) -> None:
    response = client.get(
        "/api/v1/history/agents/missing",
        params={"interval": "1m"},
    )
    assert response.status_code == 401


def test_history_csv_export(
    client: TestClient,
    auth_header: Callable[..., dict[str, str]],
) -> None:
    agent_id, token = register_agent(client, "history-csv")
    upload_full_report(
        client,
        token,
        "csv-1",
        "2026-09-07T10:00:00Z",
        cpu=12.0,
        memory=34.0,
        disk=56.0,
        temperature=45.0,
        rx=8,
        tx=9,
    )

    response = client.get(
        f"/api/v1/history/agents/{agent_id}/export",
        params={
            "from": "2026-09-07T09:00:00Z",
            "to": "2026-09-07T11:00:00Z",
            "interval": "1h",
        },
        headers=auth_header(),
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    disposition = response.headers["content-disposition"]
    assert "filename=" in disposition
    assert ".csv" in disposition
    assert "history-csv-" in disposition
    body = response.text
    assert body.splitlines()[0] == (
        "timestamp,cpu_percent,memory_percent,disk_percent,"
        "temperature_celsius,network_rx_bytes,network_tx_bytes"
    )
    assert "12" in body
    rendered = render_history_csv(
        [
            {
                "timestamp": datetime(2026, 9, 7, 10, 0, tzinfo=UTC),
                "cpu_percent": 12.0,
                "memory_percent": 34.0,
                "disk_percent": 56.0,
                "temperature_celsius": 45.0,
                "network_rx_bytes": 8.0,
                "network_tx_bytes": 9.0,
            }
        ]
    )
    assert "12" in rendered
    assert csv_filename("history-csv", datetime(2026, 9, 7, 14, 32, tzinfo=UTC)) == (
        "history-csv-20260907-1432.csv"
    )
