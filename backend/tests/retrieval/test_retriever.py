from typing import Any

from app.retrieval.retriever import retrieve_passages


class FakeDb:
    def fetch_all(self, sql: str, params: dict[str, object]) -> list[dict[str, Any]]:
        if "c.embedding <=>" in sql:
            return [_row("shared", score=0.9), _row("semantic-only", score=0.7)]
        return [_row("shared", score=0.8), _row("keyword-only", score=0.6)]


def test_retrieve_passages_embeds_query_and_fuses_search_results() -> None:
    passages = retrieve_passages(
        "What drove Apple revenue?",
        db=FakeDb(),
        embed_query=lambda query: [0.1, 0.2],
        semantic_limit=2,
        keyword_limit=2,
        limit=2,
    )

    assert [passage.chunk_id for passage in passages] == ["shared", "semantic-only"]
    assert passages[0].ticker == "AAPL"
    assert passages[0].fused_score > passages[1].fused_score


def _row(chunk_id: str, score: float) -> dict[str, Any]:
    return {
        "chunk_id": chunk_id,
        "document_id": "doc-1",
        "chunk_index": 0,
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
        "score": score,
    }
