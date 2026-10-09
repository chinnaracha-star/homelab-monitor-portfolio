import logging
import threading
from typing import Any, Protocol

from homelab_agent.buffer import ReportBuffer
from homelab_agent.config import AgentSettings
from homelab_agent.logging import log_event
from homelab_agent.models import AgentControl, ModuleResult, ReportPayload, ReportUploadResponse
from homelab_agent.transport import (
    AuthenticationError,
    PermanentTransportError,
    TransientTransportError,
)

logger = logging.getLogger("homelab_agent")


class Collector(Protocol):
    def collect(self) -> ModuleResult: ...


class Transport(Protocol):
    def check_in(self, config_revision: int) -> AgentControl: ...

    def upload_report(self, payload: dict[str, Any]) -> ReportUploadResponse: ...

    def close(self) -> None: ...


class AgentService:
    def __init__(
        self,
        settings: AgentSettings,
        transport: Transport,
        buffer: ReportBuffer,
        collector: Collector,
    ) -> None:
        self.settings = settings
        self.transport = transport
        self.buffer = buffer
        self.collector = collector
        self.stop_event = threading.Event()
        stored_revision = buffer.get_metadata("config_revision")
        self.config_revision = (
            int(stored_revision) if stored_revision is not None else settings.config_revision
        )
        self.next_report_in = settings.report_interval

    def run(self) -> None:
        log_event(
            logger,
            "agent_started",
            agent_name=self.settings.agent_name,
            report_interval=self.next_report_in,
        )
        try:
            while not self.stop_event.is_set():
                self.run_cycle()
                self.stop_event.wait(self.next_report_in)
        finally:
            self.close()

    def run_cycle(self) -> None:
        can_upload = self._check_in()
        if can_upload:
            self._flush_buffer()

        module_result = self.collector.collect()
        log_event(
            logger,
            "metrics_collected",
            module=module_result.module,
            status=module_result.status,
        )
        report = ReportPayload(
            config_revision=self.config_revision,
            modules=[module_result],
        )
        payload = report.model_dump(mode="json")

        if not can_upload:
            self._buffer_report(report.report_id, payload, "check-in unavailable")
            return

        try:
            response = self.transport.upload_report(payload)
        except AuthenticationError as error:
            self._authentication_failed(error)
            self._buffer_report(report.report_id, payload, str(error))
        except TransientTransportError as error:
            self._buffer_report(report.report_id, payload, str(error))
        except PermanentTransportError as error:
            log_event(
                logger,
                "report_rejected",
                level=logging.ERROR,
                report_id=report.report_id,
                error=str(error),
            )
        else:
            self._apply_control(response.control)
            log_event(
                logger,
                "report_uploaded",
                report_id=report.report_id,
                duplicate=response.duplicate,
            )

    def _check_in(self) -> bool:
        try:
            control = self.transport.check_in(self.config_revision)
        except AuthenticationError as error:
            self._authentication_failed(error)
            return False
        except (TransientTransportError, PermanentTransportError) as error:
            log_event(
                logger,
                "check_in_failed",
                level=logging.WARNING,
                error=str(error),
            )
            return False

        self._apply_control(control)
        log_event(
            logger,
            "check_in_success",
            next_report_in=self.next_report_in,
            config_revision=self.config_revision,
            update_available=control.update_available,
        )
        return True

    def _flush_buffer(self) -> None:
        for buffered in self.buffer.pending():
            try:
                response = self.transport.upload_report(buffered.payload)
            except AuthenticationError as error:
                self.buffer.mark_failed(buffered.report_id, str(error))
                self._authentication_failed(error)
                return
            except (TransientTransportError, PermanentTransportError) as error:
                self.buffer.mark_failed(buffered.report_id, str(error))
                log_event(
                    logger,
                    "check_in_failed",
                    level=logging.WARNING,
                    error=str(error),
                    buffered_report_id=buffered.report_id,
                )
                return

            self.buffer.mark_delivered(buffered.report_id)
            self._apply_control(response.control)
            log_event(
                logger,
                "buffered_report_retried",
                report_id=buffered.report_id,
                duplicate=response.duplicate,
                previous_attempts=buffered.attempts,
            )

    def _buffer_report(self, report_id: str, payload: dict[str, Any], error: str) -> None:
        dropped = self.buffer.enqueue(report_id, payload)
        self.buffer.mark_failed(report_id, error)
        log_event(
            logger,
            "report_buffered",
            level=logging.WARNING,
            report_id=report_id,
            buffer_size=self.buffer.count(),
            dropped_oldest=dropped,
            error=error,
        )

    def _apply_control(self, control: AgentControl) -> None:
        self.next_report_in = min(3600, max(15, control.next_report_in))
        if control.configuration is not None:
            self._apply_configuration(control.configuration)
        self.config_revision = control.config_revision
        self.buffer.set_metadata("config_revision", str(self.config_revision))

    def _apply_configuration(self, configuration: dict[str, Any]) -> None:
        system = configuration.get("modules", {}).get("system", {})
        threshold_fields = (
            "cpu_warning_percent",
            "memory_warning_percent",
            "disk_warning_percent",
        )
        for field in threshold_fields:
            value = system.get(field)
            if isinstance(value, int | float) and 0 <= value <= 100:
                setattr(self.settings, field, float(value))

    def _authentication_failed(self, error: AuthenticationError) -> None:
        self.next_report_in = max(self.next_report_in, 300)
        log_event(
            logger,
            "authentication_failed",
            level=logging.ERROR,
            error=str(error),
            next_retry_in=self.next_report_in,
        )

    def stop(self) -> None:
        self.stop_event.set()

    def close(self) -> None:
        self.transport.close()
        self.buffer.close()
