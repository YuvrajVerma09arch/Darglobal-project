# Neon Postgres setup (external database for Render backend)

The Render Blueprint in this repo creates **only the backend web service**. Use
Neon for the database because it supports the `vector` extension that pgvector
needs. Follow these steps before deploying the backend.

## 1. Create the Neon project

1. Sign up / log in at <https://console.neon.tech>.
2. **New Project**.
   - Name: `darglobal-wasalt-ai`
   - Region: pick the one closest to your Render region (Render Blueprint uses
     **Oregon**, so `US West / Oregon` is ideal).
   - Postgres version: 16 or 17.
3. Once created, note the default database name (often `neondb`) or create a new
   one named `realestate_ai`. Create a dedicated role if you like; the default
   `neondb_owner` is fine for this assessment.

## 2. Enable pgvector

Open Neon's **SQL Editor** and run:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
SELECT extname FROM pg_extension WHERE extname = 'vector';
```

The second query must return one row with `vector`. If not, stop — the backend
cannot index embeddings without it.

## 3. Copy the connection string

In Neon → **Connection Details / Connect**:

- Choose the **direct** connection (not the pooled `-pooler` host) for the app's
  startup `CREATE EXTENSION` / `CREATE TABLE` calls.
- Copy the connection string. It looks like:

```
postgresql://neondb_owner:<password>@ep-xxxxxx.us-west-2.aws.neon.tech/realestate_ai?sslmode=require
```

## 4. Convert it for SQLAlchemy asyncpg

Change **only** the scheme from `postgresql://` to `postgresql+asyncpg://`.
Keep the host, user, password, database and `?sslmode=require` unchanged:

```
postgresql+asyncpg://neondb_owner:<password>@ep-xxxxxx.us-west-2.aws.neon.tech/realestate_ai?sslmode=require
```

You can leave Neon's `?sslmode=require&channel_binding=require` exactly as-is —
the backend strips those params and translates `sslmode=require` into asyncpg's
`ssl=True` connect argument. (Older builds passed `sslmode` straight to asyncpg
and crashed with `TypeError: connect() got an unexpected keyword argument 'sslmode'`.)

If the password contains special characters, URL-encode them:
`@` → `%40`, `#` → `%23`, `/` → `%2F`, `%` → `%25`, `:` → `%3A`.

## 5. Set it on Render

Render dashboard → **darglobal-wasalt-backend** → **Environment** → edit/add:

| Key | Value |
|---|---|
| `DATABASE_URL` | the converted `postgresql+asyncpg://...` string from step 4 |

Also confirm these are set (the Blueprint prompts for the `sync:false` ones):

| Key | Notes |
|---|---|
| `ADMIN_API_KEY` | your generated secret |
| `LLM_API_KEY` | OpenRouter key |
| `GROQ_API_KEY` | fallback key |
| `APP_ACCESS_CODE` | the code you will email to the assessor |
| `ALLOWED_ORIGINS` | exact Vercel frontend origin, no trailing slash |

Save, then **Manual Deploy → Deploy latest commit**.

## 6. Verify

In the backend logs you must see:

```
database_target_configured  scheme=postgresql+asyncpg  host=ep-xxxxxx...  database=realestate_ai
vector_index_ready
database_ready
```

Then:

```bash
curl https://<your-backend>.onrender.com/health
# {"status":"ok","database":"connected","indexed_chunks":57,...}
```

If `indexed_chunks` is `0`, run the initial ingestion:

```bash
curl -X POST https://<your-backend>.onrender.com/api/v1/admin/ingest \
  -H "X-Admin-Key: $ADMIN_API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"source":"both"}'
```

## Notes

- Neon free tier suspends idle projects; the first request after inactivity can
  be slow. That is acceptable for this assessment.
- Do not use Neon's `-pooler` host unless you also configure pgbouncer mode; the
  direct host is simplest and works with SQLAlchemy asyncpg.
- Local Docker development still uses `pgvector/pgvector:pg16` from
  `docker-compose.yml`; it does not depend on Neon.
