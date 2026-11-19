"""Per-phase request timing (Server-Timing) for latency attribution.

Wall-clock phase recorder so latency can be attributed to a phase — embed,
retrieve, LLM first token — without attaching a profiler to production.
Standard ``Server-Timing`` headers on JSON responses and a ``timing`` SSE
frame on streams; browsers surface both in DevTools > Network > Timing.

Budgets are enforced by ``scripts/perf_bench.py`` (exits non-zero on breach);
this module is what tells you *which* phase blew the budget.

Not a secrets channel: phase names and millisecond durations only.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any


class PhaseTimer:
    """Records named wall-clock phases and formats them as Server-Timing."""

    def __init__(self) -> None:
        self._t0 = time.perf_counter()
        self._phases: dict[str, float] = {}

    @contextmanager
    def phase(self, name: str) -> Iterator[None]:
        """Time a synchronous-or-await block: ``with timer.phase("embed"): ...``."""
        start = time.perf_counter()
        try:
            yield
        finally:
            self.record(name, (time.perf_counter() - start) * 1000)

    def record(self, name: str, ms: float) -> None:
        """Record a pre-measured duration (for spans that cross yields)."""
        self._phases[name] = ms

    @property
    def total_ms(self) -> float:
        return (time.perf_counter() - self._t0) * 1000

    @property
    def phases(self) -> dict[str, float]:
        return dict(self._phases)

    def header(self) -> str:
        """``Server-Timing`` value: each phase plus an explicit total."""
        parts = [f"{name};dur={ms:.1f}" for name, ms in self._phases.items()]
        parts.append(f"total;dur={self.total_ms:.1f}")
        return ", ".join(parts)

    def frame_data(self) -> dict[str, Any]:
        """Payload for the SSE ``timing`` frame."""
        return {**{k: round(v, 1) for k, v in self._phases.items()},
                "total": round(self.total_ms, 1)}


def merge_header(existing: str | None, value: str) -> str:
    return f"{existing}, {value}" if existing else value
