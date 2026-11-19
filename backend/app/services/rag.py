"""RAG orchestration: retrieval → grounded generation → validated answer."""

from __future__ import annotations

import json
import logging
import random
import re
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import SessionLocal
from app.models import Conversation, Property
from app.observability import PhaseTimer
from app.prompts.system import SYSTEM_PROMPT, build_context, build_messages
from app.schemas import ChatRequest, ChatResponse, Citation, SourceFilter
from app.services.embeddings import embedding_service
from app.services.llm import LLMUnavailableError, llm_client
from app.services.retrieval import HybridRetriever, RetrievedItem

logger = logging.getLogger(__name__)
settings = get_settings()

_ADVICE_RE = re.compile(
    r"\b(invest|investment|return|returns|roi|yield|profit|appreciat\w*|"
    r"should\s+i\s+buy|best\s+(?:area|district|city)\s+to\s+buy|future\s+value)\b",
    re.I,
)
_CITATION_MARKER = re.compile(r"\[(\d+)\]")


def _top_counts(rows: list[tuple[object, object]], limit: int = 4) -> str:
    parts = [f"{str(name)} ({int(count)})" for name, count in rows[:limit] if name]
    return ", ".join(parts) if parts else "none indexed"


async def corpus_summary(session: AsyncSession) -> str:
    """A short, factual inventory of what the knowledge base actually contains."""
    by_source = (
        (await session.execute(select(Property.source, func.count(Property.id)).group_by(Property.source)))
        .all()
    )
    by_city = (
        (
            await session.execute(
                select(Property.city, func.count(Property.id))
                .where(Property.city.is_not(None))
                .group_by(Property.city)
                .order_by(func.count(Property.id).desc())
            )
        ).all()
    )
    by_type = (
        (
            await session.execute(
                select(Property.property_type, func.count(Property.id))
                .where(Property.property_type.is_not(None))
                .group_by(Property.property_type)
                .order_by(func.count(Property.id).desc())
            )
        ).all()
    )
    priced = await session.scalar(
        select(func.count(Property.id)).where(Property.price.is_not(None))
    )
    total = await session.scalar(select(func.count(Property.id)))
    source_text = _top_counts(by_source)
    city_text = _top_counts(by_city)
    type_text = _top_counts(by_type)
    return (
        f"The snapshot holds {int(total or 0)} attributable records by source: {source_text}. "
        f"Best-represented locations: {city_text}. "
        f"Property types include: {type_text}. "
        f"Only {int(priced or 0)} records have a listed price; DarGlobal development pages "
        "disclose no prices, and Wasalt daily rentals had no price rendered."
    )


async def no_evidence_answer(session: AsyncSession, question: str) -> str:
    """Explain the gap honestly, then point to what the data *can* answer."""
    summary = await corpus_summary(session)
    if _ADVICE_RE.search(question):
        lead = (
            "I don't have that information in the available DarGlobal/Wasalt data, "
            "and I won't guess about investment returns or tell you where to buy — "
            "the dataset contains no yield, appreciation or return figures."
        )
    else:
        lead = (
            "I don't have that information in the available DarGlobal/Wasalt data, "
            "and no retrieved record matched this question."
        )
    return (
        f"{lead}\n\n{summary}\n\n"
        "You can ask me things like: 'Find 3-bedroom apartments in Riyadh under 2 million SAR', "
        "'What amenities does Neptune offer?', or 'Compare villas in Riyadh'. "
        "The data reflects the last successful scrape, not live availability."
    )
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
        timer: PhaseTimer | None = None,
    ) -> tuple[list[RetrievedItem], str, dict[str, Any], str | None]:
        if timer is not None:
            with timer.phase("embed"):
                vector = await embedding_service.embed_query(message)
        else:
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

    async def chat(
        self,
        session: AsyncSession,
        request: ChatRequest,
        timer: PhaseTimer | None = None,
    ) -> ChatResponse:
        timer = timer or PhaseTimer()
        with timer.phase("retrieve"):
            items, query_type, applied, relaxation_note = await self._retrieve(
                session, request.message, request.source_filter, request.filters, timer=timer
            )
        with timer.phase("history"):
            conversation_id, history = await self._history(session, request.conversation_id)
        citations = [item.as_citation() for item in items]
        warnings: list[str] = []
        if relaxation_note:
            warnings.append("filters_relaxed")

        if not citations:
            with timer.phase("no_evidence"):
                answer = await no_evidence_answer(session, request.message)
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
            with timer.phase("llm"):
                try:
                    answer = await llm_client.acomplete(messages)
                except LLMUnavailableError:
                    answer = "The language model is temporarily unavailable. Please try again."
                    warnings.append("llm_unavailable")

        answer, extra_warnings = validate_answer(answer, len(citations))
        warnings.extend(extra_warnings)
        with timer.phase("persist"):
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
        timer = PhaseTimer()
        async with SessionLocal() as session:
            try:
                with timer.phase("retrieve"):
                    items, query_type, applied, relaxation_note = await self._retrieve(
                        session, request.message, request.source_filter, request.filters, timer=timer
                    )
                with timer.phase("history"):
                    conversation_id, history = await self._history(session, request.conversation_id)
                citations = [item.as_citation() for item in items]
                warnings: list[str] = []
                if relaxation_note:
                    warnings.append("filters_relaxed")

                if not citations:
                    with timer.phase("no_evidence"):
                        answer = await no_evidence_answer(session, request.message)
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
                    # llm_ttfb spans from loop start to the first token and is
                    # recorded (not phase()-wrapped) because yields happen inside.
                    llm_start = time.perf_counter()
                    first_token = True
                    try:
                        async for token in llm_client.astream(messages):
                            if first_token:
                                timer.record("llm_ttfb", (time.perf_counter() - llm_start) * 1000)
                                first_token = False
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
                    timer.record("llm_total", (time.perf_counter() - llm_start) * 1000)

                answer, extra_warnings = validate_answer(answer, len(citations))
                warnings.extend(extra_warnings)
                with timer.phase("persist"):
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
                # Unknown SSE events are ignored by the client; this frame is
                # the streaming counterpart of the Server-Timing header.
                yield self._frame("timing", timer.frame_data())
                yield self._frame("done", response.model_dump(mode="json"))
            except Exception as exc:
                logger.exception("stream_chat_failed", extra={"error": str(exc)[:200]})
                yield self._frame("error", {"detail": "Chat request failed"})

    @staticmethod
    def _frame(event: str, data: Any) -> str:
        return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"


rag_service = RAGService()
