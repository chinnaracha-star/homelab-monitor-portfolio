"""Public URL validation for Telegram buttons and operator-facing links."""

from __future__ import annotations

import fnmatch
import logging
from urllib.parse import urlparse

from homelab_monitor.public_url_rules import load_public_url_rules
from homelab_monitor.settings import Settings, get_settings

logger = logging.getLogger("homelab_monitor.telegram_urls")


def _rules() -> dict:
    return load_public_url_rules()


def _allowed_schemes() -> set[str]:
    schemes = _rules().get("schemes") or {}
    allow = schemes.get("allow") or ["http", "https"]
    return {str(item).lower() for item in allow}


def _host_list(key: str) -> list[str]:
    hosts = _rules().get("hosts") or {}
    values = hosts.get(key) or []
    return [str(item).lower() for item in values]


def _host_allowed(host: str) -> bool:
    exact = set(_host_list("allow_exact"))
    if host in exact:
        return True
    for suffix in _host_list("allow_suffixes"):
        if host.endswith(suffix):
            return True
    return any(fnmatch.fnmatch(host, pattern) for pattern in _host_list("allow_wildcards"))


def _host_rejected(host: str) -> str | None:
    if _host_allowed(host):
        return None
    if host in set(_host_list("reject_exact")):
        if host in {"localhost", "127.0.0.1", "::1", "0.0.0.0", "[::1]"} or host.startswith("127."):
            return "loopback"
        return "internal_docker_host"
    for prefix in _host_list("reject_prefixes"):
        if host.startswith(prefix):
            return "loopback" if prefix.startswith("127.") else "internal_docker_host"
    for suffix in _host_list("reject_suffixes"):
        if host.endswith(suffix):
            return "private_only_tld"
    hosts = _rules().get("hosts") or {}
    if hosts.get("reject_single_label", True) and "." not in host:
        return "internal_docker_host"
    return None


def public_url_rejection_reason(url: str | None) -> str | None:
    """Return a machine reason if `url` is not Telegram-safe. Never raises."""
    text = (url or "").strip()
    if not text:
        return "empty"
    try:
        parsed = urlparse(text if "://" in text else f"https://{text}")
    except ValueError:
        return "invalid"
    scheme = (parsed.scheme or "").lower()
    if scheme not in _allowed_schemes():
        return "missing_http_scheme"
    host = (parsed.hostname or "").lower().rstrip(".")
    if not host:
        return "missing_host"
    return _host_rejected(host)


def validate_public_url(url: str | None, *, kind: str = "url") -> str | None:
    """Accept only URLs Telegram can open. Return None on failure. Never raises."""
    try:
        reason = public_url_rejection_reason(url)
        text = (url or "").strip()
        if reason:
            if text and reason != "empty":
                logger.info(
                    "Telegram %s URL rejected: reason=%s url=%s",
                    kind,
                    reason,
                    text,
                )
            return None
        parsed = urlparse(text if "://" in text else f"https://{text}")
        cleaned = f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")
        return cleaned or None
    except Exception:
        logger.info("Telegram %s URL rejected: reason=invalid url=%s", kind, (url or "").strip())
        return None


def build_public_inline_keyboard(settings: Settings | None = None) -> dict | None:
    """Build Dashboard/Immich/QNAP buttons from public URLs only."""
    try:
        from homelab_monitor.telegram_links import (
            resolve_dashboard_url,
            resolve_immich_url,
            resolve_qnap_url,
        )

        config = settings or get_settings()
        buttons: list[dict[str, str]] = []
        flags: dict[str, str] = {}
        mapping = (
            ("dashboard", "🏠 Dashboard", resolve_dashboard_url(config)),
            ("immich", "📷 Immich", resolve_immich_url(config)),
            ("qnap", "💾 QNAP", resolve_qnap_url(config)),
        )
        for key, label, url in mapping:
            safe = validate_public_url(url, kind=key)
            flags[key] = "yes" if safe else "no"
            if safe:
                buttons.append({"text": label, "url": safe})
        logger.info(
            "Telegram buttons: dashboard=%s immich=%s qnap=%s",
            flags["dashboard"],
            flags["immich"],
            flags["qnap"],
        )
        if not buttons:
            logger.info("Telegram keyboard disabled: reason=no_valid_public_urls")
            return None
        return {"inline_keyboard": [[button] for button in buttons]}
    except Exception:
        logger.exception("Telegram keyboard disabled: reason=builder_error")
        return None
