from typing import Any

from app.retrieval.queries import get_chunk_by_id, get_surrounding_chunks
from app.retrieval.retriever import read_chunk, read_surrounding_chunks


class FakeDb:
    def __init__(self, rows_by_call: list[list[dict[str, Any]]]) -> None:
        self.rows_by_call = list(rows_by_call)
        self.calls: list[tuple[str, dict[str, object]]] = []

    def fetch_all(self, sql: str, params: dict[str, object]) -> list[dict[str, Any]]:
        self.calls.append((sql, params))
        return self.rows_by_call.pop(0)


def test_get_chunk_by_id_queries_uuid_and_returns_hit() -> None:
    db = FakeDb([[_row("chunk-1", chunk_index=4)]])

    hit = get_chunk_by_id("chunk-1", db=db)

    sql, params = db.calls[0]
    assert "WHERE c.id = %(chunk_id)s::uuid" in sql
    assert params == {"chunk_id": "chunk-1"}
    assert hit is not None
    assert hit.chunk_id == "chunk-1"
    assert hit.rank == 1


def test_get_chunk_by_id_returns_none_when_missing() -> None:
    db = FakeDb([[]])

    assert get_chunk_by_id("missing", db=db) is None


def test_get_surrounding_chunks_queries_index_window() -> None:
    anchor = _row("chunk-2", chunk_index=5)
    neighbors = [
        _row("chunk-1", chunk_index=4),
        anchor,
        _row("chunk-3", chunk_index=6),
    ]
    db = FakeDb([[anchor], neighbors])

    hits = get_surrounding_chunks("chunk-2", before=1, after=1, db=db)

    assert [hit.chunk_id for hit in hits] == ["chunk-1", "chunk-2", "chunk-3"]
    surrounding_sql, surrounding_params = db.calls[1]
    assert "c.chunk_index BETWEEN %(min_index)s AND %(max_index)s" in surrounding_sql
    assert surrounding_params == {
        "document_id": "doc-1",
        "min_index": 4,
        "max_index": 6,
    }


def test_read_chunk_and_surrounding_return_source_passages() -> None:
    anchor = _row("chunk-2", chunk_index=5)
    neighbors = [anchor, _row("chunk-3", chunk_index=6)]
    db = FakeDb([[anchor], [anchor], neighbors])

    passage = read_chunk("chunk-2", db=db)
    surrounding = read_surrounding_chunks("chunk-2", before=0, after=1, db=db)

    assert passage is not None
    assert passage.chunk_id == "chunk-2"
    assert passage.ticker == "AAPL"
    assert [item.chunk_id for item in surrounding] == ["chunk-2", "chunk-3"]


def _row(chunk_id: str, *, chunk_index: int) -> dict[str, Any]:
    return {
        "chunk_id": chunk_id,
        "document_id": "doc-1",
        "chunk_index": chunk_index,
        "text": f"{chunk_id} text",
        "page_label": "Item 7",
        "token_count": 4,
        "chunk_metadata": {},
        "ticker": "AAPL",
        "company_name": "Apple Inc.",
        "filing_type": "10-K",
        "filing_date": "2024-11-01",
        "fiscal_year": 2024,
        "accession_number": "0000320193-24-000123",
        "source_url": None,
        "document_metadata": {},
        "score": 1.0,
    }
