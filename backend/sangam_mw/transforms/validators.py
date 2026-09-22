"""
Deploy-time validators for transforms.

All validators raise TransformSyntaxError on failure so the flow
is rejected before any data moves.
"""

from __future__ import annotations

import pandas as pd

from ..connectors.base.errors import TransformSyntaxError


def validate_sql(sql: str, sample_frames: dict[str, pd.DataFrame] | None = None) -> None:
    """Validate SQL using DuckDB EXPLAIN against empty sample frames."""
    from .duckdb_engine import validate_sql as _duckdb_validate
    _duckdb_validate(sql, sample_frames or {})


def validate_python(code: str) -> None:
    """Validate Python using py_compile + blocked-module scan."""
    from .python_sandbox import validate_python as _sandbox_validate
    _sandbox_validate(code)


def validate_yaml_fields(raw_specs: list[dict]) -> None:
    """
    Validate that each field spec has a `target` and that any `fn`
    is a known built-in.
    """
    from .field_mapper import available_functions

    known_fns = set(available_functions())
    for i, spec in enumerate(raw_specs):
        if "target" not in spec:
            raise TransformSyntaxError(
                f"Field spec at index {i} is missing required 'target' key"
            )
        fn = spec.get("fn")
        if fn is not None and fn not in known_fns:
            raise TransformSyntaxError(
                f"Field spec at index {i} uses unknown function '{fn}'. "
                f"Available: {sorted(known_fns)}"
            )
        source = spec.get("source")
        if fn is not None and source is None and spec.get("value") is None:
            raise TransformSyntaxError(
                f"Field spec at index {i} (target='{spec['target']}') specifies "
                f"fn='{fn}' but has no 'source' or 'value'"
            )
