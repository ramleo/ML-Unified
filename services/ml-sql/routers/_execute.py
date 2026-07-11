"""SQL safety validation and execution against SQLite / PostgreSQL.

Guardrails:
  - SELECT-only whitelist (sqlparse statement type check)
  - Expanded blocked-keyword regex (covers DROP, DELETE, INSERT, etc.)
  - Both comment styles stripped before keyword scan (-- and /* */)
  - Multi-statement detection (semicolon separation)
  - SQLite opened in URI read-only mode (file:...?mode=ro)
  - PostgreSQL wrapped in a read-only transaction that is always rolled back
  - Hard row limit injected if absent
"""
from __future__ import annotations

import re
import time
import urllib.parse
from dataclasses import dataclass

import aiosqlite
import sqlparse
from sqlparse.sql import Statement


class UnsafeQueryError(Exception):
    pass


_BLOCKED_KEYWORDS = (
    "DROP", "DELETE", "INSERT", "UPDATE", "CREATE", "ALTER",
    "TRUNCATE", "EXEC", "EXECUTE", "GRANT", "REVOKE", "REPLACE",
    "MERGE", "UPSERT", "LOAD", "ATTACH", "DETACH", "PRAGMA",
    "VACUUM", "ANALYZE", "EXPLAIN", "SET",
)

# Sensitive column names — values are masked in results sent to client + LLM
_SENSITIVE_COL_RE = re.compile(
    r"\b(password|passwd|secret|token|api_key|apikey|ssn|credit_card|cvv|"
    r"private_key|salt|hash|otp|pin)\b",
    re.IGNORECASE,
)

_MAX_RESULT_BYTES = 5_000_000  # 5 MB cap on raw result data

_COMMENT_STRIP = re.compile(
    r"(--[^\n]*|/\*.*?\*/)", re.DOTALL
)


def _strip_comments(sql: str) -> str:
    return _COMMENT_STRIP.sub(" ", sql)


def validate_sql(sql: str) -> None:
    """Raise UnsafeQueryError if the statement is not a safe SELECT."""
    stripped = sql.strip()
    if not stripped:
        raise UnsafeQueryError("Empty SQL query")

    # Block multi-statement queries (stacked injections: SELECT 1; DROP TABLE foo)
    # A lone semicolon at the very end is fine — strip it first.
    no_trailing = stripped.rstrip(";").strip()
    if ";" in no_trailing:
        raise UnsafeQueryError("Multiple statements are not allowed")

    parsed = sqlparse.parse(stripped)
    if not parsed:
        raise UnsafeQueryError("Could not parse SQL")

    stmt: Statement = parsed[0]
    stmt_type = stmt.get_type()
    if stmt_type not in ("SELECT", "UNKNOWN", None):
        raise UnsafeQueryError(f"Only SELECT queries are allowed (got: {stmt_type})")

    clean = _strip_comments(stripped).upper()
    for kw in _BLOCKED_KEYWORDS:
        if re.search(rf"\b{kw}\b", clean):
            raise UnsafeQueryError(f"Blocked keyword: {kw}")

    if not re.search(r"\bSELECT\b", clean):
        raise UnsafeQueryError("Query must contain SELECT")

    # Structural pre-validation — catch malformed LLM output before hitting the DB

    # 1. FROM clause required (subqueries with no outer FROM are rare and suspicious)
    if not re.search(r"\bFROM\b", clean):
        raise UnsafeQueryError("Query must contain a FROM clause")

    # 2. Balanced parentheses
    if stripped.count("(") != stripped.count(")"):
        raise UnsafeQueryError("Unbalanced parentheses in query")

    # 3. Unmatched single quotes (odd count means an open string literal)
    # Strip escaped quotes ('') before counting
    no_escaped = stripped.replace("''", "")
    if no_escaped.count("'") % 2 != 0:
        raise UnsafeQueryError("Unmatched single quote in query")

    # 4. Truncated query — ends on a dangling keyword (LLM cut off mid-generation)
    _DANGLING = re.compile(
        r"\b(WHERE|AND|OR|ON|JOIN|LEFT|RIGHT|INNER|OUTER|HAVING|GROUP|ORDER|BY|FROM|SELECT|BETWEEN|NOT|IN|LIKE|AS|CASE|WHEN|THEN|ELSE)\s*$",
        re.IGNORECASE,
    )
    if _DANGLING.search(stripped.rstrip(";")):
        raise UnsafeQueryError("Query appears truncated (ends on a keyword)")


@dataclass
class QueryResult:
    columns: list[str]
    rows: list[list]
    count: int
    exec_time_ms: float
    total_count: int = -1  # -1 = unknown; set when count query is run


def _extract_user_limit(sql: str) -> int | None:
    m = re.search(r"\bLIMIT\s+(\d+)(\s+OFFSET\s+\d+)?\s*$", sql.rstrip(";").strip(), flags=re.IGNORECASE)
    return int(m.group(1)) if m else None


def _strip_limit(sql: str) -> str:
    return re.sub(r"\bLIMIT\s+\d+(\s+OFFSET\s+\d+)?\s*$", "", sql.rstrip(";").strip(), flags=re.IGNORECASE).strip()


def paginate_sql(sql: str, page: int, page_size: int) -> str:
    """Wrap sql with LIMIT/OFFSET for the given 1-indexed page, honoring user's LIMIT if smaller."""
    user_limit = _extract_user_limit(sql)
    inner = _strip_limit(sql)
    offset = (page - 1) * page_size
    if user_limit is not None and user_limit <= page_size + offset:
        effective = max(0, user_limit - offset)
        return f"SELECT * FROM ({inner}) AS _paged LIMIT {effective} OFFSET {offset}"
    return f"SELECT * FROM ({inner}) AS _paged LIMIT {page_size} OFFSET {offset}"


def _count_sql(sql: str) -> str:
    user_limit = _extract_user_limit(sql)
    inner = _strip_limit(sql)
    if user_limit is not None:
        return f"SELECT COUNT(*) FROM (SELECT * FROM ({inner}) AS _inner LIMIT {user_limit}) AS _cnt"
    return f"SELECT COUNT(*) FROM ({inner}) AS _cnt"


async def count_rows_sqlite(db_path: str, sql: str) -> int:
    try:
        async with aiosqlite.connect(_ro_uri(db_path), uri=True) as db:
            async with db.execute(_count_sql(sql)) as cur:
                row = await cur.fetchone()
                return int(row[0]) if row else 0
    except Exception:
        return -1


async def count_rows_remote(session: dict, sql: str) -> int:
    """Count total rows for pg/mysql/mssql via a COUNT(*) subquery."""
    try:
        count_sql = _count_sql(sql)
        stype = session["type"]
        if stype == "mysql":
            result = await execute_mysql(session["conn_str"], count_sql)
        elif stype == "mssql":
            result = await execute_mssql(session["conn_str"], count_sql)
        else:
            result = await execute_pg(session["conn_str"], count_sql)
        return int(result.rows[0][0]) if result.rows else -1
    except Exception:
        return -1


def mask_sensitive_columns(result: "QueryResult") -> "QueryResult":
    """Replace cell values in sensitive columns with *** before returning to client or LLM."""
    sensitive_idx = [
        i for i, col in enumerate(result.columns)
        if _SENSITIVE_COL_RE.search(col)
    ]
    if not sensitive_idx:
        return result
    masked = [
        [("***" if j in sensitive_idx else cell) for j, cell in enumerate(row)]
        for row in result.rows
    ]
    return QueryResult(
        columns=result.columns, rows=masked,
        count=result.count, exec_time_ms=result.exec_time_ms,
    )


def _trim_oversized(rows: list[list]) -> list[list]:
    """Trim rows if total serialized size exceeds _MAX_RESULT_BYTES."""
    total = 0
    for i, row in enumerate(rows):
        total += sum(len(str(c)) for c in row)
        if total > _MAX_RESULT_BYTES:
            return rows[:max(i, 1)]
    return rows


def _parse_mysql_url(conn_str: str) -> dict:
    p = urllib.parse.urlparse(conn_str)
    return {
        "host": p.hostname or "localhost",
        "port": p.port or 3306,
        "user": p.username or "",
        "password": p.password or "",
        "db": (p.path or "").lstrip("/"),
    }


_ROW_LIMIT = 500


def _ro_uri(db_path: str) -> str:
    """Return a file:// URI that opens SQLite in read-only mode."""
    encoded = urllib.parse.quote(db_path, safe="/:")
    return f"file:{encoded}?mode=ro"


async def execute_sqlite(db_path: str, sql: str) -> QueryResult:
    t0 = time.monotonic()
    limited_sql = _inject_limit(sql, _ROW_LIMIT)
    # uri=True enables the ?mode=ro flag → SQLite refuses any write operation
    async with aiosqlite.connect(_ro_uri(db_path), uri=True) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(limited_sql) as cur:
            raw_rows = await cur.fetchall()
            if not raw_rows:
                cols = [d[0] for d in (cur.description or [])]
                return QueryResult(columns=cols, rows=[], count=0, exec_time_ms=0)
            cols = list(raw_rows[0].keys())
            rows = _trim_oversized([list(r) for r in raw_rows])

    exec_ms = (time.monotonic() - t0) * 1000
    return QueryResult(
        columns=cols, rows=rows,
        count=len(rows), exec_time_ms=round(exec_ms, 1),
    )


async def execute_pg(conn_str: str, sql: str) -> QueryResult:
    """Execute against PostgreSQL with explicit rollback after fetch.

    Two independent read-only layers:
    1. SET TRANSACTION READ ONLY — PostgreSQL rejects any write attempt at engine level.
    2. Explicit tr.rollback() — transaction is never committed regardless, so even if
       layer 1 were somehow bypassed the changes would not persist.
    """
    import asyncpg
    t0 = time.monotonic()
    limited_sql = _inject_limit(sql, _ROW_LIMIT)
    conn = await asyncpg.connect(conn_str)
    try:
        tr = conn.transaction()
        await tr.start()
        await conn.execute("SET TRANSACTION READ ONLY")
        records = await conn.fetch(limited_sql)
        await tr.rollback()  # explicit — never commits, even on clean exit
        if not records:
            return QueryResult(columns=[], rows=[], count=0, exec_time_ms=0)
        cols = list(records[0].keys())
        rows = _trim_oversized([list(r.values()) for r in records])
    finally:
        await conn.close()

    exec_ms = (time.monotonic() - t0) * 1000
    return QueryResult(
        columns=cols, rows=rows,
        count=len(rows), exec_time_ms=round(exec_ms, 1),
    )


def _inject_limit(sql: str, limit: int) -> str:
    sql_stripped = sql.rstrip(";").strip()
    if not re.search(r"\bLIMIT\b", sql_stripped, re.IGNORECASE):
        sql_stripped += f" LIMIT {limit}"
    return sql_stripped


async def execute_mysql(conn_str: str, sql: str) -> QueryResult:
    import asyncmy
    params = _parse_mysql_url(conn_str)
    t0 = time.monotonic()
    conn = await asyncmy.connect(**params)
    try:
        limited_sql = _inject_limit(sql, _ROW_LIMIT)
        async with conn.cursor() as cur:
            await cur.execute("SET SESSION TRANSACTION READ ONLY")
            await cur.execute(limited_sql)
            raw = await cur.fetchall()
            cols = [d[0] for d in (cur.description or [])]
        rows = _trim_oversized([list(r) for r in raw])
    finally:
        conn.close()
    exec_ms = (time.monotonic() - t0) * 1000
    return QueryResult(columns=cols, rows=rows, count=len(rows), exec_time_ms=round(exec_ms, 1))


def paginate_mssql_sql(sql: str, page: int, page_size: int) -> str:
    """Wrap sql with MSSQL OFFSET/FETCH pagination (strips ORDER BY for subquery compat)."""
    inner = re.sub(r"\bORDER\s+BY\s+.+$", "", sql.rstrip(";").strip(), flags=re.IGNORECASE | re.DOTALL).strip()
    inner = re.sub(r"\bTOP\s+\d+\b", "", inner, flags=re.IGNORECASE).strip()
    offset = (page - 1) * page_size
    return (
        f"SELECT * FROM ({inner}) AS _q "
        f"ORDER BY (SELECT NULL) OFFSET {offset} ROWS FETCH NEXT {page_size} ROWS ONLY"
    )


async def execute_mssql(conn_str: str, sql: str) -> QueryResult:
    import asyncio
    from urllib.parse import urlparse

    def _run() -> tuple[list[str], list[list]]:
        import pymssql
        p = urlparse(conn_str)
        conn = pymssql.connect(
            server=p.hostname, port=p.port or 1433,
            user=p.username, password=p.password,
            database=(p.path or "").lstrip("/"),
        )
        try:
            cur = conn.cursor()
            cur.execute(sql)
            raw = cur.fetchall()
            cols = [d[0] for d in (cur.description or [])]
            return cols, [list(r) for r in raw]
        finally:
            conn.close()

    t0 = time.monotonic()
    cols, rows = await asyncio.to_thread(_run)
    exec_ms = (time.monotonic() - t0) * 1000
    rows = _trim_oversized(rows)
    return QueryResult(columns=cols, rows=rows, count=len(rows), exec_time_ms=round(exec_ms, 1))


async def execute_duckdb(db_path: str, sql: str) -> QueryResult:
    import asyncio
    from pathlib import Path as _Path

    ext = _Path(db_path).suffix.lower()

    def _exec():
        import duckdb
        if ext == ".duckdb":
            con = duckdb.connect(db_path, read_only=True)
        else:
            con = duckdb.connect()
            if ext == ".parquet":
                con.execute(f"CREATE VIEW data AS SELECT * FROM read_parquet('{db_path}')")
            elif ext == ".csv":
                con.execute(f"CREATE VIEW data AS SELECT * FROM read_csv_auto('{db_path}')")
        rel = con.execute(_inject_limit(sql, _ROW_LIMIT))
        cols = [d[0] for d in rel.description]
        rows = [list(r) for r in rel.fetchall()]
        con.close()
        return cols, rows

    t0 = time.monotonic()
    cols, rows = await asyncio.to_thread(_exec)
    exec_ms = (time.monotonic() - t0) * 1000
    rows = _trim_oversized(rows)
    return QueryResult(columns=cols, rows=rows, count=len(rows), exec_time_ms=round(exec_ms, 1))


def result_to_dict(result: QueryResult) -> dict:
    d = {"columns": result.columns, "rows": result.rows, "count": result.count, "exec_time_ms": result.exec_time_ms}
    if result.total_count >= 0:
        d["total_count"] = result.total_count
    return d