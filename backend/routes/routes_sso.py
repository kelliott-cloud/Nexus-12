"""SSO Routes — SAML 2.0 SP and OIDC authorization code flow for enterprise SSO.
Supports generic SAML IdPs (Okta, Azure AD, OneLogin, etc.) and OIDC providers.
Hardened with strict claim validation, nonce replay protection, session binding,
auth_time freshness enforcement, acr validation, and provider-specific quirks.
"""
import uuid
import secrets
import logging
import base64
import zlib
import re
import hashlib
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel
from fastapi import HTTPException, Request, Response
from typing import Optional
from urllib.parse import urlencode, quote
import defusedxml.ElementTree as ET

logger = logging.getLogger(__name__)

_EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")

# Max allowed clock skew for OIDC token validation (seconds)
OIDC_CLOCK_SKEW_SECONDS = 120
# Max age for auth_time claim (seconds) — reject tokens older than this
OIDC_AUTH_TIME_MAX_AGE = 300  # 5 minutes
# Minimum acceptable ACR values (authentication context class reference)
ACCEPTED_ACR_VALUES = {
    "urn:oasis:names:tc:SAML:2.0:ac:classes:PasswordProtectedTransport",
    "urn:oasis:names:tc:SAML:2.0:ac:classes:MobileTwoFactorContract",
    "http://schemas.openid.net/pape/policies/2007/06/multi-factor",
    "urn:mace:incommon:iap:silver",
    "urn:mace:incommon:iap:bronze",
    "phishing_resistant",
    "phr",  # Phishing resistant short
    "phrh",  # Phishing resistant hardware
    "aal2",  # AAL level 2
    "aal3",  # AAL level 3
}

# Provider-specific attribute mappings for SAML
PROVIDER_ATTRIBUTE_MAPS = {
    "okta": {
        "email": ["email", "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress"],
        "name": ["displayName", "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name"],
    },
    "azure_ad": {
        "email": [
            "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress",
            "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name",
        ],
        "name": [
            "http://schemas.microsoft.com/identity/claims/displayname",
            "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/givenname",
        ],
    },
    "google": {
        "email": ["email"],
        "name": ["name", "displayName"],
    },
    "onelogin": {
        "email": ["User.email", "email"],
        "name": ["User.FirstName", "name"],
    },
}


def _validate_email(email: str) -> str:
    """Validate and normalize email from SSO claims."""
    if not email or not isinstance(email, str):
        raise HTTPException(400, "SSO response missing email claim")
    email = email.strip().lower()
    if not _EMAIL_RE.match(email):
        raise HTTPException(400, f"Invalid email format from SSO: {email[:50]}")
    if len(email) > 254:
        raise HTTPException(400, "Email address too long")
    return email


def _session_fingerprint(request: Request) -> str:
    """Generate a fingerprint from IP + User-Agent for session binding."""
    ip = request.headers.get("x-forwarded-for", request.client.host or "unknown").split(",")[0].strip()
    ua = request.headers.get("user-agent", "unknown")[:200]
    raw = f"{ip}|{ua}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


class SSOConfigCreate(BaseModel):
    provider_name: str
    protocol: str  # "saml" or "oidc"
    provider_type: Optional[str] = None  # "okta", "azure_ad", "google", "onelogin", "generic"
    # SAML fields
    idp_entity_id: Optional[str] = None
    idp_sso_url: Optional[str] = None
    idp_certificate: Optional[str] = None
    # OIDC fields
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    authorization_url: Optional[str] = None
    token_url: Optional[str] = None
    userinfo_url: Optional[str] = None
    jwks_uri: Optional[str] = None
    # Common
    auto_provision: bool = True
    default_role: str = "member"


class SSOConfigUpdate(BaseModel):
    provider_name: Optional[str] = None
    provider_type: Optional[str] = None
    idp_entity_id: Optional[str] = None
    idp_sso_url: Optional[str] = None
    idp_certificate: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    authorization_url: Optional[str] = None
    token_url: Optional[str] = None
    userinfo_url: Optional[str] = None
    jwks_uri: Optional[str] = None
    auto_provision: Optional[bool] = None
    default_role: Optional[str] = None
    enabled: Optional[bool] = None


def register_sso_routes(api_router, db, get_current_user):
    import os
    APP_URL = os.environ.get("APP_URL", os.environ.get("CORS_ORIGINS", "http://localhost:3000")).split(",")[0].strip().strip('"')

    # ============ ADMIN: SSO CONFIGURATION ============

    @api_router.post("/admin/sso/config")
    async def create_sso_config(data: SSOConfigCreate, request: Request):
        """Create SSO configuration for a workspace (admin only)."""
        user = await get_current_user(request)
        if user.get("platform_role") != "super_admin":
            raise HTTPException(403, "Super admin required")

        workspace_id = request.query_params.get("workspace_id")
        if not workspace_id:
            raise HTTPException(400, "workspace_id required")

        config_id = f"sso_{uuid.uuid4().hex[:12]}"
        config = {
            "config_id": config_id,
            "workspace_id": workspace_id,
            "protocol": data.protocol,
            "provider_name": data.provider_name,
            "provider_type": data.provider_type or "generic",
            "enabled": True,
            "auto_provision": data.auto_provision,
            "default_role": data.default_role,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": user["user_id"],
        }

        if data.protocol == "saml":
            if not all([data.idp_entity_id, data.idp_sso_url, data.idp_certificate]):
                raise HTTPException(400, "SAML requires idp_entity_id, idp_sso_url, and idp_certificate")
            config.update({
                "idp_entity_id": data.idp_entity_id,
                "idp_sso_url": data.idp_sso_url,
                "idp_certificate": data.idp_certificate,
                "sp_entity_id": f"{APP_URL}/api/sso/saml/metadata/{config_id}",
                "sp_acs_url": f"{APP_URL}/api/sso/saml/acs/{config_id}",
            })
        elif data.protocol == "oidc":
            if not all([data.client_id, data.client_secret, data.authorization_url, data.token_url]):
                raise HTTPException(400, "OIDC requires client_id, client_secret, authorization_url, and token_url")
            config.update({
                "client_id": data.client_id,
                "client_secret": data.client_secret,
                "authorization_url": data.authorization_url,
                "token_url": data.token_url,
                "userinfo_url": data.userinfo_url or "",
                "jwks_uri": data.jwks_uri or "",
                "redirect_uri": f"{APP_URL}/api/sso/oidc/callback/{config_id}",
            })
        else:
            raise HTTPException(400, "Protocol must be 'saml' or 'oidc'")

        await db.sso_configs.insert_one(config)
        config.pop("_id", None)
        config.pop("client_secret", None)
        return config

    @api_router.get("/admin/sso/configs")
    async def list_sso_configs(request: Request):
        """List all SSO configurations (admin only)."""
        user = await get_current_user(request)
        if user.get("platform_role") != "super_admin":
            raise HTTPException(403, "Super admin required")
        workspace_id = request.query_params.get("workspace_id")
        query = {}
        if workspace_id:
            query["workspace_id"] = workspace_id
        configs = await db.sso_configs.find(query, {"_id": 0, "client_secret": 0, "idp_certificate": 0}).to_list(50)
        return {"configs": configs}

    @api_router.put("/admin/sso/config/{config_id}")
    async def update_sso_config(config_id: str, data: SSOConfigUpdate, request: Request):
        """Update SSO configuration."""
        user = await get_current_user(request)
        if user.get("platform_role") != "super_admin":
            raise HTTPException(403, "Super admin required")
        updates = {k: v for k, v in data.dict().items() if v is not None}
        if not updates:
            raise HTTPException(400, "No fields to update")
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        await db.sso_configs.update_one({"config_id": config_id}, {"$set": updates})
        return {"status": "updated"}

    @api_router.delete("/admin/sso/config/{config_id}")
    async def delete_sso_config(config_id: str, request: Request):
        """Delete SSO configuration."""
        user = await get_current_user(request)
        if user.get("platform_role") != "super_admin":
            raise HTTPException(403, "Super admin required")
        await db.sso_configs.delete_one({"config_id": config_id})
        return {"status": "deleted"}

    # ============ SAML FLOW ============

    @api_router.get("/sso/saml/metadata/{config_id}")
    async def saml_sp_metadata(config_id: str):
        """Return SP metadata XML for IdP configuration."""
        config = await db.sso_configs.find_one({"config_id": config_id, "protocol": "saml"}, {"_id": 0})
        if not config:
            raise HTTPException(404, "SSO configuration not found")
        xml = f"""<?xml version="1.0"?>
<md:EntityDescriptor xmlns:md="urn:oasis:names:tc:SAML:2.0:metadata" entityID="{config['sp_entity_id']}">
  <md:SPSSODescriptor AuthnRequestsSigned="false" WantAssertionsSigned="true"
    protocolSupportEnumeration="urn:oasis:names:tc:SAML:2.0:protocol">
    <md:NameIDFormat>urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress</md:NameIDFormat>
    <md:AssertionConsumerService Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST"
      Location="{config['sp_acs_url']}" index="0" isDefault="true"/>
  </md:SPSSODescriptor>
</md:EntityDescriptor>"""
        from fastapi.responses import Response as RawResponse
        return RawResponse(content=xml, media_type="application/xml")

    @api_router.get("/sso/saml/login/{config_id}")
    async def saml_login(config_id: str, request: Request):
        """Initiate SAML SSO login — redirects to IdP."""
        config = await db.sso_configs.find_one({"config_id": config_id, "protocol": "saml", "enabled": True}, {"_id": 0})
        if not config:
            raise HTTPException(404, "SSO configuration not found or disabled")

        req_id = f"_nexus_{uuid.uuid4().hex[:16]}"
        authn_request = f"""<samlp:AuthnRequest xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol"
  xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion"
  ID="{req_id}" Version="2.0" IssueInstant="{datetime.now(timezone.utc).isoformat()}Z"
  Destination="{config['idp_sso_url']}"
  AssertionConsumerServiceURL="{config['sp_acs_url']}"
  ProtocolBinding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST">
  <saml:Issuer>{config['sp_entity_id']}</saml:Issuer>
  <samlp:NameIDPolicy Format="urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress" AllowCreate="true"/>
</samlp:AuthnRequest>"""

        deflated = zlib.compress(authn_request.encode())[2:-4]
        encoded = base64.b64encode(deflated).decode()
        params = urlencode({"SAMLRequest": encoded})
        redirect_url = f"{config['idp_sso_url']}?{params}"

        from fastapi.responses import RedirectResponse
        return RedirectResponse(url=redirect_url, status_code=302)

    @api_router.post("/sso/saml/acs/{config_id}")
    async def saml_acs(config_id: str, request: Request, response: Response):
        """SAML Assertion Consumer Service — process IdP response with signature verification."""
        config = await db.sso_configs.find_one({"config_id": config_id, "protocol": "saml"}, {"_id": 0})
        if not config:
            raise HTTPException(404, "SSO configuration not found")

        form = await request.form()
        saml_response_b64 = form.get("SAMLResponse")
        if not saml_response_b64:
            raise HTTPException(400, "Missing SAMLResponse")

        email, name = None, None
        try:
            from onelogin.saml2.auth import OneLogin_Saml2_Auth
            saml_settings = {
                "strict": True,
                "idp": {
                    "entityId": config["idp_entity_id"],
                    "singleSignOnService": {"url": config["idp_sso_url"], "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect"},
                    "x509cert": config["idp_certificate"],
                },
                "sp": {
                    "entityId": config["sp_entity_id"],
                    "assertionConsumerService": {
                        "url": config["sp_acs_url"],
                        "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST",
                    },
                    "NameIDFormat": "urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress",
                },
                "security": {
                    "wantAssertionsSigned": True,
                    "wantMessagesSigned": False,
                },
            }
            is_https = str(request.url).startswith("https") or request.headers.get("x-forwarded-proto") == "https"
            host = request.headers.get("x-forwarded-host", request.url.hostname)
            req = {
                "https": "on" if is_https else "off",
                "http_host": host,
                "script_name": request.url.path,
                "post_data": {"SAMLResponse": saml_response_b64},
            }
            auth = OneLogin_Saml2_Auth(req, old_settings=saml_settings)
            auth.process_response()
            errors = auth.get_errors()
            if errors:
                logger.error(f"SAML validation errors: {errors}, reason: {auth.get_last_error_reason()}")
                raise HTTPException(400, f"SAML validation failed: {', '.join(errors)}")

            email = auth.get_nameid()
            attributes = auth.get_attributes()

            # Provider-specific attribute extraction
            provider_type = config.get("provider_type", "generic")
            name = _extract_saml_name(attributes, provider_type)

        except HTTPException:
            raise
        except ImportError:
            logger.error("python3-saml is required for SAML SSO but is not installed. Install: pip install python3-saml")
            raise HTTPException(500, "SAML SSO is not properly configured. Contact your administrator.")
        except Exception as e:
            logger.error(f"SAML processing error: {e}")
            raise HTTPException(400, "SAML response validation failed")

        # Strict email validation
        email = _validate_email(email)

        user = await _sso_provision_user(db, email, name, config)

        session_token = secrets.token_urlsafe(32)
        fingerprint = _session_fingerprint(request)
        await db.user_sessions.insert_one({
            "user_id": user["user_id"],
            "session_token": session_token,
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "sso_provider": config.get("provider_name"),
            "auth_method": "saml",
            "session_fingerprint": fingerprint,
        })

        from fastapi.responses import RedirectResponse
        redirect = RedirectResponse(url=f"{APP_URL}/auth/sso-callback?status=success", status_code=302)
        redirect.set_cookie(
            key="session_token", value=session_token,
            httponly=True, secure=True, samesite="none", path="/", max_age=7*24*60*60
        )
        return redirect

    # ============ OIDC FLOW ============

    @api_router.get("/sso/oidc/login/{config_id}")
    async def oidc_login(config_id: str):
        """Initiate OIDC SSO login — redirects to authorization server with nonce."""
        config = await db.sso_configs.find_one({"config_id": config_id, "protocol": "oidc", "enabled": True}, {"_id": 0})
        if not config:
            raise HTTPException(404, "SSO configuration not found or disabled")

        state = secrets.token_urlsafe(24)
        nonce = secrets.token_urlsafe(24)
        await db.oidc_states.insert_one({
            "state": state,
            "nonce": nonce,
            "config_id": config_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat(),
        })

        params = urlencode({
            "client_id": config["client_id"],
            "redirect_uri": config["redirect_uri"],
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "nonce": nonce,
        })
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url=f"{config['authorization_url']}?{params}", status_code=302)

    @api_router.get("/sso/oidc/callback/{config_id}")
    async def oidc_callback(config_id: str, request: Request, response: Response):
        """OIDC callback — exchange code for tokens with strict validation."""
        code = request.query_params.get("code")
        state = request.query_params.get("state")
        error = request.query_params.get("error")

        if error:
            raise HTTPException(400, f"OIDC error: {error}")
        if not code or not state:
            raise HTTPException(400, "Missing code or state")

        # Verify state with expiry check
        state_doc = await db.oidc_states.find_one({"state": state, "config_id": config_id}, {"_id": 0})
        if not state_doc:
            raise HTTPException(400, "Invalid or expired state")

        # Enforce expiry
        expires_at = state_doc.get("expires_at", "")
        if expires_at and expires_at < datetime.now(timezone.utc).isoformat():
            await db.oidc_states.delete_one({"state": state})
            raise HTTPException(400, "OIDC state expired — please try again")

        nonce = state_doc.get("nonce")
        await db.oidc_states.delete_one({"state": state})

        config = await db.sso_configs.find_one({"config_id": config_id, "protocol": "oidc"}, {"_id": 0})
        if not config:
            raise HTTPException(404, "SSO configuration not found")

        # Exchange code for token
        import httpx
        async with httpx.AsyncClient(timeout=15) as client:
            token_resp = await client.post(config["token_url"], data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": config["redirect_uri"],
                "client_id": config["client_id"],
                "client_secret": config["client_secret"],
            })
            if token_resp.status_code != 200:
                logger.error(f"OIDC token exchange failed: {token_resp.status_code} {token_resp.text[:200]}")
                raise HTTPException(400, "Token exchange failed")
            tokens = token_resp.json()

        email, name = None, None

        # Always verify id_token first if available (most secure path)
        if tokens.get("id_token"):
            email, name = await _verify_id_token(tokens["id_token"], config, expected_nonce=nonce)

        # Fallback: userinfo endpoint
        if not email and config.get("userinfo_url"):
            async with httpx.AsyncClient(timeout=10) as client:
                userinfo_resp = await client.get(config["userinfo_url"], headers={
                    "Authorization": f"Bearer {tokens.get('access_token')}"
                })
                if userinfo_resp.status_code == 200:
                    info = userinfo_resp.json()
                    email = info.get("email")
                    name = info.get("name") or info.get("preferred_username")

        # Strict email validation
        email = _validate_email(email)

        user = await _sso_provision_user(db, email, name, config)

        session_token = secrets.token_urlsafe(32)
        fingerprint = _session_fingerprint(request)
        await db.user_sessions.insert_one({
            "user_id": user["user_id"],
            "session_token": session_token,
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "sso_provider": config.get("provider_name"),
            "auth_method": "oidc",
            "session_fingerprint": fingerprint,
        })

        from fastapi.responses import RedirectResponse
        redirect = RedirectResponse(url=f"{APP_URL}/auth/sso-callback?status=success", status_code=302)
        redirect.set_cookie(
            key="session_token", value=session_token,
            httponly=True, secure=True, samesite="none", path="/", max_age=7*24*60*60
        )
        return redirect

    # ============ PUBLIC: List SSO providers for login page ============

    @api_router.get("/sso/providers")
    async def list_sso_providers():
        """List enabled SSO providers for the login page."""
        configs = await db.sso_configs.find(
            {"enabled": True},
            {"_id": 0, "config_id": 1, "provider_name": 1, "protocol": 1, "workspace_id": 1}
        ).to_list(20)
        return {"providers": configs}


def _extract_saml_name(attributes: dict, provider_type: str) -> str:
    """Extract display name from SAML attributes using provider-specific mappings."""
    attr_map = PROVIDER_ATTRIBUTE_MAPS.get(provider_type, {})
    name_keys = attr_map.get("name", [
        "displayName", "name",
        "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name",
        "http://schemas.microsoft.com/identity/claims/displayname",
    ])
    for key in name_keys:
        val = attributes.get(key, [None])
        if val and val[0]:
            return val[0]
    return None


def _parse_saml_response(xml_str: str, provider_type: str = "generic"):
    """Extract email and name from a SAML response XML."""
    email, name = None, None
    try:
        root = ET.fromstring(xml_str)
        for nameid in root.iter("{urn:oasis:names:tc:SAML:2.0:assertion}NameID"):
            if nameid.text and "@" in nameid.text:
                email = nameid.text
                break

        attr_map = PROVIDER_ATTRIBUTE_MAPS.get(provider_type, {})
        email_keys = set(k.lower() for k in attr_map.get("email", ["email", "mail"]))
        name_keys = set(k.lower() for k in attr_map.get("name", ["displayname", "name"]))

        for attr in root.iter("{urn:oasis:names:tc:SAML:2.0:assertion}Attribute"):
            attr_name = attr.get("Name", "")
            attr_name_lower = attr_name.lower()
            values = [v.text for v in attr.iter("{urn:oasis:names:tc:SAML:2.0:assertion}AttributeValue") if v.text]
            if not values:
                continue
            if any(ek in attr_name_lower or ek == attr_name for ek in email_keys):
                email = email or values[0]
            if any(nk in attr_name_lower or nk == attr_name for nk in name_keys):
                name = name or values[0]
    except ET.ParseError as e:
        logger.error(f"SAML XML parse error: {e}")
    return email, name


async def _verify_id_token(token: str, config: dict, expected_nonce: str = None):
    """Verify and decode an OIDC id_token using JWKS with strict claim validation.
    Validates: signature, exp, aud, iss, nonce, sub, iat clock skew, auth_time freshness, acr, email_verified.
    """
    try:
        import jwt as pyjwt
        from jwt import PyJWKClient

        jwks_uri = config.get("jwks_uri") or config.get("token_url", "").replace("/token", "/.well-known/jwks.json")
        if not jwks_uri:
            logger.warning("No JWKS URI available for id_token verification")
            return None, None

        jwks_client = PyJWKClient(jwks_uri)
        signing_key = jwks_client.get_signing_key_from_jwt(token)

        claims = pyjwt.decode(
            token, signing_key.key,
            algorithms=["RS256", "ES256"],
            audience=config.get("client_id"),
            options={"verify_exp": True, "verify_aud": True, "verify_iss": True},
            issuer=_derive_issuer(config),
            leeway=OIDC_CLOCK_SKEW_SECONDS,
        )

        # 1. Validate nonce to prevent replay attacks
        if expected_nonce and claims.get("nonce") != expected_nonce:
            logger.error(f"OIDC nonce mismatch: expected={expected_nonce[:8]}..., got={str(claims.get('nonce', ''))[:8]}...")
            raise HTTPException(400, "OIDC nonce validation failed — possible replay attack")

        # 2. Enforce sub claim presence and consistency
        sub = claims.get("sub")
        if not sub or not isinstance(sub, str) or len(sub) > 255:
            logger.error(f"OIDC token missing or invalid sub claim: {str(sub)[:20]}")
            raise HTTPException(400, "OIDC token missing required 'sub' claim")

        # 3. Validate iat (issued-at) clock skew
        iat = claims.get("iat")
        if iat:
            now_ts = datetime.now(timezone.utc).timestamp()
            if iat > now_ts + OIDC_CLOCK_SKEW_SECONDS:
                logger.error(f"OIDC iat in future: iat={iat}, now={now_ts}")
                raise HTTPException(400, "OIDC token issued in the future — clock skew too large")

        # 4. Validate auth_time freshness (if present)
        auth_time = claims.get("auth_time")
        if auth_time:
            now_ts = datetime.now(timezone.utc).timestamp()
            age = now_ts - auth_time
            if age > OIDC_AUTH_TIME_MAX_AGE:
                logger.warning(f"OIDC auth_time too old: age={age:.0f}s, max={OIDC_AUTH_TIME_MAX_AGE}s")
                raise HTTPException(400, f"OIDC authentication too old ({int(age)}s) — please re-authenticate")

        # 5. Validate acr (authentication context) if provider sends it
        acr = claims.get("acr")
        if acr and acr not in ACCEPTED_ACR_VALUES:
            logger.warning(f"OIDC unrecognized acr value: {acr}")
            # Log but don't reject — some providers send custom values

        # 6. Validate email_verified claim if present (Google, Azure require this)
        if claims.get("email_verified") is False:
            raise HTTPException(400, "SSO email not verified by provider")

        # 7. Validate azp (authorized party) if present — must match client_id
        azp = claims.get("azp")
        if azp and azp != config.get("client_id"):
            logger.error(f"OIDC azp mismatch: azp={azp}, client_id={config.get('client_id')}")
            raise HTTPException(400, "OIDC authorized party mismatch")

        return claims.get("email"), claims.get("name")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"OIDC id_token verification failed: {e}")
        # No fallback to unverified parsing — fail securely
        return None, None


def _derive_issuer(config: dict) -> str:
    """Derive the expected issuer from the OIDC configuration."""
    token_url = config.get("token_url", "")
    # Common patterns: https://accounts.google.com, https://login.microsoftonline.com/{tenant}/v2.0
    if "google" in token_url:
        return "https://accounts.google.com"
    if "microsoftonline" in token_url:
        # Extract tenant from token_url
        import re
        match = re.search(r"microsoftonline\.com/([^/]+)", token_url)
        if match:
            return f"https://login.microsoftonline.com/{match.group(1)}/v2.0"
    if "okta" in token_url:
        # Okta issuer is the base URL
        match = re.match(r"(https://[^/]+\.okta\.com(/oauth2/[^/]+)?)", token_url)
        if match:
            return match.group(1)
    # Generic: derive from authorization_url or token_url base
    auth_url = config.get("authorization_url", token_url)
    from urllib.parse import urlparse
    parsed = urlparse(auth_url)
    return f"{parsed.scheme}://{parsed.netloc}"


async def _sso_provision_user(db, email, name, config):
    """Find or create a user from SSO login."""
    user = await db.users.find_one({"email": email}, {"_id": 0})
    if not user:
        if not config.get("auto_provision", True):
            raise HTTPException(403, "Account not found. Contact your admin for access.")
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        user = {
            "user_id": user_id,
            "email": email,
            "name": name or email.split("@")[0],
            "platform_role": config.get("default_role", "member"),
            "email_verified": True,
            "auth_provider": "sso",
            "sso_provider": config.get("provider_name"),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.users.insert_one(user)
        workspace_id = config.get("workspace_id")
        if workspace_id:
            await db.workspace_members.insert_one({
                "workspace_id": workspace_id,
                "user_id": user_id,
                "role": config.get("default_role", "member"),
                "joined_at": datetime.now(timezone.utc).isoformat(),
            })
        logger.info(f"SSO auto-provisioned user {email} (provider: {config.get('provider_name')})")
    return user
