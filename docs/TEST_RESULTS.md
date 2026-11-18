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

## Authorized security assessment (own application)

Static review by two independent agents (application code + dependencies/config)
plus a UX review were run before hardening. Findings and fixes:

| Severity | Finding | Fix applied |
|---|---|---|
| High | `--proxy-headers --forwarded-allow-ips '*'` made `X-Forwarded-For` spoofable, defeating per-IP rate limits | Removed wildcard proxy trust from `backend/Dockerfile`; limiter now keys on the ASGI path and real peer address |
| High | Raw JSONL snapshots were gitignored, so a clean Render clone would ingest 0 records | Unignored `data/raw/*.jsonl` and committed the real snapshots |
| High | `/health` returned 200 when degraded, so Render would never restart a broken DB | Returns HTTP 503 when the DB is unavailable |
| Medium | Scraper followed redirects/sitemap URLs without host validation (SSRF to metadata endpoint) | Host allowlist + DNS/private-IP checks + manual redirect validation in `scraper/base.py` |
| Medium | Client-chosen `conversation_id` allowed cross-conversation history tampering | Only opaque server-generated 20-hex IDs are accepted; 7-day TTL cleanup added |
| Medium | Streamed tokens were emitted before citation validation | Tokens now streamed only while they remain a valid prefix of the validated answer |
| Medium | Known-vulnerable `starlette 0.41.3` / `lxml 5.3.0` | Upgraded to FastAPI 0.163.2 (Starlette 1.10.0) and lxml 6.1.3 |
| Low | Scraped `javascript:` URLs could be rendered as links/images | `http/https` scheme allowlist in ingestion; CSP narrowed in nginx/Vercel |
| Low | Admin key on curl command line; non-ASCII header could 500 | 0600 curl config file; `compare_digest` TypeError caught → 401 |
| Low | Muted text contrast, weak focus ring, global citation anchors, token flood for screen readers, hidden data-currency | Fixed by frontend UX agent; see `docs/SCREENSHOTS.md` after redeploy |

Dynamic verification on the final Docker stack: `python3 scripts/pentest_local.py`
ran 19 exploit attempts (admin auth incl. non-ASCII key, CORS reflection, SQLi,
path traversal, XFF spoofing, oversized input, invalid enums, prompt injection,
conversation takeover, SSE contract) — **19/19 passed**.

### Filter reliability, plain-text output and conversation history
- Filter dropdowns are now populated from `/api/v1/stats` (real cities, property
  types, bedroom values and max price) instead of hardcoded guesses.
- Impossible filter combinations no longer dead-end: the retriever relaxes
  bedrooms → type → location → price, and finally offers other real records.
  Browser test with Riyadh/villa/3 beds/≤2M returned 4 villas with a visible
  "exact filters had no match" notice.
- Markdown (`**bold**`, `[text](url)`, backticks, `#` headings) is stripped
  deterministically in `validate_answer()`, so answers stay plain text even when
  the model ignores the prompt rule. Browser test confirmed no `**` in output.
- "New conversation" archives the current chat; a Recent conversations list in
  the sidebar restores it. Browser test confirmed archive + restore.
- The "Out of scope / mortgage" example was removed; guardrails remain in the
  system prompt but the UI no longer invites testing them directly.
- 45 tests pass including a live test for filter relaxation.

### Access-code gate and responsive controls (final round)
- `APP_ACCESS_CODE` set → `/api/v1/access` reports `access_required: true`,
  chat without the header returns 401, chat with `X-Access-Code` returns 200.
- Headless browser verified: wrong code shows an inline error, correct code
  unlocks the UI; at 1440px the hamburger and sidebar X are hidden, at 390px the
  hamburger opens the drawer and the X closes it (previous bug: a later
  `.icon-btn { display:inline-grid }` rule overrode their `display:none`).
- Docker images rebuilt after these changes; compose stack healthy.
- Brute-force simulation: 35 wrong access-code guesses in one minute produced
  30×401 then 5×429 — the sliding-window limiter caps guesses at 30/min/path.
  Header-based identity spoofing (`X-Forwarded-For`) was already verified not to
  defeat this limit (see the dynamic pentest above).

### LLM fallback verification
- With an intentionally invalid `LLM_API_KEY`, `acomplete()` and `astream()`
  both succeeded using Groq (`openai/gpt-oss-120b`) — fallback chain confirmed.
- The initially configured Groq model `llama-3.3-70b-versatile` returned 404
  `model_not_found`; the default was changed to a model the account exposes.
- Offline unit tests cover provider-chain construction and fallback-on-failure.

Additional final verification after hardening:
- `docker compose up --build` — all three images built, db/backend healthy,
  frontend container initially failed on nginx temp/pid paths and was fixed
  (`client_body_temp_path` + `/tmp/nginx.pid` rewrite); now healthy and serving 200.
- Admin ingestion inside the container — 57 records / 57 chunks, idempotent.
- Real OpenRouter generation — grounded answers with inline `[n]` markers and
  clickable citations; plain-text answer formatting enforced in the system prompt.
- Frontend E2E screenshots refreshed from the final container at `localhost:8080`.

## Not verified here

- Public Render + Vercel deployment — requires the assignment owner's accounts
  and repositories. `render.yaml`, `vercel.json` and `docs/DEPLOYMENT.md` contain
  the full configuration and click-by-click steps.
- Multi-instance rate limiting — the limiter is per-process; a shared Redis
  store is needed if the backend is scaled horizontally.
