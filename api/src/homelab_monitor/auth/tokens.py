from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

from homelab_monitor.errors import APIError
from homelab_monitor.settings import Settings

ALGORITHM = "HS256"


def create_access_token(
    settings: Settings,
    *,
    subject: str,
    user_id: str,
    role: str,
    expires_delta: timedelta | None = None,
) -> str:
    expires_at = datetime.now(UTC) + (
        expires_delta
        if expires_delta is not None
        else timedelta(minutes=settings.jwt_expire_minutes)
    )
    payload = {
        "sub": subject,
        "uid": user_id,
        "role": role,
        "exp": expires_at,
        "iat": datetime.now(UTC),
    }
    return jwt.encode(payload, settings.jwt_secret.get_secret_value(), algorithm=ALGORITHM)


def decode_access_token(settings: Settings, token: str) -> dict[str, Any]:
    try:
        return jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=[ALGORITHM],
        )
    except jwt.ExpiredSignatureError as error:
        raise APIError(401, "token_expired", "The access token has expired") from error
    except jwt.InvalidTokenError as error:
        raise APIError(401, "invalid_token", "The access token is invalid") from error
