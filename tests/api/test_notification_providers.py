from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from homelab_monitor.alert_engine import AlertEvent
from homelab_monitor.database import get_engine
from homelab_monitor.models import Notification
from homelab_monitor.notifications.dispatcher import dispatch_alert_notifications
from homelab_monitor.notifications.email import EmailProvider
from homelab_monitor.notifications.provider import DeliveryError
from homelab_monitor.notifications.telegram import TelegramProvider
from homelab_monitor.notifications.webhooks import discord_provider, slack_provider
from homelab_monitor.settings import Settings
from homelab_monitor.telegram import TelegramNotifier


def test_discord_and_slack_reject_insecure_urls() -> None:
    with pytest.raises(ValueError, match="https://"):
        discord_provider("http://discord.example/api")
    with pytest.raises(ValueError, match="https://"):
        slack_provider("http://hooks.slack.com/test")


def test_discord_send_success_and_http_failure() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = request.content.decode()
        assert '"content"' in body
        if "fail" in body:
            return httpx.Response(500, json={"ok": False})
        return httpx.Response(204)

    client = httpx.Client(transport=httpx.MockTransport(handler), timeout=2)
    provider = discord_provider("https://discord.example/api", timeout=2)
    provider._client = client
    provider._owns_client = False
    provider.send("hello")
    with pytest.raises(DeliveryError, match="HTTP 500"):
        provider.send("fail")
    client.close()


def test_slack_timeout_becomes_delivery_error() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timed out")

    client = httpx.Client(transport=httpx.MockTransport(handler), timeout=0.01)
    provider = slack_provider("https://hooks.slack.com/test", timeout=0.01)
    provider._client = client
    provider._owns_client = False
    with pytest.raises(DeliveryError, match="timed out"):
        provider.send("hello")
    client.close()


def test_telegram_provider_success_and_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = request.content.decode()
        if "timeout" in body:
            raise httpx.TimeoutException("telegram timed out")
        return httpx.Response(200, json={"ok": True, "result": {}})

    http_client = httpx.Client(transport=httpx.MockTransport(handler), timeout=2)
    notifier = TelegramNotifier(
        api_base_url="https://telegram.example.test",
        bot_token="token",
        chat_id="-100",
        timeout=2,
        client=http_client,
    )
    provider = TelegramProvider(notifier, close_notifier=False)
    provider.send("ok")
    with pytest.raises(DeliveryError, match="timed out"):
        provider.send("timeout")
    http_client.close()


def test_telegram_provider_maps_failures_to_delivery_error() -> None:
    secret = "123456:AAHsecretTokenValue"

    def handler(request: httpx.Request) -> httpx.Response:
        text = request.content.decode()
        if "unauthorized" in text:
            return httpx.Response(401, json={"ok": False, "description": "Unauthorized"})
        if "bad-chat" in text:
            return httpx.Response(
                400,
                json={"ok": False, "description": "Bad Request: chat not found"},
            )
        if "boom" in text:
            raise httpx.ConnectError("connection refused")
        return httpx.Response(500, json={"ok": False, "description": f"fail {secret}"})

    http_client = httpx.Client(transport=httpx.MockTransport(handler), timeout=2)
    notifier = TelegramNotifier(
        api_base_url="https://telegram.example.test",
        bot_token=secret,
        chat_id="-100",
        timeout=2,
        client=http_client,
    )
    provider = TelegramProvider(notifier, close_notifier=False)
    with pytest.raises(DeliveryError, match="bot token"):
        provider.send("unauthorized")
    with pytest.raises(DeliveryError, match="chat ID"):
        provider.send("bad-chat")
    with pytest.raises(DeliveryError, match="network failure"):
        provider.send("boom")
    with pytest.raises(DeliveryError) as error:
        provider.send("http-fail")
    assert secret not in str(error.value)
    assert "HTTP 500" in str(error.value)
    http_client.close()


def test_email_validation_and_smtp_failure() -> None:
    with pytest.raises(ValueError, match="SMTP host"):
        EmailProvider(
            host="",
            port=587,
            username="",
            password="",
            from_address="",
            to_address="",
        )

    provider = EmailProvider(
        host="smtp.example.test",
        port=587,
        username="user",
        password="pass",
        from_address="alerts@example.test",
        to_address="ops@example.test",
    )
    smtp = MagicMock()
    smtp.__enter__.return_value = smtp
    with patch("homelab_monitor.notifications.email.smtplib.SMTP", return_value=smtp):
        provider.send("hello")
        smtp.starttls.assert_called_once()
        smtp.login.assert_called_once_with("user", "pass")
        smtp.send_message.assert_called_once()

    with (
        patch(
            "homelab_monitor.notifications.email.smtplib.SMTP",
            side_effect=TimeoutError("smtp timed out"),
        ),
        pytest.raises(DeliveryError, match="timed out"),
    ):
        provider.send("hello")


def test_alert_dispatch_records_history(monkeypatch) -> None:
    sent: list[str] = []

    class Stub:
        channel = "discord"
        recipient = "https://discord.example/api"

        def send(self, message: str) -> None:
            sent.append(message)

        def close(self) -> None:
            return None

    monkeypatch.setattr(
        "homelab_monitor.notifications.dispatcher._providers",
        lambda settings, payload, telegram_notifier: [Stub()],
    )
    settings = Settings(
        registration_key="test-registration-key-at-least-24-chars",
        jwt_secret="test-jwt-secret-key-at-least-32-chars",
    )
    dispatch_alert_notifications(
        settings,
        [
            AlertEvent(
                agent_id="agent-id",
                agent_name="monitor",
                kind="cpu_high",
                resource="system",
                value=95,
                threshold=90,
                message="CPU high",
                observed_at=datetime(2026, 9, 8, tzinfo=UTC),
            )
        ],
    )
    assert sent
    with Session(get_engine()) as db:
        row = db.scalar(
            select(Notification)
            .where(
                Notification.channel == "discord",
                Notification.recipient == "https://discord.example/api",
            )
            .order_by(Notification.created_at.desc())
        )
        assert row is not None
        assert row.channel == "discord"
        assert row.status == "sent"
        assert row.error_message == ""
        db.delete(row)
        db.commit()
