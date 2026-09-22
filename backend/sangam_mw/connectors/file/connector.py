"""
FileConnector — reference implementation.

Demonstrates the complete BaseConnector + SourceMixin + SinkMixin pattern.
Supports: CSV, JSON, Parquet, Excel (.xlsx).
Glob patterns (e.g. *.csv) are supported in read_schema.object.
"""

import glob
from pathlib import Path

import pandas as pd

from ..base.connector import BaseConnector, SinkMixin, SourceMixin
from ..base.metadata import AuthType, ConnectorMetadata, OperationType
from ..base.schemas import (
    ColumnSchema,
    ConnectionHandle,
    ObjectSchema,
    ReadConfig,
    WriteConfig,
    WriteResult,
)

_SUPPORTED_SUFFIXES = {".csv", ".json", ".parquet", ".xlsx"}

_READERS: dict[str, object] = {
    ".csv": pd.read_csv,
    ".json": pd.read_json,
    ".parquet": pd.read_parquet,
    ".xlsx": pd.read_excel,
}

_WRITER_METHODS: dict[str, str] = {
    ".csv": "to_csv",
    ".json": "to_json",
    ".parquet": "to_parquet",
    ".xlsx": "to_excel",
}


class FileConnector(BaseConnector, SourceMixin, SinkMixin):
    @property
    def metadata(self) -> ConnectorMetadata:
        return ConnectorMetadata(
            connector_id="file",
            label="Local File",
            family="file",
            version="1.0.0",
            auth_type=AuthType.NONE,
            operations=[OperationType.READ, OperationType.WRITE],
            description="Read/write CSV, JSON, Parquet and Excel files from a local directory.",
            connection_schema={
                "type": "object",
                "required": ["base_path"],
                "properties": {
                    "base_path": {
                        "type": "string",
                        "description": "Absolute path to the base directory",
                    },
                    "create_if_not_exists": {
                        "type": "boolean",
                        "description": "Create the directory if it does not exist",
                        "default": False,
                    },
                },
            },
            read_schema={
                "type": "object",
                "required": ["object"],
                "properties": {
                    "object": {
                        "type": "string",
                        "description": "File name relative to base_path (e.g. customers.csv)",
                    },
                    "limit": {"type": "integer", "description": "Max rows to read"},
                    "fields": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Columns to return; omit for all",
                    },
                    "filter": {
                        "type": "string",
                        "description": "pandas .query() expression (e.g. 'amount > 100')",
                    },
                },
            },
            write_schema={
                "type": "object",
                "required": ["object"],
                "properties": {
                    "object": {
                        "type": "string",
                        "description": "Output file name relative to base_path",
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["replace", "append"],
                        "default": "replace",
                    },
                },
            },
        )

    # ------------------------------------------------------------------
    # BaseConnector
    # ------------------------------------------------------------------

    def test_connection(self, handle: ConnectionHandle) -> bool:
        base = Path(handle.config["base_path"])
        if handle.config.get("create_if_not_exists") and not base.exists():
            base.mkdir(parents=True, exist_ok=True)
        return base.is_dir()

    def introspect_objects(self, handle: ConnectionHandle) -> list[ObjectSchema]:
        base = Path(handle.config["base_path"])
        return [
            ObjectSchema(name=f.name, kind="file")
            for f in sorted(base.iterdir())
            if f.suffix in _SUPPORTED_SUFFIXES
        ]

    def introspect_columns(self, handle: ConnectionHandle, object_name: str) -> list[ColumnSchema]:
        df = self.sample(handle, object_name, limit=1)
        return [
            ColumnSchema(name=str(col), data_type=str(dtype)) for col, dtype in df.dtypes.items()
        ]

    # ------------------------------------------------------------------
    # SourceMixin
    # ------------------------------------------------------------------

    def read(self, handle: ConnectionHandle, config: ReadConfig) -> pd.DataFrame:
        base = Path(handle.config["base_path"])
        obj = config.object

        # Glob pattern support (e.g. "*.csv", "data_*.csv")
        if any(c in obj for c in ("*", "?", "[")):
            matched = sorted(glob.glob(str(base / obj)))
            if not matched:
                raise FileNotFoundError(f"No files matched pattern '{obj}' in {base}")
            frames: list[pd.DataFrame] = []
            for fp in matched:
                p = Path(fp)
                if p.suffix not in _READERS:
                    continue
                frames.append(_READERS[p.suffix](p))  # type: ignore[operator]
            if not frames:
                raise ValueError(f"No readable files matched '{obj}' (supported: {list(_READERS)})")
            df = pd.concat(frames, ignore_index=True)
        else:
            path = base / obj
            if path.suffix not in _READERS:
                raise ValueError(
                    f"Unsupported file format '{path.suffix}'. Supported: {list(_READERS)}"
                )
            df = _READERS[path.suffix](path)  # type: ignore[operator]

        if config.fields:
            df = df[config.fields]
        if config.filter:
            df = df.query(config.filter)
        if config.limit is not None:
            df = df.head(config.limit)
        return df.reset_index(drop=True)

    # ------------------------------------------------------------------
    # SinkMixin
    # ------------------------------------------------------------------

    def write(self, df: pd.DataFrame, handle: ConnectionHandle, config: WriteConfig) -> WriteResult:
        path = Path(handle.config["base_path"]) / config.object
        method = _WRITER_METHODS.get(path.suffix)
        if not method:
            raise ValueError(
                f"Unsupported output format '{path.suffix}'. Supported: {list(_WRITER_METHODS)}"
            )

        # Always ensure parent directory exists
        path.parent.mkdir(parents=True, exist_ok=True)

        if config.mode == "append" and path.exists() and path.suffix in (".csv",):
            existing = pd.read_csv(path)
            df = pd.concat([existing, df], ignore_index=True)

        writer = getattr(df, method)
        kwargs: dict = {"index": False}
        if path.suffix == ".json":
            kwargs = {"orient": "records"}
        writer(path, **kwargs)
        return WriteResult(rows_written=len(df))
