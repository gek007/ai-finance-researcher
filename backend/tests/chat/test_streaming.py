import asyncio
import json

from app.chat import streaming


def _decode(event: bytes) -> dict | str:
    raw = event.decode().removeprefix("data: ").rstrip("\n")
    return raw if raw == "[DONE]" else json.loads(raw)


def test_stream_text_events_emits_protocol_events_in_order() -> None:
    async def run() -> list[bytes]:
        return [
            chunk
            async for chunk in streaming.stream_text_events("msg-1", "Hello world")
        ]

    events = [_decode(chunk) for chunk in asyncio.run(run())]

    event_types = [event["type"] for event in events]
    assert event_types[0] == "start"
    assert event_types[1] == "start-step"
    assert event_types[2] == "text-start"
    assert event_types[-2] == "text-end"
    assert event_types[-1] == "finish-step"

    deltas = "".join(
        event["delta"]
        for event in events
        if isinstance(event, dict) and event["type"] == "text-delta"
    )
    assert deltas == "Hello world"
    assert events[0]["messageId"] == "msg-1"
    assert events[2]["id"] == "msg-1"


def test_stream_error_emits_error_and_done() -> None:
    async def run() -> list[bytes]:
        return [chunk async for chunk in streaming.stream_error("boom")]

    events = [_decode(chunk) for chunk in asyncio.run(run())]

    assert events[0] == {"type": "error", "errorText": "boom"}
    assert events[1] == "[DONE]"


def test_chunk_text_splits_and_handles_empty() -> None:
    assert streaming.chunk_text("abcdef", size=2) == ["ab", "cd", "ef"]
    assert streaming.chunk_text("", size=2) == [""]
