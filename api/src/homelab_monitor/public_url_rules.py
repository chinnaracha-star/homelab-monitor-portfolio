"""Load shared/public-url-rules.json — the only Public URL rule set."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from homelab_monitor.settings import get_settings

_PACKAGE_RULES = Path(__file__).resolve().parent / "public-url-rules.json"


def _candidate_paths() -> tuple[Path, ...]:
    repo = Path(__file__).resolve().parents[3] / "shared" / "public-url-rules.json"
    return (
        Path("/app/shared/public-url-rules.json"),
        repo,
        _PACKAGE_RULES,
    )


def shared_public_url_rules_path() -> Path:
    for path in _candidate_paths():
        if path.is_file():
            return path
    return _PACKAGE_RULES


@lru_cache(maxsize=1)
def load_public_url_rules() -> dict[str, Any]:
    path = shared_public_url_rules_path()
    payload = json.loads(path.read_text(encoding="utf-8"))
    return _apply_overrides(payload)


def _apply_overrides(payload: dict[str, Any]) -> dict[str, Any]:
    overrides = payload.get("overrides")
    if not isinstance(overrides, dict):
        return payload
    try:
        environment = get_settings().environment
    except Exception:
        environment = ""
    extra = overrides.get(environment)
    if not isinstance(extra, dict) or not extra:
        return payload
    merged = json.loads(json.dumps(payload))
    hosts = merged.setdefault("hosts", {})
    host_extra = extra.get("hosts")
    if isinstance(host_extra, dict):
        for key, value in host_extra.items():
            if isinstance(value, list) and isinstance(hosts.get(key), list):
                hosts[key] = list(dict.fromkeys([*hosts[key], *value]))
            else:
                hosts[key] = value
    schemes = extra.get("schemes")
    if isinstance(schemes, dict):
        merged.setdefault("schemes", {}).update(schemes)
    return merged


def reset_public_url_rules_cache() -> None:
    load_public_url_rules.cache_clear()
