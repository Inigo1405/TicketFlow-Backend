import asyncio
import logging

from langchain_google_genai import GoogleGenerativeAIEmbeddings
from app.core.config import settings

logger = logging.getLogger(__name__)


def get_embeddings() -> GoogleGenerativeAIEmbeddings:
    return GoogleGenerativeAIEmbeddings(
        model=settings.GEMINI_EMBEDDING_MODEL,
        google_api_key=settings.GEMINI_API_KEY,
    )


async def embed_with_retry(text: str, max_retries: int = 4, base_delay: float = 5.0) -> list[float]:
    """Embed text with exponential backoff on 429 rate-limit errors."""
    embeddings = get_embeddings()
    for attempt in range(max_retries):
        try:
            return await embeddings.aembed_query(text)
        except Exception as exc:
            is_rate_limit = "429" in str(exc) or "Resource exhausted" in str(exc)
            if is_rate_limit and attempt < max_retries - 1:
                wait = base_delay * (2 ** attempt)  # 5s, 10s, 20s
                logger.warning(
                    "Embedding rate limited (429), reintentando en %.0fs (intento %d/%d)",
                    wait, attempt + 1, max_retries,
                )
                await asyncio.sleep(wait)
            else:
                raise
