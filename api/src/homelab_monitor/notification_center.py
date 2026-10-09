from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from homelab_monitor.alert_engine import as_alert_utc
from homelab_monitor.models import Alert, Notification
from homelab_monitor.notifications import REPORT_TITLES
from homelab_monitor.schemas import (
    NotificationCenterItem,
    NotificationDayGroup,
    NotificationHistoryResponse,
    NotificationStatisticsResponse,
)
from homelab_monitor.telegram import THAI_MONTHS

BANGKOK = timezone(timedelta(hours=7))


def _read_state(status: str) -> str:
    return "read" if status == "sent" else "unread"


def _source_kind(notification: Notification) -> str:
    if notification.recipient in REPORT_TITLES:
        return notification.recipient
    alert = notification.alert
    if alert is None:
        return "system"
    if alert.status != "active" and alert.resolved_at is not None:
        created = as_alert_utc(notification.created_at)
        recovered = as_alert_utc(alert.resolved_at)
        if created >= recovered:
            return "recovery"
    if alert.kind.startswith("backup") or alert.resource == "backup":
        return "backup"
    return "alert"


def _title(item_kind: str, notification: Notification) -> str:
    if item_kind in REPORT_TITLES:
        return REPORT_TITLES[item_kind]
    alert = notification.alert
    if item_kind == "recovery" and alert is not None:
        return f"{alert.kind} recovered"
    if item_kind == "alert" and alert is not None:
        return alert.kind.replace("_", " ")
    if item_kind == "backup":
        return "Backup notification"
    return "System notification"


def _severity(notification: Notification) -> str:
    if notification.alert is not None:
        return notification.alert.severity
    return "info"


def to_center_item(notification: Notification) -> NotificationCenterItem:
    kind = _source_kind(notification)
    alert = notification.alert
    return NotificationCenterItem(
        id=notification.id,
        title=_title(kind, notification),
        description=(
            (notification.error_message or notification.status.title())
            if notification.recipient in REPORT_TITLES
            else (alert.message if alert is not None else (notification.error_message or kind))
        ),
        severity=_severity(notification),
        source=notification.channel,
        kind=kind,
        agent_id=alert.agent_id if alert is not None else None,
        agent_name=alert.agent.name if alert is not None else None,
        read_state=_read_state(notification.status),
        created_at=notification.created_at,
    )


def list_notification_center(
    db: Session,
    *,
    severity: str | None = None,
    source: str | None = None,
    agent_id: str | None = None,
    date: str | None = None,
    read_state: str | None = None,
) -> NotificationHistoryResponse:
    rows = list(
        db.scalars(
            select(Notification)
            .options(joinedload(Notification.alert).joinedload(Alert.agent))
            .order_by(Notification.created_at.desc(), Notification.id.desc())
        )
        .unique()
        .all()
    )
    items = [to_center_item(row) for row in rows]
    if severity:
        items = [item for item in items if item.severity == severity]
    if source:
        items = [item for item in items if item.source == source]
    if agent_id:
        items = [item for item in items if item.agent_id == agent_id]
    if read_state:
        items = [item for item in items if item.read_state == read_state]
    if date:
        items = [
            item
            for item in items
            if as_alert_utc(item.created_at).date().isoformat() == date
            or as_alert_utc(item.created_at).astimezone(BANGKOK).date().isoformat() == date
        ]
    groups_map: dict[str, list[NotificationCenterItem]] = defaultdict(list)
    for item in items:
        local = as_alert_utc(item.created_at).astimezone(BANGKOK)
        key = local.date().isoformat()
        groups_map[key].append(item)
    groups = []
    for key in sorted(groups_map.keys(), reverse=True):
        local = datetime.strptime(key, "%Y-%m-%d").replace(tzinfo=BANGKOK)
        label = f"{local.day} {THAI_MONTHS[local.month]} {local.year + 543}"
        groups.append(NotificationDayGroup(date=key, label=label, items=groups_map[key]))
    return NotificationHistoryResponse(items=items, groups=groups)


def notification_center_statistics(
    db: Session,
    *,
    now: datetime | None = None,
) -> NotificationStatisticsResponse:
    clock = now or datetime.now(UTC)
    history = list_notification_center(db)
    items = history.items
    start_today = clock.astimezone(BANGKOK).replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = start_today - timedelta(days=start_today.weekday())
    today = 0
    week = 0
    for item in items:
        local = as_alert_utc(item.created_at).astimezone(BANGKOK)
        if local >= start_today:
            today += 1
        if local >= week_start:
            week += 1
    return NotificationStatisticsResponse(
        unread=sum(1 for item in items if item.read_state == "unread"),
        today=today,
        this_week=week,
        critical=sum(1 for item in items if item.severity == "critical"),
        total=len(items),
    )
