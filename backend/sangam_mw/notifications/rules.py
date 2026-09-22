"""Alert rule models."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class AlertTrigger(str, Enum):
    FLOW_FAILED = "flow_failed"
    FLOW_SLOW = "flow_slow"
    ERROR_RATE_HIGH = "error_rate_high"
    RUN_STARTED = "run_started"
    RUN_COMPLETED = "run_completed"


@dataclass
class AlertRule:
    rule_id: str
    name: str
    trigger: AlertTrigger
    channels: list[dict[str, Any]] = field(default_factory=list)
    flow_ids: list[str] | None = None  # None = match all flows
    conditions: dict[str, Any] = field(default_factory=dict)
    is_active: bool = True
    created_at: str = ""
    updated_at: str = ""

    def matches(self, event_type: str, context: dict[str, Any]) -> bool:
        if not self.is_active:
            return False
        trigger_map = {
            AlertTrigger.FLOW_FAILED: {"run.failed", "flow_failed"},
            AlertTrigger.FLOW_SLOW: {"run.completed", "flow_completed"},
            AlertTrigger.ERROR_RATE_HIGH: {"error_rate_high"},
            AlertTrigger.RUN_STARTED: {"run.started", "run_started"},
            AlertTrigger.RUN_COMPLETED: {"run.completed", "run_completed"},
        }
        if event_type not in trigger_map.get(self.trigger, set()):
            return False

        if self.flow_ids is not None:
            flow_id = context.get("flow_id")
            if flow_id not in self.flow_ids:
                return False

        if self.trigger == AlertTrigger.FLOW_SLOW:
            threshold = self.conditions.get("threshold_ms", 30_000)
            duration = context.get("duration_ms", 0)
            if duration < threshold:
                return False

        if self.trigger == AlertTrigger.ERROR_RATE_HIGH:
            threshold = self.conditions.get("error_rate_threshold", 0.1)
            rate = context.get("error_rate", 0.0)
            if rate < threshold:
                return False

        return True
