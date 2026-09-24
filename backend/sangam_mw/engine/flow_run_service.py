"""Execute a flow by id (manual, schedule, or API trigger)."""

from __future__ import annotations

import asyncio
import logging

from ..db.base import get_session_factory
from ..db.flow_store import get_flow_definition
from ..models.execution import ExecutionRun
from ..runs.store import put_run
from .events import event_bus
from .executor import FlowExecutor

logger = logging.getLogger(__name__)


async def execute_flow_by_id(
    flow_id: str,
    *,
    trigger_type: str = "schedule",
    triggered_by: str = "scheduler",
) -> ExecutionRun | None:
    async with get_session_factory()() as session:
        flow = await get_flow_definition(session, flow_id)
    if flow is None:
        logger.error("Cannot run flow %s: not found in database", flow_id)
        return None

    def _run() -> ExecutionRun:
        executor = FlowExecutor(bus=event_bus)
        return executor.execute(
            flow=flow,
            trigger_type=trigger_type,
            triggered_by=triggered_by,
        )

    run = await asyncio.to_thread(_run)
    put_run(run)
    logger.info(
        "Flow run finished flow_id=%s run_id=%s status=%s",
        flow_id,
        run.run_id,
        run.status,
    )
    return run
