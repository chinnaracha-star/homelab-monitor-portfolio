from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta, timezone, tzinfo
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from homelab_monitor import __version__
from homelab_monitor.alert_history import list_alert_history
from homelab_monitor.alert_severity import (
    CRITICAL,
    WARNING,
    alert_payload_severity,
)
from homelab_monitor.analytics import AnalyticsService
from homelab_monitor.capacity_planning import CapacityPlanningService, _bytes_label
from homelab_monitor.database import get_engine
from homelab_monitor.history import as_utc
from homelab_monitor.insights import InsightService
from homelab_monitor.jobs.repetition import run_repeated
from homelab_monitor.models import Notification
from homelab_monitor.notifications.config import load_payload, save_payload
from homelab_monitor.notifications.dispatcher import dispatch_telegram_report
from homelab_monitor.ops_history import _start_of_local_day
from homelab_monitor.photo_events import PhotoEventRepository
from homelab_monitor.qnap_disks import format_qnap_report_section
from homelab_monitor.settings import Settings, get_settings
from homelab_monitor.sqlite_backup import sqlite_status_payload
from homelab_monitor.sqlite_diagnostics import writer_operation
from homelab_monitor.telegram_links import resolve_dashboard_url
from homelab_monitor.trends import TrendService

logger = logging.getLogger("homelab_monitor.telegram_reports")

DEFAULT_REPORTS = {
    "hourly_enabled": False,
    "daily_enabled": False,
    "weekly_enabled": False,
    "hour_interval": 1,
    "daily_time": "08:00",
    "weekly_day": "sunday",
    "weekly_time": "08:00",
    "timezone": "Asia/Bangkok",
    "last_sent": {},
}
WEEKDAYS = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}
MONTHS = (
    "",
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)
HOURLY_RULE = "━━━━━━━━━━━━━━"
TICK_SECONDS = 60
REPORT_SPRINT = "10.2.8.3"
HOURLY_RECOMMENDATIONS = {
    "cpu_high": "Check CPU load",
    "memory_high": "Check memory usage",
    "disk_high": "Check storage capacity",
    "temperature_high": "Check cooling",
    "agent_offline": "Check agent connectivity",
}


def reports_payload(payload: dict) -> dict:
    stored = payload.get("reports")
    merged = dict(DEFAULT_REPORTS)
    if isinstance(stored, dict):
        merged.update({key: stored[key] for key in stored if key in merged or key == "last_sent"})
        last_sent = stored.get("last_sent")
        merged["last_sent"] = dict(last_sent) if isinstance(last_sent, dict) else {}
    interval = int(merged.get("hour_interval") or 1)
    merged["hour_interval"] = min(24, max(1, interval))
    return merged


def report_timezone(name: str) -> tzinfo:
    try:
        return ZoneInfo(name or "Asia/Bangkok")
    except ZoneInfoNotFoundError:
        return timezone(timedelta(hours=7))


def _parse_time(value: str) -> tuple[int, int]:
    try:
        hour_text, minute_text = (value or "08:00").split(":", 1)
        hour = min(23, max(0, int(hour_text)))
        minute = min(59, max(0, int(minute_text)))
        return hour, minute
    except (TypeError, ValueError):
        return 8, 0


def _parse_sent(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return as_utc(parsed)


def _english_date(local: datetime) -> str:
    return f"{local.day} {MONTHS[local.month]} {local.year}"


def _temperature_label(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{round(value)}°C"


def _actionable_alerts(alerts: list) -> list:
    ranked: list[object] = []
    for item in alerts:
        severity = alert_payload_severity(item.alert_type, item.peak_value, item.severity)
        if severity in {WARNING, CRITICAL}:
            ranked.append(item)
    return ranked


def _hourly_recommendations(alerts: list, backup_status: str) -> list[str]:
    recs: list[str] = []
    seen: set[str] = set()
    for item in _actionable_alerts(alerts):
        text = HOURLY_RECOMMENDATIONS.get(item.alert_type)
        if text and text not in seen:
            recs.append(text)
            seen.add(text)
    if backup_status.lower() in {"failed", "error", "critical"} and "Verify NAS Backup" not in recs:
        recs.append("Verify NAS Backup")
    return recs


def _pct(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{round(value)}%"


BAR_WIDTH = 10


def _progress_bar(percent: float | None) -> str:
    if percent is None:
        return "░" * BAR_WIDTH
    filled = max(0, min(BAR_WIDTH, round(float(percent) / (100 / BAR_WIDTH))))
    return ("█" * filled) + ("░" * (BAR_WIDTH - filled))


def _usage_status(percent: float | None) -> str:
    if percent is None:
        return "⚪"
    if percent >= 90:
        return "🔴"
    if percent >= 80:
        return "🟡"
    return "🟢"


def _health_status(score: float | None) -> str:
    if score is None:
        return "⚪"
    if score >= 80:
        return "🟢"
    if score >= 50:
        return "🟡"
    return "🔴"


def _metric_block(label: str, percent: float | None) -> list[str]:
    return [
        f"{_usage_status(percent)} {label}",
        _progress_bar(percent),
        _pct(percent),
        "",
    ]


def _health_block(score: float | None) -> list[str]:
    score_label = "—" if score is None else f"{round(score)} / 100"
    return [
        f"{_health_status(score)} Health",
        _progress_bar(score),
        score_label,
        "",
    ]


def _section(title: str, *blocks: list[str]) -> list[str]:
    lines = ["", HOURLY_RULE, "", title, ""]
    for block in blocks:
        lines.extend(block)
    return lines


def _format_last_backup_time(value: str, tz: tzinfo) -> str:
    if not value:
        return "—"
    parsed = _parse_sent(value)
    if parsed is None:
        return value
    return parsed.astimezone(tz).strftime("%H:%M")


def _sqlite_backup_report() -> tuple[str, str]:
    payload = sqlite_status_payload(get_settings())
    raw = str(payload.get("status") or "").strip().lower()
    labels = {
        "healthy": "Success",
        "success": "Success",
        "failed": "Failed",
        "disabled": "Disabled",
        "idle": "Idle",
    }
    return labels.get(raw, "Unknown"), str(payload.get("latest_at") or "")


def _backup_status_label(status: str) -> str:
    normalized = (status or "Unknown").strip() or "Unknown"
    lowered = normalized.lower()
    if lowered == "success":
        return "✅ Success"
    if lowered in {"failed", "error", "critical"}:
        return f"❌ {normalized}"
    return normalized


def _dashboard_url() -> str:
    return resolve_dashboard_url() or "—"


def _timezone_label(tz: tzinfo | None) -> str:
    key = getattr(tz, "key", None)
    if isinstance(key, str) and key:
        return key
    return "Asia/Bangkok"


def _report_footer(local: datetime, dashboard_url: str) -> list[str]:
    lines = [
        "",
        HOURLY_RULE,
        "",
        "Version",
        f"v{__version__}",
        "",
        "Sprint",
        REPORT_SPRINT,
        "",
        "Generated",
        _english_date(local),
        local.strftime("%H:%M:%S"),
        "",
        "Timezone",
        _timezone_label(local.tzinfo),
    ]
    if dashboard_url and dashboard_url != "—":
        lines.extend(["", "Dashboard", dashboard_url])
    return lines


def _executive_header(subtitle: str) -> list[str]:
    return [
        HOURLY_RULE,
        "",
        "🏠 HomeLab Monitor",
        "",
        subtitle,
        "",
        HOURLY_RULE,
        "",
    ]


def _compact_metric(emoji_label: str, value: str, bar: str | None = None) -> list[str]:
    line = f"{emoji_label} {value}"
    if bar:
        return [line, bar, ""]
    return [line, ""]


def _recommendation_block(recommendation: str) -> list[str]:
    text = recommendation.strip() or "Everything looks healthy."
    if text == "Everything looks healthy.":
        text = "Everything looks healthy.\n\nContinue monitoring."
    return [text, ""]


def _indexed_label(value: int) -> str:
    return f"{value:,}"


def _photo_new_today(db: Session, now: datetime) -> str:
    try:
        return str(PhotoEventRepository(db).today_count(now))
    except SQLAlchemyError:
        return "—"


def _recovered_today(db: Session, now: datetime) -> int:
    start = _start_of_local_day(now)
    count = 0
    for item in list_alert_history(db, now=now):
        if item.status != "recovered" or item.recovered_at is None:
            continue
        if as_utc(item.recovered_at) >= start:
            count += 1
    return count


def _recommendation_text(
    *,
    alerts: list,
    backup_status: str,
    insight: str | None,
) -> str:
    recs = _hourly_recommendations(alerts, backup_status)
    if recs:
        return recs[0]
    return insight or "Everything looks healthy."


def _stack(*rows: tuple[str, str]) -> list[str]:
    lines: list[str] = []
    for label, value in rows:
        lines.extend([label, value, ""])
    return lines


def format_hourly_report(
    *,
    local: datetime,
    cpu: float | None,
    memory: float | None,
    temperature: float | None,
    storage_percent: float | None,
    photos_new_today: str,
    immich_indexed: str,
    backup_status: str,
    last_backup: str,
    active_alerts: int,
    recovered_today: int,
    health_score: float | None,
    recommendation: str,
    dashboard_url: str,
    title: str = "🏠 HomeLab Hourly Report",
    qnap_section: str | None = None,
) -> str:
    tz = local.tzinfo or timezone(timedelta(hours=7))
    backup_time = _format_last_backup_time(last_backup, tz)
    header_status = _health_status(health_score)
    score_label = "—" if health_score is None else f"{round(health_score)}%"
    subtitle = "🧪 Test Report" if "Test Report" in title else "Hourly Executive Report"
    return "\n".join(
        [
            *_executive_header(subtitle),
            *_compact_metric(
                f"{header_status} Health",
                score_label,
                _progress_bar(health_score),
            ),
            *_compact_metric("🖥 CPU", _pct(cpu), _progress_bar(cpu)),
            *_compact_metric("🧠 Memory", _pct(memory), _progress_bar(memory)),
            *_compact_metric("💾 Storage", _pct(storage_percent), _progress_bar(storage_percent)),
            *_compact_metric("📷 Photos Today", photos_new_today),
            *_compact_metric("📷 Immich Indexed", immich_indexed),
            *_compact_metric("🌡 Temperature", _temperature_label(temperature)),
            *_compact_metric("💾 Backup", _backup_status_label(backup_status)),
            *_compact_metric("🕒 Last Backup", backup_time),
            *_compact_metric("⚠ Alerts", str(active_alerts)),
            *_compact_metric("Recovered Today", str(recovered_today)),
            "",
            qnap_section if qnap_section is not None else format_qnap_report_section(None),
            HOURLY_RULE,
            "",
            "💡 Recommendation",
            "",
            *_recommendation_block(recommendation),
            *_report_footer(local, dashboard_url),
        ]
    )


def format_daily_report(
    *,
    local: datetime,
    cpu_average: float | None,
    memory_average: float | None,
    temperature_average: float | None,
    storage_growth: str,
    photo_growth: str,
    backup_success: str,
    alerts_yesterday: int,
    health_score: float | None,
    recommendation: str,
    dashboard_url: str,
) -> str:
    header_status = _health_status(health_score)
    score_label = "—" if health_score is None else f"{round(health_score)}%"
    return "\n".join(
        [
            *_executive_header("Daily Executive Report"),
            *_compact_metric(
                f"{header_status} Health",
                score_label,
                _progress_bar(health_score),
            ),
            *_compact_metric("🖥 CPU", _pct(cpu_average), _progress_bar(cpu_average)),
            *_compact_metric("🧠 Memory", _pct(memory_average), _progress_bar(memory_average)),
            *_compact_metric("🌡 Temperature", _temperature_label(temperature_average)),
            *_compact_metric("💾 Storage", storage_growth),
            *_compact_metric("📷 Photos Today", photo_growth),
            *_compact_metric("💾 Backup", backup_success),
            *_compact_metric("⚠ Alerts", str(alerts_yesterday)),
            HOURLY_RULE,
            "",
            "💡 Recommendation",
            "",
            *_recommendation_block(recommendation),
            *_report_footer(local, dashboard_url),
        ]
    )


def format_weekly_report(
    *,
    local: datetime,
    cpu_average: float | None,
    memory_average: float | None,
    storage_growth: str,
    photo_growth: str,
    backup_success: str,
    forecast: str,
    recommendation: str,
    dashboard_url: str,
) -> str:
    return "\n".join(
        [
            *_executive_header("Weekly Executive Report"),
            *_compact_metric("🖥 CPU", _pct(cpu_average), _progress_bar(cpu_average)),
            *_compact_metric("🧠 Memory", _pct(memory_average), _progress_bar(memory_average)),
            *_compact_metric("💾 Storage", storage_growth),
            *_compact_metric("📷 Photos Today", photo_growth),
            *_compact_metric("💾 Backup", backup_success),
            *_compact_metric("📈 Capacity", forecast),
            HOURLY_RULE,
            "",
            "💡 Recommendation",
            "",
            *_recommendation_block(recommendation),
            *_report_footer(local, dashboard_url),
        ]
    )


def _qnap_hourly_section() -> str:
    try:
        from homelab_monitor.infrastructure import get_infrastructure_service

        snapshot = get_infrastructure_service().cached("qnap")
    except Exception:
        logger.exception("qnap_hourly_section_failed")
        return format_qnap_report_section(None)
    if snapshot is None:
        return format_qnap_report_section(None)
    if snapshot.status == "unknown" and not snapshot.summary:
        return format_qnap_report_section(None)
    return format_qnap_report_section(snapshot.summary)


def next_hourly(local: datetime, interval: int) -> datetime:
    aligned_hour = (local.hour // interval) * interval
    slot = local.replace(hour=aligned_hour, minute=0, second=0, microsecond=0)
    if local >= slot:
        slot = slot + timedelta(hours=interval)
    return slot


def next_daily(local: datetime, hour: int, minute: int) -> datetime:
    slot = local.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if local >= slot:
        slot = slot + timedelta(days=1)
    return slot


def next_weekly(local: datetime, weekday: int, hour: int, minute: int) -> datetime:
    slot = local.replace(hour=hour, minute=minute, second=0, microsecond=0)
    days_ahead = (weekday - slot.weekday()) % 7
    if days_ahead == 0 and local >= slot:
        days_ahead = 7
    return slot + timedelta(days=days_ahead)


def due_hourly(local: datetime, last: datetime | None, interval: int) -> bool:
    aligned_hour = (local.hour // interval) * interval
    slot = local.replace(hour=aligned_hour, minute=0, second=0, microsecond=0)
    if last is None:
        return True
    return as_utc(last) < slot.astimezone(UTC)


def due_daily(local: datetime, last: datetime | None, hour: int, minute: int) -> bool:
    slot = local.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if local < slot:
        return False
    if last is None:
        return True
    return as_utc(last).astimezone(slot.tzinfo).date() < local.date()


def due_weekly(
    local: datetime,
    last: datetime | None,
    weekday: int,
    hour: int,
    minute: int,
) -> bool:
    if local.weekday() != weekday:
        return False
    return due_daily(local, last, hour, minute)


class TelegramReportService:
    def __init__(
        self,
        analytics: AnalyticsService | None = None,
        trends: TrendService | None = None,
        capacity: CapacityPlanningService | None = None,
        insights: InsightService | None = None,
    ) -> None:
        self.analytics = analytics or AnalyticsService()
        self.trends = trends or TrendService(analytics=self.analytics)
        self.capacity = capacity or CapacityPlanningService(
            analytics=self.analytics, trends=self.trends
        )
        self.insights = insights or InsightService(
            analytics=self.analytics, trends=self.trends, capacity=self.capacity
        )

    def build(self, db: Session, kind: str, *, now: datetime | None = None) -> str:
        clock = now or datetime.now(UTC)
        if kind == "daily_report":
            return self._daily(db, clock)
        if kind == "weekly_report":
            return self._weekly(db, clock)
        if kind == "test_report":
            return self.build_test_report(db, now=clock)
        return self._hourly(db, clock)

    def _snapshot(self, db: Session, now: datetime) -> dict:
        overview = self.analytics.overview(db, now=now)
        cpu = self.analytics.cpu(db, now=now)
        memory = self.analytics.memory(db, now=now)
        temperature = self.analytics.temperature(db, now=now)
        photos = self.analytics.photos(db, now=now)
        backup = self.analytics.backup(db, now=now)
        storage = self.trends.storage(db, now=now)
        system = self.capacity.system(db, now=now)
        backup_status, sqlite_last_backup = _sqlite_backup_report()
        alerts = list_alert_history(db, status="active", now=now)
        current_photos, _, _ = self.analytics.photo_detail(db, now=now)
        return {
            "overview": overview,
            "cpu": cpu,
            "memory": memory,
            "temperature": temperature,
            "photos": photos,
            "backup": backup,
            "storage": storage,
            "score": system.overall_score,
            "backup_status": backup_status,
            "sqlite_last_backup": sqlite_last_backup,
            "alerts": alerts,
            "indexed_photos": current_photos,
        }

    def _hourly(self, db: Session, now: datetime) -> str:
        data = self._snapshot(db, now)
        tz = report_timezone(str(reports_payload(load_payload(db))["timezone"]))
        local = now.astimezone(tz)
        last_backup = str(data.get("sqlite_last_backup") or "")
        insight = self.insights.overview(db).recommendation
        return format_hourly_report(
            local=local,
            cpu=data["cpu"].current,
            memory=data["memory"].current,
            temperature=data["temperature"].current,
            storage_percent=data["storage"].used_percent,
            photos_new_today=_photo_new_today(db, now),
            immich_indexed=_indexed_label(int(data["indexed_photos"])),
            backup_status=data["backup_status"],
            last_backup=last_backup,
            active_alerts=len(data["alerts"]),
            recovered_today=_recovered_today(db, now),
            health_score=data["score"],
            recommendation=_recommendation_text(
                alerts=data["alerts"],
                backup_status=data["backup_status"],
                insight=insight,
            ),
            dashboard_url=_dashboard_url(),
            qnap_section=_qnap_hourly_section(),
        )

    def build_test_report(self, db: Session, *, now: datetime | None = None) -> str:
        clock = now or datetime.now(UTC)
        data = self._snapshot(db, clock)
        tz = report_timezone(str(reports_payload(load_payload(db))["timezone"]))
        local = clock.astimezone(tz)
        last_backup = str(data.get("sqlite_last_backup") or "")
        insight = self.insights.overview(db).recommendation
        return format_hourly_report(
            title="🧪 Test Report",
            local=local,
            cpu=data["cpu"].current,
            memory=data["memory"].current,
            temperature=data["temperature"].current,
            storage_percent=data["storage"].used_percent,
            photos_new_today=_photo_new_today(db, clock),
            immich_indexed=_indexed_label(int(data["indexed_photos"])),
            backup_status=data["backup_status"],
            last_backup=last_backup,
            active_alerts=len(data["alerts"]),
            recovered_today=_recovered_today(db, clock),
            health_score=data["score"],
            recommendation=_recommendation_text(
                alerts=data["alerts"],
                backup_status=data["backup_status"],
                insight=insight,
            ),
            dashboard_url=_dashboard_url(),
            qnap_section=_qnap_hourly_section(),
        )

    def _daily(self, db: Session, now: datetime) -> str:
        data = self._snapshot(db, now)
        tz = report_timezone(str(reports_payload(load_payload(db))["timezone"]))
        local = now.astimezone(tz)
        start_today = _start_of_local_day(now)
        yesterday = [
            item
            for item in list_alert_history(db, now=now)
            if item.started_at is not None
            and start_today - timedelta(days=1) <= as_utc(item.started_at) < start_today
        ]
        recommendation = self.insights.overview(db).recommendation or ("Everything looks healthy.")
        return format_daily_report(
            local=local,
            cpu_average=data["overview"].cpu_average,
            memory_average=data["overview"].memory_average,
            temperature_average=data["overview"].temperature_average,
            storage_growth=_bytes_label(float(data["storage"].daily_growth_bytes)),
            photo_growth=f"+{data['photos'].today}",
            backup_success=_pct(data["backup"].success_rate),
            alerts_yesterday=len(yesterday),
            health_score=data["score"],
            recommendation=recommendation,
            dashboard_url=_dashboard_url(),
        )

    def _weekly(self, db: Session, now: datetime) -> str:
        data = self._snapshot(db, now)
        cpu_trend = self.trends.cpu(db, now=now)
        memory_trend = self.trends.memory(db, now=now)
        capacity = self.capacity.storage(db, now=now)
        insight = self.insights.overview(db)
        days = capacity.estimated_days_remaining
        if days is None:
            forecast = "Capacity forecast is unknown."
        else:
            forecast = f"Estimated capacity remaining {days} days."
        tz = report_timezone(str(reports_payload(load_payload(db))["timezone"]))
        local = now.astimezone(tz)
        recommendation = insight.recommendation or "Everything looks healthy."
        return format_weekly_report(
            local=local,
            cpu_average=cpu_trend.average_7d,
            memory_average=memory_trend.average_7d,
            storage_growth=_bytes_label(float(data["storage"].weekly_growth_bytes)),
            photo_growth=f"+{data['photos'].this_week}",
            backup_success=_pct(data["backup"].success_rate),
            forecast=forecast,
            recommendation=recommendation,
            dashboard_url=_dashboard_url(),
        )


def send_manual_test_report(
    db: Session,
    settings: Settings,
    *,
    now: datetime | None = None,
) -> Notification:
    message = TelegramReportService().build_test_report(db, now=now)
    return dispatch_telegram_report(db, settings, kind="test_report", message=message)


def public_reports(payload: dict, *, now: datetime | None = None) -> dict:
    reports = reports_payload(payload)
    clock = now or datetime.now(UTC)
    tz = report_timezone(str(reports["timezone"]))
    local = clock.astimezone(tz)
    interval = int(reports["hour_interval"])
    daily_hour, daily_minute = _parse_time(str(reports["daily_time"]))
    weekly_hour, weekly_time = _parse_time(str(reports["weekly_time"]))
    weekday = WEEKDAYS.get(str(reports["weekly_day"]).lower(), 6)
    last_sent = reports.get("last_sent") if isinstance(reports.get("last_sent"), dict) else {}
    cards = {
        "hourly": {
            "enabled": bool(reports["hourly_enabled"]),
            "last_sent": _parse_sent(last_sent.get("hourly_report")),
            "next_scheduled": next_hourly(local, interval).isoformat(),
            "status": "enabled" if reports["hourly_enabled"] else "disabled",
        },
        "daily": {
            "enabled": bool(reports["daily_enabled"]),
            "last_sent": _parse_sent(last_sent.get("daily_report")),
            "next_scheduled": next_daily(local, daily_hour, daily_minute).isoformat(),
            "status": "enabled" if reports["daily_enabled"] else "disabled",
        },
        "weekly": {
            "enabled": bool(reports["weekly_enabled"]),
            "last_sent": _parse_sent(last_sent.get("weekly_report")),
            "next_scheduled": next_weekly(local, weekday, weekly_hour, weekly_time).isoformat(),
            "status": "enabled" if reports["weekly_enabled"] else "disabled",
        },
    }
    return {
        "hourly_enabled": bool(reports["hourly_enabled"]),
        "daily_enabled": bool(reports["daily_enabled"]),
        "weekly_enabled": bool(reports["weekly_enabled"]),
        "hour_interval": interval,
        "daily_time": str(reports["daily_time"]),
        "weekly_day": str(reports["weekly_day"]),
        "weekly_time": str(reports["weekly_time"]),
        "timezone": str(reports["timezone"]),
        **cards,
    }


def _mark_sent(payload: dict, kind: str, when: datetime) -> dict:
    reports = reports_payload(payload)
    last_sent = dict(reports.get("last_sent") or {})
    last_sent[kind] = as_utc(when).isoformat()
    reports["last_sent"] = last_sent
    next_payload = dict(payload)
    next_payload["reports"] = reports
    return next_payload


def process_due_reports(
    db: Session,
    settings: Settings,
    *,
    now: datetime | None = None,
    service: TelegramReportService | None = None,
) -> list[Notification]:
    clock = now or datetime.now(UTC)
    payload = load_payload(db)
    reports = reports_payload(payload)
    tz = report_timezone(str(reports["timezone"]))
    local = clock.astimezone(tz)
    last_sent = reports.get("last_sent") if isinstance(reports.get("last_sent"), dict) else {}
    interval = int(reports["hour_interval"])
    daily_hour, daily_minute = _parse_time(str(reports["daily_time"]))
    weekly_hour, weekly_minute = _parse_time(str(reports["weekly_time"]))
    weekday = WEEKDAYS.get(str(reports["weekly_day"]).lower(), 6)
    builder = service or TelegramReportService()
    due: list[tuple[str, bool]] = []
    if due_hourly(local, _parse_sent(last_sent.get("hourly_report")), interval):
        due.append(("hourly_report", bool(reports["hourly_enabled"])))
    if due_daily(local, _parse_sent(last_sent.get("daily_report")), daily_hour, daily_minute):
        due.append(("daily_report", bool(reports["daily_enabled"])))
    if due_weekly(
        local, _parse_sent(last_sent.get("weekly_report")), weekday, weekly_hour, weekly_minute
    ):
        due.append(("weekly_report", bool(reports["weekly_enabled"])))
    rows: list[Notification] = []
    for kind, enabled in due:
        if not enabled:
            continue
        message = builder.build(db, kind, now=clock)
        row = dispatch_telegram_report(db, settings, kind=kind, message=message)
        if row is not None:
            rows.append(row)
        payload = _mark_sent(payload, kind, clock)
        save_payload(db, payload)
    return rows


def tick_telegram_reports(settings: Settings, *, now: datetime | None = None) -> None:
    with writer_operation("telegram_report_update"), Session(get_engine()) as db:
        process_due_reports(db, settings, now=now)


async def run_report_clock(
    settings: Settings,
    *,
    sleep: Callable[[float], Awaitable[None]] | None = None,
    tick: Callable[[Settings], None] | None = None,
) -> None:
    sleeper = asyncio.sleep if sleep is None else sleep
    operation = tick_telegram_reports if tick is None else tick
    await sleeper(TICK_SECONDS)
    await asyncio.to_thread(operation, settings)


async def run_telegram_reports(settings: Settings) -> None:
    async def report_pass() -> None:
        try:
            await run_report_clock(settings)
        except SQLAlchemyError:
            logger.exception("telegram_report_tick_failed")

    await run_repeated(report_pass)
