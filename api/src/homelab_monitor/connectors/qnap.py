import base64
import json
from urllib.parse import urlencode
from xml.etree import ElementTree

import httpx

from homelab_monitor.connectors.base import BaseConnector, ConnectorSnapshot, utc_now
from homelab_monitor.connectors.http import as_float, as_int, as_str, get_json, http_get
from homelab_monitor.qnap_disks import disks_from_payload, optional_celsius, qnap_disk_thresholds

STORAGE_WARNING_PERCENT = 80.0
STORAGE_CRITICAL_PERCENT = 90.0


def storage_health(percent: float) -> str:
    if percent >= STORAGE_CRITICAL_PERCENT:
        return "critical"
    if percent >= STORAGE_WARNING_PERCENT:
        return "warning"
    return "healthy"


class QnapConnector(BaseConnector):
    service = "qnap"

    def __init__(self, *, tls_verify: bool = True, **kwargs: object) -> None:
        super().__init__(**kwargs)  # type: ignore[arg-type]
        self.tls_verify = tls_verify
        if self._client is None:
            self._client = httpx.Client(timeout=self.timeout, verify=tls_verify)

    def collect(self) -> ConnectorSnapshot:
        if self.mock:
            return self._snapshot(self._mock_summary(), version="5.2.1")
        if not self.base_url:
            return self._unconfigured()
        return self._live()

    def _unconfigured(self) -> ConnectorSnapshot:
        return ConnectorSnapshot(
            service=self.service,
            status="unknown",
            version="",
            updated_at=utc_now(),
            summary={},
        )

    def _mock_summary(self) -> dict:
        capacity = 12_000_000_000_000
        used = 4_980_000_000_000
        free = capacity - used
        percent = round(used / capacity * 100, 1)
        return {
            "hostname": "qnap-lab-01",
            "model": "TS-453Be",
            "firmware": "5.2.1",
            "firmware_version": "5.2.1",
            "uptime_seconds": 864000,
            "online": True,
            "storage_used_percent": percent,
            "storage_percent": percent,
            "capacity_bytes": capacity,
            "used_bytes": used,
            "free_bytes": free,
            "shared_folders": 4,
            "temperature_celsius": 42,
            "storage_health": storage_health(percent),
        }

    def _live(self) -> ConnectorSnapshot:
        sid = self.api_key
        if not sid and self.username and self.password:
            sid = self._login()
            if not sid:
                return ConnectorSnapshot(
                    service=self.service,
                    status="unhealthy",
                    version="",
                    updated_at=utc_now(),
                    summary={"online": False, "error": "qnap_auth_failed"},
                )
        try:
            sysinfo = get_json(
                f"{self.base_url}/cgi-bin/management/manaRequest.cgi?subfunc=sysinfo&sid={sid}",
                timeout=self.timeout,
                client=self._client,
            )
        except httpx.HTTPError:
            return ConnectorSnapshot(
                service=self.service,
                status="unhealthy",
                version="",
                updated_at=utc_now(),
                summary={"online": False, "error": "qnap_sysinfo_failed"},
            )
        payload = sysinfo if isinstance(sysinfo, dict) else {}
        if "raw" in payload:
            payload = _parse_qnap_xml(str(payload["raw"]))
        share_count = as_int(payload.get("shared_folders"))
        try:
            shares = get_json(
                f"{self.base_url}/cgi-bin/filemanager/utilRequest.cgi?func=get_share_list&sid={sid}",
                timeout=self.timeout,
                client=self._client,
            )
            share_count = _share_count(shares) or share_count
        except httpx.HTTPError:
            pass
        capacity = _present_int(payload, "capacity_bytes", "volume_size")
        used = _present_int(payload, "used_bytes", "volume_used")
        free = _present_int(payload, "free_bytes", "volume_free")
        if free is None and capacity is not None and used is not None:
            free = capacity - used
        percent = _present_float(payload, "storage_percent")
        if percent is None and capacity:
            percent = round((used or 0) / capacity * 100, 1)
        firmware = as_str(payload.get("firmware") or payload.get("version"))
        online = payload.get("online", True)
        summary = {
            "hostname": as_str(payload.get("hostname") or payload.get("host"), "qnap"),
            "model": _nas_model(payload),
            "firmware": firmware,
            "firmware_version": firmware,
            "uptime_seconds": as_int(payload.get("uptime_seconds") or payload.get("uptime")),
            "online": bool(online),
            "storage_used_percent": percent,
            "storage_percent": percent,
            "capacity_bytes": capacity,
            "used_bytes": used,
            "free_bytes": free,
            "shared_folders": share_count,
            "temperature_celsius": optional_celsius(
                payload.get("temperature_celsius")
                if payload.get("temperature_celsius") not in (None, "")
                else payload.get("cpu_temp")
            ),
            "cpu_tempc": optional_celsius(payload.get("cpu_tempc")),
            "sys_tempc": optional_celsius(payload.get("sys_tempc")),
            "storage_health": "unknown" if percent is None else storage_health(percent),
        }
        warning, critical = qnap_disk_thresholds(payload)
        summary["disk_temp_warning_c"] = warning
        summary["disk_temp_critical_c"] = critical
        disks = disks_from_payload(payload)
        if disks is not None:
            summary["disks"] = disks
        return self._snapshot(summary, version=firmware or "unknown")

    def _login(self) -> str:
        query = urlencode(
            {
                "user": self.username,
                "pwd": base64.b64encode(self.password.encode("utf-8")).decode("ascii"),
                "serviceKey": "1",
                "client_app": "Web Desktop",
            }
        )
        try:
            login = http_get(
                f"{self.base_url}/cgi-bin/authLogin.cgi?{query}",
                timeout=self.timeout,
                client=self._client,
            )
        except httpx.HTTPError:
            return ""
        return _extract_sid(login.text)

    def _snapshot(self, summary: dict, *, version: str) -> ConnectorSnapshot:
        status = "healthy"
        if not summary.get("online") or summary.get("storage_health") == "critical":
            status = "unhealthy"
        elif summary.get("storage_health") == "warning":
            status = "degraded"
        return ConnectorSnapshot(
            service=self.service,
            status=status,
            version=version,
            updated_at=utc_now(),
            summary=summary,
        )


def _present_int(payload: dict, *keys: str) -> int | None:
    for key in keys:
        if key in payload and payload.get(key) not in (None, ""):
            return as_int(payload.get(key))
    return None


def _present_float(payload: dict, key: str) -> float | None:
    if key not in payload or payload.get(key) in (None, ""):
        return None
    return as_float(payload.get(key))


def _nas_model(payload: dict) -> str:
    for key in ("model", "modelName", "internalModelName", "customModelName", "displayModelName"):
        value = as_str(payload.get(key)).strip()
        if value:
            return value
    return ""


def _extract_sid(text: str) -> str:
    try:
        root = ElementTree.fromstring(text)
    except ElementTree.ParseError:
        root = None
    if root is not None:
        passed = ""
        sid = ""
        for node in root.iter():
            if node.tag == "authPassed":
                passed = (node.text or "").strip()
            elif node.tag == "authSid":
                sid = (node.text or "").strip()
        if passed == "0":
            return ""
        return sid
    if '"sid"' in text or '"authSid"' in text:
        try:
            body = json.loads(text)
        except json.JSONDecodeError:
            return ""
        if str(body.get("authPassed", "1")) == "0":
            return ""
        return str(body.get("authSid") or body.get("sid") or "")
    return ""


def _parse_qnap_xml(text: str) -> dict:
    try:
        root = ElementTree.fromstring(text)
    except ElementTree.ParseError:
        return {}
    values = {child.tag: (child.text or "") for child in root.iter() if child is not root}
    return values


def _share_count(payload: object) -> int:
    if isinstance(payload, list):
        return len(payload)
    if isinstance(payload, dict):
        datas = payload.get("datas") or payload.get("shares") or payload.get("items")
        if isinstance(datas, list):
            return len(datas)
        if "raw" in payload:
            return 0
        return as_int(payload.get("count") or payload.get("shared_folders"))
    return 0
