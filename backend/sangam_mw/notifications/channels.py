"""Notification channel implementations."""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import httpx

logger = logging.getLogger(__name__)


@dataclass
class Channel(ABC):
    channel_type: str

    @abstractmethod
    async def send(self, subject: str, body: str, context: dict[str, Any]) -> bool:
        ...


@dataclass
class SlackChannel(Channel):
    channel_type: str = "slack"
    webhook_url: str = ""
    username: str = "SangamMW"
    icon_emoji: str = ":zap:"

    async def send(self, subject: str, body: str, context: dict[str, Any]) -> bool:
        if not self.webhook_url:
            return False
        flow_id = context.get("flow_id", "")
        status = context.get("status", "")
        color = "#ef4444" if status in ("failed", "error") else "#16a34a"
        payload = {
            "username": self.username,
            "icon_emoji": self.icon_emoji,
            "attachments": [
                {
                    "color": color,
                    "title": subject,
                    "text": body,
                    "fields": [
                        {"title": "Flow", "value": flow_id, "short": True},
                        {"title": "Status", "value": status, "short": True},
                    ],
                    "footer": "SangamMW",
                }
            ],
        }
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.post(self.webhook_url, json=payload)
                return r.status_code == 200
        except Exception as exc:
            logger.warning("Slack notification failed: %s", exc)
            return False


@dataclass
class WebhookChannel(Channel):
    channel_type: str = "webhook"
    url: str = ""
    secret: str = ""
    headers: dict[str, str] = field(default_factory=dict)

    async def send(self, subject: str, body: str, context: dict[str, Any]) -> bool:
        if not self.url:
            return False
        payload = {"subject": subject, "body": body, **context}
        payload_bytes = json.dumps(payload).encode()
        headers = {"Content-Type": "application/json", **self.headers}
        if self.secret:
            sig = hmac.new(self.secret.encode(), payload_bytes, hashlib.sha256).hexdigest()
            headers["X-SangamMW-Signature"] = f"sha256={sig}"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.post(self.url, content=payload_bytes, headers=headers)
                return r.status_code < 300
        except Exception as exc:
            logger.warning("Webhook notification failed: %s", exc)
            return False


def channel_from_dict(d: dict[str, Any]) -> Channel:
    ct = d.get("channel_type", "")
    if ct == "slack":
        return SlackChannel(
            webhook_url=d.get("webhook_url", ""),
            username=d.get("username", "SangamMW"),
            icon_emoji=d.get("icon_emoji", ":zap:"),
        )
    if ct == "webhook":
        return WebhookChannel(
            url=d.get("url", ""),
            secret=d.get("secret", ""),
            headers=d.get("headers", {}),
        )
    raise ValueError(f"Unknown channel type: {ct!r}")
