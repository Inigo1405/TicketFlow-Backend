from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/users_db"
    SECRET_KEY: str = "change-me-in-production-use-a-long-random-secret"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    REDIS_URL: str = "redis://localhost:6379"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
