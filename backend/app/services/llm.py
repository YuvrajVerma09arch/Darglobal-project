"""Provider-agnostic LLM client (OpenAI-compatible chat completions API).

OpenRouter is the default base URL, but any OpenAI / Gemini / Anthropic-compatible
endpoint (or a local model server exposing the same API) works by changing env vars.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Any

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class LLMUnavailableError(RuntimeError):
    pass


class LLMClient:
    def __init__(self) -> None:
        self._client: Any = None
        self._lock = asyncio.Lock()
        self._semaphore = asyncio.Semaphore(settings.llm_max_concurrency)

    async def _ensure(self) -> Any:
        if not settings.is_llm_configured:
            raise LLMUnavailableError("LLM_API_KEY is not configured")
        if self._client is None:
            async with self._lock:
                if self._client is None:
                    from openai import AsyncOpenAI

                    self._client = AsyncOpenAI(
                        api_key=settings.llm_api_key,
                        base_url=settings.llm_base_url,
                        timeout=settings.llm_timeout_seconds,
                        max_retries=1,
                    )
                    logger.info(
                        "llm_client_ready",
                        extra={"provider": settings.llm_provider, "model": settings.llm_model},
                    )
        return self._client

    def _headers(self) -> dict[str, str]:
        return {
            "HTTP-Referer": settings.llm_http_referer,
            "X-Title": settings.llm_app_name,
        }

    def _kwargs(self, messages: list[dict[str, str]], stream: bool) -> dict[str, Any]:
        return {
            "model": settings.llm_model,
            "messages": messages,
            "temperature": settings.llm_temperature,
            "max_tokens": settings.llm_max_tokens,
            "stream": stream,
            "extra_headers": self._headers(),
        }

    async def acomplete(self, messages: list[dict[str, str]]) -> str:
        client = await self._ensure()
        async with self._semaphore:
            try:
                response = await client.chat.completions.create(**self._kwargs(messages, False))
            except Exception as exc:
                logger.exception("llm_completion_failed", extra={"error": str(exc)[:200]})
                raise LLMUnavailableError("The language model could not be reached") from exc
        content = response.choices[0].message.content or ""
        return content.strip()

    async def astream(self, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        client = await self._ensure()
        async with self._semaphore:
            try:
                stream = await client.chat.completions.create(**self._kwargs(messages, True))
                async for chunk in stream:
                    if not chunk.choices:
                        continue
                    delta = chunk.choices[0].delta.content
                    if delta:
                        yield delta
            except Exception as exc:
                logger.exception("llm_stream_failed", extra={"error": str(exc)[:200]})
                raise LLMUnavailableError("The language model could not be reached") from exc


llm_client = LLMClient()
