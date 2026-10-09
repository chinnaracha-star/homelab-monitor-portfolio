import json
import logging
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from homelab_monitor.telegram_links import bind_request_origin, reset_request_origin


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        try:
            message = record.getMessage()
        except Exception:
            message = str(record.msg)
        payload = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": _json_safe_text(message),
        }
        for key in ("request_id", "method", "path", "status_code", "duration_ms"):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        if record.exc_info:
            payload["exception"] = _json_safe_text(self.formatException(record.exc_info))
        try:
            return json.dumps(payload, separators=(",", ":"), ensure_ascii=True, default=str)
        except Exception:
            return json.dumps(
                {
                    "timestamp": datetime.now(UTC).isoformat(),
                    "level": getattr(record, "levelname", "ERROR"),
                    "logger": getattr(record, "name", "homelab_monitor"),
                    "message": "log_format_failed",
                },
                separators=(",", ":"),
                ensure_ascii=True,
            )


def _json_safe_text(value: object) -> str:
    return str(value).encode("utf-8", "replace").decode("utf-8")


def configure_logging(level: str, log_dir: str = "") -> None:
    formatter = JsonFormatter()
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    handlers[0].setFormatter(formatter)

    if log_dir:
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(
            log_path / "api.jsonl", encoding="utf-8", errors="replace"
        )
        file_handler.setFormatter(formatter)
        handlers.append(file_handler)

    logging.basicConfig(level=level.upper(), handlers=handlers, force=True)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        request.state.request_id = request_id
        started_at = time.perf_counter()
        origin_token = bind_request_origin(request)
        try:
            response = await call_next(request)
            duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
            from homelab_monitor.performance import record_api_duration

            record_api_duration(duration_ms)
            response.headers["x-request-id"] = request_id
            logging.getLogger("homelab_monitor.http").info(
                "request_completed",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": duration_ms,
                },
            )
            return response
        finally:
            reset_request_origin(origin_token)
