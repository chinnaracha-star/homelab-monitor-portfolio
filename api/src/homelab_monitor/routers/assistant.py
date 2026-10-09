from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from homelab_monitor.assistant import briefing
from homelab_monitor.auth.dependencies import require_roles
from homelab_monitor.database import get_db
from homelab_monitor.settings import Settings, get_settings

router = APIRouter(prefix="/api/v1/assistant", tags=["assistant"])
READ = Depends(require_roles("admin", "operator", "viewer"))


@router.get("/briefing", dependencies=[READ])
def get_briefing(
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    return briefing(db, settings)
