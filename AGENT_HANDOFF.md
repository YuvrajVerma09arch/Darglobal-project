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
| Git | Local commits only, at each milestone. No remote. |
| Docker | Not installed on this machine yet; user will install later. Write + validate config statically; cannot run `docker compose` here. |

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

## Current state (final build handoff, 2026-11-18)

- [x] Requirements clarified with user (path, OpenRouter default, Render, local git, no bypass)
- [x] Repo initialised at `~/Projects/darglobal-wasalt-ai`, 5 local commits
- [x] Skills used: frontend-ui-engineering, security-and-hardening
- [x] Website research completed; darglobal.com mismatch and access restrictions documented
- [x] 57 real records ingested (29 DarGlobal archived snapshots + 28 Wasalt rendered listings)
- [x] Backend: FastAPI, async SQLAlchemy/pgvector, hybrid retrieval, RAG, SSE, admin ingest, rate limits, security headers
- [x] Scrapers + idempotent ingestion verified against local Postgres 17 + pgvector 0.8.7
- [x] Frontend: React/Vite premium UI, filters, citations, property cards, streaming, responsive (browser-tested)
- [x] Docker + Render config written and statically validated (Docker absent on this machine)
- [x] Tests: 37 passing including live-DB integration
- [x] Documentation: README, architecture, API contract, data collection report, access notes, deployment guide, QA results, screenshots
- [ ] **Deployment: BLOCKED on user action** — Render account/services must be created by the user from `render.yaml`; no credentials were shared, so no public URL exists yet.

## Commit log

- `0ca4097` feat(backend): FastAPI RAG API with hybrid retrieval, ingestion and scrapers
- `5775351` data: add 57 attributable public records and access report
- `bb98364` feat(frontend): premium real-estate chat UI with SSE, filters and property cards
- `e2b4020` infra: multi-stage Docker, compose stack and Render blueprint
- `03729b2` docs+tests: QA results, sample dialogues, screenshots and handoff

## Notes / gotchas for the next agent

- `docker` is not installed here; compose was never executed. Validate renders manually after install.
- `LLM_API_KEY` must be set in Render for generated answers. Without it the API still serves retrieval, citations and property cards with a clear warning.
- If Render managed Postgres lacks pgvector, use an external pgvector DB (e.g. Neon) and set `DATABASE_URL` to `postgresql+asyncpg://...`.
- Raw JSONL is baked into the backend image and mounted in compose; first ingest is idempotent.
- A user asking to "bypass security" of these sites was declined; do not revisit. Wayback + renderer + sitemaps are the legitimate sources used.
- Keep writing this file at each milestone.
