from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from sqlalchemy.orm import Session

from homelab_monitor.photo_watcher import get_photo_watcher_service
from homelab_monitor.settings import Settings, get_settings
from homelab_monitor.sqlite_backup import sqlite_status_payload

Lifecycle = Literal["discovered", "loaded", "started", "stopped", "unloaded"]


def plugins_root() -> Path:
    candidates = (
        Path("/app/plugins"),
        Path(__file__).resolve().parents[3] / "plugins",
        Path.cwd() / "plugins",
    )
    for path in candidates:
        if path.is_dir():
            return path
    return candidates[1]


@dataclass
class PluginRecord:
    name: str
    version: str
    author: str
    description: str
    capabilities: list[str]
    status: str
    health: str
    configuration: dict
    lifecycle: Lifecycle = "discovered"
    plugin_id: str = ""
    builtin: bool = True

    def to_dict(self) -> dict:
        return {
            "id": self.plugin_id,
            "name": self.name,
            "version": self.version,
            "author": self.author,
            "description": self.description,
            "capabilities": self.capabilities,
            "status": self.status,
            "health": self.health,
            "configuration": self.configuration,
            "lifecycle": self.lifecycle,
            "builtin": self.builtin,
        }


_registry: dict[str, PluginRecord] = {}


def discover() -> list[PluginRecord]:
    records: dict[str, PluginRecord] = {}
    root = plugins_root()
    if root.is_dir():
        for folder in sorted(item for item in root.iterdir() if item.is_dir()):
            if folder.name in {"examples", "sdk"}:
                continue
            manifest = folder / "manifest.json"
            if not manifest.is_file():
                continue
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            config_path = folder / "config.json"
            configuration = {}
            if config_path.is_file():
                configuration = json.loads(config_path.read_text(encoding="utf-8"))
            plugin_id = str(payload.get("id") or folder.name)
            records[plugin_id] = PluginRecord(
                plugin_id=plugin_id,
                name=str(payload.get("name") or folder.name),
                version=str(payload.get("version") or "0.0.0"),
                author=str(payload.get("author") or "HomeLab Monitor"),
                description=str(payload.get("description") or ""),
                capabilities=list(payload.get("capabilities") or []),
                status="discovered",
                health="unknown",
                configuration=configuration,
                lifecycle="discovered",
                builtin=bool(payload.get("builtin", True)),
            )
    if not records:
        records = _builtin_fallback()
    _registry.clear()
    _registry.update(records)
    return list(_registry.values())


def load_all() -> list[PluginRecord]:
    if not _registry:
        discover()
    for item in _registry.values():
        if item.lifecycle in {"discovered", "unloaded"}:
            item.lifecycle = "loaded"
            item.status = "loaded"
    return list(_registry.values())


def start_all(settings: Settings | None = None, db: Session | None = None) -> list[PluginRecord]:
    load_all()
    for item in _registry.values():
        start(item.plugin_id, settings=settings, db=db)
    return list(_registry.values())


def start(
    plugin_id: str, settings: Settings | None = None, db: Session | None = None
) -> PluginRecord:
    item = _require(plugin_id)
    item.lifecycle = "started"
    item.status = "running"
    item.health = health_check(plugin_id, settings=settings, db=db)
    return item


def stop(plugin_id: str) -> PluginRecord:
    item = _require(plugin_id)
    item.lifecycle = "stopped"
    item.status = "stopped"
    return item


def unload(plugin_id: str) -> PluginRecord:
    item = stop(plugin_id)
    item.lifecycle = "unloaded"
    item.status = "unloaded"
    return item


def health_check(
    plugin_id: str, settings: Settings | None = None, db: Session | None = None
) -> str:
    item = _require(plugin_id)
    settings = settings or get_settings()
    if plugin_id == "core-system":
        item.health = "healthy"
    elif plugin_id == "telegram":
        token = settings.telegram_bot_token
        item.health = (
            "healthy"
            if settings.telegram_enabled and token and settings.telegram_chat_id
            else "unknown"
        )
    elif plugin_id == "photo-monitor":
        watcher = get_photo_watcher_service(settings)
        item.health = "healthy" if watcher.last_successful_scan else "unknown"
    elif plugin_id == "backup":
        payload = sqlite_status_payload(settings)
        item.health = "healthy" if payload.get("integrity") == "PASS" else "unknown"
    elif plugin_id == "analytics":
        item.health = "healthy"
    else:
        item.health = "unknown"
    return item.health


def list_plugins(settings: Settings | None = None, db: Session | None = None) -> list[dict]:
    if not _registry:
        discover()
        start_all(settings=settings, db=db)
    for plugin_id in list(_registry):
        if _registry[plugin_id].lifecycle == "started":
            health_check(plugin_id, settings=settings, db=db)
    return [item.to_dict() for item in _registry.values()]


def apply_lifecycle(plugin_id: str, action: str) -> PluginRecord:
    if action == "discover":
        discover()
        return _require(plugin_id)
    if action == "load":
        load_all()
        return _require(plugin_id)
    if action == "start":
        return start(plugin_id)
    if action == "health":
        health_check(plugin_id)
        return _require(plugin_id)
    if action == "stop":
        return stop(plugin_id)
    if action == "unload":
        return unload(plugin_id)
    raise ValueError(f"unknown lifecycle action {action}")


def reset_plugins() -> None:
    _registry.clear()


def _require(plugin_id: str) -> PluginRecord:
    if plugin_id not in _registry:
        discover()
    if plugin_id not in _registry:
        raise KeyError(plugin_id)
    return _registry[plugin_id]


def _builtin_fallback() -> dict[str, PluginRecord]:
    names = (
        ("core-system", "Core System", ["runtime"]),
        ("telegram", "Telegram", ["notify"]),
        ("photo-monitor", "Photo Monitor", ["photos"]),
        ("backup", "Backup", ["backup"]),
        ("analytics", "Analytics", ["metrics"]),
    )
    return {
        plugin_id: PluginRecord(
            plugin_id=plugin_id,
            name=name,
            version="1.0.0-rc3",
            author="HomeLab Monitor",
            description=f"Built-in adapter for {name}",
            capabilities=caps,
            status="discovered",
            health="unknown",
            configuration={},
            builtin=True,
        )
        for plugin_id, name, caps in names
    }
