"""RAG orchestration: retrieval → grounded generation → validated answer."""

from __future__ import annotations

import json
import logging
import random
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import SessionLocal
from app.models import Conversation
from app.prompts.system import SYSTEM_PROMPT, build_context, build_messages
from app.schemas import ChatRequest, ChatResponse, Citation, SourceFilter
from app.services.embeddings import embedding_service
from app.services.llm import LLMUnavailableError, llm_client
from app.services.retrieval import HybridRetriever, RetrievedItem

logger = logging.getLogger(__name__)
settings = get_settings()

NO_EVIDENCE_ANSWER = (
    "I don't have that information in the available DarGlobal/Wasalt data. "
    "I can help with projects, locations, property types, prices, and amenities "
    "that appear in the collected sources."
)
_CITATION_MARKER = re.compile(r"\[(\d+)\]")
# Only accept opaque server-generated IDs. Rejecting user-chosen IDs prevents a
# guessed/shared value from reading or overwriting another conversation.
_OPAQUE_CONVERSATION_ID = re.compile(r"^[0-9a-f]{20}$")


def sanitise_markdown(text: str) -> str:
    """Force plain text even when the model ignores the prompt's no-markdown rule."""
    # Markdown links -> label only. URLs are already listed as clickable citations.
    text = re.sub(r"\[([^\]\n]+)\]\((https?://[^)\s]+)\)", r"\1", text)
    # Bold/italic markers, inline code, heading hashes. Bullets use "- " and stay.
    text = text.replace("**", "").replace("__", "").replace("`", "")
    text = re.sub(r"^\s*#{1,6}\s+", "", text, flags=re.M)
    return text


def validate_answer(answer: str, citation_count: int) -> tuple[str, list[str]]:
    """Strip invalid citations and Markdown; never emit unverifiable links."""
    warnings: list[str] = []
    answer = sanitise_markdown(answer)
    if citation_count == 0:
        cleaned = _CITATION_MARKER.sub("", answer)
        if cleaned != answer:
            warnings.append("removed_unverifiable_citations")
        return cleaned.strip(), warnings

    def replace(match: re.Match[str]) -> str:
        number = int(match.group(1))
        if 1 <= number <= citation_count:
            return match.group(0)
        warnings.append("removed_out_of_range_citation")
        return ""

    return _CITATION_MARKER.sub(replace, answer).strip(), warnings


class RAGService:
    def __init__(self) -> None:
        self.retriever = HybridRetriever(rrf_k=settings.rrf_k)

    async def _retrieve(
        self,
        session: AsyncSession,
        message: str,
        source_filter: SourceFilter,
        explicit_filters: Any,
    ) -> tuple[list[RetrievedItem], str, dict[str, Any], str | None]:
        vector = await embedding_service.embed_query(message)
        return await self.retriever.search(
            session,
            query=message,
            query_vector=vector,
            source_filter=source_filter,
            explicit_filters=explicit_filters,
            top_k=settings.retrieval_top_k,
            candidate_k=settings.retrieval_candidate_k,
        )

    @staticmethod
    async def _history(session: AsyncSession, conversation_id: str | None) -> tuple[str, list[dict]]:
        # Opportunistic TTL cleanup keeps the table bounded.
        if random.random() < 0.05:
            cutoff = datetime.now(timezone.utc) - timedelta(days=7)
            await session.execute(
                delete(Conversation).where(Conversation.created_at < cutoff)
            )
        if not conversation_id or not _OPAQUE_CONVERSATION_ID.fullmatch(conversation_id):
            return uuid.uuid4().hex[:20], []
        row = await session.get(Conversation, conversation_id)
        if row is None:
            return uuid.uuid4().hex[:20], []
        return conversation_id, (row.messages if row else [])

    @staticmethod
    async def _persist(
        session: AsyncSession,
        conversation_id: str,
        history: list[dict],
        question: str,
        answer: str,
    ) -> None:
        row = await session.get(Conversation, conversation_id)
        if row is None:
            row = Conversation(id=conversation_id, messages=[])
            session.add(row)
        messages = list(history) + [
            {"role": "user", "content": question},
            {"role": "assistant", "content": answer},
        ]
        limit = settings.max_conversation_turns * 2
        row.messages = messages[-limit:] if limit > 0 else messages
        row.updated_at = datetime.now(timezone.utc)
        await session.commit()

    @staticmethod
    def _data_as_of(items: list[RetrievedItem]) -> datetime | None:
        stamps = [item.scraped_at for item in items if item.scraped_at is not None]
        return max(stamps) if stamps else None

    async def chat(self, session: AsyncSession, request: ChatRequest) -> ChatResponse:
        items, query_type, applied, relaxation_note = await self._retrieve(
            session, request.message, request.source_filter, request.filters
        )
        conversation_id, history = await self._history(session, request.conversation_id)
        citations = [item.as_citation() for item in items]
        warnings: list[str] = []
        if relaxation_note:
            warnings.append("filters_relaxed")

        if not citations:
            answer = NO_EVIDENCE_ANSWER
            warnings.append("no_retrieved_evidence")
        elif not settings.is_llm_configured:
            answer = (
                "Retrieval succeeded, but answer generation is unavailable because "
                "LLM_API_KEY is not configured on the server."
            )
            warnings.append("llm_not_configured")
        else:
            context = build_context(citations, settings.context_max_chars)
            if relaxation_note:
                context = (
                    f"RETRIEVAL NOTE: {relaxation_note} "
                    "Tell the user their exact filters matched no records and that these are alternatives.\n\n"
                    + context
                )
            messages = build_messages(SYSTEM_PROMPT, history, request.message, context)
            try:
                answer = await llm_client.acomplete(messages)
            except LLMUnavailableError:
                answer = "The language model is temporarily unavailable. Please try again."
                warnings.append("llm_unavailable")

        answer, extra_warnings = validate_answer(answer, len(citations))
        warnings.extend(extra_warnings)
        await self._persist(session, conversation_id, history, request.message, answer)

        return ChatResponse(
            answer=answer,
            conversation_id=conversation_id,
            citations=citations,
            records=[item.as_record() for item in items],
            retrieved_count=len(items),
            query_type=query_type,
            filters_applied=applied,
            data_as_of=self._data_as_of(items),
            model=settings.llm_model,
            warnings=warnings,
        )

    async def stream(self, request: ChatRequest):
        """Async generator yielding SSE frames. Opens its own DB session."""
        async with SessionLocal() as session:
            try:
                items, query_type, applied, relaxation_note = await self._retrieve(
                    session, request.message, request.source_filter, request.filters
                )
                conversation_id, history = await self._history(session, request.conversation_id)
                citations = [item.as_citation() for item in items]
                warnings: list[str] = []
                if relaxation_note:
                    warnings.append("filters_relaxed")

                if not citations:
                    answer = NO_EVIDENCE_ANSWER
                    warnings.append("no_retrieved_evidence")
                elif not settings.is_llm_configured:
                    answer = (
                        "Retrieval succeeded, but answer generation is unavailable because "
                        "LLM_API_KEY is not configured on the server."
                    )
                    warnings.append("llm_not_configured")
                    yield self._frame("token", {"text": answer})
                else:
                    context = build_context(citations, settings.context_max_chars)
                    messages = build_messages(SYSTEM_PROMPT, history, request.message, context)
                    raw_answer = ""
                    safe_answer = ""
                    try:
                        async for token in llm_client.astream(messages):
                            raw_answer += token
                            cleaned, _ = validate_answer(raw_answer, len(citations))
                            # Only stream text that is still a valid prefix of the
                            # validated answer; this prevents a forged [n] marker
                            # from flashing in the UI before the done event.
                            if cleaned.startswith(safe_answer):
                                delta = cleaned[len(safe_answer) :]
                                safe_answer = cleaned
                                if delta:
                                    yield self._frame("token", {"text": delta})
                        answer = validate_answer(raw_answer, len(citations))[0]
                    except LLMUnavailableError:
                        answer = "The language model is temporarily unavailable. Please try again."
                        warnings.append("llm_unavailable")
                        yield self._frame("token", {"text": answer})

                answer, extra_warnings = validate_answer(answer, len(citations))
                warnings.extend(extra_warnings)
                await self._persist(session, conversation_id, history, request.message, answer)

                response = ChatResponse(
                    answer=answer,
                    conversation_id=conversation_id,
                    citations=citations,
                    records=[item.as_record() for item in items],
                    retrieved_count=len(items),
                    query_type=query_type,
                    filters_applied=applied,
                    data_as_of=self._data_as_of(items),
                    model=settings.llm_model,
                    warnings=warnings,
                )
                yield self._frame("done", response.model_dump(mode="json"))
            except Exception as exc:
                logger.exception("stream_chat_failed", extra={"error": str(exc)[:200]})
                yield self._frame("error", {"detail": "Chat request failed"})

    @staticmethod
    def _frame(event: str, data: Any) -> str:
        return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"


rag_service = RAGService()
