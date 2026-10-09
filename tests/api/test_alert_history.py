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


def _agent(db: Session, name: str) -> Agent:
    agent = Agent(
        name=name,
        hostname=f"{name}.local",
        version="0.1.0",
        token_hash=hash_agent_token(f"{name}-token"),
        status="online",
        capabilities=["ubuntu"],
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


def _alert(
    db: Session,
    agent: Agent,
    kind: str,
    *,
    opened: datetime,
    resolved: datetime | None = None,
    severity: str = "warning",
    value: float = 96,
) -> Alert:
    alert = Alert(
        agent_id=agent.id,
        kind=kind,
        resource="system",
        status="resolved" if resolved else "active",
        severity=severity,
        current_value=value,
        threshold=90,
        message=kind,
        opened_at=opened,
        last_observed_at=resolved or opened,
        resolved_at=resolved,
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert


def test_history_jwt_rbac_and_empty(
    client: TestClient,
    auth_header: Callable[..., dict[str, str]],
) -> None:
    _reset()
    assert client.get("/api/v1/alerts/history").status_code == 401
    assert client.get("/api/v1/alerts/statistics").status_code == 401
    headers = auth_header("viewer", "viewer123")
    history = client.get("/api/v1/alerts/history", headers=headers)
    stats = client.get("/api/v1/alerts/statistics", headers=headers)
    assert history.status_code == 200
    assert history.json() == []
    body = stats.json()
    assert body["active_alerts"] == 0
    assert body["total"] == 0
    assert body["recovery_rate"] == 0
    operator = auth_header("operator", "operator123")
    assert client.get("/api/v1/alerts/history", headers=operator).status_code == 200


def test_history_order_filters_duration_and_statistics(
    client: TestClient,
    auth_header: Callable[..., dict[str, str]],
) -> None:
    _reset()
    now = datetime(2026, 9, 8, 12, 0, tzinfo=UTC)
    with Session(get_engine()) as db:
        agent = _agent(db, "history-agent")
        _alert(
            db,
            agent,
            "cpu_high",
            opened=now - timedelta(hours=2),
            resolved=now - timedelta(hours=1),
            severity="critical",
            value=41,
        )
        _alert(
            db,
            agent,
            "memory_high",
            opened=now - timedelta(minutes=10),
            severity="warning",
            value=85,
        )
    headers = auth_header()
    history = client.get("/api/v1/alerts/history", headers=headers).json()
    assert [item["alert_type"] for item in history] == ["memory_high", "cpu_high"]
    assert history[1]["duration_seconds"] == 3600
    assert history[1]["status"] == "recovered"
    active = client.get(
        "/api/v1/alerts/history", params={"status": "active"}, headers=headers
    ).json()
    assert [item["alert_type"] for item in active] == ["memory_high"]
    critical = client.get(
        "/api/v1/alerts/history", params={"severity": "critical"}, headers=headers
    ).json()
    assert len(critical) == 1
    stats = client.get("/api/v1/alerts/statistics", headers=headers).json()
    assert stats["active_alerts"] == 1
    assert stats["recovered"] == 1
    assert stats["critical_count"] == 1
    assert stats["warning_count"] == 1
    assert stats["recovery_rate"] == 50.0
