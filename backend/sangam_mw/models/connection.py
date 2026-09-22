from datetime import datetime

from pydantic import BaseModel, Field


class ConnectionConfig(BaseModel):
    connection_id: str
    name: str
    connector_id: str
    config: dict = Field(default_factory=dict)
    environment: str = "default"
    created_at: datetime | None = None
    updated_at: datetime | None = None
    created_by: str = ""
    tags: list[str] = Field(default_factory=list)
