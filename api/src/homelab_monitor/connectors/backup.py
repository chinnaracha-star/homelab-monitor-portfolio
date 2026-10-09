from typing import Any

import httpx

from homelab_monitor.connectors.base import BaseConnector, ConnectorSnapshot, utc_now
from homelab_monitor.connectors.http import as_float, as_int, as_str, get_json

BACKUP_SIZE_BYTES = 2_001_111_162_552  # 1.82 TiB
LAST_BACKUP = "2026-09-08T02:00:00+00:00"
NEXT_BACKUP = "2026-09-09T02:00:00+00:00"


class BackupConnector(BaseConnector):
    service = "backup"

    def collect(self) -> ConnectorSnapshot:
        if self.mock:
            return self._snapshot(self._mock_summary(), version="HBS-26")
        if not self.base_url:
            return ConnectorSnapshot(
                service=self.service,
                status="unknown",
                version="",
                updated_at=utc_now(),
                summary={},
            )
        return self._live()

    def _mock_summary(self) -> dict[str, Any]:
        return {
            "last_backup": LAST_BACKUP,
            "next_backup": NEXT_BACKUP,
            "backup_status": "success",
            "destination": "s3://homelab-backups",
            "duration_seconds": 1080,
            "progress_percent": 43,
            "backup_size_bytes": BACKUP_SIZE_BYTES,
            "destination_name": "qnap-backup-01",
            "destination_ip": "192.168.1.253",
            "destination_model": "TS-253 Pro",
            "job_name": "Daily replication to TS-253 Pro",
            "job_type": "replication",
            "job_status": "running",
            "backup_health": "healthy",
            "last_error": "",
            "last_success": LAST_BACKUP,
            "read_only": True,
        }

    def _live(self) -> ConnectorSnapshot:
        try:
            payload = get_json(
                f"{self.base_url}/api/backup/status",
                timeout=self.timeout,
                client=self._client,
            )
        except httpx.HTTPError as error:
            raise ConnectionError(str(error)) from error
        if not isinstance(payload, dict) or "raw" in payload:
            raise ConnectionError("Backup status endpoint did not return JSON")
        last_backup = as_str(payload.get("last_backup") or payload.get("lastBackup"))
        summary = {
            "last_backup": last_backup,
            "next_backup": as_str(payload.get("next_backup") or payload.get("nextBackup")),
            "backup_status": as_str(
                payload.get("backup_status") or payload.get("result"), "unknown"
            ),
            "destination": as_str(payload.get("destination"), "s3://homelab-backups"),
            "duration_seconds": as_int(payload.get("duration_seconds") or payload.get("duration")),
            "progress_percent": as_float(
                payload.get("progress_percent") or payload.get("progress")
            ),
            "backup_size_bytes": as_int(payload.get("backup_size_bytes") or payload.get("size")),
            "destination_name": as_str(
                payload.get("destination_name") or payload.get("hostname"), "qnap-backup-01"
            ),
            "destination_ip": as_str(payload.get("destination_ip") or payload.get("ip")),
            "destination_model": as_str(
                payload.get("destination_model") or payload.get("model"), "TS-253 Pro"
            ),
            "job_name": as_str(payload.get("job_name") or payload.get("name"), "Backup"),
            "job_type": as_str(payload.get("job_type") or payload.get("type"), "replication"),
            "job_status": as_str(payload.get("job_status") or payload.get("state"), "idle"),
            "backup_health": as_str(
                payload.get("backup_health") or payload.get("health"), "unknown"
            ),
            "last_error": as_str(payload.get("last_error") or payload.get("error")),
            "last_success": as_str(payload.get("last_success") or last_backup),
            "read_only": True,
        }
        version = as_str(payload.get("version"), "unknown")
        return self._snapshot(summary, version=version)

    def _snapshot(self, summary: dict[str, Any], *, version: str) -> ConnectorSnapshot:
        return ConnectorSnapshot(
            service=self.service,
            status=_connector_status(summary),
            version=version,
            updated_at=utc_now(),
            summary=summary,
        )


def _connector_status(summary: dict[str, Any]) -> str:
    health = as_str(summary.get("backup_health")).lower()
    job_status = as_str(summary.get("job_status")).lower()
    if health in {"critical", "failed"} or job_status == "failed":
        return "unhealthy"
    if health == "warning":
        return "degraded"
    if health in {"healthy", "ok"} or job_status in {"idle", "running", "success"}:
        return "healthy"
    return "unknown"
