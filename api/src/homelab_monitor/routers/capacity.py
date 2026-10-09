from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from homelab_monitor.auth.dependencies import require_roles
from homelab_monitor.capacity_planning import CapacityPlanningService
from homelab_monitor.database import get_db
from homelab_monitor.schemas import (
    CapacityBackupResponse,
    CapacityOverviewResponse,
    CapacityPhotosResponse,
    CapacityStorageResponse,
    CapacitySystemResponse,
)

router = APIRouter(prefix="/api/v1/capacity", tags=["capacity"])
READ = Depends(require_roles("admin", "operator", "viewer"))
service = CapacityPlanningService()


@router.get("/overview", response_model=CapacityOverviewResponse, dependencies=[READ])
def get_capacity_overview(db: Annotated[Session, Depends(get_db)]) -> CapacityOverviewResponse:
    return service.overview(db)


@router.get("/storage", response_model=CapacityStorageResponse, dependencies=[READ])
def get_capacity_storage(db: Annotated[Session, Depends(get_db)]) -> CapacityStorageResponse:
    return service.storage(db)


@router.get("/photos", response_model=CapacityPhotosResponse, dependencies=[READ])
def get_capacity_photos(db: Annotated[Session, Depends(get_db)]) -> CapacityPhotosResponse:
    return service.photos(db)


@router.get("/backup", response_model=CapacityBackupResponse, dependencies=[READ])
def get_capacity_backup(db: Annotated[Session, Depends(get_db)]) -> CapacityBackupResponse:
    return service.backup(db)


@router.get("/system", response_model=CapacitySystemResponse, dependencies=[READ])
def get_capacity_system(db: Annotated[Session, Depends(get_db)]) -> CapacitySystemResponse:
    return service.system(db)
