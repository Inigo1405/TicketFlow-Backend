from fastapi import APIRouter, Depends
from httpx import ConnectError, HTTPStatusError

from app.core.http_client import notification_client
from app.core.proxy import proxy_response
from app.core.auth import get_current_user, build_auth_headers, GatewayUser

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("/")
async def list_notifications(current_user: GatewayUser = Depends(get_current_user)):
    try:
        upstream = await notification_client.get(
            "/notifications/", headers=build_auth_headers(current_user)
        )
        return proxy_response(upstream)
    except (ConnectError, Exception):
        return []


@router.patch("/{notif_id}/read")
async def mark_read(notif_id: int, current_user: GatewayUser = Depends(get_current_user)):
    try:
        upstream = await notification_client.patch(
            f"/notifications/{notif_id}/read", headers=build_auth_headers(current_user)
        )
        return proxy_response(upstream)
    except (ConnectError, Exception):
        return {"ok": True}


@router.patch("/mark-all-read")
async def mark_all_read(current_user: GatewayUser = Depends(get_current_user)):
    try:
        upstream = await notification_client.patch(
            "/notifications/mark-all-read", headers=build_auth_headers(current_user)
        )
        return proxy_response(upstream)
    except (ConnectError, Exception):
        return {"ok": True}


@router.delete("/{notif_id}")
async def delete_notification(notif_id: int, current_user: GatewayUser = Depends(get_current_user)):
    try:
        upstream = await notification_client.delete(
            f"/notifications/{notif_id}", headers=build_auth_headers(current_user)
        )
        return proxy_response(upstream)
    except (ConnectError, Exception):
        return {"ok": True}
