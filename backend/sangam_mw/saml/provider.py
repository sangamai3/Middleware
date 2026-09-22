"""
SAML 2.0 / SSO provider integration.

Supports: Okta, Azure AD, Google Workspace, and any IdP exposing standard SAML 2.0.
SCIM user provisioning is handled separately via the /scim/v2 endpoint.

Flow:
  1. SP initiates: GET /auth/saml/login → redirect to IdP with AuthnRequest
  2. IdP responds: POST /auth/saml/callback with SAMLResponse (base64 XML)
  3. We validate signature, extract NameID + attributes → upsert user + emit JWT
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

try:
    from onelogin.saml2.auth import OneLogin_Saml2_Auth  # type: ignore[import]
    from onelogin.saml2.settings import OneLogin_Saml2_Settings  # type: ignore[import]
    _HAS_SAML = True
except ImportError:
    _HAS_SAML = False


def _require_saml() -> None:
    if not _HAS_SAML:
        raise ImportError(
            "python3-saml is required for SAML SSO: pip install python3-saml"
        )


@dataclass
class SAMLConfig:
    idp_entity_id: str
    idp_sso_url: str
    idp_slo_url: str = ""
    idp_x509_cert: str = ""
    sp_entity_id: str = "sangam-mw"
    sp_acs_url: str = ""
    sp_slo_url: str = ""
    attribute_mapping: dict[str, str] = field(default_factory=lambda: {
        "email": "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress",
        "name": "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name",
        "role": "sangam_mw_role",
    })
    default_role: str = "developer"
    strict: bool = True
    debug: bool = False


@dataclass
class SAMLProvider:
    config: SAMLConfig

    def _saml_settings(self) -> dict[str, Any]:
        return {
            "strict": self.config.strict,
            "debug": self.config.debug,
            "sp": {
                "entityId": self.config.sp_entity_id,
                "assertionConsumerService": {
                    "url": self.config.sp_acs_url,
                    "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST",
                },
                "singleLogoutService": {
                    "url": self.config.sp_slo_url,
                    "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect",
                },
                "NameIDFormat": "urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress",
                "x509cert": "",
                "privateKey": "",
            },
            "idp": {
                "entityId": self.config.idp_entity_id,
                "singleSignOnService": {
                    "url": self.config.idp_sso_url,
                    "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect",
                },
                "singleLogoutService": {
                    "url": self.config.idp_slo_url,
                    "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect",
                },
                "x509cert": self.config.idp_x509_cert,
            },
        }

    def get_login_url(self) -> str:
        """Generate IdP redirect URL (SP-initiated SSO)."""
        _require_saml()
        settings = OneLogin_Saml2_Settings(self._saml_settings(), sp_validation_only=True)
        auth = OneLogin_Saml2_Auth({}, old_settings=settings)
        return str(auth.login())

    def get_metadata_xml(self) -> str:
        """Return SP metadata XML for IdP registration."""
        _require_saml()
        settings = OneLogin_Saml2_Settings(self._saml_settings(), sp_validation_only=True)
        meta = settings.get_sp_metadata()
        errors = settings.validate_metadata(meta)
        if errors:
            raise ValueError(f"SP metadata invalid: {errors}")
        return str(meta)


def process_saml_response(
    saml_config: SAMLConfig,
    request_data: dict[str, Any],
) -> dict[str, Any]:
    """
    Validate a SAML 2.0 response and extract user attributes.

    `request_data` must have:
      https (bool), http_host, script_name, server_port, get_data, post_data

    Returns dict with: email, name, role, raw_attributes, name_id
    """
    _require_saml()
    provider = SAMLProvider(saml_config)
    settings = OneLogin_Saml2_Settings(provider._saml_settings())
    auth = OneLogin_Saml2_Auth(request_data, old_settings=settings)
    auth.process_response()
    errors = auth.get_errors()
    if errors:
        raise ValueError(f"SAML validation failed: {errors} — {auth.get_last_error_reason()}")

    attrs = auth.get_attributes()
    mapping = saml_config.attribute_mapping

    def _attr(key: str) -> str:
        mapped = mapping.get(key, key)
        values = attrs.get(mapped, [])
        return values[0] if values else ""

    return {
        "name_id": auth.get_nameid(),
        "email": _attr("email") or auth.get_nameid(),
        "name": _attr("name") or _attr("email"),
        "role": _attr("role") or saml_config.default_role,
        "raw_attributes": {k: v for k, v in attrs.items()},
    }
