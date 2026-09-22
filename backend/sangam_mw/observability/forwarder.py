"""
Pluggable async log forwarder.

Configure via env:
  LOG_FORWARDER=elk|azure|loki|datadog|none
  LOG_FORWARDER_URL=https://...
  LOG_FORWARDER_API_KEY=...

Fire-and-forget: forwarder failures never block a flow run.
Batches up to 100 events or 5 seconds, whichever comes first.
"""
from __future__ import annotations

import asyncio
import json
import os
from abc import ABC, abstractmethod
from datetime import datetime, UTC
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

_BATCH_SIZE = 100
_FLUSH_INTERVAL = 5.0


class LogForwarder(ABC):
    @abstractmethod
    async def send(self, events: list[dict[str, Any]]) -> None: ...


class NullForwarder(LogForwarder):
    async def send(self, events: list[dict[str, Any]]) -> None:
        pass


class ELKForwarder(LogForwarder):
    def __init__(self, url: str, api_key: str | None = None) -> None:
        self._url = url.rstrip("/") + "/_bulk"
        self._headers = {"Content-Type": "application/x-ndjson"}
        if api_key:
            self._headers["Authorization"] = f"ApiKey {api_key}"

    async def send(self, events: list[dict[str, Any]]) -> None:
        import aiohttp
        lines = ""
        for ev in events:
            lines += json.dumps({"index": {"_index": "sangam-mw-logs"}}) + "\n"
            lines += json.dumps(ev) + "\n"
        async with aiohttp.ClientSession() as sess:
            async with sess.post(self._url, data=lines, headers=self._headers) as resp:
                if resp.status >= 400:
                    logger.warning("elk_forward_failed", status=resp.status)


class AzureForwarder(LogForwarder):
    def __init__(self, url: str, api_key: str | None = None) -> None:
        self._url = url
        self._headers = {"Content-Type": "application/json"}
        if api_key:
            self._headers["x-api-key"] = api_key

    async def send(self, events: list[dict[str, Any]]) -> None:
        import aiohttp
        body = json.dumps(events)
        async with aiohttp.ClientSession() as sess:
            async with sess.post(self._url, data=body, headers=self._headers) as resp:
                if resp.status >= 400:
                    logger.warning("azure_forward_failed", status=resp.status)


class LokiForwarder(LogForwarder):
    def __init__(self, url: str, api_key: str | None = None) -> None:
        self._url = url.rstrip("/") + "/loki/api/v1/push"
        self._headers = {"Content-Type": "application/json"}
        if api_key:
            self._headers["Authorization"] = f"Bearer {api_key}"

    async def send(self, events: list[dict[str, Any]]) -> None:
        import aiohttp
        now_ns = str(int(datetime.now(UTC).timestamp() * 1e9))
        streams = [
            {
                "stream": {"app": "sangam-mw", "flow_id": ev.get("flow_id", "unknown")},
                "values": [[now_ns, json.dumps(ev)]],
            }
            for ev in events
        ]
        body = json.dumps({"streams": streams})
        async with aiohttp.ClientSession() as sess:
            async with sess.post(self._url, data=body, headers=self._headers) as resp:
                if resp.status >= 400:
                    logger.warning("loki_forward_failed", status=resp.status)


class DatadogForwarder(LogForwarder):
    def __init__(self, url: str, api_key: str | None = None) -> None:
        self._url = url or "https://http-intake.logs.datadoghq.com/api/v2/logs"
        self._headers = {"Content-Type": "application/json"}
        if api_key:
            self._headers["DD-API-KEY"] = api_key

    async def send(self, events: list[dict[str, Any]]) -> None:
        import aiohttp
        body = json.dumps(events)
        async with aiohttp.ClientSession() as sess:
            async with sess.post(self._url, data=body, headers=self._headers) as resp:
                if resp.status >= 400:
                    logger.warning("datadog_forward_failed", status=resp.status)


class BatchingForwarder:
    """Wraps any LogForwarder and batches events before flushing."""

    def __init__(self, inner: LogForwarder) -> None:
        self._inner = inner
        self._buffer: list[dict[str, Any]] = []
        self._lock = asyncio.Lock()
        self._flush_task: asyncio.Task | None = None

    def start(self) -> None:
        self._flush_task = asyncio.create_task(self._periodic_flush())

    async def _periodic_flush(self) -> None:
        while True:
            await asyncio.sleep(_FLUSH_INTERVAL)
            await self.flush()

    async def enqueue(self, event: dict[str, Any]) -> None:
        async with self._lock:
            self._buffer.append(event)
            if len(self._buffer) >= _BATCH_SIZE:
                await self._do_flush()

    async def flush(self) -> None:
        async with self._lock:
            await self._do_flush()

    async def _do_flush(self) -> None:
        if not self._buffer:
            return
        batch, self._buffer = self._buffer, []
        try:
            await self._inner.send(batch)
        except Exception as exc:
            logger.warning("forwarder_flush_error", error=str(exc))


_forwarder: BatchingForwarder | None = None


def get_forwarder() -> BatchingForwarder:
    global _forwarder
    if _forwarder is None:
        kind = os.getenv("LOG_FORWARDER", "none").lower()
        url = os.getenv("LOG_FORWARDER_URL", "")
        api_key = os.getenv("LOG_FORWARDER_API_KEY")
        inner: LogForwarder
        if kind == "elk":
            inner = ELKForwarder(url, api_key)
        elif kind == "azure":
            inner = AzureForwarder(url, api_key)
        elif kind == "loki":
            inner = LokiForwarder(url, api_key)
        elif kind == "datadog":
            inner = DatadogForwarder(url, api_key)
        else:
            inner = NullForwarder()
        _forwarder = BatchingForwarder(inner)
    return _forwarder
