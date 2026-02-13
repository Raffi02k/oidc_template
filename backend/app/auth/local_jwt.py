import os
import logging
from dotenv import load_dotenv
from passlib.context import CryptContext
from jose import jwt, JWTError
from datetime import datetime, timedelta
from typing import Optional, cast
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from ..db import get_db
from .. import models
from ..schemas import Token, TokenData

# Configuration
load_dotenv()
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")
_raw_expire_minutes = os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES")

if not SECRET_KEY or not ALGORITHM or not _raw_expire_minutes:
    raise RuntimeError("Missing required environment variables: SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES")

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