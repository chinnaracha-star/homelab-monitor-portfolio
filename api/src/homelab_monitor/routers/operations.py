from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from homelab_monitor.auth.dependencies import get_current_user, require_roles
from homelab_monitor.database import get_db
from homelab_monitor.models import User
from homelab_monitor.operations import catalog, load_history, run_operation
from homelab_monitor.settings import Settings, get_settings

router = APIRouter(prefix="/api/v1/operations", tags=["operations"])
WRITE = Depends(require_roles("admin", "operator"))


class OperationRunRequest(BaseModel):
    confirm: bool = False


@router.get("", dependencies=[WRITE])
def list_operations() -> list[dict]:
    return catalog()


@router.get("/history", dependencies=[WRITE])
def operation_history(settings: Annotated[Settings, Depends(get_settings)]) -> list[dict]:
    return list(reversed(load_history(settings)))


@router.post("/{operation_id}/run")
def execute_operation(
    operation_id: str,
    payload: OperationRunRequest,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    if user.role not in {"admin", "operator"}:
        from homelab_monitor.errors import APIError

        raise APIError(403, "permission_denied", "Operators and admins can run operations")
    return run_operation(
        operation_id,
        settings=settings,
        db=db,
        username=user.username,
        role=user.role,
        confirm=payload.confirm,
    )
