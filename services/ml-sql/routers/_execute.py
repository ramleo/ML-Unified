"""SQL safety validation and execution against SQLite / PostgreSQL."""
from __future__ import annotations

import re
import time
from dataclasses import dataclass

import aiosqlite
import sqlparse
from sqlparse.sql import Statement


class UnsafeQueryError(Exception):
    pass


_BLOCKED_KEYWORDS = (
    "DROP", "DELETE", "INSERT", "UPDATE", "CREATE", "ALTER",
    "TRUNCATE", "EXEC", "EXECUTE", "GRANT", "REVOKE",
)


def validate_sql(sql: str) -> None:
    """Raise UnsafeQueryError if the statement is not a safe SELECT."""
    stripped = sql.strip()
    if not stripped:
        raise UnsafeQueryError("Empty SQL query")

    parsed = sqlparse.parse(stripped)
    if not parsed:
        raise UnsafeQueryError("Could not parse SQL")

    stmt: Statement = parsed[0]
    stmt_type = stmt.get_type()
    if stmt_type not in ("SELECT", "UNKNOWN", None):
        raise UnsafeQueryError(f"Only SELECT queries are allowed (got: {stmt_type})")

    sql_upper = re.sub(r"--[^\n]*", "", stripped.upper())  # strip comments
    for kw in _BLOCKED_KEYWORDS:
        if re.search(rf"\b{kw}\b", sql_upper):
            raise UnsafeQueryError(f"Blocked keyword detected: {kw}")

    if not re.search(r"\bSELECT\b", sql_upper):
        raise UnsafeQueryError("Query must contain SELECT")


@dataclass
class QueryResult:
    columns: list[str]
    rows: list[list]
    count: int
    exec_time_ms: float


_ROW_LIMIT = 500


async def execute_sqlite(db_path: str, sql: str) -> QueryResult:
    t0 = time.monotonic()
    limited_sql = _inject_limit(sql, _ROW_LIMIT)
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(limited_sql) as cur:
            raw_rows = await cur.fetchall()
            if not raw_rows:
                cols = [d[0] for d in (cur.description or [])]
                return QueryResult(columns=cols, rows=[], count=0, exec_time_ms=0)
            cols = list(raw_rows[0].keys())
            rows = [list(r) for r in raw_rows]

    exec_ms = (time.monotonic() - t0) * 1000
    return QueryResult(
        columns=cols,
        rows=rows,
        count=len(rows),
        exec_time_ms=round(exec_ms, 1),
    )


async def execute_pg(conn_str: str, sql: str) -> QueryResult:
    import asyncpg
    t0 = time.monotonic()
    limited_sql = _inject_limit(sql, _ROW_LIMIT)
    conn = await asyncpg.connect(conn_str)
    try:
        records = await conn.fetch(limited_sql)
        if not records:
            return QueryResult(columns=[], rows=[], count=0, exec_time_ms=0)
        cols = list(records[0].keys())
        rows = [list(r.values()) for r in records]
    finally:
        await conn.close()

    exec_ms = (time.monotonic() - t0) * 1000
    return QueryResult(
        columns=cols,
        rows=rows,
        count=len(rows),
        exec_time_ms=round(exec_ms, 1),
    )


def _inject_limit(sql: str, limit: int) -> str:
    """Append LIMIT if none present and query is a plain SELECT."""
    sql_stripped = sql.rstrip(";").strip()
    if not re.search(r"\bLIMIT\b", sql_stripped, re.IGNORECASE):
        sql_stripped += f" LIMIT {limit}"
    return sql_stripped


def result_to_dict(result: QueryResult) -> dict:
    return {
        "columns": result.columns,
        "rows": result.rows,
        "count": result.count,
        "exec_time_ms": result.exec_time_ms,
    }