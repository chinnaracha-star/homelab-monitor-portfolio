from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from homelab_monitor.auth.dependencies import require_roles
from homelab_monitor.database import get_db
from homelab_monitor.errors import APIError
from homelab_monitor.history import (
    csv_filename,
    default_history_window,
    query_history_points,
    render_history_csv,
)
from homelab_monitor.models import Agent
from homelab_monitor.schemas import MetricHistoryResponse

router = APIRouter(
    prefix="/api/v1",
    tags=["history"],
    dependencies=[Depends(require_roles("admin", "operator", "viewer"))],
)

IntervalQuery = Annotated[
    Literal["1m", "5m", "15m", "1h"],
    Query(description="Aggregation bucket size"),
]


def _load_agent(db: Session, agent_id: str) -> Agent:
    agent = db.scalar(select(Agent).where(Agent.id == agent_id))
    if agent is None:
        raise APIError(404, "agent_not_found", "The requested agent does not exist")
    return agent


def _window(
    from_time: datetime | None,
    to_time: datetime | None,
) -> tuple[datetime, datetime]:
    start, end = default_history_window()
    if from_time is not None:
        start = from_time
    if to_time is not None:
        end = to_time
    if start.tzinfo is None:
        start = start.replace(tzinfo=UTC)
    if end.tzinfo is None:
        end = end.replace(tzinfo=UTC)
    if start > end:
        raise APIError(400, "invalid_time_range", "The from timestamp must be before to")
    return start, end


@router.get(
    "/history/agents/{agent_id}",
    response_model=MetricHistoryResponse,
    summary="Get aggregated metric history for an agent",
)
def get_agent_history(
    agent_id: str,
    interval: IntervalQuery,
    db: Annotated[Session, Depends(get_db)],
    from_time: Annotated[datetime | None, Query(alias="from")] = None,
    to_time: Annotated[datetime | None, Query(alias="to")] = None,
) -> MetricHistoryResponse:
    _load_agent(db, agent_id)
    start, end = _window(from_time, to_time)
    points = query_history_points(
        db,
        agent_id=agent_id,
        start=start,
        end=end,
        interval=interval,
    )
    return MetricHistoryResponse.model_validate(
        {
            "agent_id": agent_id,
            "interval": interval,
            "from": start,
            "to": end,
            "points": points,
        }
    )


@router.get(
    "/history/agents/{agent_id}/export",
    summary="Export aggregated metric history as CSV",
)
def export_agent_history(
    agent_id: str,
    interval: IntervalQuery,
    db: Annotated[Session, Depends(get_db)],
    from_time: Annotated[datetime | None, Query(alias="from")] = None,
    to_time: Annotated[datetime | None, Query(alias="to")] = None,
) -> Response:
    agent = _load_agent(db, agent_id)
    start, end = _window(from_time, to_time)
    points = query_history_points(
        db,
        agent_id=agent_id,
        start=start,
        end=end,
        interval=interval,
    )
    filename = csv_filename(agent.name)
    return Response(
        content=render_history_csv(points),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
