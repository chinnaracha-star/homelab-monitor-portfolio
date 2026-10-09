from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

ConnectorStatus = Literal["healthy", "degraded", "unhealthy", "unknown"]
SERVICES = ("qnap", "docker", "immich", "qumagie", "backup")


@dataclass(frozen=True)
class ConnectorSnapshot:
    service: str
    status: ConnectorStatus
    version: str
    updated_at: datetime
    summary: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "service": self.service,
            "status": self.status,
            "version": self.version,
            "updated_at": self.updated_at.isoformat(),
            "summary": self.summary,
        }


def utc_now() -> datetime:
    return datetime.now(UTC)


def failed_snapshot(service: str, reason: str) -> ConnectorSnapshot:
    return ConnectorSnapshot(
        service=service,
        status="unhealthy",
        version="",
        updated_at=utc_now(),
        summary={"error": reason},
    )


class BaseConnector(ABC):
    service: str

    def __init__(
        self,
        *,
        mock: bool = True,
        base_url: str = "",
        timeout: float = 2.0,
        api_key: str = "",
        username: str = "",
        password: str = "",
        client: Any = None,
    ) -> None:
        self.mock = mock
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.api_key = api_key
        self.username = username
        self.password = password
        self._client = client

    @abstractmethod
    def collect(self) -> ConnectorSnapshot:
        """Collect a normalized snapshot. Must not mutate external systems."""

    def health(self) -> str:
        return self.collect().status

    def version(self) -> str:
        return self.collect().version

    def summary(self) -> dict[str, Any]:
        return self.collect().summary
