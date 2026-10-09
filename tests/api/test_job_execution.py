import asyncio
from contextlib import suppress

import pytest

import homelab_monitor.runtime_control as runtime_control
from homelab_monitor.jobs.engine import default_engine
from homelab_monitor.jobs.execution import JobExecutionWrapper
from homelab_monitor.main import app, lifespan
from homelab_monitor.operations import factories
from homelab_monitor.realtime import hub
from homelab_monitor.runtime_control import list_background, register_background, restart_background
from homelab_monitor.settings import get_settings


def test_six_executable_jobs_match_registry() -> None:
    names = set(factories(get_settings()))
    assert names == {job.name for job in default_engine().jobs()}
    assert names == {
        "offline_monitor",
        "infrastructure_monitor",
        "telegram_reports",
        "notification_worker",
        "photo_watcher",
        "sqlite_backup",
    }


def _use_idle_factories(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "homelab_monitor.jobs.execution.factories",
        lambda _settings: _idle_factories(),
    )


def _idle_factories() -> dict:
    def make(name: str):
        async def _run() -> None:
            await asyncio.Event().wait()

        _run.__name__ = name
        return _run

    return {job.name: make(job.name) for job in default_engine().jobs()}


async def _clear_background() -> None:
    for task in list(runtime_control._tasks.values()):
        if not task.done():
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
    runtime_control._tasks.clear()
    runtime_control._factories.clear()


def test_start_registers_each_factory_once(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    real = register_background

    def spy(name: str, factory):
        calls.append(name)
        return real(name, factory)

    monkeypatch.setattr("homelab_monitor.jobs.execution.register_background", spy)
    _use_idle_factories(monkeypatch)

    async def scenario() -> None:
        wrapper = JobExecutionWrapper()
        wrapper.start(get_settings())
        assert calls == list(_idle_factories())
        assert set(list_background()) == set(calls)
        await wrapper.stop()
        await _clear_background()

    asyncio.run(scenario())


def test_duplicate_start_does_not_create_more_tasks(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    real = register_background

    def spy(name: str, factory):
        calls.append(name)
        return real(name, factory)

    monkeypatch.setattr("homelab_monitor.jobs.execution.register_background", spy)
    _use_idle_factories(monkeypatch)

    async def scenario() -> None:
        wrapper = JobExecutionWrapper()
        wrapper.start(get_settings())
        wrapper.start(get_settings())
        assert len(calls) == 6
        await wrapper.stop()
        await _clear_background()

    asyncio.run(scenario())


def test_stop_cancels_and_awaits_managed_tasks(monkeypatch: pytest.MonkeyPatch) -> None:
    _use_idle_factories(monkeypatch)

    async def scenario() -> None:
        wrapper = JobExecutionWrapper()
        wrapper.start(get_settings())
        tasks = list(runtime_control._tasks.values())
        await wrapper.stop()
        assert tasks
        assert all(task.cancelled() for task in tasks)
        await wrapper.stop()
        await _clear_background()

    asyncio.run(scenario())


def test_stop_before_start_is_safe() -> None:
    async def scenario() -> None:
        await JobExecutionWrapper().stop()

    asyncio.run(scenario())


def test_finished_task_is_not_revived(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    real = register_background

    def spy(name: str, factory):
        calls.append(name)
        return real(name, factory)

    async def finished() -> None:
        return None

    monkeypatch.setattr("homelab_monitor.jobs.execution.register_background", spy)
    monkeypatch.setattr(
        "homelab_monitor.jobs.execution.factories",
        lambda _settings: {name: finished for name in _idle_factories()},
    )

    async def scenario() -> None:
        wrapper = JobExecutionWrapper()
        wrapper.start(get_settings())
        await asyncio.sleep(0)
        assert all(task.done() for task in runtime_control._tasks.values())
        wrapper.start(get_settings())
        assert len(calls) == 6
        await wrapper.stop()
        await _clear_background()

    asyncio.run(scenario())


def test_partial_start_does_not_cancel_earlier_tasks(monkeypatch: pytest.MonkeyPatch) -> None:
    created: list[asyncio.Task] = []
    real = register_background

    def flaky(name: str, factory):
        if name == "telegram_reports":
            raise RuntimeError("registration failed")
        task = real(name, factory)
        created.append(task)
        return task

    monkeypatch.setattr("homelab_monitor.jobs.execution.register_background", flaky)
    _use_idle_factories(monkeypatch)

    async def scenario() -> None:
        wrapper = JobExecutionWrapper()
        with pytest.raises(RuntimeError, match="registration failed"):
            wrapper.start(get_settings())
        assert created
        assert all(not task.cancelled() for task in created)
        await wrapper.stop()
        assert all(not task.cancelled() for task in created)
        for task in created:
            task.cancel()
        await _clear_background()

    asyncio.run(scenario())


def test_one_task_failure_does_not_cancel_another(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fail() -> None:
        raise RuntimeError("job failed")

    async def stay() -> None:
        await asyncio.Event().wait()

    names = [job.name for job in default_engine().jobs()]

    def mapped(_settings):
        jobs = {}
        for index, name in enumerate(names):
            jobs[name] = fail if index == 0 else stay
        return jobs

    monkeypatch.setattr("homelab_monitor.jobs.execution.factories", mapped)

    async def scenario() -> None:
        wrapper = JobExecutionWrapper()
        wrapper.start(get_settings())
        await asyncio.sleep(0)
        failed = runtime_control._tasks[names[0]]
        others = [runtime_control._tasks[name] for name in names[1:]]
        assert failed.done()
        assert all(not task.cancelled() and not task.done() for task in others)
        with suppress(RuntimeError):
            await wrapper.stop()
        assert all(task.cancelled() for task in others)
        await _clear_background()

    asyncio.run(scenario())


def test_restart_background_still_replaces_one_named_task(monkeypatch: pytest.MonkeyPatch) -> None:
    _use_idle_factories(monkeypatch)

    async def scenario() -> None:
        wrapper = JobExecutionWrapper()
        wrapper.start(get_settings())
        original = runtime_control._tasks["sqlite_backup"]
        await restart_background("sqlite_backup")
        replacement = runtime_control._tasks["sqlite_backup"]
        assert replacement is not original
        assert original.cancelled()
        assert not replacement.done()
        replacement.cancel()
        with suppress(asyncio.CancelledError):
            await replacement
        await wrapper.stop()
        await _clear_background()

    asyncio.run(scenario())


def test_stop_cancels_task_replaced_by_restart_background(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _use_idle_factories(monkeypatch)

    async def scenario() -> None:
        wrapper = JobExecutionWrapper()
        wrapper.start(get_settings())
        original = runtime_control._tasks["photo_watcher"]
        await restart_background("photo_watcher")
        replacement = runtime_control._tasks["photo_watcher"]
        assert replacement is not original
        await wrapper.stop()
        assert original.cancelled()
        assert replacement.cancelled()
        await _clear_background()

    asyncio.run(scenario())


def test_lifespan_stops_hub_before_background_jobs(monkeypatch: pytest.MonkeyPatch) -> None:
    order: list[str] = []

    def stop_hub() -> None:
        order.append("hub")

    async def stop_jobs(self) -> None:
        order.append("jobs")

    monkeypatch.setattr(hub, "stop", stop_hub)
    monkeypatch.setattr(JobExecutionWrapper, "start", lambda self, settings: None)
    monkeypatch.setattr(JobExecutionWrapper, "stop", stop_jobs)

    async def scenario() -> None:
        async with lifespan(app):
            assert order == []
        assert order == ["hub", "jobs"]

    asyncio.run(scenario())


def test_lifespan_starts_and_stops_wrapper_once(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"start": 0, "stop": 0}

    def start(self, settings) -> None:
        calls["start"] += 1

    async def stop(self) -> None:
        calls["stop"] += 1

    monkeypatch.setattr(JobExecutionWrapper, "start", start)
    monkeypatch.setattr(JobExecutionWrapper, "stop", stop)

    async def scenario() -> None:
        async with lifespan(app):
            assert calls == {"start": 1, "stop": 0}
        assert calls == {"start": 1, "stop": 1}

    asyncio.run(scenario())
