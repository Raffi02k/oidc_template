import logging
import os
import time
import uuid
from typing import Optional, cast
import requests
from dotenv import load_dotenv
from fastapi import HTTPException, status
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from .. import models
from .local_jwt import get_password_hash
from ..models import User, AuthMethod

logger = logging.getLogger(__name__)

# Configuration
load_dotenv()
OIDC_ISSUER = os.getenv("OIDC_ISSUER")  # Comma-separated issuers allowed
OIDC_AUDIENCE = os.getenv("OIDC_AUDIENCE")  # API App ID URI or client id
OIDC_JWKS_URL = os.getenv("OIDC_JWKS_URL")  # Entra JWKS endpoint
OIDC_REQUIRED_SCOPES = os.getenv("OIDC_REQUIRED_SCOPES")
OIDC_JWKS_CACHE_TTL_SECONDS = os.getenv("OIDC_JWKS_CACHE_TTL_SECONDS", "3600")

_jwks_cache: dict[str, object] = {}

# Helper functions for OIDC authentication 
def _parse_csv_env(value: str | None) -> list[str]:
    """Parse a comma-separated string from an environment variable into a list of strings."""
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]

# Get JWKS from OIDC provider
def _get_jwks() -> dict:
    """Get the JSON Web Key Set (JWKS) from the OIDC provider."""
    now = time.time()
    cached = _jwks_cache.get("jwks")
    expires_at = _jwks_cache.get("expires_at")
    if cached and isinstance(expires_at, (int, float)) and now < expires_at:
        return cast(dict, cached)
    # Fetch JWKS from OIDC provider and cache it for the configured TTL
    try:
        response = requests.get(cast(str, OIDC_JWKS_URL), timeout=5)
        response.raise_for_status()
        jwks = response.json()
        ttl_seconds = int(OIDC_JWKS_CACHE_TTL_SECONDS)
        _jwks_cache["jwks"] = jwks
        _jwks_cache["expires_at"] = now + max(ttl_seconds, 60)
        return jwks
    # If JWKS fetch fails, use cached JWKS if available
    except Exception as exc:
        if cached:
            logger.warning("JWKS fetch failed; using cached JWKS", exc_info=exc)
            return cast(dict, cached)
        raise

def validate_oidc_token(token: str) -> dict:
    # 0) Måste ha config
    if not (OIDC_ISSUER and OIDC_AUDIENCE and OIDC_JWKS_URL):
        raise RuntimeError("Missing OIDC config")

    # 1) Läs header för att hitta kid (vilken nyckel som används)
    header = jwt.get_unverified_header(token)
    kid = header.get("kid")
    if not kid:
        raise JWTError("Missing kid")

    # 2) Hämta JWKS (publika nycklar) från Entra
    jwks = _get_jwks()

    # 3) Leta upp rätt key baserat på kid
    matched_key = None
    for jwk in jwks.get("keys", []):
        if jwk.get("kid") == kid:
            matched_key = jwk
            break
    if not matched_key:
        raise JWTError("No matching key found")

    # 4) Validate access token for this API
    claims = jwt.decode(
        token,
        matched_key,
        algorithms=["RS256"],
        audience=cast(str, OIDC_AUDIENCE),
        options={"verify_iss": False},
    )

    allowed_issuers = _parse_csv_env(OIDC_ISSUER)
    if allowed_issuers:
        token_issuer = claims.get("iss")
        if token_issuer not in allowed_issuers:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid issuer")

    return claims

# Minimal validation of OIDC token
def validate_oidc_token_minimal(token: str) -> dict:
    if token.count(".") != 2:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not a JWT")

    claims = jwt.get_unverified_claims(token)

    if "exp" not in claims:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing exp")

    return claims


def first_non_empty_string(claims: dict, possible_keys: list[str]) -> str | None:
    """
    Returnerar första icke-tomma strängen i `claims` för någon av nycklarna i `possible_keys`.
    Trim:ar whitespace. Returnerar None om inget matchar.
    """
    for key in possible_keys:
        value = claims.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def get_or_create_oidc_user(db: Session, token_claims: dict) -> "models.User":
    # 1) Stabilt OIDC-id: oid (Entra Object ID), annars sub
    oidc_object_id = first_non_empty_string(token_claims, ["oid", "sub"])
    if not oidc_object_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token missing oid/sub")

    # Om man vill kunna stödja fler tenants i framtiden
    tenant_id = first_non_empty_string(token_claims, ["tid"])

    # 2) Finns redan användare länkad via oidc_id?
    existing_user_by_oidc = (
        db.query(models.User)
        .filter(models.User.oidc_id == oidc_object_id)
        .first()
    )
    if existing_user_by_oidc:
        if getattr(existing_user_by_oidc, "is_disabled", False):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is disabled")
        return existing_user_by_oidc

    # 3) Försök matcha/länka via email
    email_address = first_non_empty_string(token_claims, ["preferred_username", "email", "upn"])
    if email_address:
        email_address = email_address.strip().lower()

        existing_user_by_email = (
            db.query(models.User)
            .filter(models.User.email == email_address)
            .first()
        )
        if existing_user_by_email is not None:
            if getattr(existing_user_by_email, "is_disabled", False):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is disabled")
            # Skydd: samma email får inte redan vara länkad till en annan OIDC-id
            existing_oidc_id = cast(Optional[str], existing_user_by_email.oidc_id)
            if existing_oidc_id is not None and existing_oidc_id != oidc_object_id:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Email already linked to another OIDC user",
                )
            # Länka kontot
            setattr(existing_user_by_email, "oidc_id", oidc_object_id)
            setattr(existing_user_by_email, "auth_method", models.AuthMethod.OIDC)
            setattr(existing_user_by_email, "oidc_tenant_id", tenant_id)
            db.commit()
            db.refresh(existing_user_by_email)
            return existing_user_by_email

    # 4) Skapa ny användare
    display_name = first_non_empty_string(token_claims, ["name"])

    # Om email saknas: använd oid som username (fallback)
    username = email_address or oidc_object_id

    created_user = models.User(
        username=username,
        email=email_address,
        full_name=display_name, 
        role="User",
        auth_method="oidc",
        oidc_id=oidc_object_id,
        oidc_tenant_id=tenant_id,
    )

    db.add(created_user)
    db.commit()
    db.refresh(created_user)
    return created_user

def require_oidc_scopes(claims: dict, required_scopes: list[str] | None) -> None:
    scopes = claims.get("scp") or ""
    scope_list = scopes.split(" ") if isinstance(scopes, str) else []

    if required_scopes and not any(scope in scope_list for scope in required_scopes):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Missing required scope")


def get_required_scopes() -> list[str]:
    return _parse_csv_env(OIDC_REQUIRED_SCOPES)
