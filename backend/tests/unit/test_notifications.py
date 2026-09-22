"""Unit tests for notification engine (channels, rules, dispatcher)."""
from __future__ import annotations

import pytest

from sangam_mw.notifications.channels import SlackChannel, WebhookChannel, channel_from_dict
from sangam_mw.notifications.dispatcher import NotificationDispatcher, _build_body
from sangam_mw.notifications.rules import AlertRule, AlertTrigger


# ── Channel construction ──────────────────────────────────────────────────────

class TestChannelFromDict:
    def test_slack_channel(self):
        ch = channel_from_dict({"channel_type": "slack", "webhook_url": "https://hooks.slack.com/x"})
        assert isinstance(ch, SlackChannel)
        assert ch.webhook_url == "https://hooks.slack.com/x"

    def test_webhook_channel(self):
        ch = channel_from_dict({"channel_type": "webhook", "url": "https://my.app/hook", "secret": "abc"})
        assert isinstance(ch, WebhookChannel)
        assert ch.url == "https://my.app/hook"
        assert ch.secret == "abc"

    def test_unknown_type_raises(self):
        with pytest.raises(ValueError, match="Unknown channel type"):
            channel_from_dict({"channel_type": "email"})

    def test_slack_defaults(self):
        ch = channel_from_dict({"channel_type": "slack"})
        assert isinstance(ch, SlackChannel)
        assert ch.username == "SangamMW"
        assert ch.icon_emoji == ":zap:"


# ── AlertRule.matches ─────────────────────────────────────────────────────────

class TestAlertRuleMatches:
    def _rule(self, trigger: AlertTrigger, flow_ids=None, conditions=None, is_active=True):
        return AlertRule(
            rule_id="r1",
            name="test",
            trigger=trigger,
            flow_ids=flow_ids,
            conditions=conditions or {},
            is_active=is_active,
        )

    def test_flow_failed_matches(self):
        rule = self._rule(AlertTrigger.FLOW_FAILED)
        assert rule.matches("run.failed", {"flow_id": "f1"})

    def test_flow_failed_wrong_event(self):
        rule = self._rule(AlertTrigger.FLOW_FAILED)
        assert not rule.matches("run.completed", {"flow_id": "f1"})

    def test_inactive_rule_never_matches(self):
        rule = self._rule(AlertTrigger.FLOW_FAILED, is_active=False)
        assert not rule.matches("run.failed", {"flow_id": "f1"})

    def test_flow_id_filter_match(self):
        rule = self._rule(AlertTrigger.FLOW_FAILED, flow_ids=["allowed-flow"])
        assert rule.matches("run.failed", {"flow_id": "allowed-flow"})

    def test_flow_id_filter_no_match(self):
        rule = self._rule(AlertTrigger.FLOW_FAILED, flow_ids=["allowed-flow"])
        assert not rule.matches("run.failed", {"flow_id": "other-flow"})

    def test_flow_id_none_matches_all(self):
        rule = self._rule(AlertTrigger.FLOW_FAILED, flow_ids=None)
        assert rule.matches("run.failed", {"flow_id": "any-flow"})

    def test_flow_slow_above_threshold(self):
        rule = self._rule(AlertTrigger.FLOW_SLOW, conditions={"threshold_ms": 1000})
        assert rule.matches("run.completed", {"flow_id": "f1", "duration_ms": 5000})

    def test_flow_slow_below_threshold(self):
        rule = self._rule(AlertTrigger.FLOW_SLOW, conditions={"threshold_ms": 10_000})
        assert not rule.matches("run.completed", {"flow_id": "f1", "duration_ms": 500})

    def test_error_rate_high_above_threshold(self):
        rule = self._rule(AlertTrigger.ERROR_RATE_HIGH, conditions={"error_rate_threshold": 0.1})
        assert rule.matches("error_rate_high", {"flow_id": "f1", "error_rate": 0.5})

    def test_error_rate_high_below_threshold(self):
        rule = self._rule(AlertTrigger.ERROR_RATE_HIGH, conditions={"error_rate_threshold": 0.5})
        assert not rule.matches("error_rate_high", {"flow_id": "f1", "error_rate": 0.1})

    def test_run_started_matches(self):
        rule = self._rule(AlertTrigger.RUN_STARTED)
        assert rule.matches("run.started", {"flow_id": "f1"})

    def test_run_completed_matches(self):
        rule = self._rule(AlertTrigger.RUN_COMPLETED)
        assert rule.matches("run.completed", {"flow_id": "f1"})


# ── Dispatcher ────────────────────────────────────────────────────────────────

class TestNotificationDispatcher:
    def _dispatcher(self, rules=None):
        d = NotificationDispatcher()
        if rules:
            d.load_rules(rules)
        return d

    def _rule(self, trigger: AlertTrigger, channels=None, is_active=True):
        return AlertRule(
            rule_id="r1",
            name="test",
            trigger=trigger,
            channels=channels or [],
            is_active=is_active,
        )

    @pytest.mark.asyncio
    async def test_no_rules_returns_empty(self):
        d = self._dispatcher()
        fired = await d.dispatch("run.failed", {"flow_id": "f1"})
        assert fired == []

    @pytest.mark.asyncio
    async def test_no_matching_rules_returns_empty(self):
        rule = self._rule(AlertTrigger.RUN_STARTED)
        d = self._dispatcher([rule])
        fired = await d.dispatch("run.failed", {"flow_id": "f1"})
        assert fired == []

    @pytest.mark.asyncio
    async def test_matching_rule_no_channels_fires_nothing(self):
        rule = self._rule(AlertTrigger.FLOW_FAILED, channels=[])
        d = self._dispatcher([rule])
        fired = await d.dispatch("run.failed", {"flow_id": "f1"})
        assert fired == []

    def test_add_and_remove_rule(self):
        d = NotificationDispatcher()
        rule = self._rule(AlertTrigger.FLOW_FAILED)
        d.add_rule(rule)
        assert any(r.rule_id == "r1" for r in d._rules)
        d.remove_rule("r1")
        assert not any(r.rule_id == "r1" for r in d._rules)

    def test_load_rules_replaces(self):
        d = NotificationDispatcher()
        d.add_rule(self._rule(AlertTrigger.FLOW_FAILED))
        d.load_rules([self._rule(AlertTrigger.RUN_STARTED)])
        assert len(d._rules) == 1
        assert d._rules[0].trigger == AlertTrigger.RUN_STARTED


# ── _build_body ───────────────────────────────────────────────────────────────

class TestBuildBody:
    def test_includes_flow_id(self):
        body = _build_body("run.failed", {"flow_id": "my-flow", "status": "failed"})
        assert "my-flow" in body
        assert "failed" in body

    def test_includes_error_message(self):
        body = _build_body("run.failed", {"flow_id": "f", "error_message": "DB timeout"})
        assert "DB timeout" in body

    def test_empty_context_returns_event_type(self):
        body = _build_body("run.failed", {})
        assert body == "run.failed"
