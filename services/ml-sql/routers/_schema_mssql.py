"""MSSQL (SQL Server) schema introspection using pymssql + asyncio.to_thread."""
from __future__ import annotations

import asyncio
from urllib.parse import urlparse

from ._schema import ColumnInfo, DBSchema, TableSchema


def _parse_mssql_url(conn_str: str) -> dict:
    p = urlparse(conn_str)
    return {
        "server": p.hostname or "localhost",
        "port": p.port or 1433,
        "user": p.username or "",
        "password": p.password or "",
        "database": (p.path or "").lstrip("/"),
    }


def _load_mssql_schema_sync(conn_str: str) -> DBSchema:
    import pymssql
    params = _parse_mssql_url(conn_str)
    conn = pymssql.connect(**params)
    tables: dict[str, TableSchema] = {}
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES "
            "WHERE TABLE_TYPE='BASE TABLE' ORDER BY TABLE_NAME"
        )
        table_names = [r[0] for r in cur.fetchall()]

        for tname in table_names:
            cur.execute(
                "SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE "
                "FROM INFORMATION_SCHEMA.COLUMNS "
                "WHERE TABLE_NAME=%s ORDER BY ORDINAL_POSITION",
                (tname,),
            )
            cols_raw = cur.fetchall()

            cur.execute(
                "SELECT ku.COLUMN_NAME "
                "FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc "
                "JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE ku "
                "  ON tc.CONSTRAINT_NAME=ku.CONSTRAINT_NAME "
                "WHERE tc.CONSTRAINT_TYPE='PRIMARY KEY' AND tc.TABLE_NAME=%s",
                (tname,),
            )
            pks = {r[0] for r in cur.fetchall()}
            columns = [
                ColumnInfo(name=r[0], type=r[1], not_null=(r[2] == "NO"), pk=(r[0] in pks))
                for r in cols_raw
            ]

            cur.execute(f"SELECT COUNT(*) FROM [{tname}]")
            row_count = cur.fetchone()[0]

            cur.execute(f"SELECT TOP 3 * FROM [{tname}]")
            raw = cur.fetchall()
            col_names = [d[0] for d in cur.description]
            sample = [dict(zip(col_names, r)) for r in raw]

            tables[tname] = TableSchema(
                name=tname, columns=columns,
                sample_rows=sample, row_count=row_count, foreign_keys=[],
            )
    finally:
        conn.close()
    return DBSchema(tables=tables, db_type="mssql")


async def load_mssql_schema(conn_str: str) -> DBSchema:
    return await asyncio.to_thread(_load_mssql_schema_sync, conn_str)
