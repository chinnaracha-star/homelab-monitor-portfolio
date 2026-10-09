from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from homelab_monitor.alert_engine import as_alert_utc
from homelab_monitor.alert_history import list_alert_history
from homelab_monitor.schemas import (
    AlertHistoryEntry,
    IncidentDetailResponse,
    IncidentStatisticsResponse,
    IncidentSummaryResponse,
)

WINDOW = timedelta(minutes=5)
RELATED_KINDS = {"cpu_high", "memory_high", "temperature_high", "disk_high"}
SEVERITY_RANK = {"info": 1, "warning": 2, "critical": 3}


def _incident_id(agent_id: str, first_alert_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"homelab-incident:{agent_id}:{first_alert_id}"))


def _highest_severity(items: list[AlertHistoryEntry]) -> str:
    best = "info"
    for item in items:
        if SEVERITY_RANK.get(item.severity, 0) > SEVERITY_RANK.get(best, 0):
            best = item.severity
    return best


def _to_incident(items: list[AlertHistoryEntry], now: datetime) -> IncidentDetailResponse:
    ordered = sorted(items, key=lambda item: (item.started_at, item.id))
    first = ordered[0]
    recovered = all(item.status == "recovered" for item in ordered)
    recovered_at = None
    if recovered:
        stamps = [item.recovered_at for item in ordered if item.recovered_at is not None]
        recovered_at = max(stamps) if stamps else None
    start = first.started_at
    end = recovered_at if recovered and recovered_at is not None else now
    duration = max(0, int((as_alert_utc(end) - as_alert_utc(start)).total_seconds()))
    kinds = [item.alert_type for item in ordered]
    cause = max(set(kinds), key=kinds.count)
    return IncidentDetailResponse(
        id=_incident_id(first.agent_id, first.id),
        started_at=start,
        recovered_at=recovered_at,
        duration_seconds=duration,
        agent_id=first.agent_id,
        agent_name=first.agent_name,
        severity=_highest_severity(ordered),
        status="recovered" if recovered else "active",
        affected_alerts=ordered,
        alert_count=len(ordered),
        cause=cause,
    )


def correlate_incidents(
    db: Session,
    *,
    now: datetime | None = None,
) -> list[IncidentDetailResponse]:
    clock = now or datetime.now(UTC)
    entries = list_alert_history(db, now=clock)
    by_agent: dict[str, list[AlertHistoryEntry]] = defaultdict(list)
    for entry in entries:
        by_agent[entry.agent_id].append(entry)
    incidents: list[IncidentDetailResponse] = []
    for agent_entries in by_agent.values():
        related = [
            item
            for item in sorted(agent_entries, key=lambda item: (item.started_at, item.id))
            if item.alert_type in RELATED_KINDS
        ]
        others = [item for item in agent_entries if item.alert_type not in RELATED_KINDS]
        clusters: list[list[AlertHistoryEntry]] = []
        for item in related:
            placed = False
            for cluster in clusters:
                first = cluster[0]
                if abs(as_alert_utc(item.started_at) - as_alert_utc(first.started_at)) <= WINDOW:
                    cluster.append(item)
                    placed = True
                    break
            if not placed:
                clusters.append([item])
        for cluster in clusters:
            incidents.append(_to_incident(cluster, clock))
        for item in others:
            incidents.append(_to_incident([item], clock))
    incidents.sort(key=lambda item: (item.started_at, item.id), reverse=True)
    return incidents


def incident_summaries(
    db: Session, *, now: datetime | None = None
) -> list[IncidentSummaryResponse]:
    return [
        IncidentSummaryResponse(
            id=item.id,
            started_at=item.started_at,
            recovered_at=item.recovered_at,
            duration_seconds=item.duration_seconds,
            agent_id=item.agent_id,
            agent_name=item.agent_name,
            severity=item.severity,
            status=item.status,
            alert_count=item.alert_count,
            cause=item.cause,
        )
        for item in correlate_incidents(db, now=now)
    ]


def get_incident(
    db: Session, incident_id: str, *, now: datetime | None = None
) -> IncidentDetailResponse | None:
    for item in correlate_incidents(db, now=now):
        if item.id == incident_id:
            return item
    return None


def incident_statistics(db: Session, *, now: datetime | None = None) -> IncidentStatisticsResponse:
    items = correlate_incidents(db, now=now)
    durations = [item.duration_seconds for item in items if item.duration_seconds is not None]
    average = round(sum(durations) / len(durations), 2) if durations else 0.0
    agents = [item.agent_name for item in items]
    top = max(set(agents), key=agents.count) if agents else ""
    return IncidentStatisticsResponse(
        average_duration_seconds=average,
        open_count=sum(1 for item in items if item.status == "active"),
        recovered_count=sum(1 for item in items if item.status == "recovered"),
        critical_count=sum(1 for item in items if item.severity == "critical"),
        warning_count=sum(1 for item in items if item.severity == "warning"),
        incident_count=len(items),
        top_affected_agent=top,
    )
