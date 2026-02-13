import logging
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from .. import models, db
from ..auth import oidc
from ..schemas import UserOut

router = APIRouter(prefix="/oidc", tags=["oidc-auth"])
oidc_scheme = OAuth2PasswordBearer(tokenUrl="token")
logger = logging.getLogger(__name__)

def get_oidc_claims(token: str = Depends(oidc_scheme)):
    # OIDC access token -> validated claims
    try:
        return oidc.validate_oidc_token(token)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("OIDC token validation failed", exc_info=exc)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid OIDC token")


def require_oidc_access(claims: dict = Depends(get_oidc_claims)):
    # Require API scopes for protected endpoints
    oidc.require_oidc_scopes(claims, oidc.get_required_scopes())
    return claims


def get_current_user_oidc(claims: dict = Depends(get_oidc_claims), db: Session = Depends(db.get_db)):
    try:
        return oidc.get_or_create_oidc_user(db, claims)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("OIDC auth failed", exc_info=exc)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid OIDC token")

def require_oidc_role(claims: dict, required_role: str) -> None:
    roles = claims.get("roles") or claims.get("role")
    if isinstance(roles, str):
        roles = [roles]
    if not roles or required_role not in roles:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")

## OIDC routes
@router.get("/me/oidc", response_model=UserOut)
def oidc_test(current_user: models.User = Depends(get_current_user_oidc)):
    return current_user   

# Example of a protected route
@router.get("/users")
def list_users(
    current_user: models.User = Depends(get_current_user_oidc),
    _: dict = Depends(require_oidc_access),
):
    # Om du kommer hit är tokenen valid + user är länkad i DB
    return {
        "ok": True,
        "user_id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "auth_method": current_user.auth_method,
        "role": current_user.role,
        "oidc_id": getattr(current_user, "oidc_id", None),
    }