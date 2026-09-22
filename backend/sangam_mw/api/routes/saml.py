"""
SAML 2.0 SSO routes.

GET  /auth/saml/login       → redirect to IdP
POST /auth/saml/callback    → validate SAMLResponse, issue JWT
GET  /auth/saml/metadata    → SP metadata XML (for IdP registration)
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse, Response

from ...api.auth import create_access_token
from ...audit.log import AuditAction, AuditEvent, emit_audit_event
from ...config import get_settings
from ...saml.provider import SAMLConfig, SAMLProvider, process_saml_response

router = APIRouter(prefix="/auth/saml", tags=["saml"])


def _saml_config_from_settings() -> SAMLConfig:
    settings = get_settings()
    return SAMLConfig(
        idp_entity_id=getattr(settings, "saml_idp_entity_id", ""),
        idp_sso_url=getattr(settings, "saml_idp_sso_url", ""),
        idp_slo_url=getattr(settings, "saml_idp_slo_url", ""),
        idp_x509_cert=getattr(settings, "saml_idp_x509_cert", ""),
        sp_entity_id=getattr(settings, "saml_sp_entity_id", "sangam-mw"),
        sp_acs_url=getattr(settings, "saml_sp_acs_url", ""),
        default_role=getattr(settings, "saml_default_role", "developer"),
    )


def _request_to_saml(request: Request) -> dict[str, Any]:
    return {
        "https": "on" if request.url.scheme == "https" else "off",
        "http_host": request.headers.get("host", "localhost"),
        "script_name": request.url.path,
        "server_port": str(request.url.port or (443 if request.url.scheme == "https" else 80)),
        "get_data": dict(request.query_params),
        "post_data": {},
    }


@router.get("/login")
async def saml_login() -> RedirectResponse:
    try:
        config = _saml_config_from_settings()
        provider = SAMLProvider(config)
        url = provider.get_login_url()
        return RedirectResponse(url)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"SAML login failed: {exc}") from exc


@router.post("/callback")
async def saml_callback(
    request: Request,
    SAMLResponse: str = Form(...),
) -> dict[str, Any]:
    try:
        config = _saml_config_from_settings()
        req_data = _request_to_saml(request)
        req_data["post_data"] = {"SAMLResponse": SAMLResponse}
        user_info = process_saml_response(config, req_data)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"SAML authentication failed: {exc}",
        ) from exc

    token = create_access_token({
        "sub": user_info["name_id"],
        "email": user_info["email"],
        "name": user_info["name"],
        "role": user_info["role"],
        "auth_method": "saml",
    })
    return {
        "access_token": token,
        "token_type": "bearer",
        "email": user_info["email"],
        "name": user_info["name"],
        "role": user_info["role"],
    }


@router.get("/metadata")
async def saml_metadata() -> Response:
    try:
        config = _saml_config_from_settings()
        provider = SAMLProvider(config)
        xml = provider.get_metadata_xml()
        return Response(content=xml, media_type="application/xml")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"SAML metadata error: {exc}") from exc
