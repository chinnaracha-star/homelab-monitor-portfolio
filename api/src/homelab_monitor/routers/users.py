from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from homelab_monitor.auth.dependencies import get_current_user, require_roles
from homelab_monitor.auth.passwords import hash_password
from homelab_monitor.database import get_db
from homelab_monitor.errors import APIError
from homelab_monitor.models import User
from homelab_monitor.schemas import (
    UserCreateRequest,
    UserPasswordRequest,
    UserResponse,
    UserStatusRequest,
    UserUpdateRequest,
)
from homelab_monitor.user_admin import (
    ensure_not_last_active_admin,
    ensure_not_self,
    get_user_or_404,
)

router = APIRouter(
    prefix="/api/v1/users",
    tags=["users"],
    dependencies=[Depends(require_roles("admin"))],
)


@router.get(
    "",
    response_model=list[UserResponse],
    summary="List dashboard users",
)
def list_users(db: Annotated[Session, Depends(get_db)]) -> list[User]:
    return list(db.scalars(select(User).order_by(User.username.asc())).all())


@router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a dashboard user",
)
def create_user(
    payload: UserCreateRequest,
    db: Annotated[Session, Depends(get_db)],
) -> User:
    if db.scalar(select(User.id).where(User.username == payload.username)) is not None:
        raise APIError(409, "username_taken", "A user with this username already exists")

    user = User(
        username=payload.username,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
        role=payload.role,
        is_active=payload.is_active,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise APIError(409, "username_taken", "A user with this username already exists") from error
    db.refresh(user)
    return user


@router.put(
    "/{user_id}",
    response_model=UserResponse,
    summary="Update a dashboard user",
)
def update_user(
    user_id: str,
    payload: UserUpdateRequest,
    actor: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    user = get_user_or_404(db, user_id)
    if actor.id == user.id and not payload.is_active:
        ensure_not_self(actor, user, action="disable")
    ensure_not_last_active_admin(
        db,
        user,
        would_lose_admin=(not payload.is_active) or payload.role != "admin",
    )
    user.full_name = payload.full_name
    user.role = payload.role
    user.is_active = payload.is_active
    db.commit()
    db.refresh(user)
    return user


@router.patch(
    "/{user_id}/password",
    response_model=UserResponse,
    summary="Reset a dashboard user password",
)
def reset_user_password(
    user_id: str,
    payload: UserPasswordRequest,
    db: Annotated[Session, Depends(get_db)],
) -> User:
    user = get_user_or_404(db, user_id)
    user.password_hash = hash_password(payload.password)
    db.commit()
    db.refresh(user)
    return user


@router.patch(
    "/{user_id}/status",
    response_model=UserResponse,
    summary="Enable or disable a dashboard user",
)
def update_user_status(
    user_id: str,
    payload: UserStatusRequest,
    actor: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    user = get_user_or_404(db, user_id)
    if not payload.is_active:
        ensure_not_self(actor, user, action="disable")
        ensure_not_last_active_admin(db, user, would_lose_admin=True)
    user.is_active = payload.is_active
    db.commit()
    db.refresh(user)
    return user


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a dashboard user",
)
def delete_user(
    user_id: str,
    actor: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    user = get_user_or_404(db, user_id)
    ensure_not_self(actor, user, action="delete")
    ensure_not_last_active_admin(db, user, would_lose_admin=True)
    db.delete(user)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
