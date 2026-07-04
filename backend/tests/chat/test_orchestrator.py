import asyncio
import json
import uuid
from unittest.mock import MagicMock

from app.assistant.deps import DocumentAgentDeps
from app.assistant.outputs import AnswerCitation, GroundedAnswer
from app.chat import orchestrator
from app.chat.messages import UIMessage
from app.retrieval.retriever import SourcePassage


def _decode(event: bytes) -> dict | str:
    raw = event.decode().removeprefix("data: ").rstrip("\n")
    return raw if raw == "[DONE]" else json.loads(raw)


def _passage(chunk_id: str = "chunk-1") -> SourcePassage:
    return SourcePassage(
        chunk_id=chunk_id,
        document_id="doc-1",
        chunk_index=0,
        text="Revenue grew year over year.",
        ticker="AAPL",
        company_name="Apple Inc.",
        filing_type="10-K",
        accession_number="0000320193-24-000123",
        fused_score=1.0,
        filing_date="2024-11-01",
    )


def _user_message(text: str = "What was Apple revenue?") -> UIMessage:
    return UIMessage.model_validate(
        {
            "id": "msg_1",
            "role": "user",
            "parts": [{"type": "text", "text": text}],
        }
    )


def _collect(
    *,
    run_agent,
    user_message: UIMessage | None = None,
    fail_persist: bool = False,
) -> tuple[list[dict | str], list[dict], list[dict]]:
    message_calls: list[dict] = []
    citation_calls: list[dict] = []
    touched: list[uuid.UUID] = []

    def append_message(client, thread_id, **kwargs):
        if fail_persist:
            raise RuntimeError("db unavailable")
        message_calls.append(kwargs)
        return {"id": kwargs.get("message_id") or str(uuid.uuid4())}

    def append_citations(client, message_id, citations):
        citation_calls.append(
            {"message_id": message_id, "citations": citations}
        )
        return citations

    async def run() -> list[bytes]:
        return [
            chunk
            async for chunk in orchestrator.stream_grounded_reply(
                MagicMock(),
                uuid.uuid4(),
                uuid.uuid4(),
                user_message or _user_message(),
                run_agent=run_agent,
                admin_client=MagicMock(),
            )
        ]

    monkeypatch_targets = (
        (orchestrator.chats, "append_message", append_message),
        (orchestrator.chats, "append_citations", append_citations),
        (
            orchestrator.chats,
            "touch_thread",
            lambda client, thread_id: touched.append(thread_id),
        ),
    )
    originals = []
    for owner, name, value in monkeypatch_targets:
        originals.append((owner, name, getattr(owner, name)))
        setattr(owner, name, value)

    try:
        events = [_decode(chunk) for chunk in asyncio.run(run())]
    finally:
        for owner, name, value in originals:
            setattr(owner, name, value)

    return events, message_calls, citation_calls


def test_stream_grounded_reply_persists_then_streams_cited_answer() -> None:
    passage = _passage()

    async def run_agent(question: str, deps: DocumentAgentDeps) -> GroundedAnswer:
        deps.remember([passage])
        return GroundedAnswer(
            answer="Apple revenue grew.",
            citations=[AnswerCitation(chunk_id=passage.chunk_id, quote="Revenue grew")],
        )

    events, messages, citations = _collect(run_agent=run_agent)

    event_types = [event["type"] for event in events[:-1]]
    assert event_types[0] == "start"
    assert event_types[-1] == "finish"
    assert events[-1] == "[DONE]"

    deltas = "".join(
        event["delta"]
        for event in events
        if isinstance(event, dict) and event["type"] == "text-delta"
    )
    assert deltas == "Apple revenue grew."

    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[1]["role"] == "assistant"
    assert messages[1]["content"] == "Apple revenue grew."
    assert messages[1]["message_json"]["citations"][0]["chunk_id"] == "chunk-1"
    assert citations[0]["citations"][0]["chunk_id"] == "chunk-1"


def test_stream_grounded_reply_emits_error_on_grounding_failure() -> None:
    async def run_agent(question: str, deps: DocumentAgentDeps) -> GroundedAnswer:
        # Real validator rejects unknown chunk ids and missing citations.
        return GroundedAnswer(
            answer="Unsupported claim.",
            citations=[AnswerCitation(chunk_id="missing-chunk")],
        )

    events, messages, citations = _collect(run_agent=run_agent)

    assert events[0]["type"] == "error"
    assert "unknown chunk_id" in events[0]["errorText"]
    assert events[1] == "[DONE]"
    assert messages == []
    assert citations == []


def test_stream_grounded_reply_persists_insufficient_evidence_without_citations() -> None:
    async def run_agent(question: str, deps: DocumentAgentDeps) -> GroundedAnswer:
        return GroundedAnswer(
            answer="The corpus does not contain enough evidence.",
            citations=[],
            insufficient_evidence=True,
        )

    events, messages, citations = _collect(run_agent=run_agent)

    deltas = "".join(
        event["delta"]
        for event in events
        if isinstance(event, dict) and event["type"] == "text-delta"
    )
    assert "enough evidence" in deltas
    assert len(messages) == 2
    assert messages[1]["message_json"]["insufficient_evidence"] is True
    assert messages[1]["message_json"]["citations"] == []
    assert citations == []


def test_stream_grounded_reply_errors_before_streaming_when_persist_fails() -> None:
    passage = _passage()

    async def run_agent(question: str, deps: DocumentAgentDeps) -> GroundedAnswer:
        deps.remember([passage])
        return GroundedAnswer(
            answer="Apple revenue grew.",
            citations=[AnswerCitation(chunk_id=passage.chunk_id)],
        )

    events, messages, citations = _collect(run_agent=run_agent, fail_persist=True)

    assert events[0] == {"type": "error", "errorText": "Failed to save chat message"}
    assert events[1] == "[DONE]"
    assert not any(
        isinstance(event, dict) and event.get("type") == "text-delta" for event in events
    )
    assert messages == []
    assert citations == []


def test_stream_grounded_reply_rejects_empty_question() -> None:
    async def run_agent(question: str, deps: DocumentAgentDeps) -> GroundedAnswer:
        raise AssertionError("agent should not run")

    events, messages, citations = _collect(
        run_agent=run_agent,
        user_message=_user_message("   "),
    )

    assert events[0] == {"type": "error", "errorText": "Message text is required"}
    assert messages == []
    assert citations == []
