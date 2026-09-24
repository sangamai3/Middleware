"""Schedule registry helpers."""
from __future__ import annotations

import types


def _row(**kw):
    return types.SimpleNamespace(
        flow_id=kw.get("flow_id", "f1"),
        cron_expr=kw.get("cron_expr"),
        interval_seconds=kw.get("interval_seconds"),
        timezone=kw.get("timezone", "UTC"),
        is_active=kw.get("is_active", True),
    )


class TestRowToTriggerConfig:
    def test_cron(self):
        from sangam_mw.engine.schedule_registry import row_to_trigger_config

        cfg = row_to_trigger_config(_row(cron_expr="*/5 * * * *", timezone="Asia/Kolkata"))
        assert cfg == {"cron": "*/5 * * * *", "timezone": "Asia/Kolkata"}

    def test_interval(self):
        from sangam_mw.engine.schedule_registry import row_to_trigger_config

        cfg = row_to_trigger_config(_row(interval_seconds=300))
        assert cfg == {"interval_seconds": 300}

    def test_missing_raises(self):
        from sangam_mw.engine.schedule_registry import row_to_trigger_config

        import pytest

        with pytest.raises(ValueError):
            row_to_trigger_config(_row())
