import asyncio

import pytest
from sqlalchemy.exc import SQLAlchemyError

from homelab_monitor.infrastructure_monitor import (
    run_infrastructure_monitor,
    run_infrastructure_monitor_interval,
)
from homelab_monitor.jobs.engine import default_engine
from homelab_monitor.offline_monitor import run_offline_monitor, run_offline_monitor_interval
from homelab_monitor.operations import factories
from homelab_monitor.settings import Settings

SIX = {
    "offline_monitor",
    "infrastructure_monitor",
    "telegram_reports",
    "notification_worker",
    "photo_watcher",
    "sqlite_backup",
}


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "alert_evaluation_interval_seconds": 30,
        "infrastructure_refresh_seconds": 45,
    }
    values.update(overrides)
    return Settings.model_construct(**values)


def test_registry_stays_six_jobs() -> None:
    names = {job.name for job in default_engine().jobs()}
    assert names == SIX
    assert set(factories(_settings())) == SIX


def test_offline_interval_sleeps_then_evaluates_once() -> None:
    order: list[str] = []

    async def sleep(delay: float) -> None:
        order.append(f"sleep:{delay}")

    def evaluate(settings: Settings) -> None:
        order.append(f"evaluate:{settings.alert_evaluation_interval_seconds}")

    asyncio.run(
        run_offline_monitor_interval(
            _settings(alert_evaluation_interval_seconds=12),
            sleep=sleep,
            evaluate=evaluate,
        )
    )
    assert order == ["sleep:12", "evaluate:12"]


def test_offline_cancel_during_sleep_skips_evaluation() -> None:
    evaluated: list[str] = []

    async def sleep(delay: float) -> None:
        raise asyncio.CancelledError

    def evaluate(settings: Settings) -> None:
        evaluated.append("ran")

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(run_offline_monitor_interval(_settings(), sleep=sleep, evaluate=evaluate))
    assert evaluated == []


def test_offline_sqlalchemy_error_is_contained() -> None:
    def evaluate(settings: Settings) -> None:
        raise SQLAlchemyError("locked")

    asyncio.run(run_offline_monitor_interval(_settings(), sleep=_asleep, evaluate=evaluate))


def test_offline_unexpected_error_escapes() -> None:
    def evaluate(settings: Settings) -> None:
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        asyncio.run(run_offline_monitor_interval(_settings(), sleep=_asleep, evaluate=evaluate))


def test_offline_lifecycle_repeats_until_cancel(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []

    async def helper(settings: Settings) -> None:
        calls.append(1)
        if len(calls) == 2:
            raise asyncio.CancelledError

    monkeypatch.setattr(
        "homelab_monitor.offline_monitor.run_offline_monitor_interval",
        helper,
    )
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(run_offline_monitor(_settings()))
    assert calls == [1, 1]


def test_offline_lifecycle_stops_on_unexpected_error(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []

    async def helper(settings: Settings) -> None:
        calls.append(1)
        raise RuntimeError("boom")

    monkeypatch.setattr(
        "homelab_monitor.offline_monitor.run_offline_monitor_interval",
        helper,
    )
    with pytest.raises(RuntimeError, match="boom"):
        asyncio.run(run_offline_monitor(_settings()))
    assert calls == [1]


def test_infrastructure_interval_sleeps_then_refreshes_once() -> None:
    order: list[str] = []

    async def sleep(delay: float) -> None:
        order.append(f"sleep:{delay}")

    def refresh() -> None:
        order.append("refresh")

    asyncio.run(
        run_infrastructure_monitor_interval(
            _settings(infrastructure_refresh_seconds=17),
            sleep=sleep,
            refresh=refresh,
        )
    )
    assert order == ["sleep:17", "refresh"]


def test_infrastructure_cancel_during_sleep_skips_refresh() -> None:
    refreshed: list[str] = []

    async def sleep(delay: float) -> None:
        raise asyncio.CancelledError

    def refresh() -> None:
        refreshed.append("ran")

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(run_infrastructure_monitor_interval(_settings(), sleep=sleep, refresh=refresh))
    assert refreshed == []


def test_infrastructure_exception_is_contained() -> None:
    def refresh() -> None:
        raise RuntimeError("qnap down")

    asyncio.run(run_infrastructure_monitor_interval(_settings(), sleep=_asleep, refresh=refresh))


def test_infrastructure_lifecycle_repeats_until_cancel(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []

    async def helper(settings: Settings) -> None:
        calls.append(1)
        if len(calls) == 2:
            raise asyncio.CancelledError

    monkeypatch.setattr(
        "homelab_monitor.infrastructure_monitor.run_infrastructure_monitor_interval",
        helper,
    )
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(run_infrastructure_monitor(_settings()))
    assert calls == [1, 1]


def test_infrastructure_lifecycle_stops_when_helper_raises_cancel_only_after_return(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[int] = []

    async def helper(settings: Settings) -> None:
        calls.append(1)
        raise RuntimeError("refresh escaped")

    monkeypatch.setattr(
        "homelab_monitor.infrastructure_monitor.run_infrastructure_monitor_interval",
        helper,
    )
    with pytest.raises(RuntimeError, match="refresh escaped"):
        asyncio.run(run_infrastructure_monitor(_settings()))
    assert calls == [1]


async def _asleep(delay: float) -> None:
    return None
