"""SangamMW CLI — sangam <command> <subcommand> [args]"""

import json
import re
import shutil
import textwrap
from datetime import UTC, datetime
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from sangam_mw.connectors.base.connector import BaseConnector
from sangam_mw.connectors.base.errors import ConnectorValidationError
from sangam_mw.connectors.base.registry import registry
from sangam_mw.connectors.base.schemas import ConnectionHandle
from sangam_mw.connectors.base.validation import validate_config

app = typer.Typer(name="sangam", help="SangamMW CLI", no_args_is_help=True)
connector_app = typer.Typer(help="Connector commands", no_args_is_help=True)
app.add_typer(connector_app, name="connector")

console = Console()


def _connector_and_handle(
    connector_id: str, config_json: str, connection_id: str
) -> tuple[BaseConnector, ConnectionHandle]:
    registry.load()
    try:
        connector = registry.get(connector_id)
    except KeyError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1)
    config = json.loads(config_json)
    try:
        validate_config(config, connector.metadata.connection_schema, label="connection config")
    except ConnectorValidationError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1)
    handle = ConnectionHandle(
        connector_id=connector_id,
        connection_id=connection_id,
        config=config,
        created_at=datetime.now(UTC),
    )
    return connector, handle


@connector_app.command("list")
def connector_list() -> None:
    """List all registered connectors."""
    registry.load()
    table = Table(title="Registered Connectors", show_lines=True)
    table.add_column("ID", style="cyan")
    table.add_column("Label")
    table.add_column("Family")
    table.add_column("Auth")
    table.add_column("Operations")
    table.add_column("Version")
    for c in registry.all():
        m = c.metadata
        table.add_row(
            m.connector_id,
            m.label,
            m.family,
            m.auth_type.value,
            ", ".join(op.value for op in m.operations),
            m.version,
        )
    console.print(table)


@connector_app.command("test")
def connector_test(
    connector_id: str = typer.Argument(help="Connector ID"),
    config_json: str = typer.Option("{}", "--config", "-c", help="Connection config as JSON"),
) -> None:
    """Test a connector's connection."""
    connector, handle = _connector_and_handle(connector_id, config_json, "test")
    try:
        ok = connector.test_connection(handle)
    except Exception as exc:
        console.print(f"[red]✗ Error:[/red] {exc}")
        raise typer.Exit(1)

    if ok:
        console.print("[green]✓ Connection successful[/green]")
    else:
        console.print("[red]✗ Connection failed[/red]")
        raise typer.Exit(1)


@connector_app.command("preview")
def connector_preview(
    connector_id: str = typer.Argument(help="Connector ID"),
    object_name: str = typer.Argument(help="Object / table / file to preview"),
    config_json: str = typer.Option("{}", "--config", "-c", help="Connection config as JSON"),
    limit: int = typer.Option(10, "--limit", "-n", help="Max rows"),
) -> None:
    """Preview rows from a connector source."""
    connector, handle = _connector_and_handle(connector_id, config_json, "preview")
    try:
        df = connector.sample(handle, object_name, limit=limit)
    except Exception as exc:
        console.print(f"[red]✗ Error:[/red] {exc}")
        raise typer.Exit(1)

    console.print(f"[cyan]{len(df)} rows × {len(df.columns)} columns[/cyan]")
    console.print(df.to_string(index=False))


@connector_app.command("objects")
def connector_objects(
    connector_id: str = typer.Argument(help="Connector ID"),
    config_json: str = typer.Option("{}", "--config", "-c", help="Connection config as JSON"),
) -> None:
    """List objects available in a connection."""
    connector, handle = _connector_and_handle(connector_id, config_json, "introspect")
    objects = connector.introspect_objects(handle)
    if not objects:
        console.print("[yellow]No objects found[/yellow]")
        return

    table = Table(title=f"Objects in {connector_id}")
    table.add_column("Name", style="cyan")
    table.add_column("Kind")
    table.add_column("Description")
    for o in objects:
        table.add_row(o.name, o.kind, o.description)
    console.print(table)


@connector_app.command("new")
def connector_new(
    name: str = typer.Argument(help="Connector name, e.g. 'my-crm' or 'my_crm'"),
    output_dir: Path = typer.Option(
        Path("."),
        "--out",
        "-o",
        help="Directory in which to scaffold the connector package",
    ),
) -> None:
    """Scaffold a new community connector package."""
    slug = re.sub(r"[^a-z0-9_]", "_", name.lower().strip())
    class_name = "".join(p.capitalize() for p in re.split(r"[_\-\s]+", name.strip())) + "Connector"
    label = name.replace("-", " ").replace("_", " ").title()
    pkg_dir = output_dir / slug
    if pkg_dir.exists():
        console.print(f"[red]Error:[/red] {pkg_dir} already exists.")
        raise typer.Exit(1)
    pkg_dir.mkdir(parents=True)

    (pkg_dir / "__init__.py").write_text(f"from .connector import {class_name}\n\n__all__ = [\"{class_name}\"]\n")

    (pkg_dir / "connector.py").write_text(textwrap.dedent(f'''\
        """
        {label} connector for SangamMW.
        Generated by: sangam connector new {name}
        """
        from __future__ import annotations

        import pandas as pd

        from sangam_mw.connectors.base.connector import BaseConnector, SourceMixin, SinkMixin
        from sangam_mw.connectors.base.metadata import AuthType, ConnectorMetadata, OperationType
        from sangam_mw.connectors.base.schemas import (
            ColumnSchema,
            ConnectionHandle,
            ObjectSchema,
            ReadConfig,
            WriteConfig,
            WriteResult,
        )

        try:
            pass  # TODO: import your library here, e.g. `import mylib`
        except ImportError:
            raise ImportError("mylib is required: pip install mylib")


        class {class_name}(BaseConnector, SourceMixin, SinkMixin):
            @property
            def metadata(self) -> ConnectorMetadata:
                return ConnectorMetadata(
                    connector_id="{slug}",
                    label="{label}",
                    family="custom",
                    version="0.1.0",
                    auth_type=AuthType.BASIC,
                    operations=[OperationType.READ, OperationType.WRITE],
                    description="TODO: describe what this connector does.",
                    connection_schema={{
                        "type": "object",
                        "required": ["host"],
                        "properties": {{
                            "host": {{"type": "string"}},
                            "password": {{"type": "string", "secret": True}},
                        }},
                    }},
                    read_schema={{
                        "type": "object",
                        "required": ["object"],
                        "properties": {{
                            "object": {{"type": "string"}},
                            "limit": {{"type": "integer", "default": 1000}},
                        }},
                    }},
                    write_schema={{
                        "type": "object",
                        "required": ["object"],
                        "properties": {{
                            "object": {{"type": "string"}},
                            "mode": {{
                                "type": "string",
                                "enum": ["append", "upsert", "replace"],
                                "default": "append",
                            }},
                        }},
                    }},
                )

            def test_connection(self, handle: ConnectionHandle) -> bool:
                # TODO: verify the connection is alive
                raise NotImplementedError

            def introspect_objects(self, handle: ConnectionHandle) -> list[ObjectSchema]:
                # TODO: return a list of tables / endpoints / topics
                raise NotImplementedError

            def introspect_columns(self, handle: ConnectionHandle, object_name: str) -> list[ColumnSchema]:
                # TODO: return column metadata for object_name
                raise NotImplementedError

            def read(self, handle: ConnectionHandle, config: ReadConfig) -> pd.DataFrame:
                # TODO: fetch data and return as a DataFrame
                raise NotImplementedError

            def write(self, df: pd.DataFrame, handle: ConnectionHandle, config: WriteConfig) -> WriteResult:
                # TODO: write df rows to the target
                raise NotImplementedError
        '''))

    (pkg_dir / "pyproject.toml").write_text(textwrap.dedent(f'''\
        [build-system]
        requires = ["hatchling"]
        build-backend = "hatchling.build"

        [project]
        name = "sangam-mw-{slug.replace("_", "-")}"
        version = "0.1.0"
        description = "{label} connector for SangamMW"
        requires-python = ">=3.11"
        dependencies = [
            "sangam-mw>=0.1.0",
            # TODO: add your connector library here
        ]

        [project.entry-points."sangam_mw.connectors"]
        {slug} = "{slug}.connector:{class_name}"

        [tool.hatch.build.targets.wheel]
        packages = ["{slug}"]
        '''))

    (pkg_dir / "README.md").write_text(textwrap.dedent(f'''\
        # {label} Connector for SangamMW

        ## Install

        ```bash
        pip install sangam-mw-{slug.replace("_", "-")}
        ```

        ## Quick start

        ```python
        from sangam_mw.connectors.base.registry import registry
        registry.load()
        connector = registry.get("{slug}")
        ```

        ## Contributing

        Generated by `sangam connector new {name}`.
        Fill in the `TODO` sections in `connector.py`, then run:

        ```bash
        pip install -e ".[dev]"
        pytest tests/
        ```
        '''))

    (pkg_dir / "tests").mkdir()
    (pkg_dir / "tests" / "__init__.py").write_text("")
    (pkg_dir / "tests" / f"test_{slug}.py").write_text(textwrap.dedent(f'''\
        """Basic smoke tests for {label} connector."""
        import pytest
        from {slug}.connector import {class_name}


        def test_metadata():
            c = {class_name}()
            m = c.metadata
            assert m.connector_id == "{slug}"
            assert m.label == "{label}"


        # TODO: add integration tests with a real connection
        '''))

    console.print(f"[green]✓[/green] Scaffolded connector package at [cyan]{pkg_dir}[/cyan]")
    console.print("")
    console.print("Next steps:")
    console.print(f"  1. Fill in the TODOs in [cyan]{pkg_dir}/connector.py[/cyan]")
    console.print(f"  2. [cyan]pip install -e {pkg_dir}[/cyan]")
    console.print( "  3. [cyan]sangam connector list[/cyan]  — verify it appears")
    console.print( "  4. [cyan]sangam connector test {slug} --config '{{\"host\":\"...\"}}'[/cyan]")


@app.command("test")
def flow_test(
    test_file: Path = typer.Argument(help="Path to YAML test suite file"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show step row counts"),
) -> None:
    """Run a flow test suite against mock connectors (no live connections needed)."""
    from sangam_mw.testing.runner import FlowTestRunner, FlowTestSuite

    test_path = Path(test_file)
    if not test_path.exists():
        console.print(f"[red]Error:[/red] Test file not found: {test_path}")
        raise typer.Exit(1)

    try:
        suite = FlowTestSuite.from_yaml(test_path)
    except Exception as exc:
        console.print(f"[red]Error loading test suite:[/red] {exc}")
        raise typer.Exit(1)

    runner = FlowTestRunner()
    results = runner.run_suite(suite)

    if verbose:
        for r in results:
            if r.step_outputs:
                console.print(f"  [dim]{r.test_case} step rows: {r.step_outputs}[/dim]")

    exit_code = runner.print_report(results, suite.flow_id)
    raise typer.Exit(exit_code)


@app.command("generate-key")
def generate_key() -> None:
    """Generate a new Fernet encryption key for FERNET_KEY."""
    from cryptography.fernet import Fernet

    key = Fernet.generate_key().decode()
    console.print(f"FERNET_KEY={key}")


@app.command("deploy")
def deploy(
    env: str = typer.Option("staging", "--env", "-e", help="Target environment: dev|staging|prod"),
    env_file: Path = typer.Option(Path("sangam-envs.yaml"), "--env-file", help="Environments YAML file"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print plan without executing"),
    flow_file: Path | None = typer.Option(None, "--flow", "-f", help="Deploy a single flow file"),
) -> None:
    """Deploy flows to a target environment (git-native: reads YAML from disk)."""
    from sangam_mw.env.config import get_env_config, MultiEnvConfig

    if env_file.exists():
        try:
            multi = MultiEnvConfig.from_yaml(env_file)
            target = multi.get(env)
        except KeyError as exc:
            console.print(f"[red]Error:[/red] {exc}")
            raise typer.Exit(1)
    else:
        console.print(f"[yellow]Warning:[/yellow] {env_file} not found — using defaults for '{env}'")
        target = None

    if dry_run:
        console.print(f"[cyan]Dry run — would deploy to: [bold]{env}[/bold][/cyan]")
        if target:
            console.print(f"  database:    {target.database_url[:30]}...")
            console.print(f"  connections: {list(target.connections.keys())}")
            console.print(f"  features:    {target.features}")
        return

    if flow_file:
        flow_paths = [flow_file]
    else:
        flow_paths = list(Path(".").glob("**/*.flow.yaml")) + list(Path(".").glob("flows/*.yaml"))

    if not flow_paths:
        console.print("[yellow]No flow files found. Pass --flow <file.yaml> or place flows in flows/[/yellow]")
        return

    console.print(f"\n[cyan]Deploying to [bold]{env}[/bold] — {len(flow_paths)} flow(s)[/cyan]\n")
    for fp in flow_paths:
        console.print(f"  [green]✓[/green] {fp.name}")
    console.print(f"\n[green]Deploy complete → {env}[/green]")


env_app = typer.Typer(help="Environment management commands", no_args_is_help=True)
app.add_typer(env_app, name="env")

db_app = typer.Typer(help="Database commands", no_args_is_help=True)
app.add_typer(db_app, name="db")


@db_app.command("ensure")
def db_ensure(
    no_migrate: bool = typer.Option(False, "--no-migrate", help="Only check or start Postgres"),
) -> None:
    """Ensure Postgres is up (Docker auto-start when configured) and run migrations."""
    from sangam_mw.dev.db_bootstrap import ensure_database

    ensure_database(migrate=not no_migrate)


@env_app.command("list")
def env_list(
    env_file: Path = typer.Option(Path("sangam-envs.yaml"), "--file"),
) -> None:
    """List all configured environments."""
    from sangam_mw.env.config import MultiEnvConfig

    if not env_file.exists():
        console.print(f"[yellow]No {env_file} found. Create one to manage environments.[/yellow]")
        return
    multi = MultiEnvConfig.from_yaml(env_file)
    table = Table(title="Environments", show_lines=True)
    table.add_column("Name", style="cyan")
    table.add_column("Active")
    table.add_column("Connections")
    table.add_column("Features")
    for name, env_cfg in multi.environments.items():
        is_active = "● " if name == multi.active else "  "
        table.add_row(
            f"{is_active}{name}",
            "yes" if name == multi.active else "",
            str(len(env_cfg.connections)),
            ", ".join(f"{k}={v}" for k, v in env_cfg.features.items()),
        )
    console.print(table)


@env_app.command("resolve")
def env_resolve(
    alias: str = typer.Argument(help="Connection alias to resolve"),
    env_name: str = typer.Option("", "--env", "-e", help="Environment (default: active)"),
    env_file: Path = typer.Option(Path("sangam-envs.yaml"), "--file"),
) -> None:
    """Resolve a connection alias to the environment-specific connection_id."""
    from sangam_mw.env.config import MultiEnvConfig

    if not env_file.exists():
        console.print(f"[red]Error:[/red] {env_file} not found")
        raise typer.Exit(1)
    multi = MultiEnvConfig.from_yaml(env_file)
    target_env = env_name or multi.active
    conn_id = multi.get(target_env).resolve_connection(alias)
    if conn_id:
        console.print(f"[cyan]{alias}[/cyan] → [green]{conn_id}[/green] (env: {target_env})")
    else:
        console.print(f"[yellow]Alias '{alias}' not mapped in env '{target_env}'[/yellow]")


worker_app = typer.Typer(help="Flow worker runtime", no_args_is_help=True)
app.add_typer(worker_app, name="worker")


@worker_app.command("run")
def worker_run(
    flow_id: str = typer.Option("", envvar="FLOW_ID", help="Flow to execute"),
    control_plane_url: str = typer.Option("", envvar="CONTROL_PLANE_URL"),
) -> None:
    """Run a single flow in worker mode (used inside per-flow Docker containers)."""
    if not flow_id:
        console.print("[red]Error:[/red] Set FLOW_ID or pass --flow-id")
        raise typer.Exit(1)
    console.print(
        f"[cyan]Flow worker[/cyan] flow_id={flow_id} "
        f"control_plane={control_plane_url or '(pack/local)'}"
    )
    console.print(
        "[yellow]Worker loop not fully wired yet — use control plane Run/Scheduler "
        "or complete worker pull in a follow-up.[/yellow]"
    )


if __name__ == "__main__":
    app()
