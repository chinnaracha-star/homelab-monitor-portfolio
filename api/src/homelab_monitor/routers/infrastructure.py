import logging
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.exc import SQLAlchemyError

from homelab_monitor.auth.dependencies import require_roles
from homelab_monitor.backup_status import backup_status_from_snapshot
from homelab_monitor.connectors.base import ConnectorSnapshot
from homelab_monitor.errors import APIError
from homelab_monitor.infrastructure import get_infrastructure_service
from homelab_monitor.ops_history import (
    backup_history_periods,
    photo_trends,
    record_backup_snapshot,
    record_photo_snapshot,
)
from homelab_monitor.schemas import (
    BackupStatusResponse,
    InfrastructureSnapshotResponse,
    InfrastructureSummaryResponse,
    PhotoGrowthResponse,
    PhotoServicesResponse,
    PhotoStatsResponse,
    StorageHistoryResponse,
)
from homelab_monitor.settings import Settings, get_settings

router = APIRouter(prefix="/api/v1", tags=["infrastructure"])
READ = Depends(require_roles("admin", "operator", "viewer"))
logger = logging.getLogger(__name__)


def _to_response(snapshot: ConnectorSnapshot) -> InfrastructureSnapshotResponse:
    return InfrastructureSnapshotResponse(
        service=snapshot.service,
        status=snapshot.status,
        version=snapshot.version,
        updated_at=snapshot.updated_at,
        summary=snapshot.summary,
    )


@router.get(
    "/infrastructure",
    response_model=InfrastructureSummaryResponse,
    dependencies=[READ],
    summary="Get aggregated infrastructure snapshots",
)
def get_infrastructure() -> InfrastructureSummaryResponse:
    collected_at, services = get_infrastructure_service().snapshot()
    return InfrastructureSummaryResponse(
        collected_at=collected_at,
        services=[_to_response(item) for item in services],
    )


@router.get(
    "/photo-services",
    response_model=PhotoServicesResponse,
    dependencies=[READ],
    summary="Get read-only Immich, QuMagie, and QNAP photo snapshots",
)
def get_photo_services(
    settings: Annotated[Settings, Depends(get_settings)],
) -> PhotoServicesResponse:
    collected_at, services, stats = get_infrastructure_service().photo_services()
    if not settings.infrastructure_mock:
        record_photo_snapshot(stats, observed_at=collected_at)
    storage_history, photo_growth = photo_trends(stats, use_mock=settings.infrastructure_mock)
    stats = {
        **stats,
        "storage_history": StorageHistoryResponse.model_validate(storage_history),
        "photo_growth": PhotoGrowthResponse.model_validate(photo_growth),
    }
    return PhotoServicesResponse(
        collected_at=collected_at,
        read_only=True,
        services=[_to_response(item) for item in services],
        stats=PhotoStatsResponse.model_validate(stats),
    )


@router.get(
    "/backup",
    response_model=BackupStatusResponse,
    dependencies=[READ],
    summary="Get read-only backup status for the TS-253 Pro target",
)
def get_backup_status(
    settings: Annotated[Settings, Depends(get_settings)],
) -> BackupStatusResponse:
    snapshot = get_infrastructure_service().backup()
    if snapshot is None:
        raise APIError(
            404,
            "backup_not_found",
            "The backup connector is not configured",
        )
    try:
        record_backup_snapshot(snapshot)
    except SQLAlchemyError:
        logger.warning("backup_history_record_failed")
    try:
        history = backup_history_periods(snapshot, use_mock=settings.infrastructure_mock)
    except SQLAlchemyError:
        logger.warning("backup_history_read_failed")
        history = []
    return backup_status_from_snapshot(snapshot, history=history, settings=settings)


@router.get(
    "/infrastructure/{service}",
    response_model=InfrastructureSnapshotResponse,
    dependencies=[READ],
    summary="Get one infrastructure connector snapshot",
)
def get_infrastructure_service_snapshot(service: str) -> InfrastructureSnapshotResponse:
    snapshot = get_infrastructure_service().get(service)
    if snapshot is None:
        raise APIError(
            404,
            "infrastructure_service_not_found",
            "The requested infrastructure connector does not exist",
        )
    return _to_response(snapshot)
