"""DarGlobal public project scraper.

Note: darglobal.com currently redirects to an unrelated domain. The scraper
targets the official developer domain supplied by the assignment owner and
records every access restriction instead of attempting to circumvent it.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from app.scraper.base import BaseScraper, ScrapeBlocked

logger = logging.getLogger(__name__)
BASE = "https://darglobal.co.uk/"


class DarGlobalScraper(BaseScraper):
    source = "darglobal"
    start_urls = (BASE,)

    @staticmethod
    def _jsonld_objects(soup: BeautifulSoup) -> list[dict[str, Any]]:
        objects: list[dict[str, Any]] = []

        def walk(value: Any) -> None:
            if isinstance(value, dict):
                if value.get("@type"):
                    objects.append(value)
                for nested in value.values():
                    walk(nested)
            elif isinstance(value, list):
                for nested in value:
                    walk(nested)

        for tag in soup.find_all("script", type="application/ld+json"):
            try:
                walk(json.loads(tag.string or tag.get_text() or "{}"))
            except json.JSONDecodeError:
                continue
        return objects

    def extract(self, url: str, html: str) -> dict[str, Any] | None:
        soup = BeautifulSoup(html, "lxml")
        title_tag = soup.find("h1") or soup.find("title")
        title = title_tag.get_text(" ", strip=True) if title_tag else None
        description_tag = soup.find("meta", attrs={"name": "description"})
        description = description_tag.get("content") if description_tag else None
        if not description:
            description = soup.get_text(" ", strip=True)[:1400]

        price = bedrooms = bathrooms = area = None
        location = None
        images: list[str] = []
        for obj in self._jsonld_objects(soup):
            offer = obj.get("offers") or {}
            if isinstance(offer, list):
                offer = offer[0] if offer else {}
            if isinstance(offer, dict) and offer.get("price"):
                price = offer.get("price")
            address = obj.get("address") or {}
            if isinstance(address, dict):
                location = address.get("addressLocality") or address.get("addressRegion")
            if obj.get("numberOfRooms"):
                bedrooms = obj["numberOfRooms"]
            if obj.get("numberOfBathroomsTotal"):
                bathrooms = obj["numberOfBathroomsTotal"]
            if obj.get("floorSize"):
                area = obj["floorSize"]
            if isinstance(obj.get("image"), str):
                images.append(obj["image"])
            elif isinstance(obj.get("image"), list):
                images.extend(str(image) for image in obj["image"])

        text = soup.get_text(" ", strip=True)
        bed_match = re.search(r"(\d+)\s*bed(?:room)?s?", text, re.I)
        if bedrooms is None and bed_match:
            bedrooms = int(bed_match.group(1))
        area_match = re.search(r"([\d,]+)\s*(?:sq\s?ft|sqft|sqm)", text, re.I)
        if area is None and area_match:
            area = float(area_match.group(1).replace(",", ""))
        if not title:
            return None

        canonical = soup.find("link", rel="canonical")
        source_url = urljoin(url, canonical.get("href")) if canonical and canonical.get("href") else url
        return {
            "id": re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:80],
            "source": self.source,
            "document_type": "development",
            "title": title[:300],
            "description": description[:4000] if description else None,
            "property_type": None,
            "location": location,
            "city": location,
            "country": None,
            "price": price,
            "currency": "USD" if price else None,
            "bedrooms": int(bedrooms) if str(bedrooms or "").isdigit() else None,
            "bathrooms": int(bathrooms) if str(bathrooms or "").isdigit() else None,
            "area": area,
            "area_unit": None,
            "amenities": [],
            "project_status": None,
            "image_urls": list(dict.fromkeys(images))[:12],
            "source_url": source_url,
            "scraped_at": self.now(),
            "provenance": "live_rendered",
            "raw_content": text[:1200],
            "metadata": {"developer": "DarGlobal", "acquisition": "polite_http"},
        }

    async def run(self, limit: int = 40) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for start in self.start_urls:
            html = await self.fetch(start)
            if html is None:
                continue
            soup = BeautifulSoup(html, "lxml")
            links: list[str] = []
            for anchor in soup.find_all("a", href=True):
                href = urljoin(start, anchor["href"])
                if urljoin(BASE, href).startswith(BASE) and re.search(r"project|develop|property", href, re.I):
                    links.append(href.split("#")[0])
            for url in list(dict.fromkeys(links))[:limit]:
                try:
                    page = await self.fetch(url)
                except ScrapeBlocked:
                    logger.warning("darglobal_blocked", extra={"url": url})
                    break
                if not page:
                    continue
                record = self.extract(url, page)
                if record:
                    records.append(record)
        saved = self.save(records)
        logger.info("darglobal_run_complete", extra={"records": len(records), "path": str(saved)})
        return records
