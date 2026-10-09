from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from homelab_monitor.models import Alert, Notification
from homelab_monitor.photo_watcher import get_photo_watcher_service
from homelab_monitor.production_health import ProductionHealthService
from homelab_monitor.settings import Settings
from homelab_monitor.sqlite_backup import sqlite_status_payload


class LocalHeuristicProvider:
    """Read-only explanations. Never mutates the platform."""

    name = "local-heuristic"


def briefing(db: Session, settings: Settings) -> dict:
    health = ProductionHealthService().health(db)
    alerts = int(
        db.scalar(select(func.count()).select_from(Alert).where(Alert.status == "active")) or 0
    )
    telegram_failed = int(
        db.scalar(
            select(func.count())
            .select_from(Notification)
            .where(Notification.channel == "telegram", Notification.status == "failed")
        )
        or 0
    )
    backup = sqlite_status_payload(settings)
    photo = get_photo_watcher_service(settings)
    causes: list[str] = []
    checks: list[str] = []
    actions: list[str] = []
    if health.score < 75:
        causes.append("One or more production health checks are warning or critical.")
        checks.append("Open Production Health and review Auto Diagnostics.")
    if alerts:
        causes.append(f"{alerts} active alert(s) are open.")
        checks.append("Review Alerts and acknowledge recovered items.")
    if backup.get("integrity") != "PASS":
        causes.append("No verified SQLite backup is recorded.")
        checks.append("Run Backup Now from Operations Center.")
        actions.append("Copy a PASS gzip off the data volume after the next success.")
    if telegram_failed:
        causes.append("Telegram delivery has failed rows in notification history.")
        checks.append("Verify TELEGRAM_BOT_TOKEN, chat ID, and dashboard URL for buttons.")
    if photo.last_successful_scan is None:
        causes.append("Photo Monitor has not completed a successful scan.")
        checks.append("Confirm CIFS mounts under /mnt and Photo Monitor settings.")
    if not causes:
        causes.append("No active platform faults were inferred from current telemetry.")
        actions.append("No change is required. Continue the 02:00 backup watch.")
    else:
        actions.append("Do not change architecture. Follow the listed checks only.")
    return {
        "provider": LocalHeuristicProvider.name,
        "generated_at": datetime.now(UTC).isoformat(),
        "read_only": True,
        "summary": (
            f"Health score {health.score} ({health.status}). "
            f"{alerts} active alert(s). Backup integrity {backup.get('integrity') or 'unknown'}."
        ),
        "root_cause": causes,
        "possible_impact": [
            "Operators may miss outages if Telegram is failing.",
            "Photo ingest alerts pause if the watcher cannot scan.",
            "Restore pointage grows if backups are not verifying.",
        ],
        "recommended_checks": checks or ["Refresh Production Health."],
        "recommended_actions": actions,
        "never_modifies_platform": True,
    }
