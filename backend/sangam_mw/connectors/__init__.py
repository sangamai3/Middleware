from .base import registry

__all__ = ["registry"]

# Phase 6 connectors — imported here so the registry picks them up at startup
from . import kafka, redis, mongodb, bigquery, snowflake, slack, openai, anthropic, http_sidecar  # noqa: F401, E402
