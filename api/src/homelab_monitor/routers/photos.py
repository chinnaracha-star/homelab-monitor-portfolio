from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from homelab_monitor.auth.dependencies import require_roles
from homelab_monitor.database import get_db
from homelab_monitor.errors import APIError
from homelab_monitor.models import PhotoMonitorSettings
from homelab_monitor.photo_events import (
    PhotoEventRepository,
    apply_watch_folders,
    resolved_watch_folders,
)
from homelab_monitor.photo_folders import (
    display_folder_name,
    display_folder_names,
    matching_watch_root,
)
from homelab_monitor.photo_watcher import (
    ALLOWED_AUTO_DELETE_DAYS,
    ALLOWED_INTERVALS,
    ALLOWED_MAX_EVENTS,
    get_photo_watcher_service,
)
from homelab_monitor.schemas import (
    PhotoEventListResponse,
    PhotoEventResponse,
    PhotoMonitorSettingsResponse,
    PhotoMonitorSettingsUpdateRequest,
    PhotoMonitorStatsResponse,
)
from homelab_monitor.settings import Settings, get_settings

router = APIRouter(prefix="/api/v1/photos", tags=["photos"])
READ = Depends(require_roles("admin", "operator", "viewer"))
CONFIGURE = Depends(require_roles("admin"))


@router.get(
    "",
    response_model=PhotoEventListResponse,
    dependencies=[READ],
    summary="List latest photo monitor events",
)
def list_photos(
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> PhotoEventListResponse:
    items = PhotoEventRepository(db).list_latest(limit)
    return PhotoEventListResponse(items=[PhotoEventResponse.model_validate(item) for item in items])


@router.get(
    "/latest",
    response_model=PhotoEventResponse,
    dependencies=[READ],
    summary="Get the most recent photo event",
)
def get_latest_photo(db: Annotated[Session, Depends(get_db)]) -> PhotoEventResponse:
    event = PhotoEventRepository(db).latest()
    if event is None:
        raise APIError(404, "latest_photo_not_found", "No photo events have been recorded")
    return PhotoEventResponse.model_validate(event)


@router.get(
    "/stats",
    response_model=PhotoMonitorStatsResponse,
    dependencies=[READ],
    summary="Get Photo Monitor dashboard statistics",
)
def get_photo_stats(
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> PhotoMonitorStatsResponse:
    repo = PhotoEventRepository(db)
    config = repo.ensure_settings(settings)
    db.commit()
    latest = repo.latest()
    folders = resolved_watch_folders(config)
    last_folder = None
    if latest is not None:
        last_folder = display_folder_name(matching_watch_root(latest.folder, folders))
    indexed = get_photo_watcher_service(settings).indexed_files
    return PhotoMonitorStatsResponse(
        today_count=repo.today_count(),
        last_photo=None if latest is None else latest.filename,
        last_folder=last_folder,
        last_update=None if latest is None else latest.created_at,
        watch_folder=folders[0] if folders else config.watch_folder,
        watch_folders=folders,
        watch_folder_labels=display_folder_names(folders),
        indexed_files=indexed,
        status="running" if config.enabled else "stopped",
        enabled=config.enabled,
    )


@router.get(
    "/settings",
    response_model=PhotoMonitorSettingsResponse,
    dependencies=[READ],
    summary="Get Photo Monitor settings",
)
def get_photo_settings(
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> PhotoMonitorSettingsResponse:
    row = PhotoEventRepository(db).ensure_settings(settings)
    db.commit()
    return _settings_response(row)


@router.put(
    "/settings",
    response_model=PhotoMonitorSettingsResponse,
    dependencies=[CONFIGURE],
    status_code=status.HTTP_200_OK,
    summary="Update Photo Monitor settings",
)
def update_photo_settings(
    payload: PhotoMonitorSettingsUpdateRequest,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> PhotoMonitorSettingsResponse:
    if payload.scan_interval_seconds not in ALLOWED_INTERVALS:
        raise APIError(
            400,
            "invalid_scan_interval",
            "Scan interval must be 5, 10, 30, or 60 seconds",
        )
    if payload.max_events not in ALLOWED_MAX_EVENTS:
        raise APIError(400, "invalid_max_events", "Maximum events must be 100, 500, or 1000")
    if payload.auto_delete_days not in ALLOWED_AUTO_DELETE_DAYS:
        raise APIError(400, "invalid_auto_delete", "Auto delete must be Never, 30 days, or 90 days")
    repo = PhotoEventRepository(db)
    row = repo.ensure_settings(settings)
    row.enabled = payload.enabled
    apply_watch_folders(row, payload.watch_folders)
    row.recursive = payload.recursive
    row.scan_interval_seconds = payload.scan_interval_seconds
    row.max_events = payload.max_events
    row.auto_delete_days = payload.auto_delete_days
    db.commit()
    db.refresh(row)
    get_photo_watcher_service(settings).sync_watch_roots(resolved_watch_folders(row))
    return _settings_response(row)


def _settings_response(row: PhotoMonitorSettings) -> PhotoMonitorSettingsResponse:
    folders = resolved_watch_folders(row)
    payload = PhotoMonitorSettingsResponse.model_validate(row)
    return payload.model_copy(
        update={
            "watch_folders": folders,
            "watch_folder": folders[0] if folders else row.watch_folder,
            "watch_folder_labels": display_folder_names(folders),
        }
    )
