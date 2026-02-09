from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app import models, auth
from app.database import get_db
from pydantic import BaseModel
import logging
import os

router = APIRouter()
oidc_scheme = OAuth2PasswordBearer(tokenUrl="token")
logger = logging.getLogger(__name__)

class UserOut(BaseModel):
    id: int
    username: str
    email: str | None = None
    full_name: str | None = None
    role: str
    auth_method: str

    class Config:
        from_ = True

def get_oidc_claims(token: str = Depends(oidc_scheme)):
    # OIDC access token -> validated claims
    try:
        return auth.validate_oidc_token(token)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("OIDC token validation failed", exc_info=exc)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid OIDC token")


def require_oidc_access(claims: dict = Depends(get_oidc_claims)):
    # Require API scopes for protected endpoints
    auth.require_oidc_scopes(claims, auth.get_required_scopes())
    return claims


def get_current_user_oidc(claims: dict = Depends(get_oidc_claims), db: Session = Depends(get_db)):
    try:
        return auth.get_or_create_oidc_user(db, claims)
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



## Local routes
@router.post("/token", response_model=auth.Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == form_data.username).first()
    if not user or not auth.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if getattr(user, "is_disabled", False):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is disabled")
    access_token_expires = auth.timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me", response_model=UserOut)
async def read_users_me(current_user: models.User = Depends(auth.get_current_user)):
    return current_user

# Setup script endpoint (dev only)
@router.post("/setup")
async def setup_users(db: Session = Depends(get_db)):
    if os.getenv("ENABLE_DEV_SETUP") != "true":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    # Create a test user if not exists
    if not db.query(models.User).filter(models.User.username == "raffi").first():
        hashed = auth.get_password_hash("password123")
        user = models.User(username="raffi", hashed_password=hashed, role="Admin", auth_method="local", full_name="Raffi")
        db.add(user)
        db.commit()
    return {"message": "User created"}
