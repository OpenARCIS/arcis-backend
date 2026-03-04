import secrets
from fastapi import APIRouter, HTTPException, status
from arcis.config import Config
from arcis.models.auth import LoginRequest, LoginResponse

auth_router = APIRouter(tags=["auth"])

@auth_router.post("/login", response_model=LoginResponse)
async def login(credentials: LoginRequest):
    if not Config.AUTH_USERNAME or not Config.AUTH_PASSWORD:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication not configured on server"
        )
        
    if credentials.username == Config.AUTH_USERNAME and credentials.password == Config.AUTH_PASSWORD:
        # Since this is a simple setup, we return a generated token.
        token = secrets.token_hex(16)
        return LoginResponse(status="success", token=token)
    
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid credentials"
    )
