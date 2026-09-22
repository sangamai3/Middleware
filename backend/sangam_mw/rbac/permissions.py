"""
RBAC permission model.

Roles: admin > developer > operator > viewer
Each role is a cumulative superset of the one below it.
"""
from __future__ import annotations

from enum import Enum
from functools import lru_cache
from typing import Any

from fastapi import Depends, HTTPException, status

from ..api.auth import get_current_user


class Role(str, Enum):
    ADMIN = "admin"
    DEVELOPER = "developer"
    OPERATOR = "operator"
    VIEWER = "viewer"


class Permission(str, Enum):
    # Flows
    FLOW_READ = "flow:read"
    FLOW_CREATE = "flow:create"
    FLOW_UPDATE = "flow:update"
    FLOW_DELETE = "flow:delete"
    FLOW_DEPLOY = "flow:deploy"
    # Executions
    EXECUTION_READ = "execution:read"
    EXECUTION_TRIGGER = "execution:trigger"
    EXECUTION_CANCEL = "execution:cancel"
    EXECUTION_REPLAY = "execution:replay"
    # Connections
    CONNECTION_READ = "connection:read"
    CONNECTION_CREATE = "connection:create"
    CONNECTION_UPDATE = "connection:update"
    CONNECTION_DELETE = "connection:delete"
    CONNECTION_TEST = "connection:test"
    # Admin
    USER_READ = "user:read"
    USER_MANAGE = "user:manage"
    AUDIT_READ = "audit:read"
    SYSTEM_SETTINGS = "system:settings"


_ROLE_PERMISSIONS: dict[Role, set[Permission]] = {
    Role.VIEWER: {
        Permission.FLOW_READ,
        Permission.EXECUTION_READ,
        Permission.CONNECTION_READ,
    },
    Role.OPERATOR: {
        Permission.FLOW_READ,
        Permission.EXECUTION_READ,
        Permission.EXECUTION_TRIGGER,
        Permission.EXECUTION_CANCEL,
        Permission.EXECUTION_REPLAY,
        Permission.CONNECTION_READ,
        Permission.CONNECTION_TEST,
    },
    Role.DEVELOPER: {
        Permission.FLOW_READ,
        Permission.FLOW_CREATE,
        Permission.FLOW_UPDATE,
        Permission.FLOW_DELETE,
        Permission.FLOW_DEPLOY,
        Permission.EXECUTION_READ,
        Permission.EXECUTION_TRIGGER,
        Permission.EXECUTION_CANCEL,
        Permission.EXECUTION_REPLAY,
        Permission.CONNECTION_READ,
        Permission.CONNECTION_CREATE,
        Permission.CONNECTION_UPDATE,
        Permission.CONNECTION_DELETE,
        Permission.CONNECTION_TEST,
        Permission.USER_READ,
    },
    Role.ADMIN: {p for p in Permission},  # all permissions
}


@lru_cache(maxsize=None)
def _permissions_for_role(role: Role) -> frozenset[Permission]:
    return frozenset(_ROLE_PERMISSIONS.get(role, set()))


def has_permission(user_role: str, permission: Permission) -> bool:
    try:
        role = Role(user_role)
    except ValueError:
        return False
    return permission in _permissions_for_role(role)


def require_permission(permission: Permission):
    """FastAPI dependency that enforces a permission, returning the decoded user dict."""
    async def _dep(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
        role = user.get("role", "viewer")
        if not has_permission(role, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{role}' does not have permission '{permission.value}'",
            )
        return user
    return _dep
