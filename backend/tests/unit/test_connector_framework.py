"""Unit tests for the connector framework base classes."""

from datetime import UTC, datetime

import pandas as pd
import pytest

from sangam_mw.connectors.base.connector import BaseConnector, SinkMixin, SourceMixin
from sangam_mw.connectors.base.errors import AuthenticationError, RateLimitError, RetryBehavior
from sangam_mw.connectors.base.metadata import AuthType, ConnectorMetadata, OperationType
from sangam_mw.connectors.base.schemas import (
    ColumnSchema,
    ConnectionHandle,
    ObjectSchema,
    ReadConfig,
    WriteConfig,
    WriteResult,
)


def _handle(config: dict | None = None) -> ConnectionHandle:
    return ConnectionHandle(
        connector_id="test",
        connection_id="test-conn",
        config=config or {},
        created_at=datetime.now(UTC),
    )


class _MinimalConnector(BaseConnector, SourceMixin, SinkMixin):
    @property
    def metadata(self) -> ConnectorMetadata:
        return ConnectorMetadata(
            connector_id="test",
            label="Test",
            family="test",
            version="1.0.0",
            auth_type=AuthType.NONE,
            operations=[OperationType.READ, OperationType.WRITE],
        )

    def test_connection(self, handle: ConnectionHandle) -> bool:
        return True

    def introspect_objects(self, handle: ConnectionHandle) -> list[ObjectSchema]:
        return [ObjectSchema(name="table_a"), ObjectSchema(name="table_b", kind="view")]

    def introspect_columns(self, handle: ConnectionHandle, object_name: str) -> list[ColumnSchema]:
        return [
            ColumnSchema(name="id", data_type="int64", is_primary_key=True),
            ColumnSchema(name="name", data_type="object"),
        ]

    def read(self, handle: ConnectionHandle, config: ReadConfig) -> pd.DataFrame:
        return pd.DataFrame({"id": [1, 2, 3], "name": ["a", "b", "c"]})

    def write(self, df: pd.DataFrame, handle: ConnectionHandle, config: WriteConfig) -> WriteResult:
        return WriteResult(rows_written=len(df))


class TestBaseConnectorContract:
    def test_metadata_fields(self) -> None:
        c = _MinimalConnector()
        assert c.metadata.connector_id == "test"
        assert c.metadata.auth_type == AuthType.NONE
        assert OperationType.READ in c.metadata.operations

    def test_test_connection_returns_bool(self) -> None:
        assert _MinimalConnector().test_connection(_handle()) is True

    def test_introspect_objects(self) -> None:
        objects = _MinimalConnector().introspect_objects(_handle())
        assert len(objects) == 2
        assert objects[0].name == "table_a"
        assert objects[1].kind == "view"

    def test_introspect_columns(self) -> None:
        cols = _MinimalConnector().introspect_columns(_handle(), "table_a")
        pk_cols = [c for c in cols if c.is_primary_key]
        assert len(pk_cols) == 1
        assert pk_cols[0].name == "id"

    def test_sample_delegates_to_read(self) -> None:
        df = _MinimalConnector().sample(_handle(), "table_a", limit=10)
        assert isinstance(df, pd.DataFrame)
        assert len(df) <= 10

    def test_sample_raises_if_not_source(self) -> None:
        class _WriteOnly(BaseConnector, SinkMixin):
            @property
            def metadata(self):  # type: ignore[override]
                return ConnectorMetadata("w", "W", "t", "1", AuthType.NONE, [OperationType.WRITE])

            def test_connection(self, h):  # type: ignore[override]
                return True

            def introspect_objects(self, h):  # type: ignore[override]
                return []

            def introspect_columns(self, h, n):  # type: ignore[override]
                return []

            def write(self, df, h, cfg):  # type: ignore[override]
                return WriteResult(rows_written=len(df))

        with pytest.raises(TypeError, match="does not support reading"):
            _WriteOnly().sample(_handle(), "x")


class TestSourceMixin:
    def test_read_returns_dataframe(self) -> None:
        df = _MinimalConnector().read(_handle(), ReadConfig(object="table_a"))
        assert isinstance(df, pd.DataFrame)
        assert list(df.columns) == ["id", "name"]

    def test_read_batch_default_yields_once(self) -> None:
        batches = list(_MinimalConnector().read_batch(_handle(), ReadConfig(object="table_a")))
        assert len(batches) == 1
        assert len(batches[0]) == 3


class TestSinkMixin:
    def test_write_returns_result(self) -> None:
        df = pd.DataFrame({"id": [1, 2]})
        result = _MinimalConnector().write(df, _handle(), WriteConfig(object="out"))
        assert result.rows_written == 2

    def test_write_batch_concats_and_writes(self) -> None:
        batches = iter([pd.DataFrame({"id": [1]}), pd.DataFrame({"id": [2, 3]})])
        result = _MinimalConnector().write_batch(batches, _handle(), WriteConfig(object="out"))
        assert result.rows_written == 3


class TestErrors:
    def test_rate_limit_is_retryable(self) -> None:
        err = RateLimitError("Too many requests", retry_after=30)
        assert err.retry_behavior == RetryBehavior.RETRYABLE
        assert err.retry_after == 30
        assert "Too many requests" in str(err)

    def test_auth_error_is_non_retryable(self) -> None:
        err = AuthenticationError("Invalid credentials")
        assert err.retry_behavior == RetryBehavior.NON_RETRYABLE

    def test_exception_carries_context_fields(self) -> None:
        err = AuthenticationError("bad", flow_id="flow-1", run_id="run-1", step_id="step-1")
        assert err.flow_id == "flow-1"
        assert err.run_id == "run-1"
        assert err.step_id == "step-1"


class TestConnectionManager:
    def test_encrypt_decrypt_roundtrip(self) -> None:
        from cryptography.fernet import Fernet

        from sangam_mw.connectors.base.connection import ConnectionManager

        key = Fernet.generate_key()
        mgr = ConnectionManager(key)
        secret = "super-secret-password-123"
        encrypted = mgr.encrypt_secret(secret)
        assert encrypted != secret
        assert mgr.decrypt_secret(encrypted) == secret

    def test_decrypt_config_decrypts_secret_fields(self) -> None:
        from cryptography.fernet import Fernet

        from sangam_mw.connectors.base.connection import ConnectionManager

        key = Fernet.generate_key()
        mgr = ConnectionManager(key)
        schema = {
            "properties": {
                "host": {"type": "string"},
                "password": {"type": "string", "secret": True},
            }
        }
        encrypted_pw = mgr.encrypt_secret("mypassword")
        config = {"host": "localhost", "password": encrypted_pw}
        result = mgr.decrypt_config(config, schema)
        assert result["password"] == "mypassword"
        assert result["host"] == "localhost"

    def test_encrypt_config_roundtrip(self) -> None:
        from cryptography.fernet import Fernet

        from sangam_mw.connectors.base.connection import ConnectionManager

        key = Fernet.generate_key()
        mgr = ConnectionManager(key)
        schema = {
            "properties": {
                "host": {"type": "string"},
                "password": {"type": "string", "secret": True},
            }
        }
        encrypted = mgr.encrypt_config({"host": "localhost", "password": "pw"}, schema)
        assert encrypted["host"] == "localhost"
        assert encrypted["password"] != "pw"
        decrypted = mgr.decrypt_config(encrypted, schema)
        assert decrypted["password"] == "pw"

    def test_decrypt_invalid_token_passthrough(self) -> None:
        from cryptography.fernet import Fernet

        from sangam_mw.connectors.base.connection import ConnectionManager

        mgr = ConnectionManager(Fernet.generate_key())
        assert mgr.decrypt_secret("not-a-fernet-token") == "not-a-fernet-token"

    @pytest.mark.asyncio
    async def test_get_handle_refreshes_oauth(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from datetime import UTC, datetime, timedelta

        from cryptography.fernet import Fernet

        from sangam_mw.connectors.base.connection import ConnectionManager
        from sangam_mw.connectors.base.metadata import AuthType, ConnectorMetadata, OperationType

        class _OAuthConnector(_MinimalConnector):
            @property
            def metadata(self) -> ConnectorMetadata:
                return ConnectorMetadata(
                    connector_id="oauth-test",
                    label="OAuth Test",
                    family="test",
                    version="1.0.0",
                    auth_type=AuthType.OAUTH2,
                    operations=[OperationType.READ, OperationType.WRITE],
                    connection_schema={
                        "type": "object",
                        "properties": {
                            "access_token": {"type": "string"},
                            "refresh_token": {"type": "string"},
                            "client_id": {"type": "string"},
                            "token_url": {"type": "string"},
                        },
                    },
                )

        class _FakeHandler:
            def needs_refresh(self, expires_at: datetime | None, buffer_seconds: int = 60) -> bool:
                return True

            async def refresh(self, config: dict) -> dict:
                updated = dict(config)
                updated["access_token"] = "refreshed-token"
                updated["token_expires_at"] = datetime.now(UTC) + timedelta(hours=1)
                return updated

        monkeypatch.setattr(
            "sangam_mw.connectors.base.connection.OAuth2Handler",
            lambda: _FakeHandler(),
        )
        mgr = ConnectionManager(Fernet.generate_key(), ttl_seconds=60)
        handle = await mgr.get_handle(
            _OAuthConnector(),
            "conn-oauth",
            {
                "access_token": "old",
                "refresh_token": "r",
                "client_id": "cid",
                "token_url": "https://example.com/token",
                "token_expires_at": (datetime.now(UTC) - timedelta(seconds=1)).isoformat(),
            },
        )
        assert handle.config["access_token"] == "refreshed-token"
        assert handle.token_expires_at is not None

    @pytest.mark.asyncio
    async def test_get_handle_caches(self) -> None:
        from cryptography.fernet import Fernet

        from sangam_mw.connectors.base.connection import ConnectionManager

        mgr = ConnectionManager(Fernet.generate_key(), ttl_seconds=60)
        connector = _MinimalConnector()
        config = {}
        h1 = await mgr.get_handle(connector, "conn-1", config)
        h2 = await mgr.get_handle(connector, "conn-1", config)
        assert h1 is h2  # same object from pool

    @pytest.mark.asyncio
    async def test_invalidate_removes_from_pool(self) -> None:
        from cryptography.fernet import Fernet

        from sangam_mw.connectors.base.connection import ConnectionManager

        mgr = ConnectionManager(Fernet.generate_key(), ttl_seconds=60)
        connector = _MinimalConnector()
        h1 = await mgr.get_handle(connector, "conn-2", {})
        await mgr.invalidate("conn-2")
        h2 = await mgr.get_handle(connector, "conn-2", {})
        assert h1 is not h2  # new handle after invalidation


class TestConnectorRegistry:
    def test_registry_loads_file_connector(self) -> None:
        from sangam_mw.connectors.base.registry import ConnectorRegistry

        reg = ConnectorRegistry()
        reg.load()
        assert "file" in reg.ids()

    def test_registry_get_returns_instance(self) -> None:
        from sangam_mw.connectors.base.registry import ConnectorRegistry
        from sangam_mw.connectors.file.connector import FileConnector

        reg = ConnectorRegistry()
        connector = reg.get("file")
        assert isinstance(connector, FileConnector)

    def test_registry_get_unknown_raises(self) -> None:
        from sangam_mw.connectors.base.registry import ConnectorRegistry

        reg = ConnectorRegistry()
        with pytest.raises(KeyError, match="not found"):
            reg.get("nonexistent-connector-xyz")
