"""The one way ml-sql opens a DuckDB upload.

SQL reaches DuckDB from callers (/sql/page, /sql/filter) and from the LLM, and
validate_sql only blocks keywords. DuckDB's table functions — read_csv,
read_text, read_parquet — read any file the process can, so without this
`SELECT * FROM read_csv('/proc/self/environ')` returned the Space's API keys.

External access is switched off before a caller's SQL can run, and the setting
is locked so that SQL cannot switch it back on. An uploaded CSV/Parquet is
copied into a table first: a view would read the file lazily and be refused
along with everything else.
"""
from __future__ import annotations

from pathlib import Path


def open_duckdb(db_path: str):
    import duckdb

    ext = Path(db_path).suffix.lower()
    if ext == ".duckdb":
        return duckdb.connect(
            db_path, read_only=True,
            config={"enable_external_access": False, "lock_configuration": True},
        )
    con = duckdb.connect()
    if ext == ".parquet":
        con.execute(f"CREATE TABLE data AS SELECT * FROM read_parquet('{db_path}')")
    elif ext == ".csv":
        con.execute(f"CREATE TABLE data AS SELECT * FROM read_csv_auto('{db_path}')")
    con.execute("SET enable_external_access = false")
    con.execute("SET lock_configuration = true")
    return con
