from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Coroutine
from contextlib import suppress
from typing import Any

logger = logging.getLogger("homelab_monitor.runtime_control")

_tasks: dict[str, asyncio.Task[Any]] = {}
_factories: dict[str, Callable[[], Coroutine[Any, Any, None]]] = {}


def register_background(
    name: str, factory: Callable[[], Coroutine[Any, Any, None]]
) -> asyncio.Task[Any]:
    _factories[name] = factory
    task = asyncio.create_task(factory(), name=name)
    _tasks[name] = task
    return task


async def restart_background(name: str) -> None:
    task = _tasks.get(name)
    factory = _factories.get(name)
    if factory is None:
        raise RuntimeError(f"unknown background task {name}")
    if task is not None and not task.done():
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
    _tasks[name] = asyncio.create_task(factory(), name=name)
    logger.info("background_restarted name=%s", name)


def list_background() -> list[str]:
    return sorted(_factories)
