from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel

from ..auth import (
    create_access_token,
    create_refresh_token,
    decode_token,
    require_auth,
    require_refresh_cookie,
    verify_password,
)
from ..config import settings

router = APIRouter(prefix="/auth", tags=["auth"])

COOKIE_NAME = "refresh_token"
COOKIE_OPTS = dict(
    httponly=True,
    secure=True,
    samesite="lax",
    max_age=settings.refresh_token_expire_days * 86400,
    path="/api/v1/auth",
)


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, response: Response):
    if body.username != settings.admin_username:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    if not settings.admin_password_hash:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Auth not configured")

    if not verify_password(body.password, settings.admin_password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    access_token = create_access_token(body.username)
    refresh_token = create_refresh_token(body.username)

    response.set_cookie(COOKIE_NAME, refresh_token, **COOKIE_OPTS)
    return TokenResponse(access_token=access_token)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(username: str = Depends(require_refresh_cookie)):
    access_token = create_access_token(username)
    return TokenResponse(access_token=access_token)


@router.post("/logout")
async def logout(response: Response, _: str = Depends(require_auth)):
    response.delete_cookie(COOKIE_NAME, path="/api/v1/auth")
    return {"detail": "Logged out"}


@router.get("/me")
async def me(username: str = Depends(require_auth)):
    return {"username": username}
