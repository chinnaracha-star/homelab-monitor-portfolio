"""Start and stop the six existing background jobs.

Phase 13.12 owns task lifecycle only. Sleep intervals, loop bodies, and
notification paths stay in the current job modules.
"""

from __future__ import annotations

import asyncio

import homelab_monitor.runtime_control as runtime_control
from homelab_monitor.jobs.engine import default_engine
from homelab_monitor.operations import factories
from homelab_monitor.runtime_control import register_background
from homelab_monitor.settings import Settings


class JobExecutionWrapper:
    """Creates the existing factory tasks and cancels that set on stop.

    A later ``restart_background`` replaces the task stored here. Shutdown
    also cancels that replacement so the named job does not keep running.
    """

    def __init__(self) -> None:
        self._tasks: list[asyncio.Task[None]] = []
        self._names: tuple[str, ...] = ()
        self._started = False

    def start(self, settings: Settings) -> None:
        if self._started:
            return
        executable = factories(settings)
        registered = {job.name for job in default_engine().jobs()}
        if set(executable) != registered:
            raise RuntimeError("job factories do not match the job registry")
        created: list[asyncio.Task[None]] = []
        for name, factory in executable.items():
            created.append(register_background(name, factory))
        self._tasks = created
        self._names = tuple(executable)
        self._started = True

    async def stop(self) -> None:
        if not self._started:
            return
        managed = list(self._tasks)
        for name in self._names:
            current = runtime_control._tasks.get(name)
            if current is not None and current not in managed:
                managed.append(current)
        self._tasks = []
        self._names = ()
        self._started = False
        for task in managed:
            task.cancel()
        errors: list[BaseException] = []
        for task in managed:
            try:
                await task
            except asyncio.CancelledError:
                continue
            except Exception as exc:
                errors.append(exc)
        if errors:
            raise errors[0]
