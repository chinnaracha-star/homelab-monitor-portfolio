import json
import logging
import re
import socket
import time
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import httpx

from homelab_monitor import __version__
from homelab_monitor.alert_engine import AlertEvent
from homelab_monitor.settings import Settings
from homelab_monitor.telegram_url_validator import build_public_inline_keyboard

logger = logging.getLogger("homelab_monitor.telegram")

ALERT_TITLES = {
    "agent_offline": "Agent Offline",
    "cpu_high": "CPU Usage High",
    "memory_high": "Memory Usage High",
    "disk_high": "Disk Usage High",
    "temperature_high": "Temperature High",
}

ALERT_RECOVERED_TITLES = {
    "agent_offline": "Agent Recovered",
    "cpu_high": "CPU Usage Recovered",
    "memory_high": "Memory Usage Recovered",
    "disk_high": "Disk Usage Recovered",
    "temperature_high": "Temperature Recovered",
}

PERCENT_KINDS = {"cpu_high", "memory_high", "disk_high"}

_TOKEN_PATTERN = re.compile(r"\d+:[A-Za-z0-9_-]+")
DEFAULT_TELEGRAM_API_BASE_URL = "https://api.telegram.org"
BANGKOK = timezone(timedelta(hours=7))
THAI_MONTHS = (
    "",
    "มกราคม",
    "กุมภาพันธ์",
    "มีนาคม",
    "เมษายน",
    "พฤษภาคม",
    "มิถุนายน",
    "กรกฎาคม",
    "สิงหาคม",
    "กันยายน",
    "ตุลาคม",
    "พฤศจิกายน",
    "ธันวาคม",
)


class TelegramNotificationError(Exception):
    """Telegram rejected a notification or could not be reached."""


class TelegramNotifier:
    def __init__(
        self,
        *,
        api_base_url: str,
        bot_token: str,
        chat_id: str,
        timeout: float,
        client: httpx.Client | None = None,
    ) -> None:
        missing = []
        if not api_base_url:
            missing.append("API base URL")
        if not bot_token:
            missing.append("bot token")
        if not chat_id:
            missing.append("chat ID")
        if missing:
            raise ValueError("Telegram " + ", ".join(missing) + " must be configured")
        self._api_base_url = api_base_url.rstrip("/")
        self._bot_token = bot_token
        self._chat_id = chat_id
        self._owns_client = client is None
        self._client = client or httpx.Client(timeout=timeout)
        self.last_http_status = 0

    @property
    def recipient(self) -> str:
        return self._chat_id

    def _method_url(self, method: str) -> str:
        return f"{self._api_base_url}/bot{self._bot_token}/{method}"

    @classmethod
    def from_settings(cls, settings: Settings) -> "TelegramNotifier | None":
        if not settings.telegram_enabled:
            return None
        token = (
            settings.telegram_bot_token.get_secret_value() if settings.telegram_bot_token else ""
        )
        chat_id = settings.telegram_chat_id or ""
        api_base_url = settings.telegram_api_base_url or DEFAULT_TELEGRAM_API_BASE_URL
        if not token and not chat_id:
            return None
        if not api_base_url or not token or not chat_id:
            raise ValueError(telegram_config_error(api_base_url, token, chat_id))
        return cls(
            api_base_url=api_base_url,
            bot_token=token,
            chat_id=chat_id,
            timeout=settings.telegram_request_timeout,
        )

    def verify_connection(self) -> dict:
        return self._request("GET", "getMe")

    def _request(
        self,
        method: str,
        api_method: str,
        json: dict | None = None,
        *,
        data: dict | None = None,
        files: dict | None = None,
    ) -> dict:
        kwargs: dict = {}
        if json is not None:
            kwargs["json"] = json
        if data is not None:
            kwargs["data"] = data
        if files is not None:
            kwargs["files"] = files
        response = self._send(method, api_method, kwargs)
        for _attempt in range(2):
            if response.status_code != 429:
                break
            time.sleep(_retry_after_seconds(response))
            response = self._send(method, api_method, kwargs)
        return _parse_telegram_response(response)

    def _send(self, method: str, api_method: str, kwargs: dict) -> httpx.Response:
        self.last_http_status = 0
        try:
            response = self._client.request(method, self._method_url(api_method), **kwargs)
        except httpx.TimeoutException as error:
            raise TelegramNotificationError("Telegram request timed out") from error
        except httpx.RequestError as error:
            raise TelegramNotificationError("Telegram network failure") from error
        self.last_http_status = response.status_code
        return response

    def send_text(self, text: str) -> dict:
        payload: dict = {"chat_id": self._chat_id, "text": text}
        markup = _safe_inline_keyboard()
        if markup is not None:
            payload["reply_markup"] = markup
        try:
            return self._request("POST", "sendMessage", json=payload)
        except TelegramNotificationError as error:
            if markup is not None and "wrong http url" in str(error).lower():
                logger.warning("Telegram keyboard disabled: reason=telegram_rejected_button_url")
                return self._request(
                    "POST",
                    "sendMessage",
                    json={"chat_id": self._chat_id, "text": text},
                )
            raise

    def send_photo(self, image_path: Path, *, caption: str) -> dict:
        if not image_path.is_file():
            raise TelegramNotificationError("photo file unavailable")
        size = image_path.stat().st_size
        if size <= 0 or size > 10 * 1024 * 1024:
            raise TelegramNotificationError("photo file too large")
        payload: dict = {"chat_id": self._chat_id, "caption": caption[:1024]}
        markup = _safe_inline_keyboard()
        if markup is not None:
            payload["reply_markup"] = json.dumps(markup)
        try:
            return self._send_photo_payload(image_path, payload)
        except TelegramNotificationError as error:
            if markup is not None and "wrong http url" in str(error).lower():
                logger.warning("Telegram keyboard disabled: reason=telegram_rejected_button_url")
                retry_payload: dict = {"chat_id": self._chat_id, "caption": caption[:1024]}
                return self._send_photo_payload(image_path, retry_payload)
            raise

    def _send_photo_payload(self, image_path: Path, payload: dict) -> dict:
        with image_path.open("rb") as handle:
            return self._request(
                "POST",
                "sendPhoto",
                data=payload,
                files={"photo": (image_path.name, handle, "application/octet-stream")},
            )

    def send_alert(self, event: AlertEvent) -> None:
        self.send_text(format_alert_message(event))

    def close(self) -> None:
        if self._owns_client:
            self._client.close()


def telegram_reply_markup(settings: Settings | None = None) -> dict | None:
    return build_public_inline_keyboard(settings)


def _safe_inline_keyboard(settings: Settings | None = None) -> dict | None:
    try:
        return build_public_inline_keyboard(settings)
    except Exception:
        logger.exception("Telegram keyboard disabled: reason=builder_error")
        return None


def telegram_config_error(api_base_url: str, bot_token: str, chat_id: str) -> str:
    missing: list[str] = []
    if not api_base_url:
        missing.append("API base URL")
    if not bot_token:
        missing.append("bot token")
    if not chat_id:
        missing.append("chat ID")
    if not missing:
        return "Telegram configuration is invalid"
    if len(missing) == 1:
        return f"Telegram {missing[0]} must be configured"
    if len(missing) == 2:
        return f"Telegram {missing[0]} and {missing[1]} must be configured"
    return "Telegram API base URL, bot token, and chat ID must be configured together"


def format_thai_datetime(value: datetime | None = None) -> str:
    stamp = value or datetime.now(UTC)
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=UTC)
    local = stamp.astimezone(BANGKOK)
    return f"{local.day} {THAI_MONTHS[local.month]} {local.year + 543} {local.strftime('%H:%M')} น."


def format_telegram_test_message(
    *,
    server: str | None = None,
    version: str | None = None,
    observed_at: datetime | None = None,
) -> str:
    return "\n".join(
        (
            "🚀 Homelab Monitor Test",
            f"Time: {format_thai_datetime(observed_at)}",
            f"Server: {server or socket.gethostname()}",
            f"Version: {version or __version__}",
            "Status: ok",
        )
    )


def format_bangkok_clock(value: datetime | None) -> str:
    if value is None:
        return "—"
    stamp = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    return stamp.astimezone(BANGKOK).strftime("%H:%M")


def format_duration_short(seconds: int | None) -> str:
    if seconds is None:
        return "—"
    if seconds < 60:
        return "1 sec" if seconds == 1 else f"{seconds} sec"
    minutes = seconds // 60
    if minutes < 60:
        return "1 min" if minutes == 1 else f"{minutes} min"
    hours = minutes // 60
    return "1 hour" if hours == 1 else f"{hours} hours"


def format_duration_long(seconds: int | None) -> str:
    if seconds is None:
        return "—"
    if seconds < 60:
        return "1 second" if seconds == 1 else f"{seconds} seconds"
    minutes = seconds // 60
    if minutes < 60:
        return "1 minute" if minutes == 1 else f"{minutes} minutes"
    hours = minutes // 60
    return "1 hour" if hours == 1 else f"{hours} hours"


def format_metric_value(kind: str, value: float | None) -> str:
    if value is None:
        return "—"
    if kind in PERCENT_KINDS:
        return f"{int(value)}%" if float(value).is_integer() else f"{value}%"
    if kind == "temperature_high":
        return f"{int(value)}°C" if float(value).is_integer() else f"{value}°C"
    return str(int(value) if float(value).is_integer() else value)


def format_alert_message(event: AlertEvent) -> str:
    if event.kind == "qnap_disk_temperature_high" and event.message:
        return event.message
    recovered = event.transition == "recovered"
    if recovered:
        title = ALERT_RECOVERED_TITLES.get(event.kind, "Alert Recovered")
        return "\n".join(
            (
                f"🟢 {title}",
                "",
                "Recovered after",
                "",
                format_duration_long(event.duration_seconds),
                "",
                "Current:",
                format_metric_value(event.kind, event.value),
            )
        )
    title = ALERT_TITLES.get(event.kind, "HomeLab Warning")
    started = event.started_at or event.observed_at
    return "\n".join(
        (
            f"🔴 {title}",
            "",
            "Current:",
            format_metric_value(event.kind, event.value),
            "",
            "Threshold:",
            format_metric_value(event.kind, event.threshold),
            "",
            "Started:",
            format_bangkok_clock(started),
            "",
            "Duration:",
            format_duration_short(event.duration_seconds),
        )
    )


def dispatch_alert_events(
    settings: Settings,
    events: list[AlertEvent],
    notifier: TelegramNotifier | None = None,
) -> None:
    from homelab_monitor.notifications.dispatcher import dispatch_alert_notifications

    dispatch_alert_notifications(settings, events, telegram_notifier=notifier)


def _parse_telegram_response(response: httpx.Response) -> dict:
    try:
        body = response.json()
    except ValueError:
        body = {}
    description = redact_telegram_secrets(str(body.get("description") or ""))
    error_code = body.get("error_code")
    lowered = description.lower()
    if response.status_code in {401, 403} or error_code in {401, 403} or "unauthorized" in lowered:
        raise TelegramNotificationError("Telegram rejected the bot token")
    if "chat not found" in lowered or "chat_id is empty" in lowered:
        raise TelegramNotificationError("Telegram rejected the chat ID")
    if response.status_code >= 400:
        detail = f": {description}" if description else ""
        raise TelegramNotificationError(
            f"Telegram Bot API returned HTTP {response.status_code}{detail}"
        )
    if body.get("ok") is not True:
        raise TelegramNotificationError(description or "Telegram Bot API rejected the message")
    return body if isinstance(body, dict) else {}


def redact_telegram_secrets(text: str) -> str:
    return _TOKEN_PATTERN.sub("[redacted]", text)


def _retry_after_seconds(response: httpx.Response) -> float:
    header = response.headers.get("Retry-After")
    if header:
        try:
            return min(max(float(header), 1), 30)
        except ValueError:
            pass
    try:
        body = response.json()
    except ValueError:
        body = {}
    wait = None
    if isinstance(body, dict):
        parameters = body.get("parameters")
        if isinstance(parameters, dict):
            wait = parameters.get("retry_after")
    try:
        return min(max(float(wait or 2), 1), 30)
    except (TypeError, ValueError):
        return 2.0
