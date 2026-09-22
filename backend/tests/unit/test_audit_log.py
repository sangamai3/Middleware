"""Unit tests for the hash-chained audit log."""

from datetime import UTC, datetime

import pytest

from sangam_mw.audit.log import AuditAction, AuditEvent, _compute_hash


def _event(**kwargs) -> AuditEvent:
    defaults = dict(
        actor_id="user-1",
        action=AuditAction.USER_LOGIN,
        resource_type="user",
        resource_id="u1",
    )
    defaults.update(kwargs)
    return AuditEvent(**defaults)


TS = datetime(2026, 1, 1, tzinfo=UTC)


class TestComputeHash:
    def test_deterministic(self):
        e = _event()
        h1 = _compute_hash("prev", e, TS)
        h2 = _compute_hash("prev", e, TS)
        assert h1 == h2

    def test_different_prev_hash_produces_different_result(self):
        e = _event()
        h1 = _compute_hash("prev_aaa", e, TS)
        h2 = _compute_hash("prev_bbb", e, TS)
        assert h1 != h2

    def test_different_actor_produces_different_result(self):
        h1 = _compute_hash("prev", _event(actor_id="alice"), TS)
        h2 = _compute_hash("prev", _event(actor_id="bob"), TS)
        assert h1 != h2

    def test_different_action_produces_different_result(self):
        h1 = _compute_hash("prev", _event(action=AuditAction.USER_LOGIN), TS)
        h2 = _compute_hash("prev", _event(action=AuditAction.FLOW_CREATED), TS)
        assert h1 != h2

    def test_output_is_sha256_hex(self):
        h = _compute_hash("p", _event(), TS)
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_genesis_hash(self):
        genesis_prev = "0" * 64
        h = _compute_hash(genesis_prev, _event(), TS)
        assert len(h) == 64
        assert h != genesis_prev

    def test_timestamp_matters(self):
        e = _event()
        ts2 = datetime(2026, 6, 1, tzinfo=UTC)
        h1 = _compute_hash("p", e, TS)
        h2 = _compute_hash("p", e, ts2)
        assert h1 != h2


class TestAuditActionEnum:
    def test_all_actions_are_strings(self):
        for action in AuditAction:
            assert isinstance(action.value, str)
            assert "." in action.value

    def test_required_actions_present(self):
        values = {a.value for a in AuditAction}
        required = [
            "user.login", "flow.created", "flow.deployed",
            "execution.triggered", "connection.created",
        ]
        for r in required:
            assert r in values, f"AuditAction missing: {r}"
