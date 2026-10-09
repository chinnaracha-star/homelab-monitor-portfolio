from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

DashboardEventType = Literal[
    "overview_updated",
    "agent_updated",
    "alert_updated",
    "connection",
]


def build_event(
    event_type: DashboardEventType,
    *,
    reason: str,
    agent_id: str | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"reason": reason}
    if agent_id is not None:
        payload["agent_id"] = agent_id
    if status is not None:
        payload["status"] = status
    return {
        "id": str(uuid4()),
        "type": event_type,
        "timestamp": datetime.now(UTC).isoformat(),
        "payload": payload,
    }
