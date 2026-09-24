"""Parse stored cron strings into APScheduler triggers (5- or 6-field)."""

from __future__ import annotations

from typing import Any


def cron_field_count(expr: str) -> int:
    return len(expr.strip().split())


def validate_cron_expr(expr: str) -> None:
    """Raise ValueError if expression is not 5 or 6 fields."""
    n = cron_field_count(expr)
    if n not in (5, 6):
        raise ValueError(f"Expected 5 or 6 cron fields, got {n}")


def cron_trigger_from_expr(expr: str, timezone: str | None = None) -> Any:
    from apscheduler.triggers.cron import CronTrigger

    parts = expr.strip().split()
    tz_kw = {} if timezone is None else {"timezone": timezone}
    if len(parts) == 5:
        return CronTrigger.from_crontab(expr, **tz_kw)
    if len(parts) == 6:
        second, minute, hour, day, month, day_of_week = parts
        return CronTrigger(
            second=second,
            minute=minute,
            hour=hour,
            day=day,
            month=month,
            day_of_week=day_of_week,
            **tz_kw,
        )
    raise ValueError(f"Invalid cron expression: {expr!r}")
