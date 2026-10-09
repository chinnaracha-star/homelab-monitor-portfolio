from typing import Protocol


class DeliveryError(Exception):
    """A notification provider rejected or failed a delivery."""


class NotificationProvider(Protocol):
    channel: str
    recipient: str

    def send(self, message: str) -> None: ...

    def close(self) -> None: ...
