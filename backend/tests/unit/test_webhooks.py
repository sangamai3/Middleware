"""Unit tests for webhook manager — subscriptions, delivery, signing."""

import hashlib
import hmac
import json

import pytest

from sangam_mw.webhooks.manager import WebhookManager


class TestWebhookManager:
    def _mgr(self):
        return WebhookManager()

    def test_subscribe_creates_subscription(self):
        mgr = self._mgr()
        sub = mgr.subscribe("acme", "https://acme.com/hook", ["flow.completed"], "s3cr3t")
        assert sub.consumer_name == "acme"
        assert sub.url == "https://acme.com/hook"
        assert "flow.completed" in sub.events
        assert sub.is_active

    def test_unsubscribe_deactivates(self):
        mgr = self._mgr()
        sub = mgr.subscribe("corp", "https://corp.io/wh", ["execution.failed"], "key")
        mgr.unsubscribe(sub.sub_id)
        subs = mgr.list_subscriptions("corp")
        assert len(subs) == 0  # list_subscriptions filters to is_active only

    def test_list_subscriptions_filters_by_consumer(self):
        mgr = self._mgr()
        mgr.subscribe("a", "https://a.com/wh", ["flow.created"], "k1")
        mgr.subscribe("b", "https://b.com/wh", ["flow.created"], "k2")
        subs_a = mgr.list_subscriptions("a")
        assert all(s.consumer_name == "a" for s in subs_a)

    def test_sign_produces_hmac_sha256_hex(self):
        mgr = self._mgr()
        secret = "test-secret"
        payload_bytes = b'{"event":"flow.completed"}'
        sig = mgr._sign(payload_bytes, secret)
        expected = hmac.new(secret.encode(), payload_bytes, hashlib.sha256).hexdigest()
        assert sig == expected

    def test_sign_changes_with_payload(self):
        mgr = self._mgr()
        s1 = mgr._sign(b"payload_a", "secret")
        s2 = mgr._sign(b"payload_b", "secret")
        assert s1 != s2

    def test_get_delivery_history_empty_initially(self):
        mgr = self._mgr()
        sub = mgr.subscribe("x", "https://x.com/wh", ["*"], "k")
        history = mgr.get_delivery_history(sub.sub_id)
        assert history == []

    @pytest.mark.asyncio
    async def test_dispatch_routing_by_event(self):
        """dispatch() routes to matching subscriptions only."""
        mgr = self._mgr()

        sub_all = mgr.subscribe("consumer_all", "https://a.com/wh", ["*"], "k1")
        sub_flow = mgr.subscribe("consumer_flow", "https://b.com/wh", ["flow.completed"], "k2")
        sub_exec = mgr.subscribe("consumer_exec", "https://c.com/wh", ["execution.failed"], "k3")

        delivered_to: list[str] = []

        async def _mock_deliver(sub, event_type, payload):
            from sangam_mw.webhooks.manager import WebhookDelivery
            import secrets as _secrets
            delivered_to.append(sub.consumer_name)
            return WebhookDelivery(
                delivery_id=_secrets.token_hex(8),
                sub_id=sub.sub_id,
                event_type=event_type,
                payload=payload,
                status="delivered",
                attempts=1,
                last_attempt_at=None,
                response_code=200,
                response_body=None,
                error=None,
            )

        mgr._deliver = _mock_deliver  # type: ignore[method-assign]
        await mgr.dispatch("flow.completed", {"flow_id": "f1"})

        assert "consumer_all" in delivered_to
        assert "consumer_flow" in delivered_to
        assert "consumer_exec" not in delivered_to
