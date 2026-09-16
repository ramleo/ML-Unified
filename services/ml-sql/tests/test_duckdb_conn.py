"""E10 regression: an uploaded DuckDB file cannot read the Space's own files.

CSV/Parquet uploads open an in-memory DuckDB, and `/sql/page`, `/sql/filter`
and the LLM path all run caller SQL that `validate_sql` only keyword-checks.
DuckDB's table functions (`read_csv`, `read_text`, `read_parquet`) read any
file the process can, so before the fix
`SELECT * FROM read_csv('/proc/self/environ')` returned the Space's API keys.

`open_duckdb` copies the upload into a table, then disables external access and
locks the configuration so caller SQL cannot switch it back on. These tests
plant a fake secret file and prove the normal query works while every path to
that file is refused — for CSV, Parquet and a `.duckdb` upload alike.
"""
from __future__ import annotations

import pytest

pytest.importorskip("duckdb", reason="duckdb is in ml-sql's requirements; skip if absent locally")

import duckdb
from routers._duckdb_conn import open_duckdb


@pytest.fixture
def secret_file(tmp_path):
    """Stands in for the file E10 could read — e.g. /proc/self/environ."""
    f = tmp_path / "secret.txt"
    f.write_text("GROQ_API_KEY=SENTINEL_SHOULD_NEVER_BE_READ\n")
    return f


def _refuses_file_access(con, secret_path) -> None:
    """Every DuckDB path to an arbitrary file must be refused once the upload
    is open. The error DuckDB raises names the disabled configuration."""
    for sql in (
        f"SELECT * FROM read_text('{secret_path}')",
        f"SELECT * FROM read_csv('{secret_path}')",
        f"SELECT content FROM read_text('{secret_path}')",
    ):
        with pytest.raises(duckdb.Error) as exc:  # duckdb's own exception base
            con.execute(sql).fetchall()
        assert "disabled" in str(exc.value).lower() or "external access" in str(exc.value).lower(), \
            f"expected a file-access refusal, got: {exc.value}"


def _cannot_reenable_access(con) -> None:
    """The lock is the point: caller SQL must not be able to turn access back
    on and then read a file."""
    with pytest.raises(duckdb.Error):
        con.execute("SET enable_external_access = true")


def test_csv_upload_queries_but_cannot_read_files(tmp_path, secret_file):
    csv = tmp_path / "upload.csv"
    csv.write_text("id,name\n1,alice\n2,bob\n")

    con = open_duckdb(str(csv))
    try:
        rows = con.execute("SELECT * FROM data ORDER BY id").fetchall()
        assert rows == [(1, "alice"), (2, "bob")]

        _refuses_file_access(con, secret_file)
        _cannot_reenable_access(con)
    finally:
        con.close()


def test_parquet_upload_queries_but_cannot_read_files(tmp_path, secret_file):
    # Write the parquet with DuckDB itself so the test needs no pyarrow.
    parquet = tmp_path / "upload.parquet"
    w = duckdb.connect()
    w.execute("CREATE TABLE t AS SELECT * FROM (VALUES (1, 'alice'), (2, 'bob')) AS v(id, name)")
    w.execute(f"COPY t TO '{parquet}' (FORMAT PARQUET)")
    w.close()

    con = open_duckdb(str(parquet))
    try:
        rows = con.execute("SELECT * FROM data ORDER BY id").fetchall()
        assert rows == [(1, "alice"), (2, "bob")]

        _refuses_file_access(con, secret_file)
        _cannot_reenable_access(con)
    finally:
        con.close()


def test_duckdb_file_upload_queries_but_cannot_read_files(tmp_path, secret_file):
    db = tmp_path / "upload.duckdb"
    seed = duckdb.connect(str(db))
    seed.execute("CREATE TABLE data AS SELECT * FROM (VALUES (1, 'alice'), (2, 'bob')) AS v(id, name)")
    seed.close()

    con = open_duckdb(str(db))
    try:
        rows = con.execute("SELECT * FROM data ORDER BY id").fetchall()
        assert rows == [(1, "alice"), (2, "bob")]

        _refuses_file_access(con, secret_file)
        _cannot_reenable_access(con)
    finally:
        con.close()


def test_the_attack_query_that_started_e10_is_refused(tmp_path):
    """The literal payload from the finding: read the environment through an
    uploaded CSV. It must not return anything."""
    csv = tmp_path / "upload.csv"
    csv.write_text("id\n1\n")

    con = open_duckdb(str(csv))
    try:
        with pytest.raises(duckdb.Error) as exc:
            con.execute("SELECT * FROM read_csv('/proc/self/environ')").fetchall()
        assert "disabled" in str(exc.value).lower() or "external access" in str(exc.value).lower()
    finally:
        con.close()
