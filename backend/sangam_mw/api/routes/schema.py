"""
Schema inference routes.

POST /schema/infer  — parse CSV / JSON / XML sample text → [{name, type, nullable}]
"""

from __future__ import annotations

import csv
import io
import json
import re
from typing import Any

import pandas as pd
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..auth import get_current_user
from fastapi import Depends

router = APIRouter(prefix="/schema", tags=["schema"])


# ---------------------------------------------------------------------------
# Type detection helpers
# ---------------------------------------------------------------------------

_DATE_PATTERNS = [
    (r"^\d{4}-\d{2}-\d{2}$",                 "date",     "%Y-%m-%d"),
    (r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}",   "datetime", None),
    (r"^\d{2}/\d{2}/\d{4}$",                  "date",     "%d/%m/%Y"),
    (r"^\d{2}-\d{2}-\d{4}$",                  "date",     "%d-%m-%Y"),
    (r"^\d{4}/\d{2}/\d{2}$",                  "date",     "%Y/%m/%d"),
]


def _infer_type(series: "pd.Series") -> dict[str, str | None]:
    """Return {type, date_format} for a single pandas Series."""
    non_null = series.dropna().astype(str).str.strip()
    non_null = non_null[non_null != ""]

    if non_null.empty:
        return {"type": "string", "date_format": None}

    # Boolean
    bool_vals = {"true", "false", "yes", "no", "1", "0"}
    if non_null.str.lower().isin(bool_vals).all():
        return {"type": "boolean", "date_format": None}

    # Integer
    try:
        pd.to_numeric(non_null, errors="raise").astype(int)
        if non_null.str.contains(r"\.", regex=False).any():
            return {"type": "number", "date_format": None}
        return {"type": "integer", "date_format": None}
    except (ValueError, OverflowError):
        pass

    # Float
    try:
        pd.to_numeric(non_null, errors="raise")
        return {"type": "number", "date_format": None}
    except (ValueError, OverflowError):
        pass

    # Date / datetime
    sample = non_null.iloc[0]
    for pattern, type_name, fmt in _DATE_PATTERNS:
        if re.match(pattern, sample):
            return {"type": type_name, "date_format": fmt}

    return {"type": "string", "date_format": None}


def _df_to_schema(df: "pd.DataFrame") -> list[dict[str, Any]]:
    fields = []
    for col in df.columns:
        series = df[col]
        nullable = bool(series.isna().any() or (series.astype(str).str.strip() == "").any())
        type_info = _infer_type(series)
        fields.append({
            "name": str(col),
            "type": type_info["type"],
            "nullable": nullable,
            "date_format": type_info.get("date_format"),
        })
    return fields


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------

def _parse_csv(text: str) -> "pd.DataFrame":
    return pd.read_csv(io.StringIO(text.strip()), dtype=str, keep_default_na=False)


def _parse_json(text: str) -> "pd.DataFrame":
    parsed = json.loads(text.strip())
    if isinstance(parsed, list):
        return pd.DataFrame(parsed)
    if isinstance(parsed, dict):
        # Single object or {field: [values]} orientations
        try:
            return pd.DataFrame([parsed])
        except Exception:
            return pd.DataFrame(parsed)
    raise ValueError("JSON must be an array of objects or a single object")


def _parse_xml(text: str) -> "pd.DataFrame":
    try:
        return pd.read_xml(io.StringIO(text.strip()))
    except Exception as exc:
        raise ValueError(f"Could not parse XML: {exc}") from exc


def _detect_and_parse(text: str, hint: str | None) -> "pd.DataFrame":
    stripped = text.strip()
    fmt = (hint or "").lower()

    if fmt == "csv" or (not fmt and "," in stripped.split("\n")[0] and not stripped.startswith("{")):
        return _parse_csv(stripped)
    if fmt == "json" or stripped.startswith(("{", "[")):
        return _parse_json(stripped)
    if fmt == "xml" or stripped.startswith("<"):
        return _parse_xml(stripped)
    # Fallback: try CSV
    return _parse_csv(stripped)


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class InferSchemaRequest(BaseModel):
    sample: str          # raw sample text (CSV rows, JSON array, XML snippet)
    format: str | None = None   # "csv" | "json" | "xml" — auto-detected if omitted
    label: str | None = None    # optional name tag stored back in response


class SchemaField(BaseModel):
    name: str
    type: str            # "string" | "integer" | "number" | "boolean" | "date" | "datetime"
    nullable: bool = False
    date_format: str | None = None


class InferSchemaResponse(BaseModel):
    fields: list[SchemaField]
    detected_format: str
    row_count: int
    label: str | None = None


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------

@router.post("/infer", response_model=InferSchemaResponse)
def infer_schema(
    req: InferSchemaRequest,
    _user: dict = Depends(get_current_user),
) -> InferSchemaResponse:
    """Parse sample data and return inferred field schema."""
    if not req.sample or not req.sample.strip():
        raise HTTPException(status_code=400, detail="sample text is required")

    stripped = req.sample.strip()
    detected_format = req.format or (
        "json" if stripped.startswith(("{", "["))
        else "xml" if stripped.startswith("<")
        else "csv"
    )

    try:
        df = _detect_and_parse(stripped, req.format)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Could not parse sample: {exc}") from exc

    if df.empty or len(df.columns) == 0:
        raise HTTPException(status_code=422, detail="Sample produced no columns — check format")

    raw_fields = _df_to_schema(df)
    fields = [SchemaField(**f) for f in raw_fields]

    return InferSchemaResponse(
        fields=fields,
        detected_format=detected_format,
        row_count=len(df),
        label=req.label,
    )
