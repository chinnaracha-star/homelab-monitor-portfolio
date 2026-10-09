from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from homelab_monitor.alert_rules import preview_sentence
from homelab_monitor.auth.dependencies import require_roles
from homelab_monitor.database import get_db
from homelab_monitor.errors import APIError
from homelab_monitor.models import Agent, AgentGroup, AlertRule
from homelab_monitor.realtime import hub
from homelab_monitor.schemas import (
    AlertRuleCreateRequest,
    AlertRuleEnableRequest,
    AlertRuleResponse,
    AlertRuleUpdateRequest,
)

router = APIRouter(prefix="/api/v1", tags=["alert-rules"])

READ = Depends(require_roles("admin", "operator", "viewer"))
WRITE = Depends(require_roles("admin"))


def _validate_scope(payload: AlertRuleCreateRequest) -> None:
    if payload.applies_to == "all" and (payload.group_id or payload.agent_id):
        raise APIError(
            422,
            "alert_rule_scope_invalid",
            "Global rules cannot target a group or agent",
        )
    if payload.applies_to == "group" and not payload.group_id:
        raise APIError(422, "alert_rule_scope_invalid", "Group rules require group_id")
    if payload.applies_to == "group":
        payload.agent_id = None
    if payload.applies_to == "agent" and not payload.agent_id:
        raise APIError(422, "alert_rule_scope_invalid", "Agent rules require agent_id")
    if payload.applies_to == "agent":
        payload.group_id = None


def _ensure_targets(db: Session, payload: AlertRuleCreateRequest) -> None:
    _validate_scope(payload)
    if payload.group_id:
        group = db.get(AgentGroup, payload.group_id)
        if group is None:
            raise APIError(404, "group_not_found", "The requested group does not exist")
    if payload.agent_id:
        agent = db.get(Agent, payload.agent_id)
        if agent is None:
            raise APIError(404, "agent_not_found", "The requested agent does not exist")


def _to_response(row: AlertRule) -> AlertRuleResponse:
    return AlertRuleResponse(
        id=row.id,
        name=row.name,
        description=row.description,
        metric=row.metric,
        operator=row.operator,
        threshold=row.threshold,
        severity=row.severity,
        enabled=row.enabled,
        cooldown_seconds=row.cooldown_seconds,
        applies_to=row.applies_to,
        group_id=row.group_id,
        agent_id=row.agent_id,
        preview=preview_sentence(row.metric, row.operator, row.threshold, row.severity),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _get_rule(db: Session, rule_id: str) -> AlertRule:
    row = db.get(AlertRule, rule_id)
    if row is None:
        raise APIError(404, "alert_rule_not_found", "The requested alert rule does not exist")
    return row


def _notify() -> None:
    hub.publish("overview_updated", reason="rule_updated")
    hub.publish("alert_updated", reason="rule_updated")


def _duplicate_name() -> APIError:
    return APIError(409, "alert_rule_name_taken", "An alert rule with this name already exists")


@router.get(
    "/alert-rules",
    response_model=list[AlertRuleResponse],
    dependencies=[READ],
    summary="List alert rules",
)
def list_alert_rules(db: Annotated[Session, Depends(get_db)]) -> list[AlertRuleResponse]:
    rows = list(db.scalars(select(AlertRule).order_by(AlertRule.name.asc())).all())
    return [_to_response(row) for row in rows]


@router.post(
    "/alert-rules",
    response_model=AlertRuleResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[WRITE],
    summary="Create an alert rule",
)
def create_alert_rule(
    payload: AlertRuleCreateRequest,
    db: Annotated[Session, Depends(get_db)],
) -> AlertRuleResponse:
    _ensure_targets(db, payload)
    row = AlertRule(**payload.model_dump())
    db.add(row)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise _duplicate_name() from error
    db.refresh(row)
    _notify()
    return _to_response(row)


@router.get(
    "/alert-rules/{rule_id}",
    response_model=AlertRuleResponse,
    dependencies=[READ],
    summary="Get one alert rule",
)
def get_alert_rule(rule_id: str, db: Annotated[Session, Depends(get_db)]) -> AlertRuleResponse:
    return _to_response(_get_rule(db, rule_id))


@router.put(
    "/alert-rules/{rule_id}",
    response_model=AlertRuleResponse,
    dependencies=[WRITE],
    summary="Update an alert rule",
)
def update_alert_rule(
    rule_id: str,
    payload: AlertRuleUpdateRequest,
    db: Annotated[Session, Depends(get_db)],
) -> AlertRuleResponse:
    row = _get_rule(db, rule_id)
    _ensure_targets(db, payload)
    for key, value in payload.model_dump().items():
        setattr(row, key, value)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise _duplicate_name() from error
    db.refresh(row)
    _notify()
    return _to_response(row)


@router.patch(
    "/alert-rules/{rule_id}/enable",
    response_model=AlertRuleResponse,
    dependencies=[WRITE],
    summary="Enable or disable an alert rule",
)
def enable_alert_rule(
    rule_id: str,
    payload: AlertRuleEnableRequest,
    db: Annotated[Session, Depends(get_db)],
) -> AlertRuleResponse:
    row = _get_rule(db, rule_id)
    row.enabled = payload.enabled
    db.commit()
    db.refresh(row)
    _notify()
    return _to_response(row)


@router.delete(
    "/alert-rules/{rule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[WRITE],
    summary="Delete an alert rule",
    response_class=Response,
)
def delete_alert_rule(rule_id: str, db: Annotated[Session, Depends(get_db)]) -> Response:
    row = _get_rule(db, rule_id)
    db.delete(row)
    db.commit()
    _notify()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
