from typing import Literal

Metric = Literal[
    "cpu_percent",
    "memory_percent",
    "disk_percent",
    "temperature_celsius",
    "agent_offline",
]
Operator = Literal[">", ">=", "<", "<=", "==", "!="]
Severity = Literal["critical", "high", "medium", "low"]
AppliesTo = Literal["all", "group", "agent"]

METRICS: tuple[Metric, ...] = (
    "cpu_percent",
    "memory_percent",
    "disk_percent",
    "temperature_celsius",
    "agent_offline",
)
OPERATORS: tuple[Operator, ...] = (">", ">=", "<", "<=", "==", "!=")
SEVERITIES: tuple[Severity, ...] = ("critical", "high", "medium", "low")
APPLIES_TO: tuple[AppliesTo, ...] = ("all", "group", "agent")

METRIC_KIND = {
    "cpu_percent": "cpu_high",
    "memory_percent": "memory_high",
    "disk_percent": "disk_high",
    "temperature_celsius": "temperature_high",
    "agent_offline": "agent_offline",
}
METRIC_LABEL = {
    "cpu_percent": "CPU",
    "memory_percent": "memory",
    "disk_percent": "disk",
    "temperature_celsius": "temperature",
    "agent_offline": "agent offline time",
}
METRIC_UNIT = {
    "cpu_percent": "%",
    "memory_percent": "%",
    "disk_percent": "%",
    "temperature_celsius": "°C",
    "agent_offline": "s",
}
OPERATOR_LABEL = {
    ">": "greater than",
    ">=": "greater than or equal to",
    "<": "less than",
    "<=": "less than or equal to",
    "==": "equal to",
    "!=": "not equal to",
}
SEVERITY_RANK = {
    "critical": 4,
    "high": 3,
    "medium": 2,
    "warning": 2,
    "low": 1,
    "info": 0,
}


def preview_sentence(metric: str, operator: str, threshold: float, severity: str) -> str:
    label = METRIC_LABEL.get(metric, metric)
    comparison = OPERATOR_LABEL.get(operator, operator)
    unit = METRIC_UNIT.get(metric, "")
    amount = f"{threshold:g}{unit}"
    return f"If {label} is {comparison} {amount} create {severity.capitalize()} alert."
