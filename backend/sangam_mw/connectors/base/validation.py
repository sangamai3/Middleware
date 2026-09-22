"""JSON Schema validation for connector connection / read / write config."""

from __future__ import annotations

from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError, ValidationError

from .errors import ConnectorValidationError


def validate_config(
    config: dict[str, Any], schema: dict[str, Any] | None, *, label: str = "config"
) -> None:
    """Validate `config` against a JSON Schema. No-op when schema is missing.

    Custom keywords such as `"secret": true` are ignored by the validator.
    """
    if not schema:
        return
    try:
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema)
        errors = sorted(validator.iter_errors(config), key=lambda e: list(e.path))
    except SchemaError as exc:
        raise ConnectorValidationError(f"Invalid {label} JSON Schema: {exc.message}") from exc
    if not errors:
        return
    messages = [_format_error(err) for err in errors]
    raise ConnectorValidationError(f"Invalid {label}: " + "; ".join(messages))


def _format_error(err: ValidationError) -> str:
    path = ".".join(str(p) for p in err.path)
    prefix = f"{path}: " if path else ""
    return f"{prefix}{err.message}"
