# Contributing to SangamMW

## Writing a connector

A connector is a Python class that implements `BaseConnector` plus `SourceMixin`, `SinkMixin`, or both.

### Minimal example

```python
# my_connector/connector.py
from sangam_mw.connectors.base import (
    BaseConnector, SourceMixin, SinkMixin,
    ConnectorMetadata, AuthType, OperationType,
    ConnectionHandle, ReadConfig, WriteConfig, WriteResult,
    ObjectSchema, ColumnSchema,
)
import pandas as pd


class MyConnector(BaseConnector, SourceMixin):
    @property
    def metadata(self) -> ConnectorMetadata:
        return ConnectorMetadata(
            connector_id="my_connector",
            label="My Service",
            family="saas",
            version="1.0.0",
            auth_type=AuthType.API_KEY,
            operations=[OperationType.READ],
            description="Read records from My Service",
            connection_schema={
                "type": "object",
                "required": ["api_key"],
                "properties": {
                    "api_key": {"type": "string", "secret": True},
                    "base_url": {"type": "string"},
                },
            },
        )

    def test_connection(self, handle: ConnectionHandle) -> bool:
        # Call a cheap endpoint (e.g. /me or /ping)
        ...

    def introspect_objects(self, handle: ConnectionHandle) -> list[ObjectSchema]:
        # Return list of available objects (tables, endpoints, files)
        ...

    def introspect_columns(self, handle: ConnectionHandle, object_name: str) -> list[ColumnSchema]:
        # Return schema for the given object
        ...

    def read(self, handle: ConnectionHandle, config: ReadConfig) -> pd.DataFrame:
        # Fetch data and return a DataFrame
        ...
```

### Register it as an entry-point

In your `pyproject.toml`:

```toml
[project.entry-points."sangam_mw.connectors"]
my_connector = "my_connector.connector:MyConnector"
```

Then `pip install .` makes it auto-discoverable. No changes to SangamMW core needed.

### Secrets in connection_schema

Mark any field that holds credentials as `"secret": true` in the JSON Schema:

```json
"api_key": {"type": "string", "secret": true}
```

`ConnectionManager` will encrypt this field at rest with Fernet and decrypt it before passing the handle to your connector. You will always receive the plaintext value inside `handle.config`.

### Auth types

Use `get_auth_handler(self.metadata.auth_type).apply(handle.config)` instead of parsing credentials yourself:

| `auth_type` | Handler | Config keys |
|---|---|---|
| `api_key` | `APIKeyHandler` | `api_key`, optional `api_key_header` / `api_key_prefix` / `api_key_in=query` |
| `basic` | `BasicAuthHandler` | `username`, `password` |
| `oauth2` | `OAuth2Handler` | `access_token`, `refresh_token`, `token_url`, `client_id`; PKCE via `generate_pkce()` |
| `service_account` | `ServiceAccountHandler` | `json_key` object or `json_key_path` |
| `none` | `NoAuthHandler` | — |

`ConnectionManager` encrypts `"secret": true` fields, validates JSON Schema, pools handles for 180s, and refreshes OAuth2 tokens 60s before expiry.

### Error types

Raise the right exception so retry logic works automatically:

| Situation | Exception |
|---|---|
| API returned 429 | `RateLimitError(msg, retry_after=30)` |
| Network timeout / reset | `NetworkError(msg)` |
| Invalid credentials | `AuthenticationError(msg)` |
| Bad SOQL/invalid object at deploy | `ConnectorValidationError(msg)` |

### Testing your connector

1. Add a test fixture in `tests/unit/test_your_connector.py`
2. Test `test_connection`, `introspect_objects`, `introspect_columns`, `read`, and `write`
3. Use `pytest.fixture` with a real or mocked endpoint
4. Run `make test` before submitting a PR

### Large-scale reads

Override `read_batch` to yield pages rather than loading everything at once:

```python
def read_batch(self, handle, config) -> Iterator[pd.DataFrame]:
    page = 0
    while True:
        df = self._fetch_page(handle, config, page)
        if df.empty:
            break
        yield df
        page += 1
```

The engine calls `read_batch` for all flows; if you don't override it the default calls `read` once.

## Development setup

```bash
cd backend
pip install -e ".[dev]"
make dev          # starts FastAPI on :8000
make test         # runs all tests
make lint         # ruff check
make typecheck    # mypy
make fmt          # auto-format
```

Start Postgres + LocalStack:
```bash
make up
make migrate
```

Generate a Fernet key:
```bash
make generate-key  # prints FERNET_KEY=...
```
Copy the output to your `.env` file.

## Architecture overview

```
sangam_mw/
├── connectors/
│   ├── base/           # Framework: BaseConnector, SourceMixin, SinkMixin
│   │   ├── connector.py
│   │   ├── metadata.py
│   │   ├── schemas.py
│   │   ├── errors.py
│   │   ├── connection.py   # ConnectionManager — Fernet + TTL pool
│   │   └── registry.py     # Entry-point discovery
│   └── file/           # Reference implementation (CSV/JSON/Parquet/Excel)
│   └── salesforce/     # Phase 2 — AgentStudio OAuth (CC/JWT), SOQL, nextRecordsUrl
│   └── aws_s3/         # Phase 2 — AgentStudio boto3 (IAM / access key / session token)
│   └── postgres/       # Phase 2 — AgentStudio postgresql+psycopg2 + pool settings
│   └── rest_api/       # Phase 2 — AgentStudio REST auth types + unwrap list
├── transforms/         # Phase 3: YAML → DuckDB SQL → pandas → PySpark
├── engine/             # Phase 2: FlowRunner, StepExecutor, EngineRouter
├── api/                # FastAPI app
│   ├── main.py
│   ├── auth.py         # JWT + Google OAuth2
│   └── routes/
├── models/             # Pydantic models (FlowDefinition, ExecutionRun, ...)
├── db/                 # SQLAlchemy async engine + tables
├── cli.py              # sangam CLI (typer)
└── config.py           # Settings (pydantic-settings)
```

See `mw-plan.md` in the repo root for the full 9-phase implementation plan.
