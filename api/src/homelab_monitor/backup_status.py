from homelab_monitor.connectors.base import ConnectorSnapshot
from homelab_monitor.connectors.http import as_float, as_int, as_str
from homelab_monitor.schemas import (
    BackupDestinationResponse,
    BackupHistoryPeriodResponse,
    BackupStatusResponse,
    SqliteBackupStatusResponse,
)
from homelab_monitor.settings import Settings
from homelab_monitor.sqlite_backup import sqlite_status_payload


def backup_status_from_snapshot(
    snapshot: ConnectorSnapshot,
    *,
    history: list[dict[str, str]] | None = None,
    settings: Settings | None = None,
) -> BackupStatusResponse:
    summary = snapshot.summary
    job_status = as_str(summary.get("job_status")).lower()
    health = as_str(summary.get("backup_health") or snapshot.status).lower()
    status = _display_status(job_status, health, snapshot.status)
    return BackupStatusResponse(
        read_only=True,
        status=status,
        backup_health=health or "unknown",
        job_name=as_str(summary.get("job_name")),
        job_type=as_str(summary.get("job_type")),
        progress_percent=as_float(summary.get("progress_percent")),
        last_backup=as_str(summary.get("last_backup")),
        next_backup=as_str(summary.get("next_backup")),
        duration_seconds=as_int(summary.get("duration_seconds")),
        backup_size_bytes=as_int(summary.get("backup_size_bytes")),
        last_error=as_str(summary.get("last_error")),
        last_success=as_str(summary.get("last_success") or summary.get("last_backup")),
        updated_at=snapshot.updated_at,
        destination=BackupDestinationResponse(
            hostname=as_str(summary.get("destination_name")),
            ip=as_str(summary.get("destination_ip")),
            model=as_str(summary.get("destination_model"), "TS-253 Pro"),
        ),
        history=[BackupHistoryPeriodResponse.model_validate(item) for item in history or []],
        sqlite=SqliteBackupStatusResponse.model_validate(sqlite_status_payload(settings))
        if settings is not None
        else None,
    )


def _display_status(job_status: str, health: str, connector_status: str) -> str:
    if job_status == "running":
        return "running"
    if job_status == "failed" or health in {"critical", "failed"}:
        return "failed" if job_status == "failed" else "critical"
    if health == "warning":
        return "warning"
    if health in {"healthy", "ok"}:
        return "healthy"
    if job_status == "idle":
        return "idle"
    return connector_status
