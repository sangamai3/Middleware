from dataclasses import dataclass, field
from enum import StrEnum


class AuthType(StrEnum):
    NONE = "none"
    API_KEY = "api_key"
    BASIC = "basic"
    OAUTH2 = "oauth2"
    SERVICE_ACCOUNT = "service_account"


class OperationType(StrEnum):
    READ = "read"
    WRITE = "write"


@dataclass
class ConnectorMetadata:
    connector_id: str
    label: str
    family: str  # "file" | "saas" | "sql" | "cloud_storage" | "messaging" | "erp" | ...
    version: str
    auth_type: AuthType
    operations: list[OperationType]
    description: str = ""
    icon: str = ""  # base64 SVG or URL
    connection_schema: dict | None = None  # JSON Schema — drives the UI config panel
    read_schema: dict | None = None  # JSON Schema — drives the read config panel
    write_schema: dict | None = None  # JSON Schema — drives the write config panel
    tags: list[str] = field(default_factory=list)
