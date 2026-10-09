import math
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from homelab_monitor.alert_rules import SEVERITY_RANK
from homelab_monitor.alert_rules.metrics import MetricSample
from homelab_monitor.alert_severity import CRITICAL, WARNING, WARNING_MIN
from homelab_monitor.models import Agent, AgentGroupMember, AlertRule
from homelab_monitor.settings import Settings


@dataclass(frozen=True)
class EvaluatedRule:
    kind: str
    resource: str
    value: float
    threshold: float
    breached: bool
    message: str
    severity: str
    cooldown_seconds: int


@dataclass(frozen=True)
class RuleView:
    metric: str
    operator: str
    threshold: float
    severity: str
    enabled: bool
    cooldown_seconds: int
    applies_to: str
    group_id: str | None
    agent_id: str | None


def compare(operator: str, value: float, threshold: float) -> bool:
    if operator == ">":
        return value > threshold
    if operator == ">=":
        return value >= threshold
    if operator == "<":
        return value < threshold
    if operator == "<=":
        return value <= threshold
    if operator == "==":
        return math.isclose(value, threshold, rel_tol=1e-9, abs_tol=1e-6)
    if operator == "!=":
        return not math.isclose(value, threshold, rel_tol=1e-9, abs_tol=1e-6)
    return False


def _rule(metric: str, threshold: float, severity: str) -> RuleView:
    return RuleView(
        metric=metric,
        operator=">",
        threshold=threshold,
        severity=severity,
        enabled=True,
        cooldown_seconds=0,
        applies_to="all",
        group_id=None,
        agent_id=None,
    )


def fallback_rules(settings: Settings) -> list[RuleView]:
    return [
        _rule("cpu_percent", WARNING_MIN["cpu_percent"], WARNING),
        _rule("cpu_percent", max(settings.alert_cpu_threshold_percent, 90.0), CRITICAL),
        _rule("memory_percent", WARNING_MIN["memory_percent"], WARNING),
        _rule("memory_percent", max(settings.alert_memory_threshold_percent, 90.0), CRITICAL),
        _rule("disk_percent", WARNING_MIN["disk_percent"], WARNING),
        _rule("disk_percent", max(settings.alert_disk_threshold_percent, 90.0), CRITICAL),
        _rule("temperature_celsius", WARNING_MIN["temperature_celsius"], WARNING),
        _rule("temperature_celsius", 75.0, CRITICAL),
        _rule("agent_offline", float(settings.agent_offline_after_seconds), WARNING),
    ]


def load_effective_rules(db: Session, settings: Settings) -> list[RuleView]:
    rows = list(db.scalars(select(AlertRule)).all())
    if not rows:
        return fallback_rules(settings)
    return [
        RuleView(
            metric=row.metric,
            operator=row.operator,
            threshold=row.threshold,
            severity=row.severity,
            enabled=row.enabled,
            cooldown_seconds=row.cooldown_seconds,
            applies_to=row.applies_to,
            group_id=row.group_id,
            agent_id=row.agent_id,
        )
        for row in rows
        if row.enabled
    ]


def agent_group_ids(db: Session, agent_id: str) -> set[str]:
    return set(
        db.scalars(select(AgentGroupMember.group_id).where(AgentGroupMember.agent_id == agent_id))
    )


def rule_applies(rule: RuleView, agent: Agent, group_ids: set[str]) -> bool:
    if not rule.enabled:
        return False
    if rule.applies_to == "all":
        return True
    if rule.applies_to == "group":
        return bool(rule.group_id and rule.group_id in group_ids)
    if rule.applies_to == "agent":
        return rule.agent_id == agent.id
    return False


def _rank(rule: RuleView) -> tuple[int, float]:
    severity = SEVERITY_RANK.get(rule.severity, 0)
    if rule.operator in {">", ">="}:
        return (severity, rule.threshold)
    if rule.operator in {"<", "<="}:
        return (severity, -rule.threshold)
    return (severity, 0.0)


def evaluate_sample(
    sample: MetricSample,
    rules: Sequence[RuleView],
    agent: Agent,
    group_ids: set[str],
) -> EvaluatedRule | None:
    applicable = [
        rule
        for rule in rules
        if rule.metric == sample.metric and rule_applies(rule, agent, group_ids)
    ]
    if not applicable:
        return None
    matched = [rule for rule in applicable if compare(rule.operator, sample.value, rule.threshold)]
    winner = max(matched, key=_rank) if matched else applicable[0]
    breached = winner in matched
    relation = (
        "exceeded"
        if breached and winner.operator in {">", ">="}
        else ("matched" if breached else "is within")
    )
    return EvaluatedRule(
        kind=sample.kind,
        resource=sample.resource,
        value=sample.value,
        threshold=winner.threshold,
        breached=breached,
        message=(
            f"{sample.label} {sample.value:g}{sample.unit} {relation} "
            f"threshold {winner.threshold:g}{sample.unit}"
        ),
        severity=winner.severity,
        cooldown_seconds=winner.cooldown_seconds,
    )


def evaluate_samples(
    samples: Sequence[MetricSample],
    rules: Sequence[RuleView],
    agent: Agent,
    group_ids: set[str],
) -> list[EvaluatedRule]:
    results: list[EvaluatedRule] = []
    for sample in samples:
        evaluated = evaluate_sample(sample, rules, agent, group_ids)
        if evaluated is not None:
            results.append(evaluated)
        else:
            results.append(
                EvaluatedRule(
                    kind=sample.kind,
                    resource=sample.resource,
                    value=sample.value,
                    threshold=sample.value,
                    breached=False,
                    message=f"{sample.label} {sample.value:g}{sample.unit} is within threshold",
                    severity="low",
                    cooldown_seconds=0,
                )
            )
    return results
