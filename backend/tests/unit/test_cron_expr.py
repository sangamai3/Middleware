"""Cron expression parsing for scheduler."""
from __future__ import annotations

import pytest


class TestValidateCronExpr:
    def test_five_fields_ok(self):
        from sangam_mw.engine.cron_expr import validate_cron_expr

        validate_cron_expr("0 9 * * 1")

    def test_six_fields_ok(self):
        from sangam_mw.engine.cron_expr import validate_cron_expr

        validate_cron_expr("30 0 9 * * 1")

    def test_wrong_count(self):
        from sangam_mw.engine.cron_expr import validate_cron_expr

        with pytest.raises(ValueError, match="5 or 6"):
            validate_cron_expr("0 9 * *")


class TestCronTriggerFromExpr:
    def test_five_field_trigger(self):
        from apscheduler.triggers.cron import CronTrigger
        from sangam_mw.engine.cron_expr import cron_trigger_from_expr

        t = cron_trigger_from_expr("0 9 * * *")
        assert isinstance(t, CronTrigger)

    def test_six_field_trigger(self):
        from apscheduler.triggers.cron import CronTrigger
        from sangam_mw.engine.cron_expr import cron_trigger_from_expr

        t = cron_trigger_from_expr("15 30 9 * * 1-5")
        assert isinstance(t, CronTrigger)
        assert "15" in repr(t)
