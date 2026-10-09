"""QNAP disk temperatures from indexed sysinfo fields.

The verified TS-453Be payload uses disk_installedN and tempcN. Manufacturer,
model, capacity, and SMART are not present in that payload and stay null.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from homelab_monitor.connectors.http import as_str

FALLBACK_HD_TEMP_WARN_C = 55
FALLBACK_HD_TEMP_ERR_C = 60
_INSTALLED = re.compile(r"^disk_installed(\d+)$")
QNAP_DISK_ALERT_KIND = "qnap_disk_temperature_high"
QNAP_DISK_ALERT_COOLDOWN_SECONDS = 900
TELEGRAM_QNAP_SECTION_LIMIT = 1200

logger = logging.getLogger("homelab_monitor.qnap_disks")


def optional_celsius(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def qnap_disk_thresholds(payload: dict[str, Any]) -> tuple[int, int]:
    warning = optional_celsius(payload.get("HDTempWarnT"))
    critical = optional_celsius(payload.get("HDTempErrT"))
    if warning is None or critical is None or warning <= 0 or critical <= warning:
        return FALLBACK_HD_TEMP_WARN_C, FALLBACK_HD_TEMP_ERR_C
    return warning, critical


def temperature_status(celsius: int | None, warning: int, critical: int) -> str:
    if celsius is None:
        return "unknown"
    if celsius >= critical:
        return "critical"
    if celsius >= warning:
        return "warning"
    return "normal"


def _installed(value: Any) -> bool:
    return str(value).strip() == "1"


def _is_ssd(value: Any) -> bool | None:
    text = str(value).strip() if value is not None else ""
    if text == "1":
        return True
    if text == "0":
        return False
    return None


def disks_from_payload(payload: dict[str, Any]) -> list[dict[str, Any]] | None:
    indexes = sorted(
        int(match.group(1)) for key in payload if (match := _INSTALLED.match(str(key))) is not None
    )
    if not indexes:
        return None
    warning, critical = qnap_disk_thresholds(payload)
    disks: list[dict[str, Any]] = []
    for bay in indexes:
        if not _installed(payload.get(f"disk_installed{bay}")):
            continue
        temp = optional_celsius(payload.get(f"tempc{bay}"))
        alias = as_str(payload.get(f"hd_pd_alias{bay}")).strip() or None
        disks.append(
            {
                "bay": bay,
                "alias": alias,
                "installed": True,
                "is_ssd": _is_ssd(payload.get(f"hd_is_ssd{bay}")),
                "temperature_celsius": temp,
                "temp_alert": optional_celsius(payload.get(f"temp_alert{bay}")),
                "temperature_status": temperature_status(temp, warning, critical),
                "warning_c": warning,
                "critical_c": critical,
                "manufacturer": None,
                "model": None,
                "capacity_bytes": None,
                "smart_status": None,
                "abnormal_sector_count": None,
            }
        )
    return disks


def alert_resource(hostname: str, bay: int | None) -> str:
    host = hostname or "qnap"
    disk = "unknown" if bay is None else str(bay)
    return f"qnap:{host}:bay:{disk}"


def _temp_mark(status: str) -> str:
    return {"normal": "🟢", "warning": "🟠", "critical": "🔴"}.get(status, "⚪")


def disk_line(disk: dict[str, Any]) -> str:
    bay = disk.get("bay")
    kind = "SSD" if disk.get("is_ssd") is True else "HDD"
    label = f"{kind} {bay}" if bay is not None else kind
    temp = disk.get("temperature_celsius")
    temp_text = "Temperature Unknown" if temp is None else f"{temp}°C"
    mark = _temp_mark(str(disk.get("temperature_status") or "unknown"))
    return f"{mark} {label} | {temp_text}"


def format_qnap_report_section(
    summary: dict[str, Any] | None, *, online: bool | None = None
) -> str:
    if summary is None or online is False or summary.get("online") is False:
        return "\n".join(
            [
                "💾 QNAP Storage",
                "Status: 🔴 Offline",
                "Disk Temperature: unavailable",
            ]
        )
    disks = summary.get("disks")
    system_temp = optional_celsius(
        summary.get("sys_tempc") if "sys_tempc" in summary else summary.get("temperature_celsius")
    )
    cpu_temp = optional_celsius(summary.get("cpu_tempc")) if "cpu_tempc" in summary else None
    system_text = "Unknown" if system_temp is None else f"{system_temp}°C"
    percent = summary.get("storage_percent")
    storage_text = "Unknown" if percent in (None, "") else f"{percent}%"
    lines = [
        "💾 QNAP Storage",
        "Status: 🟢 Online",
        f"Storage: {storage_text}",
        f"System Temp: {system_text}",
    ]
    if cpu_temp is not None:
        lines.append(f"CPU Temp: {cpu_temp}°C")
    if not isinstance(disks, list) or not disks:
        lines.append("Disk Temperature: unavailable")
        return _fit_section(lines)
    lines.append("Disk Temperature:")
    rendered = [disk_line(disk) for disk in disks if isinstance(disk, dict)]
    kept, hidden = _fit_disk_rows(lines, rendered)
    lines.extend(kept)
    if hidden:
        lines.append(f"... +{hidden} more disks")
    warning = summary.get("disk_temp_warning_c")
    critical = summary.get("disk_temp_critical_c")
    if isinstance(warning, int) and isinstance(critical, int):
        lines.append(f"Threshold: ⚠️ {warning}°C / 🚨 {critical}°C")
    return _fit_section(lines)


def _fit_disk_rows(header: list[str], rows: list[str]) -> tuple[list[str], int]:
    kept: list[str] = []
    for index, row in enumerate(rows):
        candidate = [*header, *kept, row, f"... +{len(rows) - index - 1} more disks"]
        if len("\n".join(candidate)) > TELEGRAM_QNAP_SECTION_LIMIT and kept:
            return kept, len(rows) - len(kept)
        kept.append(row)
    return kept, 0


def _fit_section(lines: list[str]) -> str:
    text = "\n".join(lines)
    if len(text) <= TELEGRAM_QNAP_SECTION_LIMIT:
        return text
    trimmed = text[: TELEGRAM_QNAP_SECTION_LIMIT - 20].rsplit("\n", 1)[0]
    return f"{trimmed}\n... truncated"


def temperature_alert_message(
    *,
    hostname: str,
    disk: dict[str, Any],
    transition: str,
) -> str:
    bay = disk.get("bay")
    alias = disk.get("alias") or "QNAP disk"
    temp = disk.get("temperature_celsius")
    temp_text = "Unknown" if temp is None else f"{temp}°C"
    status = str(disk.get("temperature_status") or "unknown")
    warning = disk.get("warning_c")
    critical = disk.get("critical_c")
    if transition == "recovered":
        return "\n".join(
            [
                "✅ QNAP HDD Temperature Recovered",
                "",
                f"NAS: {hostname}",
                f"Disk: HDD {bay}",
                f"Alias: {alias}",
                f"Temperature: {temp_text}",
                "Status: Normal",
            ]
        )
    if status == "critical":
        title = "🔥 QNAP HDD Temperature Critical"
        limit = critical if isinstance(critical, int) else FALLBACK_HD_TEMP_ERR_C
        note = f"🚨 HDD temperature exceeded {limit}°C"
    else:
        title = "🌡️ QNAP HDD Temperature Warning"
        limit = warning if isinstance(warning, int) else FALLBACK_HD_TEMP_WARN_C
        note = f"⚠️ HDD temperature exceeded {limit}°C"
    return "\n".join(
        [
            title,
            "",
            f"NAS: {hostname}",
            f"Disk: HDD {bay}",
            f"Alias: {alias}",
            f"Temperature: {temp_text}",
            "",
            note,
        ]
    )


def iter_disk_alerts(summary: dict[str, Any]) -> list[dict[str, Any]]:
    disks = summary.get("disks")
    if not isinstance(disks, list):
        return []
    hostname = as_str(summary.get("hostname"), "qnap")
    events: list[dict[str, Any]] = []
    for disk in disks:
        if not isinstance(disk, dict):
            continue
        temp = disk.get("temperature_celsius")
        status = str(disk.get("temperature_status") or "unknown")
        if status == "unknown":
            continue
        breached = status in {"warning", "critical"}
        warning = disk.get("warning_c")
        critical = disk.get("critical_c")
        if not isinstance(warning, int):
            warning = FALLBACK_HD_TEMP_WARN_C
        if not isinstance(critical, int):
            critical = FALLBACK_HD_TEMP_ERR_C
        threshold = float(critical if status == "critical" else warning)
        events.append(
            {
                "hostname": hostname,
                "resource": alert_resource(hostname, disk.get("bay")),
                "value": float(temp) if isinstance(temp, int) else 0.0,
                "threshold": threshold,
                "breached": breached,
                "severity": "critical" if status == "critical" else "warning",
                "message": temperature_alert_message(
                    hostname=hostname,
                    disk=disk,
                    transition="activated" if breached else "recovered",
                ),
            }
        )
    return events


def sync_qnap_disk_alerts(summary: dict[str, Any]) -> None:
    """Open or resolve HDD temperature alerts on an agent whose name is the NAS hostname.

    Alerts stay off the agent temperature metric. If that agent does not exist, nothing
    is written and the caller still succeeds.
    """
    if summary.get("online") is False:
        return
    pending = iter_disk_alerts(summary)
    if not pending:
        return
    from datetime import UTC, datetime

    from sqlalchemy import select
    from sqlalchemy.orm import Session

    from homelab_monitor.alert_engine import AlertEngine
    from homelab_monitor.database import get_engine
    from homelab_monitor.models import Agent
    from homelab_monitor.settings import get_settings

    hostname = pending[0]["hostname"]
    observed_at = datetime.now(UTC)
    try:
        from homelab_monitor.sqlite_diagnostics import writer_operation

        with writer_operation("qnap_disk_alert_update"), Session(get_engine()) as db:
            agent = db.scalar(select(Agent).where(Agent.name == hostname))
            if agent is None:
                return
            engine = AlertEngine(get_settings())
            events = []
            for item in pending:
                event = engine._set_threshold_state(
                    db,
                    agent,
                    kind=QNAP_DISK_ALERT_KIND,
                    resource=item["resource"],
                    value=item["value"],
                    threshold=item["threshold"],
                    breached=item["breached"],
                    observed_at=observed_at,
                    message=item["message"],
                    severity=item["severity"],
                    cooldown_seconds=QNAP_DISK_ALERT_COOLDOWN_SECONDS,
                )
                if event is not None:
                    events.append(event)
            db.commit()
            engine._enqueue_notifications(events)
    except Exception:
        logger.exception("qnap_disk_alert_sync_failed")
