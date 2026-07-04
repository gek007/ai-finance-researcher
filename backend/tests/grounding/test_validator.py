import pytest

from app.assistant.outputs import AnswerCitation, GroundedAnswer
from app.grounding.validator import GroundingError, validate_grounded_answer
from app.retrieval.retriever import SourcePassage


def _passage(chunk_id: str) -> SourcePassage:
    return SourcePassage(
        chunk_id=chunk_id,
        document_id="doc-1",
        chunk_index=0,
        text=f"{chunk_id} text",
        ticker="AAPL",
        company_name="Apple Inc.",
        filing_type="10-K",
        accession_number="0000320193-24-000123",
        fused_score=1.0,
    )


def test_validate_accepts_known_citations_and_deduplicates() -> None:
    known = {"chunk-1": _passage("chunk-1"), "chunk-2": _passage("chunk-2")}
    answer = GroundedAnswer(
        answer="Revenue grew.",
        citations=[
            AnswerCitation(chunk_id="chunk-1", quote="Revenue grew"),
            AnswerCitation(chunk_id="chunk-1", quote="duplicate"),
            AnswerCitation(chunk_id="chunk-2"),
        ],
    )

    validated = validate_grounded_answer(answer, known)

    assert validated.answer == "Revenue grew."
    assert [citation.chunk_id for citation in validated.citations] == [
        "chunk-1",
        "chunk-2",
    ]
    assert [passage.chunk_id for passage in validated.cited_passages] == [
        "chunk-1",
        "chunk-2",
    ]
    assert validated.insufficient_evidence is False


def test_validate_allows_empty_citations_for_insufficient_evidence() -> None:
    validated = validate_grounded_answer(
        GroundedAnswer(
            answer="The corpus does not contain enough evidence.",
            citations=[],
            insufficient_evidence=True,
        ),
        {},
    )

    assert validated.insufficient_evidence is True
    assert validated.citations == []
    assert validated.cited_passages == []


def test_validate_rejects_missing_citations() -> None:
    with pytest.raises(GroundingError, match="at least one citation"):
        validate_grounded_answer(
            GroundedAnswer(answer="Revenue grew.", citations=[]),
            {"chunk-1": _passage("chunk-1")},
        )


def test_validate_rejects_unknown_chunk_ids() -> None:
    with pytest.raises(GroundingError, match="unknown chunk_id"):
        validate_grounded_answer(
            GroundedAnswer(
                answer="Revenue grew.",
                citations=[AnswerCitation(chunk_id="missing")],
            ),
            {"chunk-1": _passage("chunk-1")},
        )
