"""Safe strftime snippets for output filenames."""

from __future__ import annotations

from datetime import datetime

DEFAULT_FILENAME_TIMESTAMP_FORMAT = "%Y%m%d_%H%M%S"
_ALLOWED_CODES = frozenset("YmdHMS")


def _is_safe_strftime_pattern(pattern: str) -> bool:
    i = 0
    while i < len(pattern):
        ch = pattern[i]
        if ch == "%":
            if i + 1 >= len(pattern):
                return False
            code = pattern[i + 1]
            if code not in _ALLOWED_CODES and code != "%":
                return False
            i += 2
        else:
            i += 1
    return True


def format_filename_timestamp(pattern: str | None = None, *, when: datetime | None = None) -> str:
    """Format `when` (default: now) for embedding in a filename."""
    raw = (pattern or "").strip() or DEFAULT_FILENAME_TIMESTAMP_FORMAT
    moment = when or datetime.now()
    if not _is_safe_strftime_pattern(raw):
        raw = DEFAULT_FILENAME_TIMESTAMP_FORMAT
    try:
        text = moment.strftime(raw)
    except (ValueError, TypeError):
        text = moment.strftime(DEFAULT_FILENAME_TIMESTAMP_FORMAT)
    for bad in ("/", "\\", "\0", ":"):
        text = text.replace(bad, "-")
    return text
