from copy import deepcopy

from sqlalchemy import select
from sqlalchemy.orm import Session

from homelab_monitor.models import NotificationSettings
from homelab_monitor.notifications import SETTINGS_ROW_ID, channel_payload
from homelab_monitor.settings import Settings
from homelab_monitor.telegram import (
    DEFAULT_TELEGRAM_API_BASE_URL,
    TelegramNotifier,
    telegram_config_error,
)


def load_payload(db: Session) -> dict:
    row = db.get(NotificationSettings, SETTINGS_ROW_ID)
    if row is None:
        return {}
    return dict(row.payload or {})


def save_payload(db: Session, payload: dict) -> dict:
    row = db.get(NotificationSettings, SETTINGS_ROW_ID)
    if row is None:
        row = NotificationSettings(id=SETTINGS_ROW_ID, payload=payload)
        db.add(row)
    else:
        row.payload = payload
    db.commit()
    db.refresh(row)
    return dict(row.payload or {})


def merge_channel(existing: dict, updates: dict) -> dict:
    merged = deepcopy(existing)
    for key, value in updates.items():
        if value is None:
            continue
        merged[key] = value
    return merged


def telegram_credentials(settings: Settings, payload: dict) -> dict:
    stored = channel_payload(payload, "telegram")
    env_token = (
        settings.telegram_bot_token.get_secret_value() if settings.telegram_bot_token else ""
    )
    default_enabled = bool(env_token and settings.telegram_chat_id)
    enabled = bool(stored.get("enabled", default_enabled))
    if not settings.telegram_enabled:
        enabled = False
    return {
        "enabled": enabled,
        "api_base_url": stored.get("api_base_url")
        or settings.telegram_api_base_url
        or DEFAULT_TELEGRAM_API_BASE_URL,
        "bot_token": stored.get("bot_token") or env_token,
        "chat_id": stored.get("chat_id") or (settings.telegram_chat_id or ""),
        "timeout": settings.telegram_request_timeout,
    }


def public_settings(settings: Settings, payload: dict) -> dict:
    from homelab_monitor.telegram_reports import public_reports

    telegram = telegram_credentials(settings, payload)
    discord = channel_payload(payload, "discord")
    slack = channel_payload(payload, "slack")
    email = channel_payload(payload, "email")
    return {
        "telegram": {
            "enabled": bool(telegram["enabled"]),
            "configured": bool(telegram["bot_token"] and telegram["chat_id"]),
            "api_base_url": telegram["api_base_url"],
            "chat_id": telegram["chat_id"],
            "bot_token_set": bool(telegram["bot_token"]),
            "last_test": None,
        },
        "discord": {
            "enabled": bool(discord.get("enabled")),
            "configured": bool(discord.get("webhook_url")),
            "webhook_url_set": bool(discord.get("webhook_url")),
        },
        "slack": {
            "enabled": bool(slack.get("enabled")),
            "configured": bool(slack.get("webhook_url")),
            "webhook_url_set": bool(slack.get("webhook_url")),
        },
        "email": {
            "enabled": bool(email.get("enabled")),
            "configured": bool(
                email.get("host") and email.get("from_address") and email.get("to_address")
            ),
            "host": email.get("host") or "",
            "port": int(email.get("port") or 587),
            "username": email.get("username") or "",
            "from_address": email.get("from_address") or "",
            "to_address": email.get("to_address") or "",
            "use_tls": bool(email.get("use_tls", True)),
            "password_set": bool(email.get("password")),
        },
        "reports": public_reports(payload),
    }


def apply_updates(payload: dict, updates: dict) -> dict:
    next_payload = deepcopy(payload)
    for channel in ("telegram", "discord", "slack", "email"):
        if channel not in updates:
            continue
        next_payload[channel] = merge_channel(
            channel_payload(payload, channel),
            updates[channel],
        )
    if "reports" in updates and isinstance(updates["reports"], dict):
        from homelab_monitor.telegram_reports import reports_payload

        merged_reports = reports_payload(payload)
        for key, value in updates["reports"].items():
            if value is None or key == "last_sent":
                continue
            merged_reports[key] = value
        next_payload["reports"] = merged_reports
    return next_payload


def build_telegram_notifier(
    settings: Settings,
    payload: dict,
    injected: TelegramNotifier | None = None,
) -> TelegramNotifier | None:
    if injected is not None:
        return injected
    if not settings.telegram_enabled:
        return None
    creds = telegram_credentials(settings, payload)
    if not creds["enabled"]:
        return None
    if not creds["api_base_url"] or not creds["bot_token"] or not creds["chat_id"]:
        if not creds["bot_token"] and not creds["chat_id"]:
            return None
        raise ValueError(
            telegram_config_error(
                str(creds["api_base_url"] or ""),
                str(creds["bot_token"] or ""),
                str(creds["chat_id"] or ""),
            )
        )
    return TelegramNotifier(
        api_base_url=creds["api_base_url"],
        bot_token=creds["bot_token"],
        chat_id=creds["chat_id"],
        timeout=creds["timeout"],
    )


def load_settings_row(db: Session) -> NotificationSettings | None:
    return db.scalar(select(NotificationSettings).where(NotificationSettings.id == SETTINGS_ROW_ID))
