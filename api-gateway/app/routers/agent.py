"""Proxy all /agent/* routes to agent-service."""
from fastapi import APIRouter, Request, Depends
from app.core.http_client import agent_client
from app.core.proxy import proxy_response
from app.core.auth import get_current_user, build_auth_headers, GatewayUser

router = APIRouter(prefix="/agent", tags=["agent"])


@router.post("/categorize/{ticket_id}")
async def categorize(ticket_id: int, current_user: GatewayUser = Depends(get_current_user)):
    upstream = await agent_client.post(
        f"/agent/categorize/{ticket_id}", headers=build_auth_headers(current_user)
    )
    return proxy_response(upstream)


@router.post("/interact/{ticket_id}")
async def interact(
    ticket_id: int,
    request: Request,
    current_user: GatewayUser = Depends(get_current_user),
):
    body = await request.json() if request.headers.get("content-length", "0") != "0" else {}
    upstream = await agent_client.post(
        f"/agent/interact/{ticket_id}",
        json=body,
        headers=build_auth_headers(current_user),
    )
    return proxy_response(upstream)


@router.post("/notes/{ticket_id}")
async def notes(ticket_id: int, current_user: GatewayUser = Depends(get_current_user)):
    upstream = await agent_client.post(
        f"/agent/notes/{ticket_id}", headers=build_auth_headers(current_user)
    )
    return proxy_response(upstream)


@router.get("/qa/audit")
async def qa_audit(current_user: GatewayUser = Depends(get_current_user)):
    upstream = await agent_client.get(
        "/agent/qa/audit", headers=build_auth_headers(current_user)
    )
    return proxy_response(upstream)


@router.get("/qa")
async def list_qa(current_user: GatewayUser = Depends(get_current_user)):
    upstream = await agent_client.get("/agent/qa", headers=build_auth_headers(current_user))
    return proxy_response(upstream)


@router.post("/qa")
async def create_qa(request: Request, current_user: GatewayUser = Depends(get_current_user)):
    body = await request.json()
    upstream = await agent_client.post(
        "/agent/qa", json=body, headers=build_auth_headers(current_user)
    )
    return proxy_response(upstream)


@router.get("/knowledge")
async def list_knowledge(current_user: GatewayUser = Depends(get_current_user)):
    upstream = await agent_client.get(
        "/agent/knowledge", headers=build_auth_headers(current_user)
    )
    return proxy_response(upstream)


@router.post("/knowledge")
async def create_knowledge(
    request: Request, current_user: GatewayUser = Depends(get_current_user)
):
    body = await request.json()
    upstream = await agent_client.post(
        "/agent/knowledge", json=body, headers=build_auth_headers(current_user)
    )
    return proxy_response(upstream)


@router.delete("/knowledge/{entry_id}")
async def delete_knowledge(
    entry_id: int, current_user: GatewayUser = Depends(get_current_user)
):
    upstream = await agent_client.delete(
        f"/agent/knowledge/{entry_id}", headers=build_auth_headers(current_user)
    )
    return proxy_response(upstream)


@router.get("/memory/{client_id}")
async def get_memory(client_id: int, current_user: GatewayUser = Depends(get_current_user)):
    upstream = await agent_client.get(
        f"/agent/memory/{client_id}", headers=build_auth_headers(current_user)
    )
    return proxy_response(upstream)


@router.delete("/memory/{client_id}")
async def clear_memory(client_id: int, current_user: GatewayUser = Depends(get_current_user)):
    upstream = await agent_client.delete(
        f"/agent/memory/{client_id}", headers=build_auth_headers(current_user)
    )
    return proxy_response(upstream)


@router.get("/admin/stats")
async def admin_stats(current_user: GatewayUser = Depends(get_current_user)):
    upstream = await agent_client.get("/agent/admin/stats", headers=build_auth_headers(current_user))
    return proxy_response(upstream)


@router.get("/admin/memory")
async def admin_memory(current_user: GatewayUser = Depends(get_current_user)):
    upstream = await agent_client.get("/agent/admin/memory", headers=build_auth_headers(current_user))
    return proxy_response(upstream)


@router.post("/admin/chat")
async def admin_chat(request: Request, current_user: GatewayUser = Depends(get_current_user)):
    body = await request.json()
    upstream = await agent_client.post(
        "/agent/admin/chat", json=body, headers=build_auth_headers(current_user)
    )
    return proxy_response(upstream)


@router.get("/health")
async def agent_health(current_user: GatewayUser = Depends(get_current_user)):
    upstream = await agent_client.get("/agent/health", headers=build_auth_headers(current_user))
    return proxy_response(upstream)
