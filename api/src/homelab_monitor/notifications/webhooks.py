import httpx

from homelab_monitor.notifications.provider import DeliveryError


class WebhookProvider:
    def __init__(
        self,
        *,
        channel: str,
        webhook_url: str,
        payload_key: str,
        timeout: float,
        client: httpx.Client | None = None,
    ) -> None:
        if not webhook_url.startswith("https://"):
            raise ValueError(f"{channel} webhook URL must start with https://")
        self.channel = channel
        self.recipient = webhook_url
        self._payload_key = payload_key
        self._owns_client = client is None
        self._client = client or httpx.Client(timeout=timeout)

    def send(self, message: str) -> None:
        try:
            response = self._client.post(self.recipient, json={self._payload_key: message})
        except httpx.HTTPError as error:
            raise DeliveryError(str(error)) from error
        if response.status_code >= 400:
            raise DeliveryError(f"{self.channel} webhook returned HTTP {response.status_code}")

    def close(self) -> None:
        if self._owns_client:
            self._client.close()


def discord_provider(webhook_url: str, timeout: float = 10.0) -> WebhookProvider:
    return WebhookProvider(
        channel="discord",
        webhook_url=webhook_url,
        payload_key="content",
        timeout=timeout,
    )


def slack_provider(webhook_url: str, timeout: float = 10.0) -> WebhookProvider:
    return WebhookProvider(
        channel="slack",
        webhook_url=webhook_url,
        payload_key="text",
        timeout=timeout,
    )
