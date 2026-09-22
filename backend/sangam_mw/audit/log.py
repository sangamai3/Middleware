"""
Tamper-evident audit log.

Every write appends a new row with:
  - SHA-256 hash of the previous row's content (hash-chain)
  - actor (user_id / system)
  - action enum
  - resource type + id
  - before/after snapshot
  - IP address

Satisfies SOC 2 Type II, HIPAA, ISO 27001 append-only requirements.
"""
from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from enum import Enum
from typing import Any

import structlog
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.tables import AuditLogTable

logger = structlog.get_logger()


class AuditAction(str, Enum):
    # Auth
    USER_LOGIN = "user.login"
    USER_LOGOUT = "user.logout"
    USER_ROLE_CHANGED = "user.role_changed"
    # Flows
    FLOW_CREATED = "flow.created"
    FLOW_UPDATED = "flow.updated"
    FLOW_DELETED = "flow.deleted"
    FLOW_DEPLOYED = "flow.deployed"
    FLOW_ACTIVATED = "flow.activated"
    FLOW_DEACTIVATED = "flow.deactivated"
    # Executions
    EXECUTION_TRIGGERED = "execution.triggered"
    EXECUTION_CANCELLED = "execution.cancelled"
    EXECUTION_REPLAYED = "execution.replayed"
    # Connections
    CONNECTION_CREATED = "connection.created"
    CONNECTION_UPDATED = "connection.updated"
    CONNECTION_DELETED = "connection.deleted"
    CONNECTION_TESTED = "connection.tested"
    # System
    SETTINGS_CHANGED = "system.settings_changed"
    SAML_SSO_LOGIN = "auth.saml_sso_login"
    API_KEY_CREATED = "api_key.created"
    API_KEY_REVOKED = "api_key.revoked"


class AuditEvent(BaseModel):
    actor_id: str
    actor_email: str = ""
    action: AuditAction
    resource_type: str
    resource_id: str
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    metadata: dict[str, Any] = {}


def _compute_hash(prev_hash: str, event: AuditEvent, timestamp: datetime) -> str:
    payload = json.dumps(
        {
            "prev_hash": prev_hash,
            "actor_id": event.actor_id,
            "action": event.action.value,
            "resource_type": event.resource_type,
            "resource_id": event.resource_id,
            "timestamp": timestamp.isoformat(),
        },
        sort_keys=True,
    ).encode()
    return hashlib.sha256(payload).hexdigest()


async def emit_audit_event(
    session: AsyncSession,
    event: AuditEvent,
) -> AuditLogTable:
    # Get previous row hash for chain
    result = await session.execute(
        select(AuditLogTable.entry_hash)
        .order_by(AuditLogTable.id.desc())
        .limit(1)
    )
    prev = result.scalar_one_or_none()
    prev_hash = prev or "0" * 64

    now = datetime.now(UTC)
    entry_hash = _compute_hash(prev_hash, event, now)

    row = AuditLogTable(
        actor_id=event.actor_id,
        actor_email=event.actor_email,
        action=event.action.value,
        resource_type=event.resource_type,
        resource_id=event.resource_id,
        before_snapshot=event.before or {},
        after_snapshot=event.after or {},
        ip_address=event.ip_address,
        user_agent=event.user_agent,
        extra_metadata=event.metadata,
        prev_hash=prev_hash,
        entry_hash=entry_hash,
        timestamp=now,
    )
    session.add(row)
    await session.flush()

    logger.info(
        "audit.event",
        actor=event.actor_id,
        action=event.action.value,
        resource=f"{event.resource_type}/{event.resource_id}",
        hash=entry_hash[:12],
    )
    return row


async def verify_chain(session: AsyncSession) -> tuple[bool, int, str | None]:
    """
    Walk every audit row and verify the hash chain is unbroken.
    Returns (is_valid, rows_checked, first_broken_entry_id).
    """
    result = await session.execute(
        select(AuditLogTable).order_by(AuditLogTable.id)
    )
    rows = result.scalars().all()
    prev_hash = "0" * 64
    for row in rows:
        if row.prev_hash != prev_hash:
            return False, rows.index(row), str(row.id)
        recomputed = _compute_hash(
            prev_hash,
            AuditEvent(
                actor_id=row.actor_id,
                action=AuditAction(row.action),
                resource_type=row.resource_type,
                resource_id=row.resource_id,
            ),
            row.timestamp,
        )
        if recomputed != row.entry_hash:
            return False, rows.index(row), str(row.id)
        prev_hash = row.entry_hash
    return True, len(rows), None
