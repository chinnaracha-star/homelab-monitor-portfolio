from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.orm import Session

from homelab_monitor.auth.tokens import decode_access_token
from homelab_monitor.database import get_engine
from homelab_monitor.errors import APIError
from homelab_monitor.models import User
from homelab_monitor.realtime import hub
from homelab_monitor.settings import get_settings

router = APIRouter(prefix="/api/v1", tags=["realtime"])


def _extract_token(websocket: WebSocket, token: str | None) -> str | None:
    if token:
        return token
    header = websocket.headers.get("authorization")
    if header and header.lower().startswith("bearer "):
        return header[7:].strip()
    return None


@router.websocket("/ws/dashboard")
async def dashboard_socket(
    websocket: WebSocket,
    token: Annotated[str | None, Query()] = None,
) -> None:
    raw_token = _extract_token(websocket, token)
    if not raw_token:
        await websocket.close(code=4401, reason="Authentication required")
        return

    settings = get_settings()
    try:
        payload = decode_access_token(settings, raw_token)
    except APIError:
        await websocket.close(code=4401, reason="Authentication required")
        return

    username = payload.get("sub")
    if not isinstance(username, str) or not username:
        await websocket.close(code=4401, reason="Authentication required")
        return

    with Session(get_engine()) as db:
        user = db.scalar(select(User).where(User.username == username))
        if user is None or not user.is_active:
            await websocket.close(code=4401, reason="Authentication required")
            return

    client_id = str(uuid4())
    await hub.manager.connect(client_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await hub.manager.disconnect(client_id)
    except Exception:
        await hub.manager.disconnect(client_id)
