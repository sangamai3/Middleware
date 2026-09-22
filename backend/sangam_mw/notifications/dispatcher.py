"""Notification dispatcher — matches events to rules and fires channels."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from .channels import channel_from_dict
from .rules import AlertRule

logger = logging.getLogger(__name__)

_SUBJECTS = {
    "flow_failed": "Flow failed: {flow_id}",
    "run.failed": "Flow failed: {flow_id}",
    "flow_slow": "Flow slow: {flow_id} ({duration_ms}ms)",
    "run.completed": "Flow completed: {flow_id}",
    "run_completed": "Flow completed: {flow_id}",
    "run.started": "Flow started: {flow_id}",
    "run_started": "Flow started: {flow_id}",
    "error_rate_high": "High error rate on {flow_id}: {error_rate:.1%}",
}


def _format(template: str, context: dict[str, Any]) -> str:
    try:
        return template.format(**{k: v for k, v in context.items() if isinstance(v, (str, int, float))})
    except (KeyError, ValueError):
        return template


class NotificationDispatcher:
    def __init__(self) -> None:
        self._rules: list[AlertRule] = []

    def load_rules(self, rules: list[AlertRule]) -> None:
        self._rules = list(rules)

    def add_rule(self, rule: AlertRule) -> None:
        self._rules.append(rule)

    def remove_rule(self, rule_id: str) -> None:
        self._rules = [r for r in self._rules if r.rule_id != rule_id]

    async def dispatch(self, event_type: str, context: dict[str, Any]) -> list[str]:
        fired: list[str] = []
        matching = [r for r in self._rules if r.matches(event_type, context)]
        if not matching:
            return fired

        subject_tmpl = _SUBJECTS.get(event_type, "SangamMW alert: {flow_id}")
        subject = _format(subject_tmpl, context)
        body = _build_body(event_type, context)

        tasks = []
        for rule in matching:
            for ch_dict in rule.channels:
                try:
                    ch = channel_from_dict(ch_dict)
                    tasks.append((rule.rule_id, ch.send(subject, body, context)))
                except Exception as exc:
                    logger.warning("Bad channel config in rule %s: %s", rule.rule_id, exc)

        results = await asyncio.gather(*[t for _, t in tasks], return_exceptions=True)
        for (rule_id, _), result in zip(tasks, results):
            if isinstance(result, Exception):
                logger.warning("Notification failed for rule %s: %s", rule_id, result)
            elif result:
                fired.append(rule_id)

        return fired


def _build_body(event_type: str, ctx: dict[str, Any]) -> str:
    lines = []
    if ctx.get("flow_id"):
        lines.append(f"Flow: {ctx['flow_id']}")
    if ctx.get("run_id"):
        lines.append(f"Run: {ctx['run_id']}")
    if ctx.get("status"):
        lines.append(f"Status: {ctx['status']}")
    if ctx.get("duration_ms") is not None:
        lines.append(f"Duration: {ctx['duration_ms']}ms")
    if ctx.get("error_message"):
        lines.append(f"Error: {ctx['error_message']}")
    if ctx.get("rows_processed") is not None:
        lines.append(f"Rows processed: {ctx['rows_processed']}")
    return "\n".join(lines) if lines else event_type


_global_dispatcher: NotificationDispatcher | None = None


def get_dispatcher() -> NotificationDispatcher:
    global _global_dispatcher
    if _global_dispatcher is None:
        _global_dispatcher = NotificationDispatcher()
    return _global_dispatcher
