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

## Current state

- [x] Requirements clarified with user
- [x] Repo initialised at `~/Projects/darglobal-wasalt-ai`
- [x] Skills loaded: frontend-ui-engineering, security-and-hardening
- [x] API contract written (`docs/API_CONTRACT.md`)
- [x] Backend scaffold: config, models, schemas, logging, db, prompts, text/query utils
- [ ] Website research (subagent running) → results pending
- [ ] Backend: embeddings, retrieval, LLM, RAG, routers, main — IN PROGRESS (lead)
- [ ] Scrapers + real ingestion — lead, after research report
- [ ] Frontend — subagent running
- [ ] Docker + Render config — subagent running
- [ ] Tests — lead, after backend completes
- [ ] Documentation — lead
- [ ] Deployment (user-side manual step)

## Commit log

- (pending first commit)

## Notes / gotchas for the next agent

- `docker` is not installed: do not assume compose can be run; provide static validation (`docker compose config` cannot run here).
- The user will add `LLM_API_KEY` later. The app must start and serve retrieval/search/stats without it; chat should return a clear configuration error if missing.
- Keep writing this file at each milestone.
