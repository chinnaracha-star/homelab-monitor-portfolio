from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from homelab_monitor.auth.dependencies import get_current_user
from homelab_monitor.auth.passwords import verify_password
from homelab_monitor.auth.tokens import create_access_token
from homelab_monitor.database import get_db
from homelab_monitor.errors import APIError
from homelab_monitor.models import User
from homelab_monitor.schemas import CurrentUserResponse, LoginRequest, TokenResponse
from homelab_monitor.settings import Settings, get_settings

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate a dashboard user",
)
def login(
    payload: LoginRequest,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenResponse:
    user = db.scalar(select(User).where(User.username == payload.username))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise APIError(401, "invalid_credentials", "The username or password is incorrect")
    if not user.is_active:
        raise APIError(403, "user_inactive", "The user account is inactive")

    return TokenResponse(
        access_token=create_access_token(
            settings,
            subject=user.username,
            user_id=user.id,
            role=user.role,
        ),
        expires_in=settings.jwt_expire_minutes * 60,
    )


@router.get(
    "/me",
    response_model=CurrentUserResponse,
    summary="Return the authenticated dashboard user",
)
def read_current_user(
    user: Annotated[User, Depends(get_current_user)],
) -> User:
    return user
