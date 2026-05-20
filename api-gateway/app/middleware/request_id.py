import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Garantiza que cada solicitud tenga un encabezado X-Request-ID.
    Si el cliente envía uno, se conserva; de lo contrario, se genera un UUID.
    El mismo ID se devuelve también en la respuesta.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-ID") or f"req-{uuid.uuid4().hex[:8]}"
        # Adjuntarlo al estado de la solicitud para que los routers puedan acceder a él.
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
