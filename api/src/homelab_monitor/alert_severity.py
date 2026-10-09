from __future__ import annotations

INFO = "info"
WARNING = "warning"
CRITICAL = "critical"

KIND_METRIC = {
    "cpu_high": "cpu_percent",
    "memory_high": "memory_percent",
    "disk_high": "disk_percent",
    "temperature_high": "temperature_celsius",
}

WARNING_MIN = {
    "cpu_percent": 70.0,
    "memory_percent": 80.0,
    "disk_percent": 80.0,
    "temperature_celsius": 60.0,
}
CRITICAL_AFTER = {
    "cpu_percent": 90.0,
    "memory_percent": 90.0,
    "disk_percent": 90.0,
    "temperature_celsius": 75.0,
}


def classify_metric_severity(metric: str, value: float) -> str | None:
    warning_min = WARNING_MIN.get(metric)
    critical_after = CRITICAL_AFTER.get(metric)
    if warning_min is None or critical_after is None:
        return None
    if value > critical_after:
        return CRITICAL
    if value >= warning_min:
        return WARNING
    return INFO


def classify_kind_severity(kind: str, value: float | None) -> str | None:
    metric = KIND_METRIC.get(kind)
    if metric is None or value is None:
        return None
    return classify_metric_severity(metric, value)


def normalize_severity(value: str | None) -> str:
    rank = (value or WARNING).lower()
    if rank == CRITICAL:
        return CRITICAL
    if rank in {WARNING, "high", "medium"}:
        return WARNING
    if rank in {INFO, "low"}:
        return INFO
    return WARNING


def alert_payload_severity(kind: str, value: float | None, fallback: str | None = None) -> str:
    classified = classify_kind_severity(kind, value)
    if classified is not None:
        return classified
    return normalize_severity(fallback)


def dashboard_health_status(severities: list[str], score: float | None) -> str:
    ranks = {item.lower() for item in severities}
    if CRITICAL in ranks:
        return "Critical"
    if WARNING in ranks:
        return "Warning"
    if score is not None and score >= 90:
        return "Excellent"
    return "Good"


def telegram_alert_line(kind: str, severity: str, value: float | None) -> str:
    amount = None if value is None else round(value)
    if kind == "cpu_high":
        if severity == CRITICAL:
            return f"CPU above {amount}%" if amount is not None else "CPU above 95%"
        return "High CPU Usage"
    if kind == "disk_high":
        if severity == CRITICAL:
            return f"Storage above {amount}%" if amount is not None else "Storage above 90%"
        return "Storage above 80%"
    if kind == "temperature_high":
        if severity == CRITICAL:
            return (
                f"Temperature above {amount}°C" if amount is not None else "Temperature above 80°C"
            )
        return "High temperature"
    if kind == "memory_high":
        if severity == CRITICAL:
            return f"Memory above {amount}%" if amount is not None else "Memory above 90%"
        return "High memory usage"
    if kind == "agent_offline":
        return "Agent Offline"
    return kind.replace("_", " ").title()
