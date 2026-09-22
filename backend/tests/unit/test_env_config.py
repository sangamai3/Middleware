"""Unit tests for multi-environment configuration."""

import textwrap
from pathlib import Path

import pytest

from sangam_mw.env.config import EnvironmentConfig, MultiEnvConfig


SAMPLE_YAML = textwrap.dedent("""\
    environments:
      dev:
        database_url: "postgresql://localhost/dev_db"
        connections:
          crm: "conn_crm_dev"
          warehouse: "conn_wh_dev"
        features:
          ai_suggestions: true
          dark_mode: false
      staging:
        database_url: "postgresql://staging-host/staging_db"
        connections:
          crm: "conn_crm_stg"
          warehouse: "conn_wh_stg"
        features:
          ai_suggestions: true
          dark_mode: true
      prod:
        database_url: "${PROD_DB_URL}"
        connections:
          crm: "conn_crm_prd"
          warehouse: "conn_wh_prd"
        features:
          ai_suggestions: false
          dark_mode: true
""")


@pytest.fixture
def config_file(tmp_path):
    p = tmp_path / "sangam-envs.yaml"
    p.write_text(SAMPLE_YAML)
    return p


class TestMultiEnvConfig:
    def test_loads_environments(self, config_file):
        cfg = MultiEnvConfig.from_yaml(config_file)
        assert set(cfg.environments.keys()) == {"dev", "staging", "prod"}

    def test_resolve_connection(self, config_file):
        cfg = MultiEnvConfig.from_yaml(config_file)
        dev = cfg.environments["dev"]
        assert dev.resolve_connection("crm") == "conn_crm_dev"

    def test_resolve_nonexistent_connection_returns_none(self, config_file):
        cfg = MultiEnvConfig.from_yaml(config_file)
        dev = cfg.environments["dev"]
        assert dev.resolve_connection("no_such_alias") is None

    def test_feature_enabled(self, config_file):
        cfg = MultiEnvConfig.from_yaml(config_file)
        dev = cfg.environments["dev"]
        assert dev.feature_enabled("ai_suggestions") is True
        assert dev.feature_enabled("dark_mode") is False

    def test_feature_missing_returns_false(self, config_file):
        cfg = MultiEnvConfig.from_yaml(config_file)
        assert cfg.environments["dev"].feature_enabled("nonexistent_flag") is False

    def test_env_var_interpolation(self, config_file, monkeypatch):
        monkeypatch.setenv("PROD_DB_URL", "postgresql://prod-host/prod_db")
        cfg = MultiEnvConfig.from_yaml(config_file)
        prod = cfg.environments["prod"]
        assert prod.database_url == "postgresql://prod-host/prod_db"

    def test_unset_env_var_keeps_placeholder(self, config_file, monkeypatch):
        monkeypatch.delenv("PROD_DB_URL", raising=False)
        cfg = MultiEnvConfig.from_yaml(config_file)
        prod = cfg.environments["prod"]
        assert "${PROD_DB_URL}" in prod.database_url

    def test_active_env_from_envvar(self, config_file, monkeypatch):
        monkeypatch.setenv("SANGAM_ENV", "staging")
        cfg = MultiEnvConfig.from_yaml(config_file)
        # active is a string attribute
        assert cfg.active == "staging"
        env = cfg.get()
        assert env.name == "staging"

    def test_get_returns_named_env(self, config_file):
        cfg = MultiEnvConfig.from_yaml(config_file)
        dev = cfg.get("dev")
        assert dev.name == "dev"

    def test_promote_returns_target_env_connection_id(self, config_file):
        cfg = MultiEnvConfig.from_yaml(config_file)
        # promote returns the connection_id already in the target env for that alias
        result = cfg.promote("crm", from_env="staging", to_env="prod")
        # prod already has crm = conn_crm_prd
        assert result == "conn_crm_prd"

    def test_promote_unknown_alias_raises(self, config_file):
        cfg = MultiEnvConfig.from_yaml(config_file)
        with pytest.raises(KeyError):
            cfg.promote("nonexistent", from_env="dev", to_env="staging")
