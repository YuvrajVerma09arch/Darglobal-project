"""Shared request dependencies."""

from __future__ import annotations

import hmac

from fastapi import Header, HTTPException

from app.config import get_settings

settings = get_settings()


async def require_access_code(x_access_code: str = Header(default="")) -> None:
    """Optional shared-code gate for the public chat/search/properties APIs.

    /health, /docs and /api/v1/access stay public so the UI can detect that a
    code is needed and the platform can still health-check the service.
    """
    expected = (settings.app_access_code or "").strip()
    if not expected:
        return
    try:
        valid = hmac.compare_digest(x_access_code, expected)
    except (TypeError, ValueError):
        valid = False
    if not valid:
        raise HTTPException(status_code=401, detail="Access code required")
