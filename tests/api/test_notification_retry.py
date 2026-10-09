from homelab_monitor.notifications.retry import is_transient_delivery_error, retry_transient
from homelab_monitor.telegram import TelegramNotificationError


def test_retry_transient_succeeds_after_timeouts() -> None:
    attempts = {"count": 0}

    def flaky() -> str:
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise TelegramNotificationError("Telegram request timed out")
        return "ok"

    assert retry_transient(flaky, base_delay=0) == "ok"
    assert attempts["count"] == 3


def test_retry_transient_does_not_retry_permanent_errors() -> None:
    attempts = {"count": 0}

    def boom() -> None:
        attempts["count"] += 1
        raise RuntimeError("permanent")

    try:
        retry_transient(boom, base_delay=0)
    except RuntimeError:
        pass
    else:
        raise AssertionError("expected RuntimeError")
    assert attempts["count"] == 1
    assert is_transient_delivery_error(TelegramNotificationError("HTTP 429"))
    assert is_transient_delivery_error(TelegramNotificationError("HTTP 500"))
    assert not is_transient_delivery_error(
        TelegramNotificationError("Telegram rejected the bot token")
    )
