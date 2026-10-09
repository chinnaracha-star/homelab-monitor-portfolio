from typing import Any

import httpx

from homelab_monitor.connectors.base import BaseConnector, ConnectorSnapshot, utc_now
from homelab_monitor.connectors.http import as_int, as_str, get_json


class QuMagieConnector(BaseConnector):
    service = "qumagie"

    def collect(self) -> ConnectorSnapshot:
        if self.mock:
            return self._snapshot(self._mock_summary(), version="2.6.0")
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
            "qumagie_health": 1,
            "indexed_photos": 17602,
            "ai_status": "ready",
            "index_status": "idle",
            "indexing": "idle",
            "last_scan": "2026-09-08T00:15:00+00:00",
        }

    def _live(self) -> ConnectorSnapshot:
        payload = self._probe()
        version = as_str(payload.get("version"), "unknown")
        health = as_str(payload.get("health") or payload.get("status"), "ok")
        healthy = health.lower() in {"ok", "healthy", "ready", "running"}
        summary = {
            "health": "ok" if healthy else health or "down",
            "qumagie_health": 1 if healthy else 0,
            "indexed_photos": as_int(
                payload.get("indexed_photos") or payload.get("photos") or payload.get("count")
            ),
            "ai_status": as_str(payload.get("ai_status") or payload.get("ai"), "unknown"),
            "index_status": as_str(
                payload.get("index_status") or payload.get("indexing") or payload.get("status"),
                "unknown",
            ),
            "indexing": as_str(payload.get("indexing") or payload.get("index_status"), "unknown"),
            "last_scan": as_str(payload.get("last_scan") or payload.get("lastScan")),
        }
        return self._snapshot(summary, version=version)

    def _probe(self) -> dict[str, Any]:
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["x-api-key"] = self.api_key
        errors: list[str] = []
        for path in ("/api/status", "/cgi-bin/qphoto/qphoto.cgi?func=get_info"):
            try:
                payload = get_json(
                    f"{self.base_url}{path}",
                    headers=headers,
                    timeout=self.timeout,
                    client=self._client,
                )
                if isinstance(payload, dict) and "raw" not in payload:
                    return payload
                if isinstance(payload, dict):
                    errors.append(str(payload.get("raw", ""))[:120])
            except httpx.HTTPError as error:
                errors.append(str(error))
        raise ConnectionError("; ".join(errors) or "QuMagie status endpoint was not reachable")

    def _snapshot(self, summary: dict[str, Any], *, version: str) -> ConnectorSnapshot:
        healthy = summary.get("qumagie_health") == 1
        return ConnectorSnapshot(
            service=self.service,
            status="healthy" if healthy else "unhealthy",
            version=version,
            updated_at=utc_now(),
            summary=summary,
        )
