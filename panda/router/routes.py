from fastapi import APIRouter
from .models import UserLogin, Token

router = APIRouter()

# TODO change response model
@router.post("/login", response_model=Token)
async def create_plan(user: UserLogin):
    return {"msg": "Hello World"}