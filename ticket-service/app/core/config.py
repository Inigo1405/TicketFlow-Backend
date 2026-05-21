from datetime import datetime, timezone, timedelta

from jose import jwt
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/tickets_db"
    SECRET_KEY: str = "change-me-in-production-use-a-long-random-secret"
    ALGORITHM: str = "HS256"
    SLA_HOURS: int = 24  # Tiempo en horas para que un ticket se considere con SLA incumplido
    AGENT_SERVICE_URL: str = "http://agent-service:8004"
    RABBITMQ_URL: str = "amqp://guest:guest@rabbitmq:5672/"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()


def create_service_token() -> str:
    """Genera un JWT de servicio con rol Agente para llamadas internas."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": "0",
        "role": "Agente",
        "name": "TICBot",
        "iat": now,
        "exp": now + timedelta(days=365),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
