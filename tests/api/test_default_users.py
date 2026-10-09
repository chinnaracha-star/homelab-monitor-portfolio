from pathlib import Path

import pytest
from pydantic import SecretStr
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from homelab_monitor.auth.bootstrap import InsecureBootstrapError, ensure_default_users
from homelab_monitor.auth.passwords import hash_password, verify_password
from homelab_monitor.database import Base
from homelab_monitor.models import User
from homelab_monitor.settings import Settings

JWT = "test-jwt-secret-key-at-least-32-chars"
REG = "test-registration-key-at-least-24-chars"


def _settings(**overrides: object) -> Settings:
    values = {
        "registration_key": REG,
        "jwt_secret": JWT,
        "environment": "development",
        **overrides,
    }
    return Settings.model_validate(values)


def test_bootstrap_creates_accounts_from_configured_passwords(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'users.db'}")
    Base.metadata.create_all(bind=engine)
    settings = _settings(
        bootstrap_admin_password=SecretStr("admin-pass-ok"),
        bootstrap_operator_password=SecretStr("operator-pass-ok"),
        bootstrap_viewer_password=SecretStr("viewer-pass-ok"),
    )
    with Session(engine) as db:
        ensure_default_users(db, settings)

    with Session(engine) as db:
        users = {user.username: user for user in db.scalars(select(User)).all()}
        assert set(users) == {"admin", "operator", "viewer"}
        assert users["admin"].role == "admin"
        assert verify_password("admin-pass-ok", users["admin"].password_hash)
        assert verify_password("operator-pass-ok", users["operator"].password_hash)
        assert verify_password("viewer-pass-ok", users["viewer"].password_hash)


def test_bootstrap_does_not_overwrite_existing_custom_passwords(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'users.db'}")
    Base.metadata.create_all(bind=engine)
    custom_hash = hash_password("keep-existing-admin")
    with Session(engine) as db:
        db.add(
            User(
                username="admin",
                password_hash=custom_hash,
                full_name="Custom Admin",
                role="admin",
                is_active=True,
            )
        )
        db.commit()
        ensure_default_users(
            db,
            _settings(bootstrap_admin_password=SecretStr("replacement-admin")),
        )

    with Session(engine) as db:
        admin = db.scalars(select(User).where(User.username == "admin")).one()
        assert admin.full_name == "Custom Admin"
        assert admin.password_hash == custom_hash
        assert verify_password("keep-existing-admin", admin.password_hash)


def test_production_requires_admin_bootstrap_password(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'users.db'}")
    Base.metadata.create_all(bind=engine)
    with (
        Session(engine) as db,
        pytest.raises(InsecureBootstrapError, match="HOMELAB_BOOTSTRAP_ADMIN_PASSWORD"),
    ):
        ensure_default_users(db, _settings(environment="production"))


def test_production_replaces_insecure_default_passwords(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'users.db'}")
    Base.metadata.create_all(bind=engine)
    with Session(engine) as db:
        db.add(
            User(
                username="admin",
                password_hash=hash_password("admin123"),
                full_name="Administrator",
                role="admin",
                is_active=True,
            )
        )
        db.commit()
        ensure_default_users(
            db,
            _settings(
                environment="production",
                bootstrap_admin_password=SecretStr("rotated-admin-pass"),
            ),
        )

    with Session(engine) as db:
        admin = db.scalars(select(User).where(User.username == "admin")).one()
        assert verify_password("rotated-admin-pass", admin.password_hash)
        assert not verify_password("admin123", admin.password_hash)


def test_production_rejects_known_default_bootstrap_password(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'users.db'}")
    Base.metadata.create_all(bind=engine)
    with Session(engine) as db, pytest.raises(InsecureBootstrapError, match="documented default"):
        ensure_default_users(
            db,
            _settings(
                environment="production",
                bootstrap_admin_password=SecretStr("admin123"),
            ),
        )
