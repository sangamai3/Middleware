"""JSON Schema validation for connector connection / read / write config."""

from __future__ import annotations

from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError, ValidationError

from .errors import ConnectorValidationError


def normalize_config(config: dict[str, Any], schema: dict[str, Any] | None) -> dict[str, Any]:
    """Coerce UI / form string values to JSON Schema types (e.g. ``'true'`` → bool)."""
    if not schema:
        return dict(config)
    props = schema.get("properties") or {}
    if not isinstance(props, dict):
        return dict(config)
    out = dict(config)
    for key, prop in props.items():
        if key not in out or not isinstance(prop, dict):
            continue
        ptype = prop.get("type")
        val = out[key]
        if ptype == "boolean" and isinstance(val, str):
            lowered = val.strip().lower()
            if lowered in ("true", "1", "yes", "on"):
                out[key] = True
            elif lowered in ("false", "0", "no", "off", ""):
                out[key] = False
        elif ptype == "integer" and isinstance(val, str) and val.strip().isdigit():
            out[key] = int(val.strip())
        elif ptype == "number" and isinstance(val, str):
            try:
                out[key] = float(val.strip())
            except ValueError:
                pass
    return out


def validate_config(
    config: dict[str, Any], schema: dict[str, Any] | None, *, label: str = "config"
) -> dict[str, Any]:
    """Validate `config` against a JSON Schema. Returns normalized config.

    Custom keywords such as `"secret": true` are ignored by the validator.
    """
    normalized = normalize_config(config, schema)
    if not schema:
        return normalized
    try:
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema)
        errors = sorted(validator.iter_errors(normalized), key=lambda e: list(e.path))
    except SchemaError as exc:
        raise ConnectorValidationError(f"Invalid {label} JSON Schema: {exc.message}") from exc
    if not errors:
        return normalized
    messages = [_format_error(err) for err in errors]
    raise ConnectorValidationError(f"Invalid {label}: " + "; ".join(messages))


def _format_error(err: ValidationError) -> str:
    path = ".".join(str(p) for p in err.path)
    prefix = f"{path}: " if path else ""
    return f"{prefix}{err.message}"
