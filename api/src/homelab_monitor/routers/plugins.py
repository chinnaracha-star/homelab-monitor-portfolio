from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from homelab_monitor.auth.dependencies import require_roles
from homelab_monitor.database import get_db
from homelab_monitor.errors import APIError
from homelab_monitor.plugin_manager import apply_lifecycle, list_plugins
from homelab_monitor.settings import Settings, get_settings

router = APIRouter(prefix="/api/v1/plugins", tags=["plugins"])
READ = Depends(require_roles("admin", "operator", "viewer"))
WRITE = Depends(require_roles("admin"))


class PluginActionRequest(BaseModel):
    action: str


@router.get("", dependencies=[READ])
def get_plugins(
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[dict]:
    return list_plugins(settings=settings, db=db)


@router.post("/{plugin_id}/lifecycle", dependencies=[WRITE])
def plugin_lifecycle(plugin_id: str, payload: PluginActionRequest) -> dict:
    try:
        return apply_lifecycle(plugin_id, payload.action).to_dict()
    except KeyError as error:
        raise APIError(404, "plugin_not_found", "Unknown plugin") from error
    except ValueError as error:
        raise APIError(400, "invalid_plugin_action", str(error)) from error
