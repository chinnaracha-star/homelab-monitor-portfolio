import asyncio
import logging
from collections.abc import Awaitable, Callable

from homelab_monitor.infrastructure import get_infrastructure_service
from homelab_monitor.jobs.repetition import run_repeated
from homelab_monitor.ops_history import record_backup_snapshot, record_photo_snapshot
from homelab_monitor.photo_stats import build_photo_stats
from homelab_monitor.realtime import hub
from homelab_monitor.settings import Settings, get_settings
from homelab_monitor.sqlite_diagnostics import writer_operation

logger = logging.getLogger("homelab_monitor.infrastructure")


async def run_infrastructure_monitor_interval(
    settings: Settings,
    *,
    sleep: Callable[[float], Awaitable[None]] | None = None,
    refresh: Callable[[], None] | None = None,
) -> None:
    """One infrastructure pass: sleep, then refresh. Does not loop."""
    sleeper = asyncio.sleep if sleep is None else sleep
    operation = refresh_infrastructure if refresh is None else refresh
    await sleeper(settings.infrastructure_refresh_seconds)
    try:
        await asyncio.to_thread(operation)
    except Exception:
        logger.exception("infrastructure_refresh_failed")


async def run_infrastructure_monitor(settings: Settings) -> None:
    await run_repeated(lambda: run_infrastructure_monitor_interval(settings))


def refresh_infrastructure() -> None:
    service = get_infrastructure_service()
    snapshots = service.refresh()
    by_name = {item.service: item for item in snapshots}
    with writer_operation("infrastructure_snapshot"):
        if not get_settings().infrastructure_mock:
            record_photo_snapshot(build_photo_stats(by_name))
        backup = by_name.get("backup")
        if backup is not None:
            record_backup_snapshot(backup)
    qnap = by_name.get("qnap")
    if qnap is not None:
        try:
            from homelab_monitor.qnap_disks import sync_qnap_disk_alerts

            sync_qnap_disk_alerts(qnap.summary)
        except Exception:
            logger.exception("qnap_disk_alerts_failed")
    hub.publish("overview_updated", reason="photo_services_updated")
    hub.publish("overview_updated", reason="backup_updated")
