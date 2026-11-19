# Agent Handoff — DarGlobal & Wasalt Real Estate Intelligence Assistant

This file is the live build log. Any agent picking up work MUST read this first, then
continue from the "Current state" section. Update it whenever a milestone is completed.

## Decisions locked with the user (2026-11-18)

| Item | Decision |
|---|---|
| Project path | `~/Projects/darglobal-wasalt-ai` (local, NOT iCloud) |
| LLM provider | OpenRouter is the configured default; abstraction supports OpenAI / Gemini / Anthropic / any OpenAI-compatible endpoint / local |
| Embeddings | Local `fastembed` BGE-small (no key needed) so ingestion works before credentials exist; `openai` selectable via env |
| Deployment | Render, deployed manually by the user from `render.yaml` (no Render credentials shared) |
| Git | Local commits at each milestone, pushed to `origin/main`. |
| Docker | Docker Desktop installed and running; `docker compose` works (CLI is on `PATH`). |

## Engineering principles for this build

- Hybrid retrieval: SQL structured filters + pgvector semantic search, fused with RRF.
- No fabricated data. Missing fields stay `null`.
- Sources and clickable citations come from retrieved records only, never from model output.
- Admin ingest protected by `ADMIN_API_KEY`; no secrets in code or frontend.
- Concurrency: async FastAPI, asyncpg pool, bounded LLM concurrency semaphore, per-IP rate limits.

## Shared contract

`docs/API_CONTRACT.md` is the single source of truth for endpoints and payload shapes.
All agents MUST read it before writing code. Do not change it without telling the lead.

## Parallel work streams (file ownership — do not cross)

- Lead (this session): `backend/app/**`, `docker-compose.yml`, root README, `docs/ARCHITECTURE.md`
- Subagent FRONTEND: `frontend/**` only
- Subagent INFRA: `backend/Dockerfile`, `frontend/Dockerfile`, `frontend/nginx.conf`, `render.yaml`, `scripts/**`, `docs/DEPLOYMENT.md`
- Subagent RESEARCH: read-only website investigation (no files)

## Current state (updated 2026-11-19 after performance pass)

- [x] Requirements clarified with user (OpenRouter default, Render backend + Vercel frontend, local git, no third-party bypass)
- [x] Repo at `~/Projects/darglobal-wasalt-ai`, local commits at each milestone
- [x] Skills used: frontend-ui-engineering, security-and-hardening, conducting-api-security-testing
- [x] Website research completed; darglobal.com mismatch and access restrictions documented
- [x] 57 real records ingested (29 DarGlobal archived snapshots + 28 Wasalt rendered listings); JSONL now committed for clean-clone deploys
- [x] Backend: FastAPI 0.163.2 / Starlette 1.10.0, async SQLAlchemy/pgvector, hybrid retrieval, RAG, SSE, admin ingest, rate limits, security headers
- [x] Scrapers + idempotent ingestion verified against local Postgres 17 and Docker pgvector:pg16
- [x] Frontend: React/Vite premium UI, filters, citations, property cards, streaming, responsive, UX fixes (warnings, data currency, unique anchors, a11y)
- [x] Docker Compose FULLY VERIFIED: `./scripts/docker compose up --build` (frontend nginx temp/pid bug fixed)
- [x] Real OpenRouter generation verified with grounded `[n]` citations and plain-text answers
- [x] Authorized security review (2 static agents + 19 dynamic exploit checks): 19/19 passed after patches
- [x] Tests: 43 passing incl. live-DB; OpenRouter→Groq fallback verified with an intentionally invalid primary key
- [x] Optional `APP_ACCESS_CODE` gate implemented (public `/access` probe + `X-Access-Code` header); browser-verified
- [x] Responsive hamburger/close-button bug fixed (`.icon-btn` specificity override); browser-verified at 1440px and 390px
- [x] Honest `frontend/public/llms.txt` added (no evaluator-manipulation instructions)
- [x] Data-driven filter options + progressive filter relaxation; plain-text output sanitisation; archived conversation history in sidebar; removed "out of scope" example.
- [x] Dark mode added (token overrides + header toggle, persisted, OS-preference default) and verified in browser.
- [x] Unsupported/investment-advice questions now return a factual corpus inventory + example prompts instead of a dead end or a guessed return. 46 tests pass.
- [x] Docker images rebuilt locally after final changes; Render backend + Vercel frontend deployed externally by user.
- [x] Logo mark fixed (flex layout keeps D×W inside the 38px box); status chip now rechecks health; added working "Clear filters" button
- [x] Documentation: README, architecture, API contract, data report, access notes, Render+Vercel deployment guide, QA results, screenshots
- [x] Performance pass (measure-first): `PhaseTimer` instrumentation (`Server-Timing` + SSE `timing` frame), `scripts/perf_bench.py` with p50/p95 + phase attribution and budget gate, `PERF.md` baseline/attempts/conclusion, `backend/tests/test_observability.py` (6 guard tests).
- [x] Fixed missing `PhaseTimer` import in `routers/properties.py` (caused 500 on `/properties`); guard test added.
- [x] Tests: **53 passed, 1 skipped**. Docker stack rebuilt and running (backend/frontend/db all healthy), warm local bench passes every budget.
- [x] Attribution conclusion: live Render budget failures (health 376 ms, properties 446 ms p95) are platform/cold-start noise — same code serves health/properties in 3–10 ms next to Postgres. Search is embed+DB bound (~300 ms warm), chat is LLM bound (~2.4 s of ~2.8 s). No risky retrieval/model changes made.
- [ ] **Deployment: user action** — live Render backend is running an older build (instrumentation not yet redeployed). User action needed: Render "Manual Deploy → Clear build cache & deploy", then re-run the live bench with `APP_ACCESS_CODE` for phase attribution. Frontend Vercel deploy already live.

## Commit log

- Milestones (in order): backend RAG API → 57 real records → premium frontend → Docker/Render/Vercel config → QA docs → hardening/security patches → Groq fallback + brand mark fix → access-code gate + responsive nav fix → brute-force verification.
- All commits authored by the user's local Git identity (`Telos <telos2909@gmail.com>`).
- History was rewritten twice: once to purge an accidentally committed fastembed model cache, once to purge a local prompt-injection self-test corpus that was never meant for the assessment repo. `git log` is authoritative for current hashes.

## Notes / gotchas for the next agent

- Docker CLI is on `PATH` now; use `docker compose ...` from the repo root. If Docker Desktop is closed, `open -a Docker` first.
- `LLM_API_KEY` is now configured locally and verified with OpenRouter; set it in Render for the public deployment.
- Render + Vercel split: `VITE_API_BASE_URL` must be set in Vercel; Render `ALLOWED_ORIGINS` must match the Vercel URL exactly.
- If Render managed Postgres lacks pgvector, use an external pgvector DB (e.g. Neon) and set `DATABASE_URL` to `postgresql+asyncpg://...`.
- Raw JSONL is baked into the backend image and mounted in compose; first ingest is idempotent.
- A user asking to "bypass security" of these sites was declined; do not revisit. Wayback + renderer + sitemaps are the legitimate sources used.
- Keep writing this file at each milestone.
