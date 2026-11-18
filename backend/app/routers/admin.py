"""Protected administrative endpoints."""

from __future__ import annotations

import hmac
import logging
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_db
from app.schemas import IngestResponse
from app.services.ingestion import ingestion_service

logger = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter(prefix="/admin", tags=["admin"])


class IngestRequest(BaseModel):
    source: Literal["both", "darglobal", "wasalt"] = "both"


async def verify_admin(x_admin_key: str = Header(default="")) -> None:
    expected = settings.admin_api_key
    try:
        valid = bool(expected) and hmac.compare_digest(x_admin_key, expected)
    except (TypeError, ValueError):
        # Non-ASCII header values can make compare_digest raise; never 500 here.
        valid = False
    if not valid or expected == "replace-with-a-long-random-value":
        logger.warning("admin_auth_rejected")
        raise HTTPException(status_code=401, detail="Invalid admin key")


@router.post("/ingest", response_model=IngestResponse)
async def ingest(
    request: IngestRequest,
    session: AsyncSession = Depends(get_db),
    _: None = Depends(verify_admin),
):
    result = await ingestion_service.run(session, request.source)
    if result["status"] == "failed":
        raise HTTPException(status_code=500, detail="Ingestion failed; see ingestion_runs.notes")
    return IngestResponse(**result)
