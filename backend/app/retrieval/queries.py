"""Postgres query helpers for semantic and full-text retrieval."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

import psycopg
from psycopg.rows import dict_row

from app.config import settings

DEFAULT_SEARCH_LIMIT = 20

_PASSAGE_COLUMNS = """
    c.id AS chunk_id,
    c.document_id,
    c.chunk_index,
    c.text,
    c.page_label,
    c.token_count,
    c.metadata AS chunk_metadata,
    d.ticker,
    d.company_name,
    d.filing_type,
    d.filing_date,
    d.fiscal_year,
    d.accession_number,
    d.source_url,
    d.metadata AS document_metadata
"""

_PASSAGE_FROM = """
FROM document_chunks c
JOIN source_documents d ON d.id = c.document_id
"""


class QueryExecutor(Protocol):
    def fetch_all(self, sql: str, params: Mapping[str, object]) -> list[dict[str, Any]]:
        """Return all rows for a parameterized SQL statement."""


@dataclass(frozen=True)
class SearchHit:
    chunk_id: str
    document_id: str
    chunk_index: int
    text: str
    page_label: str | None
    token_count: int | None
    chunk_metadata: dict[str, Any]
    ticker: str
    company_name: str
    filing_type: str
    filing_date: str | None
    fiscal_year: int | None
    accession_number: str
    source_url: str | None
    document_metadata: dict[str, Any]
    score: float
    rank: int

    @classmethod
    def from_row(cls, row: Mapping[str, Any], rank: int) -> "SearchHit":
        filing_date = row.get("filing_date")
        return cls(
            chunk_id=str(row["chunk_id"]),
            document_id=str(row["document_id"]),
            chunk_index=row["chunk_index"],
            text=row["text"],
            page_label=row.get("page_label"),
            token_count=row.get("token_count"),
            chunk_metadata=row.get("chunk_metadata") or {},
            ticker=row["ticker"],
            company_name=row["company_name"],
            filing_type=row["filing_type"],
            filing_date=(
                filing_date.isoformat()
                if hasattr(filing_date, "isoformat")
                else filing_date
            ),
            fiscal_year=row.get("fiscal_year"),
            accession_number=row["accession_number"],
            source_url=row.get("source_url"),
            document_metadata=row.get("document_metadata") or {},
            score=float(row["score"]),
            rank=rank,
        )


class PsycopgQueryExecutor:
    def fetch_all(self, sql: str, params: Mapping[str, object]) -> list[dict[str, Any]]:
        with psycopg.connect(settings.database_url, row_factory=dict_row) as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql, params)
                return list(cursor.fetchall())


def semantic_search(
    embedding: Sequence[float],
    *,
    db: QueryExecutor | None = None,
    limit: int = DEFAULT_SEARCH_LIMIT,
) -> list[SearchHit]:
    sql = f"""
SELECT
{_PASSAGE_COLUMNS},
    1 - (c.embedding <=> %(embedding)s::vector) AS score
{_PASSAGE_FROM}
WHERE c.embedding IS NOT NULL
ORDER BY c.embedding <=> %(embedding)s::vector
LIMIT %(limit)s
"""
    rows = (db or PsycopgQueryExecutor()).fetch_all(
        sql,
        {"embedding": _vector_literal(embedding), "limit": limit},
    )
    return _ranked_hits(rows)


def full_text_search(
    query: str,
    *,
    db: QueryExecutor | None = None,
    limit: int = DEFAULT_SEARCH_LIMIT,
) -> list[SearchHit]:
    sql = f"""
SELECT
{_PASSAGE_COLUMNS},
    ts_rank_cd(c.search_vector, q) AS score
{_PASSAGE_FROM},
websearch_to_tsquery('english', %(query)s) q
WHERE c.search_vector @@ q
ORDER BY ts_rank_cd(c.search_vector, q) DESC
LIMIT %(limit)s
"""
    rows = (db or PsycopgQueryExecutor()).fetch_all(sql, {"query": query, "limit": limit})
    return _ranked_hits(rows)


def _ranked_hits(rows: list[dict[str, Any]]) -> list[SearchHit]:
    return [SearchHit.from_row(row, rank=index + 1) for index, row in enumerate(rows)]


def _vector_literal(embedding: Sequence[float]) -> str:
    return "[" + ",".join(str(float(value)) for value in embedding) + "]"
