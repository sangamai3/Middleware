"""JSON Schema validation for connector configs."""

import pytest

from sangam_mw.connectors.base.errors import ConnectorValidationError
from sangam_mw.connectors.base.validation import validate_config
from sangam_mw.connectors.file.connector import FileConnector


def test_valid_file_connection_config() -> None:
    schema = FileConnector().metadata.connection_schema
    validate_config({"base_path": "/tmp"}, schema)


def test_string_boolean_coerced_for_file_connector() -> None:
    schema = FileConnector().metadata.connection_schema
    normalized = validate_config(
        {"base_path": "/tmp", "create_if_not_exists": "true"},
        schema,
    )
    assert normalized["create_if_not_exists"] is True


def test_missing_required_field() -> None:
    schema = FileConnector().metadata.connection_schema
    with pytest.raises(ConnectorValidationError, match="base_path"):
        validate_config({}, schema)


def test_secret_keyword_is_allowed() -> None:
    schema = {
        "type": "object",
        "required": ["api_key"],
        "properties": {"api_key": {"type": "string", "secret": True}},
    }
    validate_config({"api_key": "abc"}, schema)


def test_none_schema_is_noop() -> None:
    validate_config({"anything": 1}, None)


def test_invalid_schema_raises() -> None:
    with pytest.raises(ConnectorValidationError, match="JSON Schema"):
        validate_config({}, {"type": 123})
