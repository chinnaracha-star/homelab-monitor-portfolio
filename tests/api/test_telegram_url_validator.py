from datetime import UTC, datetime, timedelta, timezone
from unittest.mock import MagicMock

import httpx

from homelab_monitor.alert_engine import AlertEvent
from homelab_monitor.notifications.telegram import TelegramProvider
from homelab_monitor.photo_telegram import format_new_photo_message, format_new_photos_batch_message
from homelab_monitor.schemas import RemoteAccessResponse
from homelab_monitor.settings import get_settings
from homelab_monitor.telegram import TelegramNotifier, format_alert_message, telegram_reply_markup
from homelab_monitor.telegram_reports import (
    format_daily_report,
    format_hourly_report,
    format_weekly_report,
)
from homelab_monitor.telegram_url_validator import (
    build_public_inline_keyboard,
    public_url_rejection_reason,
    validate_public_url,
)


def test_validate_public_url_accepts_https_hosts() -> None:
    assert validate_public_url("https://example.com") == "https://example.com"
    assert validate_public_url("https://monitor.example.com") == "https://monitor.example.com"


def test_validate_public_url_rejects_internal_and_non_http() -> None:
    cases = {
        "http://dashboard:8080": "internal_docker_host",
        "http://localhost": "loopback",
        "http://127.0.0.1": "loopback",
        "http://api:8000": "internal_docker_host",
        "http://nginx": "internal_docker_host",
        "http://postgres": "internal_docker_host",
        "http://redis": "internal_docker_host",
        "http://immich": "internal_docker_host",
        "http://homelab.local": "private_only_tld",
        "ftp://example.com/file": "missing_http_scheme",
        "http://0.0.0.0": "loopback",
        "": "empty",
    }
    for url, reason in cases.items():
        assert public_url_rejection_reason(url) == reason
        assert validate_public_url(url or None) is None


def test_validate_public_url_never_throws() -> None:
    assert validate_public_url(None) is None
    assert validate_public_url("://") is None


def test_health_url_never_becomes_keyboard_button(monkeypatch) -> None:
    monkeypatch.setattr(
        "homelab_monitor.telegram_links.RemoteAccessService.snapshot",
        lambda self: RemoteAccessResponse(),
    )
    settings = get_settings().model_copy(
        update={
            "dashboard_health_url": "http://dashboard:8080/",
            "api_health_url": "http://api:8000/health",
            "dashboard_public_url": "",
            "immich_url": "http://immich:2283",
            "qnap_url": "http://qnap:8080",
        }
    )
    assert telegram_reply_markup(settings) is None
    assert build_public_inline_keyboard(settings) is None


def test_public_url_and_tailnet_fallback(monkeypatch) -> None:
    monkeypatch.setattr(
        "homelab_monitor.telegram_links.RemoteAccessService.snapshot",
        lambda self: RemoteAccessResponse(hostname="monitor.example.com", https=True),
    )
    settings = get_settings().model_copy(
        update={
            "dashboard_health_url": "http://dashboard:8080/",
            "dashboard_public_url": "",
        }
    )
    markup = build_public_inline_keyboard(settings)
    assert markup is not None
    assert markup["inline_keyboard"][0][0]["url"] == "https://monitor.example.com"

    settings = settings.model_copy(update={"dashboard_public_url": "https://dash.example/"})
    markup = build_public_inline_keyboard(settings)
    assert markup["inline_keyboard"][0][0]["url"] == "https://dash.example"


def test_telegram_provider_sends_text_when_all_urls_invalid(monkeypatch) -> None:
    monkeypatch.setattr(
        "homelab_monitor.telegram_links.RemoteAccessService.snapshot",
        lambda self: RemoteAccessResponse(),
    )
    captured: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request.content.decode())
        return httpx.Response(200, json={"ok": True, "result": {}})

    http_client = httpx.Client(transport=httpx.MockTransport(handler), timeout=2)
    notifier = TelegramNotifier(
        api_base_url="https://telegram.example.test",
        bot_token="token",
        chat_id="-100",
        timeout=2,
        client=http_client,
    )
    settings = get_settings().model_copy(
        update={
            "dashboard_health_url": "http://dashboard:8080/",
            "dashboard_public_url": "http://localhost",
            "immich_public_url": "http://127.0.0.1",
            "qnap_public_url": "ftp://nas.example",
        }
    )
    monkeypatch.setattr("homelab_monitor.telegram_url_validator.get_settings", lambda: settings)
    monkeypatch.setattr("homelab_monitor.telegram_links.get_settings", lambda: settings)
    provider = TelegramProvider(notifier, close_notifier=False)
    provider.send("Hourly Executive Report")
    http_client.close()
    assert captured
    assert "Hourly Executive Report" in captured[0]
    assert "reply_markup" not in captured[0]


def test_wrong_http_url_retries_without_keyboard(monkeypatch) -> None:
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        body = request.content.decode()
        if "reply_markup" in body:
            return httpx.Response(
                400,
                json={
                    "ok": False,
                    "description": "Bad Request: Wrong HTTP URL",
                },
            )
        return httpx.Response(200, json={"ok": True, "result": {}})

    monkeypatch.setattr(
        "homelab_monitor.telegram.build_public_inline_keyboard",
        lambda settings=None: {
            "inline_keyboard": [[{"text": "🏠 Dashboard", "url": "http://dashboard:8080"}]]
        },
    )
    http_client = httpx.Client(transport=httpx.MockTransport(handler), timeout=2)
    notifier = TelegramNotifier(
        api_base_url="https://telegram.example.test",
        bot_token="token",
        chat_id="-100",
        timeout=2,
        client=http_client,
    )
    assert TelegramProvider(notifier, close_notifier=False).send("ok") is None
    http_client.close()
    assert attempts["count"] == 2


def test_photo_alert_and_report_bodies_omit_invalid_public_urls(monkeypatch) -> None:
    monkeypatch.setattr(
        "homelab_monitor.telegram_links.RemoteAccessService.snapshot",
        lambda self: RemoteAccessResponse(),
    )
    settings = get_settings().model_copy(
        update={
            "dashboard_health_url": "http://dashboard:8080/",
            "dashboard_public_url": "",
            "immich_url": "http://immich",
            "qnap_url": "http://qnap",
        }
    )
    monkeypatch.setattr("homelab_monitor.telegram_links.get_settings", lambda: settings)
    monkeypatch.setattr("homelab_monitor.photo_telegram.resolve_dashboard_url", lambda: None)
    monkeypatch.setattr(
        "homelab_monitor.photo_telegram.resolve_immich_url", lambda: "http://immich"
    )
    monkeypatch.setattr("homelab_monitor.photo_telegram.resolve_qnap_url", lambda: None)

    photo = format_new_photo_message(
        filename="a.jpg",
        folder="/data/photos/library-b",
        size_bytes=10,
        created_at=datetime(2026, 9, 22, 8, 0, tzinfo=UTC),
    )
    batch = format_new_photos_batch_message(
        folder="/data/photos/library-b",
        filenames=["a.jpg", "b.jpg"],
    )
    assert "a.jpg" in batch
    assert "b.jpg" in batch
    assert "+1 more" not in batch
    assert "http://dashboard:8080" not in photo
    assert "http://immich" not in photo
    assert "http://dashboard:8080" not in batch

    event = AlertEvent(
        agent_id="a",
        agent_name="n",
        kind="cpu_high",
        resource="system",
        value=95,
        threshold=90,
        message="high",
        observed_at=datetime(2026, 9, 22, 8, 0, tzinfo=UTC),
    )
    assert "http://dashboard:8080" not in format_alert_message(event)

    local = datetime(2026, 9, 10, 14, 0, tzinfo=timezone(timedelta(hours=7)))
    hourly = format_hourly_report(
        local=local,
        cpu=1,
        memory=1,
        temperature=1,
        storage_percent=1,
        photos_new_today="0",
        immich_indexed="0",
        backup_status="Success",
        last_backup="",
        active_alerts=0,
        recovered_today=0,
        health_score=1,
        recommendation="ok",
        dashboard_url="—",
    )
    daily = format_daily_report(
        local=local,
        cpu_average=1,
        memory_average=1,
        temperature_average=1,
        storage_growth="0%",
        photo_growth="0",
        backup_success="Success",
        alerts_yesterday=0,
        health_score=1,
        recommendation="ok",
        dashboard_url="—",
    )
    weekly = format_weekly_report(
        local=local,
        cpu_average=1,
        memory_average=1,
        storage_growth="0%",
        photo_growth="0",
        backup_success="Success",
        forecast="ok",
        recommendation="ok",
        dashboard_url="—",
    )
    for body in (hourly, daily, weekly):
        assert "http://dashboard:8080" not in body


def test_retry_rebuilds_keyboard_from_latest_settings(monkeypatch) -> None:
    snapshot = MagicMock(return_value=RemoteAccessResponse())
    monkeypatch.setattr(
        "homelab_monitor.telegram_links.RemoteAccessService.snapshot",
        lambda self: snapshot(),
    )
    first = get_settings().model_copy(update={"dashboard_public_url": ""})
    second = get_settings().model_copy(update={"dashboard_public_url": "https://fixed.example"})
    assert build_public_inline_keyboard(first) is None
    markup = build_public_inline_keyboard(second)
    assert markup["inline_keyboard"][0][0]["url"] == "https://fixed.example"
