"""Per-node span timing for the LangGraph agent pipeline (O6 of the observability
roadmap, docs/OBSERVABILITY_PLAN.md).

The agent already streams one `agent_step` SSE per node; O6 adds *how long each
node took*, so the trace shows where latency actually goes — a slow grade vs a
slow web fallback vs a slow generate — not just which nodes ran. The breakdown
rides the live `agent_step` events (`ms`) and the terminal `done` event (`spans`).

Content-free per LOGGING_SPEC §6: node names and millisecond durations only,
never the query text or any chunk content.
"""
from __future__ import annotations

import json
import time

# Node id (LangGraph) → the human step name the frontend rail/diagram renders.
STEP_MAP = {
    "router":    "routing",
    "decompose": "decomposing",
    "retrieve":  "retrieving",
    "grade":     "grading",
    "rewrite":   "rewriting",
}


def sse(obj: dict) -> str:
    return f"data: {json.dumps(obj)}\n\n"


class SpanTimer:
    """Collects the ordered per-node durations of one agent run.

    `lap(name)` closes the span since the previous lap (or since construction)
    and returns its ms — used inside the LangGraph stream loop, where receiving a
    node's update means that node just finished. `add(name, ms)` records a span
    measured directly, for the web fallback and the generate stream, which run
    outside that loop. `spans()` is the breakdown for the `done` event.
    """

    def __init__(self) -> None:
        self._last = time.monotonic()
        self._spans: list[dict] = []

    def lap(self, name: str) -> int:
        now = time.monotonic()
        ms = round((now - self._last) * 1000)
        self._last = now
        self._spans.append({"node": name, "ms": ms})
        return ms

    def add(self, name: str, ms: int) -> None:
        self._spans.append({"node": name, "ms": ms})

    def spans(self) -> list[dict]:
        return list(self._spans)
