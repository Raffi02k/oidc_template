from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from .. import models, db
from ..auth import get_current_user_hybrid
from ..schemas import UserOut

router = APIRouter(tags=["api"])


@router.get("/users", response_model=UserOut)
def get_current_user_info(
    current_user: models.User = Depends(get_current_user_hybrid)
):
    """
    Returnerar information om den inloggade användaren.
    Använder hybrid-autentisering (fungerar för både lokal JWT och OIDC).
    """
    return current_user

@router.get("/status")
async def get_status():
    return {"status": "ok", "module": "api"}
