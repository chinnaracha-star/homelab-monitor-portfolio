import inspect
import sqlite3
import threading

import pytest
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from homelab_monitor.photo_watcher import PhotoWatcherService
from homelab_monitor.routers.agents import check_in
from homelab_monitor.sqlite_diagnostics import (
    active_writers,
    classify_statement,
    is_database_locked,
    log_sqlite_busy,
    writer_operation,
)


def test_writer_visible_only_while_active() -> None:
    assert active_writers() == []
    with writer_operation("agent_check_in"):
        names = [item["operation"] for item in active_writers()]
        assert names == ["agent_check_in"]
        assert active_writers()[0]["elapsed_ms"] >= 0
    assert active_writers() == []


def test_writer_clears_after_exception() -> None:
    with pytest.raises(RuntimeError), writer_operation("photo_prune"):
        raise RuntimeError("stop")
    assert active_writers() == []


def test_concurrent_writers_are_listed() -> None:
    started = threading.Event()
    release = threading.Event()

    def other() -> None:
        with writer_operation("metric_report_ingest"):
            started.set()
            release.wait(1)

    thread = threading.Thread(target=other)
    thread.start()
    assert started.wait(1)
    with writer_operation("agent_check_in"):
        names = {item["operation"] for item in active_writers()}
    release.set()
    thread.join()
    assert names == {"agent_check_in", "metric_report_ingest"}
    assert active_writers() == []


def test_classify_statement_ignores_parameters() -> None:
    kind, target = classify_statement("UPDATE agents SET status=:status")
    assert kind == "UPDATE"
    assert target == "agents"
    assert classify_statement(None) == ("UNKNOWN", "unknown")
    assert classify_statement("PRAGMA x") == ("UNKNOWN", "unknown")


def test_only_database_locked_is_busy() -> None:
    locked = OperationalError(
        "UPDATE agents",
        {"token": "secret"},
        sqlite3.OperationalError("database is locked"),
    )
    other = OperationalError("SELECT 1", {}, sqlite3.OperationalError("no such table"))
    assert is_database_locked(locked) is True
    assert is_database_locked(other) is False


def test_busy_log_omits_parameters(caplog: pytest.LogCaptureFixture) -> None:
    error = OperationalError(
        "UPDATE agents SET token=:token",
        {"token": "secret-value"},
        sqlite3.OperationalError("database is locked"),
    )
    with caplog.at_level("WARNING"):
        log_sqlite_busy(error, operation="agent_check_in", session=None, started=0)
    assert "sqlite_busy_detected" in caplog.text
    assert "statement_kind=UPDATE" in caplog.text
    assert "target=agents" in caplog.text
    assert "secret-value" not in caplog.text
    assert ":token" not in caplog.text


def test_check_in_logs_and_reraises_lock(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    error = OperationalError(
        "UPDATE agents",
        {"password": "hidden"},
        sqlite3.OperationalError("database is locked"),
    )

    class Agent:
        version = ""
        last_seen_at = None
        status = ""
        id = "agent-1"
        name = "box"

    class DB:
        def commit(self) -> None:
            raise error

        def in_transaction(self) -> bool:
            return True

        def in_nested_transaction(self) -> bool:
            return False

    class Payload:
        version = "1"
        config_revision = 1

    class Engine:
        def __init__(self, _settings: object) -> None:
            return None

        def mark_agent_online(self, *_args: object) -> None:
            return None

    monkeypatch.setattr("homelab_monitor.routers.agents.AlertEngine", Engine)
    with (
        caplog.at_level("WARNING"),
        pytest.raises(OperationalError),
        writer_operation("photo_prune"),
    ):
        check_in(Payload(), Agent(), DB(), object())  # type: ignore[arg-type]

    assert "sqlite_busy_detected" in caplog.text
    assert "photo_prune" in caplog.text
    assert "hidden" not in caplog.text
    assert "password" not in caplog.text


def test_check_in_does_not_label_other_operational_errors(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    error = OperationalError("UPDATE agents", {}, sqlite3.OperationalError("no such table"))

    class Agent:
        version = ""
        last_seen_at = None
        status = ""

    class DB:
        def commit(self) -> None:
            raise error

    class Payload:
        version = "1"

    class Engine:
        def __init__(self, _settings: object) -> None:
            return None

        def mark_agent_online(self, *_args: object) -> None:
            return None

    monkeypatch.setattr("homelab_monitor.routers.agents.AlertEngine", Engine)
    with caplog.at_level("WARNING"), pytest.raises(OperationalError):
        check_in(Payload(), Agent(), DB(), object())  # type: ignore[arg-type]
    assert "sqlite_busy_detected" not in caplog.text


def test_directory_walk_is_not_a_writer_mark() -> None:
    source = inspect.getsource(PhotoWatcherService.scan_once)
    walk = source.split("iter_image_files", 1)[0].rsplit("\n", 1)[-1]
    assert "writer_operation" not in walk
    assert 'writer_operation("photo_prune")' in source
    insert = inspect.getsource(PhotoWatcherService._handle_discovered)
    assert 'writer_operation("photo_event_insert")' in insert
    flush = inspect.getsource(PhotoWatcherService.flush_photo_notifications)
    assert 'writer_operation("photo_notification_mark_sent")' in flush


def test_session_type_unchanged() -> None:
    assert Session.in_transaction
