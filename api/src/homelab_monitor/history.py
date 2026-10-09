from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from homelab_monitor.models import MetricHistory

HistoryInterval = Literal["1m", "5m", "15m", "1h"]

INTERVAL_SECONDS: dict[HistoryInterval, int] = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "1h": 3600,
}

HISTORY_FIELDS = (
    "cpu_percent",
    "memory_percent",
    "disk_percent",
    "temperature_celsius",
    "network_rx_bytes",
    "network_tx_bytes",
)

CSV_HEADER = ",".join(
    (
        "timestamp",
        *HISTORY_FIELDS,
    )
)


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def extract_system_metrics(payload: dict[str, Any]) -> dict[str, Any]:
    for module in payload.get("modules", []):
        if module.get("module") == "system":
            metrics = module.get("metrics", {})
            if isinstance(metrics, dict):
                return metrics
    return {}


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value)


def _usage_percent(metrics: dict[str, Any], nested_key: str, legacy_key: str) -> float | None:
    nested = metrics.get(nested_key)
    if isinstance(nested, dict):
        value = _number(nested.get("usage_percent"))
        if value is not None:
            return value
    return _number(metrics.get(legacy_key))


def _disk_percent(metrics: dict[str, Any]) -> float | None:
    disks = metrics.get("disks")
    if not isinstance(disks, list):
        return _number(metrics.get("disk_percent"))
    root = None
    highest = None
    for disk in disks:
        if not isinstance(disk, dict):
            continue
        value = _number(disk.get("usage_percent"))
        if value is None:
            continue
        if disk.get("mount_point") == "/":
            root = value
        if highest is None or value > highest:
            highest = value
    return root if root is not None else highest


def _temperature(metrics: dict[str, Any]) -> float | None:
    sensors = metrics.get("temperatures")
    if not isinstance(sensors, list):
        return _number(metrics.get("temperature_celsius"))
    highest = None
    for sensor in sensors:
        if not isinstance(sensor, dict):
            continue
        value = _number(sensor.get("current_celsius"))
        if value is None:
            continue
        if highest is None or value > highest:
            highest = value
    return highest


def _network_bytes(metrics: dict[str, Any], *keys: str) -> float | None:
    network = metrics.get("network")
    if isinstance(network, dict):
        for key in keys:
            value = _number(network.get(key))
            if value is not None:
                return value
    for key in keys:
        value = _number(metrics.get(key))
        if value is not None:
            return value
    return None


def extract_history_fields(payload: dict[str, Any]) -> dict[str, float | None]:
    metrics = extract_system_metrics(payload)
    return {
        "cpu_percent": _usage_percent(metrics, "cpu", "cpu_percent"),
        "memory_percent": _usage_percent(metrics, "memory", "memory_percent"),
        "disk_percent": _disk_percent(metrics),
        "temperature_celsius": _temperature(metrics),
        "network_rx_bytes": _network_bytes(metrics, "rx_bytes", "bytes_recv", "network_rx_bytes"),
        "network_tx_bytes": _network_bytes(metrics, "tx_bytes", "bytes_sent", "network_tx_bytes"),
    }


def record_metric_history(
    db: Session,
    *,
    agent_id: str,
    payload: dict[str, Any],
    observed_at: datetime,
) -> MetricHistory:
    fields = extract_history_fields(payload)
    row = MetricHistory(
        agent_id=agent_id,
        timestamp=as_utc(observed_at),
        **fields,
    )
    db.add(row)
    return row


def _bucket_start(value: datetime, interval_seconds: int) -> datetime:
    epoch = int(as_utc(value).timestamp())
    floored = epoch - (epoch % interval_seconds)
    return datetime.fromtimestamp(floored, UTC)


def _average(values: Sequence[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 4)


def aggregate_history(
    rows: Sequence[MetricHistory],
    interval: HistoryInterval,
) -> list[dict[str, Any]]:
    interval_seconds = INTERVAL_SECONDS[interval]
    buckets: dict[datetime, dict[str, list[float]]] = {}
    for row in rows:
        bucket = _bucket_start(row.timestamp, interval_seconds)
        collected = buckets.setdefault(bucket, {field: [] for field in HISTORY_FIELDS})
        for field in HISTORY_FIELDS:
            value = getattr(row, field)
            if value is not None:
                collected[field].append(float(value))

    points: list[dict[str, Any]] = []
    for timestamp in sorted(buckets):
        collected = buckets[timestamp]
        points.append(
            {
                "timestamp": timestamp,
                **{field: _average(collected[field]) for field in HISTORY_FIELDS},
            }
        )
    return points


def query_history_points(
    db: Session,
    *,
    agent_id: str,
    start: datetime,
    end: datetime,
    interval: HistoryInterval,
) -> list[dict[str, Any]]:
    rows = db.scalars(
        select(MetricHistory)
        .where(
            MetricHistory.agent_id == agent_id,
            MetricHistory.timestamp >= as_utc(start),
            MetricHistory.timestamp <= as_utc(end),
        )
        .order_by(MetricHistory.timestamp.asc())
    ).all()
    return aggregate_history(rows, interval)


def default_history_window(now: datetime | None = None) -> tuple[datetime, datetime]:
    end = as_utc(now or datetime.now(UTC))
    return end - timedelta(hours=24), end


def csv_filename(agent_name: str, generated_at: datetime | None = None) -> str:
    stamp = as_utc(generated_at or datetime.now(UTC)).strftime("%Y%m%d-%H%M")
    slug = "".join(
        character if character.isalnum() or character in "._-" else "-" for character in agent_name
    )
    slug = slug.strip("-") or "agent"
    return f"{slug}-{stamp}.csv"


def render_history_csv(points: Sequence[dict[str, Any]]) -> str:
    lines = [CSV_HEADER]
    for point in points:
        timestamp = as_utc(point["timestamp"]).isoformat()
        cells = [timestamp]
        for field in HISTORY_FIELDS:
            value = point.get(field)
            cells.append("" if value is None else f"{value:g}")
        lines.append(",".join(cells))
    return "\n".join(lines) + "\n"
