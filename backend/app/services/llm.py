"""Provider-agnostic LLM client with automatic fallback.

Primary: OpenRouter (OpenAI-compatible). Fallback: Groq (or any other
OpenAI-compatible endpoint configured via the LLM_FALLBACK_* env vars).

If the primary call fails — rate limit, exhausted credits, timeout, 5xx — the
client transparently retries the same grounded prompt on the fallback provider.
If a stream already emitted tokens before failing, we do not silently switch
providers mid-answer (that would mix two models in one response); the error is
surfaced instead.
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
        self._clients: dict[str, Any] = {}
        self._lock = asyncio.Lock()
        self._semaphore = asyncio.Semaphore(settings.llm_max_concurrency)

    def _providers(self) -> list[dict[str, Any]]:
        providers: list[dict[str, Any]] = []
        key = (settings.llm_api_key or "").strip()
        if key and key != "replace-with-your-openrouter-key":
            providers.append(
                {
                    "name": settings.llm_provider,
                    "api_key": key,
                    "base_url": settings.llm_base_url,
                    "model": settings.llm_model,
                    "referer": settings.llm_http_referer,
                }
            )
        if settings.fallback_api_key:
            providers.append(
                {
                    "name": settings.llm_fallback_provider,
                    "api_key": settings.fallback_api_key,
                    "base_url": settings.llm_fallback_base_url,
                    "model": settings.llm_fallback_model,
                    "referer": None,
                }
            )
        return providers

    async def _client_for(self, provider: dict[str, Any]) -> Any:
        name = provider["name"]
        if name in self._clients:
            return self._clients[name]
        async with self._lock:
            if name not in self._clients:
                from openai import AsyncOpenAI

                self._clients[name] = AsyncOpenAI(
                    api_key=provider["api_key"],
                    base_url=provider["base_url"],
                    timeout=settings.llm_timeout_seconds,
                    max_retries=1,
                )
                logger.info(
                    "llm_provider_ready",
                    extra={"provider": name, "model": provider["model"]},
                )
        return self._clients[name]

    @staticmethod
    def _kwargs(provider: dict[str, Any], messages: list[dict[str, str]], stream: bool) -> dict[str, Any]:
        headers = (
            {"HTTP-Referer": provider["referer"], "X-Title": settings.llm_app_name}
            if provider.get("referer")
            else {}
        )
        return {
            "model": provider["model"],
            "messages": messages,
            "temperature": settings.llm_temperature,
            "max_tokens": settings.llm_max_tokens,
            "stream": stream,
            "extra_headers": headers,
        }

    async def acomplete(self, messages: list[dict[str, str]]) -> str:
        providers = self._providers()
        if not providers:
            raise LLMUnavailableError("No LLM provider is configured")
        for provider in providers:
            try:
                client = await self._client_for(provider)
                async with self._semaphore:
                    response = await client.chat.completions.create(
                        **self._kwargs(provider, messages, False)
                    )
                content = (response.choices[0].message.content or "").strip()
                if content:
                    return content
                logger.warning("llm_empty_response", extra={"provider": provider["name"]})
            except Exception as exc:
                logger.warning(
                    "llm_provider_failed",
                    extra={"provider": provider["name"], "error": str(exc)[:200]},
                )
        raise LLMUnavailableError("All configured LLM providers failed")

    async def astream(self, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        providers = self._providers()
        if not providers:
            raise LLMUnavailableError("No LLM provider is configured")
        for provider in providers:
            emitted = 0
            try:
                client = await self._client_for(provider)
                async with self._semaphore:
                    stream = await client.chat.completions.create(
                        **self._kwargs(provider, messages, True)
                    )
                    async for chunk in stream:
                        if not chunk.choices:
                            continue
                        delta = chunk.choices[0].delta.content
                        if delta:
                            emitted += 1
                            yield delta
                if emitted:
                    return
                logger.warning("llm_empty_stream", extra={"provider": provider["name"]})
            except Exception as exc:
                if emitted:
                    # Never switch providers after the UI has already received
                    # tokens from this one.
                    logger.warning(
                        "llm_stream_interrupted",
                        extra={"provider": provider["name"], "error": str(exc)[:200]},
                    )
                    raise LLMUnavailableError("The language model stream was interrupted") from exc
                logger.warning(
                    "llm_provider_failed",
                    extra={"provider": provider["name"], "error": str(exc)[:200]},
                )
        raise LLMUnavailableError("All configured LLM providers failed")


llm_client = LLMClient()
