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
from ._execute import (
    UnsafeQueryError, execute_pg, execute_sqlite, execute_mysql, execute_duckdb, execute_mssql,
    validate_sql, result_to_dict, mask_sensitive_columns,
    paginate_sql, paginate_mssql_sql, count_rows_sqlite,
)
from ._generate import generate_sql, get_provider_cfg, sanitize_question
from ._schema import (
    DBSchema, load_pg_schema, load_sqlite_schema, load_mysql_schema, load_duckdb_schema,
    schema_to_dict, schema_to_prompt_text,
)
from ._schema_mssql import load_mssql_schema

router = APIRouter()

CHINOOK_PATH  = Path(__file__).parent.parent / "data" / "chinook.db"
_UPLOAD_DIR   = Path("/tmp/ml_sql_sessions")
_SESSION_FILE = _UPLOAD_DIR / "index.json"
_SESSION_TTL  = 86_400  # 24 hours
_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# in-memory session store: db_ref → {type, path|conn_str, schema, created_at}
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


def _save_session_index() -> None:
    """Persist file-based session metadata to disk so they survive in-process resets."""
    index = {
        ref: {"type": s["type"], "path": s.get("path", ""), "created_at": s.get("created_at", 0)}
        for ref, s in _sessions.items()
        if s["type"] in ("sqlite", "duckdb") and ref != "chinook"
    }
    try:
        _SESSION_FILE.write_text(json.dumps(index))
    except OSError:
        pass


async def _restore_sessions() -> None:
    """On startup, reload SQLite sessions from the index whose files still exist."""
    if not _SESSION_FILE.exists():
        return
    try:
        index = json.loads(_SESSION_FILE.read_text())
    except (OSError, json.JSONDecodeError):
        return
    cutoff = time.time() - _SESSION_TTL
    for ref, meta in index.items():
        if meta.get("created_at", 0) < cutoff:
            continue  # TTL expired
        path = meta.get("path", "")
        if path and Path(path).exists() and ref not in _sessions:
            try:
                stype = meta.get("type", "sqlite")
                if stype == "duckdb":
                    schema = await load_duckdb_schema(path)
                else:
                    schema = await load_sqlite_schema(path)
                _sessions[ref] = {"type": stype, "path": path,
                                  "schema": schema, "created_at": meta["created_at"]}
            except Exception:
                pass


async def _preload_chinook() -> None:
    if "chinook" not in _sessions and CHINOOK_PATH.exists():
        schema = await load_sqlite_schema(str(CHINOOK_PATH))
        _sessions["chinook"] = {"type": "sqlite", "path": str(CHINOOK_PATH),
                                "schema": schema, "created_at": time.time()}
    await _restore_sessions()


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

_SQLITE_EXTS = {".db", ".sqlite", ".sqlite3"}
_DUCKDB_EXTS = {".duckdb", ".parquet", ".csv"}


@router.post("/sql/upload")
async def upload_db(file: UploadFile = File(...)):
    fname = file.filename or ""
    ext   = Path(fname).suffix.lower()
    if ext in _SQLITE_EXTS:
        stype = "sqlite"
    elif ext in _DUCKDB_EXTS:
        stype = "duckdb"
    else:
        return JSONResponse(
            {"error": "Upload a .db / .sqlite / .sqlite3 / .duckdb / .parquet / .csv file"},
            status_code=400,
        )
    db_ref  = f"upload_{uuid.uuid4().hex[:8]}"
    db_path = _UPLOAD_DIR / f"{db_ref}{ext}"
    with db_path.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    try:
        if stype == "duckdb":
            schema = await load_duckdb_schema(str(db_path))
        else:
            schema = await load_sqlite_schema(str(db_path))
    except Exception as e:
        db_path.unlink(missing_ok=True)
        return JSONResponse({"error": f"Could not read file: {e}"}, status_code=422)
    _sessions[db_ref] = {"type": stype, "path": str(db_path),
                         "schema": schema, "created_at": time.time()}
    _save_session_index()
    return {"db_ref": db_ref, "schema": schema_to_dict(schema)}


# ── Connect PostgreSQL ────────────────────────────────────────────────────────

class ConnectRequest(BaseModel):
    conn_str: str
    db_type: str = "postgresql"  # "postgresql" | "mysql"


@router.post("/sql/connect")
async def connect_db(req: ConnectRequest):
    try:
        if req.db_type == "mysql":
            schema = await load_mysql_schema(req.conn_str)
            db_ref = f"mysql_{uuid.uuid4().hex[:8]}"
            stype  = "mysql"
        elif req.db_type == "mssql":
            schema = await load_mssql_schema(req.conn_str)
            db_ref = f"mssql_{uuid.uuid4().hex[:8]}"
            stype  = "mssql"
        else:
            schema = await load_pg_schema(req.conn_str)
            db_ref = f"pg_{uuid.uuid4().hex[:8]}"
            stype  = "postgresql"
    except Exception as e:
        return JSONResponse({"error": f"Connection failed: {e}"}, status_code=422)
    _sessions[db_ref] = {"type": stype, "conn_str": req.conn_str,
                         "schema": schema, "created_at": time.time()}
    return {"db_ref": db_ref, "schema": schema_to_dict(schema)}


# ── Query (SSE pipeline) ──────────────────────────────────────────────────────

class QueryRequest(BaseModel):
    question: str
    provider:  str = "groq"
    db_ref:    str = "chinook"
    history:   list[dict] = []
    glossary:  str = ""


class PageRequest(BaseModel):
    sql:       str
    db_ref:    str = "chinook"
    page:      int = 1
    page_size: int = 50


@router.post("/sql/page")
async def page_results(req: PageRequest):
    await _preload_chinook()
    session = _sessions.get(req.db_ref)
    if not session:
        return JSONResponse({"error": "Session expired or unknown"}, status_code=404)
    try:
        validate_sql(req.sql)
    except UnsafeQueryError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    page      = max(1, req.page)
    page_size = min(max(10, req.page_size), 200)
    stype     = session["type"]
    paged     = paginate_mssql_sql(req.sql, page, page_size) if stype == "mssql" else paginate_sql(req.sql, page, page_size)
    try:
        if stype == "sqlite":
            result = await execute_sqlite(session["path"], paged)
            total  = await count_rows_sqlite(session["path"], req.sql)
        elif stype == "duckdb":
            result = await execute_duckdb(session["path"], paged); total = -1
        elif stype == "mysql":
            result = await execute_mysql(session["conn_str"], paged); total = -1
        elif stype == "mssql":
            result = await execute_mssql(session["conn_str"], paged); total = -1
        else:
            result = await execute_pg(session["conn_str"], paged); total = -1
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
    safe = mask_sensitive_columns(result)
    d = result_to_dict(safe)
    d.update({"total_count": total, "page": page, "page_size": page_size})
    return d


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
        if req.db_ref.startswith("pg_"):
            msg = "PostgreSQL session expired (server restarted). Please reconnect."
        elif req.db_ref.startswith("mysql_"):
            msg = "MySQL session expired (server restarted). Please reconnect."
        elif req.db_ref.startswith("mssql_"):
            msg = "SQL Server session expired (server restarted). Please reconnect."
        elif req.db_ref.startswith("upload_"):
            msg = "Uploaded DB session expired (server restarted). Please re-upload your file."
        else:
            msg = f"Unknown db_ref: {req.db_ref}"
        yield _sse({"type": "error", "text": msg})
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
                safe_question, schema_text, req.provider, key,
                prev_sql, last_error, req.history or None, req.glossary,
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

        # --- execute (page 1 of 50) ---
        try:
            stype = session["type"]
            paged = paginate_mssql_sql(sql, 1, 50) if stype == "mssql" else paginate_sql(sql, 1, 50)
            if stype == "sqlite":
                result = await execute_sqlite(session["path"], paged)
            elif stype == "duckdb":
                result = await execute_duckdb(session["path"], paged)
            elif stype == "mysql":
                result = await execute_mysql(session["conn_str"], paged)
            elif stype == "mssql":
                result = await execute_mssql(session["conn_str"], paged)
            else:
                result = await execute_pg(session["conn_str"], paged)
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

    # Total count for pagination (SQLite only; -1 = unknown for other backends)
    total_count = await count_rows_sqlite(session["path"], sql) if session["type"] == "sqlite" else -1
    result_dict = result_to_dict(safe_result)
    result_dict["total_count"] = total_count
    result_dict["page"] = 1
    result_dict["page_size"] = 50
    yield _sse({"type": "results", **result_dict})

    # --- visualization ---
    viz = detect_visualization(safe_result.columns, safe_result.rows)
    if viz:
        yield _sse({"type": "visualization", **viz})

    # --- explanation (streaming) ---
    prompt = build_explain_prompt(safe_question, sql, safe_result.columns, safe_result.rows[:10])
    async for chunk in stream_explanation(prompt, req.provider, key):
        yield chunk