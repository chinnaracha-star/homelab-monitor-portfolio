from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from homelab_monitor.alert_history import alert_statistics, list_alert_history
from homelab_monitor.auth.dependencies import require_roles
from homelab_monitor.database import get_db
from homelab_monitor.schemas import AlertHistoryEntry, AlertStatisticsResponse

router = APIRouter(prefix="/api/v1/alerts", tags=["alerts"])
READ = Depends(require_roles("admin", "operator", "viewer"))


@router.get("/history", response_model=list[AlertHistoryEntry], dependencies=[READ])
def get_alert_history(
    db: Annotated[Session, Depends(get_db)],
    status: Annotated[str | None, Query()] = None,
    severity: Annotated[str | None, Query()] = None,
    agent_id: Annotated[str | None, Query()] = None,
    alert_type: Annotated[str | None, Query()] = None,
    on_date: Annotated[date | None, Query(alias="date")] = None,
) -> list[AlertHistoryEntry]:
    return list_alert_history(
        db,
        status=status,
        severity=severity,
        agent_id=agent_id,
        alert_type=alert_type,
        date=on_date.isoformat() if on_date else None,
    )


@router.get("/statistics", response_model=AlertStatisticsResponse, dependencies=[READ])
def get_alert_statistics(db: Annotated[Session, Depends(get_db)]) -> AlertStatisticsResponse:
    return alert_statistics(db)
