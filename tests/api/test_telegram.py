from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from homelab_monitor.alert_engine import AlertEvent
from homelab_monitor.notification_queue import get_notification_queue
from homelab_monitor.settings import Settings
from homelab_monitor.telegram import (
    TelegramNotificationError,
    TelegramNotifier,
    dispatch_alert_events,
    format_alert_message,
    format_telegram_test_message,
    format_thai_datetime,
    telegram_config_error,
)

REGISTRATION_KEY = "test-registration-key-at-least-24-chars"


def make_event(kind: str) -> AlertEvent:
    return AlertEvent(
        agent_id="agent-id",
        agent_name="monitor",
        kind=kind,
        resource="system",
        value=95,
        threshold=90,
        message="Metric 95 exceeded threshold 90",
        observed_at=datetime(2026, 9, 7, 9, 0, tzinfo=UTC),
    )


def test_notifier_uses_configured_url_and_telegram_payload() -> None:
    captured: httpx.Request | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured
        captured = request
        return httpx.Response(200, json={"ok": True, "result": {}})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    notifier = TelegramNotifier(
        api_base_url="https://telegram.example.test",
        bot_token="test-bot-token",
        chat_id="-100123",
        timeout=5,
        client=client,
    )

    notifier.send_alert(make_event("cpu_high"))

    assert captured is not None
    assert str(captured.url) == ("https://telegram.example.test/bottest-bot-token/sendMessage")
    body = captured.read().decode()
    assert '"chat_id":"-100123"' in body
    assert "CPU Usage High" in body
    assert "95%" in body


@pytest.mark.parametrize(
    ("kind", "title"),
    [
        ("agent_offline", "Agent Offline"),
        ("cpu_high", "CPU Usage High"),
        ("memory_high", "Memory Usage High"),
        ("disk_high", "Disk Usage High"),
        ("temperature_high", "Temperature High"),
    ],
)
def test_supported_alert_messages(kind: str, title: str) -> None:
    message = format_alert_message(make_event(kind))

    assert f"🔴 {title}" in message
    assert "Current:" in message
    assert "Threshold:" in message
    assert "Started:" in message
    assert "16:00" in message


def test_recovery_alert_message() -> None:
    event = AlertEvent(
        agent_id="agent-id",
        agent_name="monitor",
        kind="cpu_high",
        resource="system",
        value=41,
        threshold=90,
        message="recovered",
        observed_at=datetime(2026, 9, 7, 9, 17, tzinfo=UTC),
        transition="recovered",
        started_at=datetime(2026, 9, 7, 9, 0, tzinfo=UTC),
        recovered_at=datetime(2026, 9, 7, 9, 17, tzinfo=UTC),
        duration_seconds=17 * 60,
    )
    message = format_alert_message(event)
    assert "🟢 CPU Usage Recovered" in message
    assert "Recovered after" in message
    assert "17 minutes" in message
    assert "41%" in message


def test_dispatch_is_disabled_without_credentials() -> None:
    settings = Settings(
        registration_key=REGISTRATION_KEY,
        telegram_api_base_url="https://telegram.example.test",
        telegram_bot_token=None,
        telegram_chat_id=None,
    )

    dispatch_alert_events(settings, [make_event("cpu_high")])


def test_telegram_kill_switch_skips_delivery() -> None:
    from homelab_monitor.notifications.config import build_telegram_notifier

    settings = Settings(
        registration_key=REGISTRATION_KEY,
        jwt_secret="test-jwt-secret-key-at-least-32-chars",
        telegram_enabled=False,
        telegram_bot_token="test-bot-token",
        telegram_chat_id="-100123",
        telegram_api_base_url="https://telegram.example.test",
    )
    notifier = build_telegram_notifier(
        settings, {"telegram": {"enabled": True, "bot_token": "x", "chat_id": "1"}}
    )
    assert notifier is None
    assert TelegramNotifier.from_settings(settings) is None


def test_report_upload_enqueues_only_on_alert_transition(client: TestClient) -> None:
    registration = client.post(
        "/api/v1/agents/register",
        headers={"X-Registration-Key": REGISTRATION_KEY},
        json={
            "name": "telegram-agent",
            "hostname": "telegram-agent.local",
            "version": "0.1.0",
            "capabilities": ["ubuntu"],
        },
    ).json()

    def upload(report_id: str, observed_at: datetime) -> None:
        response = client.post(
            "/api/v1/agent/reports",
            headers={"Authorization": f"Bearer {registration['agent_token']}"},
            json={
                "report_id": report_id,
                "schema_version": "1.0",
                "observed_at": observed_at.isoformat(),
                "config_revision": 1,
                "modules": [
                    {
                        "module": "system",
                        "status": "warning",
                        "summary": "CPU threshold exceeded",
                        "metrics": {"cpu": {"usage_percent": 95}},
                        "diagnostics": {},
                    }
                ],
            },
        )
        assert response.status_code == 200

    start = datetime(2026, 9, 10, 8, 0, tzinfo=UTC)
    upload("telegram-alert-001", start)
    upload("telegram-alert-002", start + timedelta(minutes=2))
    upload("telegram-alert-003", start + timedelta(minutes=3))

    jobs = get_notification_queue().snapshot()
    assert len(jobs) == 1
    assert jobs[0].channel == "telegram"
    assert jobs[0].event == "activated"
    assert "CPU Usage High" in jobs[0].message


def test_format_thai_datetime_uses_buddhist_era_and_bangkok_time() -> None:
    assert format_thai_datetime(datetime(2026, 9, 8, 7, 25, tzinfo=UTC)) == (
        "8 กันยายน 2569 14:25 น."
    )


def test_telegram_test_message_includes_required_fields() -> None:
    message = format_telegram_test_message(
        server="production",
        version="8.3.5",
        observed_at=datetime(2026, 9, 8, 2, 0, tzinfo=UTC),
    )
    assert message.startswith("🚀 Homelab Monitor Test")
    assert "Time: 8 กันยายน 2569 09:00 น." in message
    assert "Server: production" in message
    assert "Version: 8.3.5" in message
    assert "Status: ok" in message


def test_telegram_config_error_names_missing_fields() -> None:
    assert "bot token" in telegram_config_error("https://api.telegram.org", "", "-100")
    assert "chat ID" in telegram_config_error("https://api.telegram.org", "token", "")


def _notifier(handler) -> TelegramNotifier:
    return TelegramNotifier(
        api_base_url="https://telegram.example.test",
        bot_token="123456:AAHsecretTokenValue",
        chat_id="-100123",
        timeout=2,
        client=httpx.Client(transport=httpx.MockTransport(handler), timeout=2),
    )


def test_verify_connection_calls_get_me() -> None:
    captured: httpx.Request | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured
        captured = request
        return httpx.Response(200, json={"ok": True, "result": {"id": 1}})

    notifier = _notifier(handler)
    me = notifier.verify_connection()
    assert captured is not None
    assert captured.method == "GET"
    assert str(captured.url).endswith("/bot123456:AAHsecretTokenValue/getMe")
    assert notifier.last_http_status == 200
    assert me["result"]["id"] == 1
    notifier.close()


def test_invalid_token_and_chat_id_errors() -> None:
    def unauthorized(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            401,
            json={"ok": False, "error_code": 401, "description": "Unauthorized"},
        )

    notifier = _notifier(unauthorized)
    with pytest.raises(TelegramNotificationError, match="bot token"):
        notifier.send_text("hello")
    notifier.close()

    def missing_chat(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={"ok": False, "error_code": 400, "description": "Bad Request: chat not found"},
        )

    notifier = _notifier(missing_chat)
    with pytest.raises(TelegramNotificationError, match="chat ID"):
        notifier.send_text("hello")
    notifier.close()


def test_http_error_redacts_bot_token() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={
                "ok": False,
                "description": "failed for 123456:AAHsecretTokenValue",
            },
        )

    notifier = _notifier(handler)
    with pytest.raises(TelegramNotificationError) as error:
        notifier.send_text("hello")
    assert "AAHsecretTokenValue" not in str(error.value)
    notifier.close()


def test_http_429_retries_after_retry_after() -> None:
    attempts = {"count": 0}

    def handler(_request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        if attempts["count"] == 1:
            return httpx.Response(
                429,
                json={
                    "ok": False,
                    "error_code": 429,
                    "description": "Too Many Requests: retry after 1",
                    "parameters": {"retry_after": 0},
                },
            )
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 9}})

    notifier = _notifier(handler)
    body = notifier.send_text("hello")
    assert attempts["count"] == 2
    assert notifier.last_http_status == 200
    assert body["result"]["message_id"] == 9
    notifier.close()


def test_network_failure_is_telegram_error() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    notifier = _notifier(handler)
    with pytest.raises(TelegramNotificationError, match="network failure"):
        notifier.send_text("hello")
    notifier.close()
    notifier.close()


def test_send_photo_uses_multipart_payload(tmp_path: Path) -> None:
    image = tmp_path / "shot.jpg"
    image.write_bytes(b"jpeg-bytes")
    captured: httpx.Request | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured
        captured = request
        return httpx.Response(200, json={"ok": True, "result": {}})

    notifier = _notifier(handler)
    notifier.send_photo(image, caption="📷 New Photo Detected")
    assert captured is not None
    assert str(captured.url).endswith("/sendPhoto")
    assert b"jpeg-bytes" in captured.read()
    notifier.close()


def test_send_photo_missing_file_raises(tmp_path: Path) -> None:
    notifier = _notifier(lambda _request: httpx.Response(200, json={"ok": True, "result": {}}))
    with pytest.raises(TelegramNotificationError, match="unavailable"):
        notifier.send_photo(tmp_path / "missing.jpg", caption="caption")
    notifier.close()
