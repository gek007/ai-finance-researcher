"""PydanticAI agent for grounded SEC filing answers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from app.assistant.deps import DocumentAgentDeps
from app.assistant.outputs import GroundedAnswer
from app.config import settings
from app.retrieval.retriever import SourcePassage

_INSTRUCTIONS_PATH = Path(__file__).with_name("instructions.md")
_INSTRUCTIONS = _INSTRUCTIONS_PATH.read_text(encoding="utf-8")

_MAX_SURROUNDING = 3


def _passage_payload(passage: SourcePassage) -> dict[str, Any]:
    return {
        "chunk_id": passage.chunk_id,
        "document_id": passage.document_id,
        "chunk_index": passage.chunk_index,
        "text": passage.text,
        "ticker": passage.ticker,
        "company_name": passage.company_name,
        "filing_type": passage.filing_type,
        "filing_date": passage.filing_date,
        "fiscal_year": passage.fiscal_year,
        "accession_number": passage.accession_number,
        "page_label": passage.page_label,
        "source_url": passage.source_url,
    }


def _build_model() -> OpenAIChatModel:
    return OpenAIChatModel(
        settings.openai_chat_model,
        provider=OpenAIProvider(api_key=settings.openai_api_key),
    )


document_agent: Agent[DocumentAgentDeps, GroundedAnswer] = Agent(
    _build_model(),
    deps_type=DocumentAgentDeps,
    output_type=GroundedAnswer,
    instructions=_INSTRUCTIONS,
)


@document_agent.tool
def search_filings(
    ctx: RunContext[DocumentAgentDeps],
    query: str,
) -> list[dict[str, Any]]:
    """Hybrid search over the SEC filing corpus for relevant passages."""
    passages = ctx.deps.remember(ctx.deps.retrieve_passages(query))
    return [_passage_payload(passage) for passage in passages]


@document_agent.tool
def read_chunk(
    ctx: RunContext[DocumentAgentDeps],
    chunk_id: str,
) -> dict[str, Any] | None:
    """Read one filing chunk by ID."""
    passage = ctx.deps.read_chunk(chunk_id)
    if passage is None:
        return None
    ctx.deps.remember([passage])
    return _passage_payload(passage)


@document_agent.tool
def read_surrounding_chunks(
    ctx: RunContext[DocumentAgentDeps],
    chunk_id: str,
    before: int = 1,
    after: int = 1,
) -> list[dict[str, Any]]:
    """Read a chunk and its neighbors in the same filing."""
    before = max(0, min(before, _MAX_SURROUNDING))
    after = max(0, min(after, _MAX_SURROUNDING))
    passages = ctx.deps.remember(
        ctx.deps.read_surrounding_chunks(chunk_id, before, after)
    )
    return [_passage_payload(passage) for passage in passages]


async def run_document_agent(
    question: str,
    deps: DocumentAgentDeps,
) -> GroundedAnswer:
    result = await document_agent.run(question, deps=deps)
    return result.output
