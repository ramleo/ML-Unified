"""FastAPI router — /health, /sql/schema, /sql/upload, /sql/connect, /sql/query."""
from __future__ import annotations

import asyncio
import os
import shutil
import uuid
from pathlib import Path
from typing import AsyncGenerator

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from ._explain import (
    _sse, build_explain_prompt, stream_explanation,
)
from ._execute import (
    UnsafeQueryError, validate_sql, result_to_dict, mask_sensitive_columns,
    paginate_sql, paginate_mssql_sql, count_rows_sqlite, count_rows_remote,
)
from ._generate import generate_sql, generate_filter_expr, get_provider_cfg, sanitize_question, generate_sample_questions, generate_followup_suggestions
from ._providers import RateLimitError
from ._schema import (
    DBSchema, load_pg_schema, load_sqlite_schema, load_mysql_schema, load_duckdb_schema,
    schema_to_dict, schema_to_prompt_text,
)
from ._schema_mssql import load_mssql_schema
from ._session_mgr import (
    CHINOOK_PATH, _UPLOAD_DIR, _sessions,
    save_session_index, exec_session, preload_chinook,
)

router = APIRouter()

_SQLITE_EXTS = {".db", ".sqlite", ".sqlite3"}
_DUCKDB_EXTS = {".duckdb", ".parquet", ".csv"}


@router.get("/health")
async def health():
    await preload_chinook()
    chinook = _sessions.get("chinook")
    tables  = len(chinook["schema"].tables) if chinook else 0
    return {"status": "ok", "demo_db": "chinook.db", "tables": tables}


@router.get("/sql/schema")
async def get_schema(db_ref: str = "chinook"):
    await preload_chinook()
    session = _sessions.get(db_ref)
    if not session:
        return JSONResponse({"error": f"Unknown db_ref: {db_ref}"}, status_code=404)
    return schema_to_dict(session["schema"])


@router.get("/sql/sample-questions")
async def get_sample_questions(db_ref: str, provider: str = "groq"):
    session = _sessions.get(db_ref)
    if not session:
        return JSONResponse({"error": "session not found"}, status_code=404)
    key = os.environ.get(get_provider_cfg(provider)["env"], "")
    return {"questions": await generate_sample_questions(session["schema"], provider, key)}


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
        schema = await load_duckdb_schema(str(db_path)) if stype == "duckdb" else await load_sqlite_schema(str(db_path))
    except Exception as e:
        db_path.unlink(missing_ok=True)
        return JSONResponse({"error": f"Could not read file: {e}"}, status_code=422)
    _sessions[db_ref] = {"type": stype, "path": str(db_path), "schema": schema, "created_at": __import__("time").time()}
    save_session_index()
    return {"db_ref": db_ref, "schema": schema_to_dict(schema)}


class ConnectRequest(BaseModel):
    conn_str: str
    db_type: str = "postgresql"


@router.post("/sql/connect")
async def connect_db(req: ConnectRequest):
    try:
        if req.db_type == "mysql":
            schema = await load_mysql_schema(req.conn_str)
            db_ref, stype = f"mysql_{uuid.uuid4().hex[:8]}", "mysql"
        elif req.db_type == "mssql":
            schema = await load_mssql_schema(req.conn_str)
            db_ref, stype = f"mssql_{uuid.uuid4().hex[:8]}", "mssql"
        else:
            schema = await load_pg_schema(req.conn_str)
            db_ref, stype = f"pg_{uuid.uuid4().hex[:8]}", "postgresql"
    except Exception as e:
        return JSONResponse({"error": f"Connection failed: {e}"}, status_code=422)
    _sessions[db_ref] = {"type": stype, "conn_str": req.conn_str, "schema": schema, "created_at": __import__("time").time()}
    return {"db_ref": db_ref, "schema": schema_to_dict(schema)}


class QueryRequest(BaseModel):
    question:   str
    provider:   str = "groq"
    db_ref:     str = "chinook"
    history:    list[dict] = []
    glossary:   str = ""
    correction: str = ""


class PageRequest(BaseModel):
    sql: str; db_ref: str = "chinook"; page: int = 1; page_size: int = 50


@router.post("/sql/page")
async def page_results(req: PageRequest):
    await preload_chinook()
    session = _sessions.get(req.db_ref)
    if not session:
        return JSONResponse({"error": "Session expired or unknown"}, status_code=404)
    try:
        validate_sql(req.sql)
    except UnsafeQueryError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    page, page_size = max(1, req.page), min(max(10, req.page_size), 200)
    stype  = session["type"]
    paged  = paginate_mssql_sql(req.sql, page, page_size) if stype == "mssql" else paginate_sql(req.sql, page, page_size)
    try:
        result = await exec_session(session, paged)
        total  = await count_rows_sqlite(session["path"], req.sql) if stype == "sqlite" else await count_rows_remote(session, req.sql) if stype in ("postgresql", "mysql", "mssql") else -1
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
    d = result_to_dict(mask_sensitive_columns(result))
    d.update({"total_count": total, "page": page, "page_size": page_size})
    return d


class FilterRequest(BaseModel):
    sql: str; db_ref: str = "chinook"; filter_text: str; columns: list[str] = []; provider: str = "groq"


@router.post("/sql/filter")
async def filter_results(req: FilterRequest):
    await preload_chinook()
    session = _sessions.get(req.db_ref)
    if not session:
        return JSONResponse({"error": "Session expired or unknown"}, status_code=404)
    try:
        validate_sql(req.sql)
    except UnsafeQueryError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    cfg = get_provider_cfg(req.provider)
    key = os.environ.get(cfg["env"], "")
    if not key:
        return JSONResponse({"error": f"{cfg['env']} not configured"}, status_code=422)
    try:
        expr = await generate_filter_expr(sanitize_question(req.filter_text), req.columns, req.provider, key)
    except Exception as e:
        return JSONResponse({"error": f"Filter generation failed: {e}"}, status_code=500)
    filtered_sql = f"SELECT * FROM ({req.sql.rstrip(';').strip()}) AS _filtered WHERE {expr}"
    try:
        validate_sql(filtered_sql)
    except UnsafeQueryError as e:
        return JSONResponse({"error": f"Generated filter is unsafe: {e}"}, status_code=400)
    stype = session["type"]
    paged = paginate_mssql_sql(filtered_sql, 1, 50) if stype == "mssql" else paginate_sql(filtered_sql, 1, 50)
    try:
        result = await exec_session(session, paged)
        total  = await count_rows_sqlite(session["path"], filtered_sql) if stype == "sqlite" else await count_rows_remote(session, filtered_sql) if stype in ("postgresql", "mysql", "mssql") else -1
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
    d = result_to_dict(mask_sensitive_columns(result))
    d.update({"filtered_sql": filtered_sql, "filter_expr": expr, "total_count": total, "page": 1, "page_size": 50})
    return d


@router.post("/sql/query")
async def query_sql(req: QueryRequest):
    return StreamingResponse(
        _run_pipeline(req),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _run_pipeline(req: QueryRequest) -> AsyncGenerator[str, None]:
    # Rate limits live in routers/_guard.py, per IP. The global counter that
    # stood here let a single caller lock every visitor out.
    await preload_chinook()
    session = _sessions.get(req.db_ref)
    if not session:
        if req.db_ref.startswith("pg_"):        msg = "PostgreSQL session expired (server restarted). Please reconnect."
        elif req.db_ref.startswith("mysql_"):   msg = "MySQL session expired (server restarted). Please reconnect."
        elif req.db_ref.startswith("mssql_"):   msg = "SQL Server session expired (server restarted). Please reconnect."
        elif req.db_ref.startswith("upload_"):  msg = "Uploaded DB session expired (server restarted). Please re-upload your file."
        else:                                   msg = f"Unknown db_ref: {req.db_ref}"
        yield _sse({"type": "error", "text": msg}); yield _sse({"type": "done"}); return

    cfg = get_provider_cfg(req.provider)
    key = os.environ.get(cfg["env"], "")
    if not key:
        yield _sse({"type": "error", "text": f"{cfg['env']} not configured on this server."})
        yield _sse({"type": "done"}); return

    safe_question = sanitize_question(req.question)
    schema: DBSchema = session["schema"]
    schema_text = schema_to_prompt_text(schema, safe_question)
    yield _sse({"type": "schema_loaded", "tables": len(schema.tables),
                "columns": sum(len(t.columns) for t in schema.tables.values())})

    sql = None; result = None; last_error = None; prev_sql = None
    used_provider = req.provider; used_model = get_provider_cfg(req.provider)["model"]
    for attempt in range(1, 4):
        if attempt > 1:
            await asyncio.sleep(2 ** (attempt - 2))
            yield _sse({"type": "retry", "attempt": attempt, "error": last_error})
        try:
            sql, used_provider, used_model = await generate_sql(
                safe_question, schema_text, req.provider, key,
                prev_sql, last_error, req.history or None, req.glossary, req.correction,
            )
            validate_sql(sql)
        except RateLimitError as e:
            yield _sse({"type": "error", "text": str(e)}); yield _sse({"type": "done"}); return
        except UnsafeQueryError as e:
            last_error = str(e); prev_sql = sql; continue
        except Exception as e:
            last_error = f"SQL generation error: {e}"; prev_sql = sql; continue

        # Name the provider that actually answered. On a fallback this differs
        # from req.provider, and without it the UI and analytics both report the
        # provider the user picked rather than the one that did the work.
        yield _sse({"type": "sql_generated", "sql": sql,
                    "provider": used_provider, "model": used_model,
                    "fell_back_from": req.provider if used_provider != req.provider else None})
        try:
            stype = session["type"]
            paged = paginate_mssql_sql(sql, 1, 50) if stype == "mssql" else paginate_sql(sql, 1, 50)
            result = await exec_session(session, paged)
            break
        except Exception as e:
            last_error = f"Execution error: {e}"; prev_sql = sql; result = None; continue

    if result is None:
        yield _sse({"type": "error", "text": f"Failed after 3 attempts. Last: {last_error}"})
        yield _sse({"type": "done"}); return

    safe_result = mask_sensitive_columns(result)
    stype = session["type"]
    if stype == "sqlite":                          total_count = await count_rows_sqlite(session["path"], sql)
    elif stype in ("postgresql", "mysql", "mssql"): total_count = await count_rows_remote(session, sql)
    else:                                           total_count = -1
    result_dict = result_to_dict(safe_result)
    result_dict.update({"total_count": total_count, "page": 1, "page_size": 50})
    yield _sse({"type": "results", **result_dict})
    yield _sse({"type": "done"})


class ExplainRequest(BaseModel):
    question: str; sql: str; columns: list[str]; rows: list; provider: str = "groq"


@router.post("/sql/explain")
async def explain_sql(req: ExplainRequest):
    return StreamingResponse(_stream_explain(req), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


async def _stream_explain(req: ExplainRequest) -> AsyncGenerator[str, None]:
    cfg = get_provider_cfg(req.provider)
    key = os.environ.get(cfg["env"], "")
    if not key: yield _sse({"type": "error", "text": f"{cfg['env']} not configured"}); yield _sse({"type": "done"}); return
    prompt = build_explain_prompt(sanitize_question(req.question), req.sql, req.columns, req.rows[:10])
    try:
        async for chunk in stream_explanation(prompt, req.provider, key): yield chunk
        sugg = await generate_followup_suggestions(req.question, req.sql, req.columns, req.rows[:5], req.provider, key)
        if sugg: yield _sse({"type": "suggestions", "questions": sugg})
    except RateLimitError as e:
        yield _sse({"type": "error", "text": str(e)})
    yield _sse({"type": "done"})


class ReasonRequest(BaseModel):
    question: str; sql: str; columns: list[str]; provider: str = "groq"


@router.post("/sql/reason")
async def reason_sql(req: ReasonRequest):
    return StreamingResponse(_stream_reason(req), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


async def _stream_reason(req: ReasonRequest) -> AsyncGenerator[str, None]:
    cfg = get_provider_cfg(req.provider)
    key = os.environ.get(cfg["env"], "")
    if not key: yield _sse({"type": "error", "text": f"{cfg['env']} not configured"}); yield _sse({"type": "done"}); return
    cols = ", ".join(req.columns) or "unknown"
    prompt = (
        f"Question: {sanitize_question(req.question)}\n"
        f"SQL generated: {req.sql}\n"
        f"Result columns: {cols}\n\n"
        "Explain your step-by-step reasoning for generating this SQL:\n"
        "- What did you identify as the key intent of the question?\n"
        "- Which tables and columns did you choose and why?\n"
        "- What assumptions did you make (e.g. how a term maps to a column)?\n"
        "- Why did you use this aggregation / join / filter?\n"
        "Be concise but specific. Use plain English, not SQL."
    )
    try:
        async for chunk in stream_explanation(prompt, req.provider, key): yield chunk
    except RateLimitError as e:
        yield _sse({"type": "error", "text": str(e)})
    yield _sse({"type": "done"})
