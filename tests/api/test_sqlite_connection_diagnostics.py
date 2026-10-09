import sqlite3
import tempfile
import threading
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import QueuePool

from homelab_monitor.sqlite_diagnostics import (
    active_connections,
    install_connection_diagnostics,
    log_sqlite_busy,
    writer_operation,
)


def _transaction_cleared() -> bool:
    rows = active_connections()
    return rows == [] or all(item["transaction_active"] is False for item in rows)


def _factory() -> tuple[object, sessionmaker[Session]]:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    install_connection_diagnostics(engine, factory)
    return engine, factory


def test_checkout_and_checkin() -> None:
    _engine, factory = _factory()
    assert active_connections() == []
    with factory() as session:
        session.execute(text("SELECT 1"))
        assert len(active_connections()) == 1
    assert active_connections() == []


def test_transaction_begin_commit_and_rollback() -> None:
    _engine, factory = _factory()
    with factory() as session:
        session.execute(text("CREATE TABLE sample (id INTEGER)"))
        session.commit()
        session.execute(text("SELECT 1"))
        active = active_connections()
        assert active[0]["transaction_active"] is True
        assert isinstance(active[0]["transaction_age_ms"], float)
        session.commit()
        assert _transaction_cleared()
        session.execute(text("SELECT 1"))
        session.rollback()
        assert _transaction_cleared()


def test_connections_stay_distinct() -> None:
    with tempfile.TemporaryDirectory() as directory:
        engine = create_engine(
            f"sqlite:///{Path(directory) / 'diag.db'}",
            poolclass=QueuePool,
            pool_size=2,
            max_overflow=0,
            connect_args={"check_same_thread": False},
        )
        factory = sessionmaker(bind=engine, expire_on_commit=False)
        install_connection_diagnostics(engine, factory)
        first = factory()
        second = factory()
        first.execute(text("SELECT 1"))
        second.execute(text("SELECT 1"))
        identities = {item["id"] for item in active_connections()}
        first.close()
        second.close()
        engine.dispose()
    assert len(identities) == 2
    assert active_connections() == []


def test_operation_context_and_unknown(caplog: pytest.LogCaptureFixture) -> None:
    _engine, factory = _factory()
    with factory() as session, writer_operation("agent_check_in"):
        session.execute(text("SELECT 1"))
        assert active_connections()[0]["operation"] == "agent_check_in"
    with factory() as session:
        session.execute(text("SELECT 1"))
        assert active_connections()[0]["operation"] == "unknown"
        error = OperationalError(
            "UPDATE agents",
            {"password": "hidden"},
            sqlite3.OperationalError("database is locked"),
        )
        with caplog.at_level("WARNING"):
            log_sqlite_busy(error, operation="agent_check_in", session=session, started=0)
    assert "active_connections=" in caplog.text
    assert "hidden" not in caplog.text


def test_registry_clears_when_operation_raises() -> None:
    _engine, factory = _factory()
    with pytest.raises(RuntimeError), factory() as session, writer_operation("photo_prune"):
        session.execute(text("SELECT 1"))
        raise RuntimeError("stop")
    assert active_connections() == []


def test_handlers_do_not_execute_sql() -> None:
    import inspect

    from homelab_monitor import sqlite_diagnostics

    source = inspect.getsource(sqlite_diagnostics.install_connection_diagnostics)
    source += inspect.getsource(sqlite_diagnostics._remember_checkout)
    source += inspect.getsource(sqlite_diagnostics._mark_transaction)
    assert "execute(" not in source
    assert ".commit(" not in source
    assert ".rollback(" not in source


def test_two_threads_do_not_share_identity() -> None:
    _engine, factory = _factory()
    seen: list[int] = []
    ready = threading.Event()

    def other() -> None:
        with factory() as session:
            session.execute(text("SELECT 1"))
            seen.append(int(active_connections()[0]["id"]))  # type: ignore[arg-type]
            ready.set()
            threading.Event().wait(0.05)

    thread = threading.Thread(target=other)
    thread.start()
    assert ready.wait(1)
    with factory() as session:
        session.execute(text("SELECT 1"))
        mine = {item["id"] for item in active_connections()}
    thread.join()
    assert len(mine) == 2
    assert seen[0] in mine
