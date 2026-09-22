"""Tests for the FileConnector reference implementation."""

from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pytest

from sangam_mw.connectors.base.metadata import AuthType, OperationType
from sangam_mw.connectors.base.schemas import ConnectionHandle, ReadConfig, WriteConfig
from sangam_mw.connectors.file.connector import FileConnector


@pytest.fixture
def connector() -> FileConnector:
    return FileConnector()


@pytest.fixture
def handle(tmp_path: Path) -> ConnectionHandle:
    return ConnectionHandle(
        connector_id="file",
        connection_id="test",
        config={"base_path": str(tmp_path)},
        created_at=datetime.now(UTC),
    )


@pytest.fixture
def sample_csv(tmp_path: Path) -> Path:
    path = tmp_path / "customers.csv"
    pd.DataFrame(
        {
            "id": [1, 2, 3],
            "name": ["Alice", "Bob", "Carol"],
            "amount": [100.0, 200.0, 300.0],
        }
    ).to_csv(path, index=False)
    return path


class TestMetadata:
    def test_connector_id(self, connector: FileConnector) -> None:
        assert connector.metadata.connector_id == "file"

    def test_auth_type_is_none(self, connector: FileConnector) -> None:
        assert connector.metadata.auth_type == AuthType.NONE

    def test_supports_read_and_write(self, connector: FileConnector) -> None:
        ops = connector.metadata.operations
        assert OperationType.READ in ops
        assert OperationType.WRITE in ops

    def test_has_connection_schema(self, connector: FileConnector) -> None:
        schema = connector.metadata.connection_schema
        assert schema is not None
        assert "base_path" in schema["properties"]
        assert schema["properties"]["base_path"]["type"] == "string"


class TestConnection:
    def test_ok_when_dir_exists(self, connector: FileConnector, handle: ConnectionHandle) -> None:
        assert connector.test_connection(handle) is True

    def test_fails_when_dir_missing(self, connector: FileConnector) -> None:
        bad = ConnectionHandle(
            connector_id="file",
            connection_id="x",
            config={"base_path": "/nonexistent/path/abc123"},
            created_at=datetime.now(UTC),
        )
        assert connector.test_connection(bad) is False


class TestIntrospect:
    def test_introspect_objects_lists_csv(
        self, connector: FileConnector, handle: ConnectionHandle, sample_csv: Path
    ) -> None:
        objects = connector.introspect_objects(handle)
        names = [o.name for o in objects]
        assert "customers.csv" in names

    def test_introspect_objects_ignores_unsupported(
        self, connector: FileConnector, handle: ConnectionHandle, tmp_path: Path
    ) -> None:
        (tmp_path / "notes.txt").write_text("hello")
        objects = connector.introspect_objects(handle)
        names = [o.name for o in objects]
        assert "notes.txt" not in names

    def test_introspect_columns_returns_all(
        self, connector: FileConnector, handle: ConnectionHandle, sample_csv: Path
    ) -> None:
        cols = connector.introspect_columns(handle, "customers.csv")
        names = [c.name for c in cols]
        assert "id" in names
        assert "name" in names
        assert "amount" in names


class TestRead:
    def test_read_csv_all_rows(
        self, connector: FileConnector, handle: ConnectionHandle, sample_csv: Path
    ) -> None:
        df = connector.read(handle, ReadConfig(object="customers.csv"))
        assert len(df) == 3
        assert list(df.columns) == ["id", "name", "amount"]

    def test_read_with_limit(
        self, connector: FileConnector, handle: ConnectionHandle, sample_csv: Path
    ) -> None:
        df = connector.read(handle, ReadConfig(object="customers.csv", limit=2))
        assert len(df) == 2

    def test_read_with_field_selection(
        self, connector: FileConnector, handle: ConnectionHandle, sample_csv: Path
    ) -> None:
        df = connector.read(handle, ReadConfig(object="customers.csv", fields=["id", "name"]))
        assert list(df.columns) == ["id", "name"]

    def test_read_with_filter(
        self, connector: FileConnector, handle: ConnectionHandle, sample_csv: Path
    ) -> None:
        df = connector.read(handle, ReadConfig(object="customers.csv", filter="amount > 150"))
        assert len(df) == 2
        assert all(df["amount"] > 150)

    def test_read_parquet(
        self, connector: FileConnector, handle: ConnectionHandle, tmp_path: Path
    ) -> None:
        path = tmp_path / "data.parquet"
        pd.DataFrame({"x": [1, 2, 3]}).to_parquet(path, index=False)
        df = connector.read(handle, ReadConfig(object="data.parquet"))
        assert len(df) == 3

    def test_read_excel(
        self, connector: FileConnector, handle: ConnectionHandle, tmp_path: Path
    ) -> None:
        path = tmp_path / "data.xlsx"
        pd.DataFrame({"x": [1, 2, 3]}).to_excel(path, index=False)
        df = connector.read(handle, ReadConfig(object="data.xlsx"))
        assert len(df) == 3

    def test_write_json(
        self, connector: FileConnector, handle: ConnectionHandle, tmp_path: Path
    ) -> None:
        df = pd.DataFrame({"a": [10, 20]})
        result = connector.write(df, handle, WriteConfig(object="out.json"))
        assert result.rows_written == 2
        assert (tmp_path / "out.json").exists()

    def test_read_unsupported_format_raises(
        self, connector: FileConnector, handle: ConnectionHandle, tmp_path: Path
    ) -> None:
        (tmp_path / "data.xml").write_text("<root/>")
        with pytest.raises(ValueError, match="Unsupported file format"):
            connector.read(handle, ReadConfig(object="data.xml"))


class TestWrite:
    def test_write_csv_creates_file(
        self, connector: FileConnector, handle: ConnectionHandle, tmp_path: Path
    ) -> None:
        df = pd.DataFrame({"id": [1, 2], "val": ["a", "b"]})
        result = connector.write(df, handle, WriteConfig(object="output.csv"))
        assert result.rows_written == 2
        assert (tmp_path / "output.csv").exists()

    def test_write_roundtrip(
        self, connector: FileConnector, handle: ConnectionHandle, tmp_path: Path
    ) -> None:
        original = pd.DataFrame({"id": [1, 2, 3], "name": ["x", "y", "z"]})
        connector.write(original, handle, WriteConfig(object="out.csv"))
        read_back = pd.read_csv(tmp_path / "out.csv")
        assert len(read_back) == 3
        assert list(read_back.columns) == ["id", "name"]

    def test_write_parquet(
        self, connector: FileConnector, handle: ConnectionHandle, tmp_path: Path
    ) -> None:
        df = pd.DataFrame({"x": [1, 2, 3]})
        result = connector.write(df, handle, WriteConfig(object="out.parquet"))
        assert result.rows_written == 3
        assert (tmp_path / "out.parquet").exists()

    def test_append_mode_csv(
        self, connector: FileConnector, handle: ConnectionHandle, tmp_path: Path
    ) -> None:
        df1 = pd.DataFrame({"id": [1, 2]})
        df2 = pd.DataFrame({"id": [3, 4]})
        connector.write(df1, handle, WriteConfig(object="data.csv", mode="replace"))
        result = connector.write(df2, handle, WriteConfig(object="data.csv", mode="append"))
        combined = pd.read_csv(tmp_path / "data.csv")
        assert len(combined) == 4
        assert result.rows_written == 4

    def test_write_unsupported_format_raises(
        self, connector: FileConnector, handle: ConnectionHandle
    ) -> None:
        df = pd.DataFrame({"a": [1]})
        with pytest.raises(ValueError, match="Unsupported output format"):
            connector.write(df, handle, WriteConfig(object="out.xml"))

    def test_sample_returns_limited_rows(
        self, connector: FileConnector, handle: ConnectionHandle, sample_csv: Path
    ) -> None:
        df = connector.sample(handle, "customers.csv", limit=2)
        assert len(df) == 2
