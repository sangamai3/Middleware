from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class RunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"


class StepStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    RETRYING = "retrying"
    SKIPPED = "skipped"


class StepExecution(BaseModel):
    step_id: str
    step_type: str
    status: StepStatus = StepStatus.PENDING
    started_at: datetime | None = None
    ended_at: datetime | None = None
    duration_ms: int | None = None
    rows_in: int = 0
    rows_out: int = 0
    rows_failed: int = 0
    error_type: str | None = None
    error_message: str | None = None
    retry_count: int = 0


class ExecutionRun(BaseModel):
    run_id: str
    flow_id: str
    trigger_type: str = "manual"
    status: RunStatus = RunStatus.PENDING
    started_at: datetime | None = None
    ended_at: datetime | None = None
    rows_processed: int = 0
    rows_failed: int = 0
    rows_written: int = 0
    steps: list[StepExecution] = Field(default_factory=list)
    error_message: str | None = None
    triggered_by: str = ""
