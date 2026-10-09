import asyncio
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from homelab_monitor.jobs.engine import default_engine
from homelab_monitor.operations import factories
from homelab_monitor.photo_watcher import ALLOWED_INTERVALS
from homelab_monitor.settings import Settings, get_settings
from homelab_monitor.sqlite_backup import next_scheduled, run_backup_clock, run_backup_once
from homelab_monitor.telegram_reports import TICK_SECONDS

BANGKOK = ZoneInfo("Asia/Bangkok")
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
        "backup_enabled": True,
        "backup_time": "02:00",
        "backup_timezone": "Asia/Bangkok",
    }
    values.update(overrides)
    return Settings.model_construct(**values)


def test_before_candidate_stays_today() -> None:
    now = datetime(2026, 9, 28, 1, 0, tzinfo=BANGKOK)
    nxt = next_scheduled(_settings(), now=now)
    assert nxt == datetime(2026, 9, 28, 2, 0, tzinfo=BANGKOK)
    assert nxt.second == 0
    assert nxt.microsecond == 0


def test_exact_candidate_moves_to_next_day() -> None:
    now = datetime(2026, 9, 28, 2, 0, 0, 0, tzinfo=BANGKOK)
    nxt = next_scheduled(_settings(), now=now)
    assert nxt == now + timedelta(days=1)
    assert nxt.second == 0
    assert nxt.microsecond == 0


def test_after_candidate_moves_to_next_day() -> None:
    now = datetime(2026, 9, 28, 2, 0, 1, tzinfo=BANGKOK)
    nxt = next_scheduled(_settings(), now=now)
    assert nxt == datetime(2026, 9, 29, 2, 0, tzinfo=BANGKOK)


def test_timezone_is_backup_timezone() -> None:
    now = datetime(2026, 9, 28, 18, 30, tzinfo=ZoneInfo("UTC"))
    nxt = next_scheduled(_settings(backup_timezone="Asia/Bangkok"), now=now)
    assert nxt.tzinfo == BANGKOK
    assert nxt == datetime(2026, 9, 29, 2, 0, tzinfo=BANGKOK)


def test_disabled_clock_sleeps_one_hour_and_does_not_run() -> None:
    slept: list[float] = []
    ran: list[Settings] = []

    async def sleep(delay: float) -> None:
        slept.append(delay)

    def run_once(settings: Settings) -> None:
        ran.append(settings)

    asyncio.run(
        run_backup_clock(
            _settings(backup_enabled=False),
            sleep=sleep,
            run_once=run_once,
        )
    )
    assert slept == [3600]
    assert ran == []


def test_clock_waits_then_runs_once_when_due() -> None:
    order: list[str] = []

    async def sleep(delay: float) -> None:
        order.append(f"sleep:{round(delay)}")

    def run_once(_settings: Settings) -> None:
        order.append("run")

    now = datetime(2026, 9, 28, 1, 0, tzinfo=BANGKOK)
    asyncio.run(run_backup_clock(_settings(), sleep=sleep, run_once=run_once, now=now))
    assert order == ["sleep:3600", "run"]


def test_cancel_during_wait_does_not_run_backup() -> None:
    ran: list[str] = []

    async def sleep(_delay: float) -> None:
        raise asyncio.CancelledError

    def run_once(_settings: Settings) -> None:
        ran.append("run")

    async def scenario() -> None:
        with_cancel = run_backup_clock(_settings(), sleep=sleep, run_once=run_once)
        try:
            await with_cancel
        except asyncio.CancelledError:
            return
        raise AssertionError("cancel did not propagate")

    asyncio.run(scenario())
    assert ran == []


def test_two_due_calls_are_not_deduplicated() -> None:
    calls = 0

    async def sleep(_delay: float) -> None:
        return None

    def run_once(_settings: Settings) -> None:
        nonlocal calls
        calls += 1

    now = datetime(2026, 9, 28, 3, 0, tzinfo=BANGKOK)

    async def scenario() -> None:
        settings = _settings()
        await run_backup_clock(settings, sleep=sleep, run_once=run_once, now=now)
        await run_backup_clock(settings, sleep=sleep, run_once=run_once, now=now)

    asyncio.run(scenario())
    assert calls == 2


def test_exact_boundary_wait_is_until_next_day() -> None:
    slept: list[float] = []

    async def sleep(delay: float) -> None:
        slept.append(delay)

    now = datetime(2026, 9, 28, 2, 0, tzinfo=BANGKOK)
    asyncio.run(
        run_backup_clock(
            _settings(),
            sleep=sleep,
            run_once=lambda _settings: None,
            now=now,
        )
    )
    assert slept[0] >= 86400 - 1


def test_registry_and_factory_stay_one_sqlite_backup() -> None:
    names = {job.name for job in default_engine().jobs()}
    built = factories(get_settings())
    assert names == SIX
    assert set(built) == SIX
    assert list(built).count("sqlite_backup") == 1
    assert len(built) == 6


def test_other_clocks_unchanged() -> None:
    assert TICK_SECONDS == 60
    assert {5, 10, 30, 60} == ALLOWED_INTERVALS
    assert run_backup_once.__module__ == "homelab_monitor.sqlite_backup"
