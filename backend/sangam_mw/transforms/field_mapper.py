"""
FieldMapper — YAML declarative field spec compiled to vectorised pandas ops.

25+ built-in functions. No eval(). All operations are type-safe pandas Series ops.

YAML example:
  fields:
    - source: amount
      target: revenue
      fn: to_float
    - source: [first_name, last_name]
      target: full_name
      fn: concat
      sep: " "
    - target: status
      value: "active"          # literal
    - source: created_date
      target: created_at
      fn: to_datetime
      format: "%Y-%m-%d"
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from ..connectors.base.errors import DataTypeError, TransformSyntaxError


# ---------------------------------------------------------------------------
# Built-in transform functions
# Each takes one or more pd.Series plus optional keyword args.
# ---------------------------------------------------------------------------


def _lower(s: pd.Series) -> pd.Series:
    return s.str.lower()


def _upper(s: pd.Series) -> pd.Series:
    return s.str.upper()


def _strip(s: pd.Series) -> pd.Series:
    return s.str.strip()


def _to_float(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce").astype(float)


def _to_int(s: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(s, errors="coerce")
    return numeric.round().astype("Int64")


def _to_str(s: pd.Series) -> pd.Series:
    return s.astype(str).where(s.notna(), other=None)


def _to_bool(s: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(s):
        return s
    truth = {"true": True, "false": False, "1": True, "0": False, 1: True, 0: False, "yes": True, "no": False}
    return s.map(truth)


def _to_datetime(s: pd.Series, fmt: str | None = None) -> pd.Series:
    return pd.to_datetime(s, format=fmt, errors="coerce")


def _date_format(s: pd.Series, fmt: str = "%Y-%m-%d") -> pd.Series:
    return pd.to_datetime(s).dt.strftime(fmt)


def _date_add(s: pd.Series, days: int = 0) -> pd.Series:
    return pd.to_datetime(s) + pd.Timedelta(days=days)


def _date_diff(s1: pd.Series, s2: pd.Series, unit: str = "D") -> pd.Series:
    delta = pd.to_datetime(s1) - pd.to_datetime(s2)
    if unit == "D":
        return delta.dt.days
    if unit == "H":
        return (delta.dt.total_seconds() / 3600).astype(int)
    if unit == "M":
        return (delta.dt.total_seconds() / 60).astype(int)
    return delta.dt.total_seconds().astype(int)


def _round(s: pd.Series, decimals: int = 2) -> pd.Series:
    return s.round(decimals)


def _abs_fn(s: pd.Series) -> pd.Series:
    return s.abs()


def _clamp(s: pd.Series, min_val: Any = None, max_val: Any = None) -> pd.Series:
    return s.clip(lower=min_val, upper=max_val)


def _if_null(s: pd.Series, default: Any = None) -> pd.Series:
    return s.fillna(default)


def _coalesce(s: pd.Series, *others: pd.Series) -> pd.Series:
    result = s.copy()
    for other in others:
        result = result.where(result.notna(), other)
    return result


def _replace(s: pd.Series, old: str = "", new: str = "") -> pd.Series:
    return s.str.replace(old, new, regex=False)


def _regex_replace(s: pd.Series, pattern: str = "", replacement: str = "") -> pd.Series:
    return s.str.replace(pattern, replacement, regex=True)


def _concat(*series: pd.Series, sep: str = " ") -> pd.Series:
    if len(series) == 1:
        return series[0].astype(str)
    return series[0].astype(str).str.cat([s.astype(str) for s in series[1:]], sep=sep)


def _split(s: pd.Series, sep: str = ",", index: int = 0) -> pd.Series:
    return s.str.split(sep).str[index]


def _substring(s: pd.Series, start: int = 0, end: int | None = None) -> pd.Series:
    return s.str[start:end]


def _hash_fn(s: pd.Series) -> pd.Series:
    return s.astype(str).apply(lambda x: str(hash(x)))


def _json_extract(s: pd.Series, key: str = "") -> pd.Series:
    import json as _json

    def _get(v: Any) -> Any:
        if isinstance(v, str):
            try:
                v = _json.loads(v)
            except Exception:
                return None
        if isinstance(v, dict):
            return v.get(key)
        return None

    return s.apply(_get)


_FN_REGISTRY: dict[str, Any] = {
    "lower": _lower,
    "upper": _upper,
    "strip": _strip,
    "to_float": _to_float,
    "to_int": _to_int,
    "to_str": _to_str,
    "to_bool": _to_bool,
    "to_datetime": _to_datetime,
    "date_format": _date_format,
    "date_add": _date_add,
    "date_diff": _date_diff,
    "round": _round,
    "abs": _abs_fn,
    "clamp": _clamp,
    "if_null": _if_null,
    "coalesce": _coalesce,
    "replace": _replace,
    "regex_replace": _regex_replace,
    "concat": _concat,
    "split": _split,
    "substring": _substring,
    "hash": _hash_fn,
    "json_extract": _json_extract,
}


# ---------------------------------------------------------------------------
# FieldSpec dataclass
# ---------------------------------------------------------------------------


@dataclass
class FieldSpec:
    target: str
    source: str | list[str] | None = None
    fn: str | None = None
    value: Any = None  # literal constant — target column gets this value for all rows

    # fn kwargs (passed to the function only if non-default)
    format: str | None = None  # to_datetime, date_format
    sep: str = " "  # concat, split
    old: str = ""  # replace
    new: str = ""  # replace
    pattern: str = ""  # regex_replace
    replacement: str = ""  # regex_replace
    default: Any = None  # if_null
    decimals: int = 2  # round
    min_val: Any = None  # clamp
    max_val: Any = None  # clamp
    index: int = 0  # split
    start: int = 0  # substring
    end: int | None = None  # substring
    days: int = 0  # date_add
    unit: str = "D"  # date_diff
    key: str = ""  # json_extract


def _parse_spec(raw: dict) -> FieldSpec:
    known = set(FieldSpec.__dataclass_fields__)
    filtered = {k: v for k, v in raw.items() if k in known}
    return FieldSpec(**filtered)


# ---------------------------------------------------------------------------
# FieldMapper
# ---------------------------------------------------------------------------


class FieldMapper:
    """
    Compile a list of FieldSpec dicts to a callable that transforms a DataFrame.

    Usage:
        mapper = FieldMapper.from_yaml(specs_list)
        output_df = mapper.apply(input_df)
    """

    def __init__(self, specs: list[FieldSpec]) -> None:
        self._specs = specs

    @classmethod
    def from_yaml(cls, raw_specs: list[dict]) -> "FieldMapper":
        return cls([_parse_spec(s) for s in raw_specs])

    def validate(self, available_columns: list[str]) -> None:
        """Check that all source fields exist in the upstream schema."""
        for spec in self._specs:
            sources = (
                [spec.source]
                if isinstance(spec.source, str)
                else (spec.source or [])
            )
            for col in sources:
                if col not in available_columns:
                    raise TransformSyntaxError(
                        f"FieldMapper: source column '{col}' not found in upstream schema "
                        f"(available: {available_columns})"
                    )

    def apply(self, df: pd.DataFrame) -> pd.DataFrame:
        result: dict[str, Any] = {}
        for spec in self._specs:
            try:
                result[spec.target] = self._apply_spec(df, spec)
            except TransformSyntaxError:
                raise
            except Exception as exc:
                raise DataTypeError(
                    f"FieldMapper error on target '{spec.target}': {exc}"
                ) from exc
        return pd.DataFrame(result, index=df.index)

    def _apply_spec(self, df: pd.DataFrame, spec: FieldSpec) -> Any:
        if spec.value is not None and spec.fn is None and spec.source is None:
            return spec.value  # broadcast literal to all rows

        sources = (
            [spec.source]
            if isinstance(spec.source, str)
            else (spec.source or [])
        )

        if spec.fn is None:
            if not sources:
                return spec.value
            return df[sources[0]]  # plain rename

        fn = _FN_REGISTRY.get(spec.fn)
        if not fn:
            raise TransformSyntaxError(f"Unknown transform function: {spec.fn!r}")

        series = [df[s] for s in sources]
        kwargs = self._kwargs(spec)
        return fn(*series, **kwargs)

    @staticmethod
    def _kwargs(spec: FieldSpec) -> dict:
        kw: dict = {}
        if spec.format is not None:
            kw["fmt"] = spec.format
        if spec.sep != " ":
            kw["sep"] = spec.sep
        if spec.old:
            kw["old"] = spec.old
        if spec.new:
            kw["new"] = spec.new
        if spec.pattern:
            kw["pattern"] = spec.pattern
        if spec.replacement:
            kw["replacement"] = spec.replacement
        if spec.default is not None:
            kw["default"] = spec.default
        if spec.decimals != 2:
            kw["decimals"] = spec.decimals
        if spec.min_val is not None:
            kw["min_val"] = spec.min_val
        if spec.max_val is not None:
            kw["max_val"] = spec.max_val
        if spec.index != 0:
            kw["index"] = spec.index
        if spec.start != 0:
            kw["start"] = spec.start
        if spec.end is not None:
            kw["end"] = spec.end
        if spec.days != 0:
            kw["days"] = spec.days
        if spec.unit != "D":
            kw["unit"] = spec.unit
        if spec.key:
            kw["key"] = spec.key
        return kw


def available_functions() -> list[str]:
    return sorted(_FN_REGISTRY.keys())
