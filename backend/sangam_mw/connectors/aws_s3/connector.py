"""Amazon S3 connector — service-account keys, multi-format objects, prefix listing."""

from __future__ import annotations

import io
from pathlib import PurePosixPath
from typing import Any

import pandas as pd

from ..base.connector import BaseConnector, SinkMixin, SourceMixin
from ..base.errors import AuthenticationError, ConnectorValidationError, DataReadError
from ..base.metadata import AuthType, ConnectorMetadata, OperationType
from ..base.schemas import (
    ColumnSchema,
    ConnectionHandle,
    ObjectSchema,
    ReadConfig,
    WriteConfig,
    WriteResult,
)

_READERS = {
    ".csv": pd.read_csv,
    ".json": pd.read_json,
    ".parquet": pd.read_parquet,
    ".xlsx": pd.read_excel,
}
_WRITERS: dict[str, tuple[str, dict[str, Any]]] = {
    ".csv": ("to_csv", {"index": False}),
    ".json": ("to_json", {"orient": "records"}),
    ".parquet": ("to_parquet", {"index": False}),
    ".xlsx": ("to_excel", {"index": False}),
}


class S3Connector(BaseConnector, SourceMixin, SinkMixin):
    @property
    def metadata(self) -> ConnectorMetadata:
        return ConnectorMetadata(
            connector_id="aws-s3",
            label="Amazon S3",
            family="cloud_storage",
            version="1.0.0",
            auth_type=AuthType.SERVICE_ACCOUNT,
            operations=[OperationType.READ, OperationType.WRITE],
            description="Read/write CSV, JSON, Parquet and Excel objects in S3 (LocalStack compatible).",
            connection_schema={
                "type": "object",
                "required": ["bucket"],
                "properties": {
                    "bucket": {"type": "string"},
                    "region": {"type": "string", "default": "us-east-1"},
                    "aws_access_key_id": {"type": "string", "secret": True},
                    "aws_secret_access_key": {"type": "string", "secret": True},
                    "aws_session_token": {
                        "type": "string",
                        "secret": True,
                        "description": "STS session token for temporary credentials",
                    },
                    "endpoint_url": {
                        "type": "string",
                        "description": "Override for LocalStack / MinIO (e.g. http://localhost:4566)",
                    },
                    "prefix": {
                        "type": "string",
                        "description": "Optional key prefix to list under",
                    },
                },
            },
            read_schema={
                "type": "object",
                "required": ["object"],
                "properties": {
                    "object": {"type": "string", "description": "Object key"},
                    "fields": {"type": "array", "items": {"type": "string"}},
                    "limit": {"type": "integer"},
                },
            },
            write_schema={
                "type": "object",
                "required": ["object"],
                "properties": {
                    "object": {"type": "string"},
                    "mode": {"type": "string", "enum": ["replace"], "default": "replace"},
                },
            },
        )

    def test_connection(self, handle: ConnectionHandle) -> bool:
        client = self._client(handle)
        client.head_bucket(Bucket=self._bucket(handle))
        return True

    def introspect_objects(self, handle: ConnectionHandle) -> list[ObjectSchema]:
        client = self._client(handle)
        bucket = self._bucket(handle)
        prefix = str(handle.config.get("prefix") or "")
        paginator = client.get_paginator("list_objects_v2")
        seen: list[ObjectSchema] = []
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix, Delimiter="/"):
            for common in page.get("CommonPrefixes") or []:
                name = str(common.get("Prefix") or "")
                if name:
                    seen.append(ObjectSchema(name=name, kind="prefix", description="S3 prefix"))
            for item in page.get("Contents") or []:
                key = str(item.get("Key") or "")
                if key and not key.endswith("/"):
                    seen.append(ObjectSchema(name=key, kind="file"))
        return seen

    def introspect_columns(self, handle: ConnectionHandle, object_name: str) -> list[ColumnSchema]:
        df = self.sample(handle, object_name, limit=1)
        return [
            ColumnSchema(name=str(col), data_type=str(dtype)) for col, dtype in df.dtypes.items()
        ]

    def read(self, handle: ConnectionHandle, config: ReadConfig) -> pd.DataFrame:
        suffix = PurePosixPath(config.object).suffix.lower()
        reader = _READERS.get(suffix)
        if reader is None:
            raise DataReadError(f"Unsupported S3 object format '{suffix}'")
        client = self._client(handle)
        response = client.get_object(Bucket=self._bucket(handle), Key=config.object)
        body = response["Body"].read()
        df: pd.DataFrame = reader(io.BytesIO(body))  # type: ignore[operator]
        if config.fields:
            df = df[config.fields]
        if config.limit is not None:
            df = df.head(config.limit)
        return df.reset_index(drop=True)

    def write(self, df: pd.DataFrame, handle: ConnectionHandle, config: WriteConfig) -> WriteResult:
        suffix = PurePosixPath(config.object).suffix.lower()
        spec = _WRITERS.get(suffix)
        if spec is None:
            raise ConnectorValidationError(f"Unsupported S3 output format '{suffix}'")
        method, kwargs = spec
        buf = io.BytesIO()
        getattr(df, method)(buf, **kwargs)
        buf.seek(0)
        client = self._client(handle)
        extra: dict = {}
        if suffix == ".csv":
            extra["ContentType"] = "text/csv"
        elif suffix == ".json":
            extra["ContentType"] = "application/json"
        client.put_object(
            Bucket=self._bucket(handle),
            Key=config.object,
            Body=buf.getvalue(),
            **extra,
        )
        return WriteResult(rows_written=len(df))

    def _bucket(self, handle: ConnectionHandle) -> str:
        bucket = handle.config.get("bucket")
        if not bucket:
            raise AuthenticationError("Missing S3 bucket")
        return str(bucket)

    def _client(self, handle: ConnectionHandle) -> Any:
        if handle.raw_conn is not None:
            return handle.raw_conn
        try:
            import boto3
        except ImportError as exc:
            raise ConnectorValidationError("boto3 is required for the aws-s3 connector") from exc
        kwargs: dict = {"region_name": handle.config.get("region") or "us-east-1"}
        if handle.config.get("aws_access_key_id"):
            kwargs["aws_access_key_id"] = handle.config["aws_access_key_id"]
        if handle.config.get("aws_secret_access_key"):
            kwargs["aws_secret_access_key"] = handle.config["aws_secret_access_key"]
        if handle.config.get("aws_session_token"):
            kwargs["aws_session_token"] = handle.config["aws_session_token"]
        if handle.config.get("endpoint_url"):
            kwargs["endpoint_url"] = handle.config["endpoint_url"]
        return boto3.client("s3", **kwargs)
