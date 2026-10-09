import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from homelab_monitor.agent_presence import latest_report_time, presence_of
from homelab_monitor.alert_rules.evaluate import (
    agent_group_ids,
    evaluate_samples,
    load_effective_rules,
)
from homelab_monitor.alert_rules.metrics import extract_system_samples, offline_sample
from homelab_monitor.alert_severity import alert_payload_severity
from homelab_monitor.alert_stability import (
    abandon_close_alert,
    abandon_open_alert,
    should_close_alert,
    should_open_alert,
)
from homelab_monitor.models import Agent, Alert
from homelab_monitor.settings import Settings

logger = logging.getLogger("homelab_monitor.alerts")


@dataclass(frozen=True)
class AlertEvent:
    agent_id: str
    agent_name: str
    kind: str
    resource: str
    value: float
    threshold: float
    message: str
    observed_at: datetime
    transition: str = "activated"
    started_at: datetime | None = None
    recovered_at: datetime | None = None
    duration_seconds: int | None = None


def as_alert_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def alert_duration_seconds(
    started_at: datetime | None,
    recovered_at: datetime | None,
    now: datetime,
    *,
    recovered: bool,
) -> int | None:
    if started_at is None:
        return None
    end = recovered_at if recovered and recovered_at is not None else now
    return max(0, int((as_alert_utc(end) - as_alert_utc(started_at)).total_seconds()))


class AlertEngine:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def evaluate_report(
        self,
        db: Session,
        agent: Agent,
        payload: dict[str, Any],
        observed_at: datetime,
    ) -> list[AlertEvent]:
        samples = extract_system_samples(payload)
        if not samples:
            return []
        rules = load_effective_rules(db, self.settings)
        group_ids = agent_group_ids(db, agent.id)
        events: list[AlertEvent] = []
        for evaluated in evaluate_samples(samples, rules, agent, group_ids):
            event = self._set_threshold_state(
                db,
                agent,
                kind=evaluated.kind,
                resource=evaluated.resource,
                value=evaluated.value,
                threshold=evaluated.threshold,
                breached=evaluated.breached,
                observed_at=observed_at,
                message=evaluated.message,
                severity=alert_payload_severity(
                    evaluated.kind, evaluated.value, evaluated.severity
                ),
                cooldown_seconds=evaluated.cooldown_seconds,
            )
            if event is not None:
                events.append(event)
        self._enqueue_notifications(events)
        return events

    def mark_agent_online(
        self, db: Session, agent: Agent, observed_at: datetime
    ) -> AlertEvent | None:
        event = self._set_threshold_state(
            db,
            agent,
            kind="agent_offline",
            resource="agent",
            value=0,
            threshold=float(self.settings.agent_offline_after_seconds),
            breached=False,
            observed_at=observed_at,
            message=f"Agent {agent.name} is online",
        )
        if event is not None:
            self._enqueue_notifications([event])
        return event

    def evaluate_offline_agents(
        self,
        db: Session,
        now: datetime | None = None,
    ) -> tuple[list[AlertEvent], bool]:
        observed_at = now or datetime.now(UTC)
        events: list[AlertEvent] = []
        status_changed = False
        timeout = self.settings.agent_offline_after_seconds
        rules = load_effective_rules(db, self.settings)
        for agent in db.scalars(select(Agent)).all():
            db.expire(agent)
            db.refresh(agent)
            presence = presence_of(
                agent.last_seen_at,
                latest_report_time(db, agent.id),
                now=observed_at,
                timeout_seconds=timeout,
            )
            if presence.contact_at is None:
                continue
            elapsed = (observed_at - self._as_utc(presence.contact_at)).total_seconds()
            group_ids = agent_group_ids(db, agent.id)
            evaluated_list = evaluate_samples(
                [offline_sample(elapsed, agent.name)],
                rules,
                agent,
                group_ids,
            )
            evaluated = evaluated_list[0]
            offline = presence.status == "offline"
            if offline:
                if agent.status != "offline":
                    status_changed = True
                agent.status = "offline"
            else:
                if agent.status != "online":
                    status_changed = True
                agent.status = "online"
            message = (
                f"Agent {agent.name} has been offline for {int(max(0, elapsed))} seconds"
                if offline
                else f"Agent {agent.name} is online"
            )
            event = self._set_threshold_state(
                db,
                agent,
                kind="agent_offline",
                resource="agent",
                value=max(0, elapsed),
                threshold=evaluated.threshold,
                breached=offline,
                observed_at=observed_at,
                message=message,
                severity=alert_payload_severity(
                    "agent_offline", max(0, elapsed), evaluated.severity
                ),
                cooldown_seconds=evaluated.cooldown_seconds,
            )
            if event is not None:
                events.append(event)
        self._enqueue_notifications(events)
        return events, status_changed

    @staticmethod
    def _enqueue_notifications(events: list[AlertEvent]) -> None:
        if not events:
            return
        from homelab_monitor.notification_queue import enqueue_alert_events

        enqueue_alert_events(events)

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    @staticmethod
    def _set_threshold_state(
        db: Session,
        agent: Agent,
        *,
        kind: str,
        resource: str,
        value: float,
        threshold: float,
        breached: bool,
        observed_at: datetime,
        message: str,
        severity: str = "warning",
        cooldown_seconds: int = 0,
    ) -> AlertEvent | None:
        alert = db.scalar(
            select(Alert).where(
                Alert.agent_id == agent.id,
                Alert.kind == kind,
                Alert.resource == resource,
            )
        )
        if breached:
            abandon_close_alert(agent.id, kind, resource)
            if alert is None:
                if not should_open_alert(agent.id, kind, resource, observed_at):
                    return None
                alert = Alert(
                    agent_id=agent.id,
                    kind=kind,
                    resource=resource,
                    status="active",
                    severity=severity,
                    current_value=value,
                    threshold=threshold,
                    message=message,
                    opened_at=observed_at,
                    last_observed_at=observed_at,
                )
                db.add(alert)
                logger.warning(
                    "alert_opened",
                    extra={"agent_id": agent.id, "kind": kind, "resource": resource},
                )
                return AlertEngine._lifecycle_event(
                    agent,
                    alert,
                    kind=kind,
                    resource=resource,
                    value=value,
                    threshold=threshold,
                    message=message,
                    observed_at=observed_at,
                    transition="activated",
                )
            if alert.status == "resolved":
                resolved_at = alert.resolved_at
                if (
                    cooldown_seconds > 0
                    and resolved_at is not None
                    and (observed_at - AlertEngine._as_utc(resolved_at)).total_seconds()
                    < cooldown_seconds
                ):
                    return None
                if not should_open_alert(agent.id, kind, resource, observed_at):
                    return None
                alert.status = "active"
                alert.severity = severity
                alert.opened_at = observed_at
                alert.resolved_at = None
                logger.warning(
                    "alert_reopened",
                    extra={"agent_id": agent.id, "kind": kind, "resource": resource},
                )
                event = AlertEngine._lifecycle_event(
                    agent,
                    alert,
                    kind=kind,
                    resource=resource,
                    value=value,
                    threshold=threshold,
                    message=message,
                    observed_at=observed_at,
                    transition="activated",
                )
            else:
                event = None
            alert.current_value = value
            alert.threshold = threshold
            alert.message = message
            alert.severity = severity
            alert.last_observed_at = observed_at
            return event

        abandon_open_alert(agent.id, kind, resource)
        if alert is not None and alert.status == "active":
            if not should_close_alert(agent.id, kind, resource, observed_at):
                alert.current_value = value
                alert.threshold = threshold
                alert.message = message
                alert.last_observed_at = observed_at
                return None
            alert.status = "resolved"
            alert.current_value = value
            alert.threshold = threshold
            alert.message = message
            alert.last_observed_at = observed_at
            alert.resolved_at = observed_at
            logger.info(
                "alert_resolved",
                extra={"agent_id": agent.id, "kind": kind, "resource": resource},
            )
            return AlertEngine._lifecycle_event(
                agent,
                alert,
                kind=kind,
                resource=resource,
                value=value,
                threshold=threshold,
                message=message,
                observed_at=observed_at,
                transition="recovered",
            )
        return None

    @staticmethod
    def _lifecycle_event(
        agent: Agent,
        alert: Alert,
        *,
        kind: str,
        resource: str,
        value: float,
        threshold: float,
        message: str,
        observed_at: datetime,
        transition: str,
    ) -> AlertEvent:
        recovered = transition == "recovered"
        started_at = alert.opened_at
        recovered_at = alert.resolved_at if recovered else None
        return AlertEvent(
            agent_id=agent.id,
            agent_name=agent.name,
            kind=kind,
            resource=resource,
            value=value,
            threshold=threshold,
            message=message,
            observed_at=observed_at,
            transition=transition,
            started_at=started_at,
            recovered_at=recovered_at,
            duration_seconds=alert_duration_seconds(
                started_at,
                recovered_at,
                observed_at,
                recovered=recovered,
            ),
        )
