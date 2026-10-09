from __future__ import annotations

import time
from collections.abc import Callable

import httpx

from homelab_monitor.notifications import RETRY_ATTEMPTS, RETRY_DELAY_SECONDS
from homelab_monitor.telegram import TelegramNotificationError

_TRANSIENT_TEXT = (
    "timed out",
    "timeout",
    "network failure",
    "connection",
    "http 429",
    "http 500",
    "http 502",
    "http 503",
    "http 504",
)


def is_transient_delivery_error(error: BaseException) -> bool:
    if isinstance(
        error, httpx.TimeoutException | httpx.RequestError | TimeoutError | ConnectionError
    ):
        return True
    if isinstance(error, TelegramNotificationError):
        text = str(error).lower()
        return any(marker in text for marker in _TRANSIENT_TEXT)
    return False


def retry_transient[T](
    operation: Callable[[], T],
    *,
    attempts: int = RETRY_ATTEMPTS,
    base_delay: float = RETRY_DELAY_SECONDS,
) -> T:
    last_error: BaseException | None = None
    for attempt in range(1, attempts + 1):
        try:
            return operation()
        except Exception as error:
            last_error = error
            if not is_transient_delivery_error(error) or attempt >= attempts:
                raise
            time.sleep(base_delay * (2 ** (attempt - 1)))
    assert last_error is not None
    raise last_error
