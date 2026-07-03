import asyncio
import json
import uuid
from unittest.mock import MagicMock

from app.chat import streaming
from app.chat.messages import UIMessage


def _decode(event: bytes) -> dict | str:
    raw = event.decode().removeprefix("data: ").rstrip("\n")
    return raw if raw == "[DONE]" else json.loads(raw)


def _collect(client, thread_id, user_message) -> list[dict | str]:
    async def run() -> list[bytes]:
        return [
            chunk
            async for chunk in streaming.stream_stub_reply(
                client, thread_id, user_message
            )
        ]

    return [_decode(chunk) for chunk in asyncio.run(run())]


def test_stream_stub_reply_emits_protocol_events_in_order(monkeypatch) -> None:
    persisted = []
    monkeypatch.setattr(
        streaming.chats,
        "append_message",
        lambda *args, **kwargs: persisted.append(kwargs | {"args": args}),
    )
    monkeypatch.setattr(streaming.chats, "touch_thread", lambda *args, **kwargs: None)

    thread_id = uuid.uuid4()
    user_message = UIMessage.model_validate(
        {"id": "msg_1", "role": "user", "parts": [{"type": "text", "text": "Hi"}]}
    )

    events = _collect(MagicMock(), thread_id, user_message)

    event_types = [event["type"] for event in events[:-1]]  # last is "[DONE]"
    assert event_types[0] == "start"
    assert event_types[1] == "start-step"
    assert event_types[2] == "text-start"
    assert event_types[-3] == "text-end"
    assert event_types[-2] == "finish-step"
    assert event_types[-1] == "finish"
    assert events[-1] == "[DONE]"

    # text deltas concatenate back to the full stub reply
    deltas = "".join(
        e["delta"] for e in events if isinstance(e, dict) and e["type"] == "text-delta"
    )
    assert deltas == streaming.STUB_REPLY_TEXT

    # the same message id is used for start/text-start/text-end
    message_id = events[0]["messageId"]
    assert events[2]["id"] == message_id
    assert event_types.count("text-end") == 1


def test_stream_stub_reply_persists_user_and_assistant_messages(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(
        streaming.chats,
        "append_message",
        lambda client, thread_id, **kwargs: calls.append(kwargs),
    )
    touched = []
    monkeypatch.setattr(
        streaming.chats, "touch_thread", lambda client, thread_id: touched.append(thread_id)
    )

    thread_id = uuid.uuid4()
    user_message = UIMessage.model_validate(
        {
            "id": "msg_1",
            "role": "user",
            "parts": [{"type": "text", "text": "What was Apple's revenue?"}],
        }
    )

    _collect(MagicMock(), thread_id, user_message)

    assert len(calls) == 2
    assert calls[0]["role"] == "user"
    assert calls[0]["content"] == "What was Apple's revenue?"
    assert calls[1]["role"] == "assistant"
    assert calls[1]["content"] == streaming.STUB_REPLY_TEXT
    assert touched == [thread_id]


def test_stream_stub_reply_emits_error_event_when_persistence_fails(
    monkeypatch,
) -> None:
    def failing_append(*args, **kwargs):
        raise RuntimeError("db unavailable")

    monkeypatch.setattr(streaming.chats, "append_message", failing_append)

    thread_id = uuid.uuid4()
    user_message = UIMessage.model_validate(
        {"id": "msg_1", "role": "user", "parts": [{"type": "text", "text": "Hi"}]}
    )

    events = _collect(MagicMock(), thread_id, user_message)

    assert events[-2]["type"] == "error"
    assert events[-1] == "[DONE]"
    assert not any(e == {"type": "finish"} for e in events if isinstance(e, dict))
