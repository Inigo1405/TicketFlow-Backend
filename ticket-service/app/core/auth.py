"""
Verificación de token para ticket-service.
Decodificamos el JWT localmente (misma SECRET_KEY) en lugar de hacer una solicitud HTTP 
de ida y vuelta a auth-service en cada petición.
"""
from dataclasses import dataclass
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from app.core.config import settings

bearer_scheme = HTTPBearer()


@dataclass
class TokenUser:
    id: int
    role: str


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> TokenUser:
    token = credentials.credentials
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = payload.get("sub")
        role = payload.get("role")
        if not user_id or not role:
            raise ValueError("Payload incompleto")
        return TokenUser(id=int(user_id), role=role)
    except (JWTError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )


def require_agent_or_admin(current_user: TokenUser = Depends(get_current_user)) -> TokenUser:
    if current_user.role not in ("Admin", "Agente"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Se requiere rol Agente o Admin")
    return current_user
