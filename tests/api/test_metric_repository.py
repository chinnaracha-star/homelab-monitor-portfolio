from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from homelab_monitor.database import get_engine
from homelab_monitor.metrics.repository import MetricRepository, MetricSample
from homelab_monitor.models import Agent, MetricHistory


def test_metric_repository_returns_plain_samples() -> None:
    now = datetime.now(UTC)
    earlier = now - timedelta(hours=2)
    with Session(get_engine()) as db:
        agent = Agent(
            name="metric-repo",
            hostname="metric-repo",
            version="0",
            token_hash="metric-repo-token",
        )
        db.add(agent)
        db.flush()
        db.add_all(
            [
                MetricHistory(agent_id=agent.id, timestamp=earlier, cpu_percent=10),
                MetricHistory(agent_id=agent.id, timestamp=now, cpu_percent=40, memory_percent=7),
            ]
        )
        db.commit()
        repo = MetricRepository(db)
        latest = repo.latest(agent_id=agent.id, limit=1)
        window = repo.between(start=earlier, end=now, agent_id=agent.id)
        trend = repo.trend_input(start=earlier, end=now, field="cpu_percent", agent_id=agent.id)
        aggregated = repo.aggregation_input(start=earlier, end=now, agent_id=agent.id)

    assert all(isinstance(item, MetricSample) for item in latest + window)
    assert latest[0].cpu_percent == 40.0
    assert [value for _, value in trend] == [10.0, 40.0]
    assert aggregated == window
