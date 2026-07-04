"""Ensures assistant citations map to passages known for the current turn."""

from __future__ import annotations

from dataclasses import dataclass

from app.assistant.outputs import AnswerCitation, GroundedAnswer
from app.retrieval.retriever import SourcePassage


class GroundingError(Exception):
    """Raised when an answer fails the grounding contract."""


@dataclass(frozen=True)
class ValidatedAnswer:
    answer: str
    citations: list[AnswerCitation]
    cited_passages: list[SourcePassage]
    insufficient_evidence: bool


def validate_grounded_answer(
    answer: GroundedAnswer,
    known_passages: dict[str, SourcePassage],
) -> ValidatedAnswer:
    if answer.insufficient_evidence:
        return ValidatedAnswer(
            answer=answer.answer,
            citations=[],
            cited_passages=[],
            insufficient_evidence=True,
        )

    if not answer.citations:
        raise GroundingError("Grounded answers must include at least one citation")

    seen_chunk_ids: set[str] = set()
    citations: list[AnswerCitation] = []
    cited_passages: list[SourcePassage] = []

    for citation in answer.citations:
        chunk_id = citation.chunk_id.strip()
        if not chunk_id:
            raise GroundingError("Citation is missing a chunk_id")
        if chunk_id in seen_chunk_ids:
            continue
        passage = known_passages.get(chunk_id)
        if passage is None:
            raise GroundingError(f"Citation references unknown chunk_id: {chunk_id}")
        seen_chunk_ids.add(chunk_id)
        citations.append(AnswerCitation(chunk_id=chunk_id, quote=citation.quote))
        cited_passages.append(passage)

    if not citations:
        raise GroundingError("Grounded answers must include at least one citation")

    return ValidatedAnswer(
        answer=answer.answer,
        citations=citations,
        cited_passages=cited_passages,
        insufficient_evidence=False,
    )
