"""Unit tests for API key generation, hashing, and lifecycle."""

import pytest

from sangam_mw.gateway.api_keys import (
    ApiKeyManager,
    generate_api_key,
    hash_api_key,
)


class TestGenerateApiKey:
    def test_prefix(self):
        key = generate_api_key()
        assert key.startswith("smw_")

    def test_length_sufficient(self):
        key = generate_api_key()
        assert len(key) > 20

    def test_unique(self):
        keys = {generate_api_key() for _ in range(100)}
        assert len(keys) == 100


class TestHashApiKey:
    def test_deterministic(self):
        key = "smw_test_key_abc123"
        assert hash_api_key(key) == hash_api_key(key)

    def test_sha256_length(self):
        h = hash_api_key("smw_anything")
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_different_keys_different_hashes(self):
        h1 = hash_api_key("smw_aaa")
        h2 = hash_api_key("smw_bbb")
        assert h1 != h2

    def test_plaintext_not_stored(self):
        key = generate_api_key()
        h = hash_api_key(key)
        assert key not in h


class TestApiKeyManager:
    def _manager(self):
        return ApiKeyManager()

    def test_create_returns_plaintext_and_record(self):
        mgr = self._manager()
        plaintext, record = mgr.create(
            consumer_name="acme",
            consumer_email="dev@acme.com",
            product_id="prod-1",
            plan_name="free",
        )
        assert plaintext.startswith("smw_")
        assert record.consumer_name == "acme"
        assert record.product_id == "prod-1"
        assert record.is_active

    def test_validate_returns_record(self):
        mgr = self._manager()
        plaintext, _ = mgr.create("corp", "x@corp.com", "p1", "basic")
        result = mgr.validate(plaintext)
        assert result is not None
        assert result.consumer_name == "corp"

    def test_validate_wrong_key_returns_none(self):
        mgr = self._manager()
        assert mgr.validate("smw_does_not_exist_xyz") is None

    def test_validate_twice_returns_same_record(self):
        mgr = self._manager()
        plaintext, record_create = mgr.create("u", "u@u.com", "p", "free")
        r1 = mgr.validate(plaintext)
        r2 = mgr.validate(plaintext)
        assert r1 is not None and r2 is not None
        assert r1.key_id == record_create.key_id

    def test_revoke_invalidates_key(self):
        mgr = self._manager()
        plaintext, record = mgr.create("rev", "r@r.com", "p", "free")
        mgr.revoke(record.key_id)
        assert mgr.validate(plaintext) is None

    def test_list_by_product(self):
        mgr = self._manager()
        mgr.create("a", "a@a.com", "prod-X", "free")
        mgr.create("b", "b@b.com", "prod-X", "pro")
        mgr.create("c", "c@c.com", "prod-Y", "free")
        keys = mgr.list_by_product("prod-X")
        assert len(keys) == 2
        assert all(k.product_id == "prod-X" for k in keys)

    def test_revoke_nonexistent_is_noop(self):
        mgr = self._manager()
        mgr.revoke("key-id-does-not-exist")  # should not raise
