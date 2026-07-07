"""MSSQL (SQL Server) schema introspection."""
from __future__ import annotations

from urllib.parse import urlparse

from ._schema import ColumnInfo, DBSchema, TableSchema


async def load_mssql_schema(conn_str: str) -> DBSchema:
    import aiomssql
    p = urlparse(conn_str)
    conn = await aiomssql.connect(
        host=p.hostname, port=p.port or 1433,
        user=p.username, password=p.password,
        database=(p.path or "").lstrip("/"),
    )
    tables: dict[str, TableSchema] = {}
    try:
        cur = await conn.cursor()
        await cur.execute(
            "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES "
            "WHERE TABLE_TYPE='BASE TABLE' ORDER BY TABLE_NAME"
        )
        table_names = [r[0] for r in await cur.fetchall()]

        for tname in table_names:
            await cur.execute(
                "SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE "
                "FROM INFORMATION_SCHEMA.COLUMNS "
                "WHERE TABLE_NAME=? ORDER BY ORDINAL_POSITION",
                (tname,),
            )
            cols_raw = await cur.fetchall()

            await cur.execute(
                "SELECT ku.COLUMN_NAME "
                "FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc "
                "JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE ku "
                "  ON tc.CONSTRAINT_NAME=ku.CONSTRAINT_NAME "
                "WHERE tc.CONSTRAINT_TYPE='PRIMARY KEY' AND tc.TABLE_NAME=?",
                (tname,),
            )
            pks = {r[0] for r in await cur.fetchall()}

            columns = [
                ColumnInfo(name=r[0], type=r[1], not_null=(r[2] == "NO"), pk=(r[0] in pks))
                for r in cols_raw
            ]

            await cur.execute(f"SELECT COUNT(*) FROM [{tname}]")
            row_count = (await cur.fetchone())[0]

            await cur.execute(f"SELECT TOP 3 * FROM [{tname}]")
            raw = await cur.fetchall()
            col_names = [d[0] for d in cur.description]
            sample = [dict(zip(col_names, r)) for r in raw]

            tables[tname] = TableSchema(
                name=tname, columns=columns,
                sample_rows=sample, row_count=row_count, foreign_keys=[],
            )
    finally:
        conn.close()
    return DBSchema(tables=tables, db_type="mssql")
