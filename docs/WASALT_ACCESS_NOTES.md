# Wasalt (wasalt.sa) access notes

Collection date: 2026-11-18 (all records carry `scraped_at` = `2026-11-18T07:48:26Z`).
Output: `data/raw/wasalt_rendered.jsonl` (28 records, 28 unique `source_url` values).

## Method and compliance

All page retrieval used only the `webfetch` tool, at low volume, on publicly reachable
URLs. No raw HTTP client, no header/UA spoofing, no CAPTCHA solving, no WAF/403/anti-bot
bypass, no proxy rotation and no circumvention technique of any kind was used. No
`hackskills` were used. No challenge or 403 page was encountered in this run.

`robots.txt` (`https://wasalt.sa/robots.txt`) was fetched and read:

- `User-agent: *` → `Allow: /`, `Disallow: /search`, `Disallow: /cdn-cgi/rum`.
- AI-specific agents are allowed `/search`, but this collection did **not** use any
  agent override and did **not** fetch `/search` or any `/cdn-cgi/` path.
- Sitemaps are declared under `https://cdn.wasalt.sa/sitemap/` (not at the CDN root).
- An `llms.txt` policy reference is advertised but was not fetched.

## Sitemaps used

Fetched successfully:

- `https://cdn.wasalt.sa/sitemap/category_sitemap_en_sa.xml.gz` — category/landing-page
  URLs (8,542 `<loc>` entries), used to discover Riyadh neighbourhood listing pages.
- `https://cdn.wasalt.sa/sitemap/rental_pdp_sitemap_en_sa.xml.gz` — daily-rental detail
  URLs; used to select the 8 rental records.

Attempted but unusable:

- `https://cdn.wasalt.sa/sitemap/product_sitemap_en_sa.xml.gz` — rejected by the fetch
  tool as "Response too large (exceeds 5242880 byte limit)". Not retried, chunked, or
  worked around. All sale-listing URLs were therefore harvested from category pages.

Note: despite the `.gz` filenames, the served content is plain XML.

The category pages used for URL discovery were: `properties-for-sale-in-jeddah-al-bayan`,
`apartments-for-sale-in-riyadh`, `villas-for-sale-in-riyadh`,
`properties-for-sale-in-central-riyadh-al-olaya`, and
`properties-for-sale-in-east-riyadh-al-nahdah`. They contain real detail-page links
plus price/bedroom previews; those previews were **not** copied into the dataset — every
record was built from its own detail page.

## Page counts

| Item | Attempted | Successful | Notes |
|---|---|---|---|
| robots.txt | 1 | 1 | plain text |
| sitemaps | 3 | 2 | product sitemap too large |
| category/SRP pages | 5 | 5 | URL harvesting only |
| listing detail pages | 28 | 28 | 20 sale + 8 daily rental |
| **Total webfetch calls** | **37** | **36** | 1 size-limit failure; 0 challenge/403 blocks |

The 5 known-good sample URLs were all fetched and included. One sale page (5841667) was
first fetched in `text` format to inspect structure; the other 27 were fetched as
`markdown` so real `imagedelivery.net` image URLs were visible.

## Fields consistently unavailable or constrained

- **`price` / `currency` on daily rentals (8/8):** none of the daily-rental detail pages
  rendered a nightly rate. All 8 records have `price: null` and `currency: null`.
  Do not infer a nightly price from the similar sale dataset.
- **`bathrooms`:** absent from most sale pages as a structured field (17 of 20). Where
  an Arabic description gave an explicit count it was used (2 records); conflicting
  text (e.g. 3 دورات مياه vs 4 حمامات) was left null with a note in `metadata`.
- **`project_status`:** the site only exposes an "Age" value (`New`, `4 years`,
  `10+ years`) or nothing; this is copied verbatim into `project_status` and is not a
  construction-status field. Land/building pages often have null.
- **`image_urls`:** empty for one record (5841667) because that page was fetched in
  text format, which strips image markup. All other 27 records have one real,
  observed image URL each. Only the first/main image is captured — the galleries
  rendered as bare links without URLs.
- Not rendered anywhere: latitude/longitude, floor plans, virtual tours, availability
  calendars, and structured amenity lists. `amenities` therefore contains only
  features explicitly named in a page's description or "Additional Information".
- For several Arabic listings the prose area/bedroom count disagrees with the
  structured fields. The structured field was used for `area` / `bedrooms` and the
  discrepancy recorded in `metadata` rather than silently reconciled.

## Data-freshness caveats

- All sitemap entries carried `lastmod` = `2026-10-19`; the dataset snapshot is
  `2026-11-18`. Listings may have been sold, removed, re-priced or re-phrased since.
- Individual pages show "Last updated" values ranging from "Listed Few Hours ago" to
  "293 days ago". Several REGA ad licences expire in late 2026 / 2027; expiry does not
  itself prove a listing is inactive, but licensing status can change.
- Prices are verbatim as rendered at fetch time (numeric `price`, `currency` "SAR" only
  where the literal "SAR" or "ريال" appeared). Market prices, negotiation and
  availability are not guaranteed.
- Coverage is a **small, non-random sample** (mostly Riyadh; a handful of Jeddah,
  Makkah, Najran and Almajardah rentals). It is suitable for RAG grounding and field
  extraction tests, not for market statistics or city-wide inference.
- Some descriptions are truncated in the source UI with a "See more" control;
  `description` and `raw_content` reflect only the text actually rendered to the fetcher.
- Daily-rental `property_type` for the two "Sunset Coast Resort" chalet records comes
  from the URL slug (`chalet-for-booking-*`), because those pages showed no breadcrumb
  type; this is flagged in each record's `metadata.property_type_source`.
