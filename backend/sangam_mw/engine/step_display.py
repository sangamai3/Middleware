"""Human-readable step labels for runs, logs, and observability."""

from __future__ import annotations

from ..models.flow import StepConfig

_STEP_ROLE: dict[str, str] = {
    "connector_read": "Source",
    "connector_write": "Target",
    "transform_format": "Format Convert",
    "transform_map": "Map Fields",
    "transform_filter": "Filter",
    "transform_sql": "SQL",
    "transform_script": "Script",
    "router": "Router",
    "merge": "Merge",
    "iterator": "Iterator",
    "sub_flow": "Sub-flow",
    "set_variable": "Set Variable",
    "logger": "Logger",
    "approval": "Approval",
    "notification": "Notification",
    "sync_endpoint": "Sync Endpoint",
    "scheduler": "Scheduler",
    "webhook_trigger": "Webhook",
    "streaming_trigger": "Streaming",
    "event_trigger": "Event",
}

_CONNECTOR_LABEL: dict[str, str] = {
    "file": "File",
    "postgres": "PostgreSQL",
    "aws-s3": "Amazon S3",
    "salesforce": "Salesforce",
    "rest-api": "REST API",
}


def _humanize_step_type(step_type: str) -> str:
    return step_type.replace("_", " ").strip().title()


def step_connector_id(step: StepConfig) -> str | None:
    cid = step.config.get("connector_id")
    if cid is None or cid == "":
        return None
    return str(cid)


def step_display_name(step: StepConfig) -> str:
    """
    Build a run-timeline label, e.g.:
      Source · File · *.csv
      Export orders · File · orders_a.csv
      Format Convert
    """
    config = step.config or {}
    role = _STEP_ROLE.get(step.type, _humanize_step_type(step.type))
    user_label = str(config.get("label") or "").strip()
    title = user_label if user_label and user_label != role else role

    segments: list[str] = [title]

    connector_id = step_connector_id(step)
    if connector_id:
        segments.append(_CONNECTOR_LABEL.get(connector_id, connector_id.replace("-", " ").title()))

    obj = str(config.get("object") or "").strip()
    if obj and step.type in ("connector_read", "connector_write"):
        segments.append(obj)

    return " · ".join(segments)
