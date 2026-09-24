"""
Analyze a flow and generate Docker Compose for a dedicated flow worker.

Connector-specific pip extras align with pyproject [project.optional-dependencies].
"""

from __future__ import annotations

import re
from typing import Any

import yaml

from ..models.flow import FlowDefinition, StepConfig

# Connectors that need extra pip installs beyond the slim worker base.
CONNECTOR_PIP_EXTRAS: dict[str, str | None] = {
    "file": None,
    "postgres": None,
    "salesforce": None,
    "aws-s3": None,
    "rest-api": None,
    "http_sidecar": "http-sidecar",
    "kafka": "kafka",
    "redis": "redis",
    "mongodb": "mongodb",
    "bigquery": "bigquery",
    "snowflake": "snowflake",
    "slack": "slack",
    "openai": "openai",
    "anthropic": "anthropic-connector",
    "ftp": None,  # future: ftp extra when added
}

MEMORY_PROFILES: dict[str, dict[str, str]] = {
    "minimal": {"memory": "192M", "cpus": "0.25"},
    "standard": {"memory": "512M", "cpus": "0.5"},
    "large": {"memory": "1536M", "cpus": "1.0"},
}


def _slug(flow_id: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", flow_id.lower()).strip("-")
    return s[:48] or "flow"


def _connector_ids_from_step(step: StepConfig) -> set[str]:
    out: set[str] = set()
    cfg = step.config or {}
    cid = cfg.get("connector_id")
    if isinstance(cid, str) and cid:
        out.add(cid)
    conn = cfg.get("conn")
    if isinstance(conn, dict):
        inner = conn.get("connector_id")
        if isinstance(inner, str) and inner:
            out.add(inner)
    return out


def _file_paths_from_step(step: StepConfig) -> list[str]:
    cfg = step.config or {}
    cid = cfg.get("connector_id")
    paths: list[str] = []
    conn = cfg.get("conn")
    if not isinstance(conn, dict):
        return paths
    if cid == "file" or conn.get("connector_id") == "file":
        for key in ("base_path", "path", "directory"):
            val = conn.get(key)
            if isinstance(val, str) and val.strip():
                paths.append(val.strip())
        obj = conn.get("object_name") or cfg.get("object_name")
        if isinstance(obj, str) and obj and "/" in obj and "*" not in obj:
            parent = obj.rsplit("/", 1)[0]
            if parent:
                paths.append(parent)
    return paths


def analyze_flow(flow: FlowDefinition) -> dict[str, Any]:
    connector_ids: set[str] = set()
    step_types: set[str] = set()
    file_paths: list[str] = []

    for step in flow.steps:
        step_types.add(step.type)
        connector_ids |= _connector_ids_from_step(step)
        file_paths.extend(_file_paths_from_step(step))

    extras: list[str] = []
    unknown: list[str] = []
    for cid in sorted(connector_ids):
        extra = CONNECTOR_PIP_EXTRAS.get(cid)
        if cid not in CONNECTOR_PIP_EXTRAS:
            unknown.append(cid)
        elif extra:
            extras.append(extra)

    unique_paths = list(dict.fromkeys(file_paths))

    return {
        "flow_id": flow.flow_id,
        "flow_name": flow.name,
        "connector_ids": sorted(connector_ids),
        "step_types": sorted(step_types),
        "pip_extras": sorted(set(extras)),
        "unknown_connectors": unknown,
        "file_paths": unique_paths,
    }


def generate_flow_compose(
    flow: FlowDefinition,
    *,
    memory_profile: str = "minimal",
    image_tag: str = "latest",
    control_plane_url: str = "http://host.docker.internal:8100",
    host_data_root: str | None = None,
    network_name: str = "sangam-internal",
) -> dict[str, Any]:
    """Return compose YAML string plus manifest metadata."""
    analysis = analyze_flow(flow)
    slug = _slug(flow.flow_id)
    service_name = f"flow-{slug}"
    limits = MEMORY_PROFILES.get(memory_profile, MEMORY_PROFILES["standard"])

    pip_extras = analysis["pip_extras"]
    pip_extras_arg = ",".join(pip_extras) if pip_extras else ""

    volumes: list[str] = []
    if host_data_root:
        volumes.append(f"{host_data_root.rstrip('/')}:/data:rw")
    else:
        for i, p in enumerate(analysis["file_paths"][:4]):
            host = f"./data/{slug}/vol{i}"
            volumes.append(f"{host}:{p}:rw")

    compose: dict[str, Any] = {
        "services": {
            service_name: {
                "image": f"sangam-mw-flow-worker:{image_tag}",
                "build": {
                    "context": "./backend",
                    "dockerfile": "Dockerfile.flow-worker",
                    "args": {
                        "PIP_EXTRAS": pip_extras_arg,
                    },
                },
                "container_name": service_name,
                "restart": "unless-stopped",
                "environment": {
                    "FLOW_ID": flow.flow_id,
                    "FLOW_VERSION": str(flow.version),
                    "CONTROL_PLANE_URL": control_plane_url,
                    "DATABASE_URL": "${DATABASE_URL}",
                    "FERNET_KEY": "${FERNET_KEY}",
                    "RUNTIME_TOKEN": "${RUNTIME_TOKEN:-}",
                    "LOG_LEVEL": "info",
                },
                "deploy": {
                    "resources": {
                        "limits": {
                            "memory": limits["memory"],
                            "cpus": limits["cpus"],
                        }
                    }
                },
                "networks": [network_name],
            }
        },
        "networks": {
            network_name: {"external": True},
        },
    }

    if volumes:
        compose["services"][service_name]["volumes"] = volumes

    manifest = {
        **analysis,
        "memory_profile": memory_profile,
        "pip_extras": pip_extras,
        "pip_extras_arg": pip_extras_arg,
        "service_name": service_name,
        "image": f"sangam-mw-flow-worker:{image_tag}",
    }

    compose_yaml = yaml.dump(compose, default_flow_style=False, sort_keys=False)

    return {
        "manifest": manifest,
        "compose_yaml": compose_yaml,
        "env_example": _env_example(flow.flow_id),
    }


def _env_example(flow_id: str) -> str:
    return (
        f"# Environment for flow worker ({flow_id})\n"
        "DATABASE_URL=postgresql+asyncpg://sangam:sangam@postgres:5432/sangam_mw\n"
        "FERNET_KEY=\n"
        "RUNTIME_TOKEN=\n"
    )
