"""Slack connector — post messages, files, and blocks to channels."""
from __future__ import annotations

from typing import Any

import pandas as pd

from ..base.connector import BaseConnector, SinkMixin
from ..base.errors import ConnectorValidationError, NetworkError
from ..base.metadata import AuthType, ConnectorMetadata, OperationType
from ..base.schemas import (
    ColumnSchema,
    ConnectionHandle,
    ObjectSchema,
    WriteConfig,
    WriteResult,
)

try:
    from slack_sdk import WebClient  # type: ignore[import]
    from slack_sdk.errors import SlackApiError  # type: ignore[import]
    _HAS_SLACK = True
except ImportError:
    _HAS_SLACK = False


def _require_slack() -> None:
    if not _HAS_SLACK:
        raise ImportError("slack-sdk is required: pip install slack-sdk")


class SlackConnector(BaseConnector, SinkMixin):
    @property
    def metadata(self) -> ConnectorMetadata:
        return ConnectorMetadata(
            connector_id="slack",
            label="Slack",
            family="communication",
            version="1.0.0",
            auth_type=AuthType.API_KEY,
            operations=[OperationType.WRITE],
            description="Post messages, blocks, and files to Slack channels.",
            connection_schema={
                "type": "object",
                "required": ["bot_token"],
                "properties": {
                    "bot_token": {
                        "type": "string",
                        "secret": True,
                        "description": "xoxb-... Bot User OAuth Token",
                    },
                },
            },
            write_schema={
                "type": "object",
                "required": ["object"],
                "properties": {
                    "object": {
                        "type": "string",
                        "description": "Channel ID or name (e.g. #general, C01234)",
                    },
                    "message_template": {
                        "type": "string",
                        "description": "Message with {column} placeholders; uses entire row if omitted",
                    },
                    "username": {"type": "string", "description": "Display name override"},
                    "icon_emoji": {"type": "string", "description": "e.g. :robot_face:"},
                    "send_as_table": {
                        "type": "boolean",
                        "default": False,
                        "description": "Render all rows as a formatted table block",
                    },
                },
            },
        )

    def _client(self, handle: ConnectionHandle) -> "WebClient":
        _require_slack()
        if isinstance(handle.raw_conn, WebClient):
            return handle.raw_conn
        client = WebClient(token=str(handle.config["bot_token"]))
        handle.raw_conn = client
        return client

    def test_connection(self, handle: ConnectionHandle) -> bool:
        _require_slack()
        try:
            resp = self._client(handle).auth_test()
            return bool(resp.get("ok"))
        except SlackApiError as exc:
            raise NetworkError(f"Slack auth failed: {exc}") from exc

    def introspect_objects(self, handle: ConnectionHandle) -> list[ObjectSchema]:
        _require_slack()
        try:
            client = self._client(handle)
            resp = client.conversations_list(types="public_channel,private_channel", limit=200)
            channels = resp.get("channels") or []
            return [
                ObjectSchema(name=f"#{c['name']}", kind="channel", description=c.get("id", ""))
                for c in channels
            ]
        except SlackApiError:
            return []

    def introspect_columns(self, handle: ConnectionHandle, object_name: str) -> list[ColumnSchema]:
        return [
            ColumnSchema(name="message", data_type="string", nullable=False),
            ColumnSchema(name="channel", data_type="string", nullable=True),
        ]

    def write(self, df: pd.DataFrame, handle: ConnectionHandle, config: WriteConfig) -> WriteResult:
        _require_slack()
        if df.empty:
            return WriteResult(rows_written=0)
        client = self._client(handle)
        channel = config.object
        template = config.extra.get("message_template")
        username = config.extra.get("username")
        icon_emoji = config.extra.get("icon_emoji")
        send_as_table = bool(config.extra.get("send_as_table", False))
        written = 0
        errors: list[dict[str, Any]] = []

        def _post(text: str) -> None:
            nonlocal written
            kwargs: dict[str, Any] = {"channel": channel, "text": text}
            if username:
                kwargs["username"] = username
            if icon_emoji:
                kwargs["icon_emoji"] = icon_emoji
            try:
                resp = client.chat_postMessage(**kwargs)
                if resp.get("ok"):
                    written += 1
                else:
                    errors.append({"error": resp.get("error", "unknown")})
            except SlackApiError as exc:
                errors.append({"error": str(exc)})

        if send_as_table:
            header = " | ".join(str(c) for c in df.columns)
            sep = "-" * len(header)
            rows_txt = "\n".join(
                " | ".join(str(v) for v in row)
                for row in df.values.tolist()
            )
            _post(f"```\n{header}\n{sep}\n{rows_txt}\n```")
        elif template:
            for row in df.to_dict(orient="records"):
                try:
                    msg = template.format(**{str(k): v for k, v in row.items()})
                except KeyError as exc:
                    errors.append({"error": f"Template key error: {exc}"})
                    continue
                _post(msg)
        else:
            for row in df.to_dict(orient="records"):
                if "message" in row:
                    _post(str(row["message"]))
                else:
                    import json
                    _post(json.dumps(row, default=str))

        return WriteResult(rows_written=written, rows_failed=len(errors), errors=errors)
