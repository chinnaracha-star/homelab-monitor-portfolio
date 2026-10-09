"""Read-only access to metric_history.

Sprint 13.4 adds this type and does not switch analytics, trends, capacity,
insights, or predictions onto it. Returned values are plain copies.
"""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from homelab_monitor.history import HISTORY_FIELDS, as_utc
from homelab_monitor.models import MetricHistory


@dataclass(frozen=True)
class MetricSample:
    id: str
    agent_id: str
    timestamp: datetime
    cpu_percent: float | None
    memory_percent: float | None
    disk_percent: float | None
    temperature_celsius: float | None
    network_rx_bytes: float | None
    network_tx_bytes: float | None

    def value(self, field: str) -> float | None:
        if field not in HISTORY_FIELDS:
            raise ValueError(f"unknown metric field: {field}")
        raw = getattr(self, field)
        return None if raw is None else float(raw)


def _sample(row: MetricHistory) -> MetricSample:
    return MetricSample(
        id=row.id,
        agent_id=row.agent_id,
        timestamp=as_utc(row.timestamp),
        cpu_percent=None if row.cpu_percent is None else float(row.cpu_percent),
        memory_percent=None if row.memory_percent is None else float(row.memory_percent),
        disk_percent=None if row.disk_percent is None else float(row.disk_percent),
        temperature_celsius=(
            None if row.temperature_celsius is None else float(row.temperature_celsius)
        ),
        network_rx_bytes=None if row.network_rx_bytes is None else float(row.network_rx_bytes),
        network_tx_bytes=None if row.network_tx_bytes is None else float(row.network_tx_bytes),
    )


class MetricRepository:
    """Reads metric rows for the session it is given. Does not cache."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def latest(self, *, agent_id: str | None = None, limit: int = 1) -> list[MetricSample]:
        statement = select(MetricHistory).order_by(MetricHistory.timestamp.desc())
        if agent_id is not None:
            statement = statement.where(MetricHistory.agent_id == agent_id)
        rows = self._db.scalars(statement.limit(limit)).all()
        return [_sample(row) for row in rows]

    def between(
        self,
        *,
        start: datetime,
        end: datetime,
        agent_id: str | None = None,
    ) -> list[MetricSample]:
        statement = (
            select(MetricHistory)
            .where(
                MetricHistory.timestamp >= as_utc(start),
                MetricHistory.timestamp <= as_utc(end),
            )
            .order_by(MetricHistory.timestamp.asc())
        )
        if agent_id is not None:
            statement = statement.where(MetricHistory.agent_id == agent_id)
        return [_sample(row) for row in self._db.scalars(statement).all()]

    def aggregation_input(
        self,
        *,
        start: datetime,
        end: datetime,
        agent_id: str | None = None,
    ) -> list[MetricSample]:
        return self.between(start=start, end=end, agent_id=agent_id)

    def trend_input(
        self,
        *,
        start: datetime,
        end: datetime,
        field: str,
        agent_id: str | None = None,
    ) -> list[tuple[datetime, float]]:
        if field not in HISTORY_FIELDS:
            raise ValueError(f"unknown metric field: {field}")
        points: list[tuple[datetime, float]] = []
        for sample in self.between(start=start, end=end, agent_id=agent_id):
            value = sample.value(field)
            if value is not None:
                points.append((sample.timestamp, value))
        return points
