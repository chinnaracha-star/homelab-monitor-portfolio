import asyncio
import inspect
import logging

import pytest
from sqlalchemy.exc import SQLAlchemyError

from homelab_monitor.infrastructure_monitor import run_infrastructure_monitor
from homelab_monitor.jobs.repetition import run_repeated
from homelab_monitor.offline_monitor import run_offline_monitor
from homelab_monitor.photo_watcher import run_photo_watcher
from homelab_monitor.settings import Settings
from homelab_monitor.sqlite_backup import run_sqlite_backup
from homelab_monitor.telegram_reports import run_telegram_reports


def test_repeats_after_return_without_overlap() -> None:
    active = 0
    seen: list[int] = []

    async def operation() -> None:
        nonlocal active
        active += 1
        assert active == 1
        seen.append(active)
        active -= 1
        if len(seen) == 3:
            raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(run_repeated(operation))
    assert seen == [1, 1, 1]


def test_terminal_exception_escapes_without_restart() -> None:
    calls = 0

    async def operation() -> None:
        nonlocal calls
        calls += 1
        raise RuntimeError("stop")

    with pytest.raises(RuntimeError, match="stop"):
        asyncio.run(run_repeated(operation))
    assert calls == 1


def test_adds_no_sleep_and_no_child_task() -> None:
    source = inspect.getsource(run_repeated)
    assert "sleep" not in source
    assert "create_task" not in source

    async def operation() -> None:
        raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(run_repeated(operation))


def test_report_sqlalchemy_error_continues(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    async def clock(settings: Settings) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise SQLAlchemyError("locked")
        raise RuntimeError("next")

    monkeypatch.setattr("homelab_monitor.telegram_reports.run_report_clock", clock)
    with pytest.raises(RuntimeError, match="next"):
        asyncio.run(run_telegram_reports(Settings.model_construct()))
    assert calls == 2


def test_backup_cancel_is_logged(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    async def clock(settings: Settings) -> None:
        raise asyncio.CancelledError

    monkeypatch.setattr("homelab_monitor.sqlite_backup.run_backup_clock", clock)
    with caplog.at_level(logging.INFO), pytest.raises(asyncio.CancelledError):
        asyncio.run(run_sqlite_backup(Settings.model_construct()))
    assert "sqlite_backup_scheduler_cancelled" in caplog.text


def test_five_lifecycles_delegate_repetition() -> None:
    bodies = [
        inspect.getsource(run_offline_monitor),
        inspect.getsource(run_infrastructure_monitor),
        inspect.getsource(run_telegram_reports),
        inspect.getsource(run_photo_watcher),
        inspect.getsource(run_sqlite_backup),
    ]
    for body in bodies:
        assert "while True" not in body
        assert "run_repeated" in body
