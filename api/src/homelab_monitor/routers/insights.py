from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from homelab_monitor.auth.dependencies import require_roles
from homelab_monitor.database import get_db
from homelab_monitor.insights import InsightService
from homelab_monitor.schemas import (
    InsightBackupResponse,
    InsightOverviewResponse,
    InsightPhotosResponse,
    InsightStorageResponse,
    InsightSystemResponse,
)

router = APIRouter(prefix="/api/v1/insights", tags=["insights"])
READ = Depends(require_roles("admin", "operator", "viewer"))
service = InsightService()


@router.get("/overview", response_model=InsightOverviewResponse, dependencies=[READ])
def get_insights_overview(db: Annotated[Session, Depends(get_db)]) -> InsightOverviewResponse:
    return service.overview(db)


@router.get("/storage", response_model=InsightStorageResponse, dependencies=[READ])
def get_insights_storage(db: Annotated[Session, Depends(get_db)]) -> InsightStorageResponse:
    return service.storage(db)


@router.get("/system", response_model=InsightSystemResponse, dependencies=[READ])
def get_insights_system(db: Annotated[Session, Depends(get_db)]) -> InsightSystemResponse:
    return service.system(db)


@router.get("/photos", response_model=InsightPhotosResponse, dependencies=[READ])
def get_insights_photos(db: Annotated[Session, Depends(get_db)]) -> InsightPhotosResponse:
    return service.photos(db)


@router.get("/backup", response_model=InsightBackupResponse, dependencies=[READ])
def get_insights_backup(db: Annotated[Session, Depends(get_db)]) -> InsightBackupResponse:
    return service.backup(db)
