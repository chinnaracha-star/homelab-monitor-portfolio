from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from homelab_monitor.agent_presence import (
    latest_report_time,
    online_count,
    presence_for_agents,
    presence_of,
    to_agent_summary,
)
from homelab_monitor.alert_engine import alert_duration_seconds
from homelab_monitor.alert_severity import alert_payload_severity
from homelab_monitor.auth.dependencies import require_roles
from homelab_monitor.database import get_db
from homelab_monitor.errors import APIError
from homelab_monitor.models import Agent, AgentGroup, AgentGroupMember, Alert, MetricReport
from homelab_monitor.realtime import hub
from homelab_monitor.schemas import (
    ActiveAlertResponse,
    AgentCountResponse,
    AgentDetailResponse,
    AgentSummaryResponse,
    AlertAcknowledgeResponse,
    DashboardOverviewResponse,
    GroupCountResponse,
    GroupOverviewItem,
    LatestMetricReportResponse,
    ReportCountResponse,
)
from homelab_monitor.settings import get_settings

router = APIRouter(
    prefix="/api/v1",
    tags=["dashboard"],
    dependencies=[Depends(require_roles("admin", "operator", "viewer"))],
)


@router.get(
    "/dashboard/overview",
    response_model=DashboardOverviewResponse,
    summary="Get dashboard summary counts",
)
def get_dashboard_overview(
    db: Annotated[Session, Depends(get_db)],
) -> DashboardOverviewResponse:
    agents = list(db.scalars(select(Agent)).all())
    presences = presence_for_agents(db, agents)
    total_agents = len(agents)
    online_agents = online_count(presences)
    total_reports = db.scalar(select(func.count()).select_from(MetricReport)) or 0
    total_groups = db.scalar(select(func.count()).select_from(AgentGroup)) or 0
    group_rows = db.execute(
        select(AgentGroup.id, AgentGroup.name).order_by(AgentGroup.name.asc())
    ).all()
    memberships = db.execute(
        select(AgentGroupMember.group_id, Agent.id).join(
            Agent, Agent.id == AgentGroupMember.agent_id
        )
    ).all()
    counts: dict[str, list[int]] = {group_id: [0, 0] for group_id, _ in group_rows}
    for group_id, agent_id in memberships:
        pair = counts.get(group_id)
        if pair is None:
            continue
        pair[0] += 1
        if presences.get(agent_id) and presences[agent_id].status == "online":
            pair[1] += 1

    return DashboardOverviewResponse(
        agents=AgentCountResponse(
            total=total_agents,
            online=online_agents,
            offline=total_agents - online_agents,
        ),
        reports=ReportCountResponse(total=total_reports),
        groups=GroupCountResponse(total=total_groups),
        group_stats=[
            GroupOverviewItem(
                id=group_id,
                name=name,
                agents=counts[group_id][0],
                online=counts[group_id][1],
            )
            for group_id, name in group_rows
        ],
    )


@router.get(
    "/agents",
    response_model=list[AgentSummaryResponse],
    summary="List monitored agents",
)
def list_agents(db: Annotated[Session, Depends(get_db)]) -> list[AgentSummaryResponse]:
    agents = list(db.scalars(select(Agent).order_by(Agent.name.asc())).all())
    presences = presence_for_agents(db, agents)
    return [to_agent_summary(agent, presences[agent.id]) for agent in agents]


@router.get(
    "/agents/{agent_id}",
    response_model=AgentDetailResponse,
    summary="Get one monitored agent",
)
def get_agent(
    agent_id: str,
    db: Annotated[Session, Depends(get_db)],
) -> AgentDetailResponse:
    agent = db.scalar(
        select(Agent).options(selectinload(Agent.configuration)).where(Agent.id == agent_id)
    )
    if agent is None:
        raise APIError(404, "agent_not_found", "The requested agent does not exist")

    presence = presence_of(
        agent.last_seen_at,
        latest_report_time(db, agent.id),
        now=datetime.now(UTC),
        timeout_seconds=get_settings().agent_offline_after_seconds,
    )
    return AgentDetailResponse(
        id=agent.id,
        name=agent.name,
        hostname=agent.hostname,
        version=agent.version,
        status=presence.status,
        last_seen_at=agent.last_seen_at,
        configuration_revision=agent.configuration.revision if agent.configuration else 0,
        capabilities=agent.capabilities,
    )


@router.get(
    "/agents/{agent_id}/latest-report",
    response_model=LatestMetricReportResponse,
    summary="Get the newest metric report for an agent",
)
def get_latest_agent_report(
    agent_id: str,
    db: Annotated[Session, Depends(get_db)],
) -> MetricReport:
    if db.scalar(select(Agent.id).where(Agent.id == agent_id)) is None:
        raise APIError(404, "agent_not_found", "The requested agent does not exist")

    report = db.scalar(
        select(MetricReport)
        .where(MetricReport.agent_id == agent_id)
        .order_by(
            MetricReport.observed_at.desc(),
            MetricReport.received_at.desc(),
            MetricReport.id.desc(),
        )
        .limit(1)
    )
    if report is None:
        raise APIError(
            404,
            "latest_report_not_found",
            "The requested agent has no metric reports",
        )
    return report


@router.get(
    "/agents/{agent_id}/reports",
    response_model=list[LatestMetricReportResponse],
    summary="Get recent metric reports for an agent",
)
def get_agent_report_history(
    agent_id: str,
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=2, le=100)] = 30,
) -> list[MetricReport]:
    if db.scalar(select(Agent.id).where(Agent.id == agent_id)) is None:
        raise APIError(404, "agent_not_found", "The requested agent does not exist")

    return list(
        db.scalars(
            select(MetricReport)
            .where(MetricReport.agent_id == agent_id)
            .order_by(
                MetricReport.observed_at.desc(),
                MetricReport.received_at.desc(),
                MetricReport.id.desc(),
            )
            .limit(limit)
        ).all()
    )


def _alert_response(
    alert: Alert, agent_name: str, now: datetime | None = None
) -> ActiveAlertResponse:
    clock = now or datetime.now(UTC)
    recovered = alert.status != "active"
    recovered_at = alert.resolved_at if recovered else None
    started_at = alert.opened_at
    return ActiveAlertResponse(
        id=alert.id,
        agent_id=alert.agent_id,
        agent_name=agent_name,
        kind=alert.kind,
        resource=alert.resource,
        severity=(
            alert_payload_severity(alert.kind, alert.current_value, alert.severity)
            if alert.status == "active"
            else alert.severity
        ),
        current_value=alert.current_value,
        threshold=alert.threshold,
        message=alert.message,
        opened_at=alert.opened_at,
        last_observed_at=alert.last_observed_at,
        status="recovered" if recovered else "active",
        started_at=started_at,
        last_triggered_at=alert.last_observed_at,
        recovered_at=recovered_at,
        duration_seconds=alert_duration_seconds(
            started_at,
            recovered_at,
            clock,
            recovered=recovered,
        ),
    )


@router.get(
    "/alerts/active",
    response_model=list[ActiveAlertResponse],
    summary="List active alerts",
)
def list_active_alerts(
    db: Annotated[Session, Depends(get_db)],
    include_recovered: Annotated[bool, Query()] = False,
) -> list[ActiveAlertResponse]:
    query = select(Alert, Agent.name).join(Agent, Alert.agent_id == Agent.id)
    if not include_recovered:
        query = query.where(Alert.status == "active")
    rows = db.execute(query.order_by(Alert.opened_at.desc(), Alert.id.desc())).all()
    now = datetime.now(UTC)
    return [_alert_response(alert, agent_name, now) for alert, agent_name in rows]


@router.post(
    "/alerts/{alert_id}/acknowledge",
    response_model=AlertAcknowledgeResponse,
    dependencies=[Depends(require_roles("admin", "operator"))],
    summary="Acknowledge an active alert",
)
def acknowledge_alert(
    alert_id: str,
    db: Annotated[Session, Depends(get_db)],
) -> Alert:
    alert = db.scalar(select(Alert).where(Alert.id == alert_id))
    if alert is None:
        raise APIError(404, "alert_not_found", "The requested alert does not exist")
    hub.publish("alert_updated", reason="acknowledge", agent_id=alert.agent_id)
    return alert
