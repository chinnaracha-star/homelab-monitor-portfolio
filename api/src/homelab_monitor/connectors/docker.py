from homelab_monitor.connectors.base import BaseConnector, ConnectorSnapshot, utc_now


class DockerConnector(BaseConnector):
    service = "docker"

    def collect(self) -> ConnectorSnapshot:
        if self.mock:
            return ConnectorSnapshot(
                service=self.service,
                status="healthy",
                version="27.3.1",
                updated_at=utc_now(),
                summary={
                    "running_containers": 12,
                    "stopped_containers": 2,
                    "restart_count": 4,
                    "docker_version": "27.3.1",
                },
            )
        if not self.base_url:
            return ConnectorSnapshot(
                service=self.service,
                status="unknown",
                version="",
                updated_at=utc_now(),
                summary={},
            )
        raise ConnectionError("Docker live collection is not configured for this environment")
