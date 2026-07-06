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


def result_to_dict(result: QueryResult) -> dict:
    return {
        "columns": result.columns,
        "rows": result.rows,
        "count": result.count,
        "exec_time_ms": result.exec_time_ms,
    }