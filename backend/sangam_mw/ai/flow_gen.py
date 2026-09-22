"""
AI-powered flow generation and field mapping assistance.

FlowGenerator:
  Input: natural language description + available connections
  Output: flow definition YAML (user reviews before deploying)

FieldMappingSuggester:
  Input: source schema + target schema
  Output: ranked field mapping suggestions with confidence scores

Uses the Anthropic API (falls back to OpenAI if configured).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from ..connectors.base.schemas import ColumnSchema

_FLOW_GEN_SYSTEM = """
You are an expert integration engineer for SangamMW, an open-source iPaaS platform.
Given a natural language description, generate a valid SangamMW flow definition in YAML.

Rules:
- Output ONLY valid YAML, no explanation, no markdown fences.
- Use these step types: source, sink, transform_map, transform_sql, transform_script, router, merge.
- connector_id must be one of the available_connectors list.
- Every step needs: step_id, type, connector_id (for source/sink), config.object, depends_on (except first step).
- Use meaningful step_id names like 'read_salesforce', 'filter_active', 'write_postgres'.
- Add a trigger section with type: manual unless the description implies schedule/webhook.
- Set flow_id as snake_case of the flow name.

Output format:
flow_id: <snake_case_name>
name: <Human Readable Name>
description: <brief description>
trigger:
  type: manual  # or schedule/webhook
steps:
  - step_id: <id>
    type: source
    connector_id: <connection_id>
    config:
      object: <table_or_endpoint>
    ...
""".strip()

_FIELD_MAP_SYSTEM = """
You are a data mapping expert. Given source and target field lists, suggest the best field mappings.

Return a JSON array of mapping objects:
[
  {
    "source_field": "field_name",
    "target_field": "field_name",
    "confidence": 0.95,
    "transform": null,
    "reason": "exact name match"
  }
]

Rules:
- confidence 0.0–1.0 (1.0 = exact match, 0.5 = likely match, 0.2 = possible)
- transform: null for direct copy, or a function name like "to_uppercase", "date_format", "to_integer"
- Only include mappings with confidence >= 0.3
- Prefer exact name matches, then semantic similarity, then data type compatibility
- Output ONLY the JSON array, no explanation
""".strip()


@dataclass
class FlowGenerator:
    api_key: str
    provider: str = "anthropic"
    model: str = ""

    def _resolve_model(self) -> str:
        if self.model:
            return self.model
        return "claude-haiku-4-5-20251001" if self.provider == "anthropic" else "gpt-4o-mini"

    def generate(
        self,
        description: str,
        available_connectors: list[str],
        available_connections: list[dict[str, Any]] | None = None,
    ) -> str:
        """
        Generate a flow definition YAML from a natural language description.
        Returns raw YAML string — caller validates before deploying.
        """
        conn_list = "\n".join(f"  - {c}" for c in available_connectors)
        user_msg = (
            f"Generate a flow for: {description}\n\n"
            f"Available connectors:\n{conn_list}"
        )
        if available_connections:
            conn_details = "\n".join(
                f"  - connection_id: {c.get('connection_id')}, connector: {c.get('connector_id')}, name: {c.get('name')}"
                for c in available_connections
            )
            user_msg += f"\n\nConfigured connections:\n{conn_details}"

        if self.provider == "anthropic":
            return self._call_anthropic(user_msg)
        return self._call_openai(user_msg)

    def _call_anthropic(self, prompt: str) -> str:
        try:
            import anthropic  # type: ignore[import]
        except ImportError:
            raise ImportError("pip install anthropic")
        client = anthropic.Anthropic(api_key=self.api_key)
        msg = client.messages.create(
            model=self._resolve_model(),
            max_tokens=2048,
            system=_FLOW_GEN_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text.strip()

    def _call_openai(self, prompt: str) -> str:
        try:
            from openai import OpenAI  # type: ignore[import]
        except ImportError:
            raise ImportError("pip install openai")
        client = OpenAI(api_key=self.api_key)
        resp = client.chat.completions.create(
            model=self._resolve_model(),
            messages=[
                {"role": "system", "content": _FLOW_GEN_SYSTEM},
                {"role": "user", "content": prompt},
            ],
            max_tokens=2048,
        )
        return (resp.choices[0].message.content or "").strip()


@dataclass
class MappingSuggestion:
    source_field: str
    target_field: str
    confidence: float
    transform: str | None
    reason: str


@dataclass
class FieldMappingSuggester:
    api_key: str
    provider: str = "anthropic"
    model: str = ""

    def _resolve_model(self) -> str:
        if self.model:
            return self.model
        return "claude-haiku-4-5-20251001" if self.provider == "anthropic" else "gpt-4o-mini"

    def suggest(
        self,
        source_schema: list[ColumnSchema],
        target_schema: list[ColumnSchema],
    ) -> list[MappingSuggestion]:
        source_list = [f"{c.name} ({c.data_type})" for c in source_schema]
        target_list = [f"{c.name} ({c.data_type})" for c in target_schema]
        prompt = (
            f"Source fields: {json.dumps(source_list)}\n"
            f"Target fields: {json.dumps(target_list)}\n\n"
            "Suggest field mappings."
        )
        if self.provider == "anthropic":
            raw = self._call_anthropic(prompt)
        else:
            raw = self._call_openai(prompt)

        try:
            items = json.loads(raw)
        except Exception:
            import re
            match = re.search(r"\[.*\]", raw, re.DOTALL)
            items = json.loads(match.group(0)) if match else []

        return [
            MappingSuggestion(
                source_field=m["source_field"],
                target_field=m["target_field"],
                confidence=float(m.get("confidence", 0.5)),
                transform=m.get("transform"),
                reason=m.get("reason", ""),
            )
            for m in items
            if isinstance(m, dict) and "source_field" in m and "target_field" in m
        ]

    def _call_anthropic(self, prompt: str) -> str:
        import anthropic  # type: ignore[import]
        client = anthropic.Anthropic(api_key=self.api_key)
        msg = client.messages.create(
            model=self._resolve_model(),
            max_tokens=1024,
            system=_FIELD_MAP_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text.strip()

    def _call_openai(self, prompt: str) -> str:
        from openai import OpenAI  # type: ignore[import]
        client = OpenAI(api_key=self.api_key)
        resp = client.chat.completions.create(
            model=self._resolve_model(),
            messages=[
                {"role": "system", "content": _FIELD_MAP_SYSTEM},
                {"role": "user", "content": prompt},
            ],
            max_tokens=1024,
        )
        return (resp.choices[0].message.content or "").strip()
