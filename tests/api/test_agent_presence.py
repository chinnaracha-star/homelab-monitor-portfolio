from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy.orm import Session

from homelab_monitor.agent_presence import presence_of
from homelab_monitor.alert_engine import AlertEngine
from homelab_monitor.database import get_engine
from homelab_monitor.developer_dashboard import DeveloperDashboardService
from homelab_monitor.models import Agent, AgentConfiguration, AgentGroupMember, MetricReport
from homelab_monitor.security import hash_agent_token
from homelab_monitor.settings import Settings, get_settings

REGISTRATION_KEY = "test-registration-key-at-least-24-chars"


def _settings(**overrides) -> Settings:
    return Settings(registration_key=REGISTRATION_KEY, agent_offline_after_seconds=60, **overrides)


def _reset_agents() -> None:
    with Session(get_engine()) as db:
        db.execute(delete(MetricReport))
        db.execute(delete(AgentGroupMember))
        db.execute(delete(AgentConfiguration))
        db.execute(delete(Agent))
        db.commit()


def _agent(db: Session, name: str, **fields) -> Agent:
    agent = Agent(
        name=name,
        hostname=f"{name}.local",
        version="0.1.0",
        token_hash=hash_agent_token(f"{name}-token"),
        capabilities=["ubuntu"],
        **fields,
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent
    agent = Agent(
        name=name,
        hostname=f"{name}.local",
        version="0.1.0",
        token_hash=hash_agent_token(f"{name}-token"),
        capabilities=["ubuntu"],
        **fields,
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


def test_presence_uses_latest_check_in_and_report() -> None:
    now = datetime(2026, 9, 8, 8, 35, tzinfo=UTC)
    stale_seen = now - timedelta(seconds=120)
    fresh_report = now - timedelta(seconds=5)
    presence = presence_of(stale_seen, fresh_report, now=now, timeout_seconds=60)
    assert presence.status == "online"
    assert presence.contact_at == fresh_report


def test_presence_marks_offline_only_after_timeout() -> None:
    now = datetime(2026, 9, 8, 8, 35, tzinfo=UTC)
    last_seen = now - timedelta(seconds=61)
    presence = presence_of(last_seen, None, now=now, timeout_seconds=60)
    assert presence.status == "offline"
    still_online = presence_of(now - timedelta(seconds=60), None, now=now, timeout_seconds=60)
    assert still_online.status == "online"


def test_registered_agent_is_not_offline_without_contact() -> None:
    now = datetime(2026, 9, 8, 8, 35, tzinfo=UTC)
    with Session(get_engine()) as db:
        agent = _agent(db, "presence-registered", status="registered")
        engine = AlertEngine(_settings())
        engine.evaluate_offline_agents(db, now)
        db.commit()
        db.refresh(agent)
        assert agent.status == "registered"


def test_offline_evaluator_restores_online_after_fresh_heartbeat() -> None:
    now = datetime(2026, 9, 8, 8, 35, tzinfo=UTC)
    with Session(get_engine()) as db:
        agent = _agent(
            db,
            "presence-restore",
            status="offline",
            last_seen_at=now - timedelta(seconds=5),
        )
        events, changed = AlertEngine(_settings()).evaluate_offline_agents(db, now)
        db.commit()
        db.refresh(agent)
        assert agent.status == "online"
        assert changed is True
        assert events == []


def test_report_received_at_recovers_online_status() -> None:
    now = datetime(2026, 9, 8, 8, 35, tzinfo=UTC)
    with Session(get_engine()) as db:
        agent = _agent(
            db,
            "presence-report",
            status="offline",
            last_seen_at=now - timedelta(seconds=300),
        )
        db.add(
            MetricReport(
                agent_id=agent.id,
                report_id="presence-report-1",
                schema_version="1.0",
                content_hash="abc",
                observed_at=now - timedelta(seconds=300),
                received_at=now - timedelta(seconds=2),
                payload={"modules": []},
            )
        )
        db.commit()
        AlertEngine(_settings()).evaluate_offline_agents(db, now)
        db.commit()
        db.refresh(agent)
        assert agent.status == "online"


def test_dashboard_and_developer_share_online_source(
    client: TestClient,
    auth_header,
) -> None:
    _reset_agents()
    registration = client.post(
        "/api/v1/agents/register",
        headers={"X-Registration-Key": REGISTRATION_KEY},
        json={
            "name": "presence-live",
            "hostname": "presence-live.local",
            "version": "0.1.0",
            "capabilities": ["ubuntu"],
        },
    )
    assert registration.status_code == 201
    token = registration.json()["agent_token"]
    check_in = client.post(
        "/api/v1/agent/check-ins",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "version": "0.1.0",
            "observed_at": "2020-01-01T00:00:00Z",
            "config_revision": 1,
        },
    )
    assert check_in.status_code == 200

    headers = auth_header()
    agents = client.get("/api/v1/agents", headers=headers).json()
    detail = client.get(f"/api/v1/agents/{agents[0]['id']}", headers=headers).json()
    overview = client.get("/api/v1/dashboard/overview", headers=headers).json()
    analytics = client.get("/api/v1/analytics/overview", headers=headers).json()
    developer = client.get(
        "/api/v1/developer/overview",
        headers=auth_header("admin", "admin123"),
    ).json()

    live = next(item for item in agents if item["name"] == "presence-live")
    assert live["status"] == "online"
    assert detail["status"] == "online"
    assert overview["agents"]["online"] == 1
    assert analytics["daily"]["agents_online"] == 1
    assert developer["runtime"]["agent"] == "healthy"
    assert developer["agent_service"]["agent_status"] == "online"


def test_systemd_running_is_exposed_on_mission_control(monkeypatch) -> None:
    service = DeveloperDashboardService()
    monkeypatch.setattr(
        service,
        "_systemd_show",
        lambda _unit: {
            "ActiveState": "active",
            "SubState": "running",
            "UnitFileState": "enabled",
            "MainPID": "4242",
            "NRestarts": "7",
        },
    )
    with Session(get_engine()) as db:
        payload = service._agent_service(db, get_settings())
    assert payload.state == "running"
    assert payload.pid == 4242
    assert payload.restart_count == 7
    assert payload.systemd_status == "active/running"
