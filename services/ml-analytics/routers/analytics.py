"""FastAPI router — /health, /track, /stats, /events/recent."""
from __future__ import annotations

import json
import os
from typing import Any

import asyncpg
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

router = APIRouter()

_pool: asyncpg.Pool | None = None


async def init_pool(db_url: str) -> None:
    global _pool
    _pool = await asyncpg.create_pool(db_url, min_size=1, max_size=5, ssl="require")


async def close_pool() -> None:
    if _pool:
        await _pool.close()


def _no_db() -> JSONResponse:
    return JSONResponse({"error": "Database not configured"}, status_code=503)


@router.get("/health")
async def health():
    return {"status": "ok", "service": "ml-analytics", "db": _pool is not None}


class TrackEvent(BaseModel):
    type: str
    path: str = ""
    session_id: str = ""
    referrer: str = ""
    duration_ms: int = 0
    meta: dict[str, Any] = {}


@router.post("/track")
async def track_event(req: TrackEvent, request: Request):
    if not _pool:
        return _no_db()
    country = request.headers.get("CF-IPCountry", "")
    async with _pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO events (type, path, session_id, country, referrer, duration_ms, meta)
               VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb)""",
            req.type, req.path, req.session_id, country, req.referrer,
            req.duration_ms, json.dumps(req.meta),
        )
    return {"ok": True}


@router.get("/stats")
async def get_stats():
    if not _pool:
        return _no_db()
    async with _pool.acquire() as conn:
        active_now = await conn.fetchval(
            "SELECT COUNT(DISTINCT session_id) FROM events "
            "WHERE created_at > NOW() - INTERVAL '5 minutes'"
        )
        today_count = await conn.fetchval(
            "SELECT COUNT(*) FROM events "
            "WHERE created_at >= DATE_TRUNC('day', NOW() AT TIME ZONE 'UTC')"
        )
        per_minute = await conn.fetch(
            """SELECT TO_CHAR(DATE_TRUNC('minute', created_at), 'HH24:MI') AS minute,
                      COUNT(*) AS count
               FROM events
               WHERE created_at > NOW() - INTERVAL '30 minutes'
               GROUP BY DATE_TRUNC('minute', created_at)
               ORDER BY DATE_TRUNC('minute', created_at)"""
        )
        top_pages = await conn.fetch(
            """SELECT path, COUNT(*) AS count
               FROM events
               WHERE created_at >= DATE_TRUNC('day', NOW() AT TIME ZONE 'UTC')
                 AND path != ''
               GROUP BY path
               ORDER BY count DESC
               LIMIT 10"""
        )
        by_type = await conn.fetch(
            """SELECT type, COUNT(*) AS count
               FROM events
               WHERE created_at >= DATE_TRUNC('day', NOW() AT TIME ZONE 'UTC')
               GROUP BY type
               ORDER BY count DESC"""
        )
        top_countries = await conn.fetch(
            """SELECT country, COUNT(*) AS count
               FROM events
               WHERE created_at >= DATE_TRUNC('day', NOW() AT TIME ZONE 'UTC')
                 AND country != ''
               GROUP BY country
               ORDER BY count DESC
               LIMIT 8"""
        )
        qsr_row = await conn.fetchrow(
            """SELECT
                 COUNT(*) FILTER (WHERE (meta->>'success')::boolean = true) AS success,
                 COUNT(*) AS total
               FROM events
               WHERE type = 'query_run'
                 AND created_at >= DATE_TRUNC('day', NOW() AT TIME ZONE 'UTC')"""
        )
        funnel = await conn.fetchrow(
            """SELECT
                 COUNT(*) FILTER (WHERE type = 'page_view') AS page_view,
                 COUNT(*) FILTER (WHERE type = 'tool_open') AS tool_open,
                 COUNT(*) FILTER (WHERE type = 'query_run') AS query_run
               FROM events
               WHERE created_at >= DATE_TRUNC('day', NOW() AT TIME ZONE 'UTC')"""
        )
    qsr_total = int(qsr_row["total"] or 0)
    qsr = round(int(qsr_row["success"] or 0) / qsr_total, 3) if qsr_total else None
    return {
        "active_now": int(active_now or 0),
        "today_count": int(today_count or 0),
        "per_minute": [dict(r) for r in per_minute],
        "top_pages": [dict(r) for r in top_pages],
        "by_type": [dict(r) for r in by_type],
        "top_countries": [dict(r) for r in top_countries],
        "query_success_rate": qsr,
        "funnel": {
            "page_view": int(funnel["page_view"] or 0),
            "tool_open": int(funnel["tool_open"] or 0),
            "query_run": int(funnel["query_run"] or 0),
        },
    }


@router.get("/events/recent")
async def get_recent_events():
    if not _pool:
        return _no_db()
    async with _pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT id, created_at::TEXT AS created_at, type, path, country,
                      session_id, duration_ms, meta::TEXT AS meta
               FROM events
               ORDER BY created_at DESC
               LIMIT 50"""
        )
    return {"events": [dict(r) for r in rows]}


@router.get("/events/session/{session_id}")
async def get_session_events(session_id: str):
    if not _pool:
        return _no_db()
    async with _pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT id, created_at::TEXT AS created_at, type, path,
                      duration_ms, meta::TEXT AS meta
               FROM events
               WHERE session_id = $1
               ORDER BY created_at ASC""",
            session_id,
        )
    return {"events": [dict(r) for r in rows]}