"""Unit tests for scheduler route helpers and validation."""
from __future__ import annotations

import pytest


class TestJobCreate:
    """JobCreate pydantic model validation."""

    def test_both_cron_and_interval_rejected(self):
        from pydantic import ValidationError
        from sangam_mw.api.routes.scheduler import JobCreate

        with pytest.raises(ValidationError, match="only one"):
            JobCreate(flow_id="x", cron_expr="0 * * * *", interval_seconds=60)

    def test_neither_cron_nor_interval_rejected(self):
        from pydantic import ValidationError
        from sangam_mw.api.routes.scheduler import JobCreate

        with pytest.raises(ValidationError):
            JobCreate(flow_id="x")

    def test_cron_only_ok(self):
        from sangam_mw.api.routes.scheduler import JobCreate

        job = JobCreate(flow_id="x", cron_expr="0 9 * * 1")
        assert job.cron_expr == "0 9 * * 1"
        assert job.interval_seconds is None

    def test_interval_only_ok(self):
        from sangam_mw.api.routes.scheduler import JobCreate

        job = JobCreate(flow_id="x", interval_seconds=3600)
        assert job.interval_seconds == 3600
        assert job.cron_expr is None

    def test_defaults(self):
        from sangam_mw.api.routes.scheduler import JobCreate

        job = JobCreate(flow_id="x", cron_expr="0 * * * *")
        assert job.timezone == "UTC"
        assert job.is_active is True
        assert job.flow_name == ""


class TestCronHuman:
    """_cron_human returns human-readable labels."""

    def _h(self, expr: str) -> str:
        from sangam_mw.api.routes.scheduler import _cron_human
        return _cron_human(expr)

    def test_every_hour(self):
        assert self._h("0 * * * *") == "Every hour"

    def test_every_5_min(self):
        assert self._h("*/5 * * * *") == "Every 5 minutes"

    def test_every_15_min(self):
        assert self._h("*/15 * * * *") == "Every 15 minutes"

    def test_every_30_min(self):
        assert self._h("*/30 * * * *") == "Every 30 minutes"

    def test_daily(self):
        label = self._h("0 9 * * *")
        assert "9" in label

    def test_weekly(self):
        label = self._h("0 9 * * 1")
        assert "Mon" in label

    def test_malformed_passthrough(self):
        expr = "not-a-cron"
        assert self._h(expr) == expr

    def test_unknown_pattern(self):
        label = self._h("5 4 3 2 1")
        assert "5 4 3 2 1" in label


class TestTriggerLabel:
    """_trigger_label returns the right text for different row states."""

    def _row(self, cron: str | None, interval: int | None):
        import types
        row = types.SimpleNamespace(cron_expr=cron, interval_seconds=interval)
        return row

    def _label(self, cron: str | None, interval: int | None) -> str:
        from sangam_mw.api.routes.scheduler import _trigger_label
        return _trigger_label(self._row(cron, interval))

    def test_interval_hours(self):
        label = self._label(None, 7200)
        assert "2h" in label

    def test_interval_minutes(self):
        label = self._label(None, 300)
        assert "5m" in label

    def test_interval_seconds(self):
        label = self._label(None, 45)
        assert "45s" in label

    def test_cron_every_hour(self):
        label = self._label("0 * * * *", None)
        assert "hour" in label.lower()

    def test_cron_daily(self):
        label = self._label("0 9 * * *", None)
        assert "9" in label

    def test_fallback_neither(self):
        label = self._label(None, None)
        assert label == "—"


class TestRowToDict:
    """_row_to_dict produces the expected shape."""

    def _row(self, **kw):
        import types
        from datetime import datetime, UTC
        return types.SimpleNamespace(
            flow_id=kw.get("flow_id", "f1"),
            flow_name=kw.get("flow_name", "My Flow"),
            cron_expr=kw.get("cron_expr", "0 * * * *"),
            interval_seconds=kw.get("interval_seconds", None),
            timezone=kw.get("timezone", "UTC"),
            is_active=kw.get("is_active", True),
            last_run_at=kw.get("last_run_at", None),
            created_by=kw.get("created_by", "u1"),
            created_at=kw.get("created_at", datetime.now(UTC)),
            updated_at=kw.get("updated_at", datetime.now(UTC)),
        )

    def test_trigger_type_cron(self):
        from sangam_mw.api.routes.scheduler import _row_to_dict
        d = _row_to_dict(self._row(cron_expr="0 * * * *"))
        assert d["trigger_type"] == "cron"

    def test_trigger_type_interval(self):
        from sangam_mw.api.routes.scheduler import _row_to_dict
        d = _row_to_dict(self._row(cron_expr=None, interval_seconds=600))
        assert d["trigger_type"] == "interval"

    def test_all_keys_present(self):
        from sangam_mw.api.routes.scheduler import _row_to_dict
        d = _row_to_dict(self._row())
        for key in ["flow_id", "flow_name", "cron_expr", "interval_seconds",
                    "timezone", "is_active", "last_run_at", "next_run_at",
                    "trigger_type", "trigger_label", "created_by",
                    "created_at", "updated_at"]:
            assert key in d, f"Missing key: {key}"

    def test_last_run_at_none(self):
        from sangam_mw.api.routes.scheduler import _row_to_dict
        d = _row_to_dict(self._row(last_run_at=None))
        assert d["last_run_at"] is None
