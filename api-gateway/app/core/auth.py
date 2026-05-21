from dataclasses import dataclass
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt

from app.core.config import settings
from app.core.redis_client import is_blacklisted

"""
Valida el JWT localmente (misma SECRET_KEY) sin consultar auth-service en cada petición, 
lo que lo hace más rápido y evita una dependencia circular.
Expone al usuario actual como una dataclass simple.
"""

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass
class GatewayUser:
    id: int
    role: str
    raw_token: str


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> GatewayUser:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Se requiere autenticación",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = credentials.credentials
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = payload.get("sub")
        role = payload.get("role")
        if not user_id or not role:
            raise ValueError("Payload incompleto")

        jti = payload.get("jti")
        if jti and await is_blacklisted(jti):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Sesión cerrada. Inicia sesión nuevamente.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return GatewayUser(id=int(user_id), role=role, raw_token=token)

    except (JWTError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )


def build_auth_headers(user: GatewayUser) -> dict:
    """Headers forwarded to every downstream service call."""
    return {
        "Authorization": f"Bearer {user.raw_token}",
        "Content-Type": "application/json",
        "X-User-ID": str(user.id),
        "X-User-Role": user.role,
    }
