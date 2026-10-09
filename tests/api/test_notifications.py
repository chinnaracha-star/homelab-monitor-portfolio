from collections.abc import Callable

from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy.orm import Session

from homelab_monitor.database import get_engine
from homelab_monitor.models import Notification
from homelab_monitor.notifications.telegram import TelegramProvider
from homelab_monitor.notifications.webhooks import WebhookProvider

REGISTRATION_KEY = "test-registration-key-at-least-24-chars"


def test_notification_settings_and_test_dispatch(
    client: TestClient,
    auth_header: Callable[..., dict[str, str]],
    monkeypatch,
) -> None:
    sent: list[tuple[str, str]] = []

    def fake_send(self: WebhookProvider, message: str) -> None:
        sent.append((self.channel, message))

    monkeypatch.setattr(WebhookProvider, "send", fake_send)

    with Session(get_engine()) as db:
        db.execute(delete(Notification))
        db.commit()

    listed = client.get("/api/v1/notifications", headers=auth_header("viewer", "viewer123"))
    assert listed.status_code == 200
    assert listed.json()["notifications"] == []

    settings = client.get("/api/v1/settings/notifications", headers=auth_header())
    assert settings.status_code == 200
    assert settings.json()["discord"]["configured"] is False

    denied = client.put(
        "/api/v1/settings/notifications",
        headers=auth_header("operator", "operator123"),
        json={"discord": {"enabled": True, "webhook_url": "https://discord.example/api"}},
    )
    assert denied.status_code == 403

    updated = client.put(
        "/api/v1/settings/notifications",
        headers=auth_header(),
        json={"discord": {"enabled": True, "webhook_url": "https://discord.example/api"}},
    )
    assert updated.status_code == 200
    assert updated.json()["discord"]["enabled"] is True
    assert updated.json()["discord"]["webhook_url_set"] is True
    assert "webhook_url" not in updated.json()["discord"]

    viewer_test = client.post(
        "/api/v1/notifications/test",
        headers=auth_header("viewer", "viewer123"),
        json={"channel": "discord"},
    )
    assert viewer_test.status_code == 403

    tested = client.post(
        "/api/v1/notifications/test",
        headers=auth_header("operator", "operator123"),
        json={"channel": "discord"},
    )
    assert tested.status_code == 200
    body = tested.json()
    assert body["total"] == 1
    assert body["notifications"][0]["channel"] == "discord"
    assert body["notifications"][0]["status"] == "sent"
    assert body["notifications"][0]["recipient"] == "configured webhook"
    assert sent == [("discord", "HomeLab Monitor: Test notification")]

    notification_id = body["notifications"][0]["id"]
    detail = client.get(
        f"/api/v1/notifications/{notification_id}",
        headers=auth_header("viewer", "viewer123"),
    )
    assert detail.status_code == 200
    assert detail.json()["id"] == notification_id

    missing = client.get("/api/v1/notifications/missing", headers=auth_header())
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "notification_not_found"


def test_retry_failed_notification(
    client: TestClient,
    auth_header: Callable[..., dict[str, str]],
    monkeypatch,
) -> None:
    attempts = {"count": 0}

    def flaky_send(self: WebhookProvider, message: str) -> None:
        attempts["count"] += 1
        if attempts["count"] < 4:
            raise RuntimeError("temporary")

    monkeypatch.setattr(WebhookProvider, "send", flaky_send)

    client.put(
        "/api/v1/settings/notifications",
        headers=auth_header(),
        json={"slack": {"enabled": True, "webhook_url": "https://hooks.slack.com/test"}},
    )
    created = client.post(
        "/api/v1/notifications/test",
        headers=auth_header(),
        json={"channel": "slack"},
    )
    assert created.status_code == 200
    row = created.json()["notifications"][0]
    assert row["status"] == "failed"

    def ok_send(self: WebhookProvider, message: str) -> None:
        return None

    monkeypatch.setattr(WebhookProvider, "send", ok_send)
    retried = client.post(
        f"/api/v1/notifications/{row['id']}/retry",
        headers=auth_header("operator", "operator123"),
    )
    assert retried.status_code == 200
    assert retried.json()["status"] == "sent"


def test_notifications_require_jwt(client: TestClient) -> None:
    assert client.get("/api/v1/notifications").status_code == 401
    assert client.get("/api/v1/notifications/any").status_code == 401
    assert client.get("/api/v1/settings/notifications").status_code == 401
    created = client.post("/api/v1/notifications/test", json={})
    assert created.status_code == 401
    assert client.post("/api/v1/notifications/any/retry").status_code == 401
    assert client.put("/api/v1/settings/notifications", json={}).status_code == 401


def test_telegram_test_message_and_last_test(
    client: TestClient,
    auth_header: Callable[..., dict[str, str]],
    monkeypatch,
) -> None:
    sent: list[str] = []

    def fake_send(self: TelegramProvider, message: str) -> None:
        sent.append(message)

    monkeypatch.setattr(TelegramProvider, "send", fake_send)

    settings = client.get("/api/v1/settings/notifications", headers=auth_header())
    assert settings.status_code == 200
    telegram = settings.json()["telegram"]
    assert "bot_token" not in telegram
    assert telegram["last_test"] is None

    updated = client.put(
        "/api/v1/settings/notifications",
        headers=auth_header(),
        json={
            "telegram": {
                "enabled": True,
                "api_base_url": "https://telegram.example.test",
                "chat_id": "-100123",
                "bot_token": "123456:AAHsecretTokenValue",
            }
        },
    )
    assert updated.status_code == 200
    assert updated.json()["telegram"]["configured"] is True
    assert updated.json()["telegram"]["bot_token_set"] is True
    assert "bot_token" not in updated.json()["telegram"]
    assert "AAHsecretTokenValue" not in str(updated.json())

    tested = client.post(
        "/api/v1/notifications/test",
        headers=auth_header(),
        json={"channel": "telegram"},
    )
    assert tested.status_code == 200
    row = tested.json()["notifications"][0]
    assert row["channel"] == "telegram"
    assert row["status"] == "sent"
    assert row["recipient"] == "-100123"
    assert sent
    message = sent[0]
    assert message.startswith("🚀 Homelab Monitor Test")
    assert "Time:" in message
    assert "Server:" in message
    assert "Version:" in message
    assert "Status: ok" in message

    refreshed = client.get("/api/v1/settings/notifications", headers=auth_header())
    assert refreshed.json()["telegram"]["last_test"] is not None
    assert "bot_token" not in refreshed.json()["telegram"]

    client.put(
        "/api/v1/settings/notifications",
        headers=auth_header(),
        json={"telegram": {"enabled": False}},
    )
    with Session(get_engine()) as db:
        row_id = row["id"]
        stored = db.get(Notification, row_id)
        if stored is not None:
            db.delete(stored)
            db.commit()


def test_invalid_notification_payloads_return_422(
    client: TestClient,
    auth_header: Callable[..., dict[str, str]],
) -> None:
    invalid_channel = client.post(
        "/api/v1/notifications/test",
        headers=auth_header(),
        json={"channel": "sms"},
    )
    assert invalid_channel.status_code == 422

    invalid_port = client.put(
        "/api/v1/settings/notifications",
        headers=auth_header(),
        json={"email": {"port": 0}},
    )
    assert invalid_port.status_code == 422


def test_viewer_cannot_retry_notifications(
    client: TestClient,
    auth_header: Callable[..., dict[str, str]],
    monkeypatch,
) -> None:
    monkeypatch.setattr(WebhookProvider, "send", lambda self, message: None)
    client.put(
        "/api/v1/settings/notifications",
        headers=auth_header(),
        json={"discord": {"enabled": True, "webhook_url": "https://discord.example/api"}},
    )
    created = client.post(
        "/api/v1/notifications/test",
        headers=auth_header(),
        json={"channel": "discord"},
    )
    notification_id = created.json()["notifications"][0]["id"]
    denied = client.post(
        f"/api/v1/notifications/{notification_id}/retry",
        headers=auth_header("viewer", "viewer123"),
    )
    assert denied.status_code == 403
