from typing import Any

from app.retrieval.queries import full_text_search, semantic_search


class FakeDb:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    def fetch_all(self, sql: str, params: dict[str, object]) -> list[dict[str, Any]]:
        self.calls.append((sql, params))
        return [_row(score=0.8)]


def test_semantic_search_orders_by_vector_distance() -> None:
    db = FakeDb()

    hits = semantic_search([0.1, 0.2], db=db, limit=5)

    sql, params = db.calls[0]
    assert "ORDER BY c.embedding <=>" in sql
    assert params == {"embedding": "[0.1,0.2]", "limit": 5}
    assert hits[0].chunk_id == "chunk-1"
    assert hits[0].score == 0.8
    assert hits[0].rank == 1


def test_full_text_search_uses_generated_search_vector() -> None:
    db = FakeDb()

    hits = full_text_search("revenue growth", db=db, limit=3)

    sql, params = db.calls[0]
    assert "websearch_to_tsquery('english', %(query)s)" in sql
    assert "c.search_vector @@ q" in sql
    assert params == {"query": "revenue growth", "limit": 3}
    assert hits[0].ticker == "AAPL"


def _row(score: float) -> dict[str, Any]:
    return {
        "chunk_id": "chunk-1",
        "document_id": "doc-1",
        "chunk_index": 7,
        "text": "Revenue grew year over year.",
        "page_label": "Item 7",
        "token_count": 5,
        "chunk_metadata": {"section": "MD&A"},
        "ticker": "AAPL",
        "company_name": "Apple Inc.",
        "filing_type": "10-K",
        "filing_date": "2024-11-01",
        "fiscal_year": 2024,
        "accession_number": "0000320193-24-000123",
        "source_url": "https://example.com/filing",
        "document_metadata": {"cik": "0000320193"},
        "score": score,
    }
