from collections.abc import Generator
from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from homelab_monitor.settings import get_settings
from homelab_monitor.sqlite_diagnostics import install_connection_diagnostics


class Base(DeclarativeBase):
    pass


_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    global _engine, _session_factory

    if _engine is None:
        database_url = get_settings().database_url
        if database_url.startswith("sqlite"):
            database_path = database_url.removeprefix("sqlite:///")
            if database_path and database_path != ":memory:":
                Path(database_path).parent.mkdir(parents=True, exist_ok=True)

        connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
        _engine = create_engine(database_url, connect_args=connect_args, pool_pre_ping=True)

        if database_url.startswith("sqlite"):

            @event.listens_for(_engine, "connect")
            def configure_sqlite(dbapi_connection: object, _: object) -> None:
                cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA busy_timeout=8000")
                cursor.close()

        _session_factory = sessionmaker(bind=_engine, expire_on_commit=False)
        install_connection_diagnostics(_engine, _session_factory)

    return _engine


def get_db() -> Generator[Session, None, None]:
    global _session_factory

    get_engine()
    if _session_factory is None:
        raise RuntimeError("Database session factory was not initialized")

    with _session_factory() as session:
        yield session
