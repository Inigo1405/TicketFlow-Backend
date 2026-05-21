"""
Qdrant async client — singleton with collection auto-creation.
Embedding dimension for gemini-embedding-001: 3072.
"""
from qdrant_client import AsyncQdrantClient
from qdrant_client.http.models import Distance, VectorParams
from app.core.config import settings

EMBEDDING_DIM = 3072

_client: AsyncQdrantClient | None = None


async def get_vector_client() -> AsyncQdrantClient:
    global _client
    if _client is None:
        _client = AsyncQdrantClient(url=settings.QDRANT_URL)
    return _client


async def init_collections() -> None:
    client = await get_vector_client()
    collections_needed = [
        settings.COLLECTION_KNOWLEDGE,
        settings.COLLECTION_QA,
        settings.COLLECTION_CLIENTS,
    ]
    existing_resp = await client.get_collections()
    existing = {c.name for c in existing_resp.collections}
    for name in collections_needed:
        if name in existing:
            info = await client.get_collection(name)
            current_dim = info.config.params.vectors.size
            if current_dim != EMBEDDING_DIM:
                await client.delete_collection(name)
                existing.discard(name)
        if name not in existing:
            await client.create_collection(
                collection_name=name,
                vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE),
            )


async def close_vector_client() -> None:
    global _client
    if _client is not None:
        await _client.close()
        _client = None
