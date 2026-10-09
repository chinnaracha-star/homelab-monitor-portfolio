from dataclasses import dataclass
from typing import Any

from homelab_monitor.alert_rules import METRIC_KIND, METRIC_UNIT


@dataclass(frozen=True)
class MetricSample:
    metric: str
    kind: str
    resource: str
    value: float
    label: str
    unit: str


def extract_system_samples(payload: dict[str, Any]) -> list[MetricSample]:
    samples: list[MetricSample] = []
    for module in payload.get("modules", []):
        if module.get("module") != "system":
            continue
        metrics = module.get("metrics", {})
        samples.extend(_cpu_memory(metrics))
        samples.extend(_disks(metrics))
        samples.extend(_temperatures(metrics))
    return samples


def offline_sample(elapsed_seconds: float, agent_name: str) -> MetricSample:
    return MetricSample(
        metric="agent_offline",
        kind=METRIC_KIND["agent_offline"],
        resource="agent",
        value=max(0.0, elapsed_seconds),
        label=f"Agent {agent_name} offline time",
        unit=METRIC_UNIT["agent_offline"],
    )


def _cpu_memory(metrics: dict[str, Any]) -> list[MetricSample]:
    samples: list[MetricSample] = []
    cpu = _usage_value(metrics, "cpu", "cpu_percent")
    if cpu is not None:
        samples.append(_sample("cpu_percent", "system", cpu, "CPU usage"))
    memory = _usage_value(metrics, "memory", "memory_percent")
    if memory is not None:
        samples.append(_sample("memory_percent", "system", memory, "Memory usage"))
    return samples


def _disks(metrics: dict[str, Any]) -> list[MetricSample]:
    samples: list[MetricSample] = []
    for disk in metrics.get("disks", []):
        value = _number(disk.get("usage_percent"))
        resource = str(disk.get("mount_point") or disk.get("filesystem") or "unknown")
        if value is not None:
            samples.append(_sample("disk_percent", resource, value, f"Disk usage on {resource}"))
    return samples


def _temperatures(metrics: dict[str, Any]) -> list[MetricSample]:
    samples: list[MetricSample] = []
    for sensor in metrics.get("temperatures", []):
        value = _number(sensor.get("current_celsius"))
        source = str(sensor.get("source") or "sensor")
        label = str(sensor.get("label") or source)
        if value is not None:
            samples.append(
                _sample(
                    "temperature_celsius",
                    f"{source}:{label}",
                    value,
                    f"Temperature for {label}",
                )
            )
    return samples


def _sample(metric: str, resource: str, value: float, label: str) -> MetricSample:
    return MetricSample(
        metric=metric,
        kind=METRIC_KIND[metric],
        resource=resource,
        value=value,
        label=label,
        unit=METRIC_UNIT[metric],
    )


def _usage_value(metrics: dict[str, Any], nested_key: str, legacy_key: str) -> float | None:
    nested = metrics.get(nested_key)
    if isinstance(nested, dict):
        value = _number(nested.get("usage_percent"))
        if value is not None:
            return value
    return _number(metrics.get(legacy_key))


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value)
