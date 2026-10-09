import logging
import time
from datetime import UTC, datetime

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from homelab_monitor.alert_engine import AlertEvent
from homelab_monitor.database import get_engine
from homelab_monitor.models import Alert, Notification
from homelab_monitor.notifications import (
    REPORT_RECIPIENTS,
    RETRY_ATTEMPTS,
    RETRY_DELAY_SECONDS,
    channel_payload,
)
from homelab_monitor.notifications.config import build_telegram_notifier, load_payload
from homelab_monitor.notifications.email import EmailProvider
from homelab_monitor.notifications.provider import DeliveryError
from homelab_monitor.notifications.service import NotificationService
from homelab_monitor.notifications.telegram import TelegramProvider
from homelab_monitor.notifications.webhooks import discord_provider, slack_provider
from homelab_monitor.realtime import hub
from homelab_monitor.settings import Settings
from homelab_monitor.telegram import (
    TelegramNotificationError,
    TelegramNotifier,
    format_alert_message,
    format_telegram_test_message,
)

logger = logging.getLogger("homelab_monitor.notifications")


def _alert_id(db: Session, event: AlertEvent) -> str | None:
    return db.scalar(
        select(Alert.id).where(
            Alert.agent_id == event.agent_id,
            Alert.kind == event.kind,
            Alert.resource == event.resource,
        )
    )


def _providers(
    settings: Settings,
    payload: dict,
    telegram_notifier: TelegramNotifier | None,
) -> list:
    providers = []
    try:
        notifier = build_telegram_notifier(settings, payload, telegram_notifier)
    except ValueError as error:
        logger.error("telegram_configuration_invalid", extra={"reason": str(error)})
        notifier = None
    if notifier is not None:
        providers.append(TelegramProvider(notifier, close_notifier=telegram_notifier is None))

    discord = channel_payload(payload, "discord")
    if discord.get("enabled") and discord.get("webhook_url"):
        try:
            providers.append(discord_provider(str(discord["webhook_url"])))
        except ValueError as error:
            logger.error("discord_configuration_invalid", extra={"reason": str(error)})
    slack = channel_payload(payload, "slack")
    if slack.get("enabled") and slack.get("webhook_url"):
        try:
            providers.append(slack_provider(str(slack["webhook_url"])))
        except ValueError as error:
            logger.error("slack_configuration_invalid", extra={"reason": str(error)})
    email = channel_payload(payload, "email")
    if email.get("enabled") and email.get("host") and email.get("to_address"):
        try:
            providers.append(
                EmailProvider(
                    host=str(email.get("host") or ""),
                    port=int(email.get("port") or 587),
                    username=str(email.get("username") or ""),
                    password=str(email.get("password") or ""),
                    from_address=str(email.get("from_address") or ""),
                    to_address=str(email.get("to_address") or ""),
                    use_tls=bool(email.get("use_tls", True)),
                )
            )
        except ValueError as error:
            logger.error("email_configuration_invalid", extra={"reason": str(error)})
    return providers


class _ReportDelivery:
    """One report send through NotificationService. Retry stays in _deliver."""

    channel = "telegram"

    def __init__(self, notifier: TelegramNotifier) -> None:
        self._service = NotificationService(notifier)

    def send(self, message: str) -> None:
        try:
            self._service.send_text(message)
        except (TelegramNotificationError, httpx.HTTPError) as error:
            raise DeliveryError(str(error)) from error


def _deliver(provider, message: str) -> str:
    last_error = "delivery failed"
    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            provider.send(message)
            return ""
        except Exception as error:
            last_error = str(error)[:1000]
            logger.exception(
                "notification_delivery_failed",
                extra={"channel": provider.channel, "attempt": attempt},
            )
            if attempt < RETRY_ATTEMPTS:
                time.sleep(RETRY_DELAY_SECONDS)
    return last_error


def _record(
    db: Session,
    *,
    alert_id: str | None,
    channel: str,
    recipient: str,
    error: str,
    status: str | None = None,
) -> Notification:
    now = datetime.now(UTC)
    resolved = "sent" if not error else "failed"
    if status is not None:
        resolved = status
    row = Notification(
        alert_id=alert_id,
        channel=channel,
        recipient=recipient,
        status=resolved,
        error_message=error,
        sent_at=now if resolved == "sent" else None,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def dispatch_telegram_report(
    db: Session,
    settings: Settings,
    *,
    kind: str,
    message: str,
) -> Notification:
    payload = load_payload(db)
    providers = [item for item in _providers(settings, payload, None) if item.channel == "telegram"]
    if not providers:
        row = _record(
            db,
            alert_id=None,
            channel="telegram",
            recipient=kind,
            error="Telegram is not configured",
            status="skipped",
        )
        hub.publish("overview_updated", reason="notification_updated")
        hub.publish("alert_updated", reason="notification_updated")
        return row
    provider = providers[0]
    try:
        error = _deliver(_ReportDelivery(provider._notifier), message)
    finally:
        provider.close()
    status = "sent" if not error else "failed"
    row = _record(
        db,
        alert_id=None,
        channel="telegram",
        recipient=kind,
        error=error,
        status=status,
    )
    hub.publish("overview_updated", reason="notification_updated")
    hub.publish("alert_updated", reason="notification_updated")
    return row


def dispatch_alert_notifications(
    settings: Settings,
    events: list[AlertEvent],
    telegram_notifier: TelegramNotifier | None = None,
) -> None:
    if not events:
        return

    with Session(get_engine()) as db:
        payload = load_payload(db)
        providers = _providers(settings, payload, telegram_notifier)
        if not providers:
            logger.info("notifications_disabled")
            if telegram_notifier is not None:
                telegram_notifier.close()
            return
        try:
            for event in events:
                message = format_alert_message(event)
                alert_id = _alert_id(db, event)
                for provider in providers:
                    error = _deliver(provider, message)
                    _record(
                        db,
                        alert_id=alert_id,
                        channel=provider.channel,
                        recipient=provider.recipient,
                        error=error,
                    )
                    if error:
                        logger.info(
                            "notification_failed",
                            extra={"channel": provider.channel, "kind": event.kind},
                        )
                    else:
                        logger.info(
                            "notification_sent",
                            extra={"channel": provider.channel, "kind": event.kind},
                        )
        finally:
            for provider in providers:
                provider.close()
    hub.publish("overview_updated", reason="notification_updated")
    hub.publish("alert_updated", reason="notification_updated")


def send_test_notification(
    db: Session,
    settings: Settings,
    channel: str | None = None,
) -> list[Notification]:
    payload = load_payload(db)
    providers = _providers(settings, payload, None)
    if channel:
        providers = [item for item in providers if item.channel == channel]
    if not providers:
        return []
    message = "HomeLab Monitor: Test notification"
    rows: list[Notification] = []
    try:
        for provider in providers:
            payload_message = (
                format_telegram_test_message(server=settings.environment)
                if provider.channel == "telegram"
                else message
            )
            error = _deliver(provider, payload_message)
            rows.append(
                _record(
                    db,
                    alert_id=None,
                    channel=provider.channel,
                    recipient=provider.recipient,
                    error=error,
                )
            )
    finally:
        for provider in providers:
            provider.close()
    hub.publish("overview_updated", reason="notification_updated")
    hub.publish("alert_updated", reason="notification_updated")
    return rows


def retry_notification(db: Session, settings: Settings, notification: Notification) -> Notification:
    payload = load_payload(db)
    providers = [
        item for item in _providers(settings, payload, None) if item.channel == notification.channel
    ]
    if not providers:
        notification.status = "failed"
        notification.error_message = "Channel is not configured"
        db.commit()
        db.refresh(notification)
        return notification
    provider = providers[0]
    message = "HomeLab Monitor: Retry notification"
    report_retry = notification.recipient in REPORT_RECIPIENTS
    if report_retry:
        from homelab_monitor.telegram_reports import TelegramReportService

        message = TelegramReportService().build(db, notification.recipient)
    elif notification.alert_id:
        alert = db.get(Alert, notification.alert_id)
        if alert is not None:
            message = alert.message
    try:
        sender = _ReportDelivery(provider._notifier) if report_retry else provider
        error = _deliver(sender, message)
    finally:
        provider.close()
    notification.status = "sent" if not error else "failed"
    notification.error_message = error
    notification.sent_at = datetime.now(UTC) if not error else None
    if notification.recipient not in REPORT_RECIPIENTS:
        notification.recipient = provider.recipient
    db.commit()
    db.refresh(notification)
    hub.publish("overview_updated", reason="notification_updated")
    hub.publish("alert_updated", reason="notification_updated")
    return notification
