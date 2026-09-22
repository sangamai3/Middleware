"""
Structured event emitter + in-memory EventBus for SSE streaming.

Events follow the schema:
  {type, run_id, flow_id, step_id, timestamp, payload}

The EventBus holds a circular buffer of events per run_id and delivers
them to async subscribers (SSE connections).
"""

from __future__ import annotations

import asyncio
import time
from collections import deque
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any


class EventType(str, Enum):
    RUN_STARTED = "run.started"
    RUN_COMPLETED = "run.completed"
    RUN_FAILED = "run.failed"
    STEP_STARTED = "step.started"
    STEP_COMPLETED = "step.completed"
    STEP_FAILED = "step.failed"
    STEP_RETRYING = "step.retrying"
    STEP_SKIPPED = "step.skipped"
    LOG = "log"


@dataclass
class FlowEvent:
    type: EventType
    run_id: str
    flow_id: str
    timestamp: float = field(default_factory=time.time)
    step_id: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["type"] = self.type.value
        return d

    def as_sse(self) -> str:
        import json
        return f"data: {json.dumps(self.as_dict())}\n\n"


class EventBus:
    """
    In-memory pub/sub for flow execution events.

    Multiple SSE subscribers can attach to a run; events are buffered
    per run_id so late subscribers can replay recent events.
    """

    def __init__(self, buffer_size: int = 500) -> None:
        self._buffer_size = buffer_size
        self._buffers: dict[str, deque[FlowEvent]] = {}
        self._queues: dict[str, list[asyncio.Queue[FlowEvent | None]]] = {}

    def emit(self, event: FlowEvent) -> None:
        run_id = event.run_id
        if run_id not in self._buffers:
            self._buffers[run_id] = deque(maxlen=self._buffer_size)
        self._buffers[run_id].append(event)

        for q in self._queues.get(run_id, []):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                pass

    def subscribe(self, run_id: str) -> "Subscription":
        q: asyncio.Queue[FlowEvent | None] = asyncio.Queue(maxsize=self._buffer_size)
        # Replay buffered events first
        for evt in self._buffers.get(run_id, []):
            try:
                q.put_nowait(evt)
            except asyncio.QueueFull:
                break
        self._queues.setdefault(run_id, []).append(q)
        return Subscription(run_id=run_id, queue=q, bus=self)

    def unsubscribe(self, run_id: str, queue: "asyncio.Queue[FlowEvent | None]") -> None:
        qs = self._queues.get(run_id, [])
        if queue in qs:
            qs.remove(queue)

    def close_run(self, run_id: str) -> None:
        """Signal all subscribers that the run is done."""
        for q in self._queues.get(run_id, []):
            try:
                q.put_nowait(None)  # sentinel
            except asyncio.QueueFull:
                pass
        self._queues.pop(run_id, None)


@dataclass
class Subscription:
    run_id: str
    queue: asyncio.Queue
    bus: EventBus

    async def __aiter__(self):
        while True:
            event = await self.queue.get()
            if event is None:
                break
            yield event

    def close(self) -> None:
        self.bus.unsubscribe(self.run_id, self.queue)


# Module-level singleton shared across the app
event_bus = EventBus()
