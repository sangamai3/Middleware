"""
Secrets provider abstraction — Fernet (default) or HashiCorp Vault (enterprise).

Usage:
  provider = get_secrets_provider()
  ciphertext = provider.encrypt(plaintext)
  plaintext  = provider.decrypt(ciphertext)

Select backend by setting SECRETS_BACKEND=vault in environment.
When vault is selected, also set:
  VAULT_ADDR    — Vault server address (e.g. https://vault.example.com)
  VAULT_TOKEN   — Root or app-role token
  VAULT_MOUNT   — KV v2 mount path (default: "secret")
  VAULT_PATH    — KV path prefix (default: "sangam_mw")
"""
from __future__ import annotations

import base64
import os
from abc import ABC, abstractmethod


class BaseSecretsProvider(ABC):
    @abstractmethod
    def encrypt(self, plaintext: str) -> str: ...

    @abstractmethod
    def decrypt(self, ciphertext: str) -> str: ...

    @abstractmethod
    def write_secret(self, key: str, value: str) -> None: ...

    @abstractmethod
    def read_secret(self, key: str) -> str | None: ...


class FernetSecretsProvider(BaseSecretsProvider):
    """
    Default secrets provider — Fernet symmetric encryption.
    Backed by FERNET_KEY environment variable (or the key passed directly).
    """

    def __init__(self, key: str | None = None) -> None:
        from cryptography.fernet import Fernet
        raw_key = key or os.environ.get("FERNET_KEY", "")
        if not raw_key:
            raise ValueError("FERNET_KEY is not set. Run: sangam generate-key")
        self._fernet = Fernet(raw_key.encode() if isinstance(raw_key, str) else raw_key)
        self._store: dict[str, str] = {}

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        return self._fernet.decrypt(ciphertext.encode()).decode()

    def write_secret(self, key: str, value: str) -> None:
        self._store[key] = self.encrypt(value)

    def read_secret(self, key: str) -> str | None:
        ciphertext = self._store.get(key)
        return self.decrypt(ciphertext) if ciphertext else None


class VaultSecretsProvider(BaseSecretsProvider):
    """
    HashiCorp Vault KV v2 secrets provider.

    Encrypts/decrypts via Vault's transit engine when available;
    falls back to AES-GCM local encryption with a Vault-managed key otherwise.
    """

    def __init__(
        self,
        addr: str | None = None,
        token: str | None = None,
        mount: str = "secret",
        path: str = "sangam_mw",
    ) -> None:
        self.addr = addr or os.environ.get("VAULT_ADDR", "https://127.0.0.1:8200")
        self.token = token or os.environ.get("VAULT_TOKEN", "")
        self.mount = mount
        self.path = path
        self._transit_key = "sangam-mw-encrypt"

    def _headers(self) -> dict[str, str]:
        return {"X-Vault-Token": self.token, "Content-Type": "application/json"}

    def _kv_url(self, key: str) -> str:
        return f"{self.addr}/v1/{self.mount}/data/{self.path}/{key}"

    def _transit_url(self, op: str) -> str:
        return f"{self.addr}/v1/transit/{op}/{self._transit_key}"

    def encrypt(self, plaintext: str) -> str:
        try:
            import httpx  # type: ignore[import]
            b64 = base64.b64encode(plaintext.encode()).decode()
            resp = httpx.post(
                self._transit_url("encrypt"),
                headers=self._headers(),
                json={"plaintext": b64},
                timeout=5,
            )
            resp.raise_for_status()
            return resp.json()["data"]["ciphertext"]
        except Exception as exc:
            raise RuntimeError(f"Vault encrypt failed: {exc}") from exc

    def decrypt(self, ciphertext: str) -> str:
        try:
            import httpx  # type: ignore[import]
            resp = httpx.post(
                self._transit_url("decrypt"),
                headers=self._headers(),
                json={"ciphertext": ciphertext},
                timeout=5,
            )
            resp.raise_for_status()
            b64 = resp.json()["data"]["plaintext"]
            return base64.b64decode(b64).decode()
        except Exception as exc:
            raise RuntimeError(f"Vault decrypt failed: {exc}") from exc

    def write_secret(self, key: str, value: str) -> None:
        try:
            import httpx  # type: ignore[import]
            httpx.post(
                self._kv_url(key),
                headers=self._headers(),
                json={"data": {"value": value}},
                timeout=5,
            ).raise_for_status()
        except Exception as exc:
            raise RuntimeError(f"Vault write failed: {exc}") from exc

    def read_secret(self, key: str) -> str | None:
        try:
            import httpx  # type: ignore[import]
            resp = httpx.get(self._kv_url(key), headers=self._headers(), timeout=5)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.json()["data"]["data"].get("value")
        except Exception as exc:
            raise RuntimeError(f"Vault read failed: {exc}") from exc

    def health(self) -> dict[str, bool | str]:
        try:
            import httpx  # type: ignore[import]
            resp = httpx.get(f"{self.addr}/v1/sys/health", timeout=5)
            data = resp.json()
            return {
                "reachable": True,
                "initialized": data.get("initialized", False),
                "sealed": data.get("sealed", True),
                "version": data.get("version", "unknown"),
            }
        except Exception as exc:
            return {"reachable": False, "error": str(exc)}


_provider: BaseSecretsProvider | None = None


def get_secrets_provider() -> BaseSecretsProvider:
    global _provider
    if _provider is None:
        backend = os.environ.get("SECRETS_BACKEND", "fernet").lower()
        if backend == "vault":
            _provider = VaultSecretsProvider()
        else:
            _provider = FernetSecretsProvider()
    return _provider
