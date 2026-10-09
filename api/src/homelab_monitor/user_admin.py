from sqlalchemy import func, select
from sqlalchemy.orm import Session

from homelab_monitor.errors import APIError
from homelab_monitor.models import User

LAST_ACTIVE_ADMIN_MESSAGE = "Cannot remove the last active administrator"


def get_user_or_404(db: Session, user_id: str) -> User:
    user = db.scalar(select(User).where(User.id == user_id))
    if user is None:
        raise APIError(404, "user_not_found", "The requested user does not exist")
    return user


def active_admin_count(db: Session) -> int:
    return (
        db.scalar(
            select(func.count())
            .select_from(User)
            .where(User.role == "admin", User.is_active.is_(True))
        )
        or 0
    )


def ensure_not_self(actor: User, target: User, *, action: str) -> None:
    if actor.id != target.id:
        return
    if action == "delete":
        raise APIError(409, "cannot_delete_self", "You cannot delete your own account")
    raise APIError(409, "cannot_disable_self", "You cannot disable your own account")


def ensure_not_last_active_admin(db: Session, user: User, *, would_lose_admin: bool) -> None:
    if not would_lose_admin:
        return
    if user.role == "admin" and user.is_active and active_admin_count(db) <= 1:
        raise APIError(409, "last_active_admin", LAST_ACTIVE_ADMIN_MESSAGE)
