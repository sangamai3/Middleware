"""
Ensure Postgres is reachable and migrations are applied before dev startup.

Modes (SANGAM_POSTGRES / settings.postgres_provider):
  auto   — use DATABASE_URL; if unreachable and URL looks like local Docker defaults, start compose postgres
  docker — always `docker compose up -d postgres` then migrate
  local  — only DATABASE_URL (your own Postgres); never start Docker
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from sqlalchemy import text
from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from ..config import get_settings

PostgresProvider = Literal["auto", "docker", "local"]

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_COMPOSE_FILE = _REPO_ROOT / "docker-compose.yml"
_DEFAULT_DOCKER_URL = "postgresql+asyncpg://sangam:sangam@localhost:5432/sangam_mw"


def repo_root() -> Path:
    return _REPO_ROOT


def resolve_provider() -> PostgresProvider:
    raw = (os.environ.get("SANGAM_POSTGRES") or get_settings().postgres_provider or "auto").lower()
    if raw in ("auto", "docker", "local"):
        return raw  # type: ignore[return-value]
    raise SystemExit(f"Invalid SANGAM_POSTGRES={raw!r} (use auto, docker, or local)")


def _normalized_database_url() -> str:
    return get_settings().database_url


def _is_local_host(host: str | None) -> bool:
    if not host:
        return True
    return host in ("localhost", "127.0.0.1", "::1")


def _looks_like_compose_postgres(url: str) -> bool:
    try:
        u = make_url(url)
    except Exception:
        return url.strip() == _DEFAULT_DOCKER_URL
    if not _is_local_host(u.host):
        return False
    port = u.port or 5432
    if port != 5432:
        return False
    db = (u.database or "").lstrip("/")
    user = u.username or ""
    return db == "sangam_mw" and user == "sangam"


async def _ping_database(url: str, timeout: float = 5.0) -> bool:
    engine = create_async_engine(url, pool_pre_ping=True)

    async def _check() -> None:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))

    try:
        await asyncio.wait_for(_check(), timeout=timeout)
        return True
    except Exception:
        return False
    finally:
        await engine.dispose()


def _docker_available() -> bool:
    try:
        subprocess.run(
            ["docker", "compose", "version"],
            cwd=_REPO_ROOT,
            capture_output=True,
            check=True,
            timeout=15,
        )
        return _COMPOSE_FILE.is_file()
    except (subprocess.SubprocessError, OSError, FileNotFoundError):
        return False


def _start_compose_postgres() -> None:
    if not _COMPOSE_FILE.is_file():
        raise SystemExit(f"docker-compose.yml not found at {_COMPOSE_FILE}")
    print("→ Starting Postgres via Docker Compose…", file=sys.stderr)
    subprocess.run(
        ["docker", "compose", "up", "-d", "postgres"],
        cwd=_REPO_ROOT,
        check=True,
    )


def _wait_for_postgres(url: str, attempts: int = 30, delay: float = 1.0) -> bool:
    for i in range(attempts):
        if asyncio.run(_ping_database(url, timeout=3.0)):
            return True
        if i == 0:
            print("→ Waiting for Postgres to accept connections…", file=sys.stderr)
        time.sleep(delay)
    return False


def _run_migrations() -> None:
    backend = _REPO_ROOT / "backend"
    print("→ Running Alembic migrations…", file=sys.stderr)
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=backend,
        check=True,
        env=os.environ.copy(),
    )


def ensure_database(*, migrate: bool = True) -> None:
    """Connect to Postgres (starting Docker when configured) and optionally migrate."""
    provider = resolve_provider()
    url = _normalized_database_url()

    if provider == "local":
        if not asyncio.run(_ping_database(url)):
            host = make_url(url).host or "localhost"
            raise SystemExit(
                "Cannot connect using DATABASE_URL.\n"
                f"  URL host: {host}\n"
                "  SANGAM_POSTGRES=local — Docker will not be started.\n"
                "  Create the database/user or fix DATABASE_URL in .env (see .env.example)."
            )
        if migrate:
            _run_migrations()
        print("→ Postgres ready (local)", file=sys.stderr)
        return

    if provider == "docker":
        if not _docker_available():
            raise SystemExit(
                "SANGAM_POSTGRES=docker but Docker Compose is not available.\n"
                "Install Docker Desktop or set SANGAM_POSTGRES=local with DATABASE_URL."
            )
        _start_compose_postgres()
        if not _wait_for_postgres(url):
            raise SystemExit("Postgres container did not become ready in time.")
        if migrate:
            _run_migrations()
        print("→ Postgres ready (docker)", file=sys.stderr)
        return

    # auto
    if asyncio.run(_ping_database(url)):
        if migrate:
            _run_migrations()
        print("→ Postgres ready", file=sys.stderr)
        return

    if _looks_like_compose_postgres(url) and _docker_available():
        _start_compose_postgres()
        if _wait_for_postgres(url):
            if migrate:
                _run_migrations()
            print("→ Postgres ready (docker, auto-started)", file=sys.stderr)
            return

    parsed = urlparse(url.replace("+asyncpg", ""))
    raise SystemExit(
        "Cannot connect to Postgres.\n"
        f"  DATABASE_URL → {parsed.hostname or '?'}:{parsed.port or 5432}\n"
        "  Options:\n"
        "    • Start your own Postgres and set DATABASE_URL (SANGAM_POSTGRES=local)\n"
        "    • Or use Docker: SANGAM_POSTGRES=docker (default URL in .env.example)\n"
        "    • Or leave SANGAM_POSTGRES=auto with default URL to auto-start compose postgres"
    )


def main() -> None:
    ensure_database(migrate=True)


if __name__ == "__main__":
    main()
