from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class ConnectionHandle:
    connector_id: str
    connection_id: str
    config: dict  # decrypted connection config
    raw_conn: Any = None  # actual connection object (set by connector on first use)
    created_at: datetime = field(default_factory=lambda: __import__("datetime").datetime.utcnow())
    token_expires_at: datetime | None = None  # for OAuth2


@dataclass
class ReadConfig:
    object: str  # table name, file name, endpoint path, topic, etc.
    fields: list[str] | None = None  # None = all fields
    filter: str | None = None  # WHERE clause or query expression
    limit: int | None = None
    batch_size: int = 1000
    mode: str = "object"  # "object" | "soql" | "sql" | "query"
    query: str | None = None  # raw query string (SOQL, SQL, JQL, etc.)
    extra: dict = field(default_factory=dict)


@dataclass
class WriteConfig:
    object: str  # target table / file / topic
    mode: str = "append"  # "append" | "upsert" | "replace" | "merge"
    upsert_key: str | None = None  # field to use as the upsert key
    batch_size: int = 1000
    extra: dict = field(default_factory=dict)


@dataclass
class WriteResult:
    rows_written: int
    rows_updated: int = 0
    rows_failed: int = 0
    errors: list[dict] = field(default_factory=list)


@dataclass
class ObjectSchema:
    name: str
    kind: str = "table"  # "table" | "view" | "file" | "endpoint" | "topic"
    description: str = ""
    schema: dict | None = None  # JSON Schema of the object's fields


@dataclass
class ColumnSchema:
    name: str
    data_type: str
    nullable: bool = True
    description: str = ""
    is_primary_key: bool = False
    sample_values: list[Any] = field(default_factory=list)
