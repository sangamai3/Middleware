"""
Scheduler — APScheduler wrapper for SCHEDULED trigger flows.

Converts FlowDefinition.trigger_config to APScheduler trigger types:
  - cron: {cron: "0 9 * * 1-5"}
  - interval: {interval_seconds: 300}
"""

from __future__ import annotations

import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)

try:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.triggers.interval import IntervalTrigger
    _HAS_APSCHEDULER = True
except ImportError:
    _HAS_APSCHEDULER = False


class FlowScheduler:
    """
    Manage scheduled flows.

    Usage:
        scheduler = FlowScheduler()
        scheduler.start()
        scheduler.add_flow(flow_id="my_flow", trigger_config={"cron": "0 9 * * *"}, callback=fn)
        # ... on shutdown:
        scheduler.stop()
    """

    def __init__(self) -> None:
        if not _HAS_APSCHEDULER:
            logger.warning("APScheduler not installed — scheduling disabled")
            self._scheduler = None
        else:
            self._scheduler = AsyncIOScheduler()

    def start(self) -> None:
        if self._scheduler is not None:
            try:
                self._scheduler.start()
            except Exception as exc:
                logger.warning("Scheduler start failed: %s", exc)

    def stop(self) -> None:
        if self._scheduler is not None and self._scheduler.running:
            self._scheduler.shutdown(wait=False)

    def add_flow(
        self,
        flow_id: str,
        trigger_config: dict[str, Any],
        callback: Callable[..., Any],
    ) -> None:
        if self._scheduler is None:
            logger.warning("Scheduler not available, cannot schedule flow '%s'", flow_id)
            return

        trigger = self._build_trigger(trigger_config)
        self._scheduler.add_job(
            callback,
            trigger=trigger,
            id=f"flow_{flow_id}",
            replace_existing=True,
            kwargs={"flow_id": flow_id},
        )
        logger.info("Scheduled flow '%s' with trigger %s", flow_id, trigger_config)

    def remove_flow(self, flow_id: str) -> None:
        if self._scheduler is None:
            return
        job_id = f"flow_{flow_id}"
        try:
            self._scheduler.remove_job(job_id)
        except Exception:
            pass

    def _build_trigger(self, trigger_config: dict[str, Any]) -> Any:
        if "cron" in trigger_config:
            from .cron_expr import cron_trigger_from_expr

            tz = trigger_config.get("timezone")
            return cron_trigger_from_expr(trigger_config["cron"], timezone=tz)
        if "interval_seconds" in trigger_config:
            return IntervalTrigger(seconds=int(trigger_config["interval_seconds"]))
        raise ValueError(f"Unknown trigger config: {trigger_config}")

    @property
    def running(self) -> bool:
        return self._scheduler is not None and self._scheduler.running


scheduler = FlowScheduler()
