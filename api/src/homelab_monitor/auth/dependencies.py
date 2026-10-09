from collections.abc import Callable
from typing import Annotated

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from homelab_monitor.auth.tokens import decode_access_token
from homelab_monitor.database import get_db
from homelab_monitor.errors import APIError
from homelab_monitor.models import User
from homelab_monitor.settings import Settings, get_settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

PERMISSION_DENIED_MESSAGE = "You do not have permission to access this resource"


def get_current_user(
    token: Annotated[str | None, Depends(oauth2_scheme)],
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> User:
    if not token:
        raise APIError(401, "auth_required", "A valid bearer access token is required")

    payload = decode_access_token(settings, token)
    username = payload.get("sub")
    if not isinstance(username, str) or not username:
        raise APIError(401, "invalid_token", "The access token is invalid")

    user = db.scalar(select(User).where(User.username == username))
    if user is None:
        raise APIError(401, "invalid_token", "The access token is invalid")
    if not user.is_active:
        raise APIError(403, "user_inactive", "The user account is inactive")
    return user


def require_roles(*roles: str) -> Callable[..., User]:
    if not roles:
        raise ValueError("require_roles requires at least one role")
    allowed = frozenset(roles)

    def check_roles(user: Annotated[User, Depends(get_current_user)]) -> User:
        if user.role not in allowed:
            raise APIError(403, "permission_denied", PERMISSION_DENIED_MESSAGE)
        return user

    check_roles.__name__ = f"require_roles_{'_'.join(roles)}"
    return check_roles
