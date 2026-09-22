"""MongoDB connector — document read/write via pymongo."""
from __future__ import annotations

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
    from pymongo import MongoClient, UpdateOne  # type: ignore[import]
    from pymongo.errors import ConnectionFailure, OperationFailure  # type: ignore[import]
    _HAS_MONGO = True
except ImportError:
    _HAS_MONGO = False


def _require_mongo() -> None:
    if not _HAS_MONGO:
        raise ImportError("pymongo is required: pip install pymongo")


class MongoDBConnector(BaseConnector, SourceMixin, SinkMixin):
    @property
    def metadata(self) -> ConnectorMetadata:
        return ConnectorMetadata(
            connector_id="mongodb",
            label="MongoDB",
            family="nosql",
            version="1.0.0",
            auth_type=AuthType.BASIC,
            operations=[OperationType.READ, OperationType.WRITE],
            description="Read/write MongoDB collections with filter and projection support.",
            connection_schema={
                "type": "object",
                "properties": {
                    "connection_string": {
                        "type": "string",
                        "secret": True,
                        "description": "mongodb:// or mongodb+srv:// URI",
                    },
                    "host": {"type": "string", "default": "localhost"},
                    "port": {"type": "integer", "default": 27017},
                    "username": {"type": "string"},
                    "password": {"type": "string", "secret": True},
                    "database": {"type": "string", "description": "Default database"},
                    "auth_source": {"type": "string", "default": "admin"},
                    "tls": {"type": "boolean", "default": False},
                },
            },
            read_schema={
                "type": "object",
                "required": ["object"],
                "properties": {
                    "object": {"type": "string", "description": "Collection name"},
                    "filter": {
                        "type": "string",
                        "description": "JSON filter document (MongoDB query)",
                    },
                    "fields": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Projection fields",
                    },
                    "sort": {
                        "type": "string",
                        "description": "JSON sort spec e.g. {\"created_at\": -1}",
                    },
                    "limit": {"type": "integer"},
                    "database": {"type": "string", "description": "Override database"},
                },
            },
            write_schema={
                "type": "object",
                "required": ["object"],
                "properties": {
                    "object": {"type": "string", "description": "Collection name"},
                    "mode": {
                        "type": "string",
                        "enum": ["insert", "upsert", "replace"],
                        "default": "insert",
                    },
                    "upsert_key": {
                        "type": "string",
                        "description": "Field for upsert match",
                    },
                    "database": {"type": "string"},
                },
            },
        )

    def _client(self, handle: ConnectionHandle) -> "MongoClient":
        _require_mongo()
        if isinstance(handle.raw_conn, MongoClient):
            return handle.raw_conn
        cfg = handle.config
        conn_str = cfg.get("connection_string")
        if conn_str:
            client = MongoClient(str(conn_str))
        else:
            kwargs: dict[str, Any] = {
                "host": cfg.get("host", "localhost"),
                "port": int(cfg.get("port", 27017)),
                "tls": bool(cfg.get("tls", False)),
            }
            if cfg.get("username"):
                kwargs["username"] = cfg["username"]
                kwargs["password"] = cfg.get("password", "")
                kwargs["authSource"] = cfg.get("auth_source", "admin")
            client = MongoClient(**kwargs)
        handle.raw_conn = client
        return client

    def _db(self, handle: ConnectionHandle, override_db: str | None = None) -> Any:
        db_name = override_db or handle.config.get("database") or "test"
        return self._client(handle)[str(db_name)]

    def test_connection(self, handle: ConnectionHandle) -> bool:
        _require_mongo()
        try:
            self._client(handle).admin.command("ping")
            return True
        except (ConnectionFailure, OperationFailure) as exc:
            raise NetworkError(f"MongoDB connection failed: {exc}") from exc

    def introspect_objects(self, handle: ConnectionHandle) -> list[ObjectSchema]:
        _require_mongo()
        db = self._db(handle)
        return [
            ObjectSchema(name=name, kind="collection")
            for name in sorted(db.list_collection_names())
        ]

    def introspect_columns(self, handle: ConnectionHandle, object_name: str) -> list[ColumnSchema]:
        _require_mongo()
        db = self._db(handle)
        sample = list(db[object_name].find({}, {"_id": 0}).limit(10))
        if not sample:
            return [ColumnSchema(name="_id", data_type="ObjectId", nullable=False)]
        all_keys: set[str] = set()
        for doc in sample:
            all_keys.update(doc.keys())
        columns = [ColumnSchema(name=k, data_type="mixed") for k in sorted(all_keys)]
        columns.insert(0, ColumnSchema(name="_id", data_type="ObjectId", nullable=False))
        return columns

    def read(self, handle: ConnectionHandle, config: ReadConfig) -> pd.DataFrame:
        import json as _json
        _require_mongo()
        db = self._db(handle, config.extra.get("database"))
        collection = db[config.object]

        filter_doc: dict[str, Any] = {}
        if config.filter:
            try:
                filter_doc = _json.loads(config.filter)
            except Exception:
                raise ConnectorValidationError(f"Invalid filter JSON: {config.filter}")

        projection: dict[str, Any] | None = None
        if config.fields:
            projection = {f: 1 for f in config.fields}
            projection["_id"] = 0

        sort_spec: list[tuple[str, int]] | None = None
        sort_str = config.extra.get("sort")
        if sort_str:
            try:
                sort_doc = _json.loads(sort_str)
                sort_spec = [(k, int(v)) for k, v in sort_doc.items()]
            except Exception:
                raise ConnectorValidationError(f"Invalid sort JSON: {sort_str}")

        try:
            cursor = collection.find(filter_doc, projection)
            if sort_spec:
                cursor = cursor.sort(sort_spec)
            if config.limit:
                cursor = cursor.limit(config.limit)
            docs = list(cursor)
        except Exception as exc:
            raise DataReadError(f"MongoDB find failed: {exc}") from exc

        if not docs:
            return pd.DataFrame()

        for doc in docs:
            if "_id" in doc:
                doc["_id"] = str(doc["_id"])
        return pd.DataFrame(docs).reset_index(drop=True)

    def write(self, df: pd.DataFrame, handle: ConnectionHandle, config: WriteConfig) -> WriteResult:
        _require_mongo()
        if df.empty:
            return WriteResult(rows_written=0)
        db = self._db(handle, config.extra.get("database"))
        collection = db[config.object]
        mode = config.mode
        docs = df.to_dict(orient="records")
        for doc in docs:
            if "_id" in doc and doc["_id"] is None:
                del doc["_id"]

        try:
            if mode == "replace":
                collection.drop()
                result = collection.insert_many(docs)
                return WriteResult(rows_written=len(result.inserted_ids))

            if mode == "upsert":
                key = config.upsert_key
                if not key:
                    raise ConnectorValidationError("upsert_key required for MongoDB upsert")
                ops = [
                    UpdateOne({key: doc.get(key)}, {"$set": doc}, upsert=True)
                    for doc in docs
                ]
                result = collection.bulk_write(ops)
                written = result.inserted_count + result.upserted_count + result.modified_count
                return WriteResult(rows_written=written, rows_updated=result.modified_count)

            result = collection.insert_many(docs)
            return WriteResult(rows_written=len(result.inserted_ids))
        except Exception as exc:
            raise NetworkError(f"MongoDB write failed: {exc}") from exc
