"""Coordinates one grounded chat turn end-to-end."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Callable
from typing import Any
from uuid import UUID

from fastapi.concurrency import run_in_threadpool
from supabase import Client

from app.assistant.agent import run_document_agent
from app.assistant.deps import DocumentAgentDeps
from app.assistant.outputs import GroundedAnswer
from app.chat.messages import UIMessage, extract_text
from app.chat.streaming import sse, sse_done, stream_error, stream_text_events
from app.database import chats
from app.database.supabase import get_admin_client
from app.grounding.validator import GroundingError, ValidatedAnswer, validate_grounded_answer
from app.retrieval.retriever import (
    SourcePassage,
    read_chunk,
    read_surrounding_chunks,
    retrieve_passages,
)

RunAgent = Callable[[str, DocumentAgentDeps], Any]
ValidateAnswer = Callable[[GroundedAnswer, dict[str, SourcePassage]], ValidatedAnswer]


def _passage_for_json(passage: SourcePassage) -> dict[str, Any]:
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


def _assistant_message_json(
    message_id: str,
    answer: ValidatedAnswer,
) -> dict[str, Any]:
    parts: list[dict[str, Any]] = [{"type": "text", "text": answer.answer}]
    for index, passage in enumerate(answer.cited_passages):
        citation = answer.citations[index]
        parts.append(
            {
                "type": "source-document",
                "sourceId": passage.chunk_id,
                "mediaType": "text/plain",
                "title": (
                    f"{passage.ticker} {passage.filing_type}"
                    f" ({passage.filing_date or passage.fiscal_year or 'n/a'})"
                ),
                "providerMetadata": {
                    "excerpt": citation.quote or passage.text[:280],
                    "passage": _passage_for_json(passage),
                },
            }
        )
    return {
        "id": message_id,
        "role": "assistant",
        "parts": parts,
        "citations": [
            {
                "chunk_id": citation.chunk_id,
                "quote": citation.quote,
                "passage": _passage_for_json(passage),
            }
            for citation, passage in zip(
                answer.citations, answer.cited_passages, strict=True
            )
        ],
        "insufficient_evidence": answer.insufficient_evidence,
    }


def _build_deps(user_id: UUID, thread_id: UUID) -> DocumentAgentDeps:
    return DocumentAgentDeps(
        user_id=str(user_id),
        thread_id=str(thread_id),
        retrieve_passages=lambda query: retrieve_passages(query),
        read_chunk=lambda chunk_id: read_chunk(chunk_id),
        read_surrounding_chunks=lambda chunk_id, before, after: read_surrounding_chunks(
            chunk_id, before=before, after=after
        ),
    )


def _persist_turn(
    user_client: Client,
    admin_client: Client,
    thread_id: UUID,
    user_message: UIMessage,
    assistant_message_id: str,
    answer: ValidatedAnswer,
) -> None:
    chats.append_message(
        user_client,
        thread_id=thread_id,
        role="user",
        content=extract_text(user_message),
        message_json=user_message.model_dump(mode="json"),
    )
    chats.append_message(
        user_client,
        thread_id=thread_id,
        role="assistant",
        content=answer.answer,
        message_json=_assistant_message_json(assistant_message_id, answer),
        message_id=assistant_message_id,
    )
    if answer.citations:
        chats.append_citations(
            admin_client,
            assistant_message_id,
            [
                {"chunk_id": citation.chunk_id, "quote": citation.quote}
                for citation in answer.citations
            ],
        )
    chats.touch_thread(user_client, thread_id)


async def stream_grounded_reply(
    user_client: Client,
    user_id: UUID,
    thread_id: UUID,
    user_message: UIMessage,
    *,
    run_agent: RunAgent = run_document_agent,
    validate_answer: ValidateAnswer = validate_grounded_answer,
    admin_client: Client | None = None,
) -> AsyncIterator[bytes]:
    question = extract_text(user_message).strip()
    if not question:
        async for event in stream_error("Message text is required"):
            yield event
        return

    assistant_message_id = str(uuid.uuid4())
    deps = _build_deps(user_id, thread_id)

    try:
        grounded = await run_agent(question, deps)
        validated = validate_answer(grounded, deps.known_passages)
    except GroundingError as exc:
        async for event in stream_error(str(exc)):
            yield event
        return
    except Exception:
        async for event in stream_error("Failed to generate grounded answer"):
            yield event
        return

    # Persist before streaming: the full answer is already available, so
    # stream-then-persist only creates "saw answer, refresh lost it" cases.
    try:
        await run_in_threadpool(
            _persist_turn,
            user_client,
            admin_client or get_admin_client(),
            thread_id,
            user_message,
            assistant_message_id,
            validated,
        )
    except Exception:
        async for event in stream_error("Failed to save chat message"):
            yield event
        return

    async for event in stream_text_events(assistant_message_id, validated.answer):
        yield event

    yield sse({"type": "finish"})
    yield sse_done()
