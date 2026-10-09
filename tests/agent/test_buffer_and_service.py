from pathlib import Path

from homelab_agent.buffer import ReportBuffer
from homelab_agent.config import AgentSettings
from homelab_agent.models import (
    AgentControl,
    ModuleResult,
    ReportPayload,
    ReportUploadResponse,
)
from homelab_agent.service import AgentService
from homelab_agent.transport import AuthenticationError, TransientTransportError


def control() -> AgentControl:
    return AgentControl(
        next_report_in=90,
        config_revision=3,
        configuration=None,
        minimum_agent_version="0.1.0",
        latest_agent_version="0.1.0",
        update_available=False,
        commands=[],
    )


class FakeCollector:
    def collect(self) -> ModuleResult:
        return ModuleResult(
            module="system",
            status="healthy",
            summary="System operating normally",
            metrics={"cpu": {"usage_percent": 10.0}},
            diagnostics={},
        )


class RecoveringTransport:
    def __init__(self) -> None:
        self.online = False
        self.uploaded: list[dict[str, object]] = []

    def check_in(self, _config_revision: int) -> AgentControl:
        if not self.online:
            raise TransientTransportError("connection refused")
        return control()

    def upload_report(self, payload: dict[str, object]) -> ReportUploadResponse:
        self.uploaded.append(payload)
        return ReportUploadResponse(
            accepted=True,
            duplicate=False,
            report_id=str(payload["report_id"]),
            control=control(),
        )

    def close(self) -> None:
        pass


class UnauthorizedTransport(RecoveringTransport):
    def check_in(self, _config_revision: int) -> AgentControl:
        raise AuthenticationError("Agent authentication failed with HTTP 401")


def settings(buffer_path: Path) -> AgentSettings:
    return AgentSettings(
        server_url="http://monitor.test",
        agent_token="secret-agent-token",
        buffer_path=buffer_path,
        retry_initial_backoff=0,
    )


def test_buffer_survives_restart_and_preserves_report_id(tmp_path: Path) -> None:
    path = tmp_path / "buffer.db"
    first = ReportBuffer(path, max_reports=10)
    payload = {
        "report_id": "original-report-id",
        "schema_version": "1.0",
        "modules": [],
    }
    first.enqueue("original-report-id", payload)
    first.close()

    reopened = ReportBuffer(path, max_reports=10)
    pending = reopened.pending()

    assert len(pending) == 1
    assert pending[0].report_id == "original-report-id"
    assert pending[0].payload["report_id"] == "original-report-id"
    reopened.close()


def test_buffer_size_is_bounded(tmp_path: Path) -> None:
    buffer = ReportBuffer(tmp_path / "bounded.db", max_reports=2)

    buffer.enqueue("one", {"report_id": "one"})
    buffer.enqueue("two", {"report_id": "two"})
    dropped = buffer.enqueue("three", {"report_id": "three"})

    assert dropped == 1
    assert [report.report_id for report in buffer.pending()] == ["two", "three"]
    buffer.close()


def test_offline_report_is_retried_after_agent_restart(tmp_path: Path) -> None:
    path = tmp_path / "agent.db"
    agent_settings = settings(path)
    transport = RecoveringTransport()
    first_buffer = ReportBuffer(path, max_reports=10)
    first_service = AgentService(
        agent_settings,
        transport,
        first_buffer,
        FakeCollector(),
    )

    first_service.run_cycle()
    buffered_id = first_buffer.pending()[0].report_id
    first_buffer.close()

    transport.online = True
    restarted_buffer = ReportBuffer(path, max_reports=10)
    restarted_service = AgentService(
        agent_settings,
        transport,
        restarted_buffer,
        FakeCollector(),
    )
    restarted_service.run_cycle()

    assert transport.uploaded[0]["report_id"] == buffered_id
    assert restarted_buffer.count() == 0
    assert restarted_service.next_report_in == 90
    restarted_buffer.close()


def test_authentication_failure_does_not_log_token(
    tmp_path: Path,
    caplog,
) -> None:
    agent_settings = settings(tmp_path / "auth.db")
    buffer = ReportBuffer(agent_settings.buffer_path, max_reports=10)
    service = AgentService(
        agent_settings,
        UnauthorizedTransport(),
        buffer,
        FakeCollector(),
    )

    service.run_cycle()

    assert "secret-agent-token" not in caplog.text
    assert service.next_report_in >= 300
    buffer.close()


def test_report_ids_are_unique() -> None:
    module = FakeCollector().collect()

    first = ReportPayload(modules=[module])
    second = ReportPayload(modules=[module])

    assert first.report_id != second.report_id
