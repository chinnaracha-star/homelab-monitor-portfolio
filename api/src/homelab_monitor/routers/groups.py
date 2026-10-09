from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from homelab_monitor.agent_presence import presence_for_agents, to_agent_summary
from homelab_monitor.auth.dependencies import require_roles
from homelab_monitor.database import get_db
from homelab_monitor.errors import APIError
from homelab_monitor.models import Agent, AgentGroup, AgentGroupMember
from homelab_monitor.realtime import hub
from homelab_monitor.schemas import (
    GroupCreateRequest,
    GroupDetailResponse,
    GroupMembershipRequest,
    GroupSummaryListResponse,
    GroupSummaryResponse,
    GroupUpdateRequest,
)

router = APIRouter(prefix="/api/v1", tags=["groups"])

GROUP_READ = Depends(require_roles("admin", "operator", "viewer"))
GROUP_WRITE = Depends(require_roles("admin", "operator"))


def _load_group(db: Session, group_id: str) -> AgentGroup:
    group = db.scalar(select(AgentGroup).where(AgentGroup.id == group_id))
    if group is None:
        raise APIError(404, "group_not_found", "The requested group does not exist")
    return group


def _membership_stats(db: Session) -> dict[str, tuple[int, int, list[str]]]:
    agents = list(db.scalars(select(Agent)).all())
    presences = presence_for_agents(db, agents)
    rows = db.execute(
        select(
            AgentGroupMember.group_id,
            Agent.id,
        ).join(Agent, Agent.id == AgentGroupMember.agent_id)
    ).all()
    stats: dict[str, tuple[int, int, list[str]]] = {}
    for group_id, agent_id in rows:
        total, online, agent_ids = stats.get(group_id, (0, 0, []))
        presence = presences.get(agent_id)
        stats[group_id] = (
            total + 1,
            online + (1 if presence is not None and presence.status == "online" else 0),
            [*agent_ids, agent_id],
        )
    return stats


def _to_summary(
    group: AgentGroup,
    stats: dict[str, tuple[int, int, list[str]]],
) -> GroupSummaryResponse:
    total, online, agent_ids = stats.get(group.id, (0, 0, []))
    return GroupSummaryResponse(
        id=group.id,
        name=group.name,
        description=group.description,
        agents=total,
        online=online,
        agent_ids=agent_ids,
    )


def _notify_groups() -> None:
    hub.publish("overview_updated", reason="group_updated")
    hub.publish("agent_updated", reason="group_updated")


def _detail(db: Session, group_id: str) -> GroupDetailResponse:
    group = db.scalar(
        select(AgentGroup)
        .options(selectinload(AgentGroup.memberships).selectinload(AgentGroupMember.agent))
        .where(AgentGroup.id == group_id)
    )
    if group is None:
        raise APIError(404, "group_not_found", "The requested group does not exist")

    members = sorted(
        (membership.agent for membership in group.memberships),
        key=lambda item: item.name,
    )
    presences = presence_for_agents(db, members)
    online = sum(1 for agent in members if presences[agent.id].status == "online")
    return GroupDetailResponse(
        id=group.id,
        name=group.name,
        description=group.description,
        agents=len(members),
        online=online,
        agent_ids=[agent.id for agent in members],
        created_at=group.created_at,
        updated_at=group.updated_at,
        members=[to_agent_summary(agent, presences[agent.id]) for agent in members],
    )


@router.get(
    "/groups/summary",
    response_model=GroupSummaryListResponse,
    dependencies=[GROUP_READ],
    summary="Get agent counts per group",
)
def get_groups_summary(db: Annotated[Session, Depends(get_db)]) -> GroupSummaryListResponse:
    groups = list(db.scalars(select(AgentGroup).order_by(AgentGroup.name.asc())).all())
    stats = _membership_stats(db)
    summaries = [_to_summary(group, stats) for group in groups]
    return GroupSummaryListResponse(total=len(summaries), groups=summaries)


@router.get(
    "/groups",
    response_model=list[GroupSummaryResponse],
    dependencies=[GROUP_READ],
    summary="List agent groups",
)
def list_groups(db: Annotated[Session, Depends(get_db)]) -> list[GroupSummaryResponse]:
    groups = list(db.scalars(select(AgentGroup).order_by(AgentGroup.name.asc())).all())
    stats = _membership_stats(db)
    return [_to_summary(group, stats) for group in groups]


@router.post(
    "/groups",
    response_model=GroupDetailResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[GROUP_WRITE],
    summary="Create an agent group",
)
def create_group(
    payload: GroupCreateRequest,
    db: Annotated[Session, Depends(get_db)],
) -> GroupDetailResponse:
    if db.scalar(select(AgentGroup.id).where(AgentGroup.name == payload.name)) is not None:
        raise APIError(409, "group_name_exists", "A group with this name already exists")

    group = AgentGroup(name=payload.name, description=payload.description)
    db.add(group)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise APIError(409, "group_name_exists", "A group with this name already exists") from error
    db.refresh(group)
    _notify_groups()
    return _detail(db, group.id)


@router.get(
    "/groups/{group_id}",
    response_model=GroupDetailResponse,
    dependencies=[GROUP_READ],
    summary="Get one agent group",
)
def get_group(group_id: str, db: Annotated[Session, Depends(get_db)]) -> GroupDetailResponse:
    return _detail(db, group_id)


@router.put(
    "/groups/{group_id}",
    response_model=GroupDetailResponse,
    dependencies=[GROUP_WRITE],
    summary="Update an agent group",
)
def update_group(
    group_id: str,
    payload: GroupUpdateRequest,
    db: Annotated[Session, Depends(get_db)],
) -> GroupDetailResponse:
    group = _load_group(db, group_id)
    taken = db.scalar(
        select(AgentGroup.id).where(AgentGroup.name == payload.name, AgentGroup.id != group_id)
    )
    if taken is not None:
        raise APIError(409, "group_name_exists", "A group with this name already exists")

    group.name = payload.name
    group.description = payload.description
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise APIError(409, "group_name_exists", "A group with this name already exists") from error
    _notify_groups()
    return _detail(db, group_id)


@router.delete(
    "/groups/{group_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[GROUP_WRITE],
    summary="Delete an agent group",
)
def delete_group(group_id: str, db: Annotated[Session, Depends(get_db)]) -> Response:
    group = _load_group(db, group_id)
    db.delete(group)
    db.commit()
    _notify_groups()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/groups/{group_id}/agents",
    response_model=GroupDetailResponse,
    dependencies=[GROUP_WRITE],
    summary="Assign agents to a group",
)
def assign_agents(
    group_id: str,
    payload: GroupMembershipRequest,
    db: Annotated[Session, Depends(get_db)],
) -> GroupDetailResponse:
    _load_group(db, group_id)
    unique_ids = list(dict.fromkeys(payload.agent_ids))
    found = list(db.scalars(select(Agent).where(Agent.id.in_(unique_ids))).all())
    found_ids = {agent.id for agent in found}
    missing = [agent_id for agent_id in unique_ids if agent_id not in found_ids]
    if missing:
        raise APIError(
            404,
            "agent_not_found",
            "One or more agents do not exist",
            {"agent_ids": missing},
        )

    existing = set(
        db.scalars(
            select(AgentGroupMember.agent_id).where(
                AgentGroupMember.group_id == group_id,
                AgentGroupMember.agent_id.in_(unique_ids),
            )
        ).all()
    )
    for agent_id in unique_ids:
        if agent_id in existing:
            continue
        db.add(AgentGroupMember(group_id=group_id, agent_id=agent_id))
    db.commit()
    _notify_groups()
    return _detail(db, group_id)


@router.delete(
    "/groups/{group_id}/agents/{agent_id}",
    response_model=GroupDetailResponse,
    dependencies=[GROUP_WRITE],
    summary="Remove an agent from a group",
)
def remove_agent(
    group_id: str,
    agent_id: str,
    db: Annotated[Session, Depends(get_db)],
) -> GroupDetailResponse:
    _load_group(db, group_id)
    membership = db.scalar(
        select(AgentGroupMember).where(
            AgentGroupMember.group_id == group_id,
            AgentGroupMember.agent_id == agent_id,
        )
    )
    if membership is None:
        raise APIError(404, "group_member_not_found", "The agent is not a member of this group")
    db.delete(membership)
    db.commit()
    _notify_groups()
    return _detail(db, group_id)
