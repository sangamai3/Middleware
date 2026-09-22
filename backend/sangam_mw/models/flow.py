from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class FlowStatus(StrEnum):
    DRAFT = "draft"
    DEPLOYED = "deployed"
    PAUSED = "paused"
    ARCHIVED = "archived"


class TriggerType(StrEnum):
    MANUAL = "manual"
    SCHEDULED = "scheduled"
    WEBHOOK = "webhook"
    STREAMING = "streaming"
    API = "api"


class StepConfig(BaseModel):
    id: str
    type: str
    config: dict = Field(default_factory=dict)
    depends_on: list[str] = Field(default_factory=list)
    retries: int = 0
    retry_delay: str = "exponential"
    retry_on: list[str] = Field(default_factory=list)
    timeout_seconds: int | None = None
    on_row_error: str = "fail"
    error_threshold: str | None = None
    optional: bool = False


class FlowDefinition(BaseModel):
    flow_id: str
    name: str
    description: str = ""
    version: str = "1"
    status: FlowStatus = FlowStatus.DRAFT
    trigger: TriggerType = TriggerType.MANUAL
    trigger_config: dict = Field(default_factory=dict)
    steps: list[StepConfig] = Field(default_factory=list)
    error_handler: dict = Field(default_factory=dict)
    dead_letter: dict | None = None
    variables: dict = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None
    created_by: str = ""
