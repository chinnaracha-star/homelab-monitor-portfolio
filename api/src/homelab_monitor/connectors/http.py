from typing import Any

import httpx


def http_get(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: float = 2.0,
    client: httpx.Client | None = None,
) -> httpx.Response:
    """Issue a GET request. Connectors must never POST, PUT, PATCH, or DELETE."""
    owns_client = client is None
    http = client or httpx.Client(timeout=timeout)
    try:
        response = http.get(url, headers=headers or {})
        response.raise_for_status()
        return response
    finally:
        if owns_client:
            http.close()


def get_json(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: float = 2.0,
    client: httpx.Client | None = None,
) -> Any:
    response = http_get(url, headers=headers, timeout=timeout, client=client)
    content_type = response.headers.get("content-type", "")
    if "json" in content_type or response.text.lstrip().startswith(("{", "[")):
        return response.json()
    return {"raw": response.text}


def as_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def as_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value)
