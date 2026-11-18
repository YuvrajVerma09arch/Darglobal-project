"""Cross-cutting HTTP controls: security headers and per-IP rate limiting."""

from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict, deque

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Sliding-window limiter. Single-instance by design; see DEPLOYMENT.md."""

    def __init__(self, app) -> None:
        super().__init__(app)
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def dispatch(self, request: Request, call_next):
        # Use the ASGI path, not request.url.path: the latter can be influenced
        # by a poisoned Host header (Starlette BadHost class of bug).
        path = (request.scope.get("path") or "").rstrip("/") or "/"
        is_chat = path.endswith("/chat")
        is_admin = path.endswith("/admin/ingest")
        if is_chat or is_admin or path.startswith("/api/"):
            identity = request.client.host if request.client else "unknown"
            bucket = f"{identity}:{path}"
            limit = settings.chat_rate_limit_per_minute if is_chat else settings.rate_limit_per_minute
            if is_admin:
                limit = min(limit, 6)
            now = time.monotonic()
            async with self._lock:
                hits = self._hits[bucket]
                while hits and now - hits[0] > 60:
                    hits.popleft()
                if len(hits) >= limit:
                    logger.warning("rate_limited", extra={"path": path, "identity": identity})
                    return JSONResponse(
                        status_code=429,
                        content={"detail": "Too many requests. Please try again shortly."},
                        headers={"Retry-After": "60"},
                    )
                hits.append(now)
        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        if settings.app_env == "production":
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
            )
        return response
