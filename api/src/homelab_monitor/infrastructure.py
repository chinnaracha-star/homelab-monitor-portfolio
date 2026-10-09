import logging
from datetime import UTC, datetime

from homelab_monitor.connectors import (
    SERVICES,
    BackupConnector,
    BaseConnector,
    ConnectorSnapshot,
    DockerConnector,
    ImmichConnector,
    QnapConnector,
    QuMagieConnector,
    failed_snapshot,
)
from homelab_monitor.photo_stats import PHOTO_SERVICE_NAMES, build_photo_stats
from homelab_monitor.settings import Settings

logger = logging.getLogger("homelab_monitor.infrastructure")


class InfrastructureService:
    def __init__(self, connectors: list[BaseConnector]) -> None:
        self._connectors = {connector.service: connector for connector in connectors}
        self._cache: dict[str, ConnectorSnapshot] = {}
        self._collected_at: datetime | None = None

    def refresh(self) -> list[ConnectorSnapshot]:
        snapshots: list[ConnectorSnapshot] = []
        for service, connector in self._connectors.items():
            try:
                snapshot = connector.collect()
                self._cache[service] = snapshot
                snapshots.append(snapshot)
            except Exception as error:
                logger.exception("connector_collect_failed", extra={"service": service})
                cached = self._cache.get(service)
                if cached is not None:
                    snapshots.append(cached)
                else:
                    snapshots.append(failed_snapshot(service, str(error)))
        self._collected_at = datetime.now(UTC)
        return snapshots

    def snapshot(self) -> tuple[datetime, list[ConnectorSnapshot]]:
        services = self.refresh()
        collected_at = self._collected_at or datetime.now(UTC)
        order = {name: index for index, name in enumerate(SERVICES)}
        services = sorted(services, key=lambda item: order.get(item.service, 99))
        return collected_at, services

    def cached(self, service: str) -> ConnectorSnapshot | None:
        return self._cache.get(service)

    def get(self, service: str) -> ConnectorSnapshot | None:
        if service not in self._connectors:
            return None
        for item in self.refresh():
            if item.service == service:
                return item
        return failed_snapshot(service, "No snapshot available")

    def photo_services(self) -> tuple[datetime, list[ConnectorSnapshot], dict[str, object]]:
        collected_at, services = self.snapshot()
        by_name = {item.service: item for item in services}
        selected = [by_name[name] for name in PHOTO_SERVICE_NAMES if name in by_name]
        return collected_at, selected, build_photo_stats(by_name)

    def backup(self) -> ConnectorSnapshot | None:
        if "backup" not in self._connectors:
            return None
        return self.get("backup")


def _secret(value: object) -> str:
    if value is None:
        return ""
    getter = getattr(value, "get_secret_value", None)
    if callable(getter):
        return str(getter())
    return str(value)


def build_infrastructure_service(settings: Settings) -> InfrastructureService:
    mock = settings.infrastructure_mock
    timeout = settings.infrastructure_timeout_seconds
    return InfrastructureService(
        [
            QnapConnector(
                mock=mock,
                base_url=settings.qnap_url,
                timeout=settings.qnap_timeout_seconds,
                api_key=settings.qnap_sid,
                username=settings.qnap_username,
                password=_secret(settings.qnap_password),
                tls_verify=settings.qnap_tls_verify,
            ),
            DockerConnector(mock=mock, base_url=settings.docker_url, timeout=timeout),
            ImmichConnector(
                mock=mock,
                base_url=settings.immich_url,
                timeout=timeout,
                api_key=_secret(settings.immich_api_key),
            ),
            QuMagieConnector(
                mock=mock,
                base_url=settings.qumagie_url,
                timeout=timeout,
                api_key=_secret(settings.qumagie_api_key),
            ),
            BackupConnector(mock=mock, base_url=settings.backup_url, timeout=timeout),
        ]
    )


_service: InfrastructureService | None = None


def get_infrastructure_service() -> InfrastructureService:
    global _service
    if _service is None:
        from homelab_monitor.settings import get_settings

        _service = build_infrastructure_service(get_settings())
    return _service


def reset_infrastructure_service(service: InfrastructureService | None = None) -> None:
    global _service
    _service = service
