"""Typed agent output models for grounded answers."""

from __future__ import annotations

from pydantic import BaseModel, Field


class AnswerCitation(BaseModel):
    chunk_id: str = Field(description="ID of a retrieved or tool-read passage.")
    quote: str | None = Field(
        default=None,
        description="Short excerpt from the passage that supports the claim.",
    )


class GroundedAnswer(BaseModel):
    answer: str = Field(description="Analyst-facing answer text.")
    citations: list[AnswerCitation] = Field(default_factory=list)
    insufficient_evidence: bool = Field(
        default=False,
        description=(
            "True when the corpus does not contain enough evidence to answer. "
            "When true, citations may be empty."
        ),
    )
