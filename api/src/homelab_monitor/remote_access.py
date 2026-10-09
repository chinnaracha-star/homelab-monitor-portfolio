from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal

import httpx

from homelab_monitor.schemas import RemoteAccessResponse
from homelab_monitor.settings import Settings, get_settings

STATUS_NOT_INSTALLED = "not_installed"
STATUS_DISCONNECTED = "disconnected"
STATUS_CONNECTED = "connected"
STATUS_UNKNOWN = "unknown"

RunCommand = Callable[[list[str]], tuple[int, str]]
LocalApiGet = Callable[[str], dict[str, Any] | None]
RemoteStatus = Literal["connected", "disconnected", "not_installed", "unknown"]


def _empty(status: RemoteStatus) -> RemoteAccessResponse:
    return RemoteAccessResponse(
        enabled=False,
        provider="tailscale",
        hostname=None,
        tailnet_ip=None,
        https=False,
        serve_enabled=False,
        funnel_enabled=False,
        public=False,
        status=status,
    )


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _hostname(status: dict[str, Any]) -> str | None:
    certs = status.get("CertDomains")
    if isinstance(certs, list):
        for item in certs:
            name = str(item).strip().rstrip(".")
            if name:
                return name
    dns = str(_as_dict(status.get("Self")).get("DNSName") or "").strip().rstrip(".")
    return dns or None


def _tailnet_ip(status: dict[str, Any]) -> str | None:
    ips = _as_dict(status.get("Self")).get("TailscaleIPs")
    if not isinstance(ips, list):
        return None
    for item in ips:
        text = str(item)
        if text.startswith("100."):
            return text
    return str(ips[0]) if ips else None


def _backend_running(status: dict[str, Any]) -> bool:
    backend = str(status.get("BackendState") or "")
    online = _as_dict(status.get("Self")).get("Online")
    return backend == "Running" and online is not False


def _unwrap_serve(payload: dict[str, Any]) -> dict[str, Any]:
    for key in ("Background", "Foreground"):
        inner = payload.get(key)
        if isinstance(inner, dict) and ("Web" in inner or "TCP" in inner or "AllowFunnel" in inner):
            return inner
    return payload


def _serve_flags(payload: dict[str, Any]) -> tuple[bool, bool, bool]:
    body = _unwrap_serve(payload)
    tcp = _as_dict(body.get("TCP"))
    web = _as_dict(body.get("Web"))
    funnel = body.get("AllowFunnel")
    if funnel is None:
        funnel = body.get("Funnel")
    serve_enabled = bool(tcp) or bool(web)
    https = False
    for spec in tcp.values():
        if isinstance(spec, dict) and spec.get("HTTPS"):
            https = True
    if any(":443" in str(key) for key in web):
        https = True
    funnel_enabled = False
    if isinstance(funnel, dict):
        funnel_enabled = any(bool(value) for value in funnel.values())
    elif isinstance(funnel, bool):
        funnel_enabled = funnel
    return serve_enabled, https, funnel_enabled


class RemoteAccessService:
    """Read-only Tailscale detection. Never starts, stops, or configures Tailscale."""

    def __init__(
        self,
        *,
        run: RunCommand | None = None,
        localapi: LocalApiGet | None = None,
        binary_available: Callable[[str], bool] | None = None,
        socket_exists: Callable[[str], bool] | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._run = run or self._run_cli
        self._localapi = localapi or self._localapi_get
        self._binary_available = binary_available or (lambda path: shutil.which(path) is not None)
        self._socket_exists = socket_exists or (lambda path: bool(path) and Path(path).exists())
        self._settings = settings

    def snapshot(self) -> RemoteAccessResponse:
        try:
            return self._snapshot()
        except Exception:
            return _empty(STATUS_UNKNOWN)

    def _snapshot(self) -> RemoteAccessResponse:
        settings = self._settings or get_settings()
        binary = settings.tailscale_bin.strip() or "tailscale"
        socket_path = settings.tailscale_socket.strip()
        has_cli = self._binary_available(binary)
        has_socket = self._socket_exists(socket_path)
        if not has_cli and not has_socket:
            return _empty(STATUS_NOT_INSTALLED)

        status_payload = self._load_status(has_cli)
        if status_payload is None and has_socket:
            status_payload = self._localapi("/localapi/v0/status")
        if status_payload is None:
            if has_cli:
                return _empty(STATUS_DISCONNECTED)
            return _empty(STATUS_NOT_INSTALLED)

        hostname = _hostname(status_payload)
        tailnet_ip = _tailnet_ip(status_payload)
        connected = _backend_running(status_payload)
        serve_payload = self._load_serve(has_cli)
        if serve_payload is None and has_socket:
            serve_payload = self._localapi("/localapi/v0/serve-config")
        serve_enabled, serve_https, funnel_enabled = (
            _serve_flags(serve_payload) if serve_payload else (False, False, False)
        )
        https = serve_https or bool(status_payload.get("CertDomains"))
        status = STATUS_CONNECTED if connected else STATUS_DISCONNECTED
        return RemoteAccessResponse(
            enabled=connected,
            provider="tailscale",
            hostname=hostname,
            tailnet_ip=tailnet_ip,
            https=https,
            serve_enabled=serve_enabled,
            funnel_enabled=funnel_enabled,
            public=funnel_enabled,
            status=status,
        )

    def _load_status(self, has_cli: bool) -> dict[str, Any] | None:
        if not has_cli:
            return None
        return self._cli_json(["status", "--json"])

    def _load_serve(self, has_cli: bool) -> dict[str, Any] | None:
        if not has_cli:
            return None
        return self._cli_json(["serve", "status", "--json"])

    def _cli_json(self, args: list[str]) -> dict[str, Any] | None:
        try:
            code, stdout = self._run(args)
        except FileNotFoundError:
            return None
        if code != 0 or not stdout.strip():
            return None
        try:
            parsed = json.loads(stdout)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None

    def _run_cli(self, args: list[str]) -> tuple[int, str]:
        settings = self._settings or get_settings()
        try:
            result = subprocess.run(
                [settings.tailscale_bin, *args],
                capture_output=True,
                text=True,
                timeout=settings.tailscale_timeout_seconds,
                check=False,
            )
        except FileNotFoundError:
            raise
        except (OSError, subprocess.TimeoutExpired):
            return 1, ""
        return result.returncode, result.stdout

    def _localapi_get(self, path: str) -> dict[str, Any] | None:
        settings = self._settings or get_settings()
        socket_path = settings.tailscale_socket.strip()
        if not socket_path or not self._socket_exists(socket_path):
            return None
        try:
            transport = httpx.HTTPTransport(uds=socket_path)
            with httpx.Client(
                transport=transport,
                base_url="http://local-tailscaled.sock",
                timeout=settings.tailscale_timeout_seconds,
            ) as client:
                response = client.get(path)
        except (OSError, httpx.HTTPError):
            return None
        if response.status_code >= 400:
            return None
        try:
            parsed = response.json()
        except ValueError:
            return None
        return parsed if isinstance(parsed, dict) else None
