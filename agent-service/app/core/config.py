from pydantic_settings import BaseSettings, SettingsConfigDict
from jose import jwt
from datetime import datetime, timezone, timedelta


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/agent_db"
    SECRET_KEY: str = "change-me-in-production-use-a-long-random-secret"
    ALGORITHM: str = "HS256"

    # Gemini
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-3.1-flash-lite"
    # Gemini 2.x model for features that use tool calling inside LangGraph.
    # Gemini 3 requires thought_signatures to be preserved across ReAct steps,
    # which langchain-google-genai <3.x does not yet do automatically.
    # gemini-2.0-flash has no thinking mode, so no signatures needed.
    GEMINI_ADMIN_MODEL: str = "gemini-3.1-flash-lite"
    GEMINI_EMBEDDING_MODEL: str = "gemini-embedding-001"

    # Qdrant
    QDRANT_URL: str = "http://qdrant:6333"

    # Internal service URLs (Docker network)
    TICKET_SERVICE_URL: str = "http://ticket-service:8002"

    # Qdrant collection names
    COLLECTION_KNOWLEDGE: str = "company_knowledge"
    COLLECTION_QA: str = "qa_entries"
    COLLECTION_CLIENTS: str = "client_profiles"

    # Web search
    DUCKDUCKGO_MAX_RESULTS: int = 5

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()


def create_service_token() -> str:
    """Generate a long-lived internal service JWT for service-to-service calls."""
    payload = {
        "sub": "0",
        "role": "Agente",
        "name": "TICBot",
        "exp": datetime.now(timezone.utc) + timedelta(days=365),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
