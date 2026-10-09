import asyncio
import logging
from collections.abc import Awaitable, Callable

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from homelab_monitor.alert_engine import AlertEngine
from homelab_monitor.database import get_engine
from homelab_monitor.jobs.repetition import run_repeated
from homelab_monitor.realtime import hub
from homelab_monitor.settings import Settings
from homelab_monitor.sqlite_diagnostics import writer_operation

logger = logging.getLogger("homelab_monitor.offline_monitor")


async def run_offline_monitor_interval(
    settings: Settings,
    *,
    sleep: Callable[[float], Awaitable[None]] | None = None,
    evaluate: Callable[[Settings], None] | None = None,
) -> None:
    """One offline-monitor pass: sleep, then evaluate. Does not loop."""
    sleeper = asyncio.sleep if sleep is None else sleep
    operation = evaluate_offline_agents if evaluate is None else evaluate
    await sleeper(settings.alert_evaluation_interval_seconds)
    try:
        await asyncio.to_thread(operation, settings)
    except SQLAlchemyError:
        logger.exception("offline_evaluation_failed")


async def run_offline_monitor(settings: Settings) -> None:
    await run_repeated(lambda: run_offline_monitor_interval(settings))


def evaluate_offline_agents(settings: Settings) -> None:
    with writer_operation("offline_alert_update"), Session(get_engine()) as db:
        events, status_changed = AlertEngine(settings).evaluate_offline_agents(db)
        db.commit()
    if events or status_changed:
        hub.notify_ingest(reason="offline_evaluation", agent_id=None)
