import os
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from .. import models, db
from ..auth import local_jwt
from ..schemas import Token, UserOut

router = APIRouter(tags=["local-auth"])

# Local routes
@router.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(db.get_db)):
    user = db.query(models.User).filter(models.User.username == form_data.username).first()
    if not user or not local_jwt.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if getattr(user, "is_disabled", False):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is disabled")
    
    access_token_expires = timedelta(minutes=local_jwt.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = local_jwt.create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me", response_model=UserOut)
async def read_users_me(current_user: models.User = Depends(local_jwt.get_current_user)):
    return current_user

# Setup script endpoint (dev only)
@router.post("/setup")
async def setup_users(db: Session = Depends(db.get_db)):
    if os.getenv("ENABLE_DEV_SETUP") != "true":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    # Create a test user if not exists
    if not db.query(models.User).filter(models.User.username == "raffi").first():
        hashed = local_jwt.get_password_hash("password123")
        user = models.User(username="raffi", hashed_password=hashed, role="Admin", auth_method="local", full_name="Raffi")
        db.add(user)
        db.commit()
    return {"message": "User created"}
