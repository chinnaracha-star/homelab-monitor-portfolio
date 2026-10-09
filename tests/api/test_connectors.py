from homelab_monitor.connectors import (
    BackupConnector,
    DockerConnector,
    ImmichConnector,
    QnapConnector,
    QuMagieConnector,
)
from homelab_monitor.connectors.base import BaseConnector, ConnectorSnapshot, utc_now
from homelab_monitor.infrastructure import InfrastructureService


def test_mock_connectors_return_normalized_snapshots() -> None:
    connectors = [
        QnapConnector(mock=True),
        DockerConnector(mock=True),
        ImmichConnector(mock=True),
        QuMagieConnector(mock=True),
        BackupConnector(mock=True),
    ]
    for connector in connectors:
        snapshot = connector.collect()
        assert snapshot.service == connector.service
        assert snapshot.status == "healthy"
        assert snapshot.version
        assert snapshot.summary
        assert connector.health() == "healthy"
        assert connector.version() == snapshot.version
        assert connector.summary() == snapshot.summary


def test_unconfigured_live_connectors_are_unknown() -> None:
    snapshot = QnapConnector(mock=False, base_url="").collect()
    assert snapshot.status == "unknown"
    assert snapshot.summary == {}


def test_infrastructure_service_isolates_connector_failures() -> None:
    class Boom(BaseConnector):
        service = "qnap"

        def collect(self) -> ConnectorSnapshot:
            raise RuntimeError("qnap down")

    service = InfrastructureService(
        [
            Boom(mock=True),
            DockerConnector(mock=True),
        ]
    )
    _collected_at, snapshots = service.snapshot()
    by_name = {item.service: item for item in snapshots}
    assert by_name["qnap"].status == "unhealthy"
    assert "qnap down" in str(by_name["qnap"].summary.get("error"))
    assert by_name["docker"].status == "healthy"


def test_infrastructure_service_keeps_last_successful_snapshot() -> None:
    class Flaky(BaseConnector):
        service = "immich"
        calls = 0

        def collect(self) -> ConnectorSnapshot:
            self.calls += 1
            if self.calls == 1:
                return ConnectorSnapshot(
                    service="immich",
                    status="healthy",
                    version="1.0.0",
                    updated_at=utc_now(),
                    summary={"indexed_photos": 10},
                )
            raise RuntimeError("immich timeout")

    flaky = Flaky(mock=True)
    service = InfrastructureService([flaky])
    first = service.get("immich")
    assert first is not None
    assert first.status == "healthy"
    second = service.get("immich")
    assert second is not None
    assert second.status == "healthy"
    assert second.version == "1.0.0"
