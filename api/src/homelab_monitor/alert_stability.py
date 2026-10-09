"""Hysteresis windows for metric alerts.

State is process-local so delays survive per-request AlertEngine instances
without a schema or API change. Windows reset on process restart.
"""

from datetime import UTC, datetime, timedelta


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


ZERO = timedelta(0)

TRIGGER_AFTER: dict[str, timedelta] = {
    "cpu_high": timedelta(minutes=2),
    "memory_high": timedelta(minutes=2),
    "temperature_high": timedelta(minutes=1),
    "disk_high": ZERO,
    "agent_offline": ZERO,
}

RECOVER_AFTER: dict[str, timedelta] = {
    "cpu_high": timedelta(minutes=2),
    "memory_high": timedelta(minutes=2),
    "temperature_high": timedelta(minutes=2),
    "disk_high": ZERO,
    "agent_offline": ZERO,
}

_pending_open: dict[tuple[str, str, str], datetime] = {}
_pending_close: dict[tuple[str, str, str], datetime] = {}


def reset_stability_windows() -> None:
    _pending_open.clear()
    _pending_close.clear()


def _key(agent_id: str, kind: str, resource: str) -> tuple[str, str, str]:
    return (agent_id, kind, resource)


def _elapsed(started: datetime, observed_at: datetime) -> timedelta:
    return _as_utc(observed_at) - _as_utc(started)


def should_open_alert(
    agent_id: str,
    kind: str,
    resource: str,
    observed_at: datetime,
) -> bool:
    delay = TRIGGER_AFTER.get(kind, ZERO)
    key = _key(agent_id, kind, resource)
    if delay <= ZERO:
        _pending_open.pop(key, None)
        return True
    started = _pending_open.get(key)
    observed = _as_utc(observed_at)
    if started is None:
        _pending_open[key] = observed
        return False
    if _elapsed(started, observed) >= delay:
        _pending_open.pop(key, None)
        return True
    return False


def abandon_open_alert(agent_id: str, kind: str, resource: str) -> None:
    _pending_open.pop(_key(agent_id, kind, resource), None)


def should_close_alert(
    agent_id: str,
    kind: str,
    resource: str,
    observed_at: datetime,
) -> bool:
    delay = RECOVER_AFTER.get(kind, ZERO)
    key = _key(agent_id, kind, resource)
    if delay <= ZERO:
        _pending_close.pop(key, None)
        return True
    started = _pending_close.get(key)
    observed = _as_utc(observed_at)
    if started is None:
        _pending_close[key] = observed
        return False
    if _elapsed(started, observed) >= delay:
        _pending_close.pop(key, None)
        return True
    return False


def abandon_close_alert(agent_id: str, kind: str, resource: str) -> None:
    _pending_close.pop(_key(agent_id, kind, resource), None)
