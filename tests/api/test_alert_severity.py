from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from homelab_monitor.alert_engine import AlertEngine
from homelab_monitor.alert_severity import (
    alert_payload_severity,
    classify_metric_severity,
    dashboard_health_status,
)
from homelab_monitor.capacity_planning import estimated_full_in
from homelab_monitor.database import get_engine
from homelab_monitor.models import Agent, Alert
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


def system_payload(*, cpu: float, memory: float, disk: float, temperature: float) -> dict:
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


def create_agent(db: Session, name: str) -> Agent:
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


def test_metric_severity_bands() -> None:
    assert classify_metric_severity("cpu_percent", 69.9) == "info"
    assert classify_metric_severity("cpu_percent", 70) == "warning"
    assert classify_metric_severity("cpu_percent", 90) == "warning"
    assert classify_metric_severity("cpu_percent", 90.1) == "critical"
    assert classify_metric_severity("memory_percent", 79.9) == "info"
    assert classify_metric_severity("memory_percent", 80) == "warning"
    assert classify_metric_severity("memory_percent", 91) == "critical"
    assert classify_metric_severity("temperature_celsius", 59.9) == "info"
    assert classify_metric_severity("temperature_celsius", 60) == "warning"
    assert classify_metric_severity("temperature_celsius", 75) == "warning"
    assert classify_metric_severity("temperature_celsius", 75.1) == "critical"
    assert classify_metric_severity("disk_percent", 80) == "warning"
    assert classify_metric_severity("disk_percent", 91) == "critical"


def test_dashboard_health_status_rules() -> None:
    assert dashboard_health_status(["critical"], 99) == "Critical"
    assert dashboard_health_status(["warning"], 99) == "Warning"
    assert dashboard_health_status(["info"], 94) == "Excellent"
    assert dashboard_health_status([], 70) == "Good"


def test_estimated_full_in_never_divides_by_zero() -> None:
    assert estimated_full_in(138, 12) == "138 Days"
    assert estimated_full_in(5.25, 800) == "5 Days"
    assert estimated_full_in(10, 0) == "Unknown"
    assert estimated_full_in(None, 100) == "Unknown"


def test_alert_engine_stores_band_severity() -> None:
    observed_at = datetime.now(UTC)
    with Session(get_engine()) as db:
        agent = create_agent(db, "severity-bands")
        engine = AlertEngine(alert_settings())
        warning = system_payload(cpu=75, memory=85, disk=82, temperature=66)
        engine.evaluate_report(db, agent, warning, observed_at)
        engine.evaluate_report(db, agent, warning, observed_at + timedelta(minutes=2))
        db.commit()
        alerts = {
            alert.kind: alert
            for alert in db.scalars(select(Alert).where(Alert.agent_id == agent.id))
        }
        assert alerts["cpu_high"].severity == "warning"
        assert alerts["memory_high"].severity == "warning"
        assert alerts["disk_high"].severity == "warning"
        assert alerts["temperature_high"].severity == "warning"
        engine.evaluate_report(
            db,
            agent,
            system_payload(cpu=95, memory=91, disk=91, temperature=80),
            observed_at + timedelta(minutes=2),
        )
        db.commit()
        alerts = {
            alert.kind: alert
            for alert in db.scalars(select(Alert).where(Alert.agent_id == agent.id))
        }
        assert alerts["cpu_high"].severity == "critical"
        assert alerts["memory_high"].severity == "critical"
        assert alerts["disk_high"].severity == "critical"
        assert alerts["temperature_high"].severity == "critical"


def test_alert_payload_severity_uses_current_value() -> None:
    assert alert_payload_severity("cpu_high", 96, "warning") == "critical"
    assert alert_payload_severity("cpu_high", 75, "critical") == "warning"
    assert alert_payload_severity("agent_offline", 120, "high") == "warning"
