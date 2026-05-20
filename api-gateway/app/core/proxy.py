"""
Utilidad de proxy ligera.
Toma una httpx.Response de un servicio downstream y la vuelve a lanzar 
como una FastAPI JSONResponse con el código de estado original.
"""
import json
from fastapi import HTTPException
from fastapi.responses import JSONResponse
import httpx


def proxy_response(upstream: httpx.Response) -> JSONResponse:
    """
    Convierte una respuesta de httpx en una FastAPI JSONResponse.
    Lanza una HTTPException para respuestas 4xx/5xx, de modo que FastAPI las renderice correctamente.
    """
    try:
        body = upstream.json()
    except Exception:
        body = {"detail": upstream.text or "Error desconocido en servicio upstream"}

    if upstream.status_code >= 400:
        raise HTTPException(status_code=upstream.status_code, detail=body.get("detail", body))

    return JSONResponse(content=body, status_code=upstream.status_code)
