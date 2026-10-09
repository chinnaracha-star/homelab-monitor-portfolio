from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from homelab_monitor.models import Agent, MetricReport
from homelab_monitor.schemas import AgentSummaryResponse
from homelab_monitor.settings import get_settings


@dataclass(frozen=True)
class AgentPresence:
    status: str
    last_seen_at: datetime | None
    last_report_at: datetime | None
    contact_at: datetime | None


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def later(*values: datetime | None) -> datetime | None:
    stamps = [as_utc(value) for value in values if value is not None]
    if not stamps:
        return None
    return max(stamps)


def latest_report_times(db: Session) -> dict[str, datetime]:
    rows = db.execute(
        select(MetricReport.agent_id, func.max(MetricReport.received_at)).group_by(
            MetricReport.agent_id
        )
    ).all()
    return {
        agent_id: as_utc(received_at)
        for agent_id, received_at in rows
        if agent_id is not None and received_at is not None
    }


def latest_report_time(db: Session, agent_id: str) -> datetime | None:
    received_at = db.scalar(
        select(func.max(MetricReport.received_at)).where(MetricReport.agent_id == agent_id)
    )
    return as_utc(received_at) if received_at is not None else None


def presence_of(
    last_seen_at: datetime | None,
    last_report_at: datetime | None,
    *,
    now: datetime,
    timeout_seconds: int,
) -> AgentPresence:
    last_seen = as_utc(last_seen_at) if last_seen_at is not None else None
    last_report = as_utc(last_report_at) if last_report_at is not None else None
    contact_at = later(last_seen, last_report)
    if contact_at is None:
        return AgentPresence("registered", last_seen, last_report, None)
    elapsed = (as_utc(now) - contact_at).total_seconds()
    status = "online" if elapsed <= timeout_seconds else "offline"
    return AgentPresence(status, last_seen, last_report, contact_at)


def presence_for_agents(
    db: Session,
    agents: Sequence[Agent],
    *,
    now: datetime | None = None,
    timeout_seconds: int | None = None,
) -> dict[str, AgentPresence]:
    clock = now or datetime.now(UTC)
    timeout = (
        timeout_seconds
        if timeout_seconds is not None
        else get_settings().agent_offline_after_seconds
    )
    reports = latest_report_times(db)
    return {
        agent.id: presence_of(
            agent.last_seen_at,
            reports.get(agent.id),
            now=clock,
            timeout_seconds=timeout,
        )
        for agent in agents
    }


def agent_presence_map(
    db: Session,
    *,
    now: datetime | None = None,
    timeout_seconds: int | None = None,
) -> dict[str, AgentPresence]:
    agents = list(db.scalars(select(Agent)).all())
    return presence_for_agents(db, agents, now=now, timeout_seconds=timeout_seconds)


def online_count(presences: dict[str, AgentPresence]) -> int:
    return sum(1 for item in presences.values() if item.status == "online")


def to_agent_summary(agent: Agent, presence: AgentPresence) -> AgentSummaryResponse:
    return AgentSummaryResponse(
        id=agent.id,
        name=agent.name,
        hostname=agent.hostname,
        version=agent.version,
        status=presence.status,
        last_seen_at=agent.last_seen_at,
    )
