from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from homelab_monitor.alert_engine import alert_duration_seconds, as_alert_utc
from homelab_monitor.alert_severity import alert_payload_severity
from homelab_monitor.models import Agent, Alert
from homelab_monitor.schemas import AlertHistoryEntry, AlertStatisticsResponse


def _lifecycle_status(alert: Alert) -> str:
    return "recovered" if alert.status != "active" else "active"


def to_history_entry(
    alert: Alert,
    agent_name: str,
    now: datetime,
) -> AlertHistoryEntry:
    recovered = alert.status != "active"
    recovered_at = alert.resolved_at if recovered else None
    started_at = alert.opened_at
    return AlertHistoryEntry(
        id=alert.id,
        alert_type=alert.kind,
        severity=(
            alert_payload_severity(alert.kind, alert.current_value, alert.severity)
            if alert.status == "active"
            else alert.severity
        ),
        started_at=started_at,
        recovered_at=recovered_at,
        duration_seconds=alert_duration_seconds(
            started_at,
            recovered_at,
            now,
            recovered=recovered,
        ),
        agent_id=alert.agent_id,
        agent_name=agent_name,
        source=alert.resource or "system",
        threshold=alert.threshold,
        peak_value=alert.current_value,
        status=_lifecycle_status(alert),
    )


def _date_bounds(value: str) -> tuple[datetime, datetime] | None:
    try:
        day = datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=UTC)
    except ValueError:
        return None
    return day, day + timedelta(days=1)


def list_alert_history(
    db: Session,
    *,
    status: str | None = None,
    severity: str | None = None,
    agent_id: str | None = None,
    alert_type: str | None = None,
    date: str | None = None,
    now: datetime | None = None,
) -> list[AlertHistoryEntry]:
    clock = now or datetime.now(UTC)
    query = select(Alert, Agent.name).join(Agent, Alert.agent_id == Agent.id)
    if agent_id:
        query = query.where(Alert.agent_id == agent_id)
    if alert_type:
        query = query.where(Alert.kind == alert_type)
    if severity:
        query = query.where(Alert.severity == severity)
    if status == "active":
        query = query.where(Alert.status == "active")
    elif status == "recovered":
        query = query.where(Alert.status != "active")
    bounds = _date_bounds(date) if date else None
    if bounds is not None:
        start, end = bounds
        query = query.where(Alert.opened_at >= start, Alert.opened_at < end)
    rows = db.execute(query.order_by(Alert.opened_at.desc(), Alert.id.desc())).all()
    return [to_history_entry(alert, name, clock) for alert, name in rows]


def alert_statistics(db: Session, *, now: datetime | None = None) -> AlertStatisticsResponse:
    clock = now or datetime.now(UTC)
    entries = list_alert_history(db, now=clock)
    total = len(entries)
    recovered = [item for item in entries if item.status == "recovered"]
    active = [item for item in entries if item.status == "active"]
    start_today = clock.astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    recovered_today = 0
    for item in recovered:
        if item.recovered_at is None:
            continue
        recovered_at = as_alert_utc(item.recovered_at)
        if recovered_at >= start_today:
            recovered_today += 1
    durations = [item.duration_seconds for item in entries if item.duration_seconds is not None]
    average = round(sum(durations) / len(durations), 2) if durations else 0.0
    rate = round((len(recovered) / total) * 100, 2) if total else 0.0
    return AlertStatisticsResponse(
        active_alerts=len(active),
        recovered_today=recovered_today,
        average_duration_seconds=average,
        critical_count=sum(1 for item in entries if item.severity == "critical"),
        warning_count=sum(1 for item in entries if item.severity == "warning"),
        recovery_rate=rate,
        recovered=len(recovered),
        total=total,
    )
