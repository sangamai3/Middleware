"""Salesforce URL / API-version hardening — ported from AgentStudio ``salesforce_security.py``."""

from __future__ import annotations

import ipaddress
import os
import re
import socket
from collections.abc import Callable, Iterable
from urllib.parse import urlparse

from ..base.errors import ConnectorValidationError

DEFAULT_ALLOWED_HOST_SUFFIXES = ("salesforce.com", "force.com")
_API_VERSION_RE = re.compile(r"^v(?:[1-9]\d?|100)\.\d{1,2}$")
_SOBJECT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def allowed_salesforce_host_suffixes() -> tuple[str, ...]:
    configured = os.getenv("SALESFORCE_ALLOWED_HOST_SUFFIXES", "")
    values = configured.split(",") if configured.strip() else DEFAULT_ALLOWED_HOST_SUFFIXES
    suffixes = tuple(v.strip().lower().lstrip(".") for v in values if v.strip())
    if not suffixes:
        raise ConnectorValidationError("At least one Salesforce host suffix must be configured")
    return suffixes


def validate_salesforce_url(
    value: str,
    *,
    resolver: Callable[..., Iterable[tuple]] | None = None,
    allowed_suffixes: Iterable[str] | None = None,
    check_dns: bool = True,
) -> str:
    raw = (value or "").strip()
    try:
        parsed = urlparse(raw)
        port = parsed.port
    except ValueError as exc:
        raise ConnectorValidationError("Salesforce URL is malformed") from exc
    if parsed.scheme.lower() != "https":
        raise ConnectorValidationError("Salesforce URL must use HTTPS")
    if not parsed.hostname or parsed.username is not None or parsed.password is not None:
        raise ConnectorValidationError("Salesforce URL must have a host and no user information")
    if parsed.fragment or parsed.query:
        raise ConnectorValidationError("Salesforce URL must not contain a query string or fragment")
    if port not in (None, 443):
        raise ConnectorValidationError("Salesforce URL may only use the HTTPS port")
    host = parsed.hostname.rstrip(".").lower()
    suffixes = tuple(
        s.lower().lstrip(".") for s in (allowed_suffixes or allowed_salesforce_host_suffixes())
    )
    if not any(host == suffix or host.endswith(f".{suffix}") for suffix in suffixes):
        raise ConnectorValidationError("Salesforce URL host is not in an allowed Salesforce domain")
    if check_dns:
        try:
            resolve = resolver or socket.getaddrinfo
            addresses = {entry[4][0] for entry in resolve(host, 443, type=socket.SOCK_STREAM)}
        except OSError as exc:
            raise ConnectorValidationError(
                f"Salesforce host could not be resolved: {host}"
            ) from exc
        if not addresses:
            raise ConnectorValidationError(f"Salesforce host could not be resolved: {host}")
        if any(not ipaddress.ip_address(address).is_global for address in addresses):
            raise ConnectorValidationError("Salesforce host must resolve only to public addresses")
    path = (parsed.path or "").rstrip("/")
    return f"https://{host}{path}"


def is_salesforce_my_domain_url(value: str) -> bool:
    try:
        parsed = urlparse(value or "")
    except ValueError:
        return False
    host = (parsed.hostname or "").rstrip(".").lower()
    return host.endswith(".my.salesforce.com") and host != "my.salesforce.com"


def salesforce_api_version(value: str | None = None) -> str:
    version = str(value or os.getenv("SALESFORCE_API_VERSION") or "v61.0").strip()
    if not version.startswith("v"):
        version = f"v{version}"
    if not _API_VERSION_RE.fullmatch(version):
        raise ConnectorValidationError("Salesforce API version must look like v61.0")
    return version


def validate_sobject_identifier(value: str) -> str:
    cleaned = (value or "").strip()
    if not _SOBJECT_RE.fullmatch(cleaned):
        raise ConnectorValidationError(f"Invalid Salesforce object identifier: {value!r}")
    return cleaned
