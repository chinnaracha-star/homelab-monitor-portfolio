from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from homelab_monitor.alert_engine import AlertEngine
from homelab_monitor.alert_rules import preview_sentence
from homelab_monitor.alert_rules.evaluate import compare
from homelab_monitor.database import get_engine
from homelab_monitor.models import Agent, AgentGroup, AgentGroupMember, Alert, AlertRule
from homelab_monitor.security import hash_agent_token
from homelab_monitor.settings import Settings

REGISTRATION_KEY = "test-registration-key-at-least-24-chars"


def alert_settings(**overrides) -> Settings:
    return Settings(
        registration_key=REGISTRATION_KEY,
        alert_cpu_threshold_percent=90,
        alert_memory_threshold_percent=90,
        alert_disk_threshold_percent=90,
        alert_temperature_threshold_celsius=80,
        agent_offline_after_seconds=60,
        **overrides,
    )


def system_payload(
    *,
    cpu: float,
    memory: float,
    disk: float,
    temperature: float,
) -> dict[str, object]:
    return {
        "modules": [
            {
                "module": "system",
                "status": "warning",
                "summary": "System thresholds evaluated",
                "metrics": {
                    "cpu": {"usage_percent": cpu},
                    "memory": {"usage_percent": memory},
                    "disks": [{"mount_point": "/", "usage_percent": disk}],
                    "temperatures": [
                        {
                            "source": "coretemp",
                            "label": "Package",
                            "current_celsius": temperature,
                        }
                    ],
                },
                "diagnostics": {},
            }
        ]
    }


def create_agent(db: Session, name: str, last_seen_at: datetime | None = None) -> Agent:
    agent = Agent(
        name=name,
        hostname=f"{name}.local",
        version="0.1.0",
        token_hash=hash_agent_token(f"{name}-token"),
        status="online",
        capabilities=["ubuntu"],
        last_seen_at=last_seen_at,
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


@pytest.fixture(autouse=True)
def _clear_alert_rules():
    yield
    with Session(get_engine()) as db:
        db.execute(delete(AlertRule))
        db.commit()


def _rule_payload(**overrides) -> dict:
    payload = {
        "name": "CPU high",
        "description": "Raise when CPU is busy",
        "metric": "cpu_percent",
        "operator": ">",
        "threshold": 90,
        "severity": "critical",
        "enabled": True,
        "cooldown_seconds": 0,
        "applies_to": "all",
    }
    payload.update(overrides)
    return payload


def test_compare_operators() -> None:
    assert compare(">", 91, 90) is True
    assert compare(">", 90, 90) is False
    assert compare(">=", 90, 90) is True
    assert compare("<", 10, 20) is True
    assert compare("<=", 20, 20) is True
    assert compare("==", 90.0, 90.0) is True
    assert compare("!=", 91, 90) is True


def test_preview_sentence() -> None:
    assert preview_sentence("cpu_percent", ">", 90, "critical") == (
        "If CPU is greater than 90% create Critical alert."
    )


def test_alert_rule_crud_and_enable(
    client: TestClient,
    auth_header: Callable[..., dict[str, str]],
) -> None:
    created = client.post("/api/v1/alert-rules", headers=auth_header(), json=_rule_payload())
    assert created.status_code == 201
    body = created.json()
    rule_id = body["id"]
    assert body["preview"] == "If CPU is greater than 90% create Critical alert."
    assert body["enabled"] is True

    listed = client.get("/api/v1/alert-rules", headers=auth_header("viewer", "viewer123"))
    assert listed.status_code == 200
    assert listed.json()[0]["id"] == rule_id

    detail = client.get(
        f"/api/v1/alert-rules/{rule_id}",
        headers=auth_header("operator", "operator123"),
    )
    assert detail.status_code == 200
    assert detail.json()["metric"] == "cpu_percent"

    updated = client.put(
        f"/api/v1/alert-rules/{rule_id}",
        headers=auth_header(),
        json=_rule_payload(threshold=85, severity="high", cooldown_seconds=30),
    )
    assert updated.status_code == 200
    assert updated.json()["threshold"] == 85
    assert updated.json()["cooldown_seconds"] == 30

    disabled = client.patch(
        f"/api/v1/alert-rules/{rule_id}/enable",
        headers=auth_header(),
        json={"enabled": False},
    )
    assert disabled.status_code == 200
    assert disabled.json()["enabled"] is False

    enabled = client.patch(
        f"/api/v1/alert-rules/{rule_id}/enable",
        headers=auth_header(),
        json={"enabled": True},
    )
    assert enabled.json()["enabled"] is True

    deleted = client.delete(f"/api/v1/alert-rules/{rule_id}", headers=auth_header())
    assert deleted.status_code == 204
    missing = client.get(f"/api/v1/alert-rules/{rule_id}", headers=auth_header())
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "alert_rule_not_found"


def test_alert_rules_require_jwt_and_admin_writes(
    client: TestClient,
    auth_header: Callable[..., dict[str, str]],
) -> None:
    assert client.get("/api/v1/alert-rules").status_code == 401
    assert client.post("/api/v1/alert-rules", json=_rule_payload()).status_code == 401

    operator = client.post(
        "/api/v1/alert-rules",
        headers=auth_header("operator", "operator123"),
        json=_rule_payload(),
    )
    assert operator.status_code == 403

    viewer = client.post(
        "/api/v1/alert-rules",
        headers=auth_header("viewer", "viewer123"),
        json=_rule_payload(),
    )
    assert viewer.status_code == 403

    created = client.post("/api/v1/alert-rules", headers=auth_header(), json=_rule_payload())
    rule_id = created.json()["id"]
    assert (
        client.put(
            f"/api/v1/alert-rules/{rule_id}",
            headers=auth_header("operator", "operator123"),
            json=_rule_payload(),
        ).status_code
        == 403
    )
    assert (
        client.patch(
            f"/api/v1/alert-rules/{rule_id}/enable",
            headers=auth_header("viewer", "viewer123"),
            json={"enabled": False},
        ).status_code
        == 403
    )
    assert (
        client.delete(
            f"/api/v1/alert-rules/{rule_id}",
            headers=auth_header("operator", "operator123"),
        ).status_code
        == 403
    )


def test_invalid_alert_rule_payload_returns_422(
    client: TestClient,
    auth_header: Callable[..., dict[str, str]],
) -> None:
    invalid_metric = client.post(
        "/api/v1/alert-rules",
        headers=auth_header(),
        json=_rule_payload(metric="fan_speed"),
    )
    assert invalid_metric.status_code == 422

    missing_group = client.post(
        "/api/v1/alert-rules",
        headers=auth_header(),
        json=_rule_payload(applies_to="group"),
    )
    assert missing_group.status_code == 422


def test_disabled_rule_does_not_open_alert() -> None:
    observed_at = datetime.now(UTC)
    with Session(get_engine()) as db:
        agent = create_agent(db, "rule-disabled")
        db.add(
            AlertRule(
                name="Disabled CPU",
                description="",
                metric="cpu_percent",
                operator=">",
                threshold=50,
                severity="high",
                enabled=False,
                cooldown_seconds=0,
                applies_to="all",
            )
        )
        db.commit()
        AlertEngine(alert_settings()).evaluate_report(
            db,
            agent,
            system_payload(cpu=95, memory=20, disk=30, temperature=40),
            observed_at,
        )
        db.commit()
        cpu_alert = db.scalar(
            select(Alert).where(Alert.agent_id == agent.id, Alert.kind == "cpu_high")
        )
        assert cpu_alert is None


def test_group_rule_only_matches_members() -> None:
    observed_at = datetime.now(UTC)
    with Session(get_engine()) as db:
        member = create_agent(db, "rule-group-in")
        outsider = create_agent(db, "rule-group-out")
        group = AgentGroup(name="Rules Rack", description="")
        db.add(group)
        db.flush()
        db.add(AgentGroupMember(group_id=group.id, agent_id=member.id))
        db.add(
            AlertRule(
                name="Group CPU",
                description="",
                metric="cpu_percent",
                operator=">",
                threshold=80,
                severity="high",
                enabled=True,
                cooldown_seconds=0,
                applies_to="group",
                group_id=group.id,
            )
        )
        db.commit()
        engine = AlertEngine(alert_settings())
        payload = system_payload(cpu=95, memory=20, disk=30, temperature=40)
        engine.evaluate_report(db, member, payload, observed_at)
        engine.evaluate_report(db, outsider, payload, observed_at)
        engine.evaluate_report(db, member, payload, observed_at + timedelta(minutes=2))
        engine.evaluate_report(db, outsider, payload, observed_at + timedelta(minutes=2))
        db.commit()
        assert (
            db.scalar(select(Alert).where(Alert.agent_id == member.id, Alert.kind == "cpu_high"))
            is not None
        )
        assert (
            db.scalar(select(Alert).where(Alert.agent_id == outsider.id, Alert.kind == "cpu_high"))
            is None
        )
        db.delete(group)
        db.commit()


def test_higher_severity_rule_wins_when_operators_overlap() -> None:
    observed_at = datetime.now(UTC)
    with Session(get_engine()) as db:
        agent = create_agent(db, "rule-precedence")
        db.add_all(
            [
                AlertRule(
                    name="CPU medium",
                    description="",
                    metric="cpu_percent",
                    operator=">",
                    threshold=80,
                    severity="medium",
                    enabled=True,
                    cooldown_seconds=0,
                    applies_to="all",
                ),
                AlertRule(
                    name="CPU critical",
                    description="",
                    metric="cpu_percent",
                    operator=">=",
                    threshold=90,
                    severity="critical",
                    enabled=True,
                    cooldown_seconds=0,
                    applies_to="all",
                ),
            ]
        )
        db.commit()
        payload = system_payload(cpu=95, memory=20, disk=30, temperature=40)
        engine = AlertEngine(alert_settings())
        engine.evaluate_report(db, agent, payload, observed_at)
        engine.evaluate_report(db, agent, payload, observed_at + timedelta(minutes=2))
        db.commit()
        alert = db.scalar(select(Alert).where(Alert.agent_id == agent.id, Alert.kind == "cpu_high"))
        assert alert is not None
        assert alert.severity == "critical"
        assert alert.threshold == 90


def test_cooldown_suppresses_identical_reopen() -> None:
    observed_at = datetime.now(UTC)
    with Session(get_engine()) as db:
        agent = create_agent(db, "rule-cooldown")
        db.add(
            AlertRule(
                name="CPU cooldown",
                description="",
                metric="cpu_percent",
                operator=">",
                threshold=90,
                severity="high",
                enabled=True,
                cooldown_seconds=60,
                applies_to="all",
            )
        )
        db.commit()
        engine = AlertEngine(alert_settings())
        high = system_payload(cpu=95, memory=20, disk=30, temperature=40)
        low = system_payload(cpu=20, memory=20, disk=30, temperature=40)
        engine.evaluate_report(db, agent, high, observed_at)
        first = engine.evaluate_report(db, agent, high, observed_at + timedelta(minutes=2))
        db.commit()
        assert len(first) == 1
        engine.evaluate_report(db, agent, low, observed_at + timedelta(minutes=3))
        engine.evaluate_report(db, agent, low, observed_at + timedelta(minutes=5))
        db.commit()
        suppressed = engine.evaluate_report(
            db,
            agent,
            system_payload(cpu=96, memory=20, disk=30, temperature=40),
            observed_at + timedelta(minutes=5, seconds=10),
        )
        db.commit()
        alert = db.scalar(select(Alert).where(Alert.agent_id == agent.id, Alert.kind == "cpu_high"))
        assert suppressed == []
        assert alert is not None
        assert alert.status == "resolved"
        after_cooldown = observed_at + timedelta(minutes=5, seconds=70)
        pending = engine.evaluate_report(
            db,
            agent,
            system_payload(cpu=96, memory=20, disk=30, temperature=40),
            after_cooldown,
        )
        db.commit()
        db.refresh(alert)
        assert pending == []
        assert alert.status == "resolved"
        reopened = engine.evaluate_report(
            db,
            agent,
            system_payload(cpu=96, memory=20, disk=30, temperature=40),
            after_cooldown + timedelta(minutes=2),
        )
        db.commit()
        db.refresh(alert)
        assert len(reopened) == 1
        assert alert.status == "active"
