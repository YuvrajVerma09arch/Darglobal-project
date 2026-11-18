"""Wasalt public listing scraper (sitemap discovery + detail extraction).

Raw requests may legitimately return a 403 challenge. The scraper records that
restriction and stops; it never attempts to evade it.
"""

from __future__ import annotations

import gzip
import json
import logging
import re
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from app.scraper.base import BaseScraper, ScrapeBlocked

logger = logging.getLogger(__name__)
BASE = "https://wasalt.sa/"
SITEMAP = "https://cdn.wasalt.sa/product_sitemap_en_sa.xml.gz"


class WasaltScraper(BaseScraper):
    source = "wasalt"
    start_urls = (BASE,)

    def _extract_sitemap_urls(self, body: str, limit: int) -> list[str]:
        text = body
        if body.startswith("\x1f\x8b"):
            try:
                text = gzip.decompress(body.encode("latin-1")).decode("utf-8", errors="replace")
            except (gzip.BadGzipFile, UnicodeDecodeError):
                text = body
        urls = re.findall(r"<loc>\s*([^<]+)\s*</loc>", text)
        return [url.strip() for url in urls if "/property/sale/" in url or "/dailyrental/" in url][:limit]

    @staticmethod
    def _jsonld(soup: BeautifulSoup) -> list[dict[str, Any]]:
        found: list[dict[str, Any]] = []
        for tag in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(tag.string or tag.get_text() or "{}")
            except json.JSONDecodeError:
                continue
            for item in data if isinstance(data, list) else [data]:
                if isinstance(item, dict):
                    found.append(item)
        return found

    def extract(self, url: str, html: str) -> dict[str, Any] | None:
        soup = BeautifulSoup(html, "lxml")
        title_tag = soup.find("h1") or soup.find("title")
        title = title_tag.get_text(" ", strip=True) if title_tag else None
        if not title:
            return None

        text = soup.get_text(" ", strip=True)
        price = bedrooms = bathrooms = area = None
        images: list[str] = []
        for obj in self._jsonld(soup):
            offer = obj.get("offers")
            if isinstance(offer, list):
                offer = offer[0] if offer else {}
            if isinstance(offer, dict) and offer.get("price"):
                price = offer["price"]
            if obj.get("numberOfRooms"):
                bedrooms = obj["numberOfRooms"]
            if obj.get("numberOfBathroomsTotal"):
                bathrooms = obj["numberOfBathroomsTotal"]
            if isinstance(obj.get("image"), str):
                images.append(obj["image"])
            elif isinstance(obj.get("image"), list):
                images.extend(str(image) for image in obj["image"])

        price_match = re.search(r"(?:Price|السعر)\s*:?\s*([\d,]+)\s*(SAR|ريال)?", text, re.I)
        if price is None and price_match:
            price = float(price_match.group(1).replace(",", ""))
        bed_match = re.search(r"(\d+)\s*(?:Bedrooms?|Bed|غرف)", text, re.I)
        if bedrooms is None and bed_match:
            bedrooms = int(bed_match.group(1))
        bath_match = re.search(r"(\d+)\s*(?:Bathrooms?|Bath|حمام)", text, re.I)
        if bathrooms is None and bath_match:
            bathrooms = int(bath_match.group(1))
        area_match = re.search(r"([\d,.]+)\s*(?:SQM|Sq\.?\s*M|متر)", text, re.I)
        if area_match:
            area = float(area_match.group(1).replace(",", ""))

        city = "Riyadh" if re.search(r"Riyadh|الرياض", text, re.I) else None
        match_id = re.search(r"-(\d{4,})\s*$", url)
        return {
            "id": match_id.group(1) if match_id else re.sub(r"[^a-z0-9]+", "-", url.lower())[-70:],
            "source": self.source,
            "document_type": "property",
            "title": title[:300],
            "description": text[:4000],
            "property_type": next(
                (t for t in ("Villa", "Apartment", "Townhouse", "Penthouse", "Studio", "Farm")
                 if re.search(rf"\b{t}\b", title + " " + text[:400], re.I)),
                None,
            ),
            "location": None,
            "city": city,
            "country": "Saudi Arabia",
            "price": price,
            "currency": "SAR" if price else None,
            "bedrooms": int(bedrooms) if str(bedrooms or "").isdigit() else None,
            "bathrooms": int(bathrooms) if str(bathrooms or "").isdigit() else None,
            "area": area,
            "area_unit": "SQM" if area else None,
            "amenities": [],
            "project_status": None,
            "image_urls": list(dict.fromkeys(images))[:12],
            "source_url": url,
            "scraped_at": self.now(),
            "provenance": "live_rendered",
            "raw_content": text[:1200],
            "metadata": {
                "listing_type": "rent" if "/dailyrental/" in url else "sale",
                "acquisition": "polite_http",
            },
        }

    async def run(self, limit: int = 40) -> tuple[list[dict[str, Any]], str | None]:
        sitemap_body = await self.fetch(SITEMAP)
        urls = self._extract_sitemap_urls(sitemap_body or "", limit) if sitemap_body else []
        if not urls:
            urls = [
                "https://wasalt.sa/en/property/sale/apartment-with-3-bedrooms-5841667",
                "https://wasalt.sa/en/property/sale/villa-333-sqm-facing-east-on-20m-width-street-5841671",
                "https://wasalt.sa/en/dailyrental/apartment-for-booking-5577",
            ]
        records: list[dict[str, Any]] = []
        blocking_note: str | None = None
        for url in urls[:limit]:
            try:
                html = await self.fetch(url)
            except ScrapeBlocked as exc:
                blocking_note = str(exc)
                logger.warning("wasalt_blocked", extra={"url": url})
                break
            if not html:
                continue
            record = self.extract(url, html)
            if record:
                records.append(record)
        self.save(records)
        return records, blocking_note
