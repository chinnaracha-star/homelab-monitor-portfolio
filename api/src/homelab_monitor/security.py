import hashlib
import secrets
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from homelab_monitor.database import get_db
from homelab_monitor.errors import APIError
from homelab_monitor.models import Agent

bearer_scheme = HTTPBearer(auto_error=False)


def create_agent_token() -> str:
    return secrets.token_urlsafe(32)


def hash_agent_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def get_current_agent(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> Agent:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise APIError(401, "agent_auth_required", "A valid agent bearer token is required")

    token_hash = hash_agent_token(credentials.credentials)
    agent = db.scalar(select(Agent).where(Agent.token_hash == token_hash))
    if agent is None:
        raise APIError(401, "invalid_agent_token", "The agent token is invalid")
    return agent
