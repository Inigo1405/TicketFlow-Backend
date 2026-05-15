from typing import Optional, Literal
from pydantic import BaseModel, EmailStr, field_validator


RoleType = Literal["Admin", "Agente", "Cliente"]


class UserBase(BaseModel):
    name: str
    email: EmailStr
    role: RoleType = "Cliente"
    area: Optional[str] = None


class UserCreate(UserBase):
    password: str

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("La contraseña debe tener al menos 6 caracteres")
        return v


class UserUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[RoleType] = None
    area: Optional[str] = None
    password: Optional[str] = None


class UserOut(UserBase):
    id: int

    model_config = {"from_attributes": True}


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    token: str
    user: UserOut


class MeResponse(BaseModel):
    user: UserOut


class TokenPayload(BaseModel):
    sub: str  # user id as string
    role: str
