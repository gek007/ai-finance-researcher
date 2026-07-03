"""Emits AI SDK UI Message Stream Protocol events over SSE.

Wire format reference: https://ai-sdk.dev/docs/ai-sdk-ui/stream-protocol
Each event is a `data: <json>\\n\\n` line; the stream ends with `data: [DONE]\\n\\n`.
Responses must set the `x-vercel-ai-ui-message-stream: v1` header.

This module only produces a stubbed reply (Phase 4). `app/chat/orchestrator.py`
will replace `stream_stub_reply` with a real agent-backed stream in a later phase.
"""

import asyncio
import json
import uuid
from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID

from fastapi.concurrency import run_in_threadpool
from supabase import Client

from app.chat.messages import UIMessage, extract_text
from app.database import chats

STREAM_HEADERS = {
    "x-vercel-ai-ui-message-stream": "v1",
    "Cache-Control": "no-cache",
}

STUB_REPLY_TEXT = (
    "This is a placeholder reply from Document Copilot. Grounded, cited answers "
    "from the filing corpus will replace this once retrieval and the assistant "
    "agent are wired up in a later phase."
)

_CHUNK_SIZE = 20
_CHUNK_DELAY_SECONDS = 0.02


def _sse(data: dict[str, Any]) -> bytes:
    return f"data: {json.dumps(data)}\n\n".encode()


def _sse_done() -> bytes:
    return b"data: [DONE]\n\n"


def _chunk_text(text: str, size: int) -> list[str]:
    return [text[i : i + size] for i in range(0, len(text), size)] or [text]


async def stream_stub_reply(
    client: Client,
    thread_id: UUID,
    user_message: UIMessage,
) -> AsyncIterator[bytes]:
    assistant_message_id = str(uuid.uuid4())

    yield _sse({"type": "start", "messageId": assistant_message_id})
    yield _sse({"type": "start-step"})
    yield _sse({"type": "text-start", "id": assistant_message_id})

    for chunk in _chunk_text(STUB_REPLY_TEXT, _CHUNK_SIZE):
        yield _sse({"type": "text-delta", "id": assistant_message_id, "delta": chunk})
        await asyncio.sleep(_CHUNK_DELAY_SECONDS)

    yield _sse({"type": "text-end", "id": assistant_message_id})
    yield _sse({"type": "finish-step"})

    try:
        await run_in_threadpool(
            _persist_turn, client, thread_id, user_message, assistant_message_id
        )
    except Exception:
        # Headers are already sent at this point, so a failed write can only be
        # reported as a stream error part, not an HTTP error response.
        yield _sse({"type": "error", "errorText": "Failed to save chat message"})
        yield _sse_done()
        return

    yield _sse({"type": "finish"})
    yield _sse_done()


def _persist_turn(
    client: Client,
    thread_id: UUID,
    user_message: UIMessage,
    assistant_message_id: str,
) -> None:
    # `user_message.id` is a client-generated id (not guaranteed to be a UUID),
    # so it is kept in `message_json` only; storage uses a fresh server-side id.
    chats.append_message(
        client,
        thread_id=thread_id,
        role="user",
        content=extract_text(user_message),
        message_json=user_message.model_dump(mode="json"),
    )
    chats.append_message(
        client,
        thread_id=thread_id,
        role="assistant",
        content=STUB_REPLY_TEXT,
        message_json={
            "id": assistant_message_id,
            "role": "assistant",
            "parts": [{"type": "text", "text": STUB_REPLY_TEXT}],
        },
        message_id=assistant_message_id,
    )
    chats.touch_thread(client, thread_id)
