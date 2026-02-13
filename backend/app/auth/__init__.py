"""
Auth module - handles local JWT, OIDC, and hybrid authentication
"""
from typing import cast
from jose import JWTError, jwt as jose_jwt
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session
from .. import models, db
from .local_jwt import (
    verify_password,
    get_password_hash,
    create_access_token,
    get_current_user,
    oauth2_scheme,
)
from .oidc import (
    validate_oidc_token,
    validate_oidc_token_minimal,
    get_or_create_oidc_user,
    require_oidc_scopes,
    get_required_scopes,
)
from ..schemas import Token, TokenData

# ===== HYBRID AUTH =====
def get_current_user_hybrid(
    token: str = Depends(oauth2_scheme),
    db_session: Session = Depends(db.get_db),
) -> models.User:
    """
    Hybrid authentication dependency.
    Accepts both local JWT and OIDC access tokens.
    
    Flow:
        1. Try to validate as local JWT (SECRET_KEY, HS256)
        2. If fails, try to validate as OIDC (JWKS, RS256, scopes)
        3. If both fail, raise 401
    """
    # ===== TRY LOCAL JWT FIRST =====
    # Why first? Because in development, most requests use local JWT
    # and it's faster to validate (no JWKS fetch)
    try:
        # 1. Try local JWT first (fast path)
        from .local_jwt import SECRET_KEY, ALGORITHM

        # Decode and validate local JWT
        payload = jose_jwt.decode(
            token,
            cast(str, SECRET_KEY),
            algorithms=[cast(str, ALGORITHM)],
        )
        
        # Extract username from 'sub' claim
        username = payload.get("sub")
        if isinstance(username, str) and username:
            # Lookup user in database
            user = db_session.query(models.User).filter(models.User.username == username).first()

            # Check if user exists and is not disabled
            if user and not getattr(user, "is_disabled", False):
                return user
    except JWTError:
        # Local JWT validation failed, try OIDC
        pass
    except Exception:
        # Unexpected error (DB issue, etc) - also try OIDC as fallback
        pass
    
    # ===== TRY OIDC TOKEN =====
    # 2. If fails, try OIDC (slower, needs JWKS fetch)
    try:
        # Validate OIDC token (includes signature and claims check)
        claims = validate_oidc_token(token)
        
        # Check required scopes
        required_scopes = get_required_scopes()
        if required_scopes:
            require_oidc_scopes(claims, required_scopes)

        # Get or create user from OIDC claims
        user = get_or_create_oidc_user(db_session, claims)
        return user
    except HTTPException:
        # Re-raise explicit HTTP exceptions (like 403 Forbidden)
        raise
    except Exception:
        # OIDC validation failed
        pass
    
    # ===== BOTH FAILED =====
    # 3. If both fail, raise 401
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials (tried both local JWT and OIDC)",
        headers={"WWW-Authenticate": "Bearer"},
    )

__all__ = [
    # Local JWT
    "Token",
    "TokenData",
    "verify_password",
    "get_password_hash",
    "create_access_token",
    "get_current_user",
    
    # OIDC
    "validate_oidc_token",
    "validate_oidc_token_minimal",
    "get_or_create_oidc_user",
    "require_oidc_scopes",
    "get_required_scopes",
    
    # Hybrid
    "get_current_user_hybrid",
]