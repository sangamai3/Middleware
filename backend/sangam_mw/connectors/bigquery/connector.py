"""BigQuery connector — service account auth, read tables / SQL, write via load_table."""
from __future__ import annotations

import json
from typing import Any

import pandas as pd

from ..base.connector import BaseConnector, SinkMixin, SourceMixin
from ..base.errors import ConnectorValidationError, DataReadError, NetworkError
from ..base.metadata import AuthType, ConnectorMetadata, OperationType
from ..base.schemas import (
    ColumnSchema,
    ConnectionHandle,
    ObjectSchema,
    ReadConfig,
    WriteConfig,
    WriteResult,
)

try:
    from google.cloud import bigquery  # type: ignore[import]
    from google.oauth2 import service_account  # type: ignore[import]
    _HAS_BQ = True
except ImportError:
    _HAS_BQ = False


def _require_bq() -> None:
    if not _HAS_BQ:
        raise ImportError(
            "google-cloud-bigquery is required: pip install google-cloud-bigquery"
        )


_BQ_TYPE_MAP = {
    "STRING": "string", "BYTES": "bytes", "INTEGER": "integer", "INT64": "integer",
    "FLOAT": "float", "FLOAT64": "float", "BOOLEAN": "boolean", "BOOL": "boolean",
    "RECORD": "struct", "STRUCT": "struct", "TIMESTAMP": "timestamp",
    "DATE": "date", "TIME": "time", "DATETIME": "datetime", "NUMERIC": "decimal",
    "BIGNUMERIC": "decimal", "GEOGRAPHY": "geography", "JSON": "json",
}


class BigQueryConnector(BaseConnector, SourceMixin, SinkMixin):
    @property
    def metadata(self) -> ConnectorMetadata:
        return ConnectorMetadata(
            connector_id="bigquery",
            label="Google BigQuery",
            family="analytics",
            version="1.0.0",
            auth_type=AuthType.SERVICE_ACCOUNT,
            operations=[OperationType.READ, OperationType.WRITE],
            description="Read/write BigQuery tables with SQL support and partitioned loading.",
            connection_schema={
                "type": "object",
                "required": ["project_id"],
                "properties": {
                    "project_id": {"type": "string", "description": "GCP project ID"},
                    "dataset_id": {
                        "type": "string",
                        "description": "Default dataset (can be overridden per step)",
                    },
                    "credentials_json": {
                        "type": "string",
                        "secret": True,
                        "description": "Service account key JSON (base64 or raw JSON string)",
                    },
                    "location": {"type": "string", "default": "US"},
                },
            },
            read_schema={
                "type": "object",
                "properties": {
                    "object": {
                        "type": "string",
                        "description": "Table name (dataset.table or just table if dataset set)",
                    },
                    "query": {"type": "string", "description": "Standard SQL query"},
                    "mode": {
                        "type": "string",
                        "enum": ["object", "sql"],
                        "default": "object",
                    },
                    "fields": {"type": "array", "items": {"type": "string"}},
                    "filter": {"type": "string", "description": "SQL WHERE clause"},
                    "limit": {"type": "integer"},
                },
            },
            write_schema={
                "type": "object",
                "required": ["object"],
                "properties": {
                    "object": {"type": "string", "description": "dataset.table"},
                    "mode": {
                        "type": "string",
                        "enum": ["append", "replace", "upsert"],
                        "default": "append",
                    },
                    "partition_field": {"type": "string"},
                    "clustering_fields": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
            },
        )

    def _client(self, handle: ConnectionHandle) -> "bigquery.Client":
        _require_bq()
        if isinstance(handle.raw_conn, bigquery.Client):
            return handle.raw_conn
        cfg = handle.config
        project = cfg["project_id"]
        creds_raw = cfg.get("credentials_json")
        if creds_raw:
            import base64
            try:
                decoded = base64.b64decode(str(creds_raw)).decode()
                creds_info = json.loads(decoded)
            except Exception:
                creds_info = json.loads(str(creds_raw))
            creds = service_account.Credentials.from_service_account_info(
                creds_info,
                scopes=["https://www.googleapis.com/auth/bigquery"],
            )
            client = bigquery.Client(project=project, credentials=creds)
        else:
            client = bigquery.Client(project=project)
        handle.raw_conn = client
        return client

    def _qualified(self, handle: ConnectionHandle, name: str) -> str:
        if "." in name:
            return name
        dataset = handle.config.get("dataset_id")
        if not dataset:
            raise ConnectorValidationError("dataset_id must be set when table has no prefix")
        return f"{dataset}.{name}"

    def test_connection(self, handle: ConnectionHandle) -> bool:
        _require_bq()
        try:
            client = self._client(handle)
            list(client.list_datasets(max_results=1))
            return True
        except Exception as exc:
            raise NetworkError(f"BigQuery connection failed: {exc}") from exc

    def introspect_objects(self, handle: ConnectionHandle) -> list[ObjectSchema]:
        _require_bq()
        client = self._client(handle)
        objects: list[ObjectSchema] = []
        dataset_id = handle.config.get("dataset_id")
        datasets = [client.dataset(dataset_id)] if dataset_id else list(client.list_datasets())
        for ds_ref in datasets:
            ds_id = ds_ref.dataset_id if hasattr(ds_ref, "dataset_id") else ds_ref
            for table in client.list_tables(ds_id):
                objects.append(
                    ObjectSchema(name=f"{ds_id}.{table.table_id}", kind="table")
                )
        return objects

    def introspect_columns(self, handle: ConnectionHandle, object_name: str) -> list[ColumnSchema]:
        _require_bq()
        client = self._client(handle)
        ref = self._qualified(handle, object_name)
        table = client.get_table(ref)
        return [
            ColumnSchema(
                name=f.name,
                data_type=_BQ_TYPE_MAP.get(f.field_type, f.field_type.lower()),
                nullable=f.mode != "REQUIRED",
            )
            for f in table.schema
        ]

    def read(self, handle: ConnectionHandle, config: ReadConfig) -> pd.DataFrame:
        _require_bq()
        client = self._client(handle)
        if config.mode == "sql":
            sql = config.query
            if not sql:
                raise ConnectorValidationError("query is required when mode=sql")
        else:
            ref = self._qualified(handle, config.object)
            cols = ", ".join(f"`{c}`" for c in config.fields) if config.fields else "*"
            sql = f"SELECT {cols} FROM `{ref}`"
            if config.filter:
                sql += f" WHERE {config.filter}"
            if config.limit:
                sql += f" LIMIT {int(config.limit)}"
        try:
            job = client.query(sql)
            df = job.to_dataframe()
            return df.reset_index(drop=True)
        except Exception as exc:
            raise DataReadError(f"BigQuery query failed: {exc}") from exc

    def write(self, df: pd.DataFrame, handle: ConnectionHandle, config: WriteConfig) -> WriteResult:
        _require_bq()
        if df.empty:
            return WriteResult(rows_written=0)
        client = self._client(handle)
        ref = self._qualified(handle, config.object)
        write_disposition = {
            "append": bigquery.WriteDisposition.WRITE_APPEND,
            "replace": bigquery.WriteDisposition.WRITE_TRUNCATE,
        }.get(config.mode, bigquery.WriteDisposition.WRITE_APPEND)

        job_config = bigquery.LoadJobConfig(write_disposition=write_disposition)
        partition_field = config.extra.get("partition_field")
        if partition_field:
            job_config.time_partitioning = bigquery.TimePartitioning(field=partition_field)
        clustering = config.extra.get("clustering_fields")
        if clustering and isinstance(clustering, list):
            job_config.clustering_fields = clustering

        try:
            job = client.load_table_from_dataframe(df, ref, job_config=job_config)
            job.result()
            return WriteResult(rows_written=len(df))
        except Exception as exc:
            raise NetworkError(f"BigQuery write failed: {exc}") from exc
