# Deployment Guide

This guide covers the two supported paths: a local Docker stack and a manual
Render deployment. It assumes the API contract in `docs/API_CONTRACT.md`.

> **Ownership note.** The final Render URLs are created in **your own Render
> account**. This repository only contains the configuration (`render.yaml`);
> nobody can deploy or give you a public URL on your behalf.

---

## 0. Prerequisites

- Docker + Docker Compose (local path only). Docker is **not** installed on the
  build machine, so these configs were validated statically, not by running
  `docker compose up`.
- Python 3.13 (for the helper scripts).
- `curl`.
- An OpenRouter API key for **chat** (`LLM_API_KEY`). Retrieval, stats and
  search endpoints work before that key exists.
- For Render: a Git repository you control. Render deploys from a hosted Git
  provider (GitHub / GitLab / Bitbucket). The repo in this workspace is local
  and has no remote, so **push it to a hosted remote first**.

---

## 1. Local Docker run

### Step 1 — create `.env`

```bash
cd ~/Projects/darglobal-wasalt-ai
./scripts/bootstrap_local.sh
```

This copies `.env.example` → `.env`, generates a random `ADMIN_API_KEY` and
`POSTGRES_PASSWORD`, keeps `DATABASE_URL` consistent with that password, adds
`VITE_API_BASE_URL=http://localhost:8000`, and sets file mode to `600`.
If `.env` already exists, the script refuses to overwrite it.

### Step 2 — set the LLM key

Edit `.env` and replace `LLM_API_KEY=replace-with-your-openrouter-key` with a
real key. Everything except chat works without it. Optionally set
`GROQ_API_KEY` as an automatic fallback provider.

### Step 3 — build and start

```bash
docker compose up --build -d
docker compose ps          # db should show "healthy"
```

Compose starts three containers:

| Service | Container port | Host URL |
|---|---|---|
| `db` (`pgvector/pgvector:pg16`) | 5432 | internal only |
| `backend` (FastAPI) | 8000 | http://localhost:8000 |
| `frontend` (nginx) | 8080 | http://localhost:8080 |

The backend waits for `db` to become healthy before starting. On startup it
runs `CREATE EXTENSION IF NOT EXISTS vector` and creates the tables/indexes.

### Step 4 — verify health

```bash
curl -s http://localhost:8000/health | python3 -m json.tool
# Expect: {"status":"ok", "database":"connected", ...}
```

### Step 5 — initial ingestion

```bash
./scripts/ingest.sh            # both sources
./scripts/ingest.sh wasalt     # or one source
```

Ingestion can take several minutes. The first run downloads the fastembed
model (see troubleshooting). The admin endpoint is protected by
`X-Admin-Key: <ADMIN_API_KEY>`; the script reads the key from `.env`.

### Step 6 — smoke test

```bash
./scripts/smoke_test.sh
```

This calls `/health`, `/api/v1/sources`, `/api/v1/stats`,
`/api/v1/properties?limit=3` and `POST /api/v1/chat`, then prints a citation
summary. Then open <http://localhost:8080> in a browser and ask a question.

### Step 7 — stop / restart (persistence)

```bash
docker compose down            # STOP and remove containers; data is kept
docker compose up -d           # data comes back
```

- Postgres data lives in the named volume `postgres_data`.
- Scraped data **and the fastembed model cache** live in `./data` on the host.
- `docker compose down -v` **deletes** the database volume — don't use it for a
  normal restart.

---

## 2. Render manual deployment (click-by-click)

### Step 1 — publish the repo

Create a remote on GitHub/GitLab/Bitbucket and push every file, including
`render.yaml`, both Dockerfiles, `frontend/nginx.conf` and this repository's
`.dockerignore`. Do **not** push `.env`.

### Step 2 — create the Blueprint

1. Log in to <https://dashboard.render.com/>.
2. Click **New → Blueprint**.
3. Connect the repository you pushed above (first time: **Install** the Render
   GitHub app and grant access only to that repo).
4. Render detects `render.yaml` at the repo root. Review the resources:
   - `realestate-ai-db` (Postgres)
   - `darglobal-wasalt-backend` (Docker web service)
   - `darglobal-wasalt-frontend` (Docker web service)
5. Give the Blueprint a name and choose a region (the YAML pins `oregon`; keep
   all three resources in the **same region**).
6. Render prompts for the `sync: false` values. Fill in:
   - `DATABASE_URL` — see Step 3.
   - `ADMIN_API_KEY` — paste the value from your local `.env` (so the local
     `ingest.sh` works) or a fresh secret you store somewhere safe. Generate
     one with `python3 -c "import secrets; print(secrets.token_urlsafe(32))"`.
   - `LLM_API_KEY` — your OpenRouter key.
7. Click **Apply Blueprint** / **Create Resources**. Docker builds can take
   10–20 minutes the first time (pip + npm).

### Step 3 — DATABASE_URL (important)

Render shows a connection string like
`postgres://darglobal:xxx@host/realestate_ai`. The backend uses SQLAlchemy's
async driver and needs:

```
postgresql+asyncpg://darglobal:<url-encoded-password>@<host>:5432/realestate_ai
```

Change `postgres://` → `postgresql+asyncpg://` and URL-encode special
characters in the password (`@` → `%40`, `#` → `%23`, etc.). If you leave the
`postgres://` scheme the service will fail to boot with an "Invalid request
URI" error.

`render.yaml` does not define `POSTGRES_*` env vars, so set `DATABASE_URL`
explicitly. The `POSTGRES_*` fallback exists for local/Docker runs only.
Use a pgvector-capable database (a Neon free database works); the backend
runs `CREATE EXTENSION IF NOT EXISTS vector` on startup and `/health` now
returns **503** if that fails, so a broken database is detected immediately.

### Step 4 — verify the deployments

- Backend: **Logs** tab should show uvicorn startup and
  `vector_index_ready` / successful `init_db()`.
- Backend health: `https://<backend-url>/health` → `{"status":"ok",...}`.
- Frontend: `https://<frontend-url>/health` → `ok`.

If you renamed either service, update `ALLOWED_ORIGINS` (backend) and
`VITE_API_BASE_URL` (frontend) in the dashboard. `VITE_API_BASE_URL` is baked
into the JS bundle at **build** time, so after changing it run
**Manual Deploy → Clear build cache & deploy** on the frontend.

### Step 5 — initial ingestion on Render

From your machine (reuse the same `ADMIN_API_KEY` you gave Render):

```bash
cd ~/Projects/darglobal-wasalt-ai
API_BASE_URL=https://<backend-url> ./scripts/ingest.sh
```

Or directly:

```bash
curl -X POST https://<backend-url>/api/v1/admin/ingest \
  -H "X-Admin-Key: $ADMIN_API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"source":"both"}'
```

`api/v1/admin/ingest` is the ONLY write endpoint; it is not exposed by the
frontend. Cold starts plus model download make the first ingestion slow — let
it run to completion and watch backend logs.

---

## 2b. Vercel frontend + Render backend (recommended split)

The user's chosen topology is **backend on Render, frontend on Vercel**. The
included `vercel.json` configures the Vite build and SPA rewrites.

1. Push the repo to GitHub (user-side step).
2. In Vercel, **Add New → Project**, import the repository. Vercel reads
   `vercel.json`: `rootDirectory = frontend`, `npm run build`, output `dist`.
3. Add the environment variable `VITE_API_BASE_URL` = the public Render backend
   URL (e.g. `https://darglobal-wasalt-backend.onrender.com`). It is baked into
   the JS bundle at build time, so **redeploy after changing it**.
4. Deploy, then copy the Vercel URL (e.g. `https://your-app.vercel.app`).
5. In Render → backend service → Environment, set `ALLOWED_ORIGINS` to the exact
   Vercel origin (`https://your-app.vercel.app`, no trailing slash) and set
   `LLM_HTTP_REFERER` to the same value. Redeploy the backend, otherwise the
   browser will be blocked by CORS.
6. Verify from an external network:

```bash
curl -s https://<backend>.onrender.com/health
curl -s -H 'Content-Type: application/json' \
  -d '{"message":"Show me apartments in Riyadh"}' \
  https://<backend>.onrender.com/api/v1/chat | head -c 500
```

The API docs are at `https://<backend>.onrender.com/docs`. The frontend needs no
server-side secrets; the admin key and LLM key stay only on Render.

## 3. Environment variable reference

Marked **secret** must never be committed. `PORT` is set by the blueprint so
Render routes to the right container port.

| Variable | Local value | Render value | Notes |
|---|---|---|---|
| `APP_ENV` | `development` | `production` | |
| `LOG_LEVEL` | `INFO` | `INFO` | |
| `API_V1_PREFIX` | `/api/v1` | `/api/v1` | |
| `ALLOWED_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | `https://<frontend-url>` | Exact origins, **no trailing slash** |
| `POSTGRES_USER` | `darglobal` | from DB / `.env` | |
| `POSTGRES_PASSWORD` | generated | from DB / `.env` | **secret** |
| `POSTGRES_DB` | `realestate_ai` | from DB / `.env` | |
| `POSTGRES_HOST` | `db` | from DB / `.env` | |
| `POSTGRES_PORT` | `5432` | from DB / `.env` | |
| `DATABASE_URL` | `postgresql+asyncpg://...@db:5432/...` | your external/Neon URL | **secret**; overrides all `POSTGRES_*` |
| `ADMIN_API_KEY` | generated | **secret** (dashboard) | `X-Admin-Key` header |
| `APP_ACCESS_CODE` | empty / your code | **secret** (dashboard) | If set, public chat requires `X-Access-Code`; UI shows a gate |
| `RATE_LIMIT_PER_MINUTE` | `30` | `30` | |
| `CHAT_RATE_LIMIT_PER_MINUTE` | `12` | `12` | |
| `EMBEDDING_PROVIDER` | `local` | `local` | `local` = fastembed, no key |
| `EMBEDDING_MODEL` | `BAAI/bge-small-en-v1.5` | same | |
| `EMBEDDING_DIM` | `384` | `384` | Must match the model |
| `FASTEMBED_CACHE_PATH` | `/app/data/fastembed` | `/app/data/fastembed` | Ephemeral on Render free |
| `LLM_PROVIDER` | `openrouter` | `openrouter` | |
| `LLM_BASE_URL` | `https://openrouter.ai/api/v1` | same | |
| `LLM_MODEL` | `openai/gpt-4o-mini` | same | |
| `LLM_API_KEY` | your key | **secret** (dashboard) | Required for chat only |
| `GROQ_API_KEY` | your key | **secret** (dashboard) | Optional fallback when OpenRouter fails |
| `LLM_FALLBACK_PROVIDER` | `groq` | `render.yaml` | Fallback provider name |
| `LLM_FALLBACK_BASE_URL` | `https://api.groq.com/openai/v1` | `render.yaml` | Fallback endpoint |
| `LLM_FALLBACK_MODEL` | `openai/gpt-oss-120b` | `render.yaml` | Fallback model |
| `LLM_TEMPERATURE` | `0.2` | `0.2` | |
| `LLM_MAX_TOKENS` | `900` | `900` | |
| `LLM_TIMEOUT_SECONDS` | `60` | `60` | |
| `LLM_HTTP_REFERER` | `https://localhost` | frontend URL | Optional gateway header |
| `LLM_APP_NAME` | `darglobal-wasalt-ai` | same | Optional gateway header |
| `RETRIEVAL_TOP_K` | `8` | `8` | |
| `RETRIEVAL_CANDIDATE_K` | `24` | `24` | |
| `VITE_API_BASE_URL` | `http://localhost:8000` | `https://<backend-url>` | Build-time, not a secret |
| `PORT` | `8000` / `8080` | `8000` / `8080` | Set in compose / blueprint |

Other retrieval, conversation and scraper settings (`RRF_K`,
`CONTEXT_MAX_CHARS`, `MAX_CONVERSATION_TURNS`, `SCRAPER_*`) can be left at the
`.env.example` defaults on both platforms.

---

## 4. Verify from an external network

Use a different network (phone hotspot or another machine), not the same
Wi-Fi, so you exercise the public URL and real CORS behaviour.

```bash
BACKEND=https://<backend-url>
FRONTEND=https://<frontend-url>

curl -s "$BACKEND/health" | python3 -m json.tool
# indexed_chunks must be > 0 and database must be "connected"

curl -s "$BACKEND/api/v1/stats" | python3 -m json.tool
curl -s "$BACKEND/api/v1/sources" | python3 -m json.tool
API_BASE_URL="$BACKEND" ./scripts/smoke_test.sh
```

Then in a browser on that other network:

1. Open `FRONTEND`. The page must load (no blank screen, no CSP errors in the
   browser console).
2. Ask: *"Show me 3 bedroom apartments in Riyadh under 2 million SAR"*.
3. Confirm the answer includes **clickable citations** with a `source` label
   (`darglobal` / `wasalt`) and a real `url`, and that `data_as_of` is shown.
   Citations come from retrieved records, never from the model.
4. Refresh and ask a follow-up to confirm conversations survive.

---

## 5. Persistence across restarts

- **Local:** Postgres volume `postgres_data` + host `./data` survive
  `docker compose down` / `up`. The fastembed model is cached at
  `./data/fastembed`, so restarts do not re-download it.
- **Render:** the database persists independently of the web services. Web
  services are stateless; **free** services spin down after ~15 minutes of
  inactivity and `/app/data` is not a persistent disk, so the embedding model
  is re-downloaded on each cold start (adds latency, not data loss). To avoid
  that on a paid plan, attach a Render Disk and mount it at `/app/data`.
- Render's **free Postgres expires after 30 days**; upgrade to a paid plan
  before relying on it long-term, or point `DATABASE_URL` at Neon/external
  Postgres.

---

## 6. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `extension "vector" is not available` or `must be superuser to CREATE EXTENSION` at startup | The DB user cannot create the pgvector extension. Render managed Postgres may not permit it. Use a pgvector-capable external Postgres (e.g. Neon free tier): enable the extension in that DB and paste its URL into `DATABASE_URL` with the `postgresql+asyncpg://` scheme. Locally the `pgvector/pgvector:pg16` image already has it. Verify with `psql -c '\dx'`. |
| `Invalid request URI` / driver errors on boot | `DATABASE_URL` uses `postgres://`. Change the scheme to `postgresql+asyncpg://` and URL-encode the password. |
| First ingest hangs or times out downloading a model | fastembed fetches `BAAI/bge-small-en-v1.5` over HTTPS on first use. Allow outbound HTTPS; allow several minutes on a cold start. Check `FASTEMBED_CACHE_PATH` and backend logs. Once cached locally it is fast. |
| Browser: `CORS policy: No 'Access-Control-Allow-Origin'` | Set `ALLOWED_ORIGINS` to the **exact** frontend origin, no trailing slash, then redeploy/restart the backend. Local `http://localhost:8080` should be added for the built frontend if you test CORS directly. |
| Frontend fails with `mkdir() "/tmp/nginx/client_temp" failed` on Render | Render mounts an empty tmpfs at `/tmp`; fixed in the image by keeping nginx temp/pid paths under `/app/nginx-tmp`. Pull the latest commit and redeploy. |
| Chat returns a configuration error while search works | `LLM_API_KEY` is missing or still the placeholder. Set a real OpenRouter key on the backend and redeploy. |
| `401` / `{"detail":...}` from `/api/v1/admin/ingest` | Wrong `X-Admin-Key`. Use the exact `ADMIN_API_KEY` from `.env` / Render dashboard. |
| Frontend loads but calls `localhost:8000` in production | `VITE_API_BASE_URL` is baked at build time. Set it to the public backend URL and **clear build cache & redeploy** the frontend. |
| Very slow first request on Render | Free web services sleep after inactivity. Expect a cold start of tens of seconds; upgrade to a paid plan or keep the service warm. Health checks alone do not guarantee warmth. |
| `/health` shows `indexed_chunks: 0` | No successful ingestion yet. Run `scripts/ingest.sh` (or the curl equivalent) and re-check. |

---

## 7. Honesty about the free tier

Render's free web services sleep and have limited RAM/CPU, the free Postgres
instance expires after 30 days, and there is no persistent disk on free
services. This setup is fine for a demo/prototype, but a production deployment
should use paid services, a durable pgvector-capable database, and a Render
Disk (or external object storage) for the embedding cache. The public URL is
yours to create in your Render account; this repository cannot create it for
you.
