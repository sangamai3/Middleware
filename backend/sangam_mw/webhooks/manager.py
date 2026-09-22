"""
Outbound webhook delivery manager.

Registers consumer webhook subscriptions, delivers payloads with HMAC-SHA256
signatures, retries with exponential backoff, maintains delivery history.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class WebhookSubscription:
    sub_id: str
    consumer_name: str
    url: str
    events: list[str]
    secret: str
    is_active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class WebhookDelivery:
    delivery_id: str
    sub_id: str
    event_type: str
    payload: dict[str, Any]
    status: str
    attempts: int
    last_attempt_at: datetime | None
    response_code: int | None
    response_body: str | None
    error: str | None


class WebhookManager:
    MAX_ATTEMPTS = 5
    BACKOFF_BASE = 2

    def __init__(self) -> None:
        self._subscriptions: dict[str, WebhookSubscription] = {}
        self._deliveries: dict[str, WebhookDelivery] = {}

    def subscribe(
        self,
        consumer_name: str,
        url: str,
        events: list[str],
        secret: str | None = None,
    ) -> WebhookSubscription:
        sub_id = secrets.token_hex(8)
        sub = WebhookSubscription(
            sub_id=sub_id,
            consumer_name=consumer_name,
            url=url,
            events=events,
            secret=secret or secrets.token_hex(32),
        )
        self._subscriptions[sub_id] = sub
        return sub

    def unsubscribe(self, sub_id: str) -> bool:
        if sub_id in self._subscriptions:
            self._subscriptions[sub_id].is_active = False
            return True
        return False

    def list_subscriptions(self, consumer_name: str | None = None) -> list[WebhookSubscription]:
        subs = [s for s in self._subscriptions.values() if s.is_active]
        if consumer_name:
            subs = [s for s in subs if s.consumer_name == consumer_name]
        return subs

    def _sign(self, payload_bytes: bytes, secret: str) -> str:
        return hmac.new(secret.encode(), payload_bytes, hashlib.sha256).hexdigest()

    async def dispatch(self, event_type: str, payload: dict[str, Any]) -> list[WebhookDelivery]:
        deliveries = []
        for sub in self._subscriptions.values():
            if not sub.is_active:
                continue
            if sub.events and event_type not in sub.events and "*" not in sub.events:
                continue
            delivery = await self._deliver(sub, event_type, payload)
            deliveries.append(delivery)
        return deliveries

    async def _deliver(
        self,
        sub: WebhookSubscription,
        event_type: str,
        payload: dict[str, Any],
    ) -> WebhookDelivery:
        delivery_id = secrets.token_hex(8)
        body = {
            "event": event_type,
            "timestamp": datetime.now(UTC).isoformat(),
            "delivery_id": delivery_id,
            "data": payload,
        }
        payload_bytes = json.dumps(body, separators=(",", ":")).encode()
        signature = self._sign(payload_bytes, sub.secret)

        delivery = WebhookDelivery(
            delivery_id=delivery_id,
            sub_id=sub.sub_id,
            event_type=event_type,
            payload=body,
            status="pending",
            attempts=0,
            last_attempt_at=None,
            response_code=None,
            response_body=None,
            error=None,
        )
        self._deliveries[delivery_id] = delivery

        for attempt in range(self.MAX_ATTEMPTS):
            delivery.attempts = attempt + 1
            delivery.last_attempt_at = datetime.now(UTC)
            try:
                result_code, result_body = await self._post(
                    sub.url, payload_bytes, signature
                )
                delivery.response_code = result_code
                delivery.response_body = result_body[:500] if result_body else None
                if 200 <= result_code < 300:
                    delivery.status = "delivered"
                    break
                delivery.status = "failed"
                delivery.error = f"HTTP {result_code}"
            except Exception as exc:
                delivery.status = "failed"
                delivery.error = str(exc)

            if attempt < self.MAX_ATTEMPTS - 1:
                backoff = self.BACKOFF_BASE ** attempt
                time.sleep(min(backoff, 30))

        if delivery.status == "failed" and delivery.attempts >= self.MAX_ATTEMPTS:
            delivery.status = "dead_lettered"

        return delivery

    async def _post(self, url: str, payload_bytes: bytes, signature: str) -> tuple[int, str]:
        headers = {
            "Content-Type": "application/json",
            "X-SangamMW-Signature": f"sha256={signature}",
            "X-SangamMW-Delivery": "1",
        }
        try:
            import httpx  # type: ignore[import]
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(url, content=payload_bytes, headers=headers)
                return resp.status_code, resp.text
        except ImportError:
            pass

        import urllib.request
        req = urllib.request.Request(url, data=payload_bytes, method="POST")
        for k, v in headers.items():
            req.add_header(k, v)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status, resp.read().decode()
        except Exception as exc:
            raise RuntimeError(f"Delivery failed: {exc}") from exc

    def get_delivery_history(self, sub_id: str | None = None) -> list[WebhookDelivery]:
        deliveries = list(self._deliveries.values())
        if sub_id:
            deliveries = [d for d in deliveries if d.sub_id == sub_id]
        return sorted(deliveries, key=lambda d: d.last_attempt_at or datetime.min, reverse=True)

    async def redeliver(self, delivery_id: str) -> WebhookDelivery | None:
        original = self._deliveries.get(delivery_id)
        if not original:
            return None
        sub = self._subscriptions.get(original.sub_id)
        if not sub:
            return None
        return await self._deliver(sub, original.event_type, original.payload.get("data", {}))
