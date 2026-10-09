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
    opened: datetime,
    severity: str = "warning",
    value: float = 95,
) -> Alert:
    alert = Alert(
        agent_id=agent.id,
        kind=kind,
        resource="system",
        status="active",
        severity=severity,
        current_value=value,
        threshold=90,
        message=kind,
        opened_at=opened,
        last_observed_at=opened,
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert


def test_incidents_jwt_rbac_empty(
    client: TestClient,
    auth_header: Callable[..., dict[str, str]],
) -> None:
    _reset()
    assert client.get("/api/v1/incidents").status_code == 401
    headers = auth_header("viewer", "viewer123")
    assert client.get("/api/v1/incidents", headers=headers).json() == []
    stats = client.get("/api/v1/incidents/statistics", headers=headers).json()
    assert stats["incident_count"] == 0
    assert stats["open_count"] == 0
    missing = client.get("/api/v1/incidents/missing", headers=headers)
    assert missing.status_code == 404
    operator = auth_header("operator", "operator123")
    assert client.get("/api/v1/incidents", headers=operator).status_code == 200


def test_correlation_groups_related_metrics(
    client: TestClient,
    auth_header: Callable[..., dict[str, str]],
) -> None:
    _reset()
    start = datetime(2026, 9, 8, 10, 0, tzinfo=UTC)
    with Session(get_engine()) as db:
        agent = _agent(db, "corr-agent")
        _alert(db, agent, "cpu_high", start, "critical", 96)
        _alert(db, agent, "memory_high", start + timedelta(minutes=2), "warning", 85)
        _alert(db, agent, "temperature_high", start + timedelta(minutes=4), "warning", 66)
        other = _agent(db, "corr-other")
        _alert(db, other, "cpu_high", start, "warning", 75)
    headers = auth_header()
    incidents = client.get("/api/v1/incidents", headers=headers).json()
    grouped = next(item for item in incidents if item["agent_name"] == "corr-agent")
    assert grouped["alert_count"] == 3
    assert grouped["severity"] == "critical"
    assert grouped["status"] == "active"
    detail = client.get(f"/api/v1/incidents/{grouped['id']}", headers=headers).json()
    assert len(detail["affected_alerts"]) == 3
    assert detail["duration_seconds"] >= 0
    stats = client.get("/api/v1/incidents/statistics", headers=headers).json()
    assert stats["incident_count"] == 2
    assert stats["open_count"] == 2
    assert stats["critical_count"] == 1
    assert stats["top_affected_agent"] in {"corr-agent", "corr-other"}
