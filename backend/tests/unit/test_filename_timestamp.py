from datetime import datetime

from sangam_mw.engine.filename_timestamp import (
    DEFAULT_FILENAME_TIMESTAMP_FORMAT,
    format_filename_timestamp,
)


def test_default_format() -> None:
    when = datetime(2026, 9, 23, 7, 45, 30)
    assert format_filename_timestamp(None, when=when) == "20260923_074530"


def test_custom_format() -> None:
    when = datetime(2026, 9, 23, 7, 45, 30)
    assert format_filename_timestamp("%Y-%m-%d", when=when) == "2026-09-23"


def test_invalid_format_falls_back() -> None:
    when = datetime(2026, 1, 2, 3, 4, 5)
    assert format_filename_timestamp("%q", when=when) == when.strftime(DEFAULT_FILENAME_TIMESTAMP_FORMAT)
