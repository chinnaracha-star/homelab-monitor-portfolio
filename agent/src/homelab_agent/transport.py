import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import httpx

from homelab_agent import __version__
from homelab_agent.config import AgentSettings
from homelab_agent.models import AgentControl, ReportUploadResponse


class AgentTransportError(Exception):
    """Base exception for transport failures."""


class AuthenticationError(AgentTransportError):
    """The server rejected the agent credential."""


class TransientTransportError(AgentTransportError):
    """A retryable failure remained after bounded retries."""


class PermanentTransportError(AgentTransportError):
    """The server rejected a request that must not be retried unchanged."""


class AgentTransport:
    def __init__(
        self,
        settings: AgentSettings,
        *,
        client: httpx.Client | None = None,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        server_url, token = settings.require_runtime_credentials()
        self.settings = settings
        self._sleeper = sleeper
        self._owns_client = client is None
        self._client = client or httpx.Client(
            base_url=server_url,
            timeout=settings.request_timeout,
        )
        self._authorization = f"Bearer {token}"

    def check_in(self, config_revision: int) -> AgentControl:
        response = self._request(
            "POST",
            "/api/v1/agent/check-ins",
            json={
                "version": __version__,
                "observed_at": datetime.now(UTC).isoformat(),
                "config_revision": config_revision,
            },
        )
        return AgentControl.model_validate(response.json())

    def upload_report(self, payload: dict[str, Any]) -> ReportUploadResponse:
        response = self._request("POST", "/api/v1/agent/reports", json=payload)
        return ReportUploadResponse.model_validate(response.json())

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        last_error: Exception | None = None
        backoff = self.settings.retry_initial_backoff

        for attempt in range(1, self.settings.retry_attempts + 1):
            try:
                response = self._client.request(
                    method,
                    path,
                    headers={"Authorization": self._authorization},
                    **kwargs,
                )
            except (httpx.TimeoutException, httpx.NetworkError) as error:
                last_error = error
            else:
                if response.status_code in {401, 403}:
                    raise AuthenticationError(
                        f"Agent authentication failed with HTTP {response.status_code}"
                    )
                if response.status_code < 400:
                    return response
                if response.status_code < 500:
                    raise PermanentTransportError(
                        f"Server rejected request with HTTP {response.status_code}"
                    )
                last_error = TransientTransportError(f"Server returned HTTP {response.status_code}")

            if attempt < self.settings.retry_attempts:
                self._sleeper(backoff)
                backoff = min(
                    max(backoff * 2, self.settings.retry_initial_backoff),
                    self.settings.retry_max_backoff,
                )

        message = str(last_error) if last_error else "Unknown network failure"
        raise TransientTransportError(message) from last_error

    def close(self) -> None:
        if self._owns_client:
            self._client.close()
