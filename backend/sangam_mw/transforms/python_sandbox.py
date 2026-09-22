"""
PythonSandbox — RestrictedPython-based user script execution.

Allowlisted modules: pandas, numpy, re, json, datetime, math, collections, itertools, functools
Blocklisted: os, subprocess, socket, open, __import__, eval, exec, compile

The user's code receives `df` as a pandas DataFrame and must return a DataFrame
via the name `result`. Example:

    result = df.copy()
    result["revenue"] = result["amount"] * 1.1
"""

from __future__ import annotations

import builtins
import math
import re
import json
import collections
import itertools
import functools
import datetime
from typing import Any

import pandas as pd

from ..connectors.base.errors import TransformSyntaxError, DataTypeError

try:
    from RestrictedPython import compile_restricted, safe_globals
    from RestrictedPython.Guards import (
        safe_builtins,
        guarded_iter_unpack_sequence,
        guarded_unpack_sequence,
    )
    _HAS_RESTRICTED = True
except ImportError:
    _HAS_RESTRICTED = False

_ALLOWED_MODULES: dict[str, Any] = {
    "pandas": pd,
    "pd": pd,
    "re": re,
    "json": json,
    "math": math,
    "datetime": datetime,
    "collections": collections,
    "itertools": itertools,
    "functools": functools,
}

try:
    import numpy as np
    _ALLOWED_MODULES["numpy"] = np
    _ALLOWED_MODULES["np"] = np
except ImportError:
    pass


def _safe_import(name: str, *args: Any, **kwargs: Any) -> Any:
    top = name.split(".")[0]
    if top not in _ALLOWED_MODULES:
        raise ImportError(f"Module '{name}' is not allowed in sandbox transforms")
    mod = _ALLOWED_MODULES[top]
    # Handle dotted paths (e.g. "datetime.datetime")
    parts = name.split(".")[1:]
    for part in parts:
        mod = getattr(mod, part)
    return mod


def _guarded_getattr(obj: Any, name: str) -> Any:
    if name.startswith("_"):
        raise AttributeError(f"Access to private attribute '{name}' is not allowed")
    return getattr(obj, name)


def _guarded_getitem(obj: Any, index: Any) -> Any:
    return obj[index]


def _guarded_setattr(obj: Any, name: str, value: Any) -> None:
    if name.startswith("_"):
        raise AttributeError(f"Setting private attribute '{name}' is not allowed")
    setattr(obj, name, value)


class PythonSandbox:
    """
    Execute user-supplied Python code against a DataFrame.

    The code receives `df` (the input DataFrame) and must assign `result`
    to a DataFrame.  The sandbox blocks file I/O, network, OS calls, and
    dynamic code generation.
    """

    def execute(self, code: str, df: pd.DataFrame) -> pd.DataFrame:
        if not _HAS_RESTRICTED:
            raise TransformSyntaxError(
                "RestrictedPython is not installed; cannot execute sandboxed Python"
            )

        validate_python(code)

        byte_code = compile_restricted(code, filename="<transform>", mode="exec")

        glb: dict[str, Any] = dict(safe_globals)
        glb["__builtins__"] = dict(safe_builtins)
        glb["__builtins__"]["__import__"] = _safe_import
        glb["_getattr_"] = _guarded_getattr
        glb["_getitem_"] = _guarded_getitem
        glb["_setattr_"] = _guarded_setattr
        glb["_iter_unpack_sequence_"] = guarded_iter_unpack_sequence
        glb["_unpack_sequence_"] = guarded_unpack_sequence
        glb["_write_"] = lambda x: x  # allow attribute assignment on known objects

        # Inject allowed modules directly so code can reference `pd`, `np`, etc.
        glb.update(_ALLOWED_MODULES)

        loc: dict[str, Any] = {"df": df}

        try:
            exec(byte_code, glb, loc)  # noqa: S102 — restricted execution
        except Exception as exc:
            raise DataTypeError(
                f"Error executing sandboxed Python: {exc}"
            ) from exc

        result = loc.get("result")
        if result is None:
            raise DataTypeError(
                "Sandboxed Python code must assign a DataFrame to 'result'"
            )
        if not isinstance(result, pd.DataFrame):
            raise DataTypeError(
                f"'result' must be a DataFrame, got {type(result).__name__}"
            )
        return result


def validate_python(code: str) -> None:
    """
    Deploy-time validation: compile the code with py_compile semantics and
    check for blocked module names.  Raises TransformSyntaxError on failure.
    """
    import py_compile
    import tempfile
    import os

    _BLOCKED = {"os", "subprocess", "socket", "open", "sys", "shutil", "pathlib", "ctypes"}
    for token in _BLOCKED:
        if re.search(rf"\b{token}\b", code):
            raise TransformSyntaxError(
                f"Module/builtin '{token}' is not allowed in sandbox transforms"
            )

    with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w") as f:
        f.write(code)
        tmp = f.name
    try:
        try:
            py_compile.compile(tmp, doraise=True)
        except py_compile.PyCompileError as exc:
            raise TransformSyntaxError(
                f"Python syntax error: {exc}"
            ) from exc
    finally:
        os.unlink(tmp)
        pyc = tmp + "c"
        if os.path.exists(pyc):
            os.unlink(pyc)
