# Performance log

Measure-first workflow: **baseline → identify → fix (one variable) → verify → guard.**
Numbers come from `scripts/perf_bench.py`, which prints JSON to stdout and exits 1
when a budget is breached. Live runs need `APP_ACCESS_CODE` set (env or repo `.env`).

```bash
APP_ACCESS_CODE=... .venv/bin/python scripts/perf_bench.py https://darglobal-wasalt-backend.onrender.com
```

Per-phase attribution (which phase blew the budget) comes from the `Server-Timing`
header on `/search` and non-stream `/chat`, and from the SSE `timing` frame on
streaming chat. Regression guard: `backend/tests/test_observability.py`.

Budgets (p95): health ≤ 200 ms, properties ≤ 300 ms, search ≤ 1500 ms,
chat (full LLM) ≤ 8000 ms, stream TTFB ≤ 4000 ms.

## Baseline — live Render, commit `4eefb60` (2026-01)

| Endpoint | p50 | p95 | max |
| --- | ---: | ---: | ---: |
| GET /health | 352 | 376 | 384 |
| GET /api/v1/properties | 369 | 446 | 557 |
| POST /search (embed+retrieve) | 1677 | **2312** | 2312 |
| POST /chat (full LLM) | 3573 | 6992 | 6992 |
| POST /chat (stream, TTFB) | 2431 | 2806 | 2806 |
| POST /chat (stream, total) | 3202 | 3604 | 3604 |

Budget gate **FAILED** on health (376 > 200), properties (446 > 300) and search
(2312 > 1500). Bundle was already inside budget: JS 58 kB gz, CSS 4.9 kB gz,
frontend FCP 584 ms (Playwright ×5).

Known confounders before blaming app code:

- Render free tier shows 0.5–1.8 s TTFB even on `/api/v1/access` (no DB), so a
  large slice of every p50 is platform noise / cold starts, not request handling.
- Local runs are Neon-RTT-bound (user → us-west-2 ≈ 300 ms per DB roundtrip);
  a local search is 2–7 s for reasons that do not exist next to the DB.

## Attribution run — Docker Compose, current code (2026-11-19)

Ran the same bench against the local three-container stack (backend + pgvector
DB + frontend), so app code sits next to the database and Render free-tier noise
is removed. Containers started from a rebuilt backend image (instrumented code).
Reference data: `/tmp/perf_docker_bench.txt` (first run), `/tmp/perf_docker_bench2.txt` (warm run).

| Endpoint | p50 | p95 | phase p50 |
| --- | ---: | ---: | --- |
| GET /health | 3–4 | 7–10 | db 1–2 |
| GET /api/v1/properties | 4 | 6 | db 1 |
| POST /search | 308–425 | 616–1906 | embed 137–276, retrieve 192–199 |
| POST /chat (full LLM) | 2824–4294 | 3430–5116 | embed 158, retrieve 269, llm 2376–2451 |
| POST /chat (stream, TTFB) | 1429–1831 | 1558–2496 | — |
| POST /chat (stream, total) | 1670–2030 | 1789–2760 | retrieve 423, llm_ttfb 859 |

First run's search p95 1906 ms and chat retrieve 1502 ms were cold-start /
single-CPU contention outliers: the warm run dropped search p95 to 616 ms and
chat retrieve to 269 ms with identical code. Warm run passes every budget.

**Conclusion: no application-level bottleneck explains the live budget failures.**
`/health` (3 DB roundtrips) and `/properties` complete in 3–10 ms when DB RTT is
~1 ms, versus 350–450 ms live — the live numbers are Render platform / cold-start
noise, not app code. Search is embed- (137–276 ms, local CPU model) plus DB-bound;
chat is LLM-bound (~2.4 s of a ~2.8 s total). No code change made to chase those.

## Attempts

- **Instrumentation only** (kept): added `PhaseTimer` (`Server-Timing` header +
  SSE `timing` frame), split chat `retrieve` into `embed` + `retrieve` phases,
  and added `db` phases to `/health` and `/properties`. Fixed a missing
  `PhaseTimer` import in `routers/properties.py` that made `/properties` return
  500 (caught by a live curl, not by unit tests — guard added).
- **Lowering `min_semantic_similarity` / changing relaxation** (not attempted):
  the 0.65 floor and filter-relaxation retries are retrieval-quality decisions,
  not perf fixes; changing them risks grounding accuracy for a few hundred ms.
  Left as-is.
- **LLM / model changes** (not attempted): the LLM is ~85% of chat time but is an
  external OpenRouter call; any change trades answer quality for latency.

## Open questions

- Confirm with user whether Render needs a manual redeploy before re-running the
  live bench with phase attribution (deployment is user-managed).
- Live budgets should eventually be recalibrated to the Render free-tier platform
  floor; comparing them to sub-second app budgets produces false failures.
