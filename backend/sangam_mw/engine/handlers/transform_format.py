"""TransformFormatHandler — pass-through DataFrame with format intent annotation."""

from __future__ import annotations

from typing import Any

import pandas as pd

from ..context import ExecutionContext
from .base import StepHandler


class TransformFormatHandler(StepHandler):
    @property
    def step_type(self) -> str:
        return "transform_format"

    def execute(self, config: dict[str, Any], context: ExecutionContext) -> pd.DataFrame:
        depends_on: list[str] = config.get("_depends_on", [])
        source_step: str = config.get("source_step") or (depends_on[0] if depends_on else "")
        if not source_step:
            raise ValueError("transform_format has no upstream step — connect it to a source node")

        df = context.get_output(source_step)

        # Propagate output_format hint and per-source files to downstream write steps
        step_id: str = config.get("_step_id", "")
        output_format: str = (config.get("output_format") or "").strip()
        if output_format and not output_format.startswith("."):
            output_format = f".{output_format}"

        if step_id:
            # Forward per-source file metadata so write_per_source still works downstream
            source_files = context.get_meta(f"_source_files_{source_step}")
            if source_files:
                context.set_meta(f"_source_files_{step_id}", source_files)

            if output_format:
                context.set_meta(f"_output_format_{step_id}", output_format)

        return df
