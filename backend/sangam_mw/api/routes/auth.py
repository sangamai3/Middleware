from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...config import get_settings
from ...db.base import get_session
from ...db.tables import UserTable
from ..auth import (
    create_access_token,
    exchange_google_code,
    get_current_user,
    google_auth_url,
)

router = APIRouter(prefix="/auth", tags=["auth"])

# Dev users for local development (no DB required)
_DEV_USERS = {
    "admin@sangam.ai": {"password": "admin123", "role": "admin", "name": "Admin User"},
    "dev@sangam.ai":   {"password": "dev123",   "role": "developer", "name": "Dev User"},
    "dev@example.com": {"password": "dev123",   "role": "developer", "name": "Dev User"},
    "ops@sangam.ai":   {"password": "ops123",   "role": "operator", "name": "Ops User"},
    "viewer@sangam.ai":{"password": "view123",  "role": "viewer", "name": "Viewer"},
}


class LoginRequest(BaseModel):
    email: str
    password: str


class GoogleCallbackRequest(BaseModel):
    code: str
    redirect_uri: str


@router.post("/login")
async def login(body: LoginRequest) -> dict:
    user = _DEV_USERS.get(body.email)
    if not user or user["password"] != body.password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    token = create_access_token({
        "sub": body.email,
        "email": body.email,
        "name": user["name"],
        "role": user["role"],
    })
    return {
        "access_token": token,
        "token_type": "bearer",
        "user_id": body.email,
        "email": body.email,
        "role": user["role"],
        "name": user["name"],
    }


@router.get("/google/login")
async def google_login(redirect_uri: str, state: str = "") -> dict:
    settings = get_settings()
    if not settings.google_client_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Google OAuth is not configured (GOOGLE_CLIENT_ID missing)",
        )
    return {"authorization_url": google_auth_url(redirect_uri, state)}


@router.post("/google/callback")
async def google_callback(
    body: GoogleCallbackRequest,
    session: AsyncSession = Depends(get_session),
) -> dict:
    try:
        info = await exchange_google_code(body.code, body.redirect_uri)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Google OAuth exchange failed: {exc}",
        ) from exc
    email = info.get("email")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google account did not return an email",
        )
    user = await upsert_google_user(session, info)
    token = create_access_token(
        {
            "sub": user.user_id,
            "email": user.email,
            "name": user.name,
            "role": user.role,
        }
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "user_id": user.user_id,
            "email": user.email,
            "name": user.name,
            "role": user.role,
            "picture": user.picture,
        },
    }


@router.get("/me")
async def me(user: dict = Depends(get_current_user)) -> dict:
    return user


async def upsert_google_user(session: AsyncSession, info: dict) -> UserTable:
    email = str(info["email"])
    user_id = str(info.get("id") or email)
    name = str(info.get("name") or email)
    picture = info.get("picture")
    result = await session.execute(select(UserTable).where(UserTable.email == email))
    user = result.scalar_one_or_none()
    now = datetime.now(UTC)
    if user is None:
        user = UserTable(
            user_id=user_id,
            email=email,
            name=name,
            picture=str(picture) if picture else None,
            last_login=now,
        )
        session.add(user)
    else:
        user.name = name
        user.picture = str(picture) if picture else user.picture
        user.last_login = now
        user.is_active = True
    await session.commit()
    await session.refresh(user)
    return user
