from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from homelab_monitor.errors import APIError
from homelab_monitor.infrastructure_monitor import run_infrastructure_monitor
from homelab_monitor.notification_worker import run_notification_worker
from homelab_monitor.offline_monitor import run_offline_monitor
from homelab_monitor.photo_watcher import (
    _scan_and_interval,
    get_photo_watcher_service,
    reset_photo_watcher_service,
    run_photo_watcher,
)
from homelab_monitor.production_health import ProductionHealthService
from homelab_monitor.runtime_control import restart_background
from homelab_monitor.settings import Settings, get_settings
from homelab_monitor.sqlite_backup import run_backup_once, run_sqlite_backup
from homelab_monitor.telegram import TelegramNotificationError, TelegramNotifier
from homelab_monitor.telegram_reports import run_telegram_reports

logger = logging.getLogger("homelab_monitor.operations")

CATALOG = (
    ("backup_now", "Run Backup Now", False),
    ("telegram_test", "Run Telegram Test", False),
    ("photo_scan", "Run Photo Scan", False),
    ("health_check", "Run Health Check", False),
    ("system_audit", "Run System Audit", False),
    ("restart_api", "Restart API", True),
    ("restart_dashboard", "Restart Dashboard", True),
    ("restart_photo_monitor", "Restart Photo Monitor", False),
    ("restart_scheduler", "Restart Scheduler", False),
    ("reload_configuration", "Reload Configuration", False),
    ("clear_cache", "Clear Cache", False),
)


def history_path(settings: Settings) -> Path:
    raw = settings.database_url.removeprefix("sqlite:///")
    parent = Path(raw).parent if raw and raw != ":memory:" else Path("data")
    parent.mkdir(parents=True, exist_ok=True)
    return parent / "operations-history.json"


def load_history(settings: Settings) -> list[dict]:
    path = history_path(settings)
    if not path.is_file():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return list(payload) if isinstance(payload, list) else []


def save_history(settings: Settings, rows: list[dict]) -> None:
    path = history_path(settings)
    path.write_text(json.dumps(rows[-200:], indent=2), encoding="utf-8")


def catalog() -> list[dict]:
    return [
        {"id": op_id, "label": label, "admin_only": admin_only}
        for op_id, label, admin_only in CATALOG
    ]


def run_operation(
    op_id: str,
    *,
    settings: Settings,
    db: Session,
    username: str,
    role: str,
    confirm: bool,
) -> dict:
    if not confirm:
        raise APIError(400, "confirmation_required", "Set confirm=true to run this operation")
    match = next((item for item in CATALOG if item[0] == op_id), None)
    if match is None:
        raise APIError(404, "operation_not_found", "Unknown operation")
    if match[2] and role != "admin":
        raise APIError(403, "permission_denied", "Only an admin can run this operation")
    record = {
        "id": str(uuid4()),
        "operation": op_id,
        "label": match[1],
        "status": "running",
        "progress": "started",
        "actor": username,
        "started_at": datetime.now(UTC).isoformat(),
        "finished_at": None,
        "ok": None,
        "detail": "",
    }
    rows = load_history(settings)
    rows.append(record)
    save_history(settings, rows)
    started = time.perf_counter()
    try:
        detail = _dispatch(op_id, settings=settings, db=db)
        record["ok"] = True
        record["status"] = "success"
        record["progress"] = "complete"
        record["detail"] = detail
    except Exception as error:
        logger.exception("operation_failed id=%s", op_id)
        record["ok"] = False
        record["status"] = "failed"
        record["progress"] = "failed"
        record["detail"] = str(error)
    record["finished_at"] = datetime.now(UTC).isoformat()
    record["duration_ms"] = round((time.perf_counter() - started) * 1000, 2)
    save_history(settings, rows)
    return record


def _dispatch(op_id: str, *, settings: Settings, db: Session) -> str:
    if op_id == "backup_now":
        result = run_backup_once(settings, notify=True)
        if not result.ok:
            raise RuntimeError(result.error or "backup failed")
        return result.path
    if op_id == "telegram_test":
        notifier = TelegramNotifier.from_settings(settings)
        if notifier is None:
            raise RuntimeError("Telegram is not configured")
        try:
            notifier.send_text("HomeLab Monitor Telegram test from Operations Center")
        except TelegramNotificationError as error:
            raise RuntimeError(str(error)) from error
        finally:
            notifier.close()
        return "Telegram test sent"
    if op_id == "photo_scan":
        service = get_photo_watcher_service(settings)
        created = _scan_and_interval(settings, service)
        return f"Photo scan finished interval={created}"
    if op_id == "health_check":
        health = ProductionHealthService().health(db)
        return f"Health score {health.score} ({health.status})"
    if op_id == "system_audit":
        health = ProductionHealthService().health(db)
        backup = run_backup_once(settings, notify=False)
        return f"Audit score={health.score} backup_ok={backup.ok}"
    if op_id == "reload_configuration":
        get_settings.cache_clear()
        get_settings()
        return "Settings cache reloaded"
    if op_id == "clear_cache":
        reset_photo_watcher_service()
        get_photo_watcher_service(get_settings())
        return "Photo Monitor cache cleared"
    if op_id == "restart_photo_monitor":
        _schedule(lambda: restart_background("photo_watcher"))
        return "Photo Monitor restart scheduled"
    if op_id == "restart_scheduler":
        _schedule(lambda: restart_background("sqlite_backup"))
        return "Backup scheduler restart scheduled"
    if op_id == "restart_dashboard":
        return _restart_container("dashboard")
    if op_id == "restart_api":
        threading.Timer(1.0, os._exit, args=(0,)).start()
        return "API process will exit in 1s (Compose should restart it)"
    raise RuntimeError("unhandled operation")


_background: set[asyncio.Task[Any]] = set()


def _schedule(action) -> None:  # type: ignore[no-untyped-def]
    async def _run() -> None:
        await action()

    try:
        loop = asyncio.get_running_loop()
        task = loop.create_task(_run())
        _background.add(task)
        task.add_done_callback(_background.discard)
    except RuntimeError:
        pass


def _restart_container(name: str) -> str:
    try:
        listed = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}}"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise RuntimeError("Docker CLI is unavailable") from error
    target = next(
        (item for item in listed.stdout.splitlines() if name in item and "homelab-monitor" in item),
        None,
    )
    if target is None:
        raise RuntimeError(f"No running {name} container")
    result = subprocess.run(
        ["docker", "restart", target], capture_output=True, text=True, timeout=30, check=False
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "docker restart failed")
    return f"Restarted {target}"


def factories(settings: Settings) -> dict:
    return {
        "offline_monitor": lambda: run_offline_monitor(settings),
        "infrastructure_monitor": lambda: run_infrastructure_monitor(settings),
        "telegram_reports": lambda: run_telegram_reports(settings),
        "notification_worker": lambda: run_notification_worker(settings),
        "photo_watcher": lambda: run_photo_watcher(settings),
        "sqlite_backup": lambda: run_sqlite_backup(settings),
    }
