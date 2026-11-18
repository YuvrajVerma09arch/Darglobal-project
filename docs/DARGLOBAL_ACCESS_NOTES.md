# DarGlobal public-data access notes

Date of collection: 2026-11-18 (UTC). Output: `data/raw/darglobal_rendered.jsonl` (29 records).

## Method and restrictions

Only the `webfetch` tool was used, on publicly reachable URLs, at low volume. Exactly **25 webfetch calls** were made (the stated cap). No bypass, WAF-evasion, 403-bypass, CAPTCHA-solving, anti-bot circumvention or proxy-evasion technique was used, and no install commands were run. No attempt was made to defeat Incapsula or Cloudflare. Where a URL returned a challenge or no content, collection for that URL was stopped and the limitation recorded below.

## URLs tried and observations

### Live URLs (user-supplied and official links)

| # | URL | Result |
|---|---|---|
| 1 | `https://darglobal.co.uk/?ltclid=e761ba08-8328-4e8e-a15a-60bbdb49068f` | "(no tool output)" — no content returned |
| 2 | `https://linktr.ee/darglobalofficial` | **Worked.** Returned the full public Linktree with official project links |
| 3–7 | `https://darglobal.co.uk/rayana/darglobal-mansions-fendi-casa`, `/lp/trump-international-qatar`, `/trump-plaza/executive-residences`, `/amour-sans-detour-2`, `/trump-plaza/park-residences` | All "(no tool output)" — same challenge behaviour as the homepage |

Consistent with prior research, all live `darglobal.co.uk` URLs were unusable via `webfetch`. The Linktree was the only live source that yielded data. It supplied these official (but live-blocked) project URLs: `/rayana/darglobal-mansions-fendi-casa`, `/lp/trump-international-qatar`, `/trump-plaza/executive-residences`, `/amour-sans-detour-2`, `/trump-plaza/park-residences`, plus `/get-in-touch` and `/become-an-agent`. It also lists Instagram, Telegram, YouTube, WhatsApp and other social channels; these were not fetched, so no records derive from them.

### Wayback Machine CDX API (index queries)

| # | Query | Result |
|---|---|---|
| 8 | `cdx?url=darglobal.co.uk/projects*&...&limit=60` | Worked; revealed project index, location filters and many image assets |
| 9 | `cdx?url=darglobal.co.uk&...` | Worked; one capture of the homepage (2022-12-06) |
| 10 | `cdx?url=darglobal.com&from=2021&to=2023&...` | Empty (`[]`) — no usable 2021–2023 real-estate snapshots of `darglobal.com` |
| 18–21 | CDX for `/the-astera`, `/marea`, `/les-vagues`, `/trump-tower-jeddah` | Worked; supplied exact capture timestamps |

Note: many CDX rows with 2026 timestamps and `~60KB` lengths for **image** URLs reported as `text/html` are soft-404/challenge captures and were deliberately ignored.

### Wayback snapshots

| # | Snapshot | Result |
|---|---|---|
| 11 | `web/20240302210735id_/https://darglobal.co.uk/projects` | Sparse: navigation, location filters, enquiry form; no project data |
| 12 | `web/20251017074901id_/https://darglobal.co.uk/projects/aida` | **Worked well.** Rich projects index with ~30 named projects, locations, descriptions and CDN image URLs. Source of 24 records |
| 13 | `web/20251110201822id_/https://darglobal.co.uk/projects/apartments` | Worked but index-only (titles/locations/images, no descriptive text); not used as a source to avoid duplicates |
| 14–16 | `/web/2025/https://darglobal.co.uk/the-astera`, `/marea`, `/trump-international-hotel-and-tower-dubai` | Redirected to captures that rendered only the Wayback toolbar/interstitial; no usable content |
| 17 | `/web/2025/https://darglobal.co.uk/neptune` | **Worked.** Full detail page (property type, status, bedrooms, area, completion date, amenities, images) |
| 22 | `web/20250910081757id_/.../the-astera` | **Worked.** Full detail page |
| 23 | `web/20231209122137id_/.../marea/` | Worked; older WordPress-era page. Mixed with related-project content; only unambiguously Marea fields used |
| 24 | `web/20240413092931id_/.../les-vagues` | **Worked.** Full detail page |
| 25 | `web/20250217105119id_/.../trump-tower-jeddah` | **Worked.** Full detail page |

## Data conventions

- All 29 records are labelled `provenance: "archived_snapshot"` because every project fact came from a Wayback capture. `snapshot_date` is the ISO-8601 form of the 14-digit capture timestamp; the exact capture URL is in `metadata.notes` as `wayback_url`.
- `source_url` is the exact canonical project URL as it appears publicly on the captured official page (e.g. `https://darglobal.co.uk/neptune`). The exact fetched URL is preserved in `metadata.notes`. This keeps one unique `source_url` per development for deduplication while retaining a clickable, verifiable citation.
- Index-card records (24 of 29) come from the single 2025-10-17 `/projects/aida` index snapshot; their `source_page` metadata names that capture and notes that no detail page was fetched for them.
- Every value was copied from retrieved content. No price, bedroom count, bathroom count, area, amenity, status or investment return was invented or inferred. Truncated card descriptions are stored verbatim and flagged in metadata. `price`, `currency`, `bathrooms` are `null` everywhere because they were never shown; `amenities` is `[]` where no attributable list existed.

## Records produced and unavailable fields

- **29 records**, 29 unique `source_url` values, 29 unique ids, all with the required key set.
- 18 records have a description; 5 have bedroom data; 5 have area data; 5 have an explicit `project_status`; 5 have an amenity list.
- Unavailable throughout: `price`, `currency`, `bathrooms`.
- Frequently unavailable: `bedrooms`, `area`, `area_unit`, `project_status`, `amenities` (absent from index cards).
- `country` left `null` for some London/AIDA cards where the card did not name a country; `city` left `null` where the named place was a community or island rather than a city.
- The live Linktree project pages (`/rayana/darglobal-mansions-fendi-casa`, `/lp/trump-international-qatar`, `/trump-plaza/executive-residences`, `/amour-sans-detour-2`, `/trump-plaza/park-residences`) produced **no records** because they were blocked; only the index's `AMOUR SANS DETOUR` card was captured.
- `darglobal.com` produced no records (redirect/unrelated content plus empty CDX result for 2021–2023).
