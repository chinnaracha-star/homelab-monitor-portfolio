from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from homelab_monitor.auth.dependencies import require_roles
from homelab_monitor.database import get_db
from homelab_monitor.predictions import PredictionService
from homelab_monitor.schemas import PredictionMetricResponse, PredictionOverviewResponse

router = APIRouter(prefix="/api/v1/predictions", tags=["predictions"])
READ = Depends(require_roles("admin", "operator", "viewer"))
service = PredictionService()


@router.get("/overview", response_model=PredictionOverviewResponse, dependencies=[READ])
def get_predictions_overview(
    db: Annotated[Session, Depends(get_db)],
) -> PredictionOverviewResponse:
    return service.overview(db)


@router.get("/storage", response_model=PredictionMetricResponse, dependencies=[READ])
def get_predictions_storage(db: Annotated[Session, Depends(get_db)]) -> PredictionMetricResponse:
    return service.storage(db)


@router.get("/system", response_model=PredictionMetricResponse, dependencies=[READ])
def get_predictions_system(db: Annotated[Session, Depends(get_db)]) -> PredictionMetricResponse:
    return service.system(db)


@router.get("/photos", response_model=PredictionMetricResponse, dependencies=[READ])
def get_predictions_photos(db: Annotated[Session, Depends(get_db)]) -> PredictionMetricResponse:
    return service.photos(db)


@router.get("/backup", response_model=PredictionMetricResponse, dependencies=[READ])
def get_predictions_backup(db: Annotated[Session, Depends(get_db)]) -> PredictionMetricResponse:
    return service.backup(db)
