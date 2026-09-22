"""S3 connector tests against an in-memory fake boto3 client."""

from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd

from sangam_mw.connectors.aws_s3.connector import S3Connector
from sangam_mw.connectors.base.metadata import AuthType
from sangam_mw.connectors.base.schemas import ConnectionHandle, ReadConfig, WriteConfig


class _Body:
    def __init__(self, data: bytes) -> None:
        self._data = data

    def read(self) -> bytes:
        return self._data


class FakeS3:
    def __init__(self, bucket: str = "lake") -> None:
        self.bucket = bucket
        self.objects: dict[str, bytes] = {}

    def head_bucket(self, Bucket: str) -> dict:
        if Bucket != self.bucket:
            raise RuntimeError("missing bucket")
        return {}

    def get_paginator(self, name: str) -> object:
        assert name == "list_objects_v2"

        class _Paginator:
            def paginate(self, **kwargs: object) -> object:
                yield {
                    "CommonPrefixes": [{"Prefix": "incoming/"}],
                    "Contents": [
                        {"Key": "incoming/customers.csv"},
                        {"Key": "incoming/"},
                    ],
                }

        return _Paginator()

    def get_object(self, Bucket: str, Key: str) -> dict:
        return {"Body": _Body(self.objects[Key])}

    def put_object(self, Bucket: str, Key: str, Body: bytes, **extra: object) -> dict:
        self.objects[Key] = Body
        return {}


def _handle(client: FakeS3) -> ConnectionHandle:
    return ConnectionHandle(
        connector_id="aws-s3",
        connection_id="s3",
        config={
            "bucket": "lake",
            "region": "us-east-1",
            "aws_access_key_id": "x",
            "aws_secret_access_key": "y",
        },
        created_at=datetime.now(UTC),
        raw_conn=client,
    )


def test_s3_metadata() -> None:
    assert S3Connector().metadata.auth_type == AuthType.SERVICE_ACCOUNT
    assert S3Connector().metadata.connector_id == "aws-s3"


def test_s3_introspect_lists_prefixes_and_files() -> None:
    connector = S3Connector()
    objects = connector.introspect_objects(_handle(FakeS3()))
    names = [o.name for o in objects]
    assert "incoming/" in names
    assert "incoming/customers.csv" in names
    kinds = {o.name: o.kind for o in objects}
    assert kinds["incoming/"] == "prefix"


def test_s3_write_read_csv_roundtrip() -> None:
    client = FakeS3()
    handle = _handle(client)
    connector = S3Connector()
    assert connector.test_connection(handle) is True
    original = pd.DataFrame({"id": [1, 2], "name": ["a", "b"]})
    result = connector.write(original, handle, WriteConfig(object="incoming/customers.csv"))
    assert result.rows_written == 2
    df = connector.read(handle, ReadConfig(object="incoming/customers.csv", limit=1))
    assert len(df) == 1
    cols = connector.introspect_columns(handle, "incoming/customers.csv")
    assert "id" in [c.name for c in cols]
