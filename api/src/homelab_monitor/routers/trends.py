from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from homelab_monitor.auth.dependencies import require_roles
from homelab_monitor.database import get_db
from homelab_monitor.schemas import (
    TrendBackupResponse,
    TrendCpuResponse,
    TrendMemoryResponse,
    TrendOverviewResponse,
    TrendPhotosResponse,
    TrendStorageResponse,
)
from homelab_monitor.trends import TrendService

router = APIRouter(prefix="/api/v1/trends", tags=["trends"])
READ = Depends(require_roles("admin", "operator", "viewer"))
service = TrendService()


@router.get("/overview", response_model=TrendOverviewResponse, dependencies=[READ])
def get_trends_overview(db: Annotated[Session, Depends(get_db)]) -> TrendOverviewResponse:
    return service.overview(db)


@router.get("/cpu", response_model=TrendCpuResponse, dependencies=[READ])
def get_trends_cpu(db: Annotated[Session, Depends(get_db)]) -> TrendCpuResponse:
    return service.cpu(db)


@router.get("/memory", response_model=TrendMemoryResponse, dependencies=[READ])
def get_trends_memory(db: Annotated[Session, Depends(get_db)]) -> TrendMemoryResponse:
    return service.memory(db)


@router.get("/storage", response_model=TrendStorageResponse, dependencies=[READ])
def get_trends_storage(db: Annotated[Session, Depends(get_db)]) -> TrendStorageResponse:
    return service.storage(db)


@router.get("/photos", response_model=TrendPhotosResponse, dependencies=[READ])
def get_trends_photos(db: Annotated[Session, Depends(get_db)]) -> TrendPhotosResponse:
    return service.photos(db)


@router.get("/backup", response_model=TrendBackupResponse, dependencies=[READ])
def get_trends_backup(db: Annotated[Session, Depends(get_db)]) -> TrendBackupResponse:
    return service.backup(db)
