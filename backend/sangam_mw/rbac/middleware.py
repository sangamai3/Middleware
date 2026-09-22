"""Convenience dependency that returns the current user dict including role."""
from __future__ import annotations

from typing import Any

from fastapi import Depends

from ..api.auth import get_current_user


async def get_current_user_with_role(
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    if "role" not in user:
        user["role"] = "viewer"
    return user
