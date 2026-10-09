import asyncio
from typing import Any

from homelab_monitor.realtime.events import DashboardEventType, build_event
from homelab_monitor.realtime.manager import HEARTBEAT_INTERVAL_SECONDS, ConnectionManager


class RealtimeHub:
    def __init__(self) -> None:
        self.manager = ConnectionManager()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._heartbeat_task: asyncio.Task[None] | None = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop
        if self._heartbeat_task is None or self._heartbeat_task.done():
            self._heartbeat_task = loop.create_task(self._heartbeat_loop())

    def stop(self) -> None:
        if self._heartbeat_task is not None:
            self._heartbeat_task.cancel()
            self._heartbeat_task = None
        self._loop = None

    def publish(
        self,
        event_type: DashboardEventType,
        *,
        reason: str,
        agent_id: str | None = None,
    ) -> None:
        self._schedule(build_event(event_type, reason=reason, agent_id=agent_id))

    def notify_ingest(
        self,
        *,
        reason: str,
        agent_id: str | None = None,
        alerts_changed: bool = True,
    ) -> None:
        self.publish("overview_updated", reason=reason, agent_id=agent_id)
        self.publish("agent_updated", reason=reason, agent_id=agent_id)
        if alerts_changed:
            self.publish("alert_updated", reason=reason, agent_id=agent_id)

    def _schedule(self, message: dict[str, Any]) -> None:
        loop = self._loop
        if loop is None or loop.is_closed():
            return
        asyncio.run_coroutine_threadsafe(self.manager.broadcast(message), loop)

    async def _heartbeat_loop(self) -> None:
        while True:
            await asyncio.sleep(HEARTBEAT_INTERVAL_SECONDS)
            await self.manager.heartbeat()


hub = RealtimeHub()
