from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from homelab_monitor.analytics import AnalyticsService
from homelab_monitor.auth.dependencies import require_roles
from homelab_monitor.database import get_db
from homelab_monitor.schemas import (
    AnalyticsBackupResponse,
    AnalyticsCpuResponse,
    AnalyticsMemoryResponse,
    AnalyticsOverviewResponse,
    AnalyticsPhotosResponse,
    AnalyticsStorageResponse,
    AnalyticsTemperatureResponse,
)

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])
READ = Depends(require_roles("admin", "operator", "viewer"))
service = AnalyticsService()


@router.get(
    "/overview",
    response_model=AnalyticsOverviewResponse,
    dependencies=[READ],
    summary="Get analytics summary cards",
)
def get_analytics_overview(db: Annotated[Session, Depends(get_db)]) -> AnalyticsOverviewResponse:
    return service.overview(db)


@router.get(
    "/cpu",
    response_model=AnalyticsCpuResponse,
    dependencies=[READ],
    summary="Get CPU analytics",
)
def get_analytics_cpu(db: Annotated[Session, Depends(get_db)]) -> AnalyticsCpuResponse:
    return service.cpu(db)


@router.get(
    "/memory",
    response_model=AnalyticsMemoryResponse,
    dependencies=[READ],
    summary="Get memory analytics",
)
def get_analytics_memory(db: Annotated[Session, Depends(get_db)]) -> AnalyticsMemoryResponse:
    return service.memory(db)


@router.get(
    "/storage",
    response_model=AnalyticsStorageResponse,
    dependencies=[READ],
    summary="Get storage analytics",
)
def get_analytics_storage(db: Annotated[Session, Depends(get_db)]) -> AnalyticsStorageResponse:
    return service.storage(db)


@router.get(
    "/temperature",
    response_model=AnalyticsTemperatureResponse,
    dependencies=[READ],
    summary="Get temperature analytics",
)
def get_analytics_temperature(
    db: Annotated[Session, Depends(get_db)],
) -> AnalyticsTemperatureResponse:
    return service.temperature(db)


@router.get(
    "/photos",
    response_model=AnalyticsPhotosResponse,
    dependencies=[READ],
    summary="Get photo growth analytics",
)
def get_analytics_photos(db: Annotated[Session, Depends(get_db)]) -> AnalyticsPhotosResponse:
    return service.photos(db)


@router.get(
    "/backup",
    response_model=AnalyticsBackupResponse,
    dependencies=[READ],
    summary="Get backup analytics",
)
def get_analytics_backup(db: Annotated[Session, Depends(get_db)]) -> AnalyticsBackupResponse:
    return service.backup(db)
