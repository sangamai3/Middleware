"""
ConnectorReadHandler / ConnectorWriteHandler.

These handlers delegate to the connector framework:
  - ConnectorReadHandler: calls connector.read() and caches result
  - ConnectorWriteHandler: calls connector.write() on upstream output

Both require connection_id and object keys in step config.
"""

from __future__ import annotations

import glob as _glob
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from ..context import ExecutionContext
from .base import StepHandler
from ...connectors.base.registry import registry
from ...connectors.base.schemas import ConnectionHandle, ReadConfig, WriteConfig


class ConnectorReadHandler(StepHandler):
    @property
    def step_type(self) -> str:
        return "connector_read"

    def execute(
        self,
        config: dict[str, Any],
        context: ExecutionContext,
    ) -> pd.DataFrame:
        connector_id: str = config["connector_id"]
        connection_config: dict = config.get("conn", config.get("connection_config", {}))
        object_name: str = config["object"]
        step_id: str = config.get("_step_id", "")

        connector = registry.get(connector_id)
        handle = ConnectionHandle(
            connection_id=config.get("connection_id", "inline"),
            connector_id=connector_id,
            config=connection_config,
        )
        read_cfg = ReadConfig(
            object=object_name,
            fields=config.get("fields"),
            filter=config.get("filter"),
            limit=config.get("limit"),
            extra=config.get("extra", config.get("options", {})),
        )
        result = connector.read(handle, read_cfg)  # type: ignore[union-attr]

        # For file connector with a glob pattern, store per-file frames so the
        # write handler can write them separately when write_per_source is set.
        if connector_id == "file" and step_id and any(c in object_name for c in ("*", "?", "[")):
            from ...connectors.file.connector import _READERS
            base = Path(connection_config.get("base_path", ""))
            matched = sorted(_glob.glob(str(base / object_name)))
            source_files: dict[str, pd.DataFrame] = {}
            for fp in matched:
                p = Path(fp)
                reader = _READERS.get(p.suffix)
                if reader:
                    source_files[p.name] = reader(p)  # type: ignore[operator]
            if source_files:
                context.set_meta(f"_source_files_{step_id}", source_files)

        return result


class ConnectorWriteHandler(StepHandler):
    @property
    def step_type(self) -> str:
        return "connector_write"

    def execute(
        self,
        config: dict[str, Any],
        context: ExecutionContext,
    ) -> None:
        depends_on: list[str] = config.get("_depends_on", [])
        source_step: str = config.get("source_step") or (depends_on[0] if depends_on else "")
        if not source_step:
            raise ValueError("connector_write has no upstream step — connect it to a source node")
        connector_id: str = config["connector_id"]
        connection_config: dict = config.get("conn", config.get("connection_config", {}))
        add_ts = str(config.get("add_timestamp", "false")).lower() == "true"
        write_mode: str = config.get("mode", "replace")
        extra: dict = config.get("extra", config.get("options", {}))
        write_per_source = str(config.get("write_per_source", "false")).lower() == "true"

        connector = registry.get(connector_id)
        handle = ConnectionHandle(
            connection_id=config.get("connection_id", "inline"),
            connector_id=connector_id,
            config=connection_config,
        )

        source_files: dict[str, pd.DataFrame] | None = context.get_meta(f"_source_files_{source_step}")

        if write_per_source and source_files:
            # Write each source file as a separate output file
            ts = datetime.now().strftime("%Y%m%d_%H%M%S") if add_ts else ""
            for filename, df in source_files.items():
                p = Path(filename)
                out_name = f"{p.stem}_{ts}{p.suffix}" if (add_ts and p.suffix) else (f"{p.stem}_{ts}" if add_ts else filename)
                write_cfg = WriteConfig(object=out_name, mode=write_mode, extra=extra)
                connector.write(df, handle, write_cfg)  # type: ignore[union-attr]
            return

        # Default: single merged write
        object_name: str = config.get("object") or ""
        if not object_name:
            raise ValueError("connector_write: 'object' (output filename) is required when not using write_per_source")
        df = context.get_output(source_step)
        if add_ts:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            p = Path(object_name)
            object_name = f"{p.stem}_{ts}{p.suffix}" if p.suffix else f"{object_name}_{ts}"
        write_cfg = WriteConfig(object=object_name, mode=write_mode, extra=extra)
        connector.write(df, handle, write_cfg)  # type: ignore[union-attr]
        return None
