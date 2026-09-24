import asyncio
import hashlib
import json
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from cryptography.fernet import Fernet, InvalidToken

from .auth import OAuth2Handler, parse_token_expiry
from .metadata import AuthType
from .schemas import ConnectionHandle
from .validation import validate_config

if TYPE_CHECKING:
    from .connector import BaseConnector

_DEFAULT_TTL_SECONDS = 180
_OAUTH_REFRESH_BUFFER_SECONDS = 60


@dataclass
class _PoolEntry:
    handle: ConnectionHandle
    created_at: float = field(default_factory=time.monotonic)

    def is_fresh(self, ttl: int) -> bool:
        return (time.monotonic() - self.created_at) < ttl


class ConnectionManager:
    """
    Manages connection lifecycle:
    - Encrypts/decrypts secrets with Fernet
    - Pools open handles by TTL (default 180 s)
    - Detects OAuth2 token expiry 60 s before it happens
    """

    def __init__(
        self,
        fernet_key: bytes | str | None = None,
        ttl_seconds: int = _DEFAULT_TTL_SECONDS,
    ) -> None:
        if fernet_key:
            key = fernet_key if isinstance(fernet_key, bytes) else fernet_key.encode()
            self._fernet: Fernet | None = Fernet(key)
        else:
            self._fernet = None  # test/dev mode — secrets stored plaintext
        self._ttl = ttl_seconds
        self._pool: dict[str, _PoolEntry] = {}
        self._lock = asyncio.Lock()

    def encrypt_secret(self, value: str) -> str:
        if not self._fernet:
            return value
        return self._fernet.encrypt(value.encode()).decode()

    def decrypt_secret(self, value: str) -> str:
        if not self._fernet:
            return value
        try:
            return self._fernet.decrypt(value.encode()).decode()
        except InvalidToken:
            return value  # not encrypted — dev/test plaintext passthrough

    def encrypt_config(self, config: dict, schema: dict | None) -> dict:
        """Encrypt every field marked `"secret": true` in the JSON Schema."""
        if not schema:
            return config
        encrypted = dict(config)
        props = schema.get("properties", {})
        for key, prop_schema in props.items():
            if prop_schema.get("secret") and key in encrypted and encrypted[key]:
                encrypted[key] = self.encrypt_secret(str(encrypted[key]))
        return encrypted

    def decrypt_config(self, config: dict, schema: dict | None) -> dict:
        """Decrypt every field marked `"secret": true` in the JSON Schema."""
        if not schema:
            return config
        decrypted = dict(config)
        props = schema.get("properties", {})
        for key, prop_schema in props.items():
            if prop_schema.get("secret") and key in decrypted and decrypted[key]:
                decrypted[key] = self.decrypt_secret(str(decrypted[key]))
        return decrypted

    async def get_handle(
        self,
        connector: "BaseConnector",
        connection_id: str,
        raw_config: dict,
    ) -> ConnectionHandle:
        cache_key = _cache_key(connector.metadata.connector_id, connection_id, raw_config)
        async with self._lock:
            entry = self._pool.get(cache_key)
            if entry and entry.is_fresh(self._ttl):
                handle = entry.handle
                await self._refresh_oauth_if_needed(connector, handle)
                return handle
            decrypted = self.decrypt_config(raw_config, connector.metadata.connection_schema)
            config = validate_config(
                decrypted, connector.metadata.connection_schema, label="connection config"
            )
            expires_at = parse_token_expiry(config.get("token_expires_at"))
            handle = ConnectionHandle(
                connector_id=connector.metadata.connector_id,
                connection_id=connection_id,
                config=config,
                created_at=datetime.now(UTC),
                token_expires_at=expires_at,
            )
            await self._refresh_oauth_if_needed(connector, handle)
            self._pool[cache_key] = _PoolEntry(handle=handle)
            return handle

    async def _refresh_oauth_if_needed(
        self, connector: "BaseConnector", handle: ConnectionHandle
    ) -> None:
        if connector.metadata.auth_type != AuthType.OAUTH2:
            return
        handler = OAuth2Handler()
        expires_at = handle.token_expires_at or parse_token_expiry(
            handle.config.get("token_expires_at")
        )
        if not handler.needs_refresh(expires_at, buffer_seconds=_OAUTH_REFRESH_BUFFER_SECONDS):
            return
        updated = await handler.refresh(handle.config)
        handle.config.update(updated)
        handle.token_expires_at = parse_token_expiry(updated.get("token_expires_at"))

    async def invalidate(self, connection_id: str) -> None:
        async with self._lock:
            stale = [k for k in self._pool if connection_id in k]
            for k in stale:
                del self._pool[k]


def _cache_key(connector_id: str, connection_id: str, config: dict) -> str:
    config_hash = hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()[:12]
    return f"{connector_id}:{connection_id}:{config_hash}"
