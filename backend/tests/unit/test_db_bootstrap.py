from sangam_mw.dev.db_bootstrap import _looks_like_compose_postgres, repo_root


def test_repo_root_points_at_monorepo():
    assert (repo_root() / "docker-compose.yml").is_file()


def test_looks_like_compose_postgres_default():
    assert _looks_like_compose_postgres("postgresql+asyncpg://sangam:sangam@localhost:5432/sangam_mw")


def test_looks_like_compose_postgres_rejects_remote():
    assert not _looks_like_compose_postgres(
        "postgresql+asyncpg://sangam:sangam@db.example.com:5432/sangam_mw"
    )


def test_looks_like_compose_postgres_rejects_custom_local_user():
    assert not _looks_like_compose_postgres(
        "postgresql+asyncpg://myuser:secret@localhost:5432/sangam_mw"
    )
