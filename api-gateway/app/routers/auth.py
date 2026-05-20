from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse

from app.core.http_client import auth_client
from app.core.proxy import proxy_response
from app.core.auth import get_current_user, GatewayUser

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login")
async def login(request: Request):
    """Proxy POST /auth/login → auth-service (no token required)."""
    body = await request.json()
    upstream = await auth_client.post(
        "/auth/login",
        json=body,
        headers={"Content-Type": "application/json"},
    )
    return proxy_response(upstream)


@router.get("/me")
async def me(current_user: GatewayUser = Depends(get_current_user)):
    """Proxy GET /auth/me → auth-service (token required)."""
    upstream = await auth_client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {current_user.raw_token}"},
    )
    return proxy_response(upstream)
