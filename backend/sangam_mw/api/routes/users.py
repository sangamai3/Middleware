"""
User management API — admin only.

GET  /api/v1/users            list users
GET  /api/v1/users/me         current user profile
PATCH /api/v1/users/{user_id} update role (admin only)
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.base import get_session
from ...db.tables import UserTable
from ...rbac.permissions import Permission, Role, require_permission

router = APIRouter(prefix="/users", tags=["users"])


class UserOut(BaseModel):
    user_id: str
    email: str
    name: str
    picture: str | None
    role: str
    is_active: bool
    created_at: str
    last_login: str | None


class UpdateRoleRequest(BaseModel):
    role: Role


def _user_out(row: UserTable) -> dict[str, Any]:
    return {
        "user_id": row.user_id,
        "email": row.email,
        "name": row.name,
        "picture": row.picture,
        "role": row.role,
        "is_active": row.is_active,
        "created_at": row.created_at.isoformat(),
        "last_login": row.last_login.isoformat() if row.last_login else None,
    }


@router.get("/me")
async def me(
    user: dict[str, Any] = Depends(require_permission(Permission.FLOW_READ)),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    result = await session.execute(
        select(UserTable).where(UserTable.user_id == user["sub"])
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    return _user_out(row)


@router.get("")
async def list_users(
    user: dict[str, Any] = Depends(require_permission(Permission.USER_READ)),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    result = await session.execute(select(UserTable).order_by(UserTable.created_at))
    return [_user_out(row) for row in result.scalars().all()]


@router.patch("/{user_id}")
async def update_role(
    user_id: str,
    body: UpdateRoleRequest,
    requester: dict[str, Any] = Depends(require_permission(Permission.USER_MANAGE)),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    result = await session.execute(
        select(UserTable).where(UserTable.user_id == user_id)
    )
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if target.user_id == requester["sub"] and body.role != Role.ADMIN:
        raise HTTPException(
            status_code=400, detail="Admins cannot demote themselves"
        )
    target.role = body.role.value
    await session.commit()
    await session.refresh(target)
    return _user_out(target)
