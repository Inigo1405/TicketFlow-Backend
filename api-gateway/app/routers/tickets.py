from fastapi import APIRouter, Request, Depends

from app.core.http_client import ticket_client
from app.core.proxy import proxy_response
from app.core.auth import get_current_user, build_auth_headers, GatewayUser

router = APIRouter(prefix="/tickets", tags=["tickets"])


@router.get("/mine")
async def my_tickets(current_user: GatewayUser = Depends(get_current_user)):
    upstream = await ticket_client.get("/tickets/mine", headers=build_auth_headers(current_user))
    return proxy_response(upstream)


@router.get("/")
async def list_tickets(current_user: GatewayUser = Depends(get_current_user)):
    upstream = await ticket_client.get("/tickets/", headers=build_auth_headers(current_user))
    return proxy_response(upstream)


@router.get("/{ticket_id}")
async def get_ticket(ticket_id: int, current_user: GatewayUser = Depends(get_current_user)):
    upstream = await ticket_client.get(
        f"/tickets/{ticket_id}", headers=build_auth_headers(current_user)
    )
    return proxy_response(upstream)


@router.post("/")
async def create_ticket(request: Request, current_user: GatewayUser = Depends(get_current_user)):
    body = await request.json()
    upstream = await ticket_client.post(
        "/tickets/", json=body, headers=build_auth_headers(current_user)
    )
    return proxy_response(upstream)


@router.patch("/{ticket_id}")
async def update_ticket(
    ticket_id: int,
    request: Request,
    current_user: GatewayUser = Depends(get_current_user),
):
    body = await request.json()
    upstream = await ticket_client.patch(
        f"/tickets/{ticket_id}", json=body, headers=build_auth_headers(current_user)
    )
    return proxy_response(upstream)


@router.patch("/{ticket_id}/close")
async def close_ticket(ticket_id: int, current_user: GatewayUser = Depends(get_current_user)):
    upstream = await ticket_client.patch(
        f"/tickets/{ticket_id}/close", headers=build_auth_headers(current_user)
    )
    return proxy_response(upstream)


@router.patch("/{ticket_id}/resolve")
async def resolve_ticket(ticket_id: int, current_user: GatewayUser = Depends(get_current_user)):
    upstream = await ticket_client.patch(
        f"/tickets/{ticket_id}/resolve", headers=build_auth_headers(current_user)
    )
    return proxy_response(upstream)


@router.patch("/{ticket_id}/pending")
async def set_ticket_pending(ticket_id: int, current_user: GatewayUser = Depends(get_current_user)):
    upstream = await ticket_client.patch(
        f"/tickets/{ticket_id}/pending", headers=build_auth_headers(current_user)
    )
    return proxy_response(upstream)


@router.post("/{ticket_id}/replies")
async def add_reply(
    ticket_id: int,
    request: Request,
    current_user: GatewayUser = Depends(get_current_user),
):
    body = await request.json()
    upstream = await ticket_client.post(
        f"/tickets/{ticket_id}/replies",
        json=body,
        headers=build_auth_headers(current_user),
    )
    return proxy_response(upstream)
