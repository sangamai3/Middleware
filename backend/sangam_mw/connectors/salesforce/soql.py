"""SOQL literal helpers — ported from AgentStudio ``repository_salesforce.py.eta``."""

from __future__ import annotations

import re
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation


def soql_escape(value: object) -> str:
    text = str(value)
    return text.replace("\\", "\\\\").replace("'", "\\'")


def soql_string(value: object) -> str:
    return "'" + soql_escape(value) + "'"


def soql_id(value: object) -> str:
    text = str(value or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9]{15}(?:[A-Za-z0-9]{3})?", text):
        raise ValueError("Salesforce Id must be 15 or 18 alphanumeric characters")
    return soql_string(text)


def sf_id_path(value: object) -> str:
    soql_id(value)
    return str(value or "").strip()


def soql_number(value: object) -> str:
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("Invalid numeric SOQL literal") from exc
    if not number.is_finite():
        raise ValueError("SOQL numeric literal must be finite")
    return format(number, "f")


def sf_limit(value: object = 200) -> int:
    try:
        return max(1, min(int(str(value if value is not None else 200)), 10000))
    except (TypeError, ValueError):
        return 200


def soql_datetime(value: object) -> str:
    text = str(value).strip()
    parsed = datetime.fromisoformat(text[:-1] + "+00:00" if text.endswith("Z") else text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def soql_date(value: object) -> str:
    return date.fromisoformat(str(value).strip()).isoformat()
