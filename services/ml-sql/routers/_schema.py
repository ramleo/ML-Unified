"""DB schema introspection — SQLite and PostgreSQL."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import aiosqlite


@dataclass
class ColumnInfo:
    name: str
    type: str
    not_null: bool
    pk: bool


@dataclass
class TableSchema:
    name: str
    columns: list[ColumnInfo]
    sample_rows: list[dict]
    row_count: int
    foreign_keys: list[dict]


@dataclass
class DBSchema:
    tables: dict[str, TableSchema]
    db_type: str  # "sqlite" | "postgresql"


async def load_sqlite_schema(db_path: str) -> DBSchema:
    tables: dict[str, TableSchema] = {}
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ) as cur:
            table_names = [row[0] for row in await cur.fetchall()]

        for tname in table_names:
            async with db.execute(f"PRAGMA table_info(\"{tname}\")") as cur:
                cols_raw = await cur.fetchall()
            columns = [
                ColumnInfo(
                    name=r["name"], type=r["type"],
                    not_null=bool(r["notnull"]), pk=bool(r["pk"]),
                )
                for r in cols_raw
            ]

            async with db.execute(f"PRAGMA foreign_key_list(\"{tname}\")") as cur:
                fks_raw = await cur.fetchall()
            fks = [
                {"from_col": r["from"], "to_table": r["table"], "to_col": r["to"]}
                for r in fks_raw
            ]

            async with db.execute(f"SELECT COUNT(*) FROM \"{tname}\"") as cur:
                row_count = (await cur.fetchone())[0]

            async with db.execute(f"SELECT * FROM \"{tname}\" LIMIT 3") as cur:
                sample = [dict(r) for r in await cur.fetchall()]

            tables[tname] = TableSchema(
                name=tname, columns=columns,
                sample_rows=sample, row_count=row_count, foreign_keys=fks,
            )

    return DBSchema(tables=tables, db_type="sqlite")


async def load_pg_schema(conn_str: str) -> DBSchema:
    import asyncpg
    tables: dict[str, TableSchema] = {}
    conn = await asyncpg.connect(conn_str)
    try:
        table_names = await conn.fetch(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' ORDER BY table_name"
        )
        for rec in table_names:
            tname = rec["table_name"]
            cols_raw = await conn.fetch(
                "SELECT column_name, data_type, is_nullable "
                "FROM information_schema.columns "
                "WHERE table_schema='public' AND table_name=$1 ORDER BY ordinal_position",
                tname,
            )
            columns = [
                ColumnInfo(
                    name=r["column_name"], type=r["data_type"],
                    not_null=(r["is_nullable"] == "NO"), pk=False,
                )
                for r in cols_raw
            ]
            pk_rows = await conn.fetch(
                "SELECT kcu.column_name FROM information_schema.table_constraints tc "
                "JOIN information_schema.key_column_usage kcu "
                "  ON tc.constraint_name=kcu.constraint_name "
                "WHERE tc.constraint_type='PRIMARY KEY' AND tc.table_name=$1",
                tname,
            )
            pk_cols = {r["column_name"] for r in pk_rows}
            for c in columns:
                if c.name in pk_cols:
                    c.pk = True

            fk_rows = await conn.fetch(
                "SELECT kcu.column_name, ccu.table_name AS ft, ccu.column_name AS fc "
                "FROM information_schema.table_constraints tc "
                "JOIN information_schema.key_column_usage kcu "
                "  ON tc.constraint_name=kcu.constraint_name "
                "JOIN information_schema.constraint_column_usage ccu "
                "  ON tc.constraint_name=ccu.constraint_name "
                "WHERE tc.constraint_type='FOREIGN KEY' AND tc.table_name=$1",
                tname,
            )
            fks = [
                {"from_col": r["column_name"], "to_table": r["ft"], "to_col": r["fc"]}
                for r in fk_rows
            ]
            count = await conn.fetchval(f'SELECT COUNT(*) FROM "{tname}"')
            sample_raw = await conn.fetch(f'SELECT * FROM "{tname}" LIMIT 3')
            sample = [dict(r) for r in sample_raw]
            tables[tname] = TableSchema(
                name=tname, columns=columns,
                sample_rows=sample, row_count=count, foreign_keys=fks,
            )
    finally:
        await conn.close()
    return DBSchema(tables=tables, db_type="postgresql")


def _tokenize(text: str) -> set[str]:
    return set(re.sub(r"[^a-z0-9 ]", " ", text.lower()).split())

_STOPWORDS = {"the","a","an","is","in","of","for","to","and","or","by","all",
              "what","which","how","many","show","me","get","list","find","give",
              "with","from","per","each","top","average","total","count","number"}


def link_tables(schema: DBSchema, question: str, top_k: int = 6) -> list[str]:
    """Score tables by keyword overlap with question, expand via FK relationships.

    Scoring:
      +3  per question word matching the table name
      +2  per question word matching a column name
      +1  per question word matching a sample cell value
    After picking top_k, add every directly FK-linked table so JOINs work.
    """
    q_words = _tokenize(question) - _STOPWORDS
    if not q_words:
        return list(schema.tables.keys())

    scores: dict[str, float] = {}
    for tname, t in schema.tables.items():
        score = 0.0
        score += 3 * len(q_words & _tokenize(tname))
        for col in t.columns:
            score += 2 * len(q_words & _tokenize(col.name))
        for row in t.sample_rows:
            for val in row.values():
                if val is not None:
                    score += len(q_words & _tokenize(str(val)))
        scores[tname] = score

    ranked = sorted(scores, key=lambda n: scores[n], reverse=True)
    selected = set(ranked[:top_k])

    # FK expansion: include tables directly linked to any selected table
    for tname in list(selected):
        for fk in schema.tables[tname].foreign_keys:
            selected.add(fk["to_table"])
        for other, t in schema.tables.items():
            if any(fk["to_table"] == tname for fk in t.foreign_keys):
                selected.add(other)

    return [n for n in ranked if n in selected] + [
        n for n in schema.tables if n in selected and n not in ranked[:top_k]
    ]


_RAG_THRESHOLD = 20  # use BM25 for DBs larger than this


def _table_doc(t: TableSchema) -> list[str]:
    """Tokenize a table into a BM25 document (name + columns + sample values)."""
    tokens = list(_tokenize(t.name))
    for col in t.columns:
        tokens.extend(_tokenize(col.name))
    for row in t.sample_rows:
        for val in row.values():
            if val is not None:
                tokens.extend(_tokenize(str(val)))
    return tokens or ["__empty__"]


def schema_rag_retrieve(schema: DBSchema, question: str, top_k: int = 8) -> list[str]:
    """BM25 retrieval for large schemas (>20 tables) — returns table names ranked by relevance.

    Builds a BM25 index over table documents (name + columns + sample values), scores
    each table against the question tokens, then expands via FK relationships so JOINs work.
    """
    from rank_bm25 import BM25Okapi

    table_names = list(schema.tables.keys())
    corpus = [_table_doc(schema.tables[n]) for n in table_names]
    bm25 = BM25Okapi(corpus)

    q_tokens = list((_tokenize(question) - _STOPWORDS) or _tokenize(question))
    scores = bm25.get_scores(q_tokens)
    ranked_idx = sorted(range(len(table_names)), key=lambda i: scores[i], reverse=True)
    ranked = [table_names[i] for i in ranked_idx]

    selected = set(ranked[:top_k])
    for tname in list(selected):
        for fk in schema.tables[tname].foreign_keys:
            selected.add(fk["to_table"])
        for other, t in schema.tables.items():
            if any(fk["to_table"] == tname for fk in t.foreign_keys):
                selected.add(other)

    return [n for n in ranked if n in selected] + [
        n for n in schema.tables if n in selected and n not in ranked[:top_k]
    ]


def schema_to_prompt_text(schema: DBSchema, question: str = "", max_tables: int = 30) -> str:
    """Compact schema text for LLM prompt; links relevant tables when question given.

    Small DBs (≤20 tables): keyword overlap scoring via link_tables().
    Large DBs (>20 tables): BM25 retrieval via schema_rag_retrieve().
    """
    if question:
        if len(schema.tables) > _RAG_THRESHOLD:
            linked = schema_rag_retrieve(schema, question, top_k=min(8, len(schema.tables)))
        else:
            linked = link_tables(schema, question, top_k=min(6, len(schema.tables)))
        tables = [schema.tables[n] for n in linked if n in schema.tables]
    else:
        tables = list(schema.tables.values())[:max_tables]

    lines: list[str] = [f"Database type: {schema.db_type}, total tables: {len(schema.tables)}\n"]
    for t in tables:
        lines.append(f"Table: {t.name} ({t.row_count:,} rows)")
        for c in t.columns:
            flags = " [PK]" if c.pk else ""
            lines.append(f"  {c.name}  {c.type}{flags}")
        for fk in t.foreign_keys:
            lines.append(f"  FK: {fk['from_col']} → {fk['to_table']}.{fk['to_col']}")
        if t.sample_rows:
            first = t.sample_rows[0]
            preview = {k: v for k, v in list(first.items())[:5]}
            lines.append(f"  -- sample: {preview}")
        lines.append("")
    return "\n".join(lines)


def schema_to_dict(schema: DBSchema) -> dict:
    return {
        "db_type": schema.db_type,
        "table_count": len(schema.tables),
        "tables": {
            tname: {
                "columns": [
                    {"name": c.name, "type": c.type, "pk": c.pk, "not_null": c.not_null}
                    for c in t.columns
                ],
                "row_count": t.row_count,
                "foreign_keys": t.foreign_keys,
            }
            for tname, t in schema.tables.items()
        },
    }