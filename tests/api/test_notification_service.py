from pathlib import Path
from unittest.mock import MagicMock

from homelab_monitor.notifications.service import NotificationService
from homelab_monitor.settings import get_settings
from homelab_monitor.telegram import TelegramNotifier


def test_notification_service_delegates_text_and_close() -> None:
    notifier = MagicMock(spec=TelegramNotifier)
    notifier.send_text.return_value = {"ok": True}
    service = NotificationService(notifier)
    assert service.send_text("hello") == {"ok": True}
    notifier.send_text.assert_called_once_with("hello")
    service.close()
    notifier.close.assert_called_once_with()


def test_notification_service_forwards_photo_without_text() -> None:
    notifier = MagicMock(spec=TelegramNotifier)
    notifier.send_photo.return_value = {"ok": True}
    service = NotificationService(notifier)
    image = Path("IMG_1234.jpg")
    assert service.send_photo(image, caption="📷 New Photo Detected") == {"ok": True}
    notifier.send_photo.assert_called_once_with(image, caption="📷 New Photo Detected")
    notifier.send_text.assert_not_called()
    service.close()
    notifier.close.assert_called_once_with()


def test_notification_service_from_settings_is_absent_when_telegram_disabled() -> None:
    settings = get_settings().model_copy(update={"telegram_enabled": False})
    assert NotificationService.from_settings(settings) is None
