"""Unit tests for Phase 3 Transform Engine."""

from __future__ import annotations

import pytest
import pandas as pd

from sangam_mw.transforms import (
    FieldMapper,
    DuckDBEngine,
    PythonSandbox,
    EngineRouter,
    available_functions,
    validate_sql,
    validate_python,
    validate_yaml_fields,
)
from sangam_mw.connectors.base.errors import TransformSyntaxError, DataTypeError


# ---------------------------------------------------------------------------
# FieldMapper
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "name": ["Alice", "BOB", "  charlie  "],
            "amount": ["10.5", "20", "abc"],
            "age": [25, 30, None],
            "created": ["2024-01-01", "2024-06-15", "2024-12-31"],
            "first": ["John", "Jane", "Jim"],
            "last": ["Doe", "Smith", "Brown"],
            "raw_json": ['{"key": "val1"}', '{"key": "val2"}', "not_json"],
        }
    )


class TestFieldMapperBasicTransforms:
    def test_lower(self, sample_df: pd.DataFrame) -> None:
        mapper = FieldMapper.from_yaml([{"source": "name", "target": "name_lower", "fn": "lower"}])
        out = mapper.apply(sample_df)
        assert list(out["name_lower"]) == ["alice", "bob", "  charlie  "]

    def test_upper(self, sample_df: pd.DataFrame) -> None:
        mapper = FieldMapper.from_yaml([{"source": "name", "target": "name_up", "fn": "upper"}])
        out = mapper.apply(sample_df)
        assert list(out["name_up"]) == ["ALICE", "BOB", "  CHARLIE  "]

    def test_strip(self, sample_df: pd.DataFrame) -> None:
        mapper = FieldMapper.from_yaml([{"source": "name", "target": "name_stripped", "fn": "strip"}])
        out = mapper.apply(sample_df)
        assert out["name_stripped"][2] == "charlie"

    def test_to_float(self, sample_df: pd.DataFrame) -> None:
        mapper = FieldMapper.from_yaml([{"source": "amount", "target": "amount_f", "fn": "to_float"}])
        out = mapper.apply(sample_df)
        assert out["amount_f"][0] == pytest.approx(10.5)
        assert pd.isna(out["amount_f"][2])  # "abc" → NaN

    def test_to_int(self, sample_df: pd.DataFrame) -> None:
        mapper = FieldMapper.from_yaml([{"source": "amount", "target": "amount_i", "fn": "to_int"}])
        out = mapper.apply(sample_df)
        assert out["amount_i"][1] == 20

    def test_to_str(self, sample_df: pd.DataFrame) -> None:
        df = pd.DataFrame({"v": pd.array([25, 30, None], dtype="Int64")})
        mapper = FieldMapper.from_yaml([{"source": "v", "target": "v_s", "fn": "to_str"}])
        out = mapper.apply(df)
        assert out["v_s"][0] == "25"

    def test_if_null(self, sample_df: pd.DataFrame) -> None:
        mapper = FieldMapper.from_yaml([
            {"source": "age", "target": "age_safe", "fn": "if_null", "default": 0}
        ])
        out = mapper.apply(sample_df)
        assert out["age_safe"][2] == 0

    def test_round(self, sample_df: pd.DataFrame) -> None:
        df = pd.DataFrame({"v": [1.567, 2.891]})
        mapper = FieldMapper.from_yaml([{"source": "v", "target": "v_r", "fn": "round", "decimals": 1}])
        out = mapper.apply(df)
        assert out["v_r"][0] == pytest.approx(1.6)

    def test_clamp(self) -> None:
        df = pd.DataFrame({"v": [-5, 0, 15]})
        mapper = FieldMapper.from_yaml([
            {"source": "v", "target": "v_c", "fn": "clamp", "min_val": 0, "max_val": 10}
        ])
        out = mapper.apply(df)
        assert list(out["v_c"]) == [0, 0, 10]

    def test_replace(self, sample_df: pd.DataFrame) -> None:
        mapper = FieldMapper.from_yaml([
            {"source": "name", "target": "name_r", "fn": "replace", "old": "Bob", "new": "Robert"}
        ])
        out = mapper.apply(sample_df)

    def test_regex_replace(self, sample_df: pd.DataFrame) -> None:
        mapper = FieldMapper.from_yaml([
            {"source": "name", "target": "name_rr", "fn": "regex_replace",
             "pattern": r"\s+", "replacement": "_"}
        ])
        out = mapper.apply(sample_df)
        assert "_" in out["name_rr"][2]

    def test_concat(self, sample_df: pd.DataFrame) -> None:
        mapper = FieldMapper.from_yaml([
            {"source": ["first", "last"], "target": "full", "fn": "concat", "sep": " "}
        ])
        out = mapper.apply(sample_df)
        assert out["full"][0] == "John Doe"

    def test_split(self) -> None:
        df = pd.DataFrame({"v": ["a,b,c", "x,y"]})
        mapper = FieldMapper.from_yaml([{"source": "v", "target": "part", "fn": "split", "sep": ",", "index": 1}])
        out = mapper.apply(df)
        assert out["part"][0] == "b"

    def test_substring(self) -> None:
        df = pd.DataFrame({"v": ["hello", "world"]})
        mapper = FieldMapper.from_yaml([{"source": "v", "target": "sub", "fn": "substring", "start": 1, "end": 3}])
        out = mapper.apply(df)
        assert out["sub"][0] == "el"

    def test_json_extract(self, sample_df: pd.DataFrame) -> None:
        mapper = FieldMapper.from_yaml([
            {"source": "raw_json", "target": "k", "fn": "json_extract", "key": "key"}
        ])
        out = mapper.apply(sample_df)
        assert out["k"][0] == "val1"
        assert pd.isna(out["k"][2])

    def test_to_datetime(self, sample_df: pd.DataFrame) -> None:
        mapper = FieldMapper.from_yaml([
            {"source": "created", "target": "dt", "fn": "to_datetime", "format": "%Y-%m-%d"}
        ])
        out = mapper.apply(sample_df)
        assert out["dt"][0].year == 2024

    def test_date_format(self, sample_df: pd.DataFrame) -> None:
        mapper = FieldMapper.from_yaml([
            {"source": "created", "target": "dt_fmt", "fn": "date_format", "format": "%d/%m/%Y"}
        ])
        out = mapper.apply(sample_df)
        assert out["dt_fmt"][0] == "01/01/2024"

    def test_literal_value(self, sample_df: pd.DataFrame) -> None:
        mapper = FieldMapper.from_yaml([{"target": "status", "value": "active"}])
        out = mapper.apply(sample_df)
        assert all(out["status"] == "active")

    def test_plain_rename(self, sample_df: pd.DataFrame) -> None:
        mapper = FieldMapper.from_yaml([{"source": "name", "target": "full_name"}])
        out = mapper.apply(sample_df)
        assert list(out["full_name"]) == list(sample_df["name"])

    def test_unknown_fn_raises(self, sample_df: pd.DataFrame) -> None:
        mapper = FieldMapper.from_yaml([{"source": "name", "target": "x", "fn": "nonexistent"}])
        with pytest.raises(TransformSyntaxError):
            mapper.apply(sample_df)

    def test_validate_missing_source_raises(self, sample_df: pd.DataFrame) -> None:
        mapper = FieldMapper.from_yaml([{"source": "missing_col", "target": "x"}])
        with pytest.raises(TransformSyntaxError):
            mapper.validate(list(sample_df.columns))


class TestAvailableFunctions:
    def test_returns_list(self) -> None:
        fns = available_functions()
        assert "lower" in fns
        assert "to_float" in fns
        assert len(fns) >= 20


# ---------------------------------------------------------------------------
# DuckDBEngine
# ---------------------------------------------------------------------------


class TestDuckDBEngine:
    def test_simple_select(self) -> None:
        df = pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
        engine = DuckDBEngine()
        result = engine.execute("SELECT a, a + b AS c FROM src", frames={"src": df})
        assert list(result["c"]) == [5, 7, 9]

    def test_filter(self) -> None:
        df = pd.DataFrame({"v": [10, 20, 30]})
        engine = DuckDBEngine()
        result = engine.execute("SELECT v FROM src WHERE v > 15", frames={"src": df})
        assert len(result) == 2

    def test_aggregation(self) -> None:
        df = pd.DataFrame({"cat": ["a", "a", "b"], "val": [1, 2, 3]})
        engine = DuckDBEngine()
        result = engine.execute(
            "SELECT cat, SUM(val) AS total FROM src GROUP BY cat ORDER BY cat",
            frames={"src": df},
        )
        assert result[result["cat"] == "a"]["total"].values[0] == 3

    def test_bad_sql_raises(self) -> None:
        engine = DuckDBEngine()
        with pytest.raises(TransformSyntaxError):
            engine.execute("SELECT * FROM nonexistent_table", frames={})

    def test_multiple_frames(self) -> None:
        df1 = pd.DataFrame({"id": [1, 2], "val": [10, 20]})
        df2 = pd.DataFrame({"id": [1, 2], "label": ["a", "b"]})
        engine = DuckDBEngine()
        result = engine.execute(
            "SELECT t1.id, t1.val, t2.label FROM t1 JOIN t2 ON t1.id = t2.id",
            frames={"t1": df1, "t2": df2},
        )
        assert len(result) == 2

    def test_validate_sql_ok(self) -> None:
        df = pd.DataFrame({"x": [1]})
        validate_sql("SELECT x FROM src", {"src": df})  # should not raise

    def test_validate_sql_bad(self) -> None:
        with pytest.raises(TransformSyntaxError):
            validate_sql("SELECT @@invalid FROM nowhere", {})


# ---------------------------------------------------------------------------
# PythonSandbox
# ---------------------------------------------------------------------------


class TestPythonSandbox:
    def test_simple_transform(self) -> None:
        df = pd.DataFrame({"v": [1, 2, 3]})
        sandbox = PythonSandbox()
        result = sandbox.execute("result = df.copy()\nresult['v2'] = result['v'] * 2", df)
        assert list(result["v2"]) == [2, 4, 6]

    def test_missing_result_raises(self) -> None:
        df = pd.DataFrame({"v": [1]})
        sandbox = PythonSandbox()
        with pytest.raises(DataTypeError):
            sandbox.execute("x = 1", df)

    def test_wrong_result_type_raises(self) -> None:
        df = pd.DataFrame({"v": [1]})
        sandbox = PythonSandbox()
        with pytest.raises(DataTypeError):
            sandbox.execute("result = [1, 2, 3]", df)

    def test_blocked_os_import(self) -> None:
        df = pd.DataFrame({"v": [1]})
        with pytest.raises((TransformSyntaxError, ImportError)):
            validate_python("import os\nresult = df")

    def test_blocked_subprocess(self) -> None:
        with pytest.raises(TransformSyntaxError):
            validate_python("import subprocess")

    def test_validate_python_ok(self) -> None:
        validate_python("result = df.copy()")  # should not raise

    def test_validate_python_syntax_error(self) -> None:
        with pytest.raises(TransformSyntaxError):
            validate_python("result = df.copy(\nthis is not valid python")


# ---------------------------------------------------------------------------
# EngineRouter
# ---------------------------------------------------------------------------


class TestEngineRouter:
    def test_routes_to_duckdb_small(self) -> None:
        df = pd.DataFrame({"v": range(10)})
        router = EngineRouter(spark_threshold=100)
        result = router.execute("SELECT v * 2 AS v2 FROM src", frames={"src": df})
        assert len(result) == 10

    def test_routes_to_spark_fallback_large(self) -> None:
        # Without Spark installed, falls back to DuckDB and warns.
        df = pd.DataFrame({"v": range(10)})
        router = EngineRouter(spark_threshold=1)
        result = router.execute("SELECT v FROM src", frames={"src": df})
        assert len(result) == 10


# ---------------------------------------------------------------------------
# validators
# ---------------------------------------------------------------------------


class TestValidateYamlFields:
    def test_valid_spec(self) -> None:
        validate_yaml_fields([{"source": "x", "target": "y", "fn": "lower"}])

    def test_missing_target_raises(self) -> None:
        with pytest.raises(TransformSyntaxError):
            validate_yaml_fields([{"source": "x", "fn": "lower"}])

    def test_unknown_fn_raises(self) -> None:
        with pytest.raises(TransformSyntaxError):
            validate_yaml_fields([{"source": "x", "target": "y", "fn": "nonexistent_fn"}])

    def test_fn_without_source_or_value_raises(self) -> None:
        with pytest.raises(TransformSyntaxError):
            validate_yaml_fields([{"target": "y", "fn": "lower"}])

    def test_literal_without_source_ok(self) -> None:
        validate_yaml_fields([{"target": "status", "value": "active"}])  # no fn, no source
