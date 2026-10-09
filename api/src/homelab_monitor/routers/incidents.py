from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from homelab_monitor.alert_correlation import get_incident, incident_statistics, incident_summaries
from homelab_monitor.auth.dependencies import require_roles
from homelab_monitor.database import get_db
from homelab_monitor.errors import APIError
from homelab_monitor.schemas import (
    IncidentDetailResponse,
    IncidentStatisticsResponse,
    IncidentSummaryResponse,
)

router = APIRouter(prefix="/api/v1/incidents", tags=["incidents"])
READ = Depends(require_roles("admin", "operator", "viewer"))


@router.get("", response_model=list[IncidentSummaryResponse], dependencies=[READ])
def list_incidents(db: Annotated[Session, Depends(get_db)]) -> list[IncidentSummaryResponse]:
    return incident_summaries(db)


@router.get("/statistics", response_model=IncidentStatisticsResponse, dependencies=[READ])
def get_incident_statistics(
    db: Annotated[Session, Depends(get_db)],
) -> IncidentStatisticsResponse:
    return incident_statistics(db)


@router.get("/{incident_id}", response_model=IncidentDetailResponse, dependencies=[READ])
def read_incident(
    incident_id: str,
    db: Annotated[Session, Depends(get_db)],
) -> IncidentDetailResponse:
    item = get_incident(db, incident_id)
    if item is None:
        raise APIError(404, "incident_not_found", "The requested incident does not exist")
    return item
