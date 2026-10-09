import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ModuleResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    module: str
    status: Literal["healthy", "warning", "critical", "unknown"]
    summary: str
    metrics: dict[str, Any] = Field(default_factory=dict)
    diagnostics: dict[str, Any] = Field(default_factory=dict)


class ReportPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    schema_version: str = "1.0"
    observed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    config_revision: int = 0
    modules: list[ModuleResult]


class AgentControl(BaseModel):
    next_report_in: int
    config_revision: int
    configuration: dict[str, Any] | None = None
    minimum_agent_version: str
    latest_agent_version: str
    update_available: bool
    commands: list[dict[str, Any]] = Field(default_factory=list)


class ReportUploadResponse(BaseModel):
    accepted: bool
    duplicate: bool
    report_id: str
    control: AgentControl
