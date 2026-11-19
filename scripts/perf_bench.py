#!/usr/bin/env python3
"""Latency benchmark for the backend. Run against any live instance:

    python scripts/perf_bench.py http://127.0.0.1:8000

Measures p50/p95 for health, properties, search (embed+retrieve) and chat
(full LLM, stream + non-stream), plus per-phase attribution from the
Server-Timing header / SSE `timing` frame. Prints JSON to stdout so runs can
be compared over time (see PERF.md).
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

import httpx


def access_code() -> str:
    """APP_ACCESS_CODE from the environment, or the repo .env as fallback."""
    code = os.environ.get("APP_ACCESS_CODE", "").strip()
    if code:
        return code
    env_file = Path(__file__).resolve().parent.parent / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith("APP_ACCESS_CODE="):
                return line.split("=", 1)[1].strip()
    return ""

PROPS = 30
SEARCH = 10
CHAT = 5
STREAM = 5

# SSE timing frame: one-line JSON payload after `event: timing`.
TIMING_RE = re.compile(r"event: timing\ndata: (\{[^\n]*\})")


def parse_server_timing(value: str) -> dict[str, float]:
    """Parse a Server-Timing header into {metric: milliseconds}."""
    out: dict[str, float] = {}
    for part in value.split(","):
        name, _, params = part.strip().partition(";")
        for param in params.split(";"):
            param = param.strip()
            if param.startswith("dur="):
                try:
                    out[name.strip()] = float(param[4:])
                except ValueError:
                    continue
    return out


def pct(samples: list[float], p: float) -> float:
    if not samples:
        return 0.0
    ordered = sorted(samples)
    idx = min(len(ordered) - 1, round((p / 100) * (len(ordered) - 1)))
    return round(ordered[idx] * 1000)  # ms


def pct_ms(samples: list[float], p: float) -> float:
    """Percentile of samples that are already milliseconds (Server-Timing)."""
    if not samples:
        return 0.0
    ordered = sorted(samples)
    idx = min(len(ordered) - 1, round((p / 100) * (len(ordered) - 1)))
    return round(ordered[idx])


def summarize(name: str, samples: list[float], phases: dict[str, list[float]] | None = None) -> dict:
    entry = {
        "endpoint": name,
        "n": len(samples),
        "p50_ms": pct(samples, 50),
        "p95_ms": pct(samples, 95),
        "max_ms": pct(samples, 100),
    }
    if phases:
        entry["phases_p50_ms"] = {k: pct_ms(v, 50) for k, v in sorted(phases.items()) if v}
    return entry


def add_phases(store: dict[str, list[float]], header: str) -> None:
    for name, ms in parse_server_timing(header).items():
        store.setdefault(name, []).append(ms)


def main() -> None:
    base = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://127.0.0.1:8000"
    headers = {"X-Access-Code": access_code()}
    results = []
    with httpx.Client(base_url=base, timeout=120.0, headers=headers) as client:
        # warm-up (JIT/pool/connection reuse)
        client.get("/health")
        client.post("/api/v1/search", json={"query": "apartment in Riyadh", "top_k": 5})

        health_samples: list[float] = []
        health_phases: dict[str, list[float]] = {}
        for _ in range(PROPS):
            t0 = time.perf_counter()
            resp = client.get("/health")
            health_samples.append(time.perf_counter() - t0)
            add_phases(health_phases, resp.headers.get("server-timing", ""))
        results.append(summarize("GET /health", health_samples, health_phases))

        props_samples: list[float] = []
        props_phases: dict[str, list[float]] = {}
        for _ in range(PROPS):
            t0 = time.perf_counter()
            resp = client.get("/api/v1/properties")
            props_samples.append(time.perf_counter() - t0)
            add_phases(props_phases, resp.headers.get("server-timing", ""))
        results.append(summarize("GET /api/v1/properties", props_samples, props_phases))

        search_samples: list[float] = []
        search_phases: dict[str, list[float]] = {}
        for _ in range(SEARCH):
            t0 = time.perf_counter()
            resp = client.post(
                "/api/v1/search", json={"query": "waterfront villa Jeddah", "top_k": 8}
            )
            search_samples.append(time.perf_counter() - t0)
            add_phases(search_phases, resp.headers.get("server-timing", ""))
        results.append(
            summarize("POST /api/v1/search (embed+retrieve)", search_samples, search_phases)
        )

        chat_samples: list[float] = []
        chat_phases: dict[str, list[float]] = {}
        for _ in range(CHAT):
            t0 = time.perf_counter()
            resp = client.post(
                "/api/v1/chat",
                json={"message": "What waterfront villas do you have in Jeddah?"},
            )
            chat_samples.append(time.perf_counter() - t0)
            add_phases(chat_phases, resp.headers.get("server-timing", ""))
        results.append(summarize("POST /api/v1/chat (full LLM)", chat_samples, chat_phases))

        stream_total, stream_ttfb = [], []
        stream_phases: dict[str, list[float]] = {}
        for _ in range(STREAM):
            t0 = time.perf_counter()
            ttfb = None
            body = ""
            with client.stream(
                "POST",
                "/api/v1/chat",
                json={"message": "List available compounds in Riyadh", "stream": True},
            ) as resp:
                for chunk in resp.iter_bytes():
                    if ttfb is None:
                        ttfb = time.perf_counter() - t0
                    body += chunk.decode("utf-8", errors="replace")
            stream_ttfb.append(ttfb or 0.0)
            stream_total.append(time.perf_counter() - t0)
            match = TIMING_RE.search(body)
            if match:
                for name, ms in json.loads(match.group(1)).items():
                    stream_phases.setdefault(name, []).append(float(ms))
        results.append(summarize("POST /api/v1/chat (stream, TTFB)", stream_ttfb))
        results.append(
            summarize("POST /api/v1/chat (stream, total)", stream_total, stream_phases)
        )

    print(json.dumps({"base": base, "results": results}, indent=2))

    # Budget gate (exit 1 on breach) — p95 thresholds in ms.
    budgets = {
        "GET /health": 200,
        "GET /api/v1/properties": 300,
        "POST /api/v1/search (embed+retrieve)": 1500,
        "POST /api/v1/chat (full LLM)": 15000,
        "POST /api/v1/chat (stream, TTFB)": 6000,
    }
    failures = [
        f"{r['endpoint']}: p95 {r['p95_ms']}ms > {budgets[r['endpoint']]}ms"
        for r in results
        if r["endpoint"] in budgets and r["p95_ms"] > budgets[r["endpoint"]]
    ]
    if failures:
        print("BUDGET FAILED:", *failures, sep="\n  ", file=sys.stderr)
        sys.exit(1)
    print("budgets: OK", file=sys.stderr)


if __name__ == "__main__":
    main()
