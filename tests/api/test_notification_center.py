from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy.orm import Session

from homelab_monitor.database import get_engine
from homelab_monitor.models import (
    Agent,
    AgentConfiguration,
    AgentGroupMember,
    Alert,
    MetricHistory,
    MetricReport,
    Notification,
)
from homelab_monitor.security import hash_agent_token

REGISTRATION_KEY = "test-registration-key-at-least-24-chars"


def _reset() -> None:
    with Session(get_engine()) as db:
        db.execute(delete(Notification))
        db.execute(delete(Alert))
        db.execute(delete(MetricHistory))
        db.execute(delete(MetricReport))
        db.execute(delete(AgentGroupMember))
        db.execute(delete(AgentConfiguration))
        db.execute(delete(Agent))
        db.commit()


def test_notification_center_jwt_rbac_empty(
    client: TestClient,
    auth_header: Callable[..., dict[str, str]],
) -> None:
    _reset()
    assert client.get("/api/v1/notifications/history").status_code == 401
    headers = auth_header("viewer", "viewer123")
    body = client.get("/api/v1/notifications/history", headers=headers).json()
    assert body["items"] == []
    assert body["groups"] == []
    stats = client.get("/api/v1/notifications/statistics", headers=headers).json()
    assert stats["total"] == 0
    assert stats["unread"] == 0
    operator = auth_header("operator", "operator123")
    assert client.get("/api/v1/notifications/history", headers=operator).status_code == 200


def test_notification_center_groups_and_filters(
    client: TestClient,
    auth_header: Callable[..., dict[str, str]],
) -> None:
    _reset()
    now = datetime.now(UTC)
    with Session(get_engine()) as db:
        agent = Agent(
            name="notify-agent",
            hostname="notify-agent.local",
            version="0.1.0",
            token_hash=hash_agent_token("notify-agent-token"),
            status="online",
            capabilities=["ubuntu"],
        )
        db.add(agent)
        db.commit()
        db.refresh(agent)
        alert = Alert(
            agent_id=agent.id,
            kind="cpu_high",
            resource="system",
            status="resolved",
            severity="critical",
            current_value=40,
            threshold=90,
            message="CPU recovered",
            opened_at=now - timedelta(minutes=20),
            last_observed_at=now - timedelta(minutes=1),
            resolved_at=now - timedelta(minutes=1),
        )
        db.add(alert)
        db.commit()
        db.refresh(alert)
        db.add_all(
            [
                Notification(
                    alert_id=alert.id,
                    channel="telegram",
                    recipient="chat",
                    status="sent",
                    created_at=now - timedelta(minutes=19),
                ),
                Notification(
                    alert_id=alert.id,
                    channel="telegram",
                    recipient="chat",
                    status="sent",
                    created_at=now - timedelta(seconds=30),
                ),
                Notification(
                    alert_id=None,
                    channel="discord",
                    recipient="hook",
                    status="failed",
                    error_message="test",
                    created_at=now,
                ),
            ]
        )
        db.commit()
    headers = auth_header()
    history = client.get("/api/v1/notifications/history", headers=headers).json()
    assert len(history["items"]) == 3
    assert history["groups"]
    assert history["items"][0]["kind"] in {"system", "recovery", "alert"}
    unread = client.get(
        "/api/v1/notifications/history", params={"read_state": "unread"}, headers=headers
    ).json()
    assert len(unread["items"]) == 1
    stats = client.get("/api/v1/notifications/statistics", headers=headers).json()
    assert stats["total"] == 3
    assert stats["critical"] >= 1
    assert stats["unread"] == 1
