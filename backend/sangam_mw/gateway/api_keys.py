"""
API key generation and validation for the Gateway.

Keys are never stored in plaintext — only the SHA-256 hash is persisted.
The key format: smw_<32 random url-safe bytes as base64url>
Example:       smw_Xk9mZ2...
"""
from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


_PREFIX = "smw_"


def generate_api_key() -> str:
    """Generate a new API key. Return the plaintext — only shown once."""
    token = secrets.token_urlsafe(32)
    return f"{_PREFIX}{token}"


def hash_api_key(key: str) -> str:
    """SHA-256 hex digest of the key — stored in DB instead of the plaintext."""
    return hashlib.sha256(key.encode()).hexdigest()


def verify_api_key(key: str, stored_hash: str) -> bool:
    return secrets.compare_digest(hash_api_key(key), stored_hash)


@dataclass
class ApiKeyRecord:
    key_id: str
    key_hash: str
    consumer_name: str
    consumer_email: str
    product_id: str
    plan_name: str
    scopes: list[str]
    created_at: datetime
    expires_at: datetime | None
    is_active: bool

    def is_valid(self) -> bool:
        if not self.is_active:
            return False
        if self.expires_at and datetime.now(UTC) > self.expires_at:
            return False
        return True


class ApiKeyManager:
    """
    In-memory key store for tests; production uses ApiKeyTable in Postgres.

    Inject a real session-backed store by subclassing and overriding _load / _save.
    """

    def __init__(self) -> None:
        self._keys: dict[str, ApiKeyRecord] = {}

    def create(
        self,
        consumer_name: str,
        consumer_email: str,
        product_id: str,
        plan_name: str = "default",
        scopes: list[str] | None = None,
        expires_at: datetime | None = None,
    ) -> tuple[str, ApiKeyRecord]:
        """Returns (plaintext_key, record). Store the hash — not the key."""
        plaintext = generate_api_key()
        key_hash = hash_api_key(plaintext)
        key_id = secrets.token_hex(8)
        record = ApiKeyRecord(
            key_id=key_id,
            key_hash=key_hash,
            consumer_name=consumer_name,
            consumer_email=consumer_email,
            product_id=product_id,
            plan_name=plan_name,
            scopes=scopes or [],
            created_at=datetime.now(UTC),
            expires_at=expires_at,
            is_active=True,
        )
        self._keys[key_hash] = record
        return plaintext, record

    def validate(self, key: str) -> ApiKeyRecord | None:
        key_hash = hash_api_key(key)
        record = self._keys.get(key_hash)
        if record and record.is_valid():
            return record
        return None

    def revoke(self, key_id: str) -> bool:
        for record in self._keys.values():
            if record.key_id == key_id:
                record.is_active = False
                return True
        return False

    def list_by_product(self, product_id: str) -> list[ApiKeyRecord]:
        return [r for r in self._keys.values() if r.product_id == product_id]
