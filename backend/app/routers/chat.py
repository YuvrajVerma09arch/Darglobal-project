"""Conversational RAG endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import require_access_code
from app.db import get_db
from app.observability import PhaseTimer
from app.schemas import ChatRequest, ChatResponse
from app.services.rag import rag_service

router = APIRouter(prefix="/chat", tags=["chat"], dependencies=[Depends(require_access_code)])


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest, response: Response, session: AsyncSession = Depends(get_db)):
    if request.stream:
        return StreamingResponse(
            rag_service.stream(request),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-transform",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            },
        )
    timer = PhaseTimer()
    result = await rag_service.chat(session, request, timer=timer)
    # Streamed chats report phase timing in an SSE `timing` frame instead.
    response.headers["Server-Timing"] = timer.header()
    return result
