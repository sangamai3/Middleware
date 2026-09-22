"""Unit tests for secrets providers — Fernet round-trip."""

import pytest
from cryptography.fernet import Fernet

from sangam_mw.vault.provider import FernetSecretsProvider


@pytest.fixture
def key():
    return Fernet.generate_key().decode()


@pytest.fixture
def provider(key):
    return FernetSecretsProvider(key=key)


class TestFernetSecretsProvider:
    def test_encrypt_decrypt_roundtrip(self, provider):
        plaintext = "super-secret-value"
        ciphertext = provider.encrypt(plaintext)
        assert ciphertext != plaintext
        assert provider.decrypt(ciphertext) == plaintext

    def test_encrypt_is_nondeterministic(self, provider):
        c1 = provider.encrypt("same")
        c2 = provider.encrypt("same")
        assert c1 != c2

    def test_ciphertext_is_str(self, provider):
        ct = provider.encrypt("hello world")
        assert isinstance(ct, str)

    def test_decrypt_str_ciphertext(self, provider):
        ct = provider.encrypt("hello world")
        assert provider.decrypt(ct) == "hello world"

    def test_write_and_read_secret(self, provider):
        provider.write_secret("db_password", "p@ssw0rd!")
        assert provider.read_secret("db_password") == "p@ssw0rd!"

    def test_read_nonexistent_returns_none(self, provider):
        assert provider.read_secret("no_such_key") is None

    def test_overwrite_secret(self, provider):
        provider.write_secret("key", "v1")
        provider.write_secret("key", "v2")
        assert provider.read_secret("key") == "v2"

    def test_empty_string_roundtrip(self, provider):
        ct = provider.encrypt("")
        assert provider.decrypt(ct) == ""

    def test_unicode_roundtrip(self, provider):
        value = "café ☕ 中文"
        ct = provider.encrypt(value)
        assert provider.decrypt(ct) == value

    def test_two_providers_same_key_share_ciphertext(self, key):
        p1 = FernetSecretsProvider(key=key)
        p2 = FernetSecretsProvider(key=key)
        ct = p1.encrypt("shared")
        assert p2.decrypt(ct) == "shared"

    def test_missing_key_raises(self, monkeypatch):
        monkeypatch.delenv("FERNET_KEY", raising=False)
        with pytest.raises(ValueError, match="FERNET_KEY"):
            FernetSecretsProvider()
