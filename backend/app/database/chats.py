"""Chat thread and message persistence.

Runtime reads/writes go through the user-scoped Supabase (PostgREST) client so
Row Level Security enforces per-user ownership — see the `chat_threads_owner`
and `chat_messages_owner` policies in the initial migration. SQLAlchemy models
in `app/database/models.py` describe the schema for Alembic only; they are not
used for runtime queries.

Because writes go through PostgREST instead of SQLAlchemy, the Python-side
`default=uuid.uuid4` on the ORM models does not apply here — ids must be
generated explicitly before insert.
"""

import uuid
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from supabase import Client

DEFAULT_THREAD_TITLE = "New chat"


def list_threads(client: Client) -> list[dict[str, Any]]:
    response = (
        client.table("chat_threads")
        .select("*")
        .order("updated_at", desc=True)
        .execute()
    )
    return response.data


def create_thread(
    client: Client, user_id: UUID, title: str = DEFAULT_THREAD_TITLE
) -> dict[str, Any]:
    response = (
        client.table("chat_threads")
        .insert({"id": str(uuid.uuid4()), "user_id": str(user_id), "title": title})
        .execute()
    )
    return response.data[0]


def get_thread(client: Client, thread_id: UUID) -> dict[str, Any] | None:
    response = (
        client.table("chat_threads")
        .select("*")
        .eq("id", str(thread_id))
        .maybe_single()
        .execute()
    )
    return response.data if response is not None else None


def touch_thread(client: Client, thread_id: UUID) -> None:
    client.table("chat_threads").update(
        {"updated_at": datetime.now(UTC).isoformat()}
    ).eq("id", str(thread_id)).execute()


def list_messages(client: Client, thread_id: UUID) -> list[dict[str, Any]]:
    response = (
        client.table("chat_messages")
        .select("*")
        .eq("thread_id", str(thread_id))
        .order("sort_order")
        .execute()
    )
    return response.data


def append_message(
    client: Client,
    thread_id: UUID,
    role: str,
    content: str,
    message_json: dict[str, Any] | None = None,
    message_id: UUID | str | None = None,
) -> dict[str, Any]:
    sort_order = _next_sort_order(client, thread_id)
    payload = {
        "id": str(message_id) if message_id else str(uuid.uuid4()),
        "thread_id": str(thread_id),
        "role": role,
        "content": content,
        "message_json": message_json,
        "sort_order": sort_order,
    }
    response = client.table("chat_messages").insert(payload).execute()
    return response.data[0]


def append_citations(
    client: Client,
    message_id: UUID | str,
    citations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Insert citation rows for an assistant message.

    Uses a privileged client because RLS only grants owners SELECT on
    `message_citations`. Callers must already have validated ownership of the
    parent message.
    """
    if not citations:
        return []

    payloads = [
        {
            "id": str(uuid.uuid4()),
            "message_id": str(message_id),
            "chunk_id": str(citation["chunk_id"]),
            "citation_index": index,
            "quote": citation.get("quote"),
        }
        for index, citation in enumerate(citations)
    ]
    response = client.table("message_citations").insert(payloads).execute()
    return response.data


def _next_sort_order(client: Client, thread_id: UUID) -> int:
    response = (
        client.table("chat_messages")
        .select("sort_order")
        .eq("thread_id", str(thread_id))
        .order("sort_order", desc=True)
        .limit(1)
        .execute()
    )
    if not response.data:
        return 0
    return response.data[0]["sort_order"] + 1
