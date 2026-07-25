"""Aggregate usage stats for the RAG tools — in-memory only, by design. This
Space's disk doesn't survive a restart (proven separately via the Document
Intelligence corrections-store incident), so anything claiming to persist
here would repeat that same mistake. Public, aggregate-only: never exposes
individual queries, filenames, or document content — just counts/averages."""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from fastapi import APIRouter

router = APIRouter()


@dataclass
class _AnalyticsState:
    started_at: float = field(default_factory=time.time)
    uploads_by_type: dict[str, int] = field(default_factory=dict)
    query_count: int = 0
    cache_hits: int = 0
    total_latency_ms: float = 0.0
    provider_counts: dict[str, int] = field(default_factory=dict)


_state = _AnalyticsState()


def record_upload(file_type: str) -> None:
    _state.uploads_by_type[file_type] = _state.uploads_by_type.get(file_type, 0) + 1


def record_query(latency_ms: float, cache_hit: bool, provider: str | None) -> None:
    _state.query_count += 1
    _state.total_latency_ms += latency_ms
    if cache_hit:
        _state.cache_hits += 1
    elif provider:
        _state.provider_counts[provider] = _state.provider_counts.get(provider, 0) + 1


@router.get("/analytics")
def get_analytics() -> dict:
    avg_latency = round(_state.total_latency_ms / _state.query_count) if _state.query_count else 0
    cache_hit_rate = round(_state.cache_hits / _state.query_count, 3) if _state.query_count else 0.0
    return {
        "since": _state.started_at,
        "uploads": {**_state.uploads_by_type, "total": sum(_state.uploads_by_type.values())},
        "queries": {
            "count": _state.query_count,
            "avg_latency_ms": avg_latency,
            "cache_hit_rate": cache_hit_rate,
        },
        "provider_mix": dict(_state.provider_counts),
    }
