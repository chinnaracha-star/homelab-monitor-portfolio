from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from homelab_monitor.auth.dependencies import require_roles
from homelab_monitor.database import get_db
from homelab_monitor.knowledge import collect
from homelab_monitor.settings import Settings, get_settings

router = APIRouter(prefix="/api/v1/knowledge", tags=["knowledge"])
READ = Depends(require_roles("admin", "operator", "viewer"))


@router.get("", dependencies=[READ])
def get_knowledge(
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    q: Annotated[str, Query()] = "",
    kind: Annotated[str, Query()] = "all",
) -> dict:
    return collect(db, settings, query=q, kind=kind)


@router.get("/export", dependencies=[READ])
def export_knowledge(
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    q: Annotated[str, Query()] = "",
    kind: Annotated[str, Query()] = "all",
) -> PlainTextResponse:
    payload = collect(db, settings, query=q, kind=kind)
    lines = ["kind,timestamp,title"]
    for item in payload["items"]:
        title = str(item["title"]).replace('"', "'")
        lines.append(f'{item["kind"]},{item["timestamp"]},"{title}"')
    return PlainTextResponse("\n".join(lines), media_type="text/csv")
