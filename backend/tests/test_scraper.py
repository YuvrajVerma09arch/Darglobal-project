"""Scraper extraction tests using offline HTML fixtures (no network calls)."""

import json

from app.scraper.darglobal import DarGlobalScraper
from app.scraper.wasalt import WasaltScraper

DAR_HTML = """
<html><head>
<title>Neptune by DarGlobal</title>
<meta name="description" content="Five bedroom residences in Riyadh.">
<link rel="canonical" href="https://darglobal.co.uk/neptune">
<script type="application/ld+json">{"@type":"Product","name":"Neptune",
"offers":{"price":"1200000","priceCurrency":"SAR"},
"address":{"addressLocality":"Riyadh"},"numberOfRooms":5,
"image":["https://darglobal.co.uk/img/neptune.jpg"]}</script>
</head><body><h1>Neptune</h1><p>Under development. 5 bedrooms, 300 sqm.</p></body></html>
"""

WASALT_HTML = """
<html><head><title>Apartment with 3 Bedrooms</title>
<script type="application/ld+json">{"@type":"Product","name":"Apartment",
"offers":{"price":850000},"numberOfRooms":3,
"image":["https://wasalt.sa/img/a.jpg"]}</script></head>
<body><h1>Apartment with 3 Bedrooms</h1>
<p>Al-Mahdiyah, West Riyadh. Price: 850,000 SAR. 133 SQM. 3 Bedrooms, 2 Bathrooms.</p>
</body></html>
"""


def test_darglobal_extract_reads_jsonld_and_leaves_missing_null():
    scraper = DarGlobalScraper()
    record = scraper.extract("https://darglobal.co.uk/neptune", DAR_HTML)
    assert record is not None
    assert record["title"] == "Neptune"
    assert record["city"] == "Riyadh"
    assert record["bedrooms"] == 5
    assert record["area"] == 300.0
    assert record["bathrooms"] is None
    assert record["source"] == "darglobal"
    assert record["source_url"].endswith("/neptune")


def test_wasalt_extract_reads_price_and_specs():
    scraper = WasaltScraper()
    record = scraper.extract(
        "https://wasalt.sa/en/property/sale/apartment-with-3-bedrooms-5841667", WASALT_HTML
    )
    assert record is not None
    assert record["price"] == 850000
    assert record["bedrooms"] == 3
    assert record["bathrooms"] == 2
    assert record["area"] == 133.0
    assert record["currency"] == "SAR"
    assert record["city"] == "Riyadh"
    assert record["metadata"]["listing_type"] == "sale"


def test_extract_returns_none_for_empty_page():
    assert DarGlobalScraper().extract("https://darglobal.co.uk/x", "<html></html>") is None
    assert WasaltScraper().extract("https://wasalt.sa/x", "<html></html>") is None


def test_sitemap_url_extraction_filters_property_pages():
    xml = """<urlset><url><loc>https://wasalt.sa/en/property/sale/x-1</loc></url>
    <url><loc>https://wasalt.sa/en/s/privacy-policy</loc></url>
    <url><loc>https://wasalt.sa/en/dailyrental/y-2</loc></url></urlset>"""
    urls = WasaltScraper()._extract_sitemap_urls(xml, 10)
    assert len(urls) == 2
    assert all("/property/sale/" in u or "/dailyrental/" in u for u in urls)


async def test_scraper_rejects_non_allowlisted_and_private_urls():
    from app.scraper.base import ScrapeBlocked

    scraper = DarGlobalScraper()
    for url in (
        "http://169.254.169.254/latest/meta-data/",
        "https://evil.example.com/x",
        "javascript:alert(1)",
    ):
        try:
            await scraper.validate_url(url)
        except ScrapeBlocked:
            continue
        raise AssertionError(f"Expected {url} to be rejected")


def test_jsonld_payload_is_valid_after_serialisation():
    scraper = DarGlobalScraper()
    record = scraper.extract("https://darglobal.co.uk/neptune", DAR_HTML)
    assert json.loads(json.dumps(record, default=str))["source"] == "darglobal"
