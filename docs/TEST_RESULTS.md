# Test Results

Run on 2026-11-18, macOS (arm64), Python 3.13, Node 20, local PostgreSQL 17
(pgvector 0.8.7), fastembed BGE-small model downloaded locally.

## Commands

```bash
cd backend
../.venv/bin/python -m pytest -q
RUN_DB_TESTS=1 ../.venv/bin/python -m pytest -q
cd ../frontend && npm run build && npm audit --omit=dev
```

## Results

| Suite | Result |
|---|---|
| Unit + API contract (`pytest -q`) | **36 passed** |
| Live DB integration included (`RUN_DB_TESTS=1 pytest -q`) | **37 passed** |
| Frontend production build | **passed** (Vite 5.4.21, 1600 modules, 173.94 kB JS / 54.85 kB gzip, 17.63 kB CSS) |
| Frontend production dependency audit | **0 vulnerabilities** (2 dev-toolchain advisories only) |
| Python compile check | `compileall` exit 0 |
| YAML / shell validation (infra agent) | `render.yaml` + `docker-compose.yml` parse; `bash -n` on all scripts passed |
| Live HTTP smoke tests | `/health`, `/sources`, `/stats`, `/properties`, `/search`, `/chat`, SSE stream — all 200 with expected shapes |

## What the tests actually cover

- **Scraper**: JSON-LD/DOM extraction, missing fields → `null`, sitemap URL
  filtering, empty-page handling, robots/delay logic in the base class.
- **Ingestion**: normalization, provenance preservation, deduplication across
  files, malformed-line counting; real ingestion produced 57 records / 57 chunks
  and a second run produced 0 upserts (idempotent).
- **RAG**: invalid/over-range citation markers stripped, citations removed when
  no evidence, context numbering and URL inclusion, retrieved text framed as
  data, unsupported question short-circuit.
- **API**: OpenAPI, health payload, chat validation (empty message, bad source,
  impossible price range), admin auth, security headers, CORS allowlist, 404s.
- **Live integration** (real pgvector): exact bedroom/price/source constraints
  enforced on both retrieval channels, source isolation, no citations for an
  unrelated question, all citations have HTTPS source URLs.
- **E2E scenarios** from the assignment: general DarGlobal, general Wasalt,
  property-specific, location search, cross-source comparison, follow-up
  (conversation persistence), unsupported question, unavailable pricing —
  exercised via the RAG service and HTTP smoke tests.

## Bugs found and fixed during verification

1. Exact filters were applied to the SQL channel but ignored by the pgvector
   channel — a 5-bed property appeared for a 3-bed query. Fixed with a shared
   property-ID subquery used by both channels.
2. A JSONB `listing_type` condition referenced `properties` inside the chunk
   query, producing a cartesian product. Fixed by moving that condition into the
   subquery.
3. With no filters, RRF always injected recent arbitrary records, making an
   unrelated question look grounded. Fixed by only using the structured channel
   when an exact filter exists.
4. Vector search always returns nearest neighbours, so off-topic questions had
   weak "evidence". Added a calibrated similarity floor (0.65).
5. Local `.env` discovery and raw-data path were relative to the wrong working
   directory. Fixed to resolve from the project root.
6. Replacing chunks used ORM deletes and inserts with the same primary key;
   changed to a bulk DELETE before insert.
7. Browser E2E found the send button passed the React click event into
   `handleSend`, crashing on `.trim()`. Fixed in `Composer.jsx` with a defensive
   guard in `useChat.js`; verified with headless Chromium.
8. Headless UI test used the UI's own "3-bedroom" example; the query regex did
   not handle hyphens, so bedroom filtering was skipped. Fixed and unit-tested.
9. Docker review found `data/` was excluded by `.dockerignore` and the project
   root resolved incorrectly inside the image, which would have made the first
   Render ingestion find zero records. Both fixed; raw JSONL is baked into the
   backend image.

## Not verified here

- Docker image builds and `docker compose up` — Docker is not installed on the
  build machine (user will install it). Configuration was statically validated.
- Live OpenRouter generation — no API key was provided during the build. The
  provider abstraction, streaming path and answer validation were verified with
  the key-absent fallback and mocked paths.
- Public Render deployment — requires the assignment owner's account.
