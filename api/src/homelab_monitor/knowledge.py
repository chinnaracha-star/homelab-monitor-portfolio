from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from homelab_monitor.models import Alert, Notification, OpsSnapshot, PhotoEvent
from homelab_monitor.operations import load_history
from homelab_monitor.settings import Settings
from homelab_monitor.sqlite_backup import load_state


def collect(db: Session, settings: Settings, *, query: str = "", kind: str = "all") -> dict:
    needle = query.strip().lower()
    items: list[dict] = []
    for alert in db.scalars(select(Alert).order_by(Alert.opened_at.desc()).limit(100)).all():
        items.append(
            _item(
                "incident",
                alert.message,
                alert.opened_at,
                {"status": alert.status, "kind": alert.kind, "severity": alert.severity},
            )
        )
    for note in db.scalars(
        select(Notification).order_by(Notification.created_at.desc()).limit(100)
    ).all():
        items.append(
            _item(
                "telegram",
                note.error_message or note.status,
                note.created_at,
                {"channel": note.channel, "status": note.status},
            )
        )
    for photo in db.scalars(
        select(PhotoEvent).order_by(PhotoEvent.created_at.desc()).limit(100)
    ).all():
        items.append(
            _item(
                "photo",
                photo.filename,
                photo.created_at,
                {"folder": photo.folder},
            )
        )
    for snap in db.scalars(
        select(OpsSnapshot).order_by(OpsSnapshot.observed_at.desc()).limit(100)
    ).all():
        items.append(
            _item(
                "system",
                snap.kind,
                snap.observed_at,
                {"kind": snap.kind},
            )
        )
    backup = load_state(settings).get("latest") or {}
    if backup:
        items.append(
            _item(
                "backup",
                str(backup.get("path") or "sqlite backup"),
                _parse(backup.get("created_at")),
                {"integrity": backup.get("integrity"), "status": backup.get("status")},
            )
        )
    for row in load_history(settings):
        items.append(
            _item(
                "maintenance",
                str(row.get("label") or row.get("operation")),
                _parse(row.get("started_at")),
                {"status": row.get("status")},
            )
        )
    if kind != "all":
        items = [item for item in items if item["kind"] == kind]
    if needle:
        items = [
            item
            for item in items
            if needle in item["title"].lower() or needle in str(item["details"]).lower()
        ]
    items.sort(key=lambda item: item["timestamp"] or "", reverse=True)
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "count": len(items),
        "items": items[:200],
    }


def _item(kind: str, title: str, stamp: datetime | str | None, details: dict) -> dict:
    iso = stamp.isoformat() if isinstance(stamp, datetime) else str(stamp or "")
    return {"kind": kind, "title": title, "timestamp": iso, "details": details}


def _parse(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value:
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None
