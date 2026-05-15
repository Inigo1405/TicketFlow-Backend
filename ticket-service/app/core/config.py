from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/tickets_db"
    SECRET_KEY: str = "change-me-in-production-use-a-long-random-secret"
    ALGORITHM: str = "HS256"
    SLA_HOURS: int = 24  # Tiempo en horas para que un ticket se considere con SLA incumplido

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
