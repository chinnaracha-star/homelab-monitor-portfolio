from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from homelab_monitor.auth.dependencies import require_roles
from homelab_monitor.database import get_db
from homelab_monitor.developer_dashboard import DeveloperDashboardService
from homelab_monitor.schemas import DeveloperOverviewResponse

router = APIRouter(prefix="/api/v1/developer", tags=["developer"])
ADMIN = Depends(require_roles("admin"))
service = DeveloperDashboardService()


@router.get("/overview", response_model=DeveloperOverviewResponse, dependencies=[ADMIN])
def get_developer_overview(db: Annotated[Session, Depends(get_db)]) -> DeveloperOverviewResponse:
    return service.overview(db)
