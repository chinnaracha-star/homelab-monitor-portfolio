"""Facade over the existing Telegram notifier.

SQLite backup, scheduled reports, the notification worker, and Photo Monitor
use this facade for delivery. Retry, history, and photo fallback stay with
their current owners.
"""

from pathlib import Path

from homelab_monitor.settings import Settings
from homelab_monitor.telegram import TelegramNotifier


class NotificationService:
    """Delegates text delivery to the current Telegram implementation."""

    def __init__(self, notifier: TelegramNotifier) -> None:
        self._notifier = notifier

    @classmethod
    def from_settings(cls, settings: Settings) -> "NotificationService | None":
        notifier = TelegramNotifier.from_settings(settings)
        if notifier is None:
            return None
        return cls(notifier)

    @property
    def recipient(self) -> str:
        return self._notifier.recipient

    def send_text(self, text: str) -> dict:
        return self._notifier.send_text(text)

    def send_photo(self, image_path: Path, *, caption: str) -> dict:
        return self._notifier.send_photo(image_path, caption=caption)

    def close(self) -> None:
        self._notifier.close()
