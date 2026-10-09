import os
import tempfile
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy.orm import Session

TEST_DATABASE_PATH = Path(tempfile.gettempdir()) / f"homelab-monitor-tests-{os.getpid()}.db"
os.environ["HOMELAB_ENVIRONMENT"] = "development"
os.environ["HOMELAB_REGISTRATION_KEY"] = "test-registration-key-at-least-24-chars"
os.environ["HOMELAB_DATABASE_URL"] = f"sqlite:///{TEST_DATABASE_PATH}"
os.environ["HOMELAB_LOG_LEVEL"] = "WARNING"
os.environ["HOMELAB_JWT_SECRET"] = "test-jwt-secret-key-at-least-32-chars"
os.environ["TELEGRAM_BOT_TOKEN"] = ""
os.environ["TELEGRAM_CHAT_ID"] = ""
os.environ["HOMELAB_TELEGRAM_BOT_TOKEN"] = ""
os.environ["HOMELAB_TELEGRAM_CHAT_ID"] = ""
os.environ["HOMELAB_TELEGRAM_ENABLED"] = "true"
os.environ["TELEGRAM_ENABLED"] = "true"
os.environ["HOMELAB_NOTIFICATION_WORKER_ENABLED"] = "false"
os.environ["HOMELAB_PHOTO_WATCHER_ENABLED"] = "false"
os.environ["HOMELAB_BOOTSTRAP_ADMIN_PASSWORD"] = ""
os.environ["HOMELAB_BOOTSTRAP_OPERATOR_PASSWORD"] = ""
os.environ["HOMELAB_BOOTSTRAP_VIEWER_PASSWORD"] = ""
os.environ["HOMELAB_DASHBOARD_PUBLIC_URL"] = ""
os.environ["HOMELAB_IMMICH_PUBLIC_URL"] = ""
os.environ["HOMELAB_QNAP_PUBLIC_URL"] = ""
os.environ["HOMELAB_QNAP_URL"] = ""
os.environ["HOMELAB_INFRASTRUCTURE_MOCK"] = "true"
os.environ["HOMELAB_API_HEALTH_URL"] = ""
os.environ["HOMELAB_DASHBOARD_HEALTH_URL"] = ""

from homelab_monitor.alert_stability import reset_stability_windows  # noqa: E402
from homelab_monitor.auth.passwords import hash_password  # noqa: E402
from homelab_monitor.database import Base, get_engine  # noqa: E402
from homelab_monitor.infrastructure import reset_infrastructure_service  # noqa: E402
from homelab_monitor.main import app  # noqa: E402
from homelab_monitor.models import PhotoEvent, PhotoMonitorSettings, User  # noqa: E402
from homelab_monitor.notification_history import reset_notification_history  # noqa: E402
from homelab_monitor.notification_queue import reset_notification_queue  # noqa: E402
from homelab_monitor.photo_watcher import reset_photo_watcher_service  # noqa: E402
from homelab_monitor.settings import get_settings  # noqa: E402

get_settings.cache_clear()
reset_infrastructure_service()


def _remove_sqlite(path: Path) -> None:
    path.unlink(missing_ok=True)
    Path(f"{path}-wal").unlink(missing_ok=True)
    Path(f"{path}-shm").unlink(missing_ok=True)
    (path.parent / "photo_baseline.json").unlink(missing_ok=True)
    (path.parent / "photo_baseline.json.tmp").unlink(missing_ok=True)


def seed_users() -> None:
    with Session(get_engine()) as db:
        db.add_all(
            [
                User(
                    username="admin",
                    password_hash=hash_password("admin123"),
                    full_name="Administrator",
                    role="admin",
                    is_active=True,
                ),
                User(
                    username="operator",
                    password_hash=hash_password("operator123"),
                    full_name="Operator",
                    role="operator",
                    is_active=True,
                ),
                User(
                    username="viewer",
                    password_hash=hash_password("viewer123"),
                    full_name="Viewer",
                    role="viewer",
                    is_active=True,
                ),
                User(
                    username="disabled",
                    password_hash=hash_password("disabled123"),
                    full_name="Disabled User",
                    role="viewer",
                    is_active=False,
                ),
            ]
        )
        db.commit()


@pytest.fixture(scope="session", autouse=True)
def database_schema() -> Iterator[None]:
    _remove_sqlite(TEST_DATABASE_PATH)
    Base.metadata.create_all(bind=get_engine())
    seed_users()
    yield
    Base.metadata.drop_all(bind=get_engine())
    get_engine().dispose()
    _remove_sqlite(TEST_DATABASE_PATH)


@pytest.fixture(autouse=True)
def reset_alert_stability_windows() -> Iterator[None]:
    reset_stability_windows()
    reset_notification_queue()
    reset_notification_history()
    reset_photo_watcher_service()
    with Session(get_engine()) as db:
        db.execute(delete(PhotoEvent))
        db.execute(delete(PhotoMonitorSettings))
        db.commit()
    (TEST_DATABASE_PATH.parent / "photo_baseline.json").unlink(missing_ok=True)
    yield
    reset_stability_windows()
    reset_notification_queue()
    reset_notification_history()
    reset_photo_watcher_service()


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def login(client: TestClient) -> Callable[..., str]:
    def _login(username: str = "admin", password: str = "admin123") -> str:
        response = client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": password},
        )
        assert response.status_code == 200
        return response.json()["access_token"]

    return _login


@pytest.fixture
def auth_header(login: Callable[..., str]) -> Callable[..., dict[str, str]]:
    def _auth_header(
        username: str = "admin",
        password: str = "admin123",
    ) -> dict[str, str]:
        return {"Authorization": f"Bearer {login(username, password)}"}

    return _auth_header
