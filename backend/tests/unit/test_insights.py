"""Unit tests for Phase 14 — observability persistence helpers."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# TestMetricsBucket
# ---------------------------------------------------------------------------

class TestMetricsBucketUpsert:
    """upsert_metrics_bucket creates and increments correctly."""

    def _make_session_ctx(self, existing_bucket=None):
        session = MagicMock()
        session.add = MagicMock()
        session.commit = AsyncMock()

        async def _exec(stmt):
            result = MagicMock()
            result.scalar_one_or_none.return_value = existing_bucket
            return result

        session.execute = _exec

        async def _aenter(s):
            return session

        async def _aexit(s, *a):
            pass

        cm = MagicMock()
        cm.__aenter__ = _aenter
        cm.__aexit__ = _aexit
        return cm, session

    def test_creates_new_bucket(self):
        from sangam_mw.db.tables import MetricsBucketTable
        cm, session = self._make_session_ctx(existing_bucket=None)
        with patch("sangam_mw.observability.persistence.get_session_factory", return_value=lambda: cm):
            asyncio.run(_upsert("flow-1", 500, "success", 100))
        session.add.assert_called_once()
        row = session.add.call_args[0][0]
        assert isinstance(row, MetricsBucketTable)
        assert row.flow_id == "flow-1"
        assert row.run_count == 1
        assert row.error_count == 0
        assert row.total_rows == 100
        assert row.total_duration_ms == 500

    def test_increments_existing_bucket(self):
        existing = MagicMock()
        existing.run_count = 5
        existing.error_count = 1
        existing.total_rows = 500
        existing.total_duration_ms = 2500
        existing.p95_ms = 600
        existing.p99_ms = 700
        cm, session = self._make_session_ctx(existing_bucket=existing)
        with patch("sangam_mw.observability.persistence.get_session_factory", return_value=lambda: cm):
            asyncio.run(_upsert("flow-1", 300, "success", 50))
        assert existing.run_count == 6
        assert existing.total_rows == 550
        assert existing.total_duration_ms == 2800

    def test_error_count_incremented_on_failure(self):
        existing = MagicMock()
        existing.run_count = 3
        existing.error_count = 0
        existing.total_rows = 300
        existing.total_duration_ms = 900
        existing.p95_ms = 0
        existing.p99_ms = 0
        cm, session = self._make_session_ctx(existing_bucket=existing)
        with patch("sangam_mw.observability.persistence.get_session_factory", return_value=lambda: cm):
            asyncio.run(_upsert("flow-1", 200, "failed", 0))
        assert existing.error_count == 1

    def test_p99_tracks_max(self):
        existing = MagicMock()
        existing.run_count = 2
        existing.error_count = 0
        existing.total_rows = 200
        existing.total_duration_ms = 1000
        existing.p95_ms = 500
        existing.p99_ms = 500
        cm, session = self._make_session_ctx(existing_bucket=existing)
        with patch("sangam_mw.observability.persistence.get_session_factory", return_value=lambda: cm):
            asyncio.run(_upsert("flow-1", 800, "success", 50))
        assert existing.p99_ms == 800


# ---------------------------------------------------------------------------
# TestAppendLog
# ---------------------------------------------------------------------------

class TestAppendLog:
    """append_log writes correctly to ExecutionLogTable."""

    def _make_session_ctx(self):
        session = MagicMock()
        session.add = MagicMock()
        session.commit = AsyncMock()
        cm = MagicMock()
        cm.__aenter__ = lambda s: asyncio.coroutine(lambda: session)()
        # Use proper async context manager
        async def _aenter(s):
            return session
        async def _aexit(s, *a):
            pass
        cm.__aenter__ = _aenter
        cm.__aexit__ = _aexit
        return cm, session

    def test_log_added_with_correct_fields(self):
        from sangam_mw.db.tables import ExecutionLogTable
        cm, session = self._make_session_ctx()
        with patch("sangam_mw.observability.persistence.get_session_factory", return_value=lambda: cm):
            with patch("asyncio.create_task"):
                asyncio.run(_append_log("run-1", "flow-1", "Hello world", "INFO", "step-a", "corr-1"))
        session.add.assert_called_once()
        row = session.add.call_args[0][0]
        assert isinstance(row, ExecutionLogTable)
        assert row.run_id == "run-1"
        assert row.flow_id == "flow-1"
        assert row.step_id == "step-a"
        assert row.level == "INFO"
        assert row.message == "Hello world"
        assert row.correlation_id == "corr-1"

    def test_level_uppercased(self):
        from sangam_mw.db.tables import ExecutionLogTable
        cm, session = self._make_session_ctx()
        with patch("sangam_mw.observability.persistence.get_session_factory", return_value=lambda: cm):
            with patch("asyncio.create_task"):
                asyncio.run(_append_log("run-1", "flow-1", "warn msg", "warn"))
        row = session.add.call_args[0][0]
        assert row.level == "WARN"

    def test_payload_preview_truncated_at_512(self):
        from sangam_mw.db.tables import ExecutionLogTable
        cm, session = self._make_session_ctx()
        big_payload = {"data": "x" * 1000}
        with patch("sangam_mw.observability.persistence.get_session_factory", return_value=lambda: cm):
            with patch("asyncio.create_task"):
                asyncio.run(_append_log("run-1", "flow-1", "msg", "INFO", payload=big_payload))
        row = session.add.call_args[0][0]
        assert len(row.payload_preview) <= 512

    def test_null_payload_no_preview(self):
        from sangam_mw.db.tables import ExecutionLogTable
        cm, session = self._make_session_ctx()
        with patch("sangam_mw.observability.persistence.get_session_factory", return_value=lambda: cm):
            with patch("asyncio.create_task"):
                asyncio.run(_append_log("run-1", "flow-1", "msg", "INFO", payload=None))
        row = session.add.call_args[0][0]
        assert row.payload_preview is None


# ---------------------------------------------------------------------------
# TestBusinessEvent
# ---------------------------------------------------------------------------

class TestBusinessEvent:
    """_emit_business_event stores correct fields."""

    def _make_session_ctx(self):
        session = MagicMock()
        session.add = MagicMock()
        session.commit = AsyncMock()
        cm = MagicMock()
        async def _aenter(s):
            return session
        async def _aexit(s, *a):
            pass
        cm.__aenter__ = _aenter
        cm.__aexit__ = _aexit
        return cm, session

    def test_fields_stored_correctly(self):
        from sangam_mw.db.tables import BusinessEventTable
        cm, session = self._make_session_ctx()
        with patch("sangam_mw.observability.persistence.get_session_factory", return_value=lambda: cm):
            asyncio.run(_emit_be("flow-1", "run-1", "order.created", {"id": 42}, "step-x", "corr-99"))
        row = session.add.call_args[0][0]
        assert isinstance(row, BusinessEventTable)
        assert row.flow_id == "flow-1"
        assert row.run_id == "run-1"
        assert row.event_name == "order.created"
        assert row.payload == {"id": 42}
        assert row.correlation_id == "corr-99"

    def test_correlation_id_propagated(self):
        cm, session = self._make_session_ctx()
        with patch("sangam_mw.observability.persistence.get_session_factory", return_value=lambda: cm):
            asyncio.run(_emit_be("f", "r", "my.event", {}, correlation_id="abc-123"))
        row = session.add.call_args[0][0]
        assert row.correlation_id == "abc-123"

    def test_empty_payload_stored(self):
        cm, session = self._make_session_ctx()
        with patch("sangam_mw.observability.persistence.get_session_factory", return_value=lambda: cm):
            asyncio.run(_emit_be("f", "r", "ping", {}))
        row = session.add.call_args[0][0]
        assert row.payload == {}


# ---------------------------------------------------------------------------
# TestCorrelationId
# ---------------------------------------------------------------------------

class TestCorrelationId:
    """FlowExecutor generates unique correlation_id per run."""

    def test_executor_generates_correlation_id(self):
        from sangam_mw.engine.executor import FlowExecutor
        from sangam_mw.models.flow import FlowDefinition
        from sangam_mw.engine.events import EventBus

        flow = FlowDefinition(flow_id="test-flow", name="Test", steps=[], version="1")
        bus = EventBus()
        executor = FlowExecutor(bus=bus)

        with patch("sangam_mw.engine.executor.FlowExecutor._fire_persist"):
            with patch("sangam_mw.engine.executor.FlowExecutor._fire_log"):
                run1 = executor.execute(flow)
                run2 = executor.execute(flow)

        assert run1.run_id != run2.run_id

    def test_context_stores_correlation_id(self):
        from sangam_mw.engine.context import ExecutionContext
        ctx = ExecutionContext(run_id="r-1", flow_id="f-1", correlation_id="corr-abc")
        assert ctx.correlation_id == "corr-abc"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _upsert(flow_id, duration_ms, status, rows):
    from sangam_mw.observability.persistence import upsert_metrics_bucket
    return upsert_metrics_bucket(flow_id, duration_ms, status, rows)


def _append_log(run_id, flow_id, message, level="INFO", step_id=None, correlation_id=None, payload=None):
    from sangam_mw.observability.persistence import append_log
    return append_log(run_id, flow_id, message, level, step_id, correlation_id, payload)


def _emit_be(flow_id, run_id, event_name, payload, step_id=None, correlation_id=None):
    from sangam_mw.observability.persistence import _emit_business_event
    return _emit_business_event(flow_id, run_id, event_name, payload, step_id, correlation_id)
