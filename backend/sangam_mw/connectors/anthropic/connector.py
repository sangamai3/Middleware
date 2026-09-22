"""Anthropic connector — Claude messages API for completions and structured output."""
from __future__ import annotations

from typing import Any

import pandas as pd

from ..base.connector import BaseConnector, SourceMixin
from ..base.errors import ConnectorValidationError, DataReadError, NetworkError
from ..base.metadata import AuthType, ConnectorMetadata, OperationType
from ..base.schemas import (
    ColumnSchema,
    ConnectionHandle,
    ObjectSchema,
    ReadConfig,
)

try:
    import anthropic as _anthropic_lib  # type: ignore[import]
    _HAS_ANTHROPIC = True
except ImportError:
    _HAS_ANTHROPIC = False


def _require_anthropic() -> None:
    if not _HAS_ANTHROPIC:
        raise ImportError("anthropic is required: pip install anthropic")


class AnthropicConnector(BaseConnector, SourceMixin):
    @property
    def metadata(self) -> ConnectorMetadata:
        return ConnectorMetadata(
            connector_id="anthropic",
            label="Anthropic (Claude)",
            family="ai",
            version="1.0.0",
            auth_type=AuthType.API_KEY,
            operations=[OperationType.READ],
            description="Generate text and structured output via Anthropic Claude.",
            connection_schema={
                "type": "object",
                "required": ["api_key"],
                "properties": {
                    "api_key": {"type": "string", "secret": True},
                    "base_url": {"type": "string"},
                    "default_model": {
                        "type": "string",
                        "default": "claude-haiku-4-5-20251001",
                    },
                },
            },
            read_schema={
                "type": "object",
                "properties": {
                    "object": {
                        "type": "string",
                        "enum": ["messages"],
                        "default": "messages",
                    },
                    "model": {"type": "string"},
                    "prompt_template": {
                        "type": "string",
                        "description": "Prompt with {column} placeholders",
                    },
                    "system_message": {"type": "string"},
                    "output_column": {"type": "string", "default": "_claude_output"},
                    "temperature": {"type": "number", "default": 0.0},
                    "max_tokens": {"type": "integer", "default": 1024},
                    "structured_schema": {
                        "type": "string",
                        "description": "JSON Schema string for structured output via tool use",
                    },
                },
            },
        )

    def _client(self, handle: ConnectionHandle) -> "_anthropic_lib.Anthropic":
        _require_anthropic()
        if isinstance(handle.raw_conn, _anthropic_lib.Anthropic):
            return handle.raw_conn
        cfg = handle.config
        kwargs: dict[str, Any] = {"api_key": cfg["api_key"]}
        if cfg.get("base_url"):
            kwargs["base_url"] = cfg["base_url"]
        client = _anthropic_lib.Anthropic(**kwargs)
        handle.raw_conn = client
        return client

    def test_connection(self, handle: ConnectionHandle) -> bool:
        _require_anthropic()
        try:
            cfg = handle.config
            model = str(cfg.get("default_model") or "claude-haiku-4-5-20251001")
            self._client(handle).messages.create(
                model=model,
                max_tokens=1,
                messages=[{"role": "user", "content": "hi"}],
            )
            return True
        except Exception as exc:
            raise NetworkError(f"Anthropic connection failed: {exc}") from exc

    def introspect_objects(self, handle: ConnectionHandle) -> list[ObjectSchema]:
        return [ObjectSchema(name="messages", kind="endpoint")]

    def introspect_columns(self, handle: ConnectionHandle, object_name: str) -> list[ColumnSchema]:
        return [
            ColumnSchema(name="_prompt", data_type="string", nullable=False),
            ColumnSchema(name="_claude_output", data_type="string", nullable=True),
        ]

    def read(self, handle: ConnectionHandle, config: ReadConfig) -> pd.DataFrame:
        _require_anthropic()
        client = self._client(handle)
        cfg_extra = config.extra
        model = str(cfg_extra.get("model") or handle.config.get("default_model") or "claude-haiku-4-5-20251001")
        out_col = str(cfg_extra.get("output_column") or "_claude_output")
        system = str(cfg_extra.get("system_message") or "You are a helpful assistant.")
        temp = float(cfg_extra.get("temperature") or 0.0)
        max_tokens = int(cfg_extra.get("max_tokens") or 1024)
        template = cfg_extra.get("prompt_template")

        if template:
            input_prompts = [str(template.format(**{str(k): v for k, v in row.items()}))
                             for row in (cfg_extra.get("_rows") or [{}])]
        elif config.filter:
            input_prompts = [config.filter]
        else:
            raise ConnectorValidationError("Set prompt_template or filter to provide the prompt")

        results = []
        for prompt in input_prompts:
            try:
                msg = client.messages.create(
                    model=model,
                    max_tokens=max_tokens,
                    system=system,
                    messages=[{"role": "user", "content": prompt}],
                )
                text = msg.content[0].text if msg.content else ""
                results.append({"_prompt": prompt, out_col: text})
            except Exception as exc:
                raise DataReadError(f"Anthropic API call failed: {exc}") from exc

        return pd.DataFrame(results)
