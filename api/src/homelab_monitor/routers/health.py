from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from homelab_monitor import __version__
from homelab_monitor.database import get_db
from homelab_monitor.models import PhotoEvent
from homelab_monitor.schemas import HealthResponse, JobRegistryHealth, PhotoMonitorHealth
from homelab_monitor.settings import get_settings

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Check API and database health",
)
def health(db: Annotated[Session, Depends(get_db)]) -> HealthResponse | JSONResponse:
    now = datetime.now(UTC)
    registry = _job_registry_health()
    try:
        db.execute(text("SELECT COUNT(*) FROM agents"))
        db.execute(text("SELECT COUNT(*) FROM alerts"))
    except SQLAlchemyError:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=HealthResponse(
                status="degraded",
                service="homelab-monitor-api",
                version=__version__,
                database="down",
                timestamp=now,
                job_registry=registry,
            ).model_dump(mode="json"),
        )

    return HealthResponse(
        status="healthy",
        service="homelab-monitor-api",
        version=__version__,
        database="up",
        timestamp=now,
        photo_monitor=_photo_monitor_health(db),
        job_registry=registry,
    )


def _job_registry_health() -> JobRegistryHealth:
    from homelab_monitor.jobs.engine import default_engine
    from homelab_monitor.jobs.validation import validate_runtime

    try:
        result = validate_runtime(get_settings(), list(default_engine().jobs()))
    except Exception:
        return JobRegistryHealth(status="warning", validated=False, warnings=["validation_failed"])
    return JobRegistryHealth(
        status="pass" if result.status == "pass" else "warning",
        validated=result.validated,
        registered_jobs=result.registered_jobs,
        factory_jobs=result.factory_jobs,
        warnings=list(result.warnings),
    )


def _photo_monitor_health(db: Session) -> PhotoMonitorHealth:
    from homelab_monitor.photo_watcher import get_photo_watcher_service

    try:
        service = get_photo_watcher_service(get_settings())
    except Exception:
        return PhotoMonitorHealth(status="unknown")
    token = ""
    chat = ""
    try:
        token = service._settings.telegram_bot_token.get_secret_value().strip()
        chat = str(service._settings.telegram_chat_id or "").strip()
    except Exception:
        token = ""
    label = getattr(service, "self_check_label", "UNKNOWN")
    if label not in {"PASS", "WARN", "FAIL"}:
        label = "UNKNOWN"
    last_event = db.query(PhotoEvent.created_at).order_by(PhotoEvent.id.desc()).limit(1).scalar()
    watching = service.last_successful_scan is not None or bool(service._primed)
    return PhotoMonitorHealth(
        status=service.self_check_status
        if service.self_check_status in {"pass", "fail"}
        else "unknown",
        running=watching,
        telegram_configured=bool(token and chat),
        pending=len(service._pending),
        last_telegram_at=service.last_successful_telegram,
        reasons=list(service.self_check_reasons),
        enabled=bool(service._settings.photo_watcher_enabled),
        baseline_loaded=bool(service._primed),
        watching=watching,
        current_month=datetime.now().strftime("%Y-%m"),
        last_scan=service.last_successful_scan,
        last_event=last_event,
        self_check=label,
    )
