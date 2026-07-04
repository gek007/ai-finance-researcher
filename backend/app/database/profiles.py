"""User profile persistence.

`chat_threads.user_id` references `profiles.id`, so every authenticated user needs
a profile row before they can create threads. Profiles are created on first use
via the user-scoped client (RLS: insert/select own).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from supabase import Client


def ensure_profile(
    client: Client, user_id: UUID, email: str | None = None
) -> dict[str, Any]:
    """Idempotently create the caller's profile row."""
    response = (
        client.table("profiles")
        .upsert(
            {"id": str(user_id), "email": email},
            on_conflict="id",
        )
        .execute()
    )
    return response.data[0]
