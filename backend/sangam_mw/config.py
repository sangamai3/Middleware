from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
_REPO_ROOT = _BACKEND_ROOT.parent


def _env_file_paths() -> tuple[str, ...]:
    paths: list[Path] = [
        _REPO_ROOT / ".env",
        _BACKEND_ROOT / ".env",
        Path.cwd() / ".env",
    ]
    seen: set[str] = set()
    out: list[str] = []
    for p in paths:
        key = str(p.resolve()) if p.exists() else str(p)
        if p.is_file() and key not in seen:
            seen.add(key)
            out.append(str(p))
    return tuple(out) if out else (".env",)


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://sangam:sangam@localhost:5432/sangam_mw"
    # auto: try DATABASE_URL, then start Docker Postgres for default local URL
    # docker: always start compose postgres
    # local: only DATABASE_URL — never start Docker
    postgres_provider: Literal["auto", "docker", "local"] = Field(
        default="auto",
        validation_alias=AliasChoices("SANGAM_POSTGRES", "POSTGRES_PROVIDER", "postgres_provider"),
    )

    # Fernet key for encrypting connection secrets.
    # Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    # Leave empty in tests — encryption falls back to plaintext passthrough.
    fernet_key: str = ""

    google_client_id: str = ""
    google_client_secret: str = ""

    jwt_secret: str = "dev-secret-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24  # 24 hours

    environment: str = "development"
    debug: bool = False

    model_config = SettingsConfigDict(
        env_file=_env_file_paths(),
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
