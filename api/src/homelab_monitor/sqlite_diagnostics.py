"""Process-local notes about who is writing SQLite. Does not retry or commit.

SQLAlchemy begin/commit state is not the SQLite file lock. A connection
listed here was checked out. It is not a proven lock owner.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

from sqlalchemy import Engine, event
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

logger = logging.getLogger("homelab_monitor.sqlite_diagnostics")

_lock = threading.Lock()
_seq = 0
_active: dict[int, tuple[str, float]] = {}
_operation: ContextVar[str | None] = ContextVar("sqlite_writer_operation", default=None)
_connections: dict[int, dict[str, object]] = {}
_dbapi_ids: dict[int, int] = {}
_hooks_installed: set[int] = set()

_KINDS = ("INSERT", "UPDATE", "DELETE", "SELECT")
_TABLES = (
    "agents",
    "alerts",
    "photo_events",
    "notifications",
    "ops_snapshots",
    "metric_reports",
    "notification_settings",
)


@contextmanager
def writer_operation(name: str) -> Iterator[None]:
    """Mark one DB write section. The mark ends on return or any exception."""
    global _seq
    with _lock:
        _seq += 1
        token = _seq
        _active[token] = (name, time.monotonic())
        for record in _connections.values():
            if record.get("thread_id") == threading.get_ident():
                record["operation"] = name
    context = _operation.set(name)
    try:
        yield
    finally:
        _operation.reset(context)
        with _lock:
            _active.pop(token, None)


def active_writers() -> list[dict[str, object]]:
    now = time.monotonic()
    with _lock:
        items = list(_active.values())
    return [
        {"operation": name, "elapsed_ms": round((now - started) * 1000, 1)}
        for name, started in items
    ]


def install_connection_diagnostics(engine: Engine, factory: sessionmaker[Session]) -> None:
    """Watch checkout and transaction boundaries. Handlers never touch SQL."""
    if id(engine) in _hooks_installed:
        return
    _hooks_installed.add(id(engine))

    @event.listens_for(engine, "checkout")
    def _checkout(dbapi_connection: object, _record: object, _proxy: object) -> None:
        _remember_checkout(dbapi_connection)

    @event.listens_for(engine, "checkin")
    def _checkin(dbapi_connection: object, _record: object) -> None:
        _forget_connection(dbapi_connection)

    @event.listens_for(factory, "after_begin")
    def _after_begin(session: Session, _transaction: object, connection: object) -> None:
        fairy = getattr(connection, "connection", None)
        _mark_transaction(getattr(fairy, "dbapi_connection", None), session, began=True)

    @event.listens_for(factory, "after_commit")
    def _after_commit(session: Session) -> None:
        _clear_transaction(session)

    @event.listens_for(factory, "after_rollback")
    def _after_rollback(session: Session) -> None:
        _clear_transaction(session)


def _remember_checkout(dbapi_connection: object) -> None:
    try:
        now = time.monotonic()
        operation = _operation.get() or "unknown"
        with _lock:
            global _seq
            _seq += 1
            identity = _seq
            _dbapi_ids[id(dbapi_connection)] = identity
            _connections[identity] = {
                "id": identity,
                "thread_id": threading.get_ident(),
                "checked_out_at": now,
                "transaction_started": None,
                "operation": operation,
            }
    except Exception:
        logger.warning("sqlite_connection_diagnostic_failed phase=checkout")


def _forget_connection(dbapi_connection: object) -> None:
    try:
        with _lock:
            identity = _dbapi_ids.pop(id(dbapi_connection), None)
            if identity is not None:
                _connections.pop(identity, None)
    except Exception:
        logger.warning("sqlite_connection_diagnostic_failed phase=checkin")


def _mark_transaction(dbapi_connection: object, session: Session, *, began: bool) -> None:
    try:
        if dbapi_connection is None:
            return
        with _lock:
            identity = _dbapi_ids.get(id(dbapi_connection))
            record = _connections.get(identity) if identity is not None else None
            if record is None:
                return
            record["session_key"] = id(session)
            record["transaction_started"] = time.monotonic() if began else None
    except Exception:
        logger.warning("sqlite_connection_diagnostic_failed phase=transaction")


def _clear_transaction(session: Session) -> None:
    try:
        key = id(session)
        with _lock:
            for record in _connections.values():
                if record.get("session_key") == key:
                    record["transaction_started"] = None
    except Exception:
        logger.warning("sqlite_connection_diagnostic_failed phase=transaction")


def active_connections() -> list[dict[str, object]]:
    now = time.monotonic()
    with _lock:
        records = [dict(item) for item in _connections.values()]
    snapshot: list[dict[str, object]] = []
    for record in records:
        started = record.get("transaction_started")
        checked_out = record.get("checked_out_at")
        snapshot.append(
            {
                "id": record.get("id"),
                "checked_out_ms": round((now - checked_out) * 1000, 1)
                if isinstance(checked_out, float)
                else None,
                "transaction_active": started is not None,
                "transaction_age_ms": round((now - started) * 1000, 1)
                if isinstance(started, float)
                else None,
                "operation": record.get("operation") or "unknown",
            }
        )
    return snapshot


def is_database_locked(error: OperationalError) -> bool:
    text = str(getattr(error, "orig", error))
    return "database is locked" in text.lower()


def classify_statement(statement: object) -> tuple[str, str]:
    if not isinstance(statement, str) or not statement.strip():
        return "UNKNOWN", "unknown"
    head = statement.lstrip().split(None, 1)[0].upper()
    kind = head if head in _KINDS else "UNKNOWN"
    folded = statement.upper()
    for table in _TABLES:
        if table.upper() in folded:
            return kind, table
    return kind, "unknown"


def log_sqlite_busy(
    error: OperationalError,
    *,
    operation: str,
    session: Session | None,
    started: float,
) -> None:
    """Log a lock without the SQL parameters, then return. Caller re-raises."""
    kind, target = classify_statement(getattr(error, "statement", None))
    writers = active_writers()
    logger.warning(
        "sqlite_busy_detected operation=%s statement_kind=%s target=%s "
        "transaction_active=%s transaction_nested=%s session=%s elapsed_ms=%s "
        "active_writers=%s active_connections=%s",
        operation,
        kind,
        target,
        bool(session.in_transaction()) if session is not None else "unknown",
        bool(session.in_nested_transaction()) if session is not None else "unknown",
        id(session) if session is not None else "none",
        round((time.monotonic() - started) * 1000, 1),
        writers,
        active_connections(),
    )
