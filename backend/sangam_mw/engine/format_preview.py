"""Preview DataFrame serialized as the target file format (JSON, CSV, etc.)."""

from __future__ import annotations

from typing import Any

import pandas as pd

from .serialize_beautify import beautify_for_format


def dataframe_formatted_output(
    df: pd.DataFrame,
    output_format: str,
    config: dict[str, Any] | None = None,
    limit: int = 10,
) -> dict[str, Any] | None:
    cfg = config or {}
    fmt = (output_format or "").strip().lower().lstrip(".")
    if not fmt:
        return None

    sample = df.head(limit)
    if sample.empty:
        return {"format": fmt, "content": "", "truncated": False, "row_count": 0}

    truncated = len(df) > len(sample)

    if fmt == "json":
        orient = str(cfg.get("json_orient") or "records")
        raw = sample.to_json(orient=orient, date_format="iso", force_ascii=False)
        content = beautify_for_format(raw, "json")
        return {
            "format": "json",
            "content": content,
            "truncated": truncated,
            "row_count": len(df),
            "label": f"JSON ({orient})",
        }

    if fmt == "xml":
        content = _dataframe_to_xml(sample)
        content = beautify_for_format(content, "xml")
        return {
            "format": "xml",
            "content": content,
            "truncated": truncated,
            "row_count": len(df),
            "label": "XML",
        }

    if fmt == "csv":
        content = sample.to_csv(index=False)
        return {
            "format": "csv",
            "content": content,
            "truncated": truncated,
            "row_count": len(df),
            "label": "CSV",
        }

    if fmt == "parquet":
        return {
            "format": "parquet",
            "content": f"(Binary Parquet — {len(sample)} row preview as table above)",
            "truncated": truncated,
            "row_count": len(df),
            "label": "Parquet",
        }

    if fmt in ("xlsx", "excel"):
        return {
            "format": "xlsx",
            "content": f"(Excel workbook — {len(sample)} row preview as table above)",
            "truncated": truncated,
            "row_count": len(df),
            "label": "Excel",
        }

    return None


def _dataframe_to_xml(df: pd.DataFrame) -> str:
    try:
        return df.to_xml(index=False)
    except Exception:
        rows = []
        for _, row in df.iterrows():
            cells = "".join(
                f"<{_xml_tag(k)}>{_xml_escape(row[k])}</{_xml_tag(k)}>"
                for k in df.columns
            )
            rows.append(f"  <row>{cells}</row>")
        return f"<records>\n" + "\n".join(rows) + "\n</records>"


def _xml_tag(name: object) -> str:
    return str(name).strip().replace(" ", "_")


def _xml_escape(val: object) -> str:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        s = ""
    else:
        s = str(val)
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
