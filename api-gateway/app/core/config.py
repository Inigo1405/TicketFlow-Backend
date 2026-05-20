from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    AUTH_SERVICE_URL: str = "http://auth-service:8001"
    TICKET_SERVICE_URL: str = "http://ticket-service:8002"
    NOTIFICATION_SERVICE_URL: str = "http://notification-service:8003"
    AGENT_SERVICE_URL: str = "http://agent-service:8004"
    SECRET_KEY: str = "change-me-in-production-use-a-long-random-secret"
    ALGORITHM: str = "HS256"
    REDIS_URL: str = "redis://redis:6379"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
