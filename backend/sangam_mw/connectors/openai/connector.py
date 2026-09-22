"""OpenAI connector — chat completions, embeddings, and function calling."""
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
    from openai import OpenAI  # type: ignore[import]
    _HAS_OPENAI = True
except ImportError:
    _HAS_OPENAI = False


def _require_openai() -> None:
    if not _HAS_OPENAI:
        raise ImportError("openai is required: pip install openai>=1.0")


class OpenAIConnector(BaseConnector, SourceMixin):
    @property
    def metadata(self) -> ConnectorMetadata:
        return ConnectorMetadata(
            connector_id="openai",
            label="OpenAI",
            family="ai",
            version="1.0.0",
            auth_type=AuthType.API_KEY,
            operations=[OperationType.READ],
            description="Generate text completions and embeddings via OpenAI API.",
            connection_schema={
                "type": "object",
                "required": ["api_key"],
                "properties": {
                    "api_key": {"type": "string", "secret": True},
                    "base_url": {
                        "type": "string",
                        "description": "Override API base URL (e.g. for Azure, proxy)",
                    },
                    "organization": {"type": "string"},
                    "default_model": {
                        "type": "string",
                        "default": "gpt-4o-mini",
                        "description": "Default model name",
                    },
                },
            },
            read_schema={
                "type": "object",
                "properties": {
                    "object": {
                        "type": "string",
                        "enum": ["chat", "embeddings", "models"],
                        "default": "chat",
                        "description": "Operation type",
                    },
                    "model": {"type": "string", "description": "Model name override"},
                    "prompt_template": {
                        "type": "string",
                        "description": "Prompt with {column} placeholders — applied to each row",
                    },
                    "system_message": {
                        "type": "string",
                        "description": "System instruction for chat mode",
                    },
                    "prompt_column": {
                        "type": "string",
                        "description": "Column to use as prompt when no template is set",
                    },
                    "output_column": {
                        "type": "string",
                        "default": "_llm_output",
                    },
                    "temperature": {"type": "number", "default": 0.0},
                    "max_tokens": {"type": "integer", "default": 512},
                },
            },
        )

    def _client(self, handle: ConnectionHandle) -> "OpenAI":
        _require_openai()
        if isinstance(handle.raw_conn, OpenAI):
            return handle.raw_conn
        cfg = handle.config
        kwargs: dict[str, Any] = {"api_key": cfg["api_key"]}
        if cfg.get("base_url"):
            kwargs["base_url"] = cfg["base_url"]
        if cfg.get("organization"):
            kwargs["organization"] = cfg["organization"]
        client = OpenAI(**kwargs)
        handle.raw_conn = client
        return client

    def test_connection(self, handle: ConnectionHandle) -> bool:
        _require_openai()
        try:
            self._client(handle).models.list()
            return True
        except Exception as exc:
            raise NetworkError(f"OpenAI connection failed: {exc}") from exc

    def introspect_objects(self, handle: ConnectionHandle) -> list[ObjectSchema]:
        _require_openai()
        try:
            models = list(self._client(handle).models.list())
            return [ObjectSchema(name=m.id, kind="model") for m in sorted(models, key=lambda m: m.id)]
        except Exception:
            return [
                ObjectSchema(name="chat", kind="endpoint"),
                ObjectSchema(name="embeddings", kind="endpoint"),
            ]

    def introspect_columns(self, handle: ConnectionHandle, object_name: str) -> list[ColumnSchema]:
        if object_name == "embeddings":
            return [ColumnSchema(name="_embedding", data_type="array[float]", nullable=False)]
        return [ColumnSchema(name="_llm_output", data_type="string", nullable=True)]

    def read(self, handle: ConnectionHandle, config: ReadConfig) -> pd.DataFrame:
        _require_openai()
        client = self._client(handle)
        cfg_extra = config.extra
        op = config.object or "chat"
        model = str(cfg_extra.get("model") or handle.config.get("default_model") or "gpt-4o-mini")
        out_col = str(cfg_extra.get("output_column") or "_llm_output")

        if op == "models":
            models = list(client.models.list())
            return pd.DataFrame([{"id": m.id, "owned_by": m.owned_by} for m in models])

        if op == "embeddings":
            prompt_col = str(cfg_extra.get("prompt_column") or "text")
            texts = config.extra.get("_input_texts") or []
            if not texts and config.filter:
                texts = [config.filter]
            if not texts:
                return pd.DataFrame(columns=["_input", "_embedding"])
            try:
                resp = client.embeddings.create(model=model, input=texts)
                return pd.DataFrame([
                    {"_input": texts[i], "_embedding": e.embedding}
                    for i, e in enumerate(resp.data)
                ])
            except Exception as exc:
                raise DataReadError(f"OpenAI embeddings failed: {exc}") from exc

        template = cfg_extra.get("prompt_template")
        system = str(cfg_extra.get("system_message") or "You are a helpful assistant.")
        temp = float(cfg_extra.get("temperature") or 0.0)
        max_tokens = int(cfg_extra.get("max_tokens") or 512)
        prompt_col = str(cfg_extra.get("prompt_column") or "prompt")

        input_prompts: list[str]
        if template:
            input_prompts = [str(template.format(**{str(k): v for k, v in row.items()}))
                             for row in (config.extra.get("_rows") or [{}])]
        elif config.filter:
            input_prompts = [config.filter]
        else:
            raise ConnectorValidationError(
                "Set prompt_template or filter to provide the prompt"
            )

        results = []
        for prompt in input_prompts:
            try:
                resp = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=temp,
                    max_tokens=max_tokens,
                )
                results.append({"_prompt": prompt, out_col: resp.choices[0].message.content})
            except Exception as exc:
                raise DataReadError(f"OpenAI chat failed: {exc}") from exc

        return pd.DataFrame(results)
