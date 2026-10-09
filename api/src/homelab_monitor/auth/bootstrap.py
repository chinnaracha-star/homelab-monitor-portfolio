from dataclasses import dataclass

from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from homelab_monitor.auth.passwords import hash_password, verify_password
from homelab_monitor.models import User
from homelab_monitor.settings import Settings

INSECURE_BOOTSTRAP_PASSWORDS = {
    "admin": "admin123",
    "operator": "operator123",
    "viewer": "viewer123",
}

MIN_BOOTSTRAP_PASSWORD_LENGTH = 8


@dataclass(frozen=True)
class BootstrapAccount:
    username: str
    full_name: str
    role: str
    setting_name: str


BOOTSTRAP_ACCOUNTS = (
    BootstrapAccount("admin", "Administrator", "admin", "bootstrap_admin_password"),
    BootstrapAccount("operator", "Operator", "operator", "bootstrap_operator_password"),
    BootstrapAccount("viewer", "Viewer", "viewer", "bootstrap_viewer_password"),
)


class InsecureBootstrapError(RuntimeError):
    """Raised when production would keep or create a known default password."""


def _password_value(settings: Settings, setting_name: str) -> str | None:
    secret = getattr(settings, setting_name)
    if secret is None:
        return None
    value = secret.get_secret_value().strip()
    return value or None


def _is_production(settings: Settings) -> bool:
    return settings.environment.strip().lower() == "production"


def ensure_default_users(db: Session, settings: Settings) -> None:
    bind = db.get_bind()
    if bind is None or "users" not in inspect(bind).get_table_names():
        return

    existing = {user.username: user for user in db.scalars(select(User)).all()}
    changed = False
    production = _is_production(settings)

    for account in BOOTSTRAP_ACCOUNTS:
        configured = _password_value(settings, account.setting_name)
        if configured is not None:
            if len(configured) < MIN_BOOTSTRAP_PASSWORD_LENGTH:
                raise InsecureBootstrapError(
                    f"{account.setting_name} must be at least "
                    f"{MIN_BOOTSTRAP_PASSWORD_LENGTH} characters"
                )
            if configured == INSECURE_BOOTSTRAP_PASSWORDS[account.username]:
                raise InsecureBootstrapError(
                    f"{account.setting_name} must not use a documented default password"
                )
        user = existing.get(account.username)
        if user is None:
            if configured is None:
                if production and account.username == "admin":
                    raise InsecureBootstrapError(
                        "Set HOMELAB_BOOTSTRAP_ADMIN_PASSWORD before starting production"
                    )
                continue
            db.add(
                User(
                    username=account.username,
                    password_hash=hash_password(configured),
                    full_name=account.full_name,
                    role=account.role,
                    is_active=True,
                )
            )
            changed = True
            continue
        weak = INSECURE_BOOTSTRAP_PASSWORDS[account.username]
        if verify_password(weak, user.password_hash):
            if configured is not None:
                user.password_hash = hash_password(configured)
                changed = True
                continue
            if production:
                raise InsecureBootstrapError(
                    f"Replace the insecure {account.username} password via "
                    f"HOMELAB_{account.setting_name.upper()}"
                )

    if changed:
        db.commit()
