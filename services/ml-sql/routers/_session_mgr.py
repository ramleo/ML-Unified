"""Session lifecycle — in-memory store, persistence, preloading, rate limiting."""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path

from ._execute import (
    execute_duckdb, execute_mssql, execute_mysql, execute_pg, execute_sqlite,
)
from ._schema import load_duckdb_schema, load_sqlite_schema

logger = logging.getLogger(__name__)

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


def get_sessions() -> dict[str, dict]:
    return _sessions


def check_rate_limit() -> bool:
    now = time.time()
    _recent_queries[:] = [t for t in _recent_queries if t > now - 60.0]
    if len(_recent_queries) >= _RATE_LIMIT:
        return False
    _recent_queries.append(now)
    return True


def save_session_index() -> None:
    index = {
        ref: {"type": s["type"], "path": s.get("path", ""), "created_at": s.get("created_at", 0)}
        for ref, s in _sessions.items()
        if s["type"] in ("sqlite", "duckdb") and ref != "chinook"
    }
    try:
        _SESSION_FILE.write_text(json.dumps(index))
    except OSError as exc:
        logger.warning("Failed to persist session index — sessions will not survive a restart: %s", exc)


async def restore_sessions() -> None:
    if not _SESSION_FILE.exists():
        return
    try:
        index = json.loads(_SESSION_FILE.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Failed to read session index, no sessions restored this startup: %s", exc)
        return
    cutoff = time.time() - _SESSION_TTL
    for ref, meta in index.items():
        if meta.get("created_at", 0) < cutoff:
            continue
        path = meta.get("path", "")
        if path and Path(path).exists() and ref not in _sessions:
            try:
                stype = meta.get("type", "sqlite")
                schema = await load_duckdb_schema(path) if stype == "duckdb" else await load_sqlite_schema(path)
                _sessions[ref] = {"type": stype, "path": path, "schema": schema, "created_at": meta["created_at"]}
            except Exception as exc:
                logger.warning("Failed to restore session %r, will show as expired: %s", ref, exc)


async def exec_session(session: dict, sql: str):
    stype = session["type"]
    if stype == "sqlite":   return await execute_sqlite(session["path"], sql)
    elif stype == "duckdb": return await execute_duckdb(session["path"], sql)
    elif stype == "mysql":  return await execute_mysql(session["conn_str"], sql)
    elif stype == "mssql":  return await execute_mssql(session["conn_str"], sql)
    else:                   return await execute_pg(session["conn_str"], sql)


async def preload_chinook() -> None:
    if "chinook" not in _sessions and CHINOOK_PATH.exists():
        schema = await load_sqlite_schema(str(CHINOOK_PATH))
        _sessions["chinook"] = {"type": "sqlite", "path": str(CHINOOK_PATH),
                                "schema": schema, "created_at": time.time()}
    await restore_sessions()
