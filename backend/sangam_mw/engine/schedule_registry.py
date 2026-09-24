"""
Sync ScheduledFlowTable rows with APScheduler and run flows on trigger.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from ..db.base import get_session_factory
from ..db.tables import ScheduledFlowTable
from .flow_run_service import execute_flow_by_id
from .scheduler import scheduler

logger = logging.getLogger(__name__)


def row_to_trigger_config(row: ScheduledFlowTable) -> dict[str, Any]:
    if row.cron_expr:
        return {"cron": row.cron_expr, "timezone": row.timezone or "UTC"}
    if row.interval_seconds:
        return {"interval_seconds": int(row.interval_seconds)}
    raise ValueError(f"Schedule for {row.flow_id!r} has no cron or interval")


async def _on_scheduled_tick(flow_id: str) -> None:
    try:
        await execute_flow_by_id(flow_id, trigger_type="schedule", triggered_by="scheduler")
        await touch_last_run(flow_id)
    except Exception:
        logger.exception("Scheduled run failed for flow %s", flow_id)


async def touch_last_run(flow_id: str) -> None:
    async with get_session_factory()() as session:
        result = await session.execute(
            select(ScheduledFlowTable).where(ScheduledFlowTable.flow_id == flow_id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return
        row.last_run_at = datetime.now(UTC)
        await session.commit()


def apply_schedule_row(row: ScheduledFlowTable | None, flow_id: str) -> None:
    """Register, update, or remove an APScheduler job for this flow."""
    if row is None or not row.is_active:
        scheduler.remove_flow(flow_id)
        return
    try:
        trigger_config = row_to_trigger_config(row)
    except ValueError as exc:
        logger.warning("Skipping schedule for %s: %s", flow_id, exc)
        scheduler.remove_flow(flow_id)
        return
    scheduler.add_flow(flow_id, trigger_config, _on_scheduled_tick)


def remove_schedule(flow_id: str) -> None:
    scheduler.remove_flow(flow_id)


async def load_all_active_schedules() -> int:
    """Load every active job from DB into APScheduler. Returns count registered."""
    async with get_session_factory()() as session:
        result = await session.execute(
            select(ScheduledFlowTable).where(ScheduledFlowTable.is_active.is_(True))
        )
        rows = list(result.scalars().all())

    for row in rows:
        apply_schedule_row(row, row.flow_id)

    logger.info("Loaded %s active scheduled flow(s) into APScheduler", len(rows))
    return len(rows)


async def bootstrap_scheduler() -> None:
    scheduler.start()
    await load_all_active_schedules()


async def shutdown_scheduler() -> None:
    scheduler.stop()
