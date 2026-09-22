"""
SCIM 2.0 user provisioning endpoint.

Allows identity providers (Okta, Azure AD, OneLogin) to automatically
provision and deprovision users via standard SCIM protocol.

RFC 7643 / RFC 7644 subset:
  GET    /scim/v2/Users                List users
  POST   /scim/v2/Users                Create user
  GET    /scim/v2/Users/{id}           Get user
  PUT    /scim/v2/Users/{id}           Replace user
  PATCH  /scim/v2/Users/{id}           Update user (active/role)
  DELETE /scim/v2/Users/{id}           Deprovision (deactivate)
  GET    /scim/v2/ServiceProviderConfig  Capabilities
  GET    /scim/v2/Schemas               Schema definitions
"""
from __future__ import annotations

import secrets
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from ...rbac.permissions import Permission, require_permission

router = APIRouter(prefix="/scim/v2", tags=["scim"])

# In-memory store; production wires this to the DB UserTable
_users: dict[str, dict[str, Any]] = {}

_SCIM_SCHEMA = "urn:ietf:params:scim:schemas:core:2.0:User"
_ENTERPRISE_SCHEMA = "urn:ietf:params:scim:schemas:extension:enterprise:2.0:User"


def _scim_user(user: dict[str, Any]) -> dict[str, Any]:
    return {
        "schemas": [_SCIM_SCHEMA, _ENTERPRISE_SCHEMA],
        "id": user["id"],
        "externalId": user.get("externalId", ""),
        "userName": user["email"],
        "name": {
            "formatted": user.get("name", ""),
            "givenName": user.get("name", "").split(" ")[0] if user.get("name") else "",
            "familyName": " ".join(user.get("name", "").split(" ")[1:]) if user.get("name") else "",
        },
        "emails": [{"value": user["email"], "primary": True}],
        "active": user.get("is_active", True),
        "meta": {
            "resourceType": "User",
            "created": user.get("created_at", datetime.now(UTC).isoformat()),
            "lastModified": user.get("updated_at", datetime.now(UTC).isoformat()),
            "location": f"/scim/v2/Users/{user['id']}",
        },
        _ENTERPRISE_SCHEMA: {
            "organization": "SangamMW",
            "department": user.get("role", "developer"),
        },
    }


def _require_scim_token(authorization: str = Header(...)) -> str:
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "SCIM bearer token required")
    return authorization.removeprefix("Bearer ").strip()


@router.get("/ServiceProviderConfig")
async def service_provider_config() -> dict[str, Any]:
    return {
        "schemas": ["urn:ietf:params:scim:schemas:core:2.0:ServiceProviderConfig"],
        "documentationUri": "https://docs.sangammw.io/scim",
        "patch": {"supported": True},
        "bulk": {"supported": False, "maxOperations": 0, "maxPayloadSize": 0},
        "filter": {"supported": True, "maxResults": 200},
        "changePassword": {"supported": False},
        "sort": {"supported": False},
        "etag": {"supported": False},
        "authenticationSchemes": [
            {
                "name": "OAuth Bearer Token",
                "description": "Authentication via OAuth Bearer Token",
                "specUri": "https://www.rfc-editor.org/rfc/rfc6750",
                "type": "oauthbearertoken",
                "primary": True,
            }
        ],
    }


@router.get("/Schemas")
async def list_schemas() -> dict[str, Any]:
    return {
        "schemas": ["urn:ietf:params:scim:api:messages:2.0:ListResponse"],
        "totalResults": 1,
        "Resources": [{"id": _SCIM_SCHEMA, "name": "User", "description": "User account"}],
    }


@router.get("/Users")
async def list_users(
    startIndex: int = 1,
    count: int = 100,
    filter: str | None = None,
    _token: str = Depends(_require_scim_token),
) -> dict[str, Any]:
    users = list(_users.values())
    if filter:
        if 'userName eq "' in filter:
            email = filter.split('"')[1]
            users = [u for u in users if u["email"] == email]
    total = len(users)
    page = users[startIndex - 1: startIndex - 1 + count]
    return {
        "schemas": ["urn:ietf:params:scim:api:messages:2.0:ListResponse"],
        "totalResults": total,
        "startIndex": startIndex,
        "itemsPerPage": count,
        "Resources": [_scim_user(u) for u in page],
    }


@router.post("/Users", status_code=201)
async def create_user(
    body: dict[str, Any],
    _token: str = Depends(_require_scim_token),
) -> dict[str, Any]:
    email = body.get("userName", "")
    if not email:
        raise HTTPException(400, "userName (email) is required")
    if any(u["email"] == email for u in _users.values()):
        raise HTTPException(409, f"User with userName '{email}' already exists")
    user_id = secrets.token_hex(8)
    name_obj = body.get("name", {})
    name = name_obj.get("formatted") or f"{name_obj.get('givenName', '')} {name_obj.get('familyName', '')}".strip()
    now = datetime.now(UTC).isoformat()
    user = {
        "id": user_id,
        "externalId": body.get("externalId", ""),
        "email": email,
        "name": name,
        "is_active": body.get("active", True),
        "role": "developer",
        "created_at": now,
        "updated_at": now,
    }
    _users[user_id] = user
    return _scim_user(user)


@router.get("/Users/{user_id}")
async def get_user(
    user_id: str,
    _token: str = Depends(_require_scim_token),
) -> dict[str, Any]:
    user = _users.get(user_id)
    if not user:
        raise HTTPException(404, f"User '{user_id}' not found")
    return _scim_user(user)


@router.put("/Users/{user_id}")
async def replace_user(
    user_id: str,
    body: dict[str, Any],
    _token: str = Depends(_require_scim_token),
) -> dict[str, Any]:
    user = _users.get(user_id)
    if not user:
        raise HTTPException(404, f"User '{user_id}' not found")
    name_obj = body.get("name", {})
    user["name"] = name_obj.get("formatted") or f"{name_obj.get('givenName', '')} {name_obj.get('familyName', '')}".strip()
    user["is_active"] = body.get("active", user["is_active"])
    user["updated_at"] = datetime.now(UTC).isoformat()
    return _scim_user(user)


@router.patch("/Users/{user_id}")
async def patch_user(
    user_id: str,
    body: dict[str, Any],
    _token: str = Depends(_require_scim_token),
) -> dict[str, Any]:
    user = _users.get(user_id)
    if not user:
        raise HTTPException(404, f"User '{user_id}' not found")
    for op in body.get("Operations", []):
        op_type = op.get("op", "").lower()
        path = op.get("path", "")
        value = op.get("value")
        if op_type == "replace":
            if path == "active" or (isinstance(value, dict) and "active" in value):
                active_val = value if isinstance(value, bool) else value.get("active", user["is_active"])
                user["is_active"] = active_val
            elif path == "name.formatted" and isinstance(value, str):
                user["name"] = value
    user["updated_at"] = datetime.now(UTC).isoformat()
    return _scim_user(user)


@router.delete("/Users/{user_id}", status_code=204)
async def delete_user(
    user_id: str,
    _token: str = Depends(_require_scim_token),
) -> None:
    user = _users.get(user_id)
    if not user:
        raise HTTPException(404, f"User '{user_id}' not found")
    user["is_active"] = False
    user["updated_at"] = datetime.now(UTC).isoformat()
