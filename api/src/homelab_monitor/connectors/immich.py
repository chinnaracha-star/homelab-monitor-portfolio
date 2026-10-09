from typing import Any

from homelab_monitor.connectors.base import BaseConnector, ConnectorSnapshot, utc_now
from homelab_monitor.connectors.http import as_int, as_str, get_json


class ImmichConnector(BaseConnector):
    service = "immich"

    def collect(self) -> ConnectorSnapshot:
        if self.mock:
            return self._snapshot(self._mock_summary(), version="1.118.0")
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
            "health": "ok",
            "immich_health": 1,
            "indexed_photos": 18420,
            "indexed_videos": 412,
            "albums": 28,
            "users": 3,
            "thumbnail_queue": 3,
            "face_jobs": 1,
            "face_queue": 1,
            "ml_status": "ready",
            "last_scan": "2026-09-08T00:40:00+00:00",
            "last_update": "2026-09-08T01:00:00+00:00",
        }

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["x-api-key"] = self.api_key
        return headers

    def _get(self, path: str) -> Any:
        return get_json(
            f"{self.base_url}{path}",
            headers=self._headers(),
            timeout=self.timeout,
            client=self._client,
        )

    def _live(self) -> ConnectorSnapshot:
        ping = self._get("/api/server/ping")
        version_body = self._get("/api/server/version")
        stats = self._get("/api/server/statistics")
        jobs = self._get("/api/jobs")
        users = self._get("/api/users")
        albums = self._get("/api/albums")
        version = _immich_version(version_body)
        thumb_queue, face_queue, ml_status = _job_counts(jobs)
        healthy = _immich_ping_ok(ping)
        summary = {
            "health": "ok" if healthy else "down",
            "immich_health": 1 if healthy else 0,
            "indexed_photos": as_int(_first(stats, "photos", "photoCount", "assets")),
            "indexed_videos": as_int(_first(stats, "videos", "videoCount")),
            "albums": _count(albums),
            "users": _count(users),
            "thumbnail_queue": thumb_queue,
            "face_jobs": face_queue,
            "face_queue": face_queue,
            "ml_status": ml_status,
            "last_scan": as_str(_first(stats, "lastScan", "last_scan")),
            "last_update": as_str(_first(stats, "lastUpdate", "last_update", "createdAt")),
        }
        return self._snapshot(summary, version=version)

    def _snapshot(self, summary: dict[str, Any], *, version: str) -> ConnectorSnapshot:
        healthy = summary.get("immich_health") == 1 or summary.get("health") == "ok"
        return ConnectorSnapshot(
            service=self.service,
            status="healthy" if healthy else "unhealthy",
            version=version,
            updated_at=utc_now(),
            summary=summary,
        )


def _first(payload: Any, *keys: str) -> Any:
    if not isinstance(payload, dict):
        return None
    for key in keys:
        if payload.get(key) is not None:
            return payload[key]
    return None


def _count(payload: Any) -> int:
    if isinstance(payload, list):
        return len(payload)
    if isinstance(payload, dict):
        items = payload.get("items") or payload.get("users") or payload.get("albums")
        if isinstance(items, list):
            return len(items)
        return as_int(payload.get("total") or payload.get("count"))
    return 0


def _immich_version(payload: Any) -> str:
    if not isinstance(payload, dict):
        return as_str(payload, "unknown")
    if payload.get("version"):
        return as_str(payload["version"])
    major = payload.get("major")
    minor = payload.get("minor")
    patch = payload.get("patch")
    if major is None:
        return "unknown"
    return f"{major}.{minor}.{patch}"


def _immich_ping_ok(payload: Any) -> bool:
    if payload in ("pong", True):
        return True
    if isinstance(payload, dict):
        return payload.get("res") == "pong" or payload.get("status") in {"ok", "healthy"}
    return False


def _job_counts(payload: Any) -> tuple[int, int, str]:
    jobs = payload if isinstance(payload, dict) else {}
    thumb = _waiting(jobs.get("thumbnailGeneration") or jobs.get("thumbnail"))
    face = _waiting(jobs.get("faceDetection") or jobs.get("facialRecognition"))
    ml = jobs.get("machineLearning") or jobs.get("smartSearch") or {}
    ml_status = "ready"
    if isinstance(ml, dict):
        queue = ml.get("queueStatus") or {}
        if queue.get("isPaused"):
            ml_status = "paused"
        elif queue.get("isActive") or _waiting(ml):
            ml_status = "busy"
    return thumb, face, ml_status


def _waiting(job: Any) -> int:
    if not isinstance(job, dict):
        return 0
    counts = job.get("jobCounts") or job.get("queueStatus") or job
    waiting = as_int(counts.get("waiting"))
    delayed = as_int(counts.get("delayed"))
    active = as_int(counts.get("active"))
    length = as_int(counts.get("length"))
    return (waiting + delayed) or active or length
