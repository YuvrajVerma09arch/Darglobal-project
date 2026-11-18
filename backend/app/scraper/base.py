"""Shared polite HTTP scraping primitives.

Respects robots.txt, uses delays, bounded retries with backoff, timeouts, and
never attempts to defeat authentication, CAPTCHAs or anti-bot protections.
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class ScrapeBlocked(RuntimeError):
    """Raised when a host legitimately blocks automated access."""


class BaseScraper:
    source = "unknown"
    start_urls: tuple[str, ...] = ()

    def __init__(self, output_dir: Path | None = None) -> None:
        self.output_dir = output_dir or Path("data/raw")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._robots: dict[str, RobotFileParser | None] = {}
        self._seen_urls: set[str] = set()
        self._last_request: dict[str, float] = {}
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(settings.scraper_timeout_seconds),
            follow_redirects=True,
            headers={
                "User-Agent": settings.scraper_user_agent,
                "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
            },
        )

    async def close(self) -> None:
        await self.client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args) -> None:
        await self.close()

    @staticmethod
    def _host(url: str) -> str:
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}"

    async def _robots_for(self, url: str) -> RobotFileParser | None:
        host = self._host(url)
        if host in self._robots:
            return self._robots[host]
        parser: RobotFileParser | None = None
        try:
            response = await self.client.get(urljoin(host, "/robots.txt"))
            if response.status_code == 200 and "text" in response.headers.get("content-type", ""):
                parser = RobotFileParser()
                parser.parse(response.text.splitlines())
        except httpx.HTTPError:
            parser = None
        self._robots[host] = parser
        return parser

    async def allowed(self, url: str) -> bool:
        parser = await self._robots_for(url)
        if parser is None:
            return True
        return parser.can_fetch(settings.scraper_user_agent, url)

    async def fetch(self, url: str) -> str | None:
        if url in self._seen_urls:
            return None
        self._seen_urls.add(url)
        if not await self.allowed(url):
            logger.info("robots_disallowed", extra={"url": url})
            return None

        host = self._host(url)
        wait = settings.scraper_delay_seconds - (asyncio.get_running_loop().time() - self._last_request.get(host, 0))
        if wait > 0:
            await asyncio.sleep(wait + random.uniform(0, 0.3))

        for attempt in range(settings.scraper_max_retries + 1):
            try:
                response = await self.client.get(url)
                self._last_request[host] = asyncio.get_running_loop().time()
                if response.status_code in (401, 403, 429):
                    logger.warning("access_blocked", extra={"url": url, "status": response.status_code})
                    raise ScrapeBlocked(f"HTTP {response.status_code} for {url}")
                response.raise_for_status()
                return response.text
            except ScrapeBlocked:
                raise
            except (httpx.HTTPError, httpx.TimeoutException) as exc:
                if attempt >= settings.scraper_max_retries:
                    logger.warning("fetch_failed", extra={"url": url, "error": str(exc)[:120]})
                    return None
                await asyncio.sleep(2**attempt)
        return None

    async def discover_sitemaps(self, base_url: str) -> list[str]:
        for candidate in ("/sitemap.xml", "/sitemap_index.xml", "/robots.txt"):
            body = await self.fetch(urljoin(base_url, candidate))
            if not body:
                continue
            found = [line.split(":", 1)[1].strip() for line in body.splitlines() if line.lower().startswith("sitemap:")]
            if found:
                return found
            if "<sitemapindex" in body or "<urlset" in body:
                return [urljoin(base_url, candidate)]
        return []

    def save(self, records: list[dict[str, Any]], suffix: str = "live") -> Path:
        path = self.output_dir / f"{self.source}_{suffix}.jsonl"
        with path.open("a", encoding="utf-8") as handle:
            for record in records:
                handle.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
        logger.info("snapshot_saved", extra={"path": str(path), "records": len(records)})
        return path

    @staticmethod
    def now() -> str:
        return datetime.now(timezone.utc).isoformat()
