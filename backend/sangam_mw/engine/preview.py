"""Serialize DataFrames for step preview API responses."""

from __future__ import annotations

import math
from typing import Any

import pandas as pd


def dataframe_to_preview(df: pd.DataFrame, limit: int = 25) -> dict[str, Any]:
    total = len(df)
    sample = df.head(limit)

    def _cell(val: Any) -> Any:
        if val is None:
            return None
        if isinstance(val, float) and math.isnan(val):
            return None
        if hasattr(val, "isoformat"):
            return val.isoformat()
        if isinstance(val, (pd.Timestamp,)):
            return val.isoformat()
        if isinstance(val, (int, float, str, bool)):
            return val
        return str(val)

    columns = [
        {"name": str(col), "data_type": str(sample[col].dtype)}
        for col in sample.columns
    ]
    rows: list[dict[str, Any]] = []
    for _, row in sample.iterrows():
        rows.append({str(k): _cell(v) for k, v in row.items()})

    return {
        "columns": columns,
        "rows": rows,
        "row_count": total,
        "preview_row_count": len(rows),
        "truncated": total > len(rows),
    }
