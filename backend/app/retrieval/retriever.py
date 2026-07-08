"""High-level hybrid retriever used by the assistant layer."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from openai import OpenAI

from app.config import settings
from app.retrieval.fusion import reciprocal_rank_fusion
from app.retrieval.queries import (
    DEFAULT_SEARCH_LIMIT,
    QueryExecutor,
    SearchHit,
    full_text_search,
    get_chunk_by_id,
    get_surrounding_chunks,
    semantic_search,
)

DEFAULT_RETRIEVAL_LIMIT = 8


@dataclass(frozen=True)
class SourcePassage:
    chunk_id: str
    document_id: str
    chunk_index: int
    text: str
    ticker: str
    company_name: str
    filing_type: str
    accession_number: str
    fused_score: float
    page_label: str | None = None
    filing_date: str | None = None
    fiscal_year: int | None = None
    source_url: str | None = None
    token_count: int | None = None
    chunk_metadata: dict[str, Any] | None = None
    document_metadata: dict[str, Any] | None = None

    @classmethod
    def from_hit(cls, hit: SearchHit, fused_score: float) -> "SourcePassage":
        return cls(
            chunk_id=hit.chunk_id,
            document_id=hit.document_id,
            chunk_index=hit.chunk_index,
            text=hit.text,
            ticker=hit.ticker,
            company_name=hit.company_name,
            filing_type=hit.filing_type,
            accession_number=hit.accession_number,
            fused_score=fused_score,
            page_label=hit.page_label,
            filing_date=hit.filing_date,
            fiscal_year=hit.fiscal_year,
            source_url=hit.source_url,
            token_count=hit.token_count,
            chunk_metadata=hit.chunk_metadata,
            document_metadata=hit.document_metadata,
        )


EmbedQuery = Callable[[str], list[float]]


def retrieve_passages(
    query: str,
    *,
    db: QueryExecutor | None = None,
    embed_query: EmbedQuery | None = None,
    semantic_limit: int = DEFAULT_SEARCH_LIMIT,
    keyword_limit: int = DEFAULT_SEARCH_LIMIT,
    limit: int = DEFAULT_RETRIEVAL_LIMIT,
) -> list[SourcePassage]:
    embedding = (embed_query or _embed_query)(query)
    semantic_hits = semantic_search(embedding, db=db, limit=semantic_limit)
    keyword_hits = full_text_search(query, db=db, limit=keyword_limit)

    fused = reciprocal_rank_fusion(
        [semantic_hits, keyword_hits],
        key=lambda hit: hit.chunk_id,
        limit=limit,
    )
    return [
        SourcePassage.from_hit(result.item, fused_score=result.score)
        for result in fused
    ]


def read_chunk(
    chunk_id: str,
    *,
    db: QueryExecutor | None = None,
) -> SourcePassage | None:
    hit = get_chunk_by_id(chunk_id, db=db)
    if hit is None:
        return None
    return SourcePassage.from_hit(hit, fused_score=hit.score)


def read_surrounding_chunks(
    chunk_id: str,
    *,
    before: int = 1,
    after: int = 1,
    db: QueryExecutor | None = None,
) -> list[SourcePassage]:
    hits = get_surrounding_chunks(chunk_id, before=before, after=after, db=db)
    return [SourcePassage.from_hit(hit, fused_score=hit.score) for hit in hits]


def _embed_query(query: str) -> list[float]:
    client = OpenAI(api_key=settings.openai_api_key)
    response = client.embeddings.create(
        model=settings.openai_embedding_model,
        input=query,
        dimensions=settings.openai_embedding_dimensions,
    )
    return response.data[0].embedding
