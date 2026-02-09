from datetime import datetime, timedelta
from typing import Optional, cast
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from app import models
import os
import time
import requests
import logging
from dotenv import load_dotenv
from app.database import get_db
from pydantic import BaseModel

# Configuration
load_dotenv()
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")
_raw_expire_minutes = os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES")

OIDC_ISSUER = os.getenv("OIDC_ISSUER")  # Comma-separated issuers allowed
OIDC_AUDIENCE = os.getenv("OIDC_AUDIENCE")  # API App ID URI or client id
OIDC_JWKS_URL = os.getenv("OIDC_JWKS_URL")  # Entra JWKS endpoint
OIDC_REQUIRED_SCOPES = os.getenv("OIDC_REQUIRED_SCOPES")
OIDC_JWKS_CACHE_TTL_SECONDS = os.getenv("OIDC_JWKS_CACHE_TTL_SECONDS", "3600")

if not SECRET_KEY or not ALGORITHM or not _raw_expire_minutes:
    raise RuntimeError("Missing required environment variables: SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES")

assert SECRET_KEY is not None
assert ALGORITHM is not None
assert _raw_expire_minutes is not None

SECRET_KEY = cast(str, SECRET_KEY)
ALGORITHM = cast(str, ALGORITHM)
_raw_expire_minutes = cast(str, _raw_expire_minutes)

try:
    ACCESS_TOKEN_EXPIRE_MINUTES = int(_raw_expire_minutes)
except ValueError as exc:
    raise RuntimeError("ACCESS_TOKEN_EXPIRE_MINUTES must be an integer") from exc

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
logger = logging.getLogger(__name__)

_jwks_cache: dict[str, object] = {}


def _parse_csv_env(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _get_jwks() -> dict:
    now = time.time()
    cached = _jwks_cache.get("jwks")
    expires_at = _jwks_cache.get("expires_at")
    if cached and isinstance(expires_at, (int, float)) and now < expires_at:
        return cast(dict, cached)

    try:
        response = requests.get(cast(str, OIDC_JWKS_URL), timeout=5)
        response.raise_for_status()
        jwks = response.json()
        ttl_seconds = int(OIDC_JWKS_CACHE_TTL_SECONDS)
        _jwks_cache["jwks"] = jwks
        _jwks_cache["expires_at"] = now + max(ttl_seconds, 60)
        return jwks
    except Exception as exc:
        if cached:
            logger.warning("JWKS fetch failed; using cached JWKS", exc_info=exc)
            return cast(dict, cached)
        raise

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        # Defaults to 30 minutes if not specified
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    
    # [IMPORTANT] The "sub" (subject) claim holds the unique identifier (username)
    # This is standard JWT practice.
    encoded_jwt = jwt.encode(
        to_encode,
        cast(str, SECRET_KEY),
        algorithm=cast(str, ALGORITHM),
    )
    return encoded_jwt

# [CRITICAL] Dependency Injection
# This function is used by FastAPI "Depends()" to protect routes.
# It automatically:
# 1. Extracts the Bearer token from the Authorization header
# 2. Decodes and validates the signature
# 3. Fetches the user from the database
def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token,
            cast(str, SECRET_KEY),
            algorithms=[cast(str, ALGORITHM)],
        )
        username: str | None = payload.get("sub")
        if not isinstance(username, str) or not username:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception
    
    user = db.query(models.User).filter(models.User.username == token_data.username).first()
    if user is None:
        raise credentials_exception
    if getattr(user, "is_disabled", False):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is disabled")
    return user


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
