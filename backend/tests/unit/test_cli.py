"""CLI smoke tests for `sangam connector` commands."""

import json
from pathlib import Path

from typer.testing import CliRunner

from sangam_mw.cli import app

runner = CliRunner()


def test_connector_list_includes_file() -> None:
    result = runner.invoke(app, ["connector", "list"])
    assert result.exit_code == 0
    assert "file" in result.stdout


def test_connector_test_file(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["connector", "test", "file", "-c", json.dumps({"base_path": str(tmp_path)})],
    )
    assert result.exit_code == 0
    assert "successful" in result.stdout.lower()


def test_connector_test_rejects_invalid_config() -> None:
    result = runner.invoke(app, ["connector", "test", "file", "-c", "{}"])
    assert result.exit_code == 1
    assert "base_path" in result.stdout


def test_connector_preview(tmp_path: Path) -> None:
    csv_path = tmp_path / "rows.csv"
    csv_path.write_text("id,name\n1,a\n2,b\n", encoding="utf-8")
    result = runner.invoke(
        app,
        [
            "connector",
            "preview",
            "file",
            "rows.csv",
            "-c",
            json.dumps({"base_path": str(tmp_path)}),
            "-n",
            "1",
        ],
    )
    assert result.exit_code == 0
    assert "1 rows" in result.stdout


def test_connector_unknown_id() -> None:
    result = runner.invoke(app, ["connector", "test", "nope"])
    assert result.exit_code == 1
    assert "not found" in result.stdout.lower()


def test_generate_key() -> None:
    result = runner.invoke(app, ["generate-key"])
    assert result.exit_code == 0
    assert result.stdout.startswith("FERNET_KEY=")
