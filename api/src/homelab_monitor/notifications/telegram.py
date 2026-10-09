import httpx

from homelab_monitor.notifications.provider import DeliveryError
from homelab_monitor.telegram import TelegramNotificationError, TelegramNotifier


class TelegramProvider:
    channel = "telegram"

    def __init__(self, notifier: TelegramNotifier, *, close_notifier: bool = True) -> None:
        self._notifier = notifier
        self._close_notifier = close_notifier
        self.recipient = notifier.recipient

    def send(self, message: str) -> None:
        try:
            self._notifier.send_text(message)
        except (TelegramNotificationError, httpx.HTTPError) as error:
            raise DeliveryError(str(error)) from error

    def close(self) -> None:
        if self._close_notifier:
            self._notifier.close()
