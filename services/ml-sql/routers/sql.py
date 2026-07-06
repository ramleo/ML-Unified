"""FastAPI router — /health, /sql/schema, /sql/upload, /sql/connect, /sql/query."""
from __future__ import annotations

import json
import os
import shutil
import time
import uuid
from pathlib import Path
from typing import AsyncGenerator

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from ._explain import (
    _sse, build_explain_prompt, detect_visualization, stream_explanation,
)
from ._execute import UnsafeQueryError, execute_pg, execute_sqlite, validate_sql, result_to_dict, mask_sensitive_columns
from ._generate import generate_sql, get_provider_cfg, sanitize_question
from ._schema import (
    DBSchema, load_pg_schema, load_sqlite_schema, schema_to_dict, schema_to_prompt_text,
)

router = APIRouter()

CHINOOK_PATH = Path(__file__).parent.parent / "data" / "chinook.db"
_UPLOAD_DIR  = Path("/tmp/ml_sql_sessions")
_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# in-memory session store: db_ref → {type, path|conn_str, schema}
_sessions: dict[str, dict] = {}

# Global rate limiter — sliding window of query timestamps
_recent_queries: list[float] = []
_RATE_LIMIT = 30  # max queries per 60 seconds globally


def _check_rate_limit() -> bool:
    now = time.time()
    cutoff = now - 60.0
    _recent_queries[:] = [t for t in _recent_queries if t > cutoff]
    if len(_recent_queries) >= _RATE_LIMIT:
        return False
    _recent_queries.append(now)
    return True


async def _preload_chinook() -> None:
    if "chinook" not in _sessions and CHINOOK_PATH.exists():
        schema = await load_sqlite_schema(str(CHINOOK_PATH))
        _sessions["chinook"] = {"type": "sqlite", "path": str(CHINOOK_PATH), "schema": schema}


# ── Health ────────────────────────────────────────────────────────────────────

@router.get("/health")
async def health():
    await _preload_chinook()
    chinook = _sessions.get("chinook")
    tables  = len(chinook["schema"].tables) if chinook else 0
    return {"status": "ok", "demo_db": "chinook.db", "tables": tables}


# ── Schema ────────────────────────────────────────────────────────────────────

@router.get("/sql/schema")
async def get_schema(db_ref: str = "chinook"):
    await _preload_chinook()
    session = _sessions.get(db_ref)
    if not session:
        return JSONResponse({"error": f"Unknown db_ref: {db_ref}"}, status_code=404)
    return schema_to_dict(session["schema"])


# ── Upload SQLite ─────────────────────────────────────────────────────────────

@router.post("/sql/upload")
async def upload_db(file: UploadFile = File(...)):
    if not file.filename or not file.filename.endswith((".db", ".sqlite", ".sqlite3")):
        return JSONResponse({"error": "Upload a .db / .sqlite file"}, status_code=400)
    db_ref  = f"upload_{uuid.uuid4().hex[:8]}"
    db_path = _UPLOAD_DIR / f"{db_ref}.db"
    with db_path.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    try:
        schema = await load_sqlite_schema(str(db_path))
    except Exception as e:
        db_path.unlink(missing_ok=True)
        return JSONResponse({"error": f"Could not read DB: {e}"}, status_code=422)
    _sessions[db_ref] = {"type": "sqlite", "path": str(db_path), "schema": schema}
    return {"db_ref": db_ref, "schema": schema_to_dict(schema)}


# ── Connect PostgreSQL ────────────────────────────────────────────────────────

class ConnectRequest(BaseModel):
    conn_str: str


@router.post("/sql/connect")
async def connect_pg(req: ConnectRequest):
    try:
        schema = await load_pg_schema(req.conn_str)
    except Exception as e:
        return JSONResponse({"error": f"Connection failed: {e}"}, status_code=422)
    db_ref = f"pg_{uuid.uuid4().hex[:8]}"
    _sessions[db_ref] = {"type": "postgresql", "conn_str": req.conn_str, "schema": schema}
    return {"db_ref": db_ref, "schema": schema_to_dict(schema)}


# ── Query (SSE pipeline) ──────────────────────────────────────────────────────

class QueryRequest(BaseModel):
    question: str
    provider:  str = "groq"
    db_ref:    str = "chinook"


@router.post("/sql/query")
async def query_sql(req: QueryRequest):
    return StreamingResponse(
        _run_pipeline(req),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _run_pipeline(req: QueryRequest) -> AsyncGenerator[str, None]:
    if not _check_rate_limit():
        yield _sse({"type": "error", "text": "Rate limit reached. Please wait a moment and try again."})
        yield _sse({"type": "done"})
        return

    await _preload_chinook()
    session = _sessions.get(req.db_ref)
    if not session:
        yield _sse({"type": "error", "text": f"Unknown db_ref: {req.db_ref}"})
        yield _sse({"type": "done"})
        return

    cfg = get_provider_cfg(req.provider)
    key = os.environ.get(cfg["env"], "")
    if not key:
        yield _sse({"type": "error", "text": f"{cfg['env']} not configured on this server."})
        yield _sse({"type": "done"})
        return

    # Sanitize user question — strip prompt injection attempts
    safe_question = sanitize_question(req.question)

    schema: DBSchema = session["schema"]
    schema_text = schema_to_prompt_text(schema, safe_question)
    yield _sse({"type": "schema_loaded", "tables": len(schema.tables),
                "columns": sum(len(t.columns) for t in schema.tables.values())})

    # Retry loop: generate SQL + execute (max 3 attempts total)
    sql        = None
    result     = None
    last_error = None
    prev_sql   = None

    for attempt in range(1, 4):
        if attempt > 1:
            yield _sse({"type": "retry", "attempt": attempt, "error": last_error})

        # --- generate SQL ---
        try:
            sql = await generate_sql(
                safe_question, schema_text, req.provider, key, prev_sql, last_error
            )
            validate_sql(sql)
        except UnsafeQueryError as e:
            last_error = str(e)
            prev_sql = sql
            continue
        except Exception as e:
            last_error = f"SQL generation error: {e}"
            prev_sql = sql
            continue

        yield _sse({"type": "sql_generated", "sql": sql})

        # --- execute ---
        try:
            if session["type"] == "sqlite":
                result = await execute_sqlite(session["path"], sql)
            else:
                result = await execute_pg(session["conn_str"], sql)
            break  # success
        except Exception as e:
            last_error = f"Execution error: {e}"
            prev_sql = sql
            result = None
            continue

    if result is None:
        yield _sse({"type": "error", "text": f"Failed after 3 attempts. Last: {last_error}"})
        yield _sse({"type": "done"})
        return

    # Mask sensitive columns before sending to client or LLM
    safe_result = mask_sensitive_columns(result)

    yield _sse({"type": "results", **result_to_dict(safe_result)})

    # --- visualization ---
    viz = detect_visualization(safe_result.columns, safe_result.rows)
    if viz:
        yield _sse({"type": "visualization", **viz})

    # --- explanation (streaming) ---
    prompt = build_explain_prompt(safe_question, sql, safe_result.columns, safe_result.rows[:10])
    async for chunk in stream_explanation(prompt, req.provider, key):
        yield chunk