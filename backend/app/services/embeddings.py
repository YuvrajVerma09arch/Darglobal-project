"""Configurable embedding provider.

Default: local fastembed BGE-small (384 dims, no API key, no data sent to a vendor).
Optional: OpenAI-compatible embeddings via `EMBEDDING_PROVIDER=openai`.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# BGE models were trained with this instruction prefix for short queries.
_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


class EmbeddingError(RuntimeError):
    pass


class EmbeddingService:
    def __init__(self) -> None:
        self._model: Any = None
        self._client: Any = None
        self._lock = asyncio.Lock()
        self._semaphore = asyncio.Semaphore(4)

    @property
    def dim(self) -> int:
        return settings.embedding_dim

    async def _ensure_model(self) -> None:
        if self._model is not None or self._client is not None:
            return
        async with self._lock:
            if self._model is not None or self._client is not None:
                return
            if settings.embedding_provider == "local":
                try:
                    from fastembed import TextEmbedding
                except ImportError as exc:  # pragma: no cover
                    raise EmbeddingError("fastembed is not installed") from exc
                logger.info("loading_local_embedding_model", extra={"model": settings.embedding_model})
                self._model = await asyncio.to_thread(
                    TextEmbedding, model_name=settings.embedding_model
                )
            else:
                from openai import AsyncOpenAI

                if not settings.llm_api_key:
                    raise EmbeddingError("LLM_API_KEY is required for OpenAI embeddings")
                self._client = AsyncOpenAI(
                    api_key=settings.llm_api_key, base_url=settings.llm_base_url
                )
            logger.info("embedding_provider_ready", extra={"provider": settings.embedding_provider})

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        await self._ensure_model()
        async with self._semaphore:
            try:
                if self._model is not None:
                    vectors = await asyncio.to_thread(
                        lambda: [v.tolist() for v in self._model.embed(texts)]
                    )
                else:
                    response = await self._client.embeddings.create(
                        model=settings.openai_embedding_model, input=texts
                    )
                    vectors = [item.embedding for item in response.data]
            except Exception as exc:
                logger.exception("embedding_failed", extra={"error": str(exc)[:200]})
                raise EmbeddingError("Could not compute embeddings") from exc
        if vectors and len(vectors[0]) != self.dim:
            raise EmbeddingError(
                f"Embedding dimension mismatch: got {len(vectors[0])}, expected {self.dim}"
            )
        return [[float(v) for v in vector] for vector in vectors]

    async def embed_query(self, query: str) -> list[float]:
        use_prefix = settings.embedding_provider == "local" and settings.embedding_model.startswith(
            "BAAI/bge"
        )
        text = f"{_QUERY_PREFIX}{query}" if use_prefix else query
        vectors = await self.embed_documents([text])
        return vectors[0]


embedding_service = EmbeddingService()
