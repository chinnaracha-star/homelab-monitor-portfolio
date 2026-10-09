"""Repeat one already-timed operation. Does not sleep, catch, or start tasks."""

from collections.abc import Awaitable, Callable


async def run_repeated(operation: Callable[[], Awaitable[None]]) -> None:
    while True:
        await operation()
