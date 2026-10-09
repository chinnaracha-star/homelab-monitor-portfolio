from __future__ import annotations

from contextvars import ContextVar, Token

from fastapi import Request

from homelab_monitor.remote_access import RemoteAccessService
from homelab_monitor.settings import Settings, get_settings
from homelab_monitor.telegram_url_validator import validate_public_url

_request_origin: ContextVar[str | None] = ContextVar("telegram_request_origin", default=None)


def bind_request_origin(request: Request) -> Token:
    return _request_origin.set(_origin_from_request(request))


def reset_request_origin(token: Token) -> None:
    _request_origin.reset(token)


def _origin_from_request(request: Request) -> str | None:
    forwarded_host = request.headers.get("x-forwarded-host") or request.headers.get("host")
    if not forwarded_host:
        return None
    host = forwarded_host.split(",", 1)[0].strip()
    if not host:
        return None
    proto = (request.headers.get("x-forwarded-proto") or request.url.scheme or "http").split(",")[0]
    return f"{proto.strip()}://{host}".rstrip("/")


def is_telegram_button_url(value: str | None) -> bool:
    return validate_public_url(value) is not None


def _tailnet_url(settings: Settings) -> str | None:
    access = RemoteAccessService(settings=settings).snapshot()
    hostname = (access.hostname or "").strip().rstrip(".")
    if not hostname:
        return None
    return f"https://{hostname}"


def resolve_dashboard_url(settings: Settings | None = None) -> str | None:
    """Public dashboard URL only. Never uses Docker/health/localhost URLs."""
    config = settings or get_settings()
    configured = validate_public_url(config.dashboard_public_url, kind="dashboard")
    if configured:
        return configured
    tailnet = validate_public_url(_tailnet_url(config), kind="dashboard")
    if tailnet:
        return tailnet
    origin = validate_public_url(_request_origin.get(), kind="dashboard")
    if origin:
        return origin
    return None


def resolve_immich_url(settings: Settings | None = None) -> str | None:
    config = settings or get_settings()
    public = validate_public_url(config.immich_public_url, kind="immich")
    if public:
        return public
    return validate_public_url(config.immich_url, kind="immich")


def resolve_qnap_url(settings: Settings | None = None) -> str | None:
    config = settings or get_settings()
    public = validate_public_url(config.qnap_public_url, kind="qnap")
    if public:
        return public
    return validate_public_url(config.qnap_url, kind="qnap")
