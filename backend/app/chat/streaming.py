"""Emits AI SDK UI Message Stream Protocol events over SSE.

Wire format reference: https://ai-sdk.dev/docs/ai-sdk-ui/stream-protocol
Each event is a `data: <json>\\n\\n` line; the stream ends with `data: [DONE]\\n\\n`.
Responses must set the `x-vercel-ai-ui-message-stream: v1` header.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Iterable
from typing import Any

STREAM_HEADERS = {
    "x-vercel-ai-ui-message-stream": "v1",
    "Cache-Control": "no-cache",
}

_CHUNK_SIZE = 20


def sse(data: dict[str, Any]) -> bytes:
    return f"data: {json.dumps(data)}\n\n".encode()


def sse_done() -> bytes:
    return b"data: [DONE]\n\n"


def chunk_text(text: str, size: int = _CHUNK_SIZE) -> list[str]:
    return [text[i : i + size] for i in range(0, len(text), size)] or [text]


async def stream_text_events(
    message_id: str,
    text: str,
    *,
    source_parts: Iterable[dict[str, Any]] | None = None,
) -> AsyncIterator[bytes]:
    """Emit a complete AI SDK text message, optionally with source parts."""
    yield sse({"type": "start", "messageId": message_id})
    yield sse({"type": "start-step"})
    yield sse({"type": "text-start", "id": message_id})

    for chunk in chunk_text(text):
        yield sse({"type": "text-delta", "id": message_id, "delta": chunk})

    yield sse({"type": "text-end", "id": message_id})

    if source_parts:
        for part in source_parts:
            yield sse(part)

    yield sse({"type": "finish-step"})


async def stream_error(error_text: str) -> AsyncIterator[bytes]:
    yield sse({"type": "error", "errorText": error_text})
    yield sse_done()
