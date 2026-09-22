from datetime import UTC, datetime

import pytest

from sangam_mw.connectors.base.schemas import ConnectionHandle


@pytest.fixture
def make_handle():
    def _make(connector_id: str = "test", config: dict | None = None) -> ConnectionHandle:
        return ConnectionHandle(
            connector_id=connector_id,
            connection_id="test-conn",
            config=config or {},
            created_at=datetime.now(UTC),
        )

    return _make
