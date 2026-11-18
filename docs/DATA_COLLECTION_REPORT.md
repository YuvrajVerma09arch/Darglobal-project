# Data Collection Report

Generated: 2026-11-18. All figures are counted directly from `data/raw/*.jsonl`;
nothing is estimated or inflated.

## Summary

| Metric | Value |
|---|---|
| Sources covered | 2 (DarGlobal, Wasalt) |
| Pages/documents successfully acquired | 57 unique source URLs |
| Structured records collected | 57 (29 DarGlobal, 28 Wasalt) |
| Raw snapshot files | 2 JSONL files (`darglobal_rendered.jsonl`, `wasalt_rendered.jsonl`) |
| Records with a non-null price | 20 (all Wasalt) |
| Records with a non-null bedroom count | 31 |
| Records with at least one image URL | 56 |
| Last successful collection timestamp | 2026-11-18T07:48:26Z (Wasalt); DarGlobal rows stamped 2026-11-18 |
| Last successful ingestion | See `/api/v1/stats` after running ingestion |

## DarGlobal — 29 records

- **Provenance:** 29/29 `archived_snapshot` (Wayback Machine captures). None were
  obtainable from the live site.
- **Source URLs:** 29 unique canonical `darglobal.co.uk` URLs. Each row also stores
  the exact capture URL in `metadata.notes` plus `snapshot_date`.
- **Document type:** `development` (branded residential projects).
- **Cities present:** Muscat (8), Dubai (7), Benahavís (2), London (2), Riyadh (1),
  Doha (1), Jeddah (1), Cortesín (1); 6 rows have no city.
- **Field completeness:** description 18/29, bedrooms 5/29, area 4/29, amenities
  4/29, project status 4/29, images 29/29.
- **Prices:** 0/29. No live or archived page used in this collection disclosed a
  price, so `price` and `currency` are `null` in every DarGlobal record.
- **Access notes:** `darglobal.com` now redirects to `dar.io`, an unrelated IT
  holding. The official developer domain `darglobal.co.uk` (including the URL
  supplied by the assignment owner and every project link on
  `linktr.ee/darglobalofficial`) returns an Incapsula challenge to ordinary
  HTTP/rendered requests. No attempt was made to defeat that protection. The
  publicly available Internet Archive was used instead. See
  `docs/DARGLOBAL_ACCESS_NOTES.md`.

## Wasalt — 28 records

- **Provenance:** 28/28 `live_rendered` public detail pages.
- **Listing type:** 20 sale, 8 daily rental (from URL pattern and page metadata).
- **Cities:** Riyadh 23, Jeddah 2, Makkah 1, Najran 1, Almajardah 1.
- **Property types:** Apartment 14, Villa 7, Chalet 2, Floor 1, Land 1, Building 1,
  Studio 1, Farm 1.
- **Field completeness:** price 20/28, bedrooms 26/28, bathrooms 11/28, area 28/28,
  description 28/28, images 27/28, amenities 22/28.
- **Price range (20 priced rows):** 530,000 – 11,500,000 SAR.
- **Daily rentals:** no price was rendered on any of the 8 rental pages; all are
  `null`. Nothing was inferred.
- **Access notes:** `robots.txt` allows `/` but disallows `/search` for the default
  user agent; `/search` was never requested. Sitemaps on `cdn.wasalt.sa` are public.
  Raw HTTP to detail pages returns a Cloudflare 403; a limited number of public
  pages were read through the browser renderer (37 fetches total, no challenge
  page encountered, no bypass code). See `docs/WASALT_ACCESS_NOTES.md`.

## Known limitations of the dataset

- This is a small, non-random snapshot chosen for attribute coverage, not a
  complete inventory of either website.
- DarGlobal data is historical (archived snapshots) and must not be presented as
  current availability. The UI/answer prompt states that data reflects the last
  successful scrape.
- Wasalt sitemaps were dated 2026-10-19 and individual listings showed last-update
  ages from hours to ~293 days; prices and availability may have changed.
- Missing fields are always `null` or empty lists. No synthetic or fabricated
  property information was added.
- Structured numeric constraints (e.g. "3 bedrooms under 2M SAR") are strongest
  on Wasalt rows. DarGlobal bedroom/area values are often descriptive text
  ("1 to 3-bedroom residences"); those values remain in the indexed text but are
  deliberately not coerced into misleading numeric fields.

## Reproducibility

- Raw snapshots are committed as JSONL. `POST /api/v1/admin/ingest` (protected)
  normalises, deduplicates by content hash, chunks, embeds and upserts them.
  Re-running is idempotent.
- The polite HTTP scraper (`python -m app.scraper.run`) can refresh snapshots where
  access permits, honours robots.txt, delays requests, retries with backoff, and
  records blocks instead of circumventing them.
